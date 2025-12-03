# RFC-0001: Architecture Overview

| Field | Value |
|-------|-------|
| **Status** | Draft |
| **Authors** | Platform Team |
| **Created** | 2024-12-03 |

## Abstract

Mox is a single Rust binary that implements a distributed, fault-tolerant event-sourced system for talent management operations. It takes direct inspiration from TigerBeetle's architecture: zero external dependencies, deterministic simulation testing, and relentless focus on correctness and performance.

## Core Principles

### 1. Single Binary, Zero Dependencies

```
Traditional Stack:              Mox Stack:
──────────────────              ──────────────
PostgreSQL                      
Redis                           
NATS/Kafka                      ┌─────────────┐
Kubernetes                  →   │     mox     │ (single binary)
Docker                          └─────────────┘
Vault                           
Prometheus                      
Grafana                         
```

**What's inside the binary:**
- Event log (append-only, checksummed)
- State store (B-tree, MVCC)
- Search index (inverted index)
- Consensus (Raft)
- HTTP server (Axum)
- Metrics endpoint (Prometheus format)
- Structured logging

### 2. Correctness Over Convenience

We will never:
- Use dynamic memory allocation in the hot path
- Trust the filesystem (always verify with checksums)
- Assume the network is reliable
- Skip fsync for "performance"
- Use mocks in critical path tests

We will always:
- Checksum all data at rest and in transit
- Verify reads match what was written
- Test with deterministic simulation
- Handle Byzantine faults where possible
- Prove correctness with formal methods where feasible

### 3. Deterministic Simulation Testing

Every component runs in two modes:
1. **Production mode**: Real I/O, real time, real network
2. **Simulation mode**: Fake I/O, fake time, fake network (deterministic)

```rust
// The same code runs in both modes
pub trait IO: Send + Sync {
    fn write(&self, offset: u64, data: &[u8]) -> impl Future<Output = Result<()>>;
    fn read(&self, offset: u64, len: usize) -> impl Future<Output = Result<Vec<u8>>>;
    fn now(&self) -> Instant;
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()>;
    fn random(&self) -> u64;
}

// Production
pub struct RealIO { /* io_uring handle */ }

// Simulation
pub struct SimIO {
    time: SimTime,
    disk: SimDisk,  // Can inject corruption, delays, failures
    rng: Xoroshiro128PlusPlus,  // Seeded, deterministic
}
```

### 4. Cluster-First Design

There is no "single node mode for development." The cluster is the unit of deployment:

```
Minimum deployment: 3 nodes (tolerates 1 failure)
Recommended:        5 nodes (tolerates 2 failures)
```

For local development, all 3 nodes run on localhost with different ports.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  MOX NODE                                       │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                           CLIENT LAYER                                    │ │
│  │                                                                           │ │
│  │   HTTP/REST    GraphQL     WebSocket     Webhooks (inbound)               │ │
│  │   :8080        :8080       :8080         :8080                            │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    Request Router                               │    │ │
│  │   │  • Writes → Forward to leader                                   │    │ │
│  │   │  • Reads  → Handle locally (linearizable or stale)              │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                                   ▼          STATE MACHINE                │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    Command Processor                            │    │ │
│  │   │  • Validate commands                                            │    │ │
│  │   │  • Apply business rules                                         │    │ │
│  │   │  • Generate events                                              │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                   │                                       │ │
│  │   ┌─────────────┐ ┌─────────────┐ │ ┌─────────────┐ ┌─────────────┐      │ │
│  │   │   Talent    │ │  Campaign   │ │ │  Contract   │ │  Analytics  │      │ │
│  │   │   Domain    │ │   Domain    │ │ │   Domain    │ │   Domain    │      │ │
│  │   └─────────────┘ └─────────────┘ │ └─────────────┘ └─────────────┘      │ │
│  │                                   │                                       │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    Projection Engine                            │    │ │
│  │   │  • Materialized views for queries                               │    │ │
│  │   │  • Search indexes                                               │    │ │
│  │   │  • Analytics aggregates                                         │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                                   ▼          CONSENSUS LAYER              │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                         Raft                                    │    │ │
│  │   │  • Leader election                                              │    │ │
│  │   │  • Log replication                                              │    │ │
│  │   │  • Membership changes                                           │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                   │                                       │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                 Viewstamped Replication                         │    │ │
│  │   │  • View change protocol                                         │    │ │
│  │   │  • State transfer                                               │    │ │
│  │   │  • Reconfiguration                                              │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                   │                                       │ │
│  │            ┌──────────────────────┼──────────────────────┐               │ │
│  │            │                      │                      │               │ │
│  │            ▼                      ▼                      ▼               │ │
│  │   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐       │ │
│  │   │   Node 2        │   │   Node 3        │   │   Node N        │       │ │
│  │   │   (replica)     │   │   (replica)     │   │   (replica)     │       │ │
│  │   └─────────────────┘   └─────────────────┘   └─────────────────┘       │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                          │
│  ┌───────────────────────────────────┼───────────────────────────────────────┐ │
│  │                                   ▼          STORAGE LAYER                │ │
│  │                                                                           │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    Write-Ahead Log                              │    │ │
│  │   │  • Append-only                                                  │    │ │
│  │   │  • Checksummed entries                                          │    │ │
│  │   │  • Segment-based (for compaction)                               │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                   │                                       │ │
│  │   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────┐   │ │
│  │   │     LSM Tree       │   │   Inverted Index   │   │  Time-Series   │   │ │
│  │   │  (Current State)   │   │     (Search)       │   │   (Metrics)    │   │ │
│  │   └────────────────────┘   └────────────────────┘   └────────────────┘   │ │
│  │                                   │                                       │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │   │                    io_uring / Direct I/O                        │    │ │
│  │   │  • Zero-copy where possible                                     │    │ │
│  │   │  • Bypasses page cache                                          │    │ │
│  │   │  • Predictable latency                                          │    │ │
│  │   └─────────────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Write Path (Command)

```
Client                          Leader                          Followers
   │                               │                                │
   │  POST /api/talents            │                                │
   │  ─────────────────────────►   │                                │
   │                               │                                │
   │                    ┌──────────┴──────────┐                     │
   │                    │ 1. Validate command │                     │
   │                    │ 2. Generate event   │                     │
   │                    │ 3. Append to WAL    │                     │
   │                    └──────────┬──────────┘                     │
   │                               │                                │
   │                               │  AppendEntries RPC             │
   │                               │  ─────────────────────────────►│
   │                               │                                │
   │                               │◄───────────────────────────────│
   │                               │  Ack (majority)                │
   │                               │                                │
   │                    ┌──────────┴──────────┐                     │
   │                    │ 4. Commit entry     │                     │
   │                    │ 5. Apply to state   │                     │
   │                    │ 6. Update indexes   │                     │
   │                    └──────────┬──────────┘                     │
   │                               │                                │
   │  201 Created                  │                                │
   │  ◄────────────────────────────│                                │
   │                               │                                │
```

### Read Path (Query)

```
Client                          Any Node
   │                               │
   │  GET /api/talents/:id         │
   │  ─────────────────────────►   │
   │                               │
   │                    ┌──────────┴──────────┐
   │                    │ 1. Check LSM cache  │
   │                    │ 2. Read from disk   │
   │                    │ 3. Verify checksum  │
   │                    └──────────┬──────────┘
   │                               │
   │  200 OK + data                │
   │  ◄────────────────────────────│
   │                               │
```

## Crate Structure

```
mox/
├── Cargo.toml
├── src/
│   ├── main.rs                    # Entry point, CLI
│   ├── lib.rs                     # Library root
│   │
│   ├── io/                        # I/O abstraction layer
│   │   ├── mod.rs
│   │   ├── traits.rs              # IO trait (real vs sim)
│   │   ├── uring.rs               # io_uring implementation
│   │   └── sim.rs                 # Simulation implementation
│   │
│   ├── storage/                   # Storage engine
│   │   ├── mod.rs
│   │   ├── wal.rs                 # Write-ahead log
│   │   ├── segment.rs             # Log segments
│   │   ├── lsm.rs                 # LSM tree for state
│   │   ├── index.rs               # Inverted index for search
│   │   └── checksum.rs            # CRC32/XXHash
│   │
│   ├── consensus/                 # Distributed consensus
│   │   ├── mod.rs
│   │   ├── raft.rs                # Raft implementation
│   │   ├── log.rs                 # Replicated log
│   │   ├── election.rs            # Leader election
│   │   ├── replication.rs         # Log replication
│   │   └── membership.rs          # Cluster membership
│   │
│   ├── vsr/                       # Viewstamped Replication extensions
│   │   ├── mod.rs
│   │   ├── view_change.rs         # View change protocol
│   │   ├── state_transfer.rs      # State transfer
│   │   └── reconfiguration.rs     # Dynamic reconfiguration
│   │
│   ├── state_machine/             # Application state machine
│   │   ├── mod.rs
│   │   ├── command.rs             # Command types
│   │   ├── event.rs               # Event types
│   │   ├── apply.rs               # Event application
│   │   └── snapshot.rs            # State snapshots
│   │
│   ├── domain/                    # Business domains
│   │   ├── mod.rs
│   │   ├── talent/
│   │   ├── campaign/
│   │   ├── contract/
│   │   ├── tenant/
│   │   ├── outreach/
│   │   ├── analytics/
│   │   └── integration/
│   │
│   ├── api/                       # HTTP API layer
│   │   ├── mod.rs
│   │   ├── router.rs              # Axum router
│   │   ├── handlers/              # Request handlers
│   │   ├── middleware/            # Auth, tracing, etc.
│   │   └── websocket.rs           # WebSocket support
│   │
│   ├── network/                   # Cluster networking
│   │   ├── mod.rs
│   │   ├── protocol.rs            # Binary protocol
│   │   ├── connection.rs          # Connection management
│   │   └── message.rs             # Message types
│   │
│   ├── simulator/                 # Deterministic simulation
│   │   ├── mod.rs
│   │   ├── cluster.rs             # Simulated cluster
│   │   ├── network.rs             # Simulated network
│   │   ├── disk.rs                # Simulated disk
│   │   ├── time.rs                # Simulated time
│   │   └── faults.rs              # Fault injection
│   │
│   └── observability/             # Metrics & logging
│       ├── mod.rs
│       ├── metrics.rs             # Prometheus metrics
│       └── logging.rs             # Structured logging
│
├── tests/
│   ├── simulation/                # Simulation tests
│   │   ├── consensus_test.rs
│   │   ├── replication_test.rs
│   │   └── chaos_test.rs
│   └── integration/               # Integration tests
│
└── benches/                       # Benchmarks
    ├── storage_bench.rs
    ├── consensus_bench.rs
    └── throughput_bench.rs
```

## Configuration

```toml
# mox.toml

[cluster]
node_id = 1
nodes = [
    { id = 1, host = "node1.mox.local", client_port = 8080, cluster_port = 9000 },
    { id = 2, host = "node2.mox.local", client_port = 8080, cluster_port = 9000 },
    { id = 3, host = "node3.mox.local", client_port = 8080, cluster_port = 9000 },
]

[storage]
data_dir = "/var/lib/mox"
wal_segment_size = "64MB"
cache_size = "1GB"
fsync = true
direct_io = true

[consensus]
election_timeout_min = "150ms"
election_timeout_max = "300ms"
heartbeat_interval = "50ms"
snapshot_threshold = 100000  # entries before snapshot

[api]
bind_address = "0.0.0.0:8080"
max_connections = 10000
request_timeout = "30s"

[limits]
max_batch_size = 1000
max_message_size = "16MB"
max_tenants = 10000
max_events_per_second = 100000
```

## Invariants

These must hold at all times:

1. **Linearizability**: All committed operations appear in a single global order
2. **Durability**: Committed data survives any minority of node failures
3. **Consistency**: All nodes agree on the order of committed operations
4. **Liveness**: The system makes progress if a majority of nodes are available
5. **Tenant Isolation**: No tenant can access another tenant's data
6. **Checksum Validity**: All read data has valid checksums

## Performance Targets

| Metric | Target |
|--------|--------|
| Write latency (p50) | < 1ms |
| Write latency (p99) | < 10ms |
| Read latency (p50) | < 100μs |
| Read latency (p99) | < 1ms |
| Throughput (writes) | 100K ops/sec |
| Throughput (reads) | 500K ops/sec |
| Recovery time | < 10 seconds |
| Replication lag | < 100ms |

## References

- [TigerBeetle Design Doc](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/DESIGN.md)
- [Raft Paper](https://raft.github.io/raft.pdf)
- [Viewstamped Replication Revisited](https://pmg.csail.mit.edu/papers/vr-revisited.pdf)
- [io_uring and eBPF](https://kernel.dk/io_uring.pdf)
- [FoundationDB Testing](https://www.youtube.com/watch?v=4fFDFbi3toc)
