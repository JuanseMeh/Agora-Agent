# AI Agent Service

## Overview

This service is part of a larger microservices platform designed to optimize the administrative workload of teachers in virtual classroom environments. The platform handles grading, student progress tracking, and class content generation — reducing manual effort and centralizing classroom management.

The **AI Agent** is the conversational intelligence layer of this platform. It exposes a natural language interface that allows teachers to interact with the system through chat, translating plain instructions into concrete actions across the platform's services — without needing to navigate multiple views or trigger processes manually.

> This service is **not** the AI orchestrator. The orchestrator handles deterministic, scheduled, and batch AI pipelines (e.g. automated grading runs, bulk content generation). The agent is interactive and non-deterministic — it responds to user intent in real time.

---

## Responsibilities

- Interpret natural language instructions from teachers
- Query and surface data from platform services (workspaces, members, assignments, submissions)
- Trigger the two-phase grading workflow (suggest → approve) and direct grading via the orchestrator
- Fetch and present grading results, suggestions, and statistics
- Synthesize class-level feedback from grading output and deliver it proactively
- Return **structured, typed response blocks** (tables, cards, charts, stats) for rich frontend rendering
- Maintain per-session conversational memory

---

## What This Service Is NOT Responsible For

- Authentication and authorization (handled by `auth-service`, to be integrated in a later phase)
- Executing grading or content generation logic directly (delegated to `ai-orchestrator`)
- Persisting classroom or submission data (owned by `workspace-service`)
- Routing or load balancing (handled by `gateway-service`)

---

## Platform Services Context

| Service | Role | Protocol |
|---|---|---|
| `gateway-service` | Single entry point, request routing | REST |
| `auth-service` | Token issuance, identity, permissions | REST |
| `users-service` | User profiles, roles, preferences | REST |
| `workspace-service` | Workspaces, members, assignments, and submissions | REST |
| `ai-orchestrator` | Standardizes and executes LLM requests with rubrics, academic context and evaluation criteria. Handles automatic grading and periodic report generation — deterministic, traceable, reproducible | gRPC |
| `ai-agent` *(this service)* | Conversational AI interface for teachers | REST + SSE |

> **Note:** `workspace-service` owns four domains — Workspaces, Members, Assignments, and Submissions. All four are queried through the same service URL. There is no standalone service for any of them.

---

## Architecture

```
Teacher (chat input)
        │
        ▼
  [ AI Agent API ]          FastAPI — POST /chat
        │
        ▼
  [ LangGraph Agent ]       Gemini LLM + tool-calling loop
        │
   ┌────┴─────┐
   │  Tools   │             One tool per platform action
   └────┬─────┘
        │
   ┌────┴──────────────────────────────┐
   │  services/                        │
   │  ├── http_client      (REST)      │
   │  └── grpc_client      (gRPC)      │
   └────┬──────────────────────────────┘
        │
   ┌────┴────────────────────────────────────┐
   │  users-service      workspace-service   │
   │  ai-orchestrator    (assignments,       │
   │                      submissions incl.) │
   └─────────────────────────────────────────┘
        │
        ▼
  [ Response Builder ]      Assembles typed blocks
        │
        ▼
  AgentResponse JSON        { message, blocks: [table|card|chart|stat|alert] }
```

---

## Orchestrator gRPC Contract

The orchestrator exposes three RPC methods defining a two-phase grading workflow:

```
SuggestAssignment   →  generates AI grading suggestions (not committed)
ApproveSuggestion   →  commits a suggestion set as final grades
GradeAssignment     →  direct grading without suggestion phase
```

Both `SuggestAssignment` and `GradeAssignment` accept flexible targeting — either a list of `submission_ids` or `user_ids`, with an optional flag to include already-graded submissions. The agent decides which targeting strategy to use based on teacher intent.

`suggestion_id` is orchestrator-owned. The agent stores it as a reference in `grading_summaries` to track flow state across conversation turns.

---

## Response Schema

Every agent response returns a structured envelope — never plain text — so the frontend can render rich UI components directly.

```json
{
  "session_id": "uuid",
  "message": "Here are the grading results for your last session.",
  "blocks": [
    { "type": "stat", "label": "Submissions graded", "value": 38, "delta": null },
    { "type": "chart", "chart_type": "bar", "title": "Score distribution" },
    { "type": "table", "title": "Per-student results", "columns": ["..."], "rows": ["..."] },
    { "type": "card", "title": "Top suggestion" }
  ],
  "actions_triggered": ["suggest_assignment", "grading_results"],
  "error": null
}
```

Block types: `text` · `table` · `card` · `chart` · `stat` · `alert`

---

## Tool Categories

| Category | Tools | Target Service |
|---|---|---|
| `users` | get_user, list_members | `users-service` |
| `workspace` | get_workspace, list_workspaces | `workspace-service` |
| `members` | list_members, get_member | `workspace-service` |
| `assignments` | get_assignment, list_assignments | `workspace-service` |
| `submissions` | get_submission, list_submissions, submission_stats | `workspace-service` |
| `grading` | suggest_assignment, approve_suggestion, grade_assignment, grading_results | `ai-orchestrator` (gRPC) |
| `statistics` | workspace_stats, submission_stats | `workspace-service` |

---

## Proactive Feedback Delivery

The agent supports two interaction modes — reactive (teacher asks) and proactive (agent pushes).

### Reactive (standard)
The teacher asks a question → the agent calls tools → returns structured blocks.

### Proactive (event-driven)
When the orchestrator finishes a grading job, it notifies the agent via an internal webhook. The agent synthesizes the class feedback in the background and pushes it to the teacher's active session — no question needed, no user tokens spent.

```
Orchestrator finishes grading
        │
        POST /internal/events/grading-completed
        │
        ▼
Agent synthesizes feedback (background LLM call)
        │
        ▼
Result stored + pushed via SSE to teacher's open session
```

The synthesized summary is stored after the webhook so subsequent teacher questions load it as context instead of re-synthesizing from scratch.

### Token cost comparison

| Trigger | LLM runs | User tokens spent |
|---|---|---|
| Teacher asks a question | On demand | Yes |
| Webhook-triggered synthesis | At grading completion | No |
| Teacher asks follow-up | Loads cached summary | Minimal |

### Internal endpoint (not public)

```
POST /internal/events/grading-completed
Body: { suggestion_id, workspace_id, assignment_id, teacher_id }
```

---

## Database Model

### Storage split

| Store | Owns | Why |
|---|---|---|
| Redis | Sessions | Ephemeral, TTL-managed, no query needs |
| PostgreSQL | Conversations, messages, grading summaries | Persistent, auditable, queryable |

### Redis — session shape
```
key:   session:{session_id}
value: { user_id, workspace_id, conversation_id, started_at }
ttl:   3600s
```

### PostgreSQL — tables

**conversations**
```
id              UUID         PK
session_id      UUID
user_id         UUID
workspace_id    UUID         nullable
started_at      TIMESTAMPTZ
last_active_at  TIMESTAMPTZ
```

**messages**
```
id              UUID         PK
conversation_id UUID         FK → conversations
role            ENUM         'user' | 'assistant'
content         TEXT
blocks          JSONB        nullable — assistant only
tokens_used     INT          nullable
created_at      TIMESTAMPTZ
```

**grading_summaries**
```
id              UUID         PK
conversation_id UUID         FK → conversations, nullable (proactive)
workspace_id    UUID
assignment_id   UUID
suggestion_id   TEXT         orchestrator-owned ID
status          ENUM         'suggested' | 'approved' | 'graded' | 'invalidated'
summary_blocks  JSONB
generated_at    TIMESTAMPTZ
invalidated_at  TIMESTAMPTZ  nullable
```

---

## Infrastructure

### Containers

| Container | Image | Purpose |
|---|---|---|
| `ai-agent` | custom build | FastAPI app |
| `agent-db` | postgres:16-alpine | Persistent storage |
| `agent-redis` | redis:7.2-alpine | Session store |

### Networks

All services communicate over a shared external Docker network:

```bash
docker network create microservices-net
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Package manager | `uv` |
| API framework | FastAPI + Uvicorn |
| Agent framework | LangGraph |
| LLM | Gemini 2.0 Flash (`langchain-google-genai`) |
| REST client | `httpx` (async) |
| gRPC client | `grpcio` + generated protobuf stubs |
| Session store | Redis 7 |
| Persistent DB | PostgreSQL 16 |
| ORM | SQLAlchemy 2 (async) + Alembic migrations |
| Validation | Pydantic v2 + pydantic-settings |
| Serialization | `orjson` |
| Linting / formatting | Ruff |
| Testing | pytest + pytest-asyncio + pytest-httpx |
| Containerization | Docker (multi-stage) + Docker Compose |

---

## Getting Started

### Prerequisites
- `uv` installed ([docs](https://docs.astral.sh/uv/))
- Docker + Docker Compose
- `.env` file based on `.env.example`

### Shared network
```bash
docker network create microservices-net
```

### Run locally
```bash
make install
make up
```

### Useful commands
```bash
make test       # run test suite in isolated container
make proto      # recompile gRPC stubs from proto/
make migrate    # run Alembic migrations
make logs       # tail agent container logs
```

---

## Environment Variables

```bash
# LLM
GOOGLE_API_KEY=
LLM_MODEL=gemini-2.0-flash
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=4096

# Services
USERS_SERVICE_URL=http://users-service:8001
WORKSPACE_SERVICE_URL=http://workspace-service:8002

# Orchestrator
ORCHESTRATOR_GRPC_HOST=orchestrator-service
ORCHESTRATOR_GRPC_PORT=50051

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://agent:agent@agent-db:5432/agent

# Redis
REDIS_URL=redis://agent-redis:6379/0
SESSION_TTL_SECONDS=3600

# App
APP_PORT=8000
APP_ENV=development
LOG_LEVEL=INFO
AGENT_MAX_ITERATIONS=10
```

---

## Development Notes

- **Auth is intentionally disabled** in the current phase. All requests are accepted freely for testing.
- **`workspace-service` owns four domains** — Workspaces, Members, Assignments, and Submissions. All four are queried through the same service URL.
- **gRPC stubs are generated at build time** inside the Docker builder stage. Run `make proto` locally after any `.proto` changes.
- The agent uses **LangGraph** instead of LangChain's `AgentExecutor` for explicit control over the tool-calling loop and the suggest → approve grading flow.
- **Grading is two-phase** — `SuggestAssignment` produces a `suggestion_id` the agent must hold in conversation state until the teacher approves or discards it.
- User IDs are UUIDs across all services. The proto file uses `string` for `user_id` fields.

---

## See Also

- `DEVELOPMENT.md` — phased development plan with analysis steps and dependency order