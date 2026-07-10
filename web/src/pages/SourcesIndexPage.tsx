import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSources, type PublicSource } from "../api/sources";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; sources: PublicSource[] }
  | { kind: "error"; message: string };

export function SourcesIndexPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchSources({ status: "approved", limit: 50 })
      .then((page) => {
        if (!cancelled) {
          setState({ kind: "ok", sources: page.items });
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
      <h1 className="page__title">Sources</h1>
      <p className="page__lede">
        Approved entries in the public source registry. Archive document bytes arrive in a later
        story — this is the catalog drill-down.
      </p>
      {state.kind === "loading" && <p>Loading sources…</p>}
      {state.kind === "error" && (
        <p className="banner-error">
          Could not reach the API ({state.message}). Start the engine with{" "}
          <code>make dev-engine</code>.
        </p>
      )}
      {state.kind === "ok" && state.sources.length === 0 && (
        <p className="placeholder">
          No approved sources yet. Register and approve sources, then refresh.
        </p>
      )}
      {state.kind === "ok" && state.sources.length > 0 && (
        <ul className="source-list">
          {state.sources.map((source) => (
            <li key={source.id} className="source-list__item">
              <Link className="source-list__link" to={`/sources/${source.id}`}>
                <span className="source-list__name">{source.name}</span>
                <span className="source-list__meta">
                  {source.category} · {source.jurisdiction} · {source.health_status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
