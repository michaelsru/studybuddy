import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { SessionDetail, SessionSummary } from "../types/session";

export default function SessionListPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: sessions = [], isPending } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.get<SessionSummary[]>("/sessions"),
  });

  const create = useMutation({
    mutationFn: () => api.post<SessionDetail>("/sessions", { preset: "full" }),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      navigate(`/sessions/${s.id}`);
    },
  });

  return (
    <div style={{ maxWidth: 680, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Buddy</h1>
        <button onClick={() => create.mutate()} disabled={create.isPending}>
          {create.isPending ? "Creating…" : "+ New Session"}
        </button>
      </div>

      {isPending ? (
        <p>Loading…</p>
      ) : sessions.length === 0 ? (
        <p style={{ color: "#888" }}>No sessions yet. Start one.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, marginTop: "1.5rem" }}>
          {sessions.map((s) => (
            <li
              key={s.id}
              onClick={() => navigate(`/sessions/${s.id}`)}
              style={{ padding: "0.75rem 1rem", border: "1px solid #ddd", borderRadius: 8, marginBottom: 8, cursor: "pointer" }}
            >
              <strong>{s.title ?? "Untitled"}</strong>
              <span style={{ marginLeft: "1rem", color: "#888", fontSize: 13 }}>
                Step {s.current_step} · {s.status} · {s.cards_committed} cards
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
