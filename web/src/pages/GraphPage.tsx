import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CitedSource } from "../components/CitedSource";
import { FacetBar } from "../components/FacetBar";
import { GraphCanvas } from "../components/GraphCanvas";
import { geoYearFacetPatch, parseGeoYearFacets } from "../explore/facets";
import { getDemoGraph } from "../graph/fixtures";
import { toForceGraphData, type ForceGraphNode, type GraphNodeKind } from "../graph/types";
import { listStateMetrics } from "../map/fixtures";

const KNOWN_STATES = listStateMetrics().map((row) => ({ code: row.id, name: row.name }));

const KIND_OPTIONS: { kind: GraphNodeKind; label: string }[] = [
  { kind: "party", label: "Parties" },
  { kind: "tender", label: "Tenders" },
  { kind: "award", label: "Awards" },
  { kind: "contract", label: "Contracts" },
];

const KIND_BLURB: Record<GraphNodeKind, string> = {
  party: "Agency or company in the procurement graph",
  tender: "Published contracting process",
  award: "Award decision linked to a supplier",
  contract: "Signed contract record",
};

export function GraphPage() {
  const [params, setParams] = useSearchParams();
  const { state: facetState } = parseGeoYearFacets(params);
  const doc = useMemo(() => getDemoGraph(), []);
  const data = useMemo(() => toForceGraphData(doc), [doc]);
  const [selected, setSelected] = useState<ForceGraphNode | null>(null);
  const [query, setQuery] = useState("");
  const [enabledKinds, setEnabledKinds] = useState<GraphNodeKind[]>([
    "party",
    "tender",
    "award",
    "contract",
  ]);

  const focusKinds = useMemo(() => new Set(enabledKinds), [enabledKinds]);
  const stateName = KNOWN_STATES.find((row) => row.code === facetState.toUpperCase())?.name ?? "";

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

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return [];
    }
    return data.nodes
      .filter(
        (node) =>
          focusKinds.has(node.kind) &&
          (node.name.toLowerCase().includes(q) || node.id.toLowerCase().includes(q)),
      )
      .slice(0, 6);
  }, [data.nodes, focusKinds, query]);

  const related = useMemo(() => {
    if (!selected) {
      return [];
    }
    const ids = new Set<string>();
    // Use document links (string ids) — force-graph mutates runtime link endpoints into objects.
    for (const link of doc.links) {
      if (link.source === selected.id) {
        ids.add(link.target);
      }
      if (link.target === selected.id) {
        ids.add(link.source);
      }
    }
    return data.nodes.filter((node) => ids.has(node.id));
  }, [data.nodes, doc.links, selected]);

  const toggleKind = (kind: GraphNodeKind) => {
    setEnabledKinds((prev) => {
      if (prev.includes(kind)) {
        if (prev.length === 1) {
          return prev;
        }
        return prev.filter((item) => item !== kind);
      }
      return [...prev, kind];
    });
  };

  return (
    <div className="page page--graph">
      <header className="graph-hero">
        <div className="graph-hero__copy">
          <h1 className="page__title">Graph</h1>
          <p className="page__lede">
            Follow how agencies, suppliers, tenders, awards, and contracts connect. Filter by type
            or search a name — click a node for a short briefing.
          </p>
        </div>
        {doc.demo ? (
          <p className="graph-demo-banner" role="status">
            Illustrative demo — not a live Memgraph projection
          </p>
        ) : null}
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
            if (patch.state) {
              const name =
                KNOWN_STATES.find((row) => row.code === patch.state?.toUpperCase())?.name ?? "";
              if (name) {
                setQuery(name);
              }
            }
          }}
        />
      </div>

      {facetState ? (
        <p className="explore-hint">
          Shared state facet with Explore/Map. Live graph geo filter lands with #141
          {stateName ? ` — search seeded with ${stateName}` : ""}.{" "}
          <Link to={`/explore?resource=tenders&state=${facetState}`}>Open Explore</Link>
        </p>
      ) : null}

      <div className="graph-toolbar">
        <label className="graph-search">
          <span className="sr-only">Search nodes</span>
          <input
            type="search"
            value={query}
            placeholder="Search parties, tenders…"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="graph-kind-filters" role="group" aria-label="Show node types">
          {KIND_OPTIONS.map(({ kind, label }) => (
            <button
              key={kind}
              type="button"
              className={`graph-kind-chip graph-kind-chip--${kind}${
                enabledKinds.includes(kind) ? " is-active" : ""
              }`}
              aria-pressed={enabledKinds.includes(kind)}
              onClick={() => toggleKind(kind)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {matches.length > 0 ? (
        <ul className="graph-search-hits" aria-label="Search results">
          {matches.map((node) => (
            <li key={node.id}>
              <button type="button" onClick={() => setSelected(node)}>
                <span className={`graph-kind-dot graph-kind-dot--${node.kind}`} />
                {node.name}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="graph-layout">
        <section className="graph-stage" aria-label={doc.title}>
          <GraphCanvas
            data={data}
            selectedId={selected?.id ?? null}
            focusKinds={focusKinds}
            onSelect={setSelected}
          />
          <ul className="graph-legend" aria-label="Node legend">
            {KIND_OPTIONS.map(({ kind, label }) => (
              <li key={kind}>
                <span className={`graph-kind-dot graph-kind-dot--${kind}`} />
                {label}
              </li>
            ))}
          </ul>
        </section>

        <aside className="graph-side">
          <section className="graph-panel">
            <h2 className="graph-side__title">Selected</h2>
            {selected ? (
              <div className="graph-fact">
                <p className={`graph-fact__kind graph-fact__kind--${selected.kind}`}>
                  {selected.kind}
                </p>
                <p className="graph-fact__name">{selected.name}</p>
                <p className="graph-fact__blurb">{KIND_BLURB[selected.kind]}</p>
                {related.length > 0 ? (
                  <div className="graph-fact__related">
                    <p className="graph-side__title">Connected</p>
                    <ul>
                      {related.map((node) => (
                        <li key={node.id}>
                          <button type="button" onClick={() => setSelected(node)}>
                            <span className={`graph-kind-dot graph-kind-dot--${node.kind}`} />
                            {node.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="graph-side__hint">
                Pick a node on the canvas, or use search, to see what it connects to.
              </p>
            )}
          </section>

          <div className="graph-side__actions">
            <CitedSource
              citation={{
                id: "graph-sources",
                label: "Source registry",
                href: facetState ? `/sources?state=${facetState}` : "/sources",
                kind: "registry",
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
