import { useEffect, useRef, useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { ElaborationTurn, SessionDetail } from "../../types/session";

const WS_BASE = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000";

type ChatMsg = { role: "buddy" | "user"; content: string; streaming?: boolean };

function useElaboration(sessionId: string, existingTurns: ElaborationTurn[]) {
  const [msgs, setMsgs] = useState<ChatMsg[]>(
    existingTurns.map((t) => ({ role: t.role as "buddy" | "user", content: t.content }))
  );
  const [suggestClose, setSuggestClose] = useState(false);
  const [connected, setConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const streamingIdx = useRef<number | null>(null);
  const intentionalClose = useRef(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    intentionalClose.current = false;
    const sock = new WebSocket(`${WS_BASE}/sessions/${sessionId}/elaboration`);

    sock.onopen = () => setConnected(true);
    sock.onclose = () => {
      setConnected(false);
      if (!intentionalClose.current) {
        reconnectTimer.current = setTimeout(connect, 2000);
      }
    };
    sock.onerror = () => sock.close();

    sock.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "pong") return;
      if (msg.type === "token") {
        setMsgs((prev) => {
          if (streamingIdx.current === null) {
            streamingIdx.current = prev.length;
            return [...prev, { role: "buddy", content: msg.content, streaming: true }];
          }
          const next = [...prev];
          next[streamingIdx.current!] = {
            ...next[streamingIdx.current!],
            content: next[streamingIdx.current!].content + msg.content,
          };
          return next;
        });
      }
      if (msg.type === "buddy_message") {
        streamingIdx.current = null;
        setMsgs((prev) => {
          if (prev.length > 0 && prev[prev.length - 1].streaming) {
            const next = [...prev];
            next[next.length - 1] = { role: "buddy", content: msg.content };
            return next;
          }
          const alreadyPresent = prev.some((m) => m.role === "buddy" && m.content === msg.content);
          return alreadyPresent ? prev : [...prev, { role: "buddy", content: msg.content }];
        });
        setSuggestClose(msg.suggest_close ?? false);
      }
      if (msg.type === "error") {
        setMsgs((prev) => [...prev, { role: "buddy", content: `⚠ ${msg.content}` }]);
      }
    };

    ws.current = sock;
  }, [sessionId]);

  useEffect(() => {
    connect();
    const ping = setInterval(
      () => ws.current?.readyState === WebSocket.OPEN && ws.current.send(JSON.stringify({ type: "ping" })),
      20000
    );
    return () => {
      clearInterval(ping);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      intentionalClose.current = true;
      ws.current?.close();
    };
  }, [connect]);

  const send = useCallback((content: string) => {
    ws.current?.send(JSON.stringify({ type: "user_message", content }));
    setMsgs((prev) => [...prev, { role: "user", content }]);
    streamingIdx.current = null;
  }, []);

  return { msgs, suggestClose, connected, send };
}

export default function Step5_Elaboration({ session, onAdvance }: { session: SessionDetail; onAdvance: (step: number) => void }) {
  const [input, setInput] = useState("");
  const qc = useQueryClient();
  const bottomRef = useRef<HTMLDivElement>(null);
  const { msgs, suggestClose, connected, send } = useElaboration(
    session.id,
    session.elaboration_turns
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const close = useMutation({
    mutationFn: () => api.post<SessionDetail>(`/sessions/${session.id}/elaboration/close`, {}),
    onSuccess: (s) => {
      qc.setQueryData(["session", session.id], s);
      qc.invalidateQueries({ queryKey: ["sessions"] });
      onAdvance(s.current_step);
    },
  });

  const handleSend = () => {
    const text = input.trim();
    if (!text || !connected) return;
    send(text);
    setInput("");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <h3 style={{ margin: 0 }}>Step 5 — Elaboration</h3>

      <div style={{ background: "#f8f9fa", borderRadius: 8, padding: "1rem", maxHeight: 400, overflowY: "auto" }}>
        {msgs.map((m, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: m.role === "user" ? "flex-end" : "flex-start",
              marginBottom: "0.5rem",
            }}
          >
            <div
              style={{
                maxWidth: "80%",
                background: m.role === "user" ? "#6366f1" : "#fff",
                color: m.role === "user" ? "#fff" : "#1a1a2e",
                border: m.role === "buddy" ? "1px solid #e2e8f0" : "none",
                borderRadius: 12,
                padding: "0.5rem 0.75rem",
                fontSize: 14,
                opacity: m.streaming ? 0.8 : 1,
              }}
            >
              {m.content}
              {m.streaming && <span style={{ opacity: 0.5 }}> ▋</span>}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {suggestClose && (
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: "0.75rem 1rem", fontSize: 14, color: "#166534" }}>
          Buddy thinks the topic is well covered. Ready to move on?
        </div>
      )}

      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          style={{ flex: 1, padding: "0.5rem 0.75rem", borderRadius: 8, border: "1px solid #ddd", fontSize: 14 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleSend())}
          placeholder={connected ? "Reply to Buddy…" : "Connecting…"}
          disabled={!connected}
        />
        <button onClick={handleSend} disabled={!connected || !input.trim()}>Send</button>
        {suggestClose && (
          <button
            onClick={() => close.mutate()}
            disabled={close.isPending}
            style={{ background: "#22c55e", color: "#fff" }}
          >
            {close.isPending ? "…" : "Move on →"}
          </button>
        )}
      </div>

      {!suggestClose && (
        <button
          onClick={() => close.mutate()}
          disabled={close.isPending}
          style={{ alignSelf: "flex-start", background: "transparent", color: "#888", fontSize: 13, border: "none", cursor: "pointer", padding: 0 }}
        >
          Skip elaboration →
        </button>
      )}
    </div>
  );
}
