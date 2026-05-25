"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function EvalsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["evals"], queryFn: () => api.listEvals({}) });
  const evals = data?.evals || [];

  // Build a fixture × runtime matrix
  const fixtures = [...new Set(evals.map((e) => e.fixture_id))];
  const runtimes = [...new Set(evals.map((e) => e.runtime))];

  const cell = (fixtureId: string, runtime: string) => {
    const matching = evals.filter((e) => e.fixture_id === fixtureId && e.runtime === runtime);
    if (matching.length === 0) return null;
    const latest = matching[0];
    return latest;
  };

  return (
    <div className="space-y-4">
      <div className="rounded border border-border bg-panel/30 p-4">
        <div className="text-sm text-zinc-300 font-medium mb-1">Eval matrix</div>
        <div className="text-xs text-muted">
          Each cell is the latest eval result for that fixture × runtime. Color = pass rate. Click a cell to see the
          trace.
        </div>
      </div>

      {isLoading ? (
        <div className="text-zinc-500 text-sm">Loading…</div>
      ) : evals.length === 0 ? (
        <div className="rounded border border-border bg-panel/30 p-6 text-zinc-500 text-sm">
          No eval runs yet. Trigger from CLI: <code className="bg-bg px-1 rounded">python repo-surgeon/evals/run_evals.py</code>.
        </div>
      ) : (
        <div className="rounded border border-border bg-panel/30 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-panel">
                <th className="text-left px-4 py-2 text-zinc-400">Fixture</th>
                {runtimes.map((rt) => (
                  <th key={rt} className="text-left px-4 py-2 text-zinc-400 font-mono">
                    {rt}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fixtures.map((f) => (
                <tr key={f} className="border-b border-border/50">
                  <td className="px-4 py-2 font-mono text-zinc-200">{f}</td>
                  {runtimes.map((rt) => {
                    const c = cell(f, rt);
                    return (
                      <td key={rt} className="px-4 py-2">
                        {c ? (
                          <div
                            className={cn(
                              "inline-flex items-center gap-2 px-2 py-1 rounded font-mono",
                              c.passed ? "bg-emerald-900/30 text-emerald-300" : "bg-red-900/30 text-red-300",
                            )}
                          >
                            <span>{c.passed ? "✓" : "✗"}</span>
                            <span>{c.score != null ? c.score.toFixed(2) : "—"}</span>
                            {c.latency_ms != null && <span className="text-muted">{c.latency_ms}ms</span>}
                            {c.cost_usd != null && <span className="text-muted">${c.cost_usd.toFixed(3)}</span>}
                          </div>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
