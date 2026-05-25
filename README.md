# Repo Surgeon

> An autonomous, multi-repo refactoring and bug-fixing agent built on the **GitAgent Protocol (GAP)**. Lives across an organization's 10-20 repositories. Reads issues, opens PRs, learns conventions across reviews. Forkable. Multi-runtime. Runs locally with zero cloud dependencies.

Submission for the **Lyzr GitAgent hiring challenge** (2026-05-25).

## What is this?

Most autonomous coding agents (Devin, Cursor Background Agents) are black-box services with no memory across tasks. **Repo Surgeon is different:**

- **Agent-as-repo.** The agent is a GAP-compliant git repository (`repo-surgeon/`). Its personality, rules, skills, tools, and memory are all version-controlled markdown and YAML.
- **Compounds across PRs.** Every merged PR appends learnings to git-committed memory namespaced per-repo and org-wide. The agent literally gets smarter on every review, and you can `git diff` its brain.
- **Forkable.** Clone the platform, fork the agent, point at your repos. Same agent, your conventions.
- **Multi-runtime.** Declares Claude as preferred with OpenAI as fallback in `agent.yaml`. Same agent, any LLM.
- **Local-first.** Runs entirely on your laptop via Docker Compose. No cloud accounts. Webhook tunneling via free smee.io.

## Architecture (60-second tour)

```
GitHub webhook  →  smee.io tunnel  →  localhost:8000 (FastAPI)  →  queue (Redis)
                                                                       ↓
                                                            spawns: gitagent CLI
                                                                       ↓
                                                          ./repo-surgeon/ (GAP agent)
                                                                       ↓
                                                  opens PR on target repo via GitHub API
                                                                       ↓
                                              memory writes pushed to agent repo on GitHub
                                                                       ↓
                                                  dashboard at localhost:3000 shows live
```

Five components, all local:

| Component | What it is | How it runs |
|---|---|---|
| `repo-surgeon/` | The GAP agent itself — YAML + Markdown + Python tool scripts | Invoked by `gitagent` CLI |
| `surgeon-service/` | FastAPI: webhooks → classify → spawn agent → stream logs → store runs | `uvicorn` on :8000 |
| `dashboard/` | Next.js: live run viewer, memory editor, eval matrix | `pnpm dev` on :3000 |
| `evals/` | Golden test fixtures + multi-runtime scorer | `python evals/run_evals.py` |
| `infra/` | Docker Compose for Postgres + Redis | `docker compose up -d` |

## Quick start

```bash
# 1. Clone
git clone https://github.com/<you>/repo-surgeon-platform
cd repo-surgeon-platform

# 2. One-time setup wizard (prompts for GitHub App, API keys, smee.io channel)
./scripts/setup.sh

# 3. Bring up everything
./scripts/dev.sh

# 4. Open dashboard
open http://localhost:3000
```

See [`docs/SETUP.md`](docs/SETUP.md) for the detailed setup walkthrough.

## How it works (the killer flow)

1. You file an issue on one of your repos. Label it `surgeon:fix` or `surgeon:feature`.
2. GitHub sends a webhook to smee.io → forwarded to your laptop's `localhost:8000`
3. surgeon-service classifies the event, queues a job
4. Worker spawns: `gitagent --dir ./repo-surgeon --prompt "Fix issue #142: ..."`
5. The agent reads the issue, clones the target repo into `/tmp/surgeon-workspace/<run-id>/`, navigates the code, writes a failing test, implements the fix, runs the test suite, commits, pushes a branch, opens the PR
6. Every step streams to the dashboard via SSE
7. The agent commits a memory update (`memory/repos/<repo>/lessons.md`) explaining what it learned
8. You review the PR. If you correct something, edit `memory/repos/<repo>/conventions.md` via the dashboard — next time, the agent honors that convention

That last step is the magic. **The agent learns from your reviews because its brain is a git repo you can edit.**

## What makes this a "GAP" agent, not just a script

Every primitive of the GitAgent Protocol pulls weight:

| GAP feature | How Repo Surgeon uses it |
|---|---|
| `agent.yaml` | Multi-runtime declaration, compliance config, sub-agent registry |
| `SOUL.md` | Persona that makes PR bodies feel human-authored |
| `RULES.md` | 15 hard rules enforced at `pre_tool_use` hook — blocks writes to migrations, secrets, etc. |
| `skills/` | 10 composable, scoped capabilities (scan, propose, fix, write-test, open-pr, etc.) |
| `tools/` | 5 MCP-compatible custom tools (github-api, run-tests, codebase-grep, read-issue, detect-conventions) |
| `hooks/` | 5 lifecycle scripts for memory loading, safety gating, audit, learning extraction, commit-back |
| `workflows/` | 2 declarative SkillsFlow YAMLs orchestrating refactor-mode and issue-to-pr |
| `memory/` | Namespaced by repo: `memory/org/` (shared) + `memory/repos/<name>/` (specific) — git-committed, reviewable, forkable |
| `agents/` | One sub-agent: `security-reviewer.md` for clean-context adversarial review |
| Multi-runtime | Declares Claude preferred, OpenAI fallback. Eval suite runs on both. |
| Forkability | `scripts/setup.sh` walks anyone through forking the platform for their own org |

## Layout

```
repo-surgeon-platform/
├── repo-surgeon/        # the GAP agent (publishable standalone)
├── surgeon-service/     # FastAPI dispatcher
├── dashboard/           # Next.js cockpit
├── evals/               # multi-runtime eval fixtures + runner
├── infra/               # docker-compose.yml + smee-client config
├── scripts/             # setup.sh + dev.sh
├── docs/                # ARCHITECTURE, DEMO, SETUP
└── logs/, secrets/      # local-only (gitignored)
```

## Demo

See [`docs/DEMO.md`](docs/DEMO.md) for the full 4-minute walkthrough.

## License

Apache-2.0
