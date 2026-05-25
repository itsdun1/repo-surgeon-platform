# Demo Script — 4 minutes

A minute-by-minute storyboard for the demo video. All shots are on the local machine; nothing here is cloud-deployed.

## Cold open (0:00–0:15)

**Shot**: terminal showing `gh pr list --search "author:repo-surgeon[bot]"` with 3-5 actual PRs already opened on the demo target repos during prep.

**Narration**:
> "These pull requests were all opened by an AI agent — not Devin, not Cursor. They're opened by a GitHub App that lives across my repos. The agent itself is a folder of markdown and YAML files on GitHub, which means it's forkable, reviewable, and gets smarter every time I review a PR. Here's how it works."

## Architecture explainer (0:15–0:45)

**Shot**: one slide rendering the architecture diagram from `ARCHITECTURE.md` (top-down: GitHub → smee.io → laptop → agent repo + target workspace + Postgres + dashboard).

**Narration**:
> "Three layers. The agent itself is a GitAgent Protocol repo — fully portable. The Lyzr gitagent CLI runs it. And around that, I built a FastAPI dispatcher, a Postgres-backed run history, and a Next.js dashboard so you can watch live. Everything runs on my laptop. No cloud accounts. Webhooks tunnel through smee.io."

## Live PR opening — the wow (0:45–1:30)

**Shot 1 (0:45)**: on a target repo's GitHub page, click "New issue", title: "Cart total wrong when prices have decimals", labels: `bug`, `surgeon:fix`. Click submit.

**Shot 2 (0:55)**: cut to dashboard at `localhost:3000` — a new run card appears within 3 seconds, status `running`, mode `issue:fix`.

**Shot 3 (1:00)**: click into `/runs/<id>` — the SSE-streamed tool timeline scrolls: `Read package.json`, `Grep "calculate"`, `Read src/cart.ts`, `Edit src/cart.ts`, `Bash "npm test"`, `Bash "git push"`, `github-api open_pr`.

**Shot 4 (1:20)**: cut to GitHub — PR #X appears with `[surgeon:fix]` title, body with five sections, label `surgeon:fix`. Diff shows the `Decimal`/`Money` fix.

**Narration**:
> "Issue filed at 0:45. PR ready at 1:20. The agent read the code, found the bug, added a regression test, ran the suite, opened the PR. The diff is small, the body explains why."

## Memory editing — the compound moment (1:30–2:15)

**Shot 1 (1:30)**: on the just-opened PR, leave a review comment: "Use the Money class — never raw numbers for currency."

**Shot 2 (1:40)**: dashboard `/memory` — click `repos/<target>/conventions.md`, edit it: add a section "Always use the `Money` class for currency arithmetic. Never use raw `number` for prices." Save.

**Shot 3 (1:50)**: status line confirms "✓ committed + pushed". Switch to GitHub on the agent repo (`repo-surgeon`) — show the new commit with `surgeon-memory:` message.

**Shot 4 (2:00)**: file another issue ("Discount calculation rounds wrong") on the same target. New run starts. Timeline shows `Read memory/repos/<target>/conventions.md` first. PR opens using `Money` class throughout. PR body cites the memory entry under `## Sources`.

**Narration**:
> "I didn't fix the agent — I taught it. The next PR uses Money class. The one after that uses Money class. Across every repo where this rule applies. Memory is curated infrastructure, and the agent's improvement is a git diff you can review."

## Multi-runtime — same agent, different LLM (2:15–3:00)

**Shot 1 (2:15)**: dashboard `/evals` — fixture × runtime matrix with rows = fixtures, columns = `anthropic:claude-opus-4-7` and `openai:gpt-5.1`. Cells colored by pass rate.

**Shot 2 (2:25)**: click `bug-fix-null-deref` × Claude cell. Show the trace summary, cost ($0.07), latency.

**Shot 3 (2:40)**: same cell on OpenAI — different diff style, both pass tests, different cost ($0.04).

**Shot 4 (2:50)**: terminal: same `gitagent` invocation, swap `--model openai:gpt-5.1`. Run another live issue. PR opens; identical content quality, different stylistic choices.

**Narration**:
> "Same agent. Different brain. The agent.yaml declares Claude preferred, OpenAI fallback. The eval suite runs every fixture on both. You see the diff in behavior before you ship it. This is what 'multi-runtime' means in GAP — not a marketing line."

## Fork and deploy (3:00–3:30)

**Shot 1 (3:00)**: terminal: `git clone https://github.com/<you>/repo-surgeon-platform && cd repo-surgeon-platform && ./scripts/setup.sh`. The wizard streams its prompts.

**Shot 2 (3:15)**: `./scripts/dev.sh` brings up Docker + uvicorn + Next dev. `localhost:3000` opens fresh, empty dashboard.

**Shot 3 (3:25)**: file an issue on the new test fork repo. Run card appears within 5 seconds.

**Narration**:
> "Clone. Setup. Dev. Three commands. Your platform, your repos, your model keys, on your laptop. No SaaS, no per-seat. When Lyzr releases a new GAP version, you fork upstream and merge in."

## Closing pitch (3:30–4:00)

**Shot**: split screen. Left: dashboard with live activity counter, eval matrix, memory tree. Right: the architecture diagram fades to a logo.

**Narration**:
> "1,400 lines of GAP agent. 3,000 lines of platform around it. All open source. Runs anywhere Python and Node do. Memory that compounds. Forkable agents. Multi-runtime. Made with GAP."

**End card**:
```
github.com/<you>/repo-surgeon-platform
docs/ARCHITECTURE.md  ·  docs/DEMO.md
Made with GitAgent Protocol
```

**Total runtime: 4:00**

---

## Pre-recording checklist

- [ ] Synthetic demo repo seeded with 3+ realistic bugs, issues filed
- [ ] 1 fork of a real OSS repo with `surgeon:` labels created
- [ ] GitHub App installed on those repos
- [ ] smee channel verified delivering webhooks
- [ ] `dev.sh` running, dashboard at localhost:3000 visible
- [ ] Anthropic + OpenAI API keys with credit
- [ ] Eval suite pre-populated with at least 4 runs (so the matrix isn't empty)
- [ ] At least 1 prior memory commit on the agent repo (so `git log memory/` looks alive)
- [ ] Screen recording at 1080p, 30fps, with selective zoom on key shots (dashboard timeline, PR diff, memory edit)
- [ ] Voiceover scripted; don't ad-lib

## What can break and how to recover

- **Live PR doesn't open in time**: pre-record the slow segment, intercut with the live action
- **smee delivers a duplicate event**: dedupe ensures only one run; show this as resilience, not a bug
- **An LLM call rate-limits**: have the OpenAI fallback already triggered once to demonstrate it
- **Memory push fails**: re-record that segment with the remote correctly set
