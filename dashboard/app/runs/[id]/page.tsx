"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useRunStream } from "@/lib/sse";
import { cn, fmtRelative, statusColor } from "@/lib/utils";
import { ArrowUpRight, Terminal } from "lucide-react";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const { data: run } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    enabled: !!runId,
    refetchInterval: 3_000,
  });

  const { events, state } = useRunStream(runId);
  const streamLabel: Record<typeof state, string> = {
    connecting: "○ connecting",
    live: "● live",
    ended: "✓ complete",
    error: "✗ error",
  };
  const streamColor: Record<typeof state, string> = {
    connecting: "text-zinc-500",
    live: "text-emerald-400",
    ended: "text-zinc-400",
    error: "text-red-400",
  };

  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [events.length]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs text-muted font-mono">run / {runId}</div>
          <div className="flex items-center gap-3 mt-2">
            <span className={cn("font-mono text-sm", statusColor(run?.status || ""))}>
              ● {run?.status || "loading"}
            </span>
            <span className="text-zinc-300 font-mono">{run?.repo}</span>
            <span className="text-xs text-muted">{run?.mode}</span>
            {run?.model && <span className="text-xs text-muted">on {run.model}</span>}
          </div>
        </div>
        <div className="text-right text-xs text-muted space-y-1">
          {run?.started_at && <div>started {fmtRelative(run.started_at)}</div>}
          {run?.finished_at && <div>finished {fmtRelative(run.finished_at)}</div>}
          {run?.cost_usd != null && <div>${run.cost_usd.toFixed(4)}</div>}
          {run?.pr_url && (
            <a
              href={run.pr_url}
              target="_blank"
              rel="noopener"
              className="text-emerald-400 flex items-center gap-1 justify-end"
            >
              PR #{run.pr_number} <ArrowUpRight size={12} />
            </a>
          )}
        </div>
      </div>

      <div className="rounded border border-border bg-panel/50">
        <div className="px-4 py-2 border-b border-border bg-panel flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm">
            <Terminal size={14} />
            <span>agent stream</span>
            <span className={cn("text-xs", streamColor[state])}>{streamLabel[state]}</span>
          </div>
          <div className="text-xs text-muted font-mono">{events.length} lines</div>
        </div>
        <div
          ref={logRef}
          className="font-mono text-xs leading-relaxed p-4 max-h-[600px] overflow-y-auto scrollbar-mono whitespace-pre-wrap"
        >
          {events.length === 0 ? (
            <div className="text-zinc-600">waiting for agent output…</div>
          ) : (
            events.map((e, i) => {
              if (e.kind === "stream_end") {
                return (
                  <div key={i} className="text-zinc-500 italic py-2">
                    — stream ended ({e.reason || "complete"}
                    {e.exit_code != null ? `, exit=${e.exit_code}` : ""})
                    {e.pr_url && (
                      <>
                        {" — "}
                        <a href={e.pr_url} target="_blank" rel="noopener" className="text-emerald-400 underline">
                          {e.pr_url}
                        </a>
                      </>
                    )}
                  </div>
                );
              }
              if (e.kind === "error") {
                return (
                  <div key={i} className="text-red-400 py-1">
                    error: {e.message}
                  </div>
                );
              }
              return (
                <div key={i} className={cn(e.kind === "historical" ? "text-zinc-500" : "text-zinc-200")}>
                  {e.line}
                </div>
              );
            })
          )}
        </div>
      </div>

      {run?.prompt && (
        <details className="rounded border border-border bg-panel/30 p-3 text-sm">
          <summary className="cursor-pointer text-zinc-400">Prompt</summary>
          <pre className="mt-2 text-xs whitespace-pre-wrap text-zinc-300">{run.prompt}</pre>
        </details>
      )}

      {run?.error && (
        <div className="rounded border border-red-900 bg-red-950/30 p-3 text-sm text-red-300">
          <div className="font-medium">Error</div>
          <pre className="mt-2 text-xs whitespace-pre-wrap">{run.error}</pre>
        </div>
      )}
    </div>
  );
}
