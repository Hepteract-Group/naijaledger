/** Demo state metrics for 3D map (E10.5 / spec 0030). */

import nigeriaStates from "../../../engine/src/naijaledger/data/nigeria_states.json";

export type MapMetric = "contract_volume" | "anomaly_density";

export type StateMetric = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  contract_volume: number;
  anomaly_density: number;
  tender_count?: number;
  open_flag_count?: number;
  source?: "live" | "demo";
};

/** Deterministic illustrative volumes/densities — coords from nigeria_states.json SSO. */
const DEMO_VOLUME: Record<string, { contract_volume: number; anomaly_density: number }> = {
  AB: { contract_volume: 12, anomaly_density: 0.22 },
  AD: { contract_volume: 8, anomaly_density: 0.31 },
  AK: { contract_volume: 18, anomaly_density: 0.28 },
  AN: { contract_volume: 15, anomaly_density: 0.35 },
  BA: { contract_volume: 9, anomaly_density: 0.19 },
  BY: { contract_volume: 22, anomaly_density: 0.41 },
  BE: { contract_volume: 11, anomaly_density: 0.27 },
  BO: { contract_volume: 14, anomaly_density: 0.48 },
  CR: { contract_volume: 10, anomaly_density: 0.24 },
  DE: { contract_volume: 28, anomaly_density: 0.39 },
  EB: { contract_volume: 7, anomaly_density: 0.18 },
  ED: { contract_volume: 16, anomaly_density: 0.33 },
  EK: { contract_volume: 6, anomaly_density: 0.15 },
  EN: { contract_volume: 13, anomaly_density: 0.26 },
  FC: { contract_volume: 45, anomaly_density: 0.52 },
  GO: { contract_volume: 8, anomaly_density: 0.21 },
  IM: { contract_volume: 14, anomaly_density: 0.3 },
  JI: { contract_volume: 7, anomaly_density: 0.17 },
  KD: { contract_volume: 24, anomaly_density: 0.44 },
  KN: { contract_volume: 32, anomaly_density: 0.37 },
  KT: { contract_volume: 11, anomaly_density: 0.23 },
  KE: { contract_volume: 9, anomaly_density: 0.2 },
  KO: { contract_volume: 12, anomaly_density: 0.29 },
  KW: { contract_volume: 10, anomaly_density: 0.25 },
  LA: { contract_volume: 58, anomaly_density: 0.61 },
  NA: { contract_volume: 9, anomaly_density: 0.22 },
  NI: { contract_volume: 13, anomaly_density: 0.28 },
  OG: { contract_volume: 20, anomaly_density: 0.34 },
  ON: { contract_volume: 12, anomaly_density: 0.27 },
  OS: { contract_volume: 11, anomaly_density: 0.24 },
  OY: { contract_volume: 17, anomaly_density: 0.32 },
  PL: { contract_volume: 10, anomaly_density: 0.26 },
  RI: { contract_volume: 36, anomaly_density: 0.55 },
  SO: { contract_volume: 8, anomaly_density: 0.18 },
  TA: { contract_volume: 7, anomaly_density: 0.21 },
  YO: { contract_volume: 6, anomaly_density: 0.3 },
  ZA: { contract_volume: 8, anomaly_density: 0.36 },
};

/** Approximate centroids — illustrative only, not survey-grade (JSON SSO). */
export const STATE_METRICS: StateMetric[] = nigeriaStates.map((row) => {
  const demo = DEMO_VOLUME[row.code] ?? { contract_volume: 1, anomaly_density: 0.1 };
  return {
    id: row.code,
    name: row.name,
    lat: row.lat,
    lng: row.lng,
    contract_volume: demo.contract_volume,
    anomaly_density: demo.anomaly_density,
  };
});

export function listStateMetrics(): StateMetric[] {
  return STATE_METRICS.map((row) => ({ ...row, source: "demo" as const }));
}

/** Height scaled to national max so demo ints and live kobo both fit the stage. */
export function elevationForMetric(row: StateMetric, metric: MapMetric, ceiling: number): number {
  const maxHeight = metric === "contract_volume" ? 60_000 : 80_000;
  return metricIntensity(row, metric, ceiling) * maxHeight;
}

export function maxMetric(rows: readonly StateMetric[], metric: MapMetric): number {
  return rows.reduce((acc, row) => Math.max(acc, row[metric]), 0);
}

export function metricLabel(metric: MapMetric): string {
  return metric === "contract_volume" ? "Contract volume" : "Anomaly density";
}

export function formatMetricValue(row: StateMetric, metric: MapMetric): string {
  if (metric === "contract_volume") {
    if (row.source === "live") {
      const naira = row.contract_volume / 100;
      return `₦${naira.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    }
    return String(row.contract_volume);
  }
  return row.anomaly_density.toFixed(2);
}

export function metricIntensity(row: StateMetric, metric: MapMetric, max: number): number {
  if (max <= 0) {
    return 0;
  }
  return Math.min(1, row[metric] / max);
}

/** Rank 1 = highest for the active metric. */
export function rankForMetric(
  rows: readonly StateMetric[],
  metric: MapMetric,
  id: string,
): number | null {
  const ordered = [...rows].sort((a, b) => b[metric] - a[metric]);
  const index = ordered.findIndex((row) => row.id === id);
  return index === -1 ? null : index + 1;
}

export function topStates(
  rows: readonly StateMetric[],
  metric: MapMetric,
  limit = 5,
): StateMetric[] {
  return [...rows].sort((a, b) => b[metric] - a[metric]).slice(0, limit);
}

/** RGBA for column fill — forest scale for volume, indigo for anomaly. */
export function columnFillColor(
  intensity: number,
  metric: MapMetric,
  selected: boolean,
): [number, number, number, number] {
  const t = Math.max(0.15, intensity);
  if (selected) {
    return [184, 137, 45, 245];
  }
  if (metric === "contract_volume") {
    return [11, Math.round(70 + t * 70), Math.round(55 + t * 40), Math.round(160 + t * 70)];
  }
  return [36, Math.round(50 + t * 40), Math.round(90 + t * 70), Math.round(160 + t * 70)];
}
