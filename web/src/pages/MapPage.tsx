import { useState } from "react";
import { Link } from "react-router-dom";
import { NigeriaMap } from "../components/NigeriaMap";
import { listStateMetrics, type MapMetric, type StateMetric } from "../map/fixtures";

export function MapPage() {
  const [metric, setMetric] = useState<MapMetric>("contract_volume");
  const [selected, setSelected] = useState<StateMetric | null>(null);
  const count = listStateMetrics().length;

  return (
    <div className="page page--map">
      <h1 className="page__title">Map</h1>
      <p className="page__lede">
        3D extrusions by Nigerian state — contract volume or anomaly density. Live aggregates are
        not wired yet; this view uses a labelled demo fixture.
      </p>
      <p className="map-demo-banner" role="status">
        Illustrative demo — not live contract or anomaly totals ({count} jurisdictions).
      </p>

      <div className="map-controls">
        <label className="explore-field">
          <span>Metric</span>
          <select value={metric} onChange={(event) => setMetric(event.target.value as MapMetric)}>
            <option value="contract_volume">Contract volume</option>
            <option value="anomaly_density">Anomaly density</option>
          </select>
        </label>
      </div>

      <div className="map-layout">
        <section className="map-stage" aria-label="Nigeria state map">
          <NigeriaMap metric={metric} selectedId={selected?.id ?? null} onSelect={setSelected} />
        </section>
        <aside className="map-side">
          <h2 className="map-side__title">Detail</h2>
          {selected ? (
            <dl className="detail-panel__dl">
              <div>
                <dt>State</dt>
                <dd>
                  {selected.name} ({selected.id})
                </dd>
              </div>
              <div>
                <dt>Contract volume (demo)</dt>
                <dd>{selected.contract_volume}</dd>
              </div>
              <div>
                <dt>Anomaly density (demo)</dt>
                <dd>{selected.anomaly_density.toFixed(2)}</dd>
              </div>
            </dl>
          ) : (
            <p className="map-side__hint">Click a column to inspect a state.</p>
          )}
          <Link className="btn btn--ghost" to="/explore">
            Open explore
          </Link>
        </aside>
      </div>
    </div>
  );
}
