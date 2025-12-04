# Mox EDA — TigerBeetle Architecture RFCs

> **Single binary. Zero dependencies. Deterministic. Clustered.**

## Philosophy

We're building Mox the TigerBeetle way:

1. **One binary** — No Docker, no Kubernetes, no managed services
2. **Zero external dependencies** — Everything embedded
3. **Deterministic simulation testing** — Simulate years of failures in minutes
4. **Raft consensus** — Fault-tolerant replication from day one
5. **Direct I/O** — io_uring, no filesystem caching, predictable latency

## RFC Index

| RFC | Title | Status |
|-----|-------|--------|
| [RFC-0001](./RFC-0001-architecture-overview.md) | Architecture Overview | Draft |
| [RFC-0002](./RFC-0002-storage-engine.md) | Storage Engine | Draft |
| [RFC-0003](./RFC-0003-consensus-replication.md) | Consensus & Replication | Draft |
| [RFC-0004](./RFC-0004-state-machine.md) | State Machine | Draft |
| [RFC-0005](./RFC-0005-deterministic-simulation.md) | Deterministic Simulation Testing | Draft |
| [RFC-0006](./RFC-0006-network-protocol.md) | Network Protocol | Draft |
| [RFC-0007](./RFC-0007-domain-model.md) | Domain Model | Draft |
| [RFC-0008](./RFC-0008-api-layer.md) | API Layer | Draft |

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MOX CLUSTER (3+ nodes)                             │
│                                                                                 │
│   ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐      │
│   │       Node 1        │ │       Node 2        │ │       Node 3        │      │
│   │      (Leader)       │ │     (Follower)      │ │     (Follower)      │      │
│   │                     │ │                     │ │                     │      │
│   │  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │      │
│   │  │  HTTP :8080   │  │ │  │  HTTP :8080   │  │ │  │  HTTP :8080   │  │      │
│   │  └───────────────┘  │ │  └───────────────┘  │ │  └───────────────┘  │      │
│   │         │           │ │         │           │ │         │           │      │
│   │  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │      │
│   │  │ State Machine │  │ │  │ State Machine │  │ │  │ State Machine │  │      │
│   │  │   (Domains)   │  │ │  │   (Domains)   │  │ │  │   (Domains)   │  │      │
│   │  └───────────────┘  │ │  └───────────────┘  │ │  └───────────────┘  │      │
│   │         │           │ │         │           │ │         │           │      │
│   │  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │      │
│   │  │     Raft      │◄─┼─┼──│     Raft      │◄─┼─┼──│     Raft      │  │      │
│   │  │   Consensus   │──┼─┼─►│   Consensus   │──┼─┼─►│   Consensus   │  │      │
│   │  └───────────────┘  │ │  └───────────────┘  │ │  └───────────────┘  │      │
│   │         │           │ │         │           │ │         │           │      │
│   │  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │      │
│   │  │Storage Engine │  │ │  │Storage Engine │  │ │  │Storage Engine │  │      │
│   │  │  (io_uring)   │  │ │  │  (io_uring)   │  │ │  │  (io_uring)   │  │      │
│   │  └───────────────┘  │ │  └───────────────┘  │ │  └───────────────┘  │      │
│   └─────────────────────┘ └─────────────────────┘ └─────────────────────┘      │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                         Load Balancer (Optional)                        │  │
│   │                     Routes writes to leader, reads anywhere             │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Cost Model

| Environment | Nodes | Spec | Monthly Cost |
|-------------|-------|------|--------------|
| Development | 1 | 2 vCPU, 4GB RAM | $20 |
| Staging | 3 | 2 vCPU, 4GB RAM | $60 |
| Production | 3-5 | 4 vCPU, 16GB RAM, NVMe | $150-300 |

## Deployment

```bash
# Build
cargo build --release

# Deploy to 3 nodes
scp target/release/mox node1:/usr/local/bin/
scp target/release/mox node2:/usr/local/bin/
scp target/release/mox node3:/usr/local/bin/

# Start cluster
ssh node1 'mox start --cluster node1:9000,node2:9000,node3:9000 --id 1'
ssh node2 'mox start --cluster node1:9000,node2:9000,node3:9000 --id 2'
ssh node3 'mox start --cluster node1:9000,node2:9000,node3:9000 --id 3'
```

## Inspiration

- [TigerBeetle](https://tigerbeetle.com/) — Financial accounting database
- [FoundationDB](https://www.foundationdb.org/) — Simulation testing pioneer
- [Jepsen](https://jepsen.io/) — Distributed systems testing
- [Raft](https://raft.github.io/) — Understandable consensus

## Implementation Timeline

| Week | Milestone |
|------|-----------|
| 1-2 | Storage engine with io_uring |
| 3-4 | Raft consensus implementation |
| 5-6 | State machine + domain logic |
| 7-8 | Deterministic simulation harness |
| 9-10 | Network protocol + client |
| 11-12 | API layer + webhooks |
| 13-14 | Production hardening |
| 15-16 | Chaos testing + benchmarks |
