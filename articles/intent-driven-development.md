# Intent-Driven Development: Define the System Before You Write the Code

*How I architected a complete event-driven system with 122 events, 8 RFCs, and 82 GitHub Issues—without writing a single line of implementation code.*

---

## The Problem With "Code First"

We've all been there.

You get a feature request. You spin up a branch. You start coding. Three days later, you realize the data model is wrong. A week later, you're refactoring because another team's API doesn't work the way you assumed. A month later, someone asks "wait, what does this system actually do?" and nobody can answer without reading the code.

The traditional software development loop looks like this:

```
Vague Requirements → Code → Debug → More Code → Hope → Ship → Regret
```

We've normalized this. We call it "agile." We say "the code is the documentation." We accept that understanding a system requires archaeology.

**But what if we inverted the entire process?**

---

## Introducing Intent-Driven Development

Intent-Driven Development is a methodology where you **fully specify what a system does before you write any implementation code**. Not just high-level requirements—complete, machine-readable specifications that can be transformed into trackable work.

The flow looks like this:

```
Define Intent → Architect → Operationalize → Implement → Validate
      ↓              ↓            ↓              ↓           ↓
   AsyncAPI       RFCs        JSON Tasks     Code       Tests
   122 events    8 docs      74 tasks       [future]   [future]
```

I recently applied this methodology to design a TigerBeetle-inspired event-sourced platform. Here's exactly how it works.

---

## Phase 1: Define Intent (AsyncAPI Specification)

Before writing any code, I defined **every event the system would ever emit**.

Using [AsyncAPI](https://www.asyncapi.com/)—think OpenAPI but for event-driven systems—I specified:

- **122 event types** across 14 domains
- **Schemas** for every event payload
- **Channels** for event routing
- **Publishers and subscribers** for each operation

Here's a taste:

```yaml
# asyncapi.yaml
channels:
  talent.created:
    messages:
      TalentCreated:
        payload:
          type: object
          properties:
            talent_id:
              type: string
              format: uuid
            tenant_id:
              type: string
            display_name:
              type: string
            platforms:
              type: array
              items:
                $ref: '#/components/schemas/PlatformConnection'
            created_at:
              type: string
              format: date-time
```

**Why this matters:**
- Everyone (devs, PMs, stakeholders) can read the spec and understand what the system does
- The spec is machine-readable—you can generate code, docs, and tests from it
- No ambiguity about "what events exist" or "what data they carry"

---

## Phase 2: Architect (RFCs)

With the event model defined, I wrote **8 Architecture RFCs** covering every technical component:

| RFC | Topic | Key Decisions |
|-----|-------|---------------|
| RFC-0001 | Architecture Overview | Single-binary, TigerBeetle-inspired design |
| RFC-0002 | Storage Engine | WAL + LSM Tree with io_uring |
| RFC-0003 | Consensus | Raft with Viewstamped Replication |
| RFC-0004 | State Machine | Command/Event processing, domain logic |
| RFC-0005 | Simulation Testing | Deterministic testing with fault injection |
| RFC-0006 | Network Protocol | Binary protocol, TLS, batching |
| RFC-0007 | Domain Model | All 14 domains mapped to state machine |
| RFC-0008 | API Layer | HTTP, WebSocket, Webhooks |

Each RFC follows a consistent structure:
- **Summary**: What this component does
- **Motivation**: Why we need it
- **Design**: How it works (with code examples)
- **Acceptance Criteria**: How we'll know it's done

**Why this matters:**
- Forces you to think through the hard problems *before* coding
- Creates shared understanding across the team
- Becomes permanent documentation (not a stale wiki)

---

## Phase 3: Operationalize (JSON Schemas → GitHub Issues)

Here's where it gets interesting.

I transformed each RFC into a **machine-readable JSON schema**:

```json
{
  "id": "RFC-0002",
  "title": "Storage Engine",
  "tasks": [
    {
      "id": "TASK-001",
      "title": "Implement WAL entry header format",
      "description": "Define the binary format for WAL entries...",
      "acceptance_criteria_ids": ["AC-001", "AC-002"],
      "estimate": "m",
      "labels": ["storage", "wal"]
    }
  ],
  "acceptance_criteria": [
    {
      "id": "AC-001",
      "criterion": "Entry includes timestamp, term, index, and CRC32C checksum",
      "verification": "Unit test validates header serialization"
    }
  ]
}
```

Then I wrote a Python script to **automatically import these into GitHub Issues**:

```bash
$ python scripts/import_issues.py

✓ Created milestone: RFC-0002: Storage Engine
✓ Created issue: [RFC-0002] Implement WAL entry header format
✓ Created issue: [RFC-0002] Implement WAL append and sync
...
✓ Import complete! Created 82 issues.
```

**The result:**
- **8 Milestones** (one per RFC)
- **82 Issues** with full descriptions, acceptance criteria, labels, and dependencies
- **Complete traceability** from spec → RFC → task → implementation

---

## Phase 4: The "RAG Environment" Insight

Here's what I didn't expect: **the project itself becomes a knowledge base for AI-assisted development**.

Think about it:

| Artifact | What AI Can Query |
|----------|-------------------|
| `asyncapi.yaml` | "What events exist in the system?" |
| `RFC-*.md` | "How does the storage engine work?" |
| `RFC-*.json` | "What tasks are needed for consensus?" |
| GitHub Issues | "What's already implemented?" |
| Acceptance Criteria | "How do I know this task is done?" |

An AI coding assistant (like [Windsurf](https://windsurf.com/refer?referral_code=f718a97d8e), Cursor, or Copilot) can now:

1. Read the RFC to understand the architecture
2. Check the JSON schema for task details
3. Query GitHub to see what's done vs pending
4. Generate code that fits the design
5. Write tests based on acceptance criteria

**GitHub Issues become a state machine:**

```
[OPEN] → [IN PROGRESS] → [CLOSED]
   ↓           ↓             ↓
Queryable   Working      Verified
Context     on it        Complete
```

The project is no longer just code—it's a **semantic index** that humans and AI can traverse.

---

## What I Built (Without Building Anything)

| Artifact | Count |
|----------|-------|
| Event Types | 122 |
| Domains | 14 |
| RFCs | 8 |
| Tasks | 74 |
| Acceptance Criteria | 73 |
| GitHub Issues | 82 |
| Architecture Diagrams | 7 |
| Lines of Implementation Code | **0** |

Estimated implementation effort: **~343 developer-days**

But here's the thing: that estimate is *meaningful* now. It's based on defined tasks, not vibes.

---

## The Benefits

### 1. Parallelizable Work
With 82 well-defined issues across 8 milestones, multiple developers can work independently without stepping on each other.

### 2. Measurable Progress
- 0/82 issues closed = 0% complete
- 41/82 issues closed = 50% complete
- No "it's almost done" hand-waving

### 3. Reduced Rework
Acceptance criteria are defined *before* coding. PRs are reviewed against clear expectations.

### 4. Onboarding Efficiency
New team members can:
1. Read the AsyncAPI spec (30 min)
2. Skim the RFCs (1 hour)
3. Pick an issue and start contributing (day 1)

### 5. AI-Amplified Development
The structured artifacts make AI tools significantly more effective. Context is persistent and queryable.

---

## When to Use This Approach

Intent-Driven Development works best when:

- ✅ You're building something complex (many domains, many events)
- ✅ Multiple people will work on the system
- ✅ You need strong consistency and auditability
- ✅ You want to leverage AI coding assistants effectively
- ✅ You value documentation that stays accurate

It might be overkill when:

- ❌ You're prototyping or exploring
- ❌ You're the only developer
- ❌ Requirements are genuinely unknown

---

## Try It Yourself

The complete project is open source:

🔗 **[github.com/copyleftdev/mox_eda](https://github.com/copyleftdev/mox_eda)**

You'll find:
- The full AsyncAPI specification (122 events)
- All 8 Architecture RFCs
- JSON task schemas
- The GitHub issue import script
- Architecture diagrams (generated as code)

Star it, fork it, or just browse it to see intent-driven development in action.

---

## Key Takeaways

1. **Specification is not bureaucracy**—it's investment in clarity
2. **RFCs force you to think before you code**—saving weeks of rework
3. **Machine-readable formats enable automation**—from docs to issues to code
4. **GitHub Issues can be a state machine**—not just a todo list
5. **AI works better with structured context**—the project becomes the prompt

---

*"The best way to predict the future is to design it."* — Alan Kay

---

**What do you think?** Have you tried specification-first development? What challenges have you faced? Drop a comment below or join the discussion on the repo.

---

*Tags: #softwaredevelopment #architecture #asyncapi #eventdriven #ai #productivity #rust #methodology*
