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

---

# How to use

## For developers using the agent (the GAP repo only)

The agent works standalone, without the platform. Useful for one-off CLI runs or scripted automation.

```bash
# 1. Install the Lyzr gitagent CLI
bash <(curl -fsSL "https://raw.githubusercontent.com/open-gitagent/gitagent/main/install.sh")

# 2. Clone the agent
git clone https://github.com/itsdun1/repo-surgeon

# 3. Clone whatever target you want to operate on
git clone https://github.com/<you>/<some-repo> /tmp/target-repo

# 4. Run the agent against the target
export TARGET_REPO=<you>/<some-repo>
export TARGET_DIR=/tmp/target-repo
export GITHUB_TOKEN=ghp_xxx    # PAT or installation token
export OPENAI_API_KEY=sk-...   # or ANTHROPIC_API_KEY

cd repo-surgeon
gitagent --dir . \
         --prompt "Fix issue #42 on $TARGET_REPO. The bug is..." \
         --model openai:gpt-5.1
```

The agent reads its own SOUL/RULES/skills/memory, edits code in `$TARGET_DIR`, and opens a PR via the GitHub API. Done.

## For teams running the full platform

This is the webhook-driven, multi-repo, dashboard-driven flow.

### One-time setup

```bash
# Clone the platform with submodules
git clone --recurse-submodules https://github.com/itsdun1/repo-surgeon-platform
cd repo-surgeon-platform

# Run the interactive setup wizard
./scripts/setup.sh
```

The wizard walks you through:
1. Verifying `gh` CLI auth
2. Capturing your Anthropic + OpenAI API keys
3. Creating a smee.io channel (browser step, 30 sec)
4. Creating the GitHub App (browser step, 5 min) — webhook URL = your smee URL
5. Downloading the App's private key into `secrets/`
6. Optionally forking 1-2 small OSS repos to your account as demo targets
7. Writing `.env.local` with everything captured

After the wizard, install the App on whichever repos you want covered: `https://github.com/settings/installations` → Configure.

### Daily use

```bash
# Bring up the whole stack (Docker)
./scripts/dev.sh
# → postgres, redis, surgeon-service, dashboard, smee-client all start
# → dashboard at http://localhost:3000
```

Then in any repo where the App is installed:

| Trigger | What happens |
|---|---|
| File an issue + add label `surgeon:fix` | Agent reads the issue, finds the bug, writes a failing test, fixes it, opens a PR |
| File an issue + add label `surgeon:feature` | Agent decomposes the feature, implements it, writes tests, opens a PR (with approval gate) |
| Cron job (nightly 03:00 UTC by default) | Agent scans the repo for smells and opens at most ONE refactor PR per repo per 24h |
| Reviewer comments on a Surgeon PR | Human edits memory via dashboard → next PR honors the new convention |

### The compounding moment (the magic step)

When a Surgeon PR gets feedback like "use the Money class for currency arithmetic":

1. Open `http://localhost:3000/memory`
2. Navigate to `repos/<repo>/conventions.md`
3. Add a section: "Always use the `Money` class for currency arithmetic. Never use raw `number` for prices."
4. Save → opens a commit on the agent repo

Next time the agent works on any related code, that convention is loaded automatically and cited in the PR body's `## Sources` section. **You teach the agent by editing markdown, not code.**

### Stopping everything

```bash
# In another terminal
docker compose -f infra/docker-compose.yml --profile full down

# Nuclear (also wipe Postgres data)
docker compose -f infra/docker-compose.yml --profile full down -v
```

### Manual housekeeping

| Action | Command |
|---|---|
| Trigger cleanup now | `curl -X POST http://localhost:18000/api/admin/cleanup` |
| Tail logs of all containers | `docker compose -f infra/docker-compose.yml --profile full logs -f` |
| Inspect a specific run | `http://localhost:3000/runs/<run-id>` |
| Re-run an issue without filing a new one | Remove + re-add the `surgeon:fix` label |
| Test the agent without webhooks | `POST http://localhost:18000/api/manual-trigger` (body: `{repo, mode, prompt, installation_id}`) |
| Run evals (multi-runtime) | Inside `repo-surgeon/`: `python evals/run_evals.py` |

### Forking for your own org

1. Fork both `itsdun1/repo-surgeon-platform` and `itsdun1/repo-surgeon`
2. Update `.env.local`: `AGENT_REPO_REMOTE=https://github.com/<your-org>/repo-surgeon`
3. Customize `repo-surgeon/RULES.md` and `repo-surgeon/memory/org/*.md` for your team
4. Push to your fork; `./scripts/dev.sh` clones from your remote on startup
5. Create a GitHub App on your org (instead of personal account) and install on your real repos

The agent is now *your* org's agent. Forks diverge intelligently because memory commits are scoped per-repo.

---

# Future work

## Production deployment on Kubernetes

The current Docker Compose setup is great for local development and small-team self-hosting. For production multi-tenant deployment, the recommended target is **Kubernetes**.

```
┌──────────────────────────── Kubernetes cluster ────────────────────────────┐
│                                                                            │
│  ┌─ Ingress (cert-manager + Let's Encrypt) ─────────────────────────────┐  │
│  │  surgeon.example.com   →  dashboard service                          │  │
│  │  api.surgeon.example.com → surgeon-service ingress                   │  │
│  │  webhooks.surgeon.example.com → surgeon-service /webhooks (rate     │  │
│  │                                  limited via NGINX/Envoy)            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ Deployment: dashboard (Next.js, stateless) ─────── HPA: 2-10 pods ──┐  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ Deployment: surgeon-web (FastAPI HTTP only) ────── HPA: 2-20 pods ──┐  │
│  │   Receives webhooks + serves dashboard API + SSE                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ Deployment: surgeon-worker (subprocess spawner) ──── KEDA scaled ───┐  │
│  │   Scales based on Redis queue depth (KEDA Redis trigger)              │  │
│  │   Each worker pod: gitagent CLI + git + gh + python tooling           │  │
│  │   Spawns the agent inside a SANDBOX pod (see next section)            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ StatefulSet: postgres ──── CloudNativePG or Zalando operator ───────┐  │
│  │   HA: primary + 2 replicas, automatic failover, point-in-time recovery│  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ StatefulSet: redis ──── Redis Operator (Sentinel) ──────────────────┐  │
│  │   3-node Sentinel cluster for queue durability                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ Observability stack ──────────────────────────────────────────────────┐ │
│  │  Prometheus (metrics) + Grafana (dashboards) + Loki (logs) + Tempo    │ │
│  │  (traces). FastAPI instrumented with OpenTelemetry.                   │ │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

### Helm chart layout (planned)

```
helm/repo-surgeon/
├── Chart.yaml
├── values.yaml                  # tunable defaults
├── values.production.yaml       # prod overrides
├── templates/
│   ├── dashboard-deployment.yaml
│   ├── surgeon-web-deployment.yaml
│   ├── surgeon-worker-deployment.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml
│   ├── keda-scaledobject.yaml   # queue-depth autoscaling for workers
│   ├── networkpolicy.yaml       # zero-trust between pods
│   ├── pdb.yaml                 # pod disruption budgets
│   ├── servicemonitor.yaml      # Prometheus scrape config
│   └── _helpers.tpl
└── crds/
    └── sandbox-runtime.yaml     # custom resource for sandboxed agent runs
```

### Multi-tenancy at scale

| Concern | Approach |
|---|---|
| Tenant isolation | Postgres row-level security on `tenant_id` + namespace-per-tenant for compute pods |
| Per-tenant agent repo | Each tenant points `AGENT_REPO_REMOTE` at their fork; worker clones to `/data/agent-repos/<tenant-id>/` |
| Per-tenant API key billing | Tenants bring their own LLM keys (BYOK); platform proxies LLM calls and meters cost |
| Per-tenant rate limits | NGINX rate-limit module keyed on installation_id |
| Secrets management | External Secrets Operator + AWS Secrets Manager / GCP Secret Manager / Vault |
| Audit log compliance | `hooks/audit-trail.jsonl` shipped to S3 via Fluent Bit; 7-year retention |

### Operational concerns

- **Webhook ingress**: replace smee.io with direct ingress at `webhooks.<your-domain>` once we have a public URL
- **Background jobs**: cleanup + eval cron jobs run as Kubernetes `CronJob` resources
- **Rolling updates**: `surgeon-worker` uses `OnDelete` strategy so in-flight runs aren't killed mid-execution
- **PR throttling**: per-installation token bucket (e.g., max 10 PRs/hour) in `surgeon-web` before enqueueing
- **Dead letter queue**: Redis Streams instead of Lists, with consumer groups + DLQ for failed jobs

## Sandboxed clone + run

**Why it matters**: when the agent clones a target repo and runs `npm install` / `npm test` / arbitrary build scripts, it's effectively executing untrusted code. Today this happens directly inside the `surgeon-worker` container — meaning a malicious target repo could:

- Exfiltrate the installation token via `npm postinstall` script
- Read `secrets/` mounts or env vars
- Use up unbounded CPU / memory / disk
- Make outbound network calls to attacker-controlled servers

For multi-tenant production, **every agent run must execute inside a per-run ephemeral sandbox** with no access to platform state.

### Sandbox architecture

```
surgeon-worker (orchestrator pod, trusted)
    │
    │  1. Receive job from Redis queue
    │  2. Mint short-lived (10-minute) installation token
    │  3. Create sandbox pod via Kubernetes API:
    │
    ▼
    ┌───────────────── Sandbox pod (ephemeral, untrusted) ────────────────┐
    │                                                                     │
    │  Runtime: gVisor (runsc) or Kata Containers (microVM)               │
    │                                                                     │
    │  Image: surgeon-sandbox:local                                       │
    │   • gitagent CLI                                                    │
    │   • git, gh, node, python, common build tools                       │
    │   • NO platform code, NO secrets mounted                            │
    │                                                                     │
    │  Resource limits:                                                   │
    │   • CPU: 2 cores                                                    │
    │   • RAM: 4 GiB                                                      │
    │   • Disk: 5 GiB ephemeral                                           │
    │   • PID limit: 200                                                  │
    │   • Wall-clock timeout: 30 min                                      │
    │                                                                     │
    │  Network policy:                                                    │
    │   • Egress allowed: github.com, registry.npmjs.org, pypi.org,       │
    │     LLM API providers (api.anthropic.com, api.openai.com)           │
    │   • Egress blocked: everything else (default deny)                  │
    │   • Ingress: none                                                   │
    │                                                                     │
    │  Mounts:                                                            │
    │   • /workspace/agent  (read-only, the GAP repo)                     │
    │   • /workspace/target (empty; agent will clone into here)           │
    │   • emptyDir for /tmp                                               │
    │                                                                     │
    │  Env:                                                               │
    │   • GITHUB_TOKEN (10-min TTL)                                       │
    │   • LLM_API_KEY (proxy URL, not the real key — see below)           │
    │                                                                     │
    └─────────────────────────────────────────────────────────────────────┘
    │
    │  4. Stream stdout/stderr back to orchestrator via gRPC
    │  5. Sandbox completes (success/failure/timeout)
    │  6. Orchestrator captures PR URL, cost, etc.
    │  7. Sandbox pod is deleted (Kubernetes garbage collects)
```

### Defense layers

| Layer | What it prevents |
|---|---|
| **gVisor / Kata runtime** | Kernel-level isolation; untrusted code can't escape to host kernel |
| **NetworkPolicy default-deny + allowlist** | Even if compromised, sandbox can only reach known-good hosts |
| **No secret mounts** | Sandbox never sees the GitHub App private key or webhook secret |
| **Short-lived installation token** | Even if exfiltrated, token expires in 10 minutes |
| **LLM API proxy** | Sandbox doesn't see the real API key — calls go through `surgeon-llm-proxy` which holds the key and enforces budgets |
| **Resource limits** | DoS via fork bomb / memory hog / disk fill is bounded |
| **Read-only agent mount** | Malicious code can't modify the GAP repo to escalate future runs |
| **Audit logs** | Every sandbox spawn + every outbound network connection logged |
| **Egress proxy with TLS termination** | Inspect outbound traffic for credential exfiltration patterns |

### Alternative sandbox backends

For teams without Kubernetes, the platform should support:

| Backend | Use case |
|---|---|
| **E2B** (`gitagent --sandbox` flag, already supported) | SaaS sandboxes, zero infra |
| **Firecracker microVMs** | Self-hosted, very fast cold start, AWS Lambda-style |
| **Docker-in-Docker** with `--read-only` + `--security-opt=no-new-privileges` | Lighter weight, less isolation |
| **nsjail / firejail** | Linux-only, no container runtime needed |

The sandbox backend should be pluggable: `SANDBOX_BACKEND=kubernetes|e2b|firecracker|local-docker` env var in `surgeon-service`.

## Other roadmap items

- **PR comment iteration**: today a Surgeon PR is one-shot. Future: agent listens to PR review comments and pushes follow-up commits to the same PR.
- **Cross-repo refactors**: when a shared utility lives in repo A and is used in repos B, C, D — the agent should be able to coordinate a single change across all of them.
- **Run replay**: persist the full LLM transcript so any run can be replayed against a different model for comparison.
- **Eval auto-generation**: LLM-assisted generation of golden test cases from real merged PRs.
- **Self-healing memory**: if a memory entry causes regressions across N PRs, auto-flag for human review.
- **Diff-of-behavior viewer**: when SOUL/RULES change, render side-by-side which evals shifted.
- **Slack / Discord integrations**: agent posts run summaries; humans approve gates via emoji reaction.
- **SSO + RBAC**: enterprise tenants want SAML/OIDC login and role-based access (admin / reviewer / viewer).
- **Cost dashboards**: per-tenant LLM spend breakdown by repo, by mode, by model.
- **Webhook backfill**: replay old GitHub events through the pipeline for testing or retroactive coverage.
- **Marketplace of forks**: a public gallery of community-tuned `repo-surgeon` forks for specific languages/frameworks.
