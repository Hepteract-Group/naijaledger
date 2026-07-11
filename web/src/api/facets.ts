import { apiGet } from "./client";

export type FacetState = { code: string; name: string };

export type PublicFacets = {
  states: FacetState[];
  years: number[];
  lgas: string[];
};

export function fetchFacets(): Promise<PublicFacets> {
  return apiGet<PublicFacets>("/v1/facets");
}
