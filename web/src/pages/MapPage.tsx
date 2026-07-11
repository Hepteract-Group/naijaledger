import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchMapStates } from "../api/map";
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

const DEMO_ROWS = listStateMetrics();
const KNOWN_STATES = DEMO_ROWS.map((row) => ({ code: row.id, name: row.name }));

type LoadState =
  | { kind: "loading" }
  | { kind: "live"; rows: StateMetric[] }
  | { kind: "demo"; rows: StateMetric[]; reason: string };

export function MapPage() {
  const [params, setParams] = useSearchParams();
  const { state: facetState, year: facetYear } = parseGeoYearFacets(params);
  const focusId = facetState.trim().toUpperCase() || null;
  const yearNum = facetYear ? Number(facetYear) : undefined;
  const [metric, setMetric] = useState<MapMetric>("contract_volume");
  const [selected, setSelected] = useState<StateMetric | null>(null);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setLoad({ kind: "loading" });
    void fetchMapStates({
      year: Number.isFinite(yearNum) ? yearNum : undefined,
    })
      .then((page) => {
        if (cancelled) {
          return;
        }
        const rows: StateMetric[] = page.items.map((item) => ({
          id: item.id,
          name: item.name,
          lat: item.lat,
          lng: item.lng,
          contract_volume: item.contract_volume,
          anomaly_density: item.anomaly_density,
          tender_count: item.tender_count,
          open_flag_count: item.open_flag_count,
          source: "live",
        }));
        setLoad({ kind: "live", rows });
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        const reason = error instanceof Error ? error.message : "API unavailable";
        setLoad({ kind: "demo", rows: DEMO_ROWS, reason });
      });
    return () => {
      cancelled = true;
    };
  }, [yearNum]);

  const allRows = load.kind === "loading" ? DEMO_ROWS : load.rows;
  const rows = useMemo(() => {
    if (!focusId) {
      return allRows;
    }
    return allRows.filter((row) => row.id === focusId);
  }, [allRows, focusId]);
  const leaders = useMemo(() => topStates(rows, metric, 5), [rows, metric]);
  const ceiling = useMemo(() => maxMetric(allRows, metric), [allRows, metric]);
  const rank =
    selected && rows.some((row) => row.id === selected.id)
      ? rankForMetric(rows, metric, selected.id)
      : null;
  useEffect(() => {
    if (!focusId) {
      return;
    }
    const match = allRows.find((row) => row.id === focusId) ?? null;
    setSelected(match);
  }, [focusId, allRows]);

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

  const onSelectColumn = (row: StateMetric | null) => {
    setSelected(row);
    if (row) {
      patchParams(geoYearFacetPatch({ state: row.id }));
    }
  };

  const banner =
    load.kind === "live"
      ? `Live from public API (${rows.length} ${rows.length === 1 ? "jurisdiction" : "jurisdictions"})`
      : load.kind === "demo"
        ? `Illustrative demo — not live totals (${load.reason})`
        : "Loading state aggregates…";

  return (
    <div className="page page--map">
      <header className="map-hero">
        <div className="map-hero__copy">
          <h1 className="page__title">Map</h1>
          <p className="page__lede">
            Compare Nigerian states by tender contract volume or open anomaly-flag density. Select a
            column or a name in the ranking to inspect.
          </p>
        </div>
        <p className="map-demo-banner" role="status">
          {banner}
        </p>
      </header>

      <div className="explore-controls">
        <FacetBar
          state={facetState}
          lga=""
          year={facetYear}
          states={KNOWN_STATES}
          years={[]}
          lgas={[]}
          showLga={false}
          showYear={true}
          onChange={(patch) => {
            patchParams(geoYearFacetPatch(patch));
            if (!patch.state) {
              setSelected(null);
            }
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
          Height and colour encode <strong>{metricLabel(metric).toLowerCase()}</strong>
          {load.kind === "live" ? " (tender value / open-flag density)" : " (demo scale)"}
          {focusId ? " · map focused on selected state" : ""}.
        </p>
      </div>

      <div className="map-layout">
        <section className="map-stage" aria-label="Nigeria state map">
          <NigeriaMap
            metric={metric}
            data={allRows}
            selectedId={selected?.id ?? null}
            focusId={focusId}
            onSelect={onSelectColumn}
          />
          <div className="map-legend" aria-hidden="true">
            <span className="map-legend__label">Low</span>
            <span className={`map-legend__ramp map-legend__ramp--${metric}`} />
            <span className="map-legend__label">
              High · max{" "}
              {metric === "contract_volume"
                ? load.kind === "live"
                  ? `₦${(ceiling / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                  : String(ceiling)
                : ceiling.toFixed(2)}
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
                <p className="map-fact__label">
                  {metricLabel(metric)}
                  {selected.source === "live" ? "" : " (demo)"}
                </p>
                {rank !== null ? (
                  <p className="map-fact__rank">
                    Rank {rank} of {rows.length}
                  </p>
                ) : null}
                <dl className="map-fact__secondary">
                  <div>
                    <dt>Contract volume</dt>
                    <dd>{formatMetricValue(selected, "contract_volume")}</dd>
                  </div>
                  <div>
                    <dt>Anomaly density</dt>
                    <dd>{selected.anomaly_density.toFixed(2)}</dd>
                  </div>
                  {selected.tender_count != null ? (
                    <div>
                      <dt>Tenders</dt>
                      <dd>{selected.tender_count}</dd>
                    </div>
                  ) : null}
                  {selected.open_flag_count != null ? (
                    <div>
                      <dt>Open flags</dt>
                      <dd>{selected.open_flag_count} (hypotheses)</dd>
                    </div>
                  ) : null}
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
                    onClick={() => onSelectColumn(row)}
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
                href: focusId ? `/sources?state=${focusId}` : "/sources",
                kind: "registry",
                note: "Drill to catalogued sources",
              }}
            />
            <Link
              className="btn btn--ghost"
              to={focusId ? `/explore?resource=tenders&state=${focusId}` : "/explore"}
            >
              Open explore
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
