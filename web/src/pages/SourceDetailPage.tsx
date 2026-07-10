import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { fetchSource, type PublicSource } from "../api/sources";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; source: PublicSource }
  | { kind: "missing" }
  | { kind: "error"; message: string };

export function SourceDetailPage() {
  const { id = "" } = useParams();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    if (!id) {
      setState({ kind: "missing" });
      return;
    }
    fetchSource(id)
      .then((source) => {
        if (!cancelled) {
          setState({ kind: "ok", source });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          if (error instanceof ApiError && error.status === 404) {
            setState({ kind: "missing" });
            return;
          }
          const message = error instanceof Error ? error.message : "Unknown error";
          setState({ kind: "error", message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (state.kind === "loading") {
    return (
      <div className="page">
        <p>Loading source…</p>
      </div>
    );
  }

  if (state.kind === "missing") {
    return (
      <div className="page">
        <h1 className="page__title">Source not found</h1>
        <p className="page__lede">No registry entry for this id.</p>
        <Link className="btn btn--ghost" to="/sources">
          Back to sources
        </Link>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="page">
        <h1 className="page__title">Source</h1>
        <p className="banner-error">Could not reach the API ({state.message}).</p>
        <Link className="btn btn--ghost" to="/sources">
          Back to sources
        </Link>
      </div>
    );
  }

  const { source } = state;
  return (
    <div className="page">
      <p className="source-detail__back">
        <Link to="/sources">← Sources</Link>
      </p>
      <h1 className="page__title">{source.name}</h1>
      <p className="page__lede">
        {source.category} · {source.jurisdiction}
        {source.region ? ` · ${source.region}` : ""}
      </p>
      <dl className="detail-panel__dl source-detail__dl">
        <div>
          <dt>URL</dt>
          <dd>
            <a href={source.url} rel="noreferrer" target="_blank">
              {source.url}
            </a>
          </dd>
        </div>
        <div>
          <dt>Format</dt>
          <dd>{source.format}</dd>
        </div>
        <div>
          <dt>Fetch method</dt>
          <dd>{source.fetch_method}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{source.status}</dd>
        </div>
        <div>
          <dt>Health</dt>
          <dd>{source.health_status}</dd>
        </div>
        <div>
          <dt>Expected cadence</dt>
          <dd>{source.expected_cadence == null ? "—" : `${source.expected_cadence} seconds`}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{new Date(source.updated_at).toLocaleString()}</dd>
        </div>
      </dl>
      <p className="placeholder">
        Archived document bytes and page-level provenance drill-down land with E10.6 / archive
        serving.
      </p>
      <Link className="btn btn--primary" to="/explore">
        Back to explore
      </Link>
    </div>
  );
}
