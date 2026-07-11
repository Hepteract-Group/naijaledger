import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchFacets, type PublicFacets } from "../api/facets";
import { fetchSources, type PublicSource } from "../api/sources";
import { FacetBar } from "../components/FacetBar";
import { geoYearFacetPatch, parseGeoYearFacets } from "../explore/facets";

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; sources: PublicSource[] }
  | { kind: "error"; message: string };

export function SourcesIndexPage() {
  const [params, setParams] = useSearchParams();
  const { state: facetState } = parseGeoYearFacets(params);
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [facets, setFacets] = useState<PublicFacets>({ states: [], years: [], lgas: [] });

  useEffect(() => {
    let cancelled = false;
    void fetchFacets()
      .then((data) => {
        if (!cancelled && Array.isArray(data.states)) {
          setFacets(data);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    fetchSources({ status: "approved", state: facetState || undefined, limit: 50 })
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
  }, [facetState]);

  const patchParams = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value == null || value === "") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
    }
    setParams(next, { replace: true });
  };

  return (
    <div className="page">
      <h1 className="page__title">Sources</h1>
      <p className="page__lede">
        Approved entries in the public source registry. Filter by state when region is set on the
        source.
      </p>

      <div className="explore-controls">
        <FacetBar
          state={facetState}
          lga=""
          year=""
          states={facets.states}
          years={[]}
          lgas={[]}
          showLga={false}
          showYear={false}
          onChange={(patch) => patchParams(geoYearFacetPatch(patch))}
        />
      </div>

      {state.kind === "loading" && <p>Loading sources…</p>}
      {state.kind === "error" && (
        <p className="banner-error">
          Could not reach the API ({state.message}). Start the engine with{" "}
          <code>make dev-engine</code>.
        </p>
      )}
      {state.kind === "ok" && state.sources.length === 0 && (
        <p className="placeholder">
          No approved sources match. Widen the state filter or register sources, then refresh.
        </p>
      )}
      {state.kind === "ok" && state.sources.length > 0 && (
        <ul className="source-list">
          {state.sources.map((source) => (
            <li key={source.id} className="source-list__item">
              <Link className="source-list__link" to={`/sources/${source.id}`}>
                <span className="source-list__name">{source.name}</span>
                <span className="source-list__meta">
                  {source.category} · {source.region ?? source.jurisdiction} ·{" "}
                  {source.health_status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
