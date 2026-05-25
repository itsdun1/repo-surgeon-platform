"use client";

import { useEffect, useRef, useState } from "react";

export type StreamEvent = {
  kind: "historical" | "live" | "stream_end" | "error";
  line?: string;
  reason?: string;
  status?: string;
  pr_url?: string | null;
  exit_code?: number | null;
  message?: string;
  ts?: number;
};

export type StreamState = "connecting" | "live" | "ended" | "error";

export function useRunStream(runId: string | null) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [state, setState] = useState<StreamState>("connecting");
  const closedNaturally = useRef(false);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    setState("connecting");
    closedNaturally.current = false;

    // Next.js rewrites don't stream SSE reliably in prod builds. Talk to the
    // backend directly from the browser. CORS is allowed for localhost:3000.
    const sseBase = process.env.NEXT_PUBLIC_BACKEND_BROWSER_URL || "http://localhost:18000";
    const es = new EventSource(`${sseBase}/sse/runs/${runId}`);

    es.onopen = () => {
      if (!closedNaturally.current) setState("live");
    };

    es.onmessage = (e) => {
      try {
        const obj = JSON.parse(e.data) as StreamEvent;
        setEvents((prev) => [...prev, { ...obj, ts: Date.now() }]);

        if (obj.kind === "stream_end") {
          // Server told us to stop. Close locally so the browser doesn't try to
          // reconnect and trigger a false "error" state.
          closedNaturally.current = true;
          setState("ended");
          es.close();
        } else if (obj.kind === "error") {
          closedNaturally.current = true;
          setState("error");
          es.close();
        }
      } catch {
        // keepalive comments (`: keepalive\n\n`) are not JSON — ignore silently.
      }
    };

    es.onerror = () => {
      // If the server already told us to stop, this is the expected close —
      // don't downgrade the state to error.
      if (closedNaturally.current) return;
      // Browsers fire onerror BOTH for transient network blips (and then auto-
      // reconnect) AND for permanent failures. Use readyState to disambiguate.
      if (es.readyState === EventSource.CLOSED) {
        setState("error");
      }
      // readyState === CONNECTING means it's retrying; keep state as is.
    };

    return () => {
      closedNaturally.current = true;
      es.close();
    };
  }, [runId]);

  return { events, state };
}
