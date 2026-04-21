import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { SessionDetail } from "../types/session";
import SessionShell from "../components/SessionShell";

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();

  const { data: session, isPending, isError } = useQuery({
    queryKey: ["session", id],
    queryFn: () => api.get<SessionDetail>(`/sessions/${id}`),
    enabled: !!id,
    refetchOnWindowFocus: false,
  });

  if (isPending) return <p style={{ fontFamily: "sans-serif", padding: "2rem" }}>Loading…</p>;
  if (isError || !session) return <p style={{ fontFamily: "sans-serif", padding: "2rem" }}>Session not found.</p>;

  return <SessionShell session={session} />;
}
