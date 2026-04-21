import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail } from "../../types/session";

export default function Step1_Topics({ session }: { session: SessionDetail }) {
  const [text, setText] = useState("");
  const qc = useQueryClient();

  const submit = useMutation({
    mutationFn: () =>
      api.post<SessionDetail>(`/sessions/${session.id}/topics`, {
        topics: text.split("\n").map((t) => t.trim()).filter(Boolean),
      }),
    onSuccess: (s) => qc.setQueryData(["session", session.id], s),
  });

  // Review mode — topics already submitted
  if (session.topics.length > 0) {
    return (
      <div>
        <h3>Step 1 — Topics</h3>
        <p><strong>Topics submitted:</strong></p>
        <ul>{session.topics.map((t, i) => <li key={i}>{t}</li>)}</ul>
        {session.priming_questions.length > 0 && (
          <>
            <p><strong>Priming questions:</strong></p>
            <ol>{session.priming_questions.map((q, i) => <li key={i}>{q}</li>)}</ol>
          </>
        )}
      </div>
    );
  }

  return (
    <div>
      <h3>Step 1 — Topics</h3>
      <p>Paste your topic list (one per line).</p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={8}
        style={{ width: "100%", fontSize: 14, padding: "0.5rem" }}
        placeholder={"TCP/IP basics\nSubnetting\nARP protocol"}
      />
      <button
        onClick={() => submit.mutate()}
        disabled={!text.trim() || submit.isPending}
        style={{ marginTop: "0.75rem" }}
      >
        {submit.isPending ? "Generating…" : "Generate Priming Questions"}
      </button>
    </div>
  );
}

