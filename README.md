# Session Baton

**Structured cross-session state handoff for AI coding agents.**

> "I don't prompt Claude anymore. I have loops that are running. My job is to write loops."
> — Boris Cherny, Claude Code Engineering Lead

Most AI coding sessions are stateless. You start, you work, you stop. Next time, the agent has amnesia. Session Baton changes that.

## What It Does

Session Baton is a lightweight state store that sits between your AI coding sessions. It tracks four types of cross-session state:

| Type | What It Tracks | Lifecycle |
|---|---|---|
| **Open Loops** | Actions you took + expected outcomes | Auto-verify next session, then archive |
| **Follow-ups** | Deferred tasks with escalation | Auto-escalate after N deferrals |
| **Patterns** | Recurring failure modes | Graduate to enforced rules at threshold |
| **Decisions** | Choices with rationale + evidence | Active until superseded |

The key insight: **the output of each session becomes the input of the next session.** This creates a spiral, not a flat repeat.

```
Session N                          Session N+1
┌─────────────┐                    ┌─────────────┐
│ BOOT        │◄── read baton ◄────│ baton store  │
│ ORIENT      │    (what happened  │              │
│ EXECUTE     │     last time?)    │  open_loops  │
│ REFLECT     │                    │  follow_ups  │
│ PERSIST ────┼──► write baton ──►│  patterns    │
└─────────────┘                    │  decisions   │
                                   └──────┬───────┘
                                          │
                                   ┌──────▼───────┐
                                   │ Session N+2   │
                                   │ BOOT ◄── read │
                                   └──────────────┘
```

## Why This Matters: Loop Engineering

Loop Engineering is the emerging practice of designing systems where AI agents discover work, execute, verify, and hand off state autonomously. It sits above Prompt Engineering (crafting prompts) and Harness Engineering (configuring agent environments).

Most implementations stop at "dump a summary at session end." Session Baton goes further:

- **Action-Outcome Verification**: Record what you did + expected outcome. Next session, automatically verify.
- **Pattern-to-Rule Graduation**: Track recurring failures. At threshold (default: 3 occurrences), propose upgrading to an enforced rule.
- **Three-Tier Handoff**: Impact (short-lived, auto-verify), Decision (medium-lived, with rationale), Experience (long-lived, becomes rules).
- **Anti-Ouroboros Gate**: LLM-derived patterns cannot self-promote to rules. Human approval required. ([ACA](https://github.com/MakiDevelop/agent-civilization-architecture) compliance)

## Quick Start

### Option 1: Standalone server

```bash
pip install fastapi uvicorn pydantic
git clone https://github.com/MakiDevelop/session-baton.git
cd session-baton
python -m src.server
# Server runs on http://127.0.0.1:9101
```

### Option 2: Docker

```bash
docker compose up -d
```

### Option 3: Add to existing memory system

Session Baton is designed to coexist with any memory system (memhall, mem0, Letta, etc.). The baton table can be added to your existing SQLite database:

```sql
CREATE TABLE IF NOT EXISTS batons (
    namespace TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL
);
```

## API

### Read Baton

```bash
curl -X POST http://localhost:9101/v1/baton/read \
  -H "Content-Type: application/json" \
  -d '{"namespace": "my-project"}'
```

Response:
```json
{
  "baton": { "open_loops": [...], "follow_ups": [...], ... },
  "namespace": "my-project",
  "updated_at": "2026-06-17T12:00:00+00:00"
}
```

### Write Baton

```bash
curl -X POST http://localhost:9101/v1/baton/write \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "my-project",
    "baton": {
      "schema_version": 1,
      "session_id": "2026-06-17-001",
      "open_loops": [
        {
          "id": "OL-001",
          "action": "Deployed service X",
          "expected_outcome": "Health endpoint returns 200",
          "verify": {
            "method": "http",
            "url": "https://service-x.example.com/health",
            "expected_status": 200
          },
          "created_at": "2026-06-17",
          "status": "open",
          "source_tier": "llm_derived"
        }
      ],
      "follow_ups": [],
      "patterns": [],
      "active_decisions": [],
      "context": "Deployed service X, pending verification."
    }
  }'
```

## Baton Schema

```yaml
baton:
  schema_version: 1
  session_id: "2026-06-17-001"
  parent_session: null            # session lineage

  open_loops:                     # Impact tier (Hot)
    - id: "OL-001"
      action: "Deployed X"
      verify:
        method: http              # http | file_exists | process_running | manual
        url: "https://..."
        expected_status: 200
      status: open                # open → verified | failed | escalated
      source_tier: llm_derived    # ACA L1 compliance

  follow_ups:                     # Task queue with escalation
    - id: "FU-001"
      item: "Refactor scoring formula"
      defer_count: 5              # auto-escalate at 3 and 5
      priority: escalated         # normal → elevated → escalated
      source_tier: llm_derived

  patterns:                       # Experience tier (accumulating)
    - id: "PAT-001"
      what: "Assumed Docker architecture without reading compose"
      count: 3
      recent_occurrences: [...]   # capped at 5 (FIFO)
      status: rule_candidate      # observing → rule_candidate → graduated
      source_tier: llm_derived    # cannot self-graduate (Anti-Ouroboros)

  active_decisions:               # Decision tier (Warm)
    - id: "DEC-001"
      what: "Always use --update-env-vars"
      why: "--set-env-vars clears existing variables"
      evidence: ["2026-06-12 incident"]
      status: active              # active → monitoring → superseded
      source_tier: human_confirmed

  context: "Free-form session narrative."
```

## Integration with Claude Code

Add to your `/start` skill:

```bash
# Read baton at session start
BATON=$(curl -s -X POST http://localhost:9101/v1/baton/read \
  -H "Content-Type: application/json" \
  -d '{"namespace": "my-project"}')
```

Add to your `/wrap-up` skill:

```bash
# Write baton at session end
curl -s -X POST http://localhost:9101/v1/baton/write \
  -H "Content-Type: application/json" \
  -d "{\"namespace\": \"my-project\", \"baton\": $BATON_JSON}"
```

See `skills/` directory for complete skill templates.

## ACA Compliance

Session Baton implements [ACA (Agent Civilization Architecture)](https://github.com/MakiDevelop/agent-civilization-architecture) Layer 1 Memory session-state extension:

- **`source_tier`** field on every item (`raw_source` / `llm_derived` / `human_confirmed`)
- **Anti-Ouroboros Gate**: Patterns with `source_tier: llm_derived` cannot auto-graduate to rules. Human confirmation required.
- **Namespace isolation**: Inherits trust boundaries from your memory system.

## Local Cache / Offline Fallback

Session Baton includes a local cache module (`src/cache.py`) for resilience:

- **Write-through**: Every successful remote write also writes to `~/.claude/loop/batons/{namespace}.json`
- **Read fallback**: When remote is unreachable, read from local cache
- **Dirty tracking**: Failed remote writes are marked `pending_upload`, auto-synced next session

## Design Decisions

See `spec/SPEC.md` for the full specification, including:

- Council review (7-agent + 2 scout review process)
- Risk analysis and edge case handling
- ACA compliance details
- Migration and rollback plan

## Related

- [Loop Engineering knowledge base](https://chiba.tw/loop-engineering/) (Chinese)
- [ACA Protocol](https://github.com/MakiDevelop/agent-civilization-architecture)
- [Agent Memory Hall](https://github.com/MakiDevelop/memory-hall) (ACA Layer 1-3 reference implementation)
- [Addy Osmani's Loop Engineering](https://addyosmani.com/blog/loop-engineering/)

## License

MIT
