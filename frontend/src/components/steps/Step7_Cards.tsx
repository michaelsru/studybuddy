import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { CardProposal, SessionDetail } from "../../types/session";

export default function Step7_Cards({ session }: { session: SessionDetail }) {
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const qc = useQueryClient();

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
      setApproved(new Set()); // clear selection after each commit
    },
  });

  const failedCards = session.card_proposals.filter(
    (c) => c.approved && !c.committed && !c.duplicate_warning
  );

  return (
    <div>
      <h3>Step 7 — Card Proposals</h3>

      {commit.isError && (
        <div style={{ background: "#fee2e2", color: "#991b1b", padding: "0.75rem 1rem", borderRadius: 8, marginBottom: "1rem" }}>
          {(commit.error as Error).message}
        </div>
      )}

      {failedCards.length > 0 && (
        <div style={{ background: "#fef3c7", color: "#92400e", padding: "0.75rem 1rem", borderRadius: 8, marginBottom: "1rem" }}>
          {failedCards.length} card{failedCards.length !== 1 ? "s" : ""} failed to write to Anki. Fix the error and retry.
        </div>
      )}

      {session.card_proposals.length === 0 ? (
        <p>No cards generated.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {session.card_proposals.map((c) => (
            <CardRow
              key={c.id}
              card={c}
              checked={approved.has(c.id)}
              onToggle={() => !c.committed && !c.duplicate_warning && toggle(c.id)}
            />
          ))}
        </ul>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginTop: "1rem" }}>
        <button onClick={() => commit.mutate()} disabled={commit.isPending || approved.size === 0}>
          {commit.isPending ? "Adding…" : `Add ${approved.size} Card${approved.size !== 1 ? "s" : ""} to Anki`}
        </button>
        <a href="/" style={{ color: "#888", fontSize: 13 }}>← Back to sessions</a>
      </div>
    </div>
  );
}

function CardRow({
  card,
  checked,
  onToggle,
}: {
  card: CardProposal;
  checked: boolean;
  onToggle: () => void;
}) {
  const failed = card.approved && !card.committed && !card.duplicate_warning;
  return (
    <li
      style={{
        border: `1px solid ${card.committed ? "#34d399" : card.duplicate_warning ? "#fbbf24" : failed ? "#f87171" : checked ? "#6366f1" : "#ddd"}`,
        borderRadius: 8,
        padding: "0.75rem 1rem",
        marginBottom: 8,
        cursor: card.committed || card.duplicate_warning ? "default" : "pointer",
        background: card.committed ? "#f0fdf4" : card.duplicate_warning ? "#fffbeb" : failed ? "#fef2f2" : checked ? "#eef2ff" : "#fff",
        opacity: card.committed || card.duplicate_warning ? 0.8 : 1,
      }}
      onClick={onToggle}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12, background: "#e0e7ff", color: "#4338ca", borderRadius: 4, padding: "2px 6px" }}>
          {card.card_type}
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          {card.committed && <span style={{ fontSize: 12, background: "#bbf7d0", color: "#166534", borderRadius: 4, padding: "2px 6px" }}>✓ added</span>}
          {card.duplicate_warning && <span style={{ fontSize: 12, background: "#fef3c7", color: "#92400e", borderRadius: 4, padding: "2px 6px" }}>duplicate</span>}
          {failed && <span style={{ fontSize: 12, background: "#fee2e2", color: "#991b1b", borderRadius: 4, padding: "2px 6px" }}>failed</span>}
          {card.is_gap_card && <span style={{ fontSize: 12, background: "#fef3c7", color: "#92400e", borderRadius: 4, padding: "2px 6px" }}>gap</span>}
        </div>
      </div>
      <p style={{ margin: "0.25rem 0", fontWeight: 600 }}>{card.front}</p>
      <p style={{ margin: 0, color: "#555", fontSize: 14 }}>{card.back}</p>
    </li>
  );
}

