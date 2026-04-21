import { useState } from "react";
import type { SessionDetail } from "../types/session";
import Step1_Topics from "./steps/Step1_Topics";
import Step2_Watch from "./steps/Step2_Watch";
import Step3_Quiz from "./steps/Step3_Quiz";
import Step4_GapAnalysis from "./steps/Step4_GapAnalysis";
import Step5_Elaboration from "./steps/Step5_Elaboration";
import Step6_Application from "./steps/Step6_Application";
import Step7_Cards from "./steps/Step7_Cards";

const STEP_LABELS: Record<number, string> = {
  1: "Topics",
  2: "Watch",
  3: "Recall",
  4: "Analysis",
  5: "Elaboration",
  6: "Application",
  7: "Cards",
};

interface Props {
  session: SessionDetail;
}

export default function SessionShell({ session }: Props) {
  const allSteps = [1, 2, 3, 4, 5, 6, 7];
  const active = new Set(session.active_steps);
  const [viewStep, setViewStep] = useState(session.current_step);

  // Only advance viewStep if it's still pointing at the current active step
  // (guards against session being refreshed while user reviews a past step)
  const onAdvance = (nextStep: number) => {
    setViewStep(nextStep);
  };

  return (
    <div style={{ maxWidth: 720, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h2 style={{ marginBottom: "0.25rem" }}>{session.title ?? "New Session"}</h2>

      {/* Progress bar */}
      <div style={{ display: "flex", gap: 4, marginBottom: "2rem" }}>
        {allSteps.map((step) => {
          const isActive = active.has(step);
          const isCurrent = session.current_step === step;
          const isDone = session.current_step > step;
          const isViewing = viewStep === step;
          const isClickable = isActive && (isDone || isCurrent);

          return (
            <div
              key={step}
              onClick={() => isClickable && setViewStep(step)}
              style={{
                flex: 1,
                padding: "0.35rem 0",
                textAlign: "center",
                fontSize: 12,
                borderRadius: 6,
                cursor: isClickable ? "pointer" : "default",
                outline: isViewing && !isCurrent ? "2px solid #6366f1" : "none",
                outlineOffset: 2,
                background: !isActive
                  ? "#f0f0f0"
                  : isDone
                  ? "#34d399"
                  : isCurrent
                  ? "#6366f1"
                  : "#e0e7ff",
                color: !isActive ? "#bbb" : isDone || isCurrent ? "#fff" : "#4338ca",
                fontWeight: isCurrent ? 700 : 400,
              }}
            >
              {STEP_LABELS[step]}
            </div>
          );
        })}
      </div>

      {/* Step view — driven by viewStep, not current_step */}
      <StepView session={session} step={viewStep} onAdvance={onAdvance} />
    </div>
  );
}

function StepView({
  session,
  step,
  onAdvance,
}: {
  session: SessionDetail;
  step: number;
  onAdvance: (step: number) => void;
}) {
  switch (step) {
    case 1: return <Step1_Topics session={session} onAdvance={onAdvance} />;
    case 2: return <Step2_Watch session={session} onAdvance={onAdvance} />;
    case 3: return <Step3_Quiz session={session} onAdvance={onAdvance} />;
    case 4: return <Step4_GapAnalysis session={session} onAdvance={onAdvance} />;
    case 5: return <Step5_Elaboration session={session} onAdvance={onAdvance} />;
    case 6: return <Step6_Application session={session} onAdvance={onAdvance} />;
    case 7: return <Step7_Cards session={session} />;
    default: return session.status === "completed"
      ? <p>Session complete. <a href="/">Back to sessions</a></p>
      : null;
  }
}
