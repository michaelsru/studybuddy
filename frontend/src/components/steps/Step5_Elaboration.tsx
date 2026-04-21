import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail } from "../../types/session";

export default function Step5_Elaboration({ session }: { session: SessionDetail }) {
  const qc = useQueryClient();
  const gap = session.gap_analysis;

  const close = useMutation({
    mutationFn: () => api.post<SessionDetail>(`/sessions/${session.id}/elaboration/close`, {}),
    onSuccess: (s) => qc.setQueryData(["session", session.id], s),
  });

  return (
    <div>
      <h3>Step 5 — Elaboration</h3>

      {gap && (
        <div style={{ marginBottom: "1.5rem" }}>
          <p><strong>Strong:</strong> {gap.strong_areas.join(", ") || "—"}</p>
          <p><strong>Weak:</strong> {gap.weak_areas.join(", ") || "—"}</p>
          {gap.missing_areas.length > 0 && (
            <p><strong>Missing:</strong> {gap.missing_areas.join(", ")}</p>
          )}
        </div>
      )}

      <div style={{ background: "#f5f5f5", padding: "1rem", borderRadius: 8, marginBottom: "1rem" }}>
        {session.elaboration_turns.map((t) => (
          <div key={t.id} style={{ marginBottom: "0.75rem" }}>
            <strong>{t.role === "buddy" ? "Buddy" : "You"}:</strong> {t.content}
          </div>
        ))}
      </div>

      <p style={{ color: "#888", fontSize: 13 }}>
        WebSocket chat added in Phase 3. For now, click to continue.
      </p>

      <button onClick={() => close.mutate()} disabled={close.isPending}>
        {close.isPending ? "…" : "Move on →"}
      </button>
    </div>
  );
}
