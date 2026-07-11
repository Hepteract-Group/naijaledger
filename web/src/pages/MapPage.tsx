import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CitedSource } from "../components/CitedSource";
import { FacetBar } from "../components/FacetBar";
import { NigeriaMap } from "../components/NigeriaMap";
import { geoYearFacetPatch, parseGeoYearFacets } from "../explore/facets";
import {
  formatMetricValue,
  listStateMetrics,
  maxMetric,
  metricLabel,
  rankForMetric,
  topStates,
  type MapMetric,
  type StateMetric,
} from "../map/fixtures";

const KNOWN_STATES = listStateMetrics().map((row) => ({ code: row.id, name: row.name }));

export function MapPage() {
  const [params, setParams] = useSearchParams();
  const { state: facetState } = parseGeoYearFacets(params);
  const [metric, setMetric] = useState<MapMetric>("contract_volume");
  const [selected, setSelected] = useState<StateMetric | null>(null);
  const rows = useMemo(() => {
    const all = listStateMetrics();
    if (!facetState) {
      return all;
    }
    return all.filter((row) => row.id === facetState.toUpperCase());
  }, [facetState]);
  const leaders = useMemo(() => topStates(rows, metric, 5), [rows, metric]);
  const ceiling = useMemo(() => maxMetric(rows, metric), [rows, metric]);
  const rank =
    selected && rows.some((row) => row.id === selected.id)
      ? rankForMetric(rows, metric, selected.id)
      : null;

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
    <div className="page page--map">
      <header className="map-hero">
        <div className="map-hero__copy">
          <h1 className="page__title">Map</h1>
          <p className="page__lede">
            Compare Nigerian states by contract volume or anomaly density. Select a column or a name
            in the ranking to inspect.
          </p>
        </div>
        <p className="map-demo-banner" role="status">
          Illustrative demo — not live totals ({rows.length} jurisdictions)
        </p>
      </header>

      <div className="explore-controls">
        <FacetBar
          state={facetState}
          lga=""
          year=""
          states={KNOWN_STATES}
          years={[]}
          lgas={[]}
          showLga={false}
          showYear={false}
          onChange={(patch) => {
            patchParams(geoYearFacetPatch(patch));
            setSelected(null);
          }}
        />
      </div>

      <div className="map-toolbar" role="toolbar" aria-label="Map metrics">
        <div className="map-metric-toggle" role="group" aria-label="Metric">
          {(
            [
              ["contract_volume", "Contract volume"],
              ["anomaly_density", "Anomaly density"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={`map-metric-toggle__btn${metric === value ? " is-active" : ""}`}
              aria-pressed={metric === value}
              onClick={() => setMetric(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="map-toolbar__hint">
          Height and colour encode <strong>{metricLabel(metric).toLowerCase()}</strong> (demo
          scale).
        </p>
      </div>

      <div className="map-layout">
        <section className="map-stage" aria-label="Nigeria state map">
          <NigeriaMap metric={metric} selectedId={selected?.id ?? null} onSelect={setSelected} />
          <div className="map-legend" aria-hidden="true">
            <span className="map-legend__label">Low</span>
            <span className={`map-legend__ramp map-legend__ramp--${metric}`} />
            <span className="map-legend__label">
              High · max {metric === "contract_volume" ? String(ceiling) : ceiling.toFixed(2)}
            </span>
          </div>
        </section>

        <aside className="map-side">
          <section className="map-panel">
            <h2 className="map-side__title">Selected</h2>
            {selected ? (
              <div className="map-fact">
                <p className="map-fact__place">
                  {selected.name}
                  <span className="map-fact__code">{selected.id}</span>
                </p>
                <p className="map-fact__value">{formatMetricValue(selected, metric)}</p>
                <p className="map-fact__label">{metricLabel(metric)} (demo)</p>
                {rank !== null ? (
                  <p className="map-fact__rank">
                    Rank {rank} of {rows.length}
                  </p>
                ) : null}
                <dl className="map-fact__secondary">
                  <div>
                    <dt>Contract volume</dt>
                    <dd>{selected.contract_volume}</dd>
                  </div>
                  <div>
                    <dt>Anomaly density</dt>
                    <dd>{selected.anomaly_density.toFixed(2)}</dd>
                  </div>
                </dl>
                <Link
                  className="btn btn--ghost"
                  to={`/explore?resource=tenders&state=${selected.id}`}
                >
                  Explore tenders in {selected.name}
                </Link>
              </div>
            ) : (
              <p className="map-side__hint">
                Hover a column for a quick read, or click to pin detail here.
              </p>
            )}
          </section>

          <section className="map-panel">
            <h2 className="map-side__title">Top {leaders.length}</h2>
            <ol className="map-rank">
              {leaders.map((row, index) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className={`map-rank__btn${selected?.id === row.id ? " is-active" : ""}`}
                    onClick={() => setSelected(row)}
                  >
                    <span className="map-rank__n">{index + 1}</span>
                    <span className="map-rank__name">{row.name}</span>
                    <span className="map-rank__val">{formatMetricValue(row, metric)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </section>

          <div className="map-side__actions">
            <CitedSource
              citation={{
                id: "map-sources",
                label: "Source registry",
                href: facetState ? `/sources?state=${facetState}` : "/sources",
                kind: "registry",
                note: "Drill to catalogued sources",
              }}
            />
            <Link
              className="btn btn--ghost"
              to={facetState ? `/explore?resource=tenders&state=${facetState}` : "/explore"}
            >
              Open explore
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
