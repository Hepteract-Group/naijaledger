/** Demo state metrics for 3D map (E10.5 / spec 0030). */

export type MapMetric = "contract_volume" | "anomaly_density";

export type StateMetric = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  contract_volume: number;
  anomaly_density: number;
};

/** Approximate centroids — illustrative only, not survey-grade. */
export const STATE_METRICS: StateMetric[] = [
  { id: "AB", name: "Abia", lat: 5.4527, lng: 7.5248, contract_volume: 12, anomaly_density: 0.22 },
  {
    id: "AD",
    name: "Adamawa",
    lat: 9.3265,
    lng: 12.3984,
    contract_volume: 8,
    anomaly_density: 0.31,
  },
  {
    id: "AK",
    name: "Akwa Ibom",
    lat: 5.0077,
    lng: 7.8537,
    contract_volume: 18,
    anomaly_density: 0.28,
  },
  {
    id: "AN",
    name: "Anambra",
    lat: 6.2209,
    lng: 7.067,
    contract_volume: 15,
    anomaly_density: 0.35,
  },
  {
    id: "BA",
    name: "Bauchi",
    lat: 10.3158,
    lng: 9.8442,
    contract_volume: 9,
    anomaly_density: 0.19,
  },
  {
    id: "BY",
    name: "Bayelsa",
    lat: 4.7719,
    lng: 6.0699,
    contract_volume: 22,
    anomaly_density: 0.41,
  },
  { id: "BE", name: "Benue", lat: 7.3369, lng: 8.7404, contract_volume: 11, anomaly_density: 0.27 },
  { id: "BO", name: "Borno", lat: 11.8333, lng: 13.15, contract_volume: 14, anomaly_density: 0.48 },
  {
    id: "CR",
    name: "Cross River",
    lat: 5.8702,
    lng: 8.5988,
    contract_volume: 10,
    anomaly_density: 0.24,
  },
  { id: "DE", name: "Delta", lat: 5.704, lng: 5.9339, contract_volume: 28, anomaly_density: 0.39 },
  { id: "EB", name: "Ebonyi", lat: 6.2649, lng: 8.0137, contract_volume: 7, anomaly_density: 0.18 },
  { id: "ED", name: "Edo", lat: 6.634, lng: 5.93, contract_volume: 16, anomaly_density: 0.33 },
  { id: "EK", name: "Ekiti", lat: 7.719, lng: 5.311, contract_volume: 6, anomaly_density: 0.15 },
  { id: "EN", name: "Enugu", lat: 6.4584, lng: 7.5464, contract_volume: 13, anomaly_density: 0.26 },
  { id: "FC", name: "FCT", lat: 9.0765, lng: 7.3986, contract_volume: 45, anomaly_density: 0.52 },
  { id: "GO", name: "Gombe", lat: 10.2897, lng: 11.171, contract_volume: 8, anomaly_density: 0.21 },
  { id: "IM", name: "Imo", lat: 5.572, lng: 7.0588, contract_volume: 14, anomaly_density: 0.3 },
  { id: "JI", name: "Jigawa", lat: 12.228, lng: 9.5616, contract_volume: 7, anomaly_density: 0.17 },
  {
    id: "KD",
    name: "Kaduna",
    lat: 10.5105,
    lng: 7.4165,
    contract_volume: 24,
    anomaly_density: 0.44,
  },
  { id: "KN", name: "Kano", lat: 12.0022, lng: 8.592, contract_volume: 32, anomaly_density: 0.37 },
  {
    id: "KT",
    name: "Katsina",
    lat: 12.9908,
    lng: 7.601,
    contract_volume: 11,
    anomaly_density: 0.23,
  },
  { id: "KE", name: "Kebbi", lat: 11.4942, lng: 4.2333, contract_volume: 9, anomaly_density: 0.2 },
  { id: "KO", name: "Kogi", lat: 7.7337, lng: 6.6906, contract_volume: 12, anomaly_density: 0.29 },
  { id: "KW", name: "Kwara", lat: 8.9669, lng: 4.3874, contract_volume: 10, anomaly_density: 0.25 },
  { id: "LA", name: "Lagos", lat: 6.5244, lng: 3.3792, contract_volume: 58, anomaly_density: 0.61 },
  { id: "NA", name: "Nasarawa", lat: 8.4991, lng: 8.5, contract_volume: 9, anomaly_density: 0.22 },
  { id: "NI", name: "Niger", lat: 9.9306, lng: 5.5983, contract_volume: 13, anomaly_density: 0.28 },
  { id: "OG", name: "Ogun", lat: 6.998, lng: 3.4737, contract_volume: 20, anomaly_density: 0.34 },
  { id: "ON", name: "Ondo", lat: 7.1, lng: 5.05, contract_volume: 12, anomaly_density: 0.27 },
  { id: "OS", name: "Osun", lat: 7.5629, lng: 4.52, contract_volume: 11, anomaly_density: 0.24 },
  { id: "OY", name: "Oyo", lat: 8.1574, lng: 3.6147, contract_volume: 17, anomaly_density: 0.32 },
  {
    id: "PL",
    name: "Plateau",
    lat: 9.2182,
    lng: 9.5179,
    contract_volume: 10,
    anomaly_density: 0.26,
  },
  {
    id: "RI",
    name: "Rivers",
    lat: 4.8156,
    lng: 7.0498,
    contract_volume: 36,
    anomaly_density: 0.55,
  },
  {
    id: "SO",
    name: "Sokoto",
    lat: 13.0059,
    lng: 5.2476,
    contract_volume: 8,
    anomaly_density: 0.18,
  },
  { id: "TA", name: "Taraba", lat: 8.0, lng: 10.5, contract_volume: 7, anomaly_density: 0.21 },
  { id: "YO", name: "Yobe", lat: 12.0, lng: 11.5, contract_volume: 6, anomaly_density: 0.3 },
  { id: "ZA", name: "Zamfara", lat: 12.17, lng: 6.66, contract_volume: 8, anomaly_density: 0.36 },
];

export function listStateMetrics(): StateMetric[] {
  return STATE_METRICS;
}

export function elevationForMetric(row: StateMetric, metric: MapMetric): number {
  if (metric === "contract_volume") {
    return row.contract_volume * 1200;
  }
  return row.anomaly_density * 80000;
}

export function maxMetric(rows: readonly StateMetric[], metric: MapMetric): number {
  return rows.reduce((acc, row) => Math.max(acc, row[metric]), 0);
}
