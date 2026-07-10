import { useEffect, useState } from "react";
import { fetchParties, type PublicParty } from "../api/parties";

type LoadState =
  { kind: "loading" } | { kind: "ok"; parties: PublicParty[] } | { kind: "error"; message: string };

export function ExplorePage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchParties()
      .then((page) => {
        if (!cancelled) {
          setState({ kind: "ok", parties: page.items });
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
      <h1 className="page__title">Explore</h1>
      <p className="page__lede">
        Canonical parties from the public read API. Empty until finance data is loaded into
        Postgres.
      </p>
      {state.kind === "loading" && <p>Loading parties…</p>}
      {state.kind === "error" && (
        <p className="banner-error">
          Could not reach the API ({state.message}). Start the engine with{" "}
          <code>make dev-engine</code>.
        </p>
      )}
      {state.kind === "ok" && state.parties.length === 0 && (
        <p className="placeholder">No parties yet. Seed or ingest finance data, then refresh.</p>
      )}
      {state.kind === "ok" && state.parties.length > 0 && (
        <ul className="party-list">
          {state.parties.map((party) => (
            <li key={party.id}>
              <span className="party-list__type">{party.party_type}</span>
              <span>{party.canonical_name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
