# Setup Guide

End-to-end setup for running Repo Surgeon locally on your laptop.

## Prerequisites

- **macOS or Linux** (Windows works via WSL2)
- **Docker** (for Postgres + Redis)
- **Python 3.11+** (for `surgeon-service` and the GAP agent's tool scripts)
- **Node.js 20+** + **pnpm** (for the dashboard)
- **`gh` CLI** authenticated to your GitHub account
- An **Anthropic API key** (and optionally OpenAI)
- The **`gitagent` CLI** installed:
  ```bash
  bash <(curl -fsSL "https://raw.githubusercontent.com/open-gitagent/gitagent/main/install.sh")
  ```

## Step 1 — Clone the platform

```bash
git clone https://github.com/<you>/repo-surgeon-platform
cd repo-surgeon-platform
```

## Step 2 — Run the setup wizard

```bash
./scripts/setup.sh
```

The wizard walks through:

1. **Verify `gh` CLI auth** — bails if you're not logged in
2. **Capture API keys** — `ANTHROPIC_API_KEY`, optionally `OPENAI_API_KEY`
3. **smee.io channel** — visit `https://smee.io/new` in your browser, click "Start a new channel", paste the URL
4. **GitHub App** — opens `https://github.com/settings/apps/new` in your browser
   - Set the webhook URL to your smee.io URL
   - Set the webhook secret (anything; you'll paste it back into the wizard)
   - Permissions: Issues R/W, Pull requests R/W, Contents R/W, Metadata R, Checks R/W
   - Events: issues, issue_comment, pull_request, push, installation
   - Generate a private key, download the `.pem` file, move it to `secrets/github-app-private-key.pem`
5. **Demo target repos (optional)** — wizard offers to `gh repo fork` 1-2 small OSS repos to your account as targets, adding `surgeon:fix`/`surgeon:feature`/`surgeon:refactor` labels
6. **Writes `.env.local`** with everything captured

## Step 3 — Install the GitHub App on your repos

Visit `https://github.com/settings/installations` → click **Configure** next to your app → select the repos to enable.

## Step 4 — Start everything

```bash
./scripts/dev.sh
```

This brings up:

- Postgres on `:5432` (via Docker)
- Redis on `:6379` (via Docker)
- smee-client (if `SMEE_URL` is set) forwarding webhooks to localhost
- `surgeon-service` on `:8000`
- `dashboard` on `:3000`

Hit Ctrl+C to stop everything.

## Step 5 — Try it

1. Open one of your configured demo repos on GitHub
2. File a new issue, e.g.:
   - Title: "Add input validation to /upload endpoint"
   - Body: describe the bug or feature
   - Add label `surgeon:fix` or `surgeon:feature`
3. Open `http://localhost:3000` in your browser — within ~5 seconds a new run card appears
4. Click into the run → watch the agent's tool calls stream live
5. After ~1-3 minutes, a PR appears on the target repo

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Webhook not arriving | Check the smee.io channel page — it shows live events. Check the GitHub App settings for the webhook URL. |
| `401 bad signature` | `GITHUB_WEBHOOK_SECRET` mismatch between `.env.local` and GitHub App settings |
| `gitagent: command not found` | The Lyzr CLI isn't installed or not on PATH |
| Run stuck at "queued" | Worker didn't start. Check `surgeon-service` logs. |
| Memory edit doesn't push | `./repo-surgeon/` has no git remote configured. `cd repo-surgeon && git remote add origin https://github.com/<you>/repo-surgeon` |
| Tests don't run in target repo | The agent aborted per RULE 13. Check the issue comment it posted explaining what was needed. |

## Stopping & cleaning up

```bash
# stop running services (if dev.sh is in foreground, Ctrl+C does this)
docker compose -f infra/docker-compose.yml down

# nuclear: also remove DB volume
docker compose -f infra/docker-compose.yml down -v
```
