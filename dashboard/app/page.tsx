"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, type Run } from "@/lib/api";
import { cn, fmtRelative, statusColor } from "@/lib/utils";
import { ArrowUpRight } from "lucide-react";

function RunRow({ r }: { r: Run }) {
  return (
    <Link
      href={`/runs/${r.id}`}
      className="block px-4 py-3 hover:bg-panel transition border-b border-border/50"
    >
      <div className="flex items-center gap-4 text-sm">
        <span className={cn("font-mono w-20 truncate", statusColor(r.status))}>{r.status}</span>
        <span className="text-zinc-400 w-20">{r.mode}</span>
        <span className="flex-1 font-mono text-zinc-100 truncate">{r.repo}</span>
        {r.pr_url && (
          <a href={r.pr_url} target="_blank" rel="noopener" className="text-emerald-400 text-xs flex items-center gap-1">
            PR #{r.pr_number} <ArrowUpRight size={12} />
          </a>
        )}
        <span className="text-zinc-500 text-xs w-20 text-right">{fmtRelative(r.created_at)}</span>
      </div>
    </Link>
  );
}

export default function HomePage() {
  const { data, isLoading } = useQuery({ queryKey: ["runs"], queryFn: () => api.listRuns({ limit: 50 }) });

  const runs = data?.runs || [];
  const counts = {
    running: runs.filter((r) => r.status === "running").length,
    success: runs.filter((r) => r.status === "success").length,
    failed: runs.filter((r) => r.status === "failed").length,
    queued: runs.filter((r) => r.status === "queued").length,
  };
  const totalCost = runs.reduce((acc, r) => acc + (r.cost_usd || 0), 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-5 gap-3">
        <Stat label="Running" value={counts.running} accent="text-blue-400" />
        <Stat label="Queued" value={counts.queued} accent="text-zinc-400" />
        <Stat label="Succeeded (50)" value={counts.success} accent="text-emerald-400" />
        <Stat label="Failed (50)" value={counts.failed} accent="text-red-400" />
        <Stat label="LLM cost (50)" value={`$${totalCost.toFixed(2)}`} accent="text-zinc-200" />
      </div>

      <div className="rounded border border-border bg-panel/50 overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-panel font-medium text-sm">
          Recent runs
        </div>
        {isLoading ? (
          <div className="p-6 text-zinc-500 text-sm">Loading…</div>
        ) : runs.length === 0 ? (
          <div className="p-6 text-zinc-500 text-sm">
            No runs yet. Label an issue with <code className="bg-bg px-1 rounded">surgeon:fix</code> in one of your configured repos.
          </div>
        ) : (
          runs.map((r) => <RunRow key={r.id} r={r} />)
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent: string }) {
  return (
    <div className="border border-border bg-panel/50 rounded px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={cn("text-2xl font-mono mt-1", accent)}>{value}</div>
    </div>
  );
}
