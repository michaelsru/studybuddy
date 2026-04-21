import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail, QuizQuestion } from "../../types/session";

const SCORE_COLOR: Record<string, string> = {
  strong: "#22c55e",
  partial: "#f59e0b",
  missing: "#ef4444",
};

const SCORE_LABEL: Record<string, string> = {
  strong: "✓ Correct",
  partial: "~ Partial",
  missing: "✗ Incorrect",
};

const DIFF_COLOR: Record<string, string> = {
  easy: "#86efac",
  medium: "#fcd34d",
  hard: "#f87171",
};

function QuestionInput({
  q,
  value,
  onChange,
}: {
  q: QuizQuestion;
  value: string;
  onChange: (v: string) => void;
}) {
  if (q.question_type === "multiple_choice" && q.options) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.75rem" }}>
        {q.options.map((opt) => (
          <label
            key={opt}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.6rem",
              padding: "0.6rem 0.9rem",
              borderRadius: 8,
              border: `2px solid ${value === opt ? "#6366f1" : "#e2e8f0"}`,
              background: value === opt ? "#eef2ff" : "#fff",
              cursor: "pointer",
              fontSize: 14,
              transition: "all 0.15s",
            }}
          >
            <input
              type="radio"
              name={q.id}
              value={opt}
              checked={value === opt}
              onChange={() => onChange(opt)}
              style={{ accentColor: "#6366f1" }}
            />
            {opt}
          </label>
        ))}
      </div>
    );
  }

  if (q.question_type === "fill_blank" || q.question_type === "calculation") {
    return (
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={q.question_type === "calculation" ? "Enter your answer…" : "Fill in the blank…"}
        style={{
          width: "100%",
          padding: "0.6rem 0.75rem",
          fontSize: 14,
          fontFamily: q.question_type === "calculation" ? "monospace" : "inherit",
          borderRadius: 8,
          border: "1.5px solid #e2e8f0",
          marginTop: "0.75rem",
          boxSizing: "border-box",
        }}
      />
    );
  }

  // short_answer
  return (
    <textarea
      rows={4}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Write your answer here…"
      style={{
        width: "100%",
        padding: "0.6rem 0.75rem",
        fontSize: 14,
        borderRadius: 8,
        border: "1.5px solid #e2e8f0",
        marginTop: "0.75rem",
        resize: "vertical",
        boxSizing: "border-box",
      }}
    />
  );
}

function ReviewScreen({
  session,
  onAdvance,
}: {
  session: SessionDetail;
  onAdvance: (step: number) => void;
}) {
  const answerMap = Object.fromEntries(session.quiz_answers.map((a) => [a.question_id, a]));
  const scores = session.quiz_answers.map((a) => a.score);
  const total = scores.length;
  const strong = scores.filter((s) => s === "strong").length;
  const partial = scores.filter((s) => s === "partial").length;
  const missing = scores.filter((s) => s === "missing").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <h3 style={{ margin: 0 }}>Step 3 — Quiz Results</h3>

      {/* Summary bar */}
      <div style={{
        display: "flex",
        gap: "0.75rem",
        padding: "0.75rem 1rem",
        background: "#f8fafc",
        borderRadius: 10,
        flexWrap: "wrap",
      }}>
        <span style={{ color: SCORE_COLOR.strong, fontWeight: 600 }}>✓ {strong} correct</span>
        <span style={{ color: "#94a3b8" }}>·</span>
        <span style={{ color: SCORE_COLOR.partial, fontWeight: 600 }}>~ {partial} partial</span>
        <span style={{ color: "#94a3b8" }}>·</span>
        <span style={{ color: SCORE_COLOR.missing, fontWeight: 600 }}>✗ {missing} incorrect</span>
        <span style={{ color: "#94a3b8" }}>·</span>
        <span style={{ color: "#64748b" }}>{total} total</span>
      </div>

      {/* Per-question review */}
      {session.quiz_questions.map((q, i) => {
        const a = answerMap[q.id];
        return (
          <div
            key={q.id}
            style={{
              border: `1.5px solid ${a ? SCORE_COLOR[a.score] : "#e2e8f0"}22`,
              borderLeft: `4px solid ${a ? SCORE_COLOR[a.score] : "#e2e8f0"}`,
              borderRadius: 10,
              padding: "0.9rem 1rem",
              background: "#fafafa",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.4rem" }}>
              <span style={{ fontSize: 12, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Q{i + 1} · {q.question_type.replace("_", " ")} · {q.difficulty}
              </span>
              {a && (
                <span style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: SCORE_COLOR[a.score],
                  background: `${SCORE_COLOR[a.score]}18`,
                  borderRadius: 4,
                  padding: "2px 8px",
                }}>
                  {SCORE_LABEL[a.score]}
                </span>
              )}
            </div>

            <p style={{ margin: "0 0 0.4rem", fontWeight: 600, fontSize: 14 }}>{q.question_text}</p>

            {/* MCQ options */}
            {q.question_type === "multiple_choice" && q.options && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginBottom: "0.4rem" }}>
                {q.options.map((opt) => {
                  const isSelected = a?.answer_text === opt;
                  const isCorrect = a?.answer_key === opt;
                  return (
                    <div
                      key={opt}
                      style={{
                        fontSize: 13,
                        padding: "0.3rem 0.6rem",
                        borderRadius: 6,
                        background: isCorrect ? "#dcfce7" : isSelected && !isCorrect ? "#fee2e2" : "transparent",
                        color: isCorrect ? "#166534" : isSelected && !isCorrect ? "#991b1b" : "#64748b",
                      }}
                    >
                      {isCorrect ? "✓ " : isSelected && !isCorrect ? "✗ " : "  "}{opt}
                    </div>
                  );
                })}
              </div>
            )}

            {/* User answer (non-MCQ) */}
            {q.question_type !== "multiple_choice" && a && (
              <p style={{ fontSize: 13, color: "#475569", margin: "0 0 0.3rem" }}>
                <strong>Your answer:</strong> {a.answer_text || <em style={{ color: "#94a3b8" }}>no answer</em>}
              </p>
            )}

            {/* Feedback */}
            {a?.feedback && (
              <p style={{ fontSize: 13, color: "#64748b", margin: "0.25rem 0 0", fontStyle: "italic" }}>
                {a.feedback}
              </p>
            )}
          </div>
        );
      })}

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
        Continue to Gap Analysis →
      </button>
    </div>
  );
}

export default function Step3_Quiz({ session, onAdvance }: { session: SessionDetail; onAdvance: (step: number) => void }) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [currentIdx, setCurrentIdx] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const qc = useQueryClient();

  const submit = useMutation({
    mutationFn: () =>
      api.post<SessionDetail>(`/sessions/${session.id}/answers`, {
        answers: session.quiz_questions.map((q) => ({
          question_id: q.id,
          answer_text: answers[q.id] ?? "",
        })),
      }),
    onSuccess: (s) => {
      qc.setQueryData(["session", session.id], s);
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  // ── Review mode ───────────────────────────────────────────────────────────
  if (session.quiz_answers.length > 0) {
    return (
      <ReviewScreen
        session={session}
        onAdvance={onAdvance}
      />
    );
  }

  const qs = session.quiz_questions;
  const q = qs[currentIdx];
  if (!q) return null;

  const currentAnswer = answers[q.id] ?? "";
  const isLast = currentIdx === qs.length - 1;
  const canAdvance = currentAnswer.trim().length > 0;

  const handleNext = () => {
    if (!canAdvance) return;
    if (isLast) {
      submit.mutate();
    } else {
      setCurrentIdx((i) => i + 1);
    }
  };

  // ── Taking mode ───────────────────────────────────────────────────────────
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Step 3 — Quiz</h3>
        <span style={{ fontSize: 13, color: "#94a3b8" }}>Q{currentIdx + 1} of {qs.length}</span>
      </div>

      {/* Progress bar */}
      <div style={{ height: 4, background: "#e2e8f0", borderRadius: 2 }}>
        <div style={{
          height: "100%",
          width: `${((currentIdx + 1) / qs.length) * 100}%`,
          background: "#6366f1",
          borderRadius: 2,
          transition: "width 0.3s ease",
        }} />
      </div>

      {/* Question card */}
      <div style={{
        border: "1.5px solid #e2e8f0",
        borderRadius: 12,
        padding: "1.25rem",
        background: "#fafafa",
      }}>
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.6rem" }}>
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "#6366f1",
            background: "#eef2ff",
            borderRadius: 4,
            padding: "2px 7px",
          }}>
            {q.question_type.replace("_", " ")}
          </span>
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "#64748b",
            background: `${DIFF_COLOR[q.difficulty]}44`,
            borderRadius: 4,
            padding: "2px 7px",
          }}>
            {q.difficulty}
          </span>
        </div>

        <p style={{ margin: 0, fontWeight: 600, fontSize: 15, lineHeight: 1.5 }}>{q.question_text}</p>

        <QuestionInput
          q={q}
          value={currentAnswer}
          onChange={(v) => setAnswers((prev) => ({ ...prev, [q.id]: v }))}
        />
      </div>

      {/* Navigation */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button
          onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
          disabled={currentIdx === 0}
          style={{
            background: "transparent",
            border: "1.5px solid #e2e8f0",
            borderRadius: 8,
            padding: "0.5rem 1rem",
            fontSize: 13,
            cursor: currentIdx === 0 ? "not-allowed" : "pointer",
            color: currentIdx === 0 ? "#94a3b8" : "#475569",
          }}
        >
          ← Back
        </button>

        <button
          onClick={handleNext}
          disabled={!canAdvance || submit.isPending}
          style={{
            background: canAdvance ? (isLast ? "#22c55e" : "#6366f1") : "#e2e8f0",
            color: canAdvance ? "#fff" : "#94a3b8",
            border: "none",
            borderRadius: 8,
            padding: "0.5rem 1.25rem",
            fontSize: 14,
            fontWeight: 600,
            cursor: canAdvance ? "pointer" : "not-allowed",
            transition: "background 0.15s",
          }}
        >
          {submit.isPending ? "Marking…" : isLast ? "Submit & Mark →" : "Next →"}
        </button>
      </div>

      {/* Answer preview dots */}
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", justifyContent: "center" }}>
        {qs.map((qi, i) => (
          <button
            key={qi.id}
            onClick={() => setCurrentIdx(i)}
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: i === currentIdx ? "#6366f1" : (answers[qi.id] ?? "").trim() ? "#a5b4fc" : "#e2e8f0",
              border: "none",
              cursor: "pointer",
              padding: 0,
              transition: "background 0.15s",
            }}
          />
        ))}
      </div>
    </div>
  );
}
