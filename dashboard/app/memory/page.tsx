"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type MemoryNode } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ChevronRight, ChevronDown, File, Folder, Save } from "lucide-react";

function TreeNode({
  node,
  onSelect,
  selected,
  depth = 0,
}: {
  node: MemoryNode;
  onSelect: (path: string) => void;
  selected: string | null;
  depth?: number;
}) {
  const [open, setOpen] = useState(depth < 2);
  if (node.type === "file") {
    return (
      <div
        onClick={() => onSelect(node.path)}
        className={cn(
          "flex items-center gap-1 px-2 py-1 cursor-pointer text-sm hover:bg-panel rounded",
          selected === node.path && "bg-panel text-emerald-400",
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <File size={12} className="text-zinc-500" />
        <span className="truncate">{node.name}</span>
      </div>
    );
  }
  return (
    <div>
      <div
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 px-2 py-1 cursor-pointer text-sm hover:bg-panel rounded"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Folder size={12} className="text-zinc-500" />
        <span className="text-zinc-300 truncate">{node.name}</span>
      </div>
      {open && node.children && (
        <div>
          {node.children.map((c) => (
            <TreeNode key={c.path} node={c} onSelect={onSelect} selected={selected} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function MemoryPage() {
  const qc = useQueryClient();
  const { data: tree } = useQuery({ queryKey: ["memory-tree"], queryFn: api.memoryTree });
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [message, setMessage] = useState<string>("memory: human edit via dashboard");
  const [status, setStatus] = useState<string>("");

  const { data: file } = useQuery({
    queryKey: ["memory-file", selected],
    queryFn: () => api.memoryFile(selected!),
    enabled: !!selected,
  });

  // Sync draft when the loaded file matches the selected path
  useEffect(() => {
    if (file && file.path === selected) setDraft(file.content);
  }, [file, selected]);

  const save = useMutation({
    mutationFn: () =>
      api.editMemory({ path: selected!, new_content: draft, message, edited_by: "dashboard" }),
    onSuccess: (res: any) => {
      setStatus(res.committed ? "✓ committed" + (res.pushed ? " + pushed" : " (push failed — check git remote)") : "× commit failed");
      qc.invalidateQueries({ queryKey: ["memory-tree"] });
    },
    onError: (e: any) => setStatus(`error: ${e.message}`),
  });

  return (
    <div className="grid grid-cols-12 gap-4 h-[calc(100vh-160px)]">
      <div className="col-span-3 border border-border bg-panel/30 rounded overflow-y-auto scrollbar-mono">
        <div className="px-3 py-2 border-b border-border text-xs text-muted">memory/ tree</div>
        {tree ? <TreeNode node={tree} onSelect={(p) => { setSelected(p); setDraft(""); setStatus(""); }} selected={selected} /> : <div className="p-3 text-zinc-500 text-sm">Loading…</div>}
      </div>

      <div className="col-span-9 border border-border bg-panel/30 rounded flex flex-col">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
            Select a file from the tree to edit. Saving creates a commit on the agent repo.
          </div>
        ) : (
          <>
            <div className="px-4 py-2 border-b border-border bg-panel flex items-center justify-between">
              <div className="font-mono text-sm">{selected}</div>
              <div className="flex items-center gap-3">
                <input
                  className="bg-bg border border-border rounded px-2 py-1 text-xs w-72"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="commit message"
                />
                <button
                  onClick={() => save.mutate()}
                  disabled={save.isPending || !file}
                  className="bg-emerald-700 hover:bg-emerald-600 text-zinc-100 text-xs px-3 py-1 rounded flex items-center gap-1 disabled:opacity-50"
                >
                  <Save size={12} /> Save + commit
                </button>
              </div>
            </div>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="flex-1 bg-bg text-zinc-200 font-mono text-sm p-4 outline-none resize-none scrollbar-mono"
              spellCheck={false}
            />
            <div className="px-4 py-2 border-t border-border text-xs text-muted">{status}</div>
          </>
        )}
      </div>
    </div>
  );
}
