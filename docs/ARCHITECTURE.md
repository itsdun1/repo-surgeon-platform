# Architecture

## Three-layer separation

```
┌──────────────────────────────────────────────────────────┐
│  THE AGENT (this is what makes Repo Surgeon a GAP agent) │
│  ./repo-surgeon/                                          │
│    agent.yaml, SOUL.md, RULES.md                          │
│    skills/ tools/ hooks/ workflows/ memory/ agents/       │
└────────────────────────┬─────────────────────────────────┘
                         │ read & executed by
                         ▼
┌──────────────────────────────────────────────────────────┐
│  THE GITAGENT CLI (Lyzr's runtime)                       │
│  `gitagent --dir ./repo-surgeon --prompt "..."`           │
│  Loads the agent, applies hooks, executes workflows,      │
│  runs skills, invokes tools, commits memory.              │
└────────────────────────┬─────────────────────────────────┘
                         │ spawned by
                         ▼
┌──────────────────────────────────────────────────────────┐
│  THE PLATFORM (the wrapping we built)                    │
│  surgeon-service/  — FastAPI: webhooks, queue, runner    │
│  dashboard/        — Next.js: cockpit                    │
│  infra/            — Docker Compose: Postgres, Redis     │
│  scripts/          — setup.sh, dev.sh                    │
│  evals/            — golden tests (run via Python)       │
└──────────────────────────────────────────────────────────┘
```

**Key insight**: the agent is portable. Someone can `gitagent --dir ./repo-surgeon ...` from a terminal without any of the platform code. The platform exists to give it *automation*: GitHub webhooks → queue → dispatched runs → live observability.

## Request → PR lifecycle

```
1. Someone labels an issue `surgeon:fix` on their GitHub repo
       │
       ▼
2. GitHub POSTs webhook to smee.io  →  forwarded to localhost:8000/webhooks/github
       │
       ▼
3. surgeon-service:
   • Verifies HMAC signature
   • Dedupes by X-GitHub-Delivery (Redis SETNX)
   • Persists raw payload to webhook_events table
   • Classifies: "issues" + "labeled" + label.startswith("surgeon:")  →  mode "issue:fix"
   • Mints GitHub App installation token (1-hour TTL, cached in Redis)
   • Creates a `runs` row with status="queued"
   • LPUSHes job to Redis list `queue:repo:<repo_id>`
       │
       ▼
4. Worker (asyncio task in same process, per-repo consumer):
   • BRPOPs job
   • Acquires per-repo Redis lock (serializes runs on same target repo)
   • `git pull --rebase` on ./repo-surgeon/
   • Clones target repo into /tmp/surgeon-workspace/<run-id>/target/
   • Creates branch `surgeon/<run-id>` in the workspace
   • Spawns: gitagent --dir ./repo-surgeon --prompt "<contextual task>"
              with env: TARGET_DIR, TARGET_REPO, GITHUB_TOKEN, model keys
       │
       ▼
5. gitagent CLI (Lyzr's runtime):
   • Fires on_session_start hook  →  load_memory_namespace.py reads memory/org/* + memory/repos/<TARGET_REPO>/*
   • Executes workflow `issue-to-pr.yaml`:
       load_context → fetch_issue → classify → clone (no-op, already done) →
       detect_conv → [implement_fix | implement_feature | implement_refactor] →
       [security_review (if sensitive)] → tests → [feature_approval (if feature)] →
       open_pr → comment_back → update_memory
   • For each tool call, pre_tool_use hook validates against RULES.md
       (e.g., blocks writes to migrations/, .env, .github/workflows/)
   • For each turn, post_tool_use hook appends a redacted line to audit-trail.jsonl
   • For each response, post_response hook scans for LESSON:/CONVENTION:/SMELL: sentinels,
     captures into memory/sessions/<session-id>.md
       │
       ▼
6. On agent completion:
   • PR opened on target repo via github-api tool
   • on_session_end hook  →  commit_memory.py dedupes session scratch into
     canonical memory/repos/<TARGET_REPO>/*.md, commits with structured message,
     pushes to agent repo's GitHub origin
   • Worker:
       - Parses PR URL from logs
       - Updates `runs` row: status=success, finished_at, pr_url, cost_usd
       - rm -rf workspace
       - Releases per-repo lock
       │
       ▼
7. Dashboard at localhost:3000/runs/<id>:
   • SSE from localhost:8000/sse/runs/<id> streamed every tool call
   • PR URL appears with link
   • Memory tab shows new commits in the agent repo
```

## Why each piece exists

| Piece | Why we built it |
|---|---|
| `repo-surgeon/` GAP agent | The agent definition — portable, forkable, reviewable as code |
| Hooks (load/enforce/audit/extract/commit) | Without hooks, RULES.md is just documentation and memory doesn't compound |
| Workflows | Deterministic orchestration of skills — easier to reason about than letting the LLM decide everything |
| Sub-agent (security-reviewer) | Adversarial review needs a *clean context* — having the implementer also review the implementation has known bias problems |
| `surgeon-service` FastAPI | Lyzr's CLI is single-shot; we need a long-running service to receive webhooks and orchestrate |
| Per-repo Redis lock | Two concurrent runs on the same target would race on the memory file commits |
| Per-repo Redis queue | Each repo can be busy without blocking others (parallelism between repos, serialization within) |
| smee.io tunnel | GitHub can't POST to localhost; smee is the simplest free option |
| Dashboard | The agent's value isn't legible without observability of tool calls, memory growth, eval results |
| Eval harness | Without evals, you can't change the agent confidently. The eval matrix on Claude vs OpenAI is also the multi-runtime credibility shot |

## Why GAP specifically (not LangChain/CrewAI)

The unique GAP primitives Repo Surgeon depends on:

1. **Memory as git** — every learning is a commit. Reviewers curate memory via PR. Time-travel and behavioral diffs are free.
2. **Forkable** — `gh repo fork repo-surgeon` and you have your own variant. Customize RULES.md, redeploy.
3. **Multi-runtime** — `agent.yaml` declares Claude preferred, OpenAI fallback. Same agent, both LLMs. Eval suite runs against both and surfaces behavioral diff.
4. **Markdown over code** — SOUL/RULES are read as part of the agent's prompt at every session; editing them changes behavior without code changes.
5. **Hooks as scripts** — `enforce_rules.py` is a tiny standalone Python file that returns JSON. Anyone can read, audit, and modify it.

A LangChain version of Repo Surgeon would have to invent these primitives. GAP gives them as part of the standard.

## Single-tenant local mode (v1)

For the demo deploy, we run as a single-tenant local app:

- `tenants` table contains one row (`'local'`)
- All other tables FK to it
- Agent repo lives at `./repo-surgeon/` (in this monorepo) — not per-tenant subdir
- A future cloud deploy would use Fly.io for surgeon-service, Vercel for dashboard, Neon for Postgres — all with the existing `tenant_id` columns activated

The local mode keeps complexity low and removes deploy as a moving piece during the hiring-challenge window.
