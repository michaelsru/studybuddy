import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail } from "../../types/session";

export default function Step6_Application({
  session,
  onAdvance,
}: {
  session: SessionDetail;
  onAdvance: (step: number) => void;
}) {
  const [response, setResponse] = useState("");
  const qc = useQueryClient();

  const submit = useMutation({
    mutationFn: (skip: boolean) =>
      api.post<SessionDetail>(`/sessions/${session.id}/application`, {
        response: skip ? null : response || null,
      }),
    onSuccess: (s) => {
      qc.setQueryData(["session", session.id], s);
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  const app = session.application;
  const challenge = app?.challenge_text ?? "No challenge generated yet.";

  // Review mode — feedback received, waiting for user to continue
  if (app && (app.user_response !== null || app.buddy_feedback !== null)) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h3 style={{ margin: 0 }}>Step 6 — Application</h3>

        <div style={{ background: "#f8fafc", borderRadius: 10, padding: "1rem", border: "1.5px solid #e2e8f0" }}>
          <p style={{ margin: "0 0 0.4rem", fontWeight: 600, fontSize: 13, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.05em" }}>Challenge</p>
          <p style={{ margin: 0, fontSize: 15 }}>{challenge}</p>
        </div>

        {app.user_response ? (
          <>
            <div style={{ background: "#f0fdf4", borderRadius: 10, padding: "1rem", border: "1.5px solid #bbf7d0" }}>
              <p style={{ margin: "0 0 0.4rem", fontWeight: 600, fontSize: 13, color: "#16a34a", textTransform: "uppercase", letterSpacing: "0.05em" }}>Your Response</p>
              <p style={{ margin: 0, fontSize: 14, color: "#374151" }}>{app.user_response}</p>
            </div>

            {app.buddy_feedback && (
              <div style={{ background: "#eef2ff", borderRadius: 10, padding: "1rem", border: "1.5px solid #c7d2fe" }}>
                <p style={{ margin: "0 0 0.4rem", fontWeight: 600, fontSize: 13, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.05em" }}>Buddy's Feedback</p>
                <p style={{ margin: 0, fontSize: 14, color: "#374151", lineHeight: 1.6 }}>{app.buddy_feedback}</p>
              </div>
            )}
          </>
        ) : (
          <p style={{ color: "#94a3b8", fontStyle: "italic" }}>Skipped.</p>
        )}

        <button
          onClick={() => onAdvance(session.current_step)}
          style={{
            alignSelf: "flex-end",
            background: "#6366f1",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            padding: "0.6rem 1.4rem",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Continue to Cards →
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <h3 style={{ margin: 0 }}>Step 6 — Application</h3>

      <div style={{ background: "#f8fafc", borderRadius: 10, padding: "1rem", border: "1.5px solid #e2e8f0" }}>
        <p style={{ margin: "0 0 0.4rem", fontWeight: 600, fontSize: 13, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.05em" }}>Challenge</p>
        <p style={{ margin: 0, fontSize: 15 }}>{challenge}</p>
      </div>

      <textarea
        rows={5}
        style={{ width: "100%", fontSize: 14, padding: "0.75rem", borderRadius: 8, border: "1.5px solid #e2e8f0", boxSizing: "border-box", resize: "vertical" }}
        placeholder="Your response (optional)…"
        value={response}
        onChange={(e) => setResponse(e.target.value)}
      />

      <div style={{ display: "flex", gap: "0.75rem" }}>
        <button
          onClick={() => submit.mutate(false)}
          disabled={submit.isPending || !response.trim()}
          style={{ background: "#6366f1", color: "#fff", border: "none", borderRadius: 8, padding: "0.6rem 1.2rem", fontSize: 14, fontWeight: 600, cursor: response.trim() ? "pointer" : "not-allowed" }}
        >
          {submit.isPending ? "Getting feedback…" : "Submit for Feedback"}
        </button>
        <button
          onClick={() => submit.mutate(true)}
          disabled={submit.isPending}
          style={{ background: "transparent", color: "#94a3b8", border: "1.5px solid #e2e8f0", borderRadius: 8, padding: "0.6rem 1rem", fontSize: 14, cursor: "pointer" }}
        >
          Skip
        </button>
      </div>
    </div>
  );
}
