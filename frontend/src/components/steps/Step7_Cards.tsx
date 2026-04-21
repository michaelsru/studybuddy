import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { CardProposal, SessionDetail } from "../../types/session";

export default function Step7_Cards({ session }: { session: SessionDetail }) {
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const qc = useQueryClient();
  const navigate = useNavigate();

  const toggle = (id: string) =>
    setApproved((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const commit = useMutation({
    mutationFn: () =>
      api.post<SessionDetail>(`/sessions/${session.id}/cards/commit`, {
        approved_ids: [...approved],
      }),
    onSuccess: (s) => {
      qc.setQueryData(["session", session.id], s);
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  return (
    <div>
      <h3>Step 7 — Card Proposals</h3>
      {session.card_proposals.length === 0 ? (
        <p>No cards generated.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {session.card_proposals.map((c) => (
            <CardRow key={c.id} card={c} checked={approved.has(c.id)} onToggle={() => toggle(c.id)} />
          ))}
        </ul>
      )}

      {session.status !== "completed" ? (
        <button onClick={() => commit.mutate()} disabled={commit.isPending} style={{ marginTop: "1rem" }}>
          {commit.isPending ? "Adding…" : `Add ${approved.size} Card${approved.size !== 1 ? "s" : ""} to Anki`}
        </button>
      ) : (
        <div style={{ marginTop: "1rem" }}>
          <p style={{ color: "#34d399", fontWeight: 600 }}>✓ Session complete</p>
          <a href="/">← Back to sessions</a>
        </div>
      )}
    </div>
  );
}

function CardRow({ card, checked, onToggle }: { card: CardProposal; checked: boolean; onToggle: () => void }) {
  return (
    <li
      style={{
        border: `1px solid ${checked ? "#6366f1" : "#ddd"}`,
        borderRadius: 8,
        padding: "0.75rem 1rem",
        marginBottom: 8,
        cursor: "pointer",
        background: checked ? "#eef2ff" : "#fff",
      }}
      onClick={onToggle}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12, background: "#e0e7ff", color: "#4338ca", borderRadius: 4, padding: "2px 6px" }}>
          {card.card_type}
        </span>
        {card.is_gap_card && (
          <span style={{ fontSize: 12, background: "#fef3c7", color: "#92400e", borderRadius: 4, padding: "2px 6px" }}>gap</span>
        )}
      </div>
      <p style={{ margin: "0.25rem 0", fontWeight: 600 }}>{card.front}</p>
      <p style={{ margin: 0, color: "#555", fontSize: 14 }}>{card.back}</p>
    </li>
  );
}
