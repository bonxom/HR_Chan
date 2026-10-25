import { useHealth } from "@/shared/hooks/queries/useHealth";

export function HomePage() {
  const health = useHealth();
  return <section>
    <p className="eyebrow">Your hiring workspace</p>
    <h1>Build your next great team.</h1>
    <p>The foundation for candidates, jobs, applications, and AI-assisted recommendations.</p>
    <p role="status">{health.isPending ? "Connecting to API…" : health.isError ? "API unavailable. Check that the backend is running." : `API status: ${health.data.status}`}</p>
    {health.isError && <button onClick={() => void health.refetch()}>Retry connection</button>}
    <p>Business workflows are coming next.</p>
  </section>;
}
