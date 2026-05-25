// Typed wrappers for surgeon-service API.
// All paths go through the Next rewrite at /api/backend -> http://localhost:8000/api

export type Run = {
  id: string;
  repo: string;
  mode: string;
  status: "queued" | "running" | "success" | "failed" | "cancelled" | string;
  trigger: string;
  model: string | null;
  started_at: string | null;
  finished_at: string | null;
  cost_usd: number | null;
  pr_url: string | null;
  pr_number: number | null;
  issue_number: number | null;
  tool_calls: number;
  created_at: string | null;
};

export type Repo = {
  id: string;
  full_name: string;
  default_branch: string;
  language: string | null;
  enabled: boolean;
  rules: Record<string, unknown>;
};

const BASE = "/api/backend";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

export const api = {
  listRuns: (q?: { repo?: string; status?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (q?.repo) qs.set("repo", q.repo);
    if (q?.status) qs.set("status", q.status);
    if (q?.limit) qs.set("limit", String(q.limit));
    return get<{ runs: Run[] }>(`/agents/runs?${qs}`);
  },
  getRun: (id: string) => get<Run & { prompt: string | null; log_path: string | null; error: string | null }>(`/runs/${id}`),
  listRepos: () => get<{ repos: Repo[] }>(`/repos`),
  updateRepo: (id: string, body: Partial<Repo>) => patch(`/repos/${id}`, body),

  memoryTree: () => get<MemoryNode>(`/memory/tree`),
  memoryFile: (path: string) =>
    get<{ path: string; content: string; size: number }>(`/memory/file?path=${encodeURIComponent(path)}`),
  editMemory: (body: { path: string; new_content: string; message?: string; edited_by?: string }) =>
    patch(`/memory/file`, body),

  listEvals: (q?: { suite?: string; runtime?: string }) => {
    const qs = new URLSearchParams();
    if (q?.suite) qs.set("suite", q.suite);
    if (q?.runtime) qs.set("runtime", q.runtime);
    return get<{ evals: EvalRun[] }>(`/evals?${qs}`);
  },

  manualTrigger: (body: {
    repo: string;
    mode: string;
    installation_id: number;
    prompt?: string;
    issue_number?: number;
    model?: string;
  }) => post<{ queued: boolean; run_id: string }>(`/manual-trigger`, body),
};

export type MemoryNode = {
  name: string;
  type: "dir" | "file";
  path: string;
  size?: number;
  children?: MemoryNode[];
};

export type EvalRun = {
  id: string;
  fixture_id: string;
  suite: string;
  runtime: string;
  passed: boolean;
  score: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
  created_at: string | null;
};
