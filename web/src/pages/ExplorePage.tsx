import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchFlags, type PublicFlag } from "../api/flags";
import { fetchParties, type PublicParty } from "../api/parties";
import { fetchTenders, type PublicTender } from "../api/tenders";
import { DistributionChart } from "../components/DistributionChart";
import {
  countBy,
  filterByText,
  sortBy,
  toggleCompareSelection,
  type ExploreResource,
  type SortDir,
} from "../explore/helpers";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; parties: PublicParty[]; tenders: PublicTender[]; flags: PublicFlag[] };

type Detail =
  | { resource: "parties"; row: PublicParty }
  | { resource: "tenders"; row: PublicTender }
  | { resource: "flags"; row: PublicFlag };

function parseResource(value: string | null): ExploreResource {
  if (value === "tenders" || value === "flags" || value === "parties") {
    return value;
  }
  return "parties";
}

function formatAmount(amount: number | null, currency: string): string {
  if (amount == null) {
    return "—";
  }
  return `${amount.toLocaleString()} ${currency}`;
}

export function ExplorePage() {
  const [params, setParams] = useSearchParams();
  const resource = parseResource(params.get("resource"));
  const q = params.get("q") ?? "";
  const partyType = params.get("party_type") ?? "";
  const sortKey = params.get("sort") ?? "name";
  const sortDir = (params.get("dir") === "desc" ? "desc" : "asc") as SortDir;

  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [selected, setSelected] = useState<string[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);

  // Parties: server filter on type/q. Tenders/flags: refetch only when resource changes.
  const partyQuery = resource === "parties" ? `${partyType}|${q}` : "";

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    setSelected([]);
    setDetail(null);

    const load = async () => {
      try {
        if (resource === "parties") {
          const page = await fetchParties({
            party_type: partyType || undefined,
            q: q || undefined,
            limit: 50,
          });
          if (!cancelled) {
            setState({ kind: "ok", parties: page.items, tenders: [], flags: [] });
          }
          return;
        }
        if (resource === "tenders") {
          const page = await fetchTenders(50);
          if (!cancelled) {
            setState({ kind: "ok", parties: [], tenders: page.items, flags: [] });
          }
          return;
        }
        const page = await fetchFlags(50);
        if (!cancelled) {
          setState({ kind: "ok", parties: [], tenders: [], flags: page.items });
        }
      } catch (error: unknown) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unknown error";
          setState({ kind: "error", message });
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
    // partyQuery encodes partyType+q only while resource === "parties"
  }, [resource, partyQuery, partyType, q]);

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

  const parties = useMemo(() => {
    if (state.kind !== "ok") {
      return [];
    }
    return sortBy(state.parties, sortDir, (row) =>
      sortKey === "updated" ? row.updated_at : row.canonical_name,
    );
  }, [state, sortDir, sortKey]);

  const tenders = useMemo(() => {
    if (state.kind !== "ok") {
      return [];
    }
    const filtered = filterByText(state.tenders, q, (row) => `${row.title} ${row.method ?? ""}`);
    return sortBy(filtered, sortDir, (row) => {
      if (sortKey === "value") {
        return row.value_amount;
      }
      if (sortKey === "updated") {
        return row.updated_at;
      }
      return row.title;
    });
  }, [state, q, sortDir, sortKey]);

  const flags = useMemo(() => {
    if (state.kind !== "ok") {
      return [];
    }
    const filtered = filterByText(state.flags, q, (row) => `${row.rule} ${row.severity}`);
    return sortBy(filtered, sortDir, (row) => {
      if (sortKey === "severity") {
        return row.severity;
      }
      if (sortKey === "updated") {
        return row.updated_at;
      }
      return row.rule;
    });
  }, [state, q, sortDir, sortKey]);

  const buckets = useMemo(() => {
    if (resource === "parties") {
      return countBy(parties.map((row) => row.party_type));
    }
    if (resource === "tenders") {
      return countBy(tenders.map((row) => row.method ?? "unknown"));
    }
    return countBy(flags.map((row) => row.severity));
  }, [resource, parties, tenders, flags]);

  const compareRows = useMemo(() => {
    if (resource === "parties") {
      return parties.filter((row) => selected.includes(row.id));
    }
    if (resource === "tenders") {
      return tenders.filter((row) => selected.includes(row.id));
    }
    return flags.filter((row) => selected.includes(row.id));
  }, [resource, parties, tenders, flags, selected]);

  const rowCount =
    resource === "parties"
      ? parties.length
      : resource === "tenders"
        ? tenders.length
        : flags.length;

  return (
    <div className="page page--explore">
      <h1 className="page__title">Explore</h1>
      <p className="page__lede">
        Filter, sort, and compare public finance entities. Flags are open hypotheses — not verified
        claims. Drill into the <Link to="/sources">source registry</Link> for provenance.
      </p>

      <div className="explore-tabs" role="tablist" aria-label="Resource">
        {(
          [
            ["parties", "Parties"],
            ["tenders", "Tenders"],
            ["flags", "Flags"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={resource === id}
            className={`explore-tabs__btn${resource === id ? " explore-tabs__btn--active" : ""}`}
            onClick={() =>
              patchParams({
                resource: id,
                party_type: null,
                q: null,
                sort: "name",
                dir: "asc",
              })
            }
          >
            {label}
          </button>
        ))}
      </div>

      {resource === "flags" ? (
        <p className="explore-hypothesis" role="note">
          Anomaly flags are hypotheses pending human review — not published facts.
        </p>
      ) : null}

      <div className="explore-controls">
        {resource === "parties" ? (
          <label className="explore-field">
            <span>Type</span>
            <select
              value={partyType}
              onChange={(event) => patchParams({ party_type: event.target.value || null })}
            >
              <option value="">All</option>
              <option value="agency">Agency</option>
              <option value="company">Company</option>
              <option value="person">Person</option>
            </select>
          </label>
        ) : null}
        <label className="explore-field explore-field--grow">
          <span>{resource === "parties" ? "Name contains" : "Filter"}</span>
          <input
            type="search"
            value={q}
            placeholder={
              resource === "parties"
                ? "Search canonical name"
                : resource === "tenders"
                  ? "Filter title or method"
                  : "Filter rule or severity"
            }
            onChange={(event) => patchParams({ q: event.target.value || null })}
          />
        </label>
        <label className="explore-field">
          <span>Sort</span>
          <select value={sortKey} onChange={(event) => patchParams({ sort: event.target.value })}>
            <option value="name">{resource === "flags" ? "Rule" : "Name / title"}</option>
            {resource === "tenders" ? <option value="value">Value</option> : null}
            {resource === "flags" ? <option value="severity">Severity</option> : null}
            <option value="updated">Updated</option>
          </select>
        </label>
        <label className="explore-field">
          <span>Direction</span>
          <select value={sortDir} onChange={(event) => patchParams({ dir: event.target.value })}>
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </label>
      </div>

      {state.kind === "loading" && <p>Loading {resource}…</p>}
      {state.kind === "error" && (
        <p className="banner-error">
          Could not reach the API ({state.message}). Start the engine with{" "}
          <code>make dev-engine</code>.
        </p>
      )}

      {state.kind === "ok" && (
        <div className="explore-grid">
          <div className="explore-main">
            {rowCount === 0 ? (
              <p className="placeholder">
                No {resource} match. Seed data or widen filters, then refresh.
              </p>
            ) : (
              <div className="explore-table-wrap">
                <table className="explore-table">
                  <thead>
                    <tr>
                      <th scope="col">Compare</th>
                      {resource === "parties" ? (
                        <>
                          <th scope="col">Type</th>
                          <th scope="col">Name</th>
                        </>
                      ) : null}
                      {resource === "tenders" ? (
                        <>
                          <th scope="col">Title</th>
                          <th scope="col">Method</th>
                          <th scope="col">Value</th>
                        </>
                      ) : null}
                      {resource === "flags" ? (
                        <>
                          <th scope="col">Severity</th>
                          <th scope="col">Rule</th>
                          <th scope="col">Subject</th>
                        </>
                      ) : null}
                    </tr>
                  </thead>
                  <tbody>
                    {resource === "parties" &&
                      parties.map((row) => (
                        <tr
                          key={row.id}
                          className={detail?.row.id === row.id ? "is-active" : undefined}
                        >
                          <td>
                            <input
                              type="checkbox"
                              checked={selected.includes(row.id)}
                              aria-label={`Compare ${row.canonical_name}`}
                              onChange={() =>
                                setSelected((prev) => toggleCompareSelection(prev, row.id))
                              }
                            />
                          </td>
                          <td>
                            <button
                              type="button"
                              className="linkish"
                              onClick={() => setDetail({ resource: "parties", row })}
                            >
                              {row.party_type}
                            </button>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="linkish"
                              onClick={() => setDetail({ resource: "parties", row })}
                            >
                              {row.canonical_name}
                            </button>
                          </td>
                        </tr>
                      ))}
                    {resource === "tenders" &&
                      tenders.map((row) => (
                        <tr
                          key={row.id}
                          className={detail?.row.id === row.id ? "is-active" : undefined}
                        >
                          <td>
                            <input
                              type="checkbox"
                              checked={selected.includes(row.id)}
                              aria-label={`Compare ${row.title}`}
                              onChange={() =>
                                setSelected((prev) => toggleCompareSelection(prev, row.id))
                              }
                            />
                          </td>
                          <td>
                            <button
                              type="button"
                              className="linkish"
                              onClick={() => setDetail({ resource: "tenders", row })}
                            >
                              {row.title}
                            </button>
                          </td>
                          <td>{row.method ?? "—"}</td>
                          <td>{formatAmount(row.value_amount, row.currency)}</td>
                        </tr>
                      ))}
                    {resource === "flags" &&
                      flags.map((row) => (
                        <tr
                          key={row.id}
                          className={detail?.row.id === row.id ? "is-active" : undefined}
                        >
                          <td>
                            <input
                              type="checkbox"
                              checked={selected.includes(row.id)}
                              aria-label={`Compare ${row.rule}`}
                              onChange={() =>
                                setSelected((prev) => toggleCompareSelection(prev, row.id))
                              }
                            />
                          </td>
                          <td>{row.severity}</td>
                          <td>
                            <button
                              type="button"
                              className="linkish"
                              onClick={() => setDetail({ resource: "flags", row })}
                            >
                              {row.rule}
                            </button>
                          </td>
                          <td>
                            {row.subject_type}/{row.subject_id.slice(0, 8)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}

            {compareRows.length === 2 ? (
              <section className="compare-panel" aria-label="Compare selection">
                <h2 className="compare-panel__title">Compare</h2>
                <div className="compare-panel__grid">
                  {compareRows.map((row) => (
                    <div key={row.id} className="compare-panel__card">
                      {"canonical_name" in row ? (
                        <>
                          <p className="compare-panel__kicker">{row.party_type}</p>
                          <p className="compare-panel__name">{row.canonical_name}</p>
                          <p>Aliases: {row.aliases.length ? row.aliases.join(", ") : "—"}</p>
                        </>
                      ) : null}
                      {"title" in row ? (
                        <>
                          <p className="compare-panel__kicker">{row.method ?? "tender"}</p>
                          <p className="compare-panel__name">{row.title}</p>
                          <p>Value: {formatAmount(row.value_amount, row.currency)}</p>
                        </>
                      ) : null}
                      {"rule" in row ? (
                        <>
                          <p className="compare-panel__kicker">{row.severity} · hypothesis</p>
                          <p className="compare-panel__name">{row.rule}</p>
                          <p>
                            Subject: {row.subject_type}/{row.subject_id}
                          </p>
                        </>
                      ) : null}
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              <p className="explore-hint">Select two rows to compare side by side.</p>
            )}
          </div>

          <aside className="explore-side">
            <DistributionChart
              title={
                resource === "parties"
                  ? "Party types"
                  : resource === "tenders"
                    ? "Tender methods"
                    : "Flag severity"
              }
              buckets={buckets}
            />
            {detail ? (
              <section className="detail-panel" aria-label="Row detail">
                <h2 className="detail-panel__title">Detail</h2>
                {detail.resource === "parties" ? (
                  <dl className="detail-panel__dl">
                    <div>
                      <dt>Name</dt>
                      <dd>{detail.row.canonical_name}</dd>
                    </div>
                    <div>
                      <dt>Type</dt>
                      <dd>{detail.row.party_type}</dd>
                    </div>
                    <div>
                      <dt>Aliases</dt>
                      <dd>{detail.row.aliases.length ? detail.row.aliases.join(", ") : "—"}</dd>
                    </div>
                  </dl>
                ) : null}
                {detail.resource === "tenders" ? (
                  <dl className="detail-panel__dl">
                    <div>
                      <dt>Title</dt>
                      <dd>{detail.row.title}</dd>
                    </div>
                    <div>
                      <dt>Value</dt>
                      <dd>{formatAmount(detail.row.value_amount, detail.row.currency)}</dd>
                    </div>
                    <div>
                      <dt>Agency</dt>
                      <dd>
                        <code>{detail.row.agency_id}</code>
                      </dd>
                    </div>
                  </dl>
                ) : null}
                {detail.resource === "flags" ? (
                  <dl className="detail-panel__dl">
                    <div>
                      <dt>Status</dt>
                      <dd>Hypothesis ({detail.row.status})</dd>
                    </div>
                    <div>
                      <dt>Rule</dt>
                      <dd>{detail.row.rule}</dd>
                    </div>
                    <div>
                      <dt>Severity</dt>
                      <dd>{detail.row.severity}</dd>
                    </div>
                  </dl>
                ) : null}
                <Link className="btn btn--ghost" to="/sources">
                  Browse sources
                </Link>
              </section>
            ) : null}
          </aside>
        </div>
      )}
    </div>
  );
}
