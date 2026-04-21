import type { SessionDetail } from "../../types/session";

const SCORE_COLOR = { strong: "#22c55e", partial: "#f59e0b", missing: "#ef4444" };

export default function Step4_GapAnalysis({
  session,
  onAdvance,
}: {
  session: SessionDetail;
  onAdvance: (step: number) => void;
}) {
  const gap = session.gap_analysis;

  // Transient state — backend is still processing (shouldn't normally render)
  if (!gap) {
    return (
      <div style={{ textAlign: "center", padding: "3rem" }}>
        <p style={{ fontSize: 18 }}>Analysing gaps…</p>
      </div>
    );
  }

  const Section = ({
    title,
    items,
    color,
  }: {
    title: string;
    items: string[];
    color: string;
  }) =>
    items.length === 0 ? null : (
      <div style={{ marginBottom: "1rem" }}>
        <p style={{ fontWeight: 700, color, margin: "0 0 0.4rem" }}>{title}</p>
        <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
          {items.map((item, i) => (
            <li key={i} style={{ fontSize: 14, color: "#374151", marginBottom: "0.2rem" }}>
              {item}
            </li>
          ))}
        </ul>
      </div>
    );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <h3 style={{ margin: 0 }}>Step 4 — Gap Analysis</h3>

      <div
        style={{
          border: "1.5px solid #e2e8f0",
          borderRadius: 12,
          padding: "1.25rem",
          background: "#fafafa",
        }}
      >
        <Section title="✓ Strong areas" items={gap.strong_areas} color={SCORE_COLOR.strong} />
        <Section title="~ Needs work" items={gap.weak_areas} color={SCORE_COLOR.partial} />
        <Section title="✗ Missing areas" items={gap.missing_areas} color={SCORE_COLOR.missing} />
        {gap.strong_areas.length === 0 &&
          gap.weak_areas.length === 0 &&
          gap.missing_areas.length === 0 && (
            <p style={{ color: "#94a3b8", fontSize: 14 }}>No gap data available.</p>
          )}
      </div>

      <button
        onClick={() => onAdvance(session.current_step)}
        style={{
          alignSelf: "flex-end",
          background: "#6366f1",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          padding: "0.5rem 1.2rem",
          fontSize: 14,
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        Continue to Elaboration →
      </button>
    </div>
  );
}
