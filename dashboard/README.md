# Repo Surgeon Dashboard

Next.js cockpit for the Repo Surgeon platform. Talks to `surgeon-service` at `localhost:8000`.

## Pages

- `/` — recent runs across all repos, live status
- `/runs/[id]` — live agent stream via SSE; tool calls, files touched, PR link
- `/memory` — file-tree of `repo-surgeon/memory/`, editable; saving opens a commit on the agent repo
- `/evals` — fixture × runtime matrix; multi-runtime side-by-side comparison
- `/repos` — list of repos with the GitHub App installed; toggle which are active

## Development

```bash
pnpm install
pnpm dev   # http://localhost:3000
```

API rewrites in `next.config.js` proxy `/api/backend/*` → `localhost:8000/api/*` and `/sse/*` → `localhost:8000/sse/*`. So you only need one origin in the browser.

## Stack

Next.js 15 (App Router) + React 19, Tailwind, TanStack Query, lucide-react. Dark-only by design.
