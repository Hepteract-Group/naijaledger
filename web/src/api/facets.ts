import { apiGet } from "./client";
import { buildQuery } from "./types";

export type FacetState = { code: string; name: string };

export type PublicFacets = {
  states: FacetState[];
  years: number[];
  lgas: string[];
};

export function fetchFacets(params: { state?: string } = {}): Promise<PublicFacets> {
  return apiGet<PublicFacets>(`/v1/facets${buildQuery(params)}`);
}
