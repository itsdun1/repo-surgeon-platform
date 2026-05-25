"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function ReposPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["repos"], queryFn: api.listRepos });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api.updateRepo(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["repos"] }),
  });
  return (
    <div className="space-y-4">
      <div className="text-sm text-muted">Repos discovered via GitHub App installation webhooks.</div>
      <div className="rounded border border-border bg-panel/30 overflow-hidden">
        <table className="min-w-full text-sm">
          <thead className="bg-panel border-b border-border text-xs text-muted">
            <tr>
              <th className="text-left px-4 py-2">Repo</th>
              <th className="text-left px-4 py-2">Default branch</th>
              <th className="text-left px-4 py-2">Language</th>
              <th className="text-left px-4 py-2">Enabled</th>
            </tr>
          </thead>
          <tbody>
            {(data?.repos || []).map((r) => (
              <tr key={r.id} className="border-b border-border/50">
                <td className="px-4 py-2 font-mono">{r.full_name}</td>
                <td className="px-4 py-2 text-zinc-400">{r.default_branch}</td>
                <td className="px-4 py-2 text-zinc-400">{r.language || "—"}</td>
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={(e) => toggle.mutate({ id: r.id, enabled: e.target.checked })}
                    className="accent-emerald-500"
                  />
                </td>
              </tr>
            ))}
            {(!data || data.repos.length === 0) && (
              <tr>
                <td className="px-4 py-6 text-zinc-500" colSpan={4}>
                  No repos yet. Install the App on your account and label an issue with{" "}
                  <code className="bg-bg px-1 rounded">surgeon:fix</code>.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
