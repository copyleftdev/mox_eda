# RFC-0003: Consensus & Replication

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

Mox uses Raft for consensus with Viewstamped Replication (VR) extensions for view changes and state transfer. This combination provides strong consistency, fault tolerance, and efficient reconfiguration.

## Why Raft + VR?

**Raft** provides:
- Understandable leader election
- Simple log replication
- Strong safety guarantees

**Viewstamped Replication** adds:
- Efficient view change protocol
- State transfer for lagging replicas
- Better reconfiguration semantics

Together, they give us a consensus layer that is both correct and practical.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CONSENSUS LAYER                                    │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                              RAFT CORE                                    │ │
│  │                                                                           │ │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │ │
│  │   │   Leader    │  │  Candidate  │  │  Follower   │  │   Learner   │     │ │
│  │   │   State     │  │   State     │  │   State     │  │   State     │     │ │
│  │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │ │
│  │          │                │                │                │            │ │
│  │          └────────────────┴────────────────┴────────────────┘            │ │
│  │                                   │                                       │ │
│  │                                   ▼                                       │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    State Machine                                │    │ │
│  │   │  • Leader: Accept commands, replicate, apply                    │    │ │
│  │   │  • Follower: Accept replicated entries, apply                   │    │ │
│  │   │  • Candidate: Request votes, become leader/follower             │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                    VIEWSTAMPED REPLICATION EXTENSIONS                     │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                 View Change Protocol                            │    │ │
│  │   │  • Faster leader failover                                       │    │ │
│  │   │  • Guaranteed progress during partition healing                 │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                 State Transfer                                  │    │ │
│  │   │  • Snapshot-based catch-up for lagging replicas                 │    │ │
│  │   │  • Incremental transfer for small gaps                          │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                 Reconfiguration                                 │    │ │
│  │   │  • Add/remove nodes without downtime                            │    │ │
│  │   │  • Joint consensus for safety                                   │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                         NETWORK LAYER                                     │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │  RPC: AppendEntries | RequestVote | InstallSnapshot | ...       │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │  Transport: TCP with checksums, connection pooling, backoff     │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Raft State Machine

```rust
// src/consensus/raft.rs

use std::time::Duration;
use tokio::sync::{mpsc, oneshot};

/// Raft node states
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum State {
    Follower,
    Candidate,
    Leader,
    Learner,  // Non-voting member (for state transfer)
}

/// Persistent state (must survive restarts)
#[derive(Debug, Clone)]
pub struct PersistentState {
    /// Current term
    pub current_term: u64,
    /// Candidate that received vote in current term
    pub voted_for: Option<NodeId>,
    /// Log entries
    pub log: Vec<LogEntry>,
}

/// Volatile state (can be reconstructed)
#[derive(Debug, Clone)]
pub struct VolatileState {
    /// Index of highest log entry known to be committed
    pub commit_index: u64,
    /// Index of highest log entry applied to state machine
    pub last_applied: u64,
}

/// Leader-only volatile state
#[derive(Debug, Clone)]
pub struct LeaderState {
    /// For each server, index of next log entry to send
    pub next_index: HashMap<NodeId, u64>,
    /// For each server, index of highest log entry known to be replicated
    pub match_index: HashMap<NodeId, u64>,
}

/// The Raft node
pub struct RaftNode<I: IO, S: StateMachine> {
    // Identity
    id: NodeId,
    cluster: ClusterConfig,
    
    // I/O abstraction
    io: I,
    
    // State
    state: State,
    persistent: PersistentState,
    volatile: VolatileState,
    leader_state: Option<LeaderState>,
    
    // Timers
    election_timeout: Duration,
    heartbeat_interval: Duration,
    last_heartbeat: Instant,
    
    // State machine
    state_machine: S,
    
    // Channels
    command_rx: mpsc::Receiver<Command>,
    rpc_rx: mpsc::Receiver<RpcMessage>,
    
    // Metrics
    metrics: RaftMetrics,
}

impl<I: IO, S: StateMachine> RaftNode<I, S> {
    /// Main event loop
    pub async fn run(&mut self) -> Result<()> {
        loop {
            match self.state {
                State::Follower => self.run_follower().await?,
                State::Candidate => self.run_candidate().await?,
                State::Leader => self.run_leader().await?,
                State::Learner => self.run_learner().await?,
            }
        }
    }
    
    /// Follower event loop
    async fn run_follower(&mut self) -> Result<()> {
        let timeout = self.randomized_election_timeout();
        
        loop {
            tokio::select! {
                // Election timeout
                _ = self.io.sleep(timeout) => {
                    if self.io.now().duration_since(self.last_heartbeat) > timeout {
                        // Transition to candidate
                        self.state = State::Candidate;
                        return Ok(());
                    }
                }
                
                // Incoming RPC
                Some(rpc) = self.rpc_rx.recv() => {
                    match rpc {
                        RpcMessage::AppendEntries(req, reply) => {
                            let resp = self.handle_append_entries(req).await?;
                            let _ = reply.send(resp);
                        }
                        RpcMessage::RequestVote(req, reply) => {
                            let resp = self.handle_request_vote(req).await?;
                            let _ = reply.send(resp);
                        }
                        RpcMessage::InstallSnapshot(req, reply) => {
                            let resp = self.handle_install_snapshot(req).await?;
                            let _ = reply.send(resp);
                        }
                    }
                }
                
                // Client command (forward to leader)
                Some(cmd) = self.command_rx.recv() => {
                    if let Some(leader_id) = self.current_leader() {
                        cmd.reply.send(Err(RaftError::NotLeader(leader_id)));
                    } else {
                        cmd.reply.send(Err(RaftError::NoLeader));
                    }
                }
            }
        }
    }
    
    /// Candidate event loop
    async fn run_candidate(&mut self) -> Result<()> {
        // Increment term
        self.persistent.current_term += 1;
        let term = self.persistent.current_term;
        
        // Vote for self
        self.persistent.voted_for = Some(self.id);
        self.persist_state().await?;
        
        // Request votes from all peers
        let (last_log_index, last_log_term) = self.last_log_info();
        let mut votes_received = 1; // Self vote
        let votes_needed = self.cluster.quorum_size();
        
        let mut vote_futures = FuturesUnordered::new();
        for peer in self.cluster.peers() {
            if peer != self.id {
                vote_futures.push(self.send_request_vote(
                    peer,
                    RequestVote {
                        term,
                        candidate_id: self.id,
                        last_log_index,
                        last_log_term,
                    },
                ));
            }
        }
        
        let timeout = self.randomized_election_timeout();
        let deadline = self.io.now() + timeout;
        
        loop {
            tokio::select! {
                // Election timeout (start new election)
                _ = self.io.sleep_until(deadline) => {
                    // Stay candidate, will restart election
                    return Ok(());
                }
                
                // Vote response
                Some(result) = vote_futures.next() => {
                    if let Ok(resp) = result {
                        if resp.term > self.persistent.current_term {
                            // Higher term, revert to follower
                            self.persistent.current_term = resp.term;
                            self.persistent.voted_for = None;
                            self.persist_state().await?;
                            self.state = State::Follower;
                            return Ok(());
                        }
                        
                        if resp.vote_granted {
                            votes_received += 1;
                            if votes_received >= votes_needed {
                                // Won election!
                                self.become_leader().await?;
                                return Ok(());
                            }
                        }
                    }
                }
                
                // Incoming RPC (might be from new leader)
                Some(rpc) = self.rpc_rx.recv() => {
                    match rpc {
                        RpcMessage::AppendEntries(req, reply) => {
                            if req.term >= self.persistent.current_term {
                                // Legitimate leader, revert to follower
                                self.persistent.current_term = req.term;
                                self.persistent.voted_for = None;
                                self.persist_state().await?;
                                self.state = State::Follower;
                                
                                let resp = self.handle_append_entries(req).await?;
                                let _ = reply.send(resp);
                                return Ok(());
                            }
                        }
                        _ => {}
                    }
                }
            }
        }
    }
    
    /// Leader event loop
    async fn run_leader(&mut self) -> Result<()> {
        // Send initial heartbeats
        self.send_heartbeats().await?;
        
        let heartbeat_interval = self.heartbeat_interval;
        
        loop {
            tokio::select! {
                // Heartbeat timer
                _ = self.io.sleep(heartbeat_interval) => {
                    self.send_heartbeats().await?;
                }
                
                // Client command
                Some(cmd) = self.command_rx.recv() => {
                    // Append to log
                    let index = self.append_entry(cmd.data).await?;
                    
                    // Track pending response
                    self.pending_commands.insert(index, cmd.reply);
                    
                    // Replicate to followers
                    self.replicate_entries().await?;
                }
                
                // Incoming RPC
                Some(rpc) = self.rpc_rx.recv() => {
                    match rpc {
                        RpcMessage::AppendEntries(req, reply) => {
                            if req.term > self.persistent.current_term {
                                // Higher term, step down
                                self.persistent.current_term = req.term;
                                self.persist_state().await?;
                                self.state = State::Follower;
                                
                                let resp = self.handle_append_entries(req).await?;
                                let _ = reply.send(resp);
                                return Ok(());
                            }
                        }
                        RpcMessage::AppendEntriesResponse(node_id, resp) => {
                            self.handle_append_entries_response(node_id, resp).await?;
                        }
                        _ => {}
                    }
                }
            }
        }
    }
    
    /// Handle AppendEntries RPC
    async fn handle_append_entries(&mut self, req: AppendEntries) -> Result<AppendEntriesResponse> {
        // Update heartbeat
        self.last_heartbeat = self.io.now();
        
        // Reply false if term < currentTerm
        if req.term < self.persistent.current_term {
            return Ok(AppendEntriesResponse {
                term: self.persistent.current_term,
                success: false,
                match_index: 0,
            });
        }
        
        // Update term if needed
        if req.term > self.persistent.current_term {
            self.persistent.current_term = req.term;
            self.persistent.voted_for = None;
            self.persist_state().await?;
        }
        
        // Reply false if log doesn't contain entry at prevLogIndex with prevLogTerm
        if req.prev_log_index > 0 {
            match self.persistent.log.get(req.prev_log_index as usize - 1) {
                Some(entry) if entry.term != req.prev_log_term => {
                    return Ok(AppendEntriesResponse {
                        term: self.persistent.current_term,
                        success: false,
                        match_index: 0,
                    });
                }
                None => {
                    return Ok(AppendEntriesResponse {
                        term: self.persistent.current_term,
                        success: false,
                        match_index: 0,
                    });
                }
                _ => {}
            }
        }
        
        // Append new entries, replacing conflicts
        for (i, entry) in req.entries.iter().enumerate() {
            let index = req.prev_log_index + 1 + i as u64;
            if index <= self.persistent.log.len() as u64 {
                let existing = &self.persistent.log[index as usize - 1];
                if existing.term != entry.term {
                    // Conflict, truncate and append
                    self.persistent.log.truncate(index as usize - 1);
                    self.persistent.log.push(entry.clone());
                }
            } else {
                self.persistent.log.push(entry.clone());
            }
        }
        
        self.persist_state().await?;
        
        // Update commit index
        if req.leader_commit > self.volatile.commit_index {
            self.volatile.commit_index = std::cmp::min(
                req.leader_commit,
                self.persistent.log.len() as u64,
            );
            
            // Apply committed entries
            self.apply_committed_entries().await?;
        }
        
        Ok(AppendEntriesResponse {
            term: self.persistent.current_term,
            success: true,
            match_index: self.persistent.log.len() as u64,
        })
    }
    
    /// Handle RequestVote RPC
    async fn handle_request_vote(&mut self, req: RequestVote) -> Result<RequestVoteResponse> {
        // Reply false if term < currentTerm
        if req.term < self.persistent.current_term {
            return Ok(RequestVoteResponse {
                term: self.persistent.current_term,
                vote_granted: false,
            });
        }
        
        // Update term if needed
        if req.term > self.persistent.current_term {
            self.persistent.current_term = req.term;
            self.persistent.voted_for = None;
            self.state = State::Follower;
            self.persist_state().await?;
        }
        
        // Check if we can grant vote
        let can_vote = self.persistent.voted_for.is_none() 
            || self.persistent.voted_for == Some(req.candidate_id);
        
        // Check log is up-to-date
        let (last_log_index, last_log_term) = self.last_log_info();
        let log_ok = req.last_log_term > last_log_term
            || (req.last_log_term == last_log_term && req.last_log_index >= last_log_index);
        
        let vote_granted = can_vote && log_ok;
        
        if vote_granted {
            self.persistent.voted_for = Some(req.candidate_id);
            self.persist_state().await?;
            self.last_heartbeat = self.io.now(); // Reset election timer
        }
        
        Ok(RequestVoteResponse {
            term: self.persistent.current_term,
            vote_granted,
        })
    }
}
```

## View Change Protocol (VR Extension)

```rust
// src/vsr/view_change.rs

/// View change state
pub struct ViewChangeState {
    /// Current view number
    view_number: u64,
    /// Status of view change
    status: ViewChangeStatus,
    /// Collected DoViewChange messages
    do_view_change_msgs: Vec<DoViewChange>,
}

pub enum ViewChangeStatus {
    Normal,
    ViewChange,
    Recovering,
}

/// DoViewChange message (sent to new leader)
pub struct DoViewChange {
    view: u64,
    log: Vec<LogEntry>,
    view_number: u64,
    op_number: u64,
    commit_number: u64,
    node_id: NodeId,
}

/// StartView message (sent by new leader)
pub struct StartView {
    view: u64,
    log: Vec<LogEntry>,
    op_number: u64,
    commit_number: u64,
}

impl<I: IO, S: StateMachine> RaftNode<I, S> {
    /// Initiate view change (leader failure detected)
    pub async fn start_view_change(&mut self) -> Result<()> {
        let new_view = self.view_number + 1;
        
        // Broadcast StartViewChange to all replicas
        for peer in self.cluster.peers() {
            self.send_start_view_change(peer, StartViewChange {
                view: new_view,
                node_id: self.id,
            }).await?;
        }
        
        self.view_change_state = Some(ViewChangeState {
            view_number: new_view,
            status: ViewChangeStatus::ViewChange,
            do_view_change_msgs: vec![],
        });
        
        Ok(())
    }
    
    /// Handle StartViewChange from peer
    pub async fn handle_start_view_change(&mut self, msg: StartViewChange) -> Result<()> {
        if msg.view <= self.view_number {
            return Ok(()); // Ignore old view
        }
        
        // Compute new primary
        let new_primary = self.primary_for_view(msg.view);
        
        // Send DoViewChange to new primary
        self.send_do_view_change(new_primary, DoViewChange {
            view: msg.view,
            log: self.persistent.log.clone(),
            view_number: self.view_number,
            op_number: self.persistent.log.len() as u64,
            commit_number: self.volatile.commit_index,
            node_id: self.id,
        }).await?;
        
        self.view_change_state = Some(ViewChangeState {
            view_number: msg.view,
            status: ViewChangeStatus::ViewChange,
            do_view_change_msgs: vec![],
        });
        
        Ok(())
    }
    
    /// Handle DoViewChange (new primary collects these)
    pub async fn handle_do_view_change(&mut self, msg: DoViewChange) -> Result<()> {
        let state = self.view_change_state.as_mut()
            .ok_or(RaftError::InvalidState)?;
        
        if msg.view != state.view_number {
            return Ok(()); // Wrong view
        }
        
        state.do_view_change_msgs.push(msg);
        
        // Check if we have quorum
        if state.do_view_change_msgs.len() >= self.cluster.quorum_size() {
            // Select log with highest view number and op number
            let best_log = state.do_view_change_msgs.iter()
                .max_by_key(|m| (m.view_number, m.op_number))
                .map(|m| m.log.clone())
                .unwrap();
            
            // Determine commit point
            let commit_number = state.do_view_change_msgs.iter()
                .map(|m| m.commit_number)
                .max()
                .unwrap_or(0);
            
            // Install new log
            self.persistent.log = best_log;
            self.volatile.commit_index = commit_number;
            self.view_number = state.view_number;
            
            // Become leader
            self.state = State::Leader;
            self.leader_state = Some(LeaderState::new(&self.cluster));
            
            // Broadcast StartView to all replicas
            for peer in self.cluster.peers() {
                self.send_start_view(peer, StartView {
                    view: self.view_number,
                    log: self.persistent.log.clone(),
                    op_number: self.persistent.log.len() as u64,
                    commit_number: self.volatile.commit_index,
                }).await?;
            }
            
            self.view_change_state = None;
        }
        
        Ok(())
    }
    
    /// Handle StartView (new primary elected)
    pub async fn handle_start_view(&mut self, msg: StartView) -> Result<()> {
        if msg.view < self.view_number {
            return Ok(()); // Ignore old view
        }
        
        // Install log from new primary
        self.persistent.log = msg.log;
        self.volatile.commit_index = msg.commit_number;
        self.view_number = msg.view;
        
        // Apply any newly committed entries
        self.apply_committed_entries().await?;
        
        // Become follower
        self.state = State::Follower;
        self.view_change_state = None;
        
        Ok(())
    }
}
```

## State Transfer

```rust
// src/vsr/state_transfer.rs

/// Snapshot for state transfer
pub struct Snapshot {
    /// Last included index
    last_included_index: u64,
    /// Last included term
    last_included_term: u64,
    /// Serialized state machine
    data: Vec<u8>,
    /// Checksum
    checksum: u64,
}

impl<I: IO, S: StateMachine> RaftNode<I, S> {
    /// Create snapshot of current state
    pub async fn create_snapshot(&self) -> Result<Snapshot> {
        let data = self.state_machine.snapshot()?;
        let checksum = xxhash_rust::xxh64::xxh64(&data, 0);
        
        Ok(Snapshot {
            last_included_index: self.volatile.last_applied,
            last_included_term: self.persistent.log
                .get(self.volatile.last_applied as usize - 1)
                .map(|e| e.term)
                .unwrap_or(0),
            data,
            checksum,
        })
    }
    
    /// Install snapshot from leader
    pub async fn handle_install_snapshot(&mut self, req: InstallSnapshot) -> Result<InstallSnapshotResponse> {
        if req.term < self.persistent.current_term {
            return Ok(InstallSnapshotResponse {
                term: self.persistent.current_term,
            });
        }
        
        // Verify checksum
        let computed_checksum = xxhash_rust::xxh64::xxh64(&req.data, 0);
        if computed_checksum != req.checksum {
            return Err(RaftError::ChecksumMismatch);
        }
        
        // If this is a newer snapshot than we have
        if req.last_included_index > self.volatile.last_applied {
            // Discard log entries covered by snapshot
            if req.last_included_index <= self.persistent.log.len() as u64 {
                self.persistent.log.drain(0..req.last_included_index as usize);
            } else {
                self.persistent.log.clear();
            }
            
            // Install snapshot into state machine
            self.state_machine.restore(&req.data)?;
            
            self.volatile.commit_index = req.last_included_index;
            self.volatile.last_applied = req.last_included_index;
            
            self.persist_state().await?;
        }
        
        Ok(InstallSnapshotResponse {
            term: self.persistent.current_term,
        })
    }
    
    /// Send snapshot to lagging follower
    pub async fn send_snapshot(&self, follower: NodeId) -> Result<()> {
        let snapshot = self.create_snapshot().await?;
        
        // For large snapshots, chunk the transfer
        const CHUNK_SIZE: usize = 1024 * 1024; // 1MB chunks
        
        if snapshot.data.len() <= CHUNK_SIZE {
            // Single message
            self.send_install_snapshot(follower, InstallSnapshot {
                term: self.persistent.current_term,
                leader_id: self.id,
                last_included_index: snapshot.last_included_index,
                last_included_term: snapshot.last_included_term,
                offset: 0,
                data: snapshot.data,
                done: true,
                checksum: snapshot.checksum,
            }).await?;
        } else {
            // Chunked transfer
            for (i, chunk) in snapshot.data.chunks(CHUNK_SIZE).enumerate() {
                let offset = i * CHUNK_SIZE;
                let done = offset + chunk.len() >= snapshot.data.len();
                
                self.send_install_snapshot(follower, InstallSnapshot {
                    term: self.persistent.current_term,
                    leader_id: self.id,
                    last_included_index: snapshot.last_included_index,
                    last_included_term: snapshot.last_included_term,
                    offset: offset as u64,
                    data: chunk.to_vec(),
                    done,
                    checksum: snapshot.checksum,
                }).await?;
            }
        }
        
        Ok(())
    }
}
```

## Cluster Membership

```rust
// src/consensus/membership.rs

/// Cluster configuration
#[derive(Debug, Clone)]
pub struct ClusterConfig {
    /// All voting members
    pub voters: Vec<NodeId>,
    /// Non-voting members (learners)
    pub learners: Vec<NodeId>,
    /// Configuration index (for joint consensus)
    pub config_index: u64,
}

impl ClusterConfig {
    pub fn quorum_size(&self) -> usize {
        self.voters.len() / 2 + 1
    }
    
    pub fn is_voter(&self, node: NodeId) -> bool {
        self.voters.contains(&node)
    }
}

/// Joint consensus configuration (during transitions)
pub struct JointConfig {
    old: ClusterConfig,
    new: ClusterConfig,
}

impl JointConfig {
    /// Requires quorum from BOTH old and new configs
    pub fn quorum_size(&self) -> (usize, usize) {
        (self.old.quorum_size(), self.new.quorum_size())
    }
}

impl<I: IO, S: StateMachine> RaftNode<I, S> {
    /// Add a new node to the cluster
    pub async fn add_node(&mut self, new_node: NodeId) -> Result<()> {
        if !self.is_leader() {
            return Err(RaftError::NotLeader(self.current_leader()));
        }
        
        // First add as learner
        let mut new_config = self.cluster.clone();
        new_config.learners.push(new_node);
        
        // Replicate configuration change
        self.append_config_change(ConfigChange::AddLearner(new_node)).await?;
        
        // Wait for learner to catch up
        self.wait_for_catch_up(new_node).await?;
        
        // Promote to voter using joint consensus
        self.start_joint_consensus(new_node).await?;
        
        Ok(())
    }
    
    /// Remove a node from the cluster
    pub async fn remove_node(&mut self, node: NodeId) -> Result<()> {
        if !self.is_leader() {
            return Err(RaftError::NotLeader(self.current_leader()));
        }
        
        // Use joint consensus for safe removal
        let old_config = self.cluster.clone();
        let mut new_config = self.cluster.clone();
        new_config.voters.retain(|n| *n != node);
        
        // Enter joint configuration
        let joint = JointConfig { old: old_config, new: new_config.clone() };
        self.append_config_change(ConfigChange::Joint(joint)).await?;
        
        // Wait for joint config to commit
        self.wait_for_commit().await?;
        
        // Exit to new configuration
        self.append_config_change(ConfigChange::NewConfig(new_config)).await?;
        
        Ok(())
    }
    
    async fn start_joint_consensus(&mut self, new_voter: NodeId) -> Result<()> {
        let old_config = self.cluster.clone();
        let mut new_config = self.cluster.clone();
        new_config.learners.retain(|n| *n != new_voter);
        new_config.voters.push(new_voter);
        
        // Enter joint configuration
        let joint = JointConfig { old: old_config, new: new_config.clone() };
        self.append_config_change(ConfigChange::Joint(joint)).await?;
        
        // Wait for joint config to commit
        self.wait_for_commit().await?;
        
        // Exit to new configuration
        self.append_config_change(ConfigChange::NewConfig(new_config)).await?;
        
        Ok(())
    }
}
```

## Safety Invariants

| Invariant | Description |
|-----------|-------------|
| **Election Safety** | At most one leader per term |
| **Leader Append-Only** | Leader never overwrites or deletes entries |
| **Log Matching** | If two logs contain entry with same index and term, all preceding entries are identical |
| **Leader Completeness** | If entry is committed in term T, it's present in all leaders for terms > T |
| **State Machine Safety** | If server applies entry at index I, no other server applies different entry at I |

## Performance Tuning

```toml
# Timing parameters
[consensus.timing]
election_timeout_min = "150ms"
election_timeout_max = "300ms"
heartbeat_interval = "50ms"

# For high-latency networks
[consensus.timing.wan]
election_timeout_min = "500ms"
election_timeout_max = "1000ms"
heartbeat_interval = "150ms"

# Batching
[consensus.batching]
max_batch_size = 1000
max_batch_bytes = "1MB"
linger_ms = 5
```

## References

- [Raft Paper](https://raft.github.io/raft.pdf)
- [Viewstamped Replication Revisited](https://pmg.csail.mit.edu/papers/vr-revisited.pdf)
- [TigerBeetle Consensus](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/DESIGN.md#consensus)
- [Raft Membership Changes](https://web.stanford.edu/~ouster/cgi-bin/papers/OngaroPhD.pdf)
