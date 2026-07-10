import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { GraphCanvas } from "../components/GraphCanvas";
import { getDemoGraph } from "../graph/fixtures";
import { toForceGraphData, type ForceGraphNode } from "../graph/types";

export function GraphPage() {
  const doc = useMemo(() => getDemoGraph(), []);
  const data = useMemo(() => toForceGraphData(doc), [doc]);
  const [selected, setSelected] = useState<ForceGraphNode | null>(null);

  return (
    <div className="page page--graph">
      <h1 className="page__title">Graph</h1>
      <p className="page__lede">
        Relationship view of agencies, suppliers, tenders, awards, and contracts. Live Memgraph
        wiring lands after a public graph API — this canvas uses a labelled demo fixture.
      </p>
      {doc.demo ? (
        <p className="graph-demo-banner" role="status">
          Illustrative demo — not a live Memgraph projection.
        </p>
      ) : null}

      <div className="graph-layout">
        <section className="graph-stage" aria-label={doc.title}>
          <GraphCanvas data={data} selectedId={selected?.id ?? null} onSelect={setSelected} />
        </section>
        <aside className="graph-side">
          <h2 className="graph-side__title">Detail</h2>
          {selected ? (
            <dl className="detail-panel__dl">
              <div>
                <dt>Name</dt>
                <dd>{selected.name}</dd>
              </div>
              <div>
                <dt>Kind</dt>
                <dd>{selected.kind}</dd>
              </div>
              <div>
                <dt>Labels</dt>
                <dd>{selected.labels.join(", ")}</dd>
              </div>
              <div>
                <dt>Id</dt>
                <dd>
                  <code>{selected.id}</code>
                </dd>
              </div>
            </dl>
          ) : (
            <p className="graph-side__hint">Click a node to inspect labels and id.</p>
          )}
          <Link className="btn btn--ghost" to="/explore">
            Open explore
          </Link>
        </aside>
      </div>
    </div>
  );
}
