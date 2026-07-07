import { useEffect, useState } from "react";
import { fetchEngineHealth, type EngineHealth } from "./api/health";

type LoadState =
  { kind: "loading" } | { kind: "ok"; health: EngineHealth } | { kind: "error"; message: string };

const initialState: LoadState = { kind: "loading" };

export function App() {
  const [state, setState] = useState<LoadState>(initialState);

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
    <main className="shell">
      <header>
        <p className="eyebrow">NaijaLedger</p>
        <h1>Civic accountability, source-backed</h1>
        <p className="lede">
          Preservation-first public finance and election verification for Nigeria.
        </p>
      </header>

      <section className="panel" aria-live="polite">
        <h2>Engine health</h2>
        {state.kind === "loading" && <p>Checking API…</p>}
        {state.kind === "error" && (
          <p className="status error">
            Engine unreachable: {state.message}. Run <code>make dev-engine</code> in another
            terminal.
          </p>
        )}
        {state.kind === "ok" && (
          <dl className="health">
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
      </section>
    </main>
  );
}
