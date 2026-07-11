import { describe, expect, it } from "vitest";
import { geoYearFacetPatch, parseFacetYear, parseGeoYearFacets } from "./facets";

describe("geo year facets", () => {
  it("parses URL params", () => {
    const params = new URLSearchParams("state=EK&lga=ADO-EKITI&year=2026");
    expect(parseGeoYearFacets(params)).toEqual({
      state: "EK",
      lga: "ADO-EKITI",
      year: "2026",
    });
  });

  it("patches clear empty values", () => {
    expect(geoYearFacetPatch({ state: "", lga: "X", year: "2026" })).toEqual({
      state: null,
      lga: "X",
      year: "2026",
    });
  });

  it("only accepts complete fiscal years for API", () => {
    expect(parseFacetYear("")).toBeUndefined();
    expect(parseFacetYear("2")).toBeUndefined();
    expect(parseFacetYear("202")).toBeUndefined();
    expect(parseFacetYear("2026")).toBe(2026);
    expect(parseFacetYear("1899")).toBeUndefined();
  });
});
