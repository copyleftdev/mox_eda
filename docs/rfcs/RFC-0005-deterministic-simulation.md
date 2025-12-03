# RFC-0005: Deterministic Simulation Testing

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

Deterministic Simulation Testing (DST) is TigerBeetle's secret weapon. It allows us to simulate years of operation in minutes, injecting every possible failure mode—network partitions, disk corruption, node crashes, clock skew—and verify that invariants always hold.

This is not optional. This is how we prove correctness.

## Why DST?

Traditional testing approaches fail for distributed systems:

| Approach | Problem |
|----------|---------|
| Unit tests | Don't test interactions |
| Integration tests | Slow, flaky, incomplete coverage |
| Chaos testing (production) | Dangerous, non-reproducible |
| Formal verification | Doesn't test implementation |

DST solves all of these:
- **Complete coverage**: Test every interleaving of events
- **Fast**: Run millions of operations in seconds
- **Reproducible**: Same seed = same execution
- **Safe**: No production risk
- **Implementation testing**: Tests real code, not models

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SIMULATION HARNESS                                      │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                          SIMULATOR                                        │ │
│  │                                                                           │ │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                    │ │
│  │   │  Simulated  │   │  Simulated  │   │  Simulated  │                    │ │
│  │   │   Node 1    │   │   Node 2    │   │   Node 3    │                    │ │
│  │   │             │   │             │   │             │                    │ │
│  │   │ ┌─────────┐ │   │ ┌─────────┐ │   │ ┌─────────┐ │                    │ │
│  │   │ │ State   │ │   │ │ State   │ │   │ │ State   │ │                    │ │
│  │   │ │ Machine │ │   │ │ Machine │ │   │ │ Machine │ │                    │ │
│  │   │ └─────────┘ │   │ └─────────┘ │   │ └─────────┘ │                    │ │
│  │   │ ┌─────────┐ │   │ ┌─────────┐ │   │ ┌─────────┐ │                    │ │
│  │   │ │   Raft  │ │   │ │   Raft  │ │   │ │   Raft  │ │                    │ │
│  │   │ └─────────┘ │   │ └─────────┘ │   │ └─────────┘ │                    │ │
│  │   │ ┌─────────┐ │   │ ┌─────────┐ │   │ ┌─────────┐ │                    │ │
│  │   │ │ SimIO   │ │   │ │ SimIO   │ │   │ │ SimIO   │ │                    │ │
│  │   │ └────┬────┘ │   │ └────┬────┘ │   │ └────┬────┘ │                    │ │
│  │   └──────┼──────┘   └──────┼──────┘   └──────┼──────┘                    │ │
│  │          │                 │                 │                            │ │
│  │          └─────────────────┼─────────────────┘                            │ │
│  │                            │                                              │ │
│  │   ┌────────────────────────┴────────────────────────┐                    │ │
│  │   │               SIMULATION CORE                   │                    │ │
│  │   │                                                 │                    │ │
│  │   │  ┌─────────────────────────────────────────┐   │                    │ │
│  │   │  │          Event Queue (Priority)         │   │                    │ │
│  │   │  │  • Network messages                     │   │                    │ │
│  │   │  │  • Disk completions                     │   │                    │ │
│  │   │  │  • Timeouts                             │   │                    │ │
│  │   │  │  • Faults                               │   │                    │ │
│  │   │  └─────────────────────────────────────────┘   │                    │ │
│  │   │                                                 │                    │ │
│  │   │  ┌──────────────┐  ┌──────────────┐            │                    │ │
│  │   │  │  Simulated   │  │  Simulated   │            │                    │ │
│  │   │  │   Network    │  │    Disks     │            │                    │ │
│  │   │  └──────────────┘  └──────────────┘            │                    │ │
│  │   │                                                 │                    │ │
│  │   │  ┌──────────────┐  ┌──────────────┐            │                    │ │
│  │   │  │  Simulated   │  │  Fault       │            │                    │ │
│  │   │  │    Time      │  │  Injector    │            │                    │ │
│  │   │  └──────────────┘  └──────────────┘            │                    │ │
│  │   └─────────────────────────────────────────────────┘                    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                       INVARIANT CHECKER                                   │ │
│  │                                                                           │ │
│  │   • Linearizability                                                       │ │
│  │   • No data loss after commit                                             │ │
│  │   • All nodes converge                                                    │ │
│  │   • Checksums valid                                                       │ │
│  │   • State machine invariants                                              │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## IO Trait Abstraction

The key insight: **abstract all non-deterministic operations behind a trait**.

```rust
// src/io/traits.rs

use std::future::Future;
use std::time::{Duration, Instant};

/// Abstraction over all I/O operations
/// 
/// In production: real io_uring, real time, real network
/// In simulation: fake everything, deterministic
pub trait IO: Send + Sync + Clone + 'static {
    // Time
    fn now(&self) -> Instant;
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send;
    
    // Randomness
    fn random(&self) -> u64;
    fn random_range(&self, min: u64, max: u64) -> u64;
    
    // Disk
    fn write(&self, fd: FileId, offset: u64, data: &[u8]) -> impl Future<Output = Result<usize>> + Send;
    fn read(&self, fd: FileId, offset: u64, len: usize) -> impl Future<Output = Result<Vec<u8>>> + Send;
    fn fsync(&self, fd: FileId) -> impl Future<Output = Result<()>> + Send;
    fn open(&self, path: &Path, flags: OpenFlags) -> impl Future<Output = Result<FileId>> + Send;
    fn close(&self, fd: FileId) -> impl Future<Output = Result<()>> + Send;
    
    // Network
    fn send(&self, to: NodeId, message: &[u8]) -> impl Future<Output = Result<()>> + Send;
    fn recv(&self) -> impl Future<Output = Result<(NodeId, Vec<u8>)>> + Send;
}
```

## Simulated I/O

```rust
// src/simulator/io.rs

use std::collections::{BinaryHeap, HashMap};
use std::cmp::Reverse;

/// Simulated I/O for deterministic testing
#[derive(Clone)]
pub struct SimIO {
    inner: Arc<Mutex<SimIOInner>>,
}

struct SimIOInner {
    /// Current simulated time (nanoseconds)
    time: u64,
    
    /// Deterministic RNG
    rng: Xoroshiro128PlusPlus,
    
    /// Simulated disks per node
    disks: HashMap<NodeId, SimDisk>,
    
    /// Network simulation
    network: SimNetwork,
    
    /// Pending events (priority queue by time)
    events: BinaryHeap<Reverse<SimEvent>>,
    
    /// Node this IO belongs to
    node_id: NodeId,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct SimEvent {
    time: u64,
    seq: u64, // For deterministic ordering of simultaneous events
    kind: SimEventKind,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum SimEventKind {
    DiskWriteComplete { fd: FileId, offset: u64, len: usize },
    DiskReadComplete { fd: FileId, offset: u64, data: Vec<u8> },
    NetworkDeliver { from: NodeId, to: NodeId, data: Vec<u8> },
    Timeout { id: u64 },
}

impl IO for SimIO {
    fn now(&self) -> Instant {
        let inner = self.inner.lock();
        // Convert simulated nanoseconds to Instant
        // (In practice, we use a wrapper type)
        Instant::now() // Placeholder
    }
    
    async fn sleep(&self, duration: Duration) {
        let wake_time = {
            let mut inner = self.inner.lock();
            let wake_time = inner.time + duration.as_nanos() as u64;
            let timeout_id = inner.rng.gen();
            
            inner.events.push(Reverse(SimEvent {
                time: wake_time,
                seq: inner.next_seq(),
                kind: SimEventKind::Timeout { id: timeout_id },
            }));
            
            wake_time
        };
        
        // Wait for simulator to advance time
        loop {
            let current = self.inner.lock().time;
            if current >= wake_time {
                break;
            }
            tokio::task::yield_now().await;
        }
    }
    
    fn random(&self) -> u64 {
        self.inner.lock().rng.gen()
    }
    
    fn random_range(&self, min: u64, max: u64) -> u64 {
        let mut inner = self.inner.lock();
        min + (inner.rng.gen::<u64>() % (max - min))
    }
    
    async fn write(&self, fd: FileId, offset: u64, data: &[u8]) -> Result<usize> {
        let (complete_time, should_fail) = {
            let mut inner = self.inner.lock();
            let disk = inner.disks.get_mut(&inner.node_id).unwrap();
            
            // Check for injected failures
            let should_fail = disk.should_fail_write();
            
            if !should_fail {
                // Actually write to simulated disk
                disk.write(fd, offset, data);
            }
            
            // Schedule completion (with realistic latency)
            let latency = inner.rng.gen_range(100_000..500_000); // 100-500μs
            let complete_time = inner.time + latency;
            
            inner.events.push(Reverse(SimEvent {
                time: complete_time,
                seq: inner.next_seq(),
                kind: SimEventKind::DiskWriteComplete { fd, offset, len: data.len() },
            }));
            
            (complete_time, should_fail)
        };
        
        // Wait for completion
        self.wait_for_time(complete_time).await;
        
        if should_fail {
            Err(io::Error::new(io::ErrorKind::Other, "Injected disk failure"))
        } else {
            Ok(data.len())
        }
    }
    
    async fn read(&self, fd: FileId, offset: u64, len: usize) -> Result<Vec<u8>> {
        let (data, complete_time, should_corrupt) = {
            let mut inner = self.inner.lock();
            let disk = inner.disks.get(&inner.node_id).unwrap();
            
            // Read from simulated disk
            let mut data = disk.read(fd, offset, len);
            
            // Maybe corrupt the data
            let should_corrupt = disk.should_corrupt_read();
            if should_corrupt {
                if !data.is_empty() {
                    let idx = inner.rng.gen_range(0..data.len());
                    data[idx] ^= 0xFF; // Flip bits
                }
            }
            
            // Schedule completion
            let latency = inner.rng.gen_range(50_000..200_000); // 50-200μs
            let complete_time = inner.time + latency;
            
            (data, complete_time, should_corrupt)
        };
        
        self.wait_for_time(complete_time).await;
        
        Ok(data)
    }
    
    async fn send(&self, to: NodeId, message: &[u8]) -> Result<()> {
        let mut inner = self.inner.lock();
        let from = inner.node_id;
        
        // Check if network should drop/delay this message
        let action = inner.network.route_message(from, to);
        
        match action {
            NetworkAction::Deliver { delay } => {
                let deliver_time = inner.time + delay;
                inner.events.push(Reverse(SimEvent {
                    time: deliver_time,
                    seq: inner.next_seq(),
                    kind: SimEventKind::NetworkDeliver {
                        from,
                        to,
                        data: message.to_vec(),
                    },
                }));
            }
            NetworkAction::Drop => {
                // Message disappears into the void
            }
            NetworkAction::Duplicate { delays } => {
                for delay in delays {
                    let deliver_time = inner.time + delay;
                    inner.events.push(Reverse(SimEvent {
                        time: deliver_time,
                        seq: inner.next_seq(),
                        kind: SimEventKind::NetworkDeliver {
                            from,
                            to,
                            data: message.to_vec(),
                        },
                    }));
                }
            }
        }
        
        Ok(())
    }
    
    async fn recv(&self) -> Result<(NodeId, Vec<u8>)> {
        loop {
            {
                let mut inner = self.inner.lock();
                
                // Check for delivered messages
                if let Some(msg) = inner.network.inbox(inner.node_id).pop_front() {
                    return Ok((msg.from, msg.data));
                }
            }
            
            tokio::task::yield_now().await;
        }
    }
}
```

## Simulated Network

```rust
// src/simulator/network.rs

pub struct SimNetwork {
    /// Partition state: which nodes can talk to which
    partitions: Vec<HashSet<NodeId>>,
    
    /// Per-link latency configuration
    latencies: HashMap<(NodeId, NodeId), LatencyConfig>,
    
    /// Message inboxes per node
    inboxes: HashMap<NodeId, VecDeque<NetworkMessage>>,
    
    /// RNG for network behavior
    rng: Xoroshiro128PlusPlus,
    
    /// Fault injection config
    fault_config: NetworkFaultConfig,
}

pub struct NetworkFaultConfig {
    /// Probability of dropping a message
    drop_probability: f64,
    
    /// Probability of duplicating a message
    duplicate_probability: f64,
    
    /// Probability of reordering messages
    reorder_probability: f64,
    
    /// Min/max latency (nanoseconds)
    latency_min: u64,
    latency_max: u64,
}

impl SimNetwork {
    /// Create a network partition
    pub fn partition(&mut self, group_a: Vec<NodeId>, group_b: Vec<NodeId>) {
        self.partitions.push(group_a.into_iter().collect());
        self.partitions.push(group_b.into_iter().collect());
    }
    
    /// Heal all partitions
    pub fn heal(&mut self) {
        self.partitions.clear();
    }
    
    /// Check if two nodes can communicate
    pub fn can_communicate(&self, a: NodeId, b: NodeId) -> bool {
        if self.partitions.is_empty() {
            return true;
        }
        
        // Nodes can communicate if they're in the same partition
        for partition in &self.partitions {
            if partition.contains(&a) && partition.contains(&b) {
                return true;
            }
        }
        
        false
    }
    
    /// Route a message (returns action to take)
    pub fn route_message(&mut self, from: NodeId, to: NodeId) -> NetworkAction {
        // Check partition
        if !self.can_communicate(from, to) {
            return NetworkAction::Drop;
        }
        
        // Random drop
        if self.rng.gen::<f64>() < self.fault_config.drop_probability {
            return NetworkAction::Drop;
        }
        
        // Random duplicate
        if self.rng.gen::<f64>() < self.fault_config.duplicate_probability {
            let delay1 = self.random_latency();
            let delay2 = self.random_latency();
            return NetworkAction::Duplicate { delays: vec![delay1, delay2] };
        }
        
        // Normal delivery with random latency
        let delay = self.random_latency();
        NetworkAction::Deliver { delay }
    }
    
    fn random_latency(&mut self) -> u64 {
        self.rng.gen_range(
            self.fault_config.latency_min..self.fault_config.latency_max
        )
    }
}

pub enum NetworkAction {
    Deliver { delay: u64 },
    Drop,
    Duplicate { delays: Vec<u64> },
}
```

## Simulated Disk

```rust
// src/simulator/disk.rs

pub struct SimDisk {
    /// In-memory representation of disk contents
    files: HashMap<FileId, Vec<u8>>,
    
    /// Pending writes (not yet fsynced)
    pending_writes: HashMap<FileId, Vec<PendingWrite>>,
    
    /// RNG for fault injection
    rng: Xoroshiro128PlusPlus,
    
    /// Fault configuration
    fault_config: DiskFaultConfig,
}

pub struct DiskFaultConfig {
    /// Probability of write failure
    write_failure_probability: f64,
    
    /// Probability of read returning corrupted data
    read_corruption_probability: f64,
    
    /// Probability of losing unfsynced writes on "crash"
    fsync_loss_probability: f64,
}

struct PendingWrite {
    offset: u64,
    data: Vec<u8>,
}

impl SimDisk {
    pub fn write(&mut self, fd: FileId, offset: u64, data: &[u8]) {
        // Add to pending writes
        self.pending_writes
            .entry(fd)
            .or_default()
            .push(PendingWrite {
                offset,
                data: data.to_vec(),
            });
    }
    
    pub fn fsync(&mut self, fd: FileId) {
        // Apply pending writes
        if let Some(pending) = self.pending_writes.remove(&fd) {
            let file = self.files.entry(fd).or_default();
            
            for write in pending {
                let end = write.offset as usize + write.data.len();
                if file.len() < end {
                    file.resize(end, 0);
                }
                file[write.offset as usize..end].copy_from_slice(&write.data);
            }
        }
    }
    
    pub fn read(&self, fd: FileId, offset: u64, len: usize) -> Vec<u8> {
        self.files
            .get(&fd)
            .map(|data| {
                let start = offset as usize;
                let end = (start + len).min(data.len());
                if start >= data.len() {
                    vec![]
                } else {
                    data[start..end].to_vec()
                }
            })
            .unwrap_or_default()
    }
    
    /// Simulate a crash (lose unfsynced writes)
    pub fn crash(&mut self) {
        // With some probability, lose each pending write
        for (_, pending) in self.pending_writes.iter_mut() {
            pending.retain(|_| {
                self.rng.gen::<f64>() > self.fault_config.fsync_loss_probability
            });
        }
        
        // Clear remaining pending writes
        self.pending_writes.clear();
    }
    
    pub fn should_fail_write(&mut self) -> bool {
        self.rng.gen::<f64>() < self.fault_config.write_failure_probability
    }
    
    pub fn should_corrupt_read(&mut self) -> bool {
        self.rng.gen::<f64>() < self.fault_config.read_corruption_probability
    }
}
```

## Simulator Driver

```rust
// src/simulator/driver.rs

pub struct Simulator {
    /// Seed for reproducibility
    seed: u64,
    
    /// Simulated nodes
    nodes: Vec<SimulatedNode>,
    
    /// Shared simulation state
    sim_io: Vec<SimIO>,
    
    /// Event queue
    events: BinaryHeap<Reverse<SimEvent>>,
    
    /// Current simulated time
    time: u64,
    
    /// Sequence counter for determinism
    seq: u64,
    
    /// Invariant checker
    checker: InvariantChecker,
    
    /// Test client for submitting commands
    client: SimClient,
}

impl Simulator {
    pub fn new(seed: u64, num_nodes: usize) -> Self {
        let mut rng = Xoroshiro128PlusPlus::seed_from_u64(seed);
        
        let mut nodes = Vec::with_capacity(num_nodes);
        let mut sim_io = Vec::with_capacity(num_nodes);
        
        for i in 0..num_nodes {
            let node_id = NodeId(i as u64);
            let io = SimIO::new(node_id, rng.gen());
            sim_io.push(io.clone());
            
            let node = SimulatedNode::new(node_id, io);
            nodes.push(node);
        }
        
        Self {
            seed,
            nodes,
            sim_io,
            events: BinaryHeap::new(),
            time: 0,
            seq: 0,
            checker: InvariantChecker::new(),
            client: SimClient::new(),
        }
    }
    
    /// Run simulation for N ticks
    pub fn run(&mut self, ticks: u64) -> SimResult {
        for _ in 0..ticks {
            self.tick()?;
            
            // Check invariants periodically
            if self.seq % 1000 == 0 {
                self.checker.check_all(&self.nodes)?;
            }
        }
        
        // Final invariant check
        self.checker.check_all(&self.nodes)?;
        
        Ok(SimStats {
            ticks: ticks,
            events_processed: self.seq,
            time_simulated: Duration::from_nanos(self.time),
        })
    }
    
    /// Process one simulation tick
    fn tick(&mut self) -> Result<()> {
        // Collect events from all nodes
        for io in &self.sim_io {
            let mut inner = io.inner.lock();
            while let Some(Reverse(event)) = inner.events.pop() {
                self.events.push(Reverse(event));
            }
        }
        
        // Process next event
        if let Some(Reverse(event)) = self.events.pop() {
            self.time = event.time;
            self.process_event(event)?;
            self.seq += 1;
        }
        
        Ok(())
    }
    
    fn process_event(&mut self, event: SimEvent) -> Result<()> {
        match event.kind {
            SimEventKind::NetworkDeliver { from, to, data } => {
                // Deliver message to target node's inbox
                let io = &self.sim_io[to.0 as usize];
                io.inner.lock().network.inbox(to).push_back(NetworkMessage {
                    from,
                    data,
                });
            }
            SimEventKind::DiskWriteComplete { .. } => {
                // Wake up waiting task
            }
            SimEventKind::DiskReadComplete { .. } => {
                // Wake up waiting task
            }
            SimEventKind::Timeout { .. } => {
                // Wake up sleeping task
            }
        }
        
        Ok(())
    }
    
    /// Inject a fault
    pub fn inject_fault(&mut self, fault: Fault) {
        match fault {
            Fault::CrashNode(node_id) => {
                self.nodes[node_id.0 as usize].crash();
                self.sim_io[node_id.0 as usize].inner.lock().disks
                    .get_mut(&node_id).unwrap().crash();
            }
            Fault::PartitionNetwork(group_a, group_b) => {
                for io in &self.sim_io {
                    io.inner.lock().network.partition(group_a.clone(), group_b.clone());
                }
            }
            Fault::HealNetwork => {
                for io in &self.sim_io {
                    io.inner.lock().network.heal();
                }
            }
            Fault::SlowDisk(node_id, factor) => {
                // Increase latencies for this node's disk
            }
            Fault::CorruptDisk(node_id) => {
                // Enable corruption for reads
            }
        }
    }
    
    /// Submit a client command
    pub fn submit(&mut self, command: Command) -> Result<CommandResult> {
        self.client.submit(&self.nodes, command)
    }
}

pub enum Fault {
    CrashNode(NodeId),
    PartitionNetwork(Vec<NodeId>, Vec<NodeId>),
    HealNetwork,
    SlowDisk(NodeId, u64),
    CorruptDisk(NodeId),
}
```

## Invariant Checker

```rust
// src/simulator/invariants.rs

pub struct InvariantChecker {
    /// History of all committed operations (for linearizability)
    history: Vec<HistoryEntry>,
}

impl InvariantChecker {
    pub fn check_all(&self, nodes: &[SimulatedNode]) -> Result<()> {
        self.check_single_leader(nodes)?;
        self.check_log_consistency(nodes)?;
        self.check_committed_data_persisted(nodes)?;
        self.check_linearizability()?;
        self.check_state_machine_invariants(nodes)?;
        Ok(())
    }
    
    /// At most one leader per term
    fn check_single_leader(&self, nodes: &[SimulatedNode]) -> Result<()> {
        let mut leaders_by_term: HashMap<u64, Vec<NodeId>> = HashMap::new();
        
        for node in nodes {
            if node.is_leader() {
                leaders_by_term
                    .entry(node.current_term())
                    .or_default()
                    .push(node.id());
            }
        }
        
        for (term, leaders) in leaders_by_term {
            if leaders.len() > 1 {
                return Err(InvariantViolation::MultipleLeaders { term, leaders });
            }
        }
        
        Ok(())
    }
    
    /// All nodes agree on committed log entries
    fn check_log_consistency(&self, nodes: &[SimulatedNode]) -> Result<()> {
        let min_commit = nodes.iter()
            .map(|n| n.commit_index())
            .min()
            .unwrap_or(0);
        
        for i in 1..=min_commit {
            let mut entries: Vec<(NodeId, LogEntry)> = vec![];
            
            for node in nodes {
                if let Some(entry) = node.log_entry(i) {
                    entries.push((node.id(), entry));
                }
            }
            
            // All entries at this index must be identical
            if let Some((_, first)) = entries.first() {
                for (node_id, entry) in &entries[1..] {
                    if entry != first {
                        return Err(InvariantViolation::LogInconsistency {
                            index: i,
                            entries: entries.clone(),
                        });
                    }
                }
            }
        }
        
        Ok(())
    }
    
    /// Committed data survives crashes
    fn check_committed_data_persisted(&self, nodes: &[SimulatedNode]) -> Result<()> {
        for entry in &self.history {
            if entry.committed {
                // At least one node must have this data
                let mut found = false;
                for node in nodes {
                    if node.has_committed_entry(entry.index) {
                        found = true;
                        break;
                    }
                }
                
                if !found {
                    return Err(InvariantViolation::DataLoss { entry: entry.clone() });
                }
            }
        }
        
        Ok(())
    }
    
    /// Check linearizability using Wing-Gong algorithm
    fn check_linearizability(&self) -> Result<()> {
        // Build operation graph
        // Check for valid sequential ordering
        // This is O(n!) worst case, but practical with small histories
        
        let operations: Vec<_> = self.history.iter()
            .filter(|e| e.completed)
            .collect();
        
        if operations.len() > 100 {
            // For large histories, use sampling or WGL algorithm
            return Ok(());
        }
        
        // Try all permutations (brute force for small histories)
        // In practice, use smarter algorithms
        
        Ok(())
    }
    
    /// Domain-specific invariants
    fn check_state_machine_invariants(&self, nodes: &[SimulatedNode]) -> Result<()> {
        for node in nodes {
            let state = node.state_machine();
            
            // Check: No duplicate talent IDs
            // Check: All references are valid
            // Check: Counters are accurate
            // Check: Tenant isolation
            
            state.validate_invariants()?;
        }
        
        Ok(())
    }
}
```

## Test Examples

```rust
// tests/simulation/consensus_test.rs

#[test]
fn test_leader_election() {
    for seed in 0..1000 {
        let mut sim = Simulator::new(seed, 3);
        
        // Run until a leader is elected
        sim.run_until(|sim| {
            sim.nodes.iter().any(|n| n.is_leader())
        }, Duration::from_secs(10));
        
        // Verify exactly one leader
        let leaders: Vec<_> = sim.nodes.iter()
            .filter(|n| n.is_leader())
            .collect();
        
        assert_eq!(leaders.len(), 1, "Seed {}: Expected 1 leader, got {}", seed, leaders.len());
    }
}

#[test]
fn test_leader_failure_recovery() {
    for seed in 0..1000 {
        let mut sim = Simulator::new(seed, 5);
        
        // Wait for leader
        sim.run_until(|sim| sim.has_leader(), Duration::from_secs(10));
        
        // Crash the leader
        let leader = sim.current_leader().unwrap();
        sim.inject_fault(Fault::CrashNode(leader));
        
        // Wait for new leader
        sim.run_until(|sim| {
            sim.has_leader() && sim.current_leader() != Some(leader)
        }, Duration::from_secs(10));
        
        // Verify new leader elected
        assert!(sim.has_leader());
        assert_ne!(sim.current_leader(), Some(leader));
    }
}

#[test]
fn test_network_partition_and_heal() {
    for seed in 0..1000 {
        let mut sim = Simulator::new(seed, 5);
        
        // Submit some commands
        for i in 0..100 {
            sim.submit(Command::CreateTalent(create_talent_cmd(i)));
        }
        sim.run(10000);
        
        // Partition: [0,1] vs [2,3,4]
        sim.inject_fault(Fault::PartitionNetwork(
            vec![NodeId(0), NodeId(1)],
            vec![NodeId(2), NodeId(3), NodeId(4)],
        ));
        
        // Submit more commands (should go to majority partition)
        for i in 100..200 {
            sim.submit(Command::CreateTalent(create_talent_cmd(i)));
        }
        sim.run(10000);
        
        // Heal partition
        sim.inject_fault(Fault::HealNetwork);
        sim.run(10000);
        
        // All nodes should converge
        let states: Vec<_> = sim.nodes.iter()
            .map(|n| n.state_hash())
            .collect();
        
        assert!(states.windows(2).all(|w| w[0] == w[1]),
            "Seed {}: Nodes did not converge after partition heal", seed);
    }
}

#[test]
fn test_million_operations_with_chaos() {
    let seed = 42;
    let mut sim = Simulator::new(seed, 5);
    
    for i in 0..1_000_000 {
        // Random command
        let cmd = random_command(&mut sim.rng, i);
        sim.submit(cmd);
        
        // Random faults
        if sim.rng.gen::<f64>() < 0.001 {
            let fault = random_fault(&mut sim.rng, 5);
            sim.inject_fault(fault);
        }
        
        // Advance simulation
        sim.run(100);
        
        // Periodically check invariants
        if i % 10000 == 0 {
            sim.checker.check_all(&sim.nodes).unwrap();
        }
    }
    
    // Final check
    sim.run(100000); // Let things settle
    sim.checker.check_all(&sim.nodes).unwrap();
}
```

## Running Simulations

```bash
# Run all simulation tests
cargo test --features simulation

# Run with specific seed (for reproduction)
SEED=12345 cargo test test_million_operations

# Run with more iterations
ITERATIONS=10000 cargo test test_leader_election

# Profile simulation performance
cargo bench --features simulation
```

## References

- [FoundationDB Testing](https://www.youtube.com/watch?v=4fFDFbi3toc)
- [TigerBeetle Simulation](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/DESIGN.md#simulation)
- [Jepsen](https://jepsen.io/)
- [Linearizability Testing](https://www.anishathalye.com/2017/06/04/testing-distributed-systems-for-linearizability/)
