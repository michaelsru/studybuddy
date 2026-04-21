import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail } from "../../types/session";

export default function Step6_Application({ session }: { session: SessionDetail }) {
  const [response, setResponse] = useState("");
  const qc = useQueryClient();

  const submit = useMutation({
    mutationFn: (skip: boolean) =>
      api.post<SessionDetail>(`/sessions/${session.id}/application`, {
        response: skip ? null : response || null,
      }),
    onSuccess: (s) => qc.setQueryData(["session", session.id], s),
  });

  const app = session.application;
  const challenge = app?.challenge_text ?? "No challenge generated yet.";

  // Review mode — user already submitted or skipped
  if (app && (app.user_response !== null || session.current_step > 6)) {
    return (
      <div>
        <h3>Step 6 — Application</h3>
        <div style={{ background: "#f5f5f5", padding: "1rem", borderRadius: 8, marginBottom: "1rem" }}>
          {challenge}
        </div>
        {app.user_response ? (
          <>
            <p><strong>Your response:</strong></p>
            <p style={{ color: "#444" }}>{app.user_response}</p>
            {app.buddy_feedback && (
              <>
                <p><strong>Feedback:</strong></p>
                <p style={{ color: "#555" }}>{app.buddy_feedback}</p>
              </>
            )}
          </>
        ) : (
          <p style={{ color: "#888" }}>Skipped.</p>
        )}
      </div>
    );
  }

  return (
    <div>
      <h3>Step 6 — Application</h3>
      <div style={{ background: "#f5f5f5", padding: "1rem", borderRadius: 8, marginBottom: "1rem" }}>
        {challenge}
      </div>
      <textarea
        rows={5}
        style={{ width: "100%", fontSize: 14, padding: "0.5rem" }}
        placeholder="Your response (optional)…"
        value={response}
        onChange={(e) => setResponse(e.target.value)}
      />
      <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.75rem" }}>
        <button onClick={() => submit.mutate(false)} disabled={submit.isPending}>
          Submit for Feedback
        </button>
        <button onClick={() => submit.mutate(true)} disabled={submit.isPending} style={{ background: "none", color: "#666" }}>
          Skip
        </button>
      </div>
    </div>
  );
}

