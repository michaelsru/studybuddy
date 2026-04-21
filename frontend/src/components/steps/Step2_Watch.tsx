import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail } from "../../types/session";

export default function Step2_Watch({ session }: { session: SessionDetail }) {
  const qc = useQueryClient();

  const watched = useMutation({
    mutationFn: () => api.post<SessionDetail>(`/sessions/${session.id}/watched`, {}),
    onSuccess: (s) => qc.setQueryData(["session", session.id], s),
  });

  return (
    <div>
      <h3>Step 2 — Watch</h3>
      <p>Keep these questions in mind while you watch:</p>
      <ol>
        {session.priming_questions.map((q, i) => <li key={i}>{q}</li>)}
      </ol>
      <button onClick={() => watched.mutate()} disabled={watched.isPending}>
        {watched.isPending ? "…" : "I've finished watching →"}
      </button>
    </div>
  );
}
