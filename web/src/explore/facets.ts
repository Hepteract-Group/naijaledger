export type GeoYearFacets = {
  state: string;
  lga: string;
  year: string;
};

export function parseGeoYearFacets(params: URLSearchParams): GeoYearFacets {
  return {
    state: params.get("state") ?? "",
    lga: params.get("lga") ?? "",
    year: params.get("year") ?? "",
  };
}

export function geoYearFacetPatch(facets: Partial<GeoYearFacets>): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  if (facets.state !== undefined) {
    out.state = facets.state || null;
  }
  if (facets.lga !== undefined) {
    out.lga = facets.lga || null;
  }
  if (facets.year !== undefined) {
    out.year = facets.year || null;
  }
  return out;
}
