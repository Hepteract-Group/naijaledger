import { describe, expect, it } from "vitest";
import { elevationForMetric, listStateMetrics, maxMetric } from "./fixtures";

describe("map fixtures", () => {
  it("covers 36 states + FCT", () => {
    const rows = listStateMetrics();
    expect(rows.length).toBe(37);
    expect(rows.some((row) => row.id === "FC")).toBe(true);
    expect(rows.some((row) => row.id === "LA")).toBe(true);
  });

  it("scales elevation by selected metric", () => {
    const lagos = listStateMetrics().find((row) => row.id === "LA");
    expect(lagos).toBeTruthy();
    if (!lagos) {
      return;
    }
    expect(elevationForMetric(lagos, "contract_volume")).toBe(lagos.contract_volume * 1200);
    expect(elevationForMetric(lagos, "anomaly_density")).toBe(lagos.anomaly_density * 80000);
    expect(maxMetric(listStateMetrics(), "contract_volume")).toBeGreaterThan(0);
  });
});
