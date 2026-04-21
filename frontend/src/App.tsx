import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";

export default function App() {
  const { data, isError, isPending } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<{ status: string }>("/health"),
    retry: false,
  });

  const label = isPending
    ? "Checking backend…"
    : isError
    ? "Backend: unreachable"
    : `Backend: ${data?.status}`;

  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>Buddy</h1>
      <p>{label}</p>
    </div>
  );
}
