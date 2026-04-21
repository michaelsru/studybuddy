import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail } from "../../types/session";

const SCORE_COLOR: Record<string, string> = {
  strong: "#34d399",
  partial: "#fbbf24",
  missing: "#f87171",
};

export default function Step3_Quiz({ session }: { session: SessionDetail }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const qc = useQueryClient();

  const submit = useMutation({
    mutationFn: () =>
      api.post<SessionDetail>(`/sessions/${session.id}/answers`, {
        answers: session.quiz_questions.map((q) => ({
          question_id: q.id,
          answer_text: answers[q.id] ?? "",
        })),
      }),
    onSuccess: (s) => qc.setQueryData(["session", session.id], s),
  });

  // Review mode — answers already submitted
  if (session.quiz_answers.length > 0) {
    const answerMap = Object.fromEntries(session.quiz_answers.map((a) => [a.question_id, a]));
    return (
      <div>
        <h3>Step 3 — Recall Quiz</h3>
        {session.quiz_questions.map((q, i) => {
          const a = answerMap[q.id];
          return (
            <div key={q.id} style={{ marginBottom: "1.25rem" }}>
              <p style={{ fontWeight: 600 }}>Q{i + 1}. {q.question_text}</p>
              <p style={{ margin: "0.25rem 0" }}>{a?.answer_text ?? "—"}</p>
              {a && (
                <span style={{
                  fontSize: 12,
                  background: SCORE_COLOR[a.score],
                  color: "#fff",
                  borderRadius: 4,
                  padding: "2px 8px",
                }}>
                  {a.score}
                </span>
              )}
              {a?.feedback && <p style={{ color: "#666", fontSize: 13, marginTop: 4 }}>{a.feedback}</p>}
            </div>
          );
        })}
      </div>
    );
  }

  const allAnswered = session.quiz_questions.every((q) => (answers[q.id] ?? "").trim());

  return (
    <div>
      <h3>Step 3 — Recall Quiz</h3>
      {session.quiz_questions.map((q, i) => (
        <div key={q.id} style={{ marginBottom: "1.25rem" }}>
          <p style={{ fontWeight: 600 }}>Q{i + 1}. {q.question_text}</p>
          <textarea
            rows={3}
            style={{ width: "100%", fontSize: 14, padding: "0.5rem" }}
            value={answers[q.id] ?? ""}
            onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
          />
        </div>
      ))}
      <button onClick={() => submit.mutate()} disabled={!allAnswered || submit.isPending}>
        {submit.isPending ? "Submitting…" : "Submit Answers"}
      </button>
    </div>
  );
}

