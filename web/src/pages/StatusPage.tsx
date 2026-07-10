import { useEffect, useState } from "react";
import { fetchEngineHealth, type EngineHealth } from "../api/health";

type LoadState =
  { kind: "loading" } | { kind: "ok"; health: EngineHealth } | { kind: "error"; message: string };

export function StatusPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchEngineHealth()
      .then((health) => {
        if (!cancelled) {
          setState({ kind: "ok", health });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unknown error";
          setState({ kind: "error", message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page">
      <h1 className="page__title">Engine status</h1>
      <p className="page__lede">Live check against the NaijaLedger API health endpoint.</p>
      {state.kind === "loading" && <p>Checking API…</p>}
      {state.kind === "error" && (
        <p className="banner-error">
          Engine unreachable: {state.message}. Run <code>make dev-engine</code>.
        </p>
      )}
      {state.kind === "ok" && (
        <dl className="status-grid">
          <div>
            <dt>Status</dt>
            <dd>{state.health.status}</dd>
          </div>
          <div>
            <dt>Service</dt>
            <dd>{state.health.service}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{state.health.version}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}
