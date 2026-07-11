import type { FacetState } from "../api/facets";

type FacetBarProps = {
  state: string;
  lga: string;
  year: string;
  states: FacetState[];
  years: number[];
  lgas: string[];
  showLga?: boolean;
  showYear?: boolean;
  onChange: (patch: { state?: string; lga?: string; year?: string }) => void;
};

export function FacetBar({
  state,
  lga,
  year,
  states = [],
  years = [],
  lgas = [],
  showLga = true,
  showYear = true,
  onChange,
}: FacetBarProps) {
  return (
    <div className="facet-bar" role="group" aria-label="Geography and year">
      <label className="explore-field">
        <span>State</span>
        <select value={state} onChange={(event) => onChange({ state: event.target.value })}>
          <option value="">All states</option>
          {states.map((row) => (
            <option key={row.code} value={row.code}>
              {row.name}
            </option>
          ))}
        </select>
      </label>
      {showLga ? (
        <label className="explore-field">
          <span>LGA</span>
          {lgas.length > 0 ? (
            <select value={lga} onChange={(event) => onChange({ lga: event.target.value })}>
              <option value="">All LGAs</option>
              {lgas.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="search"
              value={lga}
              placeholder="LGA contains…"
              onChange={(event) => onChange({ lga: event.target.value })}
            />
          )}
        </label>
      ) : null}
      {showYear ? (
        <label className="explore-field">
          <span>Year</span>
          {years.length > 0 ? (
            <select value={year} onChange={(event) => onChange({ year: event.target.value })}>
              <option value="">All years</option>
              {years.map((value) => (
                <option key={value} value={String(value)}>
                  {value}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="search"
              inputMode="numeric"
              value={year}
              placeholder="e.g. 2026"
              onChange={(event) => onChange({ year: event.target.value })}
            />
          )}
        </label>
      ) : null}
    </div>
  );
}
