# Development Plan

## Guiding Principles

- **No assumptions.** Every phase has an analysis step that must be completed before writing code. If a question is unanswered, the phase does not start.
- **Bottom-up dependencies.** Infrastructure before services, services before tools, tools before agent, agent before API.
- **Verify before wire.** Every external endpoint gets manually tested with curl or Postman before a tool is written against it.
- **One working thing at a time.** Each phase ends with something runnable and verifiable, not just written.

---

## Phase 0 — Infrastructure & Project Skeleton

### Goal
Docker stack is running. `/health` returns 200. Postgres and Redis are reachable from the app container.

### Analysis steps (resolve before writing anything)
- [X] Confirm the shared Docker network name used by existing services
- [X] Confirm ports used by `users-service`, `workspace-service`, and `ai-orchestrator` to avoid conflicts
- [X] Confirm Postgres and Redis are not already shared with another service that would conflict
- [X] Confirm `GOOGLE_API_KEY` is valid and Gemini 2.0 Flash is accessible from your network

### Build order
1. `pyproject.toml` — all dependencies declared, dev extras separated
2. `.python-version` — pin 3.14.4
3. `.env.example` — every variable documented, no values
4. `config/settings.py` — pydantic-settings, reads from `.env`
5. `main.py` — FastAPI app, `/health` endpoint only
6. `Dockerfile` — multi-stage: builder (uv sync + proto compile) → runtime
7. `docker-compose.yml` — agent + agent-db + agent-redis + shared network
8. `Makefile` — `up`, `down`, `logs`, `migrate`, `proto`, `test`, `install`

### Done when
```bash
docker compose up
curl http://localhost:8000/health  # → {"status": "ok"}
```
Postgres and Redis containers are healthy. Agent container starts without errors.

---

## Phase 1 — Database Layer

### Goal
Migrations run. Tables exist. SQLAlchemy models match the schema. Basic read/write works from a test script.

### Analysis steps
- [ ] Confirm UUID strategy — does PostgreSQL generate them (`gen_random_uuid()`) or does the app?
- [ ] Confirm whether `workspace_id` on conversations can always be inferred from session, or if it truly is nullable at the DB level
- [ ] Confirm the ENUM values for `role` and `grading_summaries.status` are final — changing ENUMs in Postgres after data exists is painful

### Build order
1. `db/pool.py`          — asyncpg connection pool, init + teardown
2. `db/migrations/`      — Alembic setup pointed directly at the DB (no models needed)
3. `First migration`     — raw SQL: CREATE TYPE enums + CREATE TABLE for all three tables
4. `db/queries/`         — one file per table with raw async query functions
                         conversations.py, messages.py, grading_summaries.py

### Done when
```bash
make migrate  # runs without errors
# tables exist in agent-db with correct columns and constraints
```

---

## Phase 2 — Service Clients

### Goal
The agent can call `workspace-service` and `users-service` over HTTP, and `ai-orchestrator` over gRPC — all verified against real running services.

### Analysis steps — REST
- [ ] Get the full list of available endpoints from `workspace-service` (check Postman collection already in the repo)
- [ ] Confirm which endpoints are internal-only vs public — the agent should prefer internal ones
- [ ] Confirm the response shape for: workspace, member, assignment, submission — map to Pydantic models before writing tools
- [ ] Confirm `users-service` endpoint for fetching a user profile by ID
- [ ] Confirm whether any endpoint requires headers beyond auth (e.g. `X-Workspace-Id`)

### Analysis steps — gRPC
- [ ] Drop final `.proto` file into `proto/` — the version in this repo must match the running orchestrator exactly
- [ ] Run `make proto` and confirm stubs generate without errors
- [ ] Manually call `SuggestAssignment` with a known `workspace_id` and `assignment_id` using a gRPC client (e.g. Postman or grpcurl) to verify the orchestrator is reachable and responding

### Build order
1. `services/http_client.py` — base async httpx client, shared timeout config
2. `services/workspace_service.py` — typed methods for workspace, assignment, submission, member endpoints
3. `services/users_service.py` — typed methods for user profile endpoint
4. `proto/` — drop proto file, run `make proto`, commit generated stubs
5. `services/grpc_client.py` — channel + stub initialization, connection reuse
6. `services/orchestrator_service.py` — typed wrappers for `SuggestAssignment`, `ApproveSuggestion`, `GradeAssignment`

### Done when
Each service file has a corresponding `__main__` block or test that calls a real endpoint and prints the response. Nothing moves to Phase 3 until all three clients return real data.

---

## Phase 3 — Session & Memory

### Goal
A session is created on first chat, persisted in Redis with TTL, and linked to a Postgres conversation record. Subsequent messages in the same session reload context correctly.

### Analysis steps
- [ ] Decide session lifetime — 1 hour idle TTL is the default, confirm if this is acceptable
- [ ] Decide what happens when a session expires mid-conversation — silent new session, or error to frontend?
- [ ] Confirm whether `workspace_id` is always sent by the frontend or if the agent must infer it

### Build order
1. `agent/session.py` — create, load, refresh session in Redis; link to Postgres conversation
2. `db/repositories/conversation_repository.py` — create conversation, append message, load history
3. `agent/memory.py` — LangGraph-compatible memory loader that reads last N messages from Postgres and injects into graph state

### Done when
Two sequential POST `/chat` requests with the same `session_id` correctly load prior message history into the agent context.

---

## Phase 4 — Tools

### Goal
Each tool is independently testable, returns structured data, and has a docstring precise enough for the LLM to select it correctly.

### Analysis steps
- [ ] For each tool: confirm the exact endpoint and response shape it will call (from Phase 2 verification)
- [ ] For grading tools: manually trace the full suggest → approve flow end-to-end with real data before coding the tools
- [ ] Confirm what `submission_stats` returns from workspace-service — if it doesn't exist as an endpoint, the tool cannot be built until it does
- [ ] Decide tool error contract — every tool must return a dict, never raise. Errors are represented as `{"error": "message"}` so the LLM can reason about them

### Build order (dependency order within phase)

**Read-only tools first — no side effects, safe to test freely**
1. `tools/workspace/get_workspace.py`
2. `tools/workspace/list_workspaces.py`
3. `tools/assignments/get_assignment.py`
4. `tools/assignments/list_assignments.py`
5. `tools/submissions/get_submission.py`
6. `tools/submissions/list_submissions.py`
7. `tools/users/get_user.py`
8. `tools/statistics/submission_stats.py`

**Write/trigger tools second — side effects, require real data setup**

9. `tools/grading/suggest_assignment.py`
10. `tools/grading/approve_suggestion.py`
11. `tools/grading/grade_assignment.py`
12. `tools/grading/grading_results.py`

**Registry last**

13. `tools/__init__.py` — imports all tools, exports a single `get_tools()` list

### Done when
Each tool file can be run directly and returns a valid dict against real services. Grading flow is tested end-to-end: suggest → inspect results → approve → confirm status.

---

## Phase 5 — Agent Core

### Goal
LangGraph agent receives a message, selects the correct tool(s), calls them, and returns a valid `AgentResponse` with populated blocks.

### Analysis steps
- [ ] Finalize the system prompt — it must describe the platform domain, available actions, and the block output format. This is the most important prompt in the system. Draft it, test it against at least 10 realistic teacher messages before wiring
- [ ] Decide LangGraph graph topology — linear (one tool at a time) or parallel (multiple tools per turn). Start linear, document the decision
- [ ] Decide `max_iterations` cap — default is 10, confirm this is enough for the most complex expected flow (suggest → approve requires at minimum 2 tool calls)
- [ ] Confirm Gemini 2.0 Flash supports tool calling with the LangChain integration — run a minimal standalone test with one tool before building the full graph

### Build order
1. `agent/prompt.py` — system prompt with platform context and block format instructions
2. `agent/graph.py` — LangGraph state definition + node functions (call_llm, call_tool, build_response)
3. `agent/response_builder.py` — maps tool outputs to typed blocks
4. `agent/core.py` — compiles the graph, exposes `run(message, context)` entrypoint

### Done when
```
Input:  "Show me all submissions for assignment X"
Output: AgentResponse with a TableBlock containing real submission data
```

---

## Phase 6 — API Layer

### Goal
`POST /chat` is fully wired. Session management, agent execution, and response persistence all work end-to-end.

### Build order
1. `api/dependencies.py` — extract and validate `session_id`, `user_id`, `workspace_id` from request
2. `api/routes.py` — wire chat endpoint to session manager + agent core + message persistence
3. `api/internal_routes.py` — `POST /internal/events/grading-completed` stub (returns 200, logs payload)

### Done when
Full round-trip: POST request → session created → agent runs → tool called → response persisted → `AgentResponse` returned with real blocks.

---

## Phase 7 — Proactive Feedback

### Goal
When the internal webhook fires, the agent synthesizes a grading summary and stores it. SSE delivery is stubbed for now — the stored summary is the deliverable.

### Analysis steps
- [ ] Confirm the orchestrator will actually call the internal endpoint — coordinate with the orchestrator team on the webhook payload shape
- [ ] Decide what happens if the teacher has no active session when the webhook fires — store summary anyway, deliver on next session open
- [ ] Decide invalidation trigger — if the same assignment is regraded, the previous summary status should become `invalidated`

### Build order
1. `agent/proactive.py` — background synthesis function, takes grading results, returns blocks, stores to `grading_summaries`
2. Wire `internal_routes.py` to call `proactive.py`
3. SSE stub in `api/routes.py` — `GET /chat/stream/{session_id}` returns a heartbeat for now

### Done when
POST to `/internal/events/grading-completed` with a valid payload creates a `grading_summaries` row with status `suggested` and populated `summary_blocks`.

---

## Phase 8 — Auth Integration

> **Not started until all previous phases are stable and tested.**

### What changes
- Every inbound request must carry a valid JWT from `auth-service`
- `api/dependencies.py` validates the token and extracts `user_id` from claims instead of the request body
- Tool calls that mutate data (grading, approval) check that the requesting user has teacher-level access to the workspace
- The service-to-service call strategy is confirmed: forward user token vs service account

### Analysis steps (when phase begins)
- [ ] Get the JWT structure from `auth-service` — which claims carry `user_id` and `role`
- [ ] Confirm whether the agent calls other services with the user's token or its own service token
- [ ] Confirm whether `workspace-service` enforces its own authorization or trusts the caller

---

## Assumption Log

Assumptions made during planning that must be validated before the relevant phase begins.

| # | Assumption | Phase | Status |
|---|---|---|---|
| 1 | `workspace-service` internal routes are callable without auth from within the Docker network | 2 | unverified |
| 2 | `ai-orchestrator` is reachable by container name on the shared network | 2 | unverified |
| 3 | `SuggestAssignment` is synchronous — it blocks until all submissions are graded | 2 | unverified |
| 4 | `submission_stats` exists as an endpoint on `workspace-service` | 4 | unverified |
| 5 | Gemini 2.0 Flash supports parallel tool calling via LangChain integration | 5 | unverified |
| 6 | The orchestrator will send the webhook to the agent when grading completes | 7 | unverified |
| 7 | `workspace_id` is always provided by the frontend — agent never needs to infer it | 3 | unverified |