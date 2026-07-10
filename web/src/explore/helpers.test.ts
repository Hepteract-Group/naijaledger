import { describe, expect, it } from "vitest";
import { countBy, filterByText, sortBy, toggleCompareSelection } from "./helpers";

describe("toggleCompareSelection", () => {
  it("adds, removes, and caps at two", () => {
    expect(toggleCompareSelection([], "a")).toEqual(["a"]);
    expect(toggleCompareSelection(["a"], "a")).toEqual([]);
    expect(toggleCompareSelection(["a", "b"], "c")).toEqual(["b", "c"]);
  });
});

describe("sortBy / filterByText / countBy", () => {
  const rows = [
    { id: "1", name: "Lagos", value: 30 },
    { id: "2", name: "Abuja", value: 10 },
    { id: "3", name: "Kano", value: null as number | null },
  ];

  it("sorts ascending and descending", () => {
    expect(sortBy(rows, "asc", (row) => row.name).map((row) => row.name)).toEqual([
      "Abuja",
      "Kano",
      "Lagos",
    ]);
    expect(sortBy(rows, "desc", (row) => row.value).map((row) => row.id)).toEqual(["1", "2", "3"]);
  });

  it("filters by text and counts buckets", () => {
    expect(filterByText(rows, "ab", (row) => row.name).map((row) => row.id)).toEqual(["2"]);
    expect(countBy(["agency", "company", "agency"])).toEqual([
      { key: "agency", count: 2 },
      { key: "company", count: 1 },
    ]);
  });
});
