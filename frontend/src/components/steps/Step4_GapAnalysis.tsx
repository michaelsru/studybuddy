import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { SessionDetail } from "../../types/session";

// Step 4 is transient — backend has already advanced to step 5 by the time
// POST /answers returns. This view only renders if the client receives a
// step=4 response (e.g. mid-flight on a slow connection). It polls once
// to catch up automatically.
export default function Step4_GapAnalysis({ session }: { session: SessionDetail }) {
  const qc = useQueryClient();

  useEffect(() => {
    const t = setTimeout(async () => {
      const updated = await api.get<SessionDetail>(`/sessions/${session.id}`);
      qc.setQueryData(["session", session.id], updated);
    }, 800);
    return () => clearTimeout(t);
  }, [session.id, qc]);

  return (
    <div style={{ textAlign: "center", padding: "3rem" }}>
      <p style={{ fontSize: 18 }}>Analysing gaps…</p>
    </div>
  );
}
