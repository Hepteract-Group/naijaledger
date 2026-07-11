import { apiGet } from "./client";
import { buildQuery, type Page } from "./types";

export type PublicMapState = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  contract_volume: number;
  tender_count: number;
  open_flag_count: number;
  anomaly_density: number;
};

export type MapStatesPage = Page<PublicMapState>;

export function fetchMapStates(params: { year?: number } = {}): Promise<MapStatesPage> {
  return apiGet<MapStatesPage>(`/v1/map/states${buildQuery(params)}`);
}
