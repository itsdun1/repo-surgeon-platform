# How to use Repo Surgeon — step by step

There are three paths depending on what you want. Pick one:

| I want to… | Go to |
|---|---|
| **Try it on my own GitHub repos** — install on my account, label an issue, get a PR | **Path A** (~15 min) |
| **Just run the agent from a terminal** — no platform, no webhooks | **Path B** (~3 min) |
| **Fork it for my team** — customize the agent + deploy on my org | **Path C** (extends Path A) |

---

## Path A — Full platform on your laptop

### Step 1: Prerequisites (install once)

| Tool | Why | How |
|---|---|---|
| **Docker Desktop** | Runs the whole stack | https://www.docker.com/products/docker-desktop |
| **`gh` CLI** | Talks to GitHub for setup | `brew install gh` (Mac) or https://cli.github.com |
| **An LLM API key** | Powers the agent | Anthropic OR OpenAI |

Authenticate `gh`:
```bash
gh auth login
```

Verify Docker is running:
```bash
docker info
```

### Step 2: Clone the platform

```bash
git clone --recurse-submodules https://github.com/itsdun1/repo-surgeon-platform
cd repo-surgeon-platform
```

The `--recurse-submodules` pulls down the `repo-surgeon` agent too. If you forget:
```bash
git submodule update --init --recursive
```

### Step 3: Create a smee.io channel (30 sec, browser)

GitHub can't POST webhooks to your laptop directly, so smee tunnels them.

1. Open **https://smee.io/new** in your browser
2. Click "Start a new channel"
3. Copy the URL (looks like `https://smee.io/abc123XyZ`) — keep this tab open

### Step 4: Create a GitHub App (5 min, browser)

1. Open **https://github.com/settings/apps/new**
2. Fill these fields:

   | Field | Value |
   |---|---|
   | App name | `Repo Surgeon Local` (must be globally unique — add a suffix if taken) |
   | Homepage URL | `https://github.com/<your-username>/repo-surgeon-platform` *(must be a real URL, not localhost)* |
   | Webhook URL | the smee URL from Step 3 |
   | Webhook secret | run `openssl rand -hex 32` in a terminal, paste output here, also save it for Step 5 |
   | Permissions → Repository → Issues | **Read & write** |
   | Permissions → Repository → Pull requests | **Read & write** |
   | Permissions → Repository → Contents | **Read & write** |
   | Permissions → Repository → Metadata | **Read** |
   | Permissions → Repository → Checks | **Read & write** |
   | Subscribe to events | ✓ Issues, ✓ Issue comment, ✓ Pull request, ✓ Push, ✓ Installation |
   | Where can this be installed? | Only on this account |

3. Click **Create GitHub App**
4. On the next page: note the **App ID** at the top (e.g. `3852083`)
5. Scroll to **Private keys** → click **Generate a private key** → `.pem` file downloads
6. Move the `.pem` file into place:
   ```bash
   mv ~/Downloads/repo-surgeon-local.*.private-key.pem \
      ./secrets/github-app-private-key.pem
   ```

### Step 5: Run the setup wizard

```bash
./scripts/setup.sh
```

It will ask you for:
- Your OpenAI API key (paste it; if you have an Anthropic key too, paste that — otherwise leave blank)
- Your smee URL from Step 3
- Your GitHub App ID from Step 4
- Your webhook secret from Step 4

When done, you'll have a `.env.local` file with everything filled in.

### Step 6: Install the App on your repos (1 min, browser)

1. Open **https://github.com/settings/installations**
2. Click **Configure** next to "Repo Surgeon Local"
3. Choose either:
   - **All repositories** (simplest), or
   - **Only select repositories** → pick 1-2 small repos you don't mind getting PRs on
4. Click **Save**

### Step 7: Start the stack

```bash
./scripts/dev.sh
```

This brings up 5 Docker containers:
- Postgres on :15432
- Redis on :16379
- `surgeon-service` (FastAPI + gitagent CLI baked in) on :18000
- `dashboard` (Next.js) on :3000
- `smee-client` forwarding webhooks to localhost

Wait ~15 seconds, then in another terminal:
```bash
curl http://localhost:18000/health     # {"status":"ok"}
open http://localhost:3000             # dashboard loads
```

### Step 8: Trigger your first agent run

Pick a repo where you installed the App. Then:

```bash
# Add the labels (one-time per repo)
gh label create "surgeon:fix" --repo <your-user>/<repo> --color "d73a4a"
gh label create "surgeon:feature" --repo <your-user>/<repo> --color "a2eeef"
gh label create "surgeon:refactor" --repo <your-user>/<repo> --color "0075ca"

# File a test issue
gh issue create --repo <your-user>/<repo> \
  --title "Fix the typo in README" \
  --body "There's a spelling error in line 5 of the README that should be corrected." \
  --label "surgeon:fix"
```

### Step 9: Watch it happen

1. Open `http://localhost:3000` — a new run card appears within ~5 seconds
2. Click the run → live timeline of the agent's tool calls scrolls in real-time
3. After 1-3 minutes, a PR appears on your repo
4. The dashboard shows **✓ complete** with the PR link

See a real example of a Surgeon PR: **https://github.com/itsdun1/widget-store-api/pull/2**

### Step 10: Teach the agent (the compounding moment)

If the agent does something you'd want differently:

1. Open **http://localhost:3000/memory**
2. Navigate the tree to `repos/<your-repo>/conventions.md`
3. Add your rule, e.g.:
   ```
   ## Logging
   Always log errors with `console.error`, never `console.log`.
   ```
4. Click **Save + commit** — this commits to the agent repo on GitHub

Next time the agent works on related code, it loads this convention automatically and cites it in the PR body's `## Sources` section.

### Step 11: Stop everything

In the terminal where `dev.sh` is running, press **Ctrl+C**. All 5 containers stop.

To also delete the Postgres data:
```bash
docker compose -f infra/docker-compose.yml --profile full down -v
```

---

## Path B — Run the agent standalone (no platform)

If you just want to use the agent from your terminal, no webhooks, no Docker:

### Step 1: Install the Lyzr gitagent CLI

```bash
bash <(curl -fsSL "https://raw.githubusercontent.com/open-gitagent/gitagent/main/install.sh")
```

The installer asks a few questions — pick **Advanced Setup** and paste your API key when asked.

### Step 2: Clone the agent

```bash
git clone https://github.com/itsdun1/repo-surgeon
cd repo-surgeon
```

### Step 3: Clone the target repo you want the agent to work on

```bash
git clone https://github.com/<you>/<some-repo> /tmp/target-repo
```

### Step 4: Run the agent

```bash
export TARGET_REPO=<you>/<some-repo>
export TARGET_DIR=/tmp/target-repo
export GITHUB_TOKEN=ghp_xxxxx     # a PAT with repo scope works
export OPENAI_API_KEY=sk-...

gitagent --dir . \
  --prompt "Read issue #1 on $TARGET_REPO. Fix the bug it describes. Open a PR." \
  --model openai:gpt-5.1
```

The agent will:
- Read its own SOUL/RULES/skills/memory from the current directory
- Look at code in `$TARGET_DIR`
- Make edits, run tests
- Commit + push a branch + open a PR via the GitHub API

---

## Path C — Fork for your own team

After Path A is working, customize:

### Step 1: Fork both repos

```bash
gh repo fork itsdun1/repo-surgeon --clone=false
gh repo fork itsdun1/repo-surgeon-platform --clone=false
```

### Step 2: Re-clone your fork

```bash
git clone --recurse-submodules https://github.com/<your-user>/repo-surgeon-platform
cd repo-surgeon-platform
```

### Step 3: Customize the agent

```bash
cd repo-surgeon

# Edit the persona
$EDITOR SOUL.md

# Add your team's rules (e.g., language-specific constraints)
$EDITOR RULES.md

# Document your tech stack so the agent doesn't have to guess
$EDITOR memory/org/tech-stack.md
$EDITOR memory/org/team-conventions.md

git add -A
git commit -m "customize for <your org>"
git push origin main
```

### Step 4: Point the platform at your fork

Edit `.env.local`:
```
AGENT_REPO_REMOTE=https://github.com/<your-user>/repo-surgeon
```

Re-run `./scripts/dev.sh`. The platform now uses your fork.

### Step 5: Optionally rebuild on a real cloud

The current `docker-compose` is local-first. For production, see [`ARCHITECTURE.md → Future work → Production deployment on Kubernetes`](ARCHITECTURE.md#production-deployment-on-kubernetes).

---

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `gitagent: command not found` after install | New shell needed to pick up PATH | Open a new terminal, or `source ~/.zshrc` |
| Setup wizard fails on `gh auth status` | `gh` CLI not logged in | `gh auth login` |
| `Address already in use` for port 15432/16379/18000/3000 | Another service on your laptop is using these | Either stop the other service, or change the port in `infra/docker-compose.yml` |
| Webhook not arriving | smee channel mismatch | Open the smee URL in browser — it shows live events. Compare with `SMEE_URL` in `.env.local` |
| Run failed with `gitagent CLI not installed` | The container couldn't find gitagent | Rebuild: `docker compose -f infra/docker-compose.yml --profile full build surgeon` |
| Agent opens PR but tests didn't run | Dependencies weren't installed in target clone | Check that the target repo's `package.json` / `pyproject.toml` is at the repo root |
| Dashboard shows "○ disconnected" on a finished run | Older version before the SSE fix | `git pull` and rebuild dashboard |

---

## At-a-glance trigger reference

| You do | Agent does |
|---|---|
| Label issue `surgeon:fix` | Read issue → find bug → write failing test → fix → run tests → open PR |
| Label issue `surgeon:feature` | Decompose feature → implement → write tests → human approval gate → open PR |
| Label issue `surgeon:refactor` | Treat as refactor request — pick smell, propose minimal change, open PR |
| Comment `/surgeon <mode>` on an issue | Same as label, but via comment |
| Trigger via dashboard "Manual trigger" button | Spawn a run with custom prompt |
| Daily 03:00 UTC cron | Cleanup old logs / runs / orphaned workspaces |

---

## Useful API endpoints (advanced)

```bash
# Trigger cleanup manually
curl -X POST http://localhost:18000/api/admin/cleanup

# List recent runs
curl http://localhost:18000/api/agents/runs?limit=20

# Get one run's details
curl http://localhost:18000/api/runs/<run-id>

# List repos the App is installed on
curl http://localhost:18000/api/repos

# Get memory file tree
curl http://localhost:18000/api/memory/tree

# Read a memory file
curl 'http://localhost:18000/api/memory/file?path=org/tech-stack.md'

# Manually trigger a run (no webhook)
curl -X POST http://localhost:18000/api/manual-trigger \
  -H 'content-type: application/json' \
  -d '{
    "repo": "<you>/<repo>",
    "mode": "issue:fix",
    "issue_number": 1,
    "installation_id": <id>,
    "prompt": "<optional custom prompt>"
  }'
```
