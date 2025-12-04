# Mox EDA

> **🎓 Intent-Driven Software Development Showcase**

> **This is not a production project.** It's a demonstration of how software development can be approached with deliberate intent, transforming high-level specifications into actionable, trackable work before writing a single line of implementation code.

---

## 🎯 The Core Philosophy

Traditional software development often follows a pattern of:
1. Vague requirements → Code → Debugging → More code → Hope

**Intent-Driven Development** inverts this:
1. **Define Intent** → Capture the complete system behavior as a specification
2. **Architect with Purpose** → Write RFCs that describe *how* each component works
3. **Make Work Visible** → Transform architecture into trackable tasks
4. **Implement with Confidence** → Code against well-defined acceptance criteria
5. **Validate Continuously** → Tests verify the intent was met

---

## 📊 What We Built (Without Writing Implementation Code)

| Artifact | Count | Purpose |
|----------|-------|---------|
| **AsyncAPI Specification** | 1 | Complete event-driven architecture definition |
| **Event Types** | 122 | Every domain event the system will emit |
| **Domains** | 14 | Bounded contexts with clear boundaries |
| **Architecture RFCs** | 8 | Detailed technical specifications |
| **JSON Task Schemas** | 8 | Machine-readable, deterministic task definitions |
| **GitHub Issues** | 82 | Trackable, actionable work items |
| **Acceptance Criteria** | 73 | Verifiable success conditions |
| **Architecture Diagrams** | 7 | Visual system documentation |

---

## 🔄 The Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INTENT PHASE                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   AsyncAPI Spec          What events exist? What data do they carry?│
│        │                 Who publishes? Who subscribes?             │
│        ▼                                                            │
│   122 Events             TalentCreated, CampaignStarted,            │
│   14 Domains             ContractSigned, StripePayoutProcessed...   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                       ARCHITECTURE PHASE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   RFC-0001               Single-binary, TigerBeetle-inspired        │
│   Architecture           Zero external dependencies                 │
│        │                                                            │
│        ▼                                                            │
│   RFC-0002-0008          Storage Engine (WAL + LSM)                 │
│   Technical Specs        Raft Consensus + VR Extensions             │
│                          State Machine + Domain Model               │
│                          Deterministic Simulation Testing           │
│                          Network Protocol (Binary, TLS)             │
│                          API Layer (HTTP, WebSocket, Webhooks)      │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                      OPERATIONALIZATION PHASE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   JSON Schemas           Deterministic, machine-readable            │
│        │                 74 Tasks with dependencies                 │
│        │                 73 Acceptance criteria                     │
│        ▼                                                            │
│   import_issues.py       Automated GitHub issue creation            │
│        │                                                            │
│        ▼                                                            │
│   GitHub Project         8 Milestones (1 per RFC)                   │
│                          82 Issues with labels, links               │
│                          Full traceability                          │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                      IMPLEMENTATION PHASE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Pick Issue             [RFC-0002] Implement WAL entry format      │
│        │                                                            │
│        ▼                                                            │
│   Acceptance Criteria    ✓ Entry includes timestamp, term, index    │
│                          ✓ CRC32C checksum validated                │
│                          ✓ Serialize/deserialize round-trips        │
│        │                                                            │
│        ▼                                                            │
│   Write Code             Focused, testable, reviewable              │
│        │                                                            │
│        ▼                                                            │
│   Close Issue            PR linked, criteria verified               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture Highlights

### TigerBeetle-Inspired Design
- **Single Binary**: No Kubernetes, no message queues, no external databases
- **Zero Dependencies**: Custom storage, custom networking, custom everything
- **Deterministic**: Same input = same output, always
- **Simulation-Tested**: Run years of operation in minutes

### Technical Stack (Planned)
- **Language**: Rust (memory safety, performance, fearless concurrency)
- **Storage**: Custom WAL + LSM Tree with io_uring
- **Consensus**: Raft with Viewstamped Replication extensions
- **API**: Axum (HTTP/WS), custom binary protocol (cluster)
- **Testing**: Deterministic simulation with fault injection

---

## 📁 Repository Structure

```
mox_eda/
├── asyncapi.yaml              # Complete event specification
├── components/                # Modular AsyncAPI components
│   ├── schemas/               # Event data schemas
│   ├── messages/              # Message definitions  
│   └── channels/              # Channel definitions
├── docs/
│   └── rfcs/
│       ├── RFC-0001-architecture-overview.md
│       ├── RFC-0002-storage-engine.md
│       ├── RFC-0003-consensus-replication.md
│       ├── RFC-0004-state-machine.md
│       ├── RFC-0005-deterministic-simulation.md
│       ├── RFC-0006-network-protocol.md
│       ├── RFC-0007-domain-model.md
│       ├── RFC-0008-api-layer.md
│       └── schema/
│           ├── rfc-schema.json    # JSON schema for RFCs
│           ├── RFC-0001.json      # Machine-readable RFCs
│           └── ...
├── diagrams/                  # Architecture diagrams (as code)
│   ├── generate_all.py
│   ├── architecture_overview.py
│   └── output/                # Generated PNGs
└── scripts/
    └── import_issues.py       # GitHub issue importer
```

---

## 🤖 AI-Native Development: The Project as Context

This architecture creates something powerful: **the project itself becomes a RAG (Retrieval-Augmented Generation) environment**.

### GitHub Issues as State Management

Think of GitHub Issues not just as a todo list, but as a **distributed state machine** for development:

```
┌─────────────────────────────────────────────────────────────┐
│                    ISSUE STATE MACHINE                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   [OPEN]  ──────►  [IN PROGRESS]  ──────►  [CLOSED]        │
│     │                    │                    │             │
│     │                    │                    │             │
│     ▼                    ▼                    ▼             │
│   Queryable          AI/Human             Verified          │
│   Context            Working              Complete          │
│                                                             │
│   "What needs        "What's being        "What's the       │
│    to be done?"       worked on?"          system state?"   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Structured Context for AI Agents

An AI agent (like Windsurf/Cascade) can:

1. **Query the AsyncAPI spec** → Understand what events exist
2. **Read the relevant RFC** → Understand the architecture
3. **Parse the JSON schema** → Get machine-readable task details
4. **Check GitHub Issues** → Know what's done vs pending
5. **Read acceptance criteria** → Know when the task is complete
6. **Generate implementation** → Write code that fits the design

```python
# Pseudo-code for AI-assisted development
context = {
    "spec": load("asyncapi.yaml"),           # What events?
    "rfc": load("RFC-0004-state-machine.md"), # How does it work?
    "task": github.get_issue(42),             # What to build?
    "criteria": task["acceptance_criteria"],  # When is it done?
    "existing_code": codebase.search(task),   # What exists?
}

implementation = ai.generate(context)
tests = ai.generate_tests(context["criteria"])
```

### Why This Works

| Traditional Dev | Intent-Driven + AI |
|-----------------|-------------------|
| Vague requirements | Structured AsyncAPI spec |
| Tribal knowledge | Documented RFCs |
| "It's in my head" | Machine-readable JSON |
| Manual tracking | GitHub as state machine |
| Context switching | Persistent, queryable context |

The entire repository becomes a **semantic index** that AI can traverse:
- **asyncapi.yaml** → Event ontology
- **RFC-*.md** → Architectural decisions
- **RFC-*.json** → Actionable tasks
- **GitHub Issues** → Current state
- **Code** → Implementation (links back to issues)

---

## 🚀 How This Empowers Development

### 1. **Shared Understanding**
Everyone—developers, PMs, stakeholders—can read the AsyncAPI spec and understand exactly what the system does. No ambiguity.

### 2. **Parallelizable Work**
With 82 well-defined issues across 8 milestones, multiple developers can work independently without stepping on each other.

### 3. **Measurable Progress**
- 0/82 issues closed = 0% complete
- 41/82 issues closed = 50% complete
- No "it's almost done" hand-waving

### 4. **Reduced Rework**
Acceptance criteria are defined *before* coding. PRs are reviewed against clear expectations.

### 5. **Onboarding Efficiency**
New team members can:
1. Read the AsyncAPI spec (30 min)
2. Skim the RFCs (1 hour)
3. Pick an issue and start contributing (day 1)

### 6. **AI-Assisted Development**
The JSON schemas are designed to be LLM-friendly. An AI can:
- Generate boilerplate code from task descriptions
- Write tests from acceptance criteria
- Review PRs against the RFC specifications

---

## 📈 Metrics & Visibility

### GitHub Project Dashboard
- **8 Milestones** tracking RFC completion
- **Labels** for size (XS to XL), priority, domain
- **Dependencies** between tasks clearly marked
- **Acceptance criteria** as checklists in each issue

### Estimated Effort Distribution
| Size | Count | Est. Days Each | Total Days |
|------|-------|----------------|------------|
| XS   | 5     | < 1            | ~3         |
| S    | 20    | 1-2            | ~30        |
| M    | 25    | 3-5            | ~100       |
| L    | 18    | 5-10           | ~135       |
| XL   | 6     | 10-15          | ~75        |
| **Total** | **74 tasks** | | **~343 dev-days** |

---

## 🎓 Key Takeaways

1. **Specification is not bureaucracy**—it's investment in clarity
2. **RFCs force you to think before you code**—saving weeks of rework
3. **Machine-readable formats enable automation**—from docs to issues to code
4. **Diagrams as code are maintainable**—text diffs, version control, automation
5. **The best code is code you didn't have to rewrite**

---

## 🔧 Generating the Diagrams

```bash
# Install dependencies
pip install diagrams

# Generate all diagrams
cd diagrams
python generate_all.py

# Output in diagrams/output/*.png
```

---

## 📚 References

- [TigerBeetle Architecture](https://tigerbeetle.com/) - Inspiration for single-binary design
- [AsyncAPI Specification](https://www.asyncapi.com/) - Event-driven API specification
- [Raft Consensus](https://raft.github.io/) - Distributed consensus algorithm
- [Diagrams (Python)](https://diagrams.mingrammer.com/) - Diagram as Code

---

## 🤝 The Human + AI Collaboration

This entire specification was created through human-AI collaboration:
- **Human**: Vision, domain knowledge, architectural decisions
- **AI (Cascade)**: Specification generation, consistency checking, automation scripts

This showcases how AI can amplify human intent rather than replace human judgment.

---

*"The best way to predict the future is to design it."* — Alan Kay
