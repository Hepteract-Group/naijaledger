import { describe, expect, it } from "vitest";
import {
  columnFillColor,
  elevationForMetric,
  formatArchiveAsOf,
  listStateMetrics,
  maxMetric,
  maxMetricRow,
  metricIntensity,
  rankForMetric,
  topStates,
} from "./fixtures";

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
    const max = maxMetric(listStateMetrics(), "contract_volume");
    expect(elevationForMetric(lagos, "contract_volume", max)).toBe(60_000);
    expect(elevationForMetric(lagos, "anomaly_density", 1)).toBeCloseTo(
      lagos.anomaly_density * 80_000,
    );
    expect(maxMetric(listStateMetrics(), "contract_volume")).toBeGreaterThan(0);
  });

  it("ranks and colours by metric intensity", () => {
    const rows = listStateMetrics();
    const leaders = topStates(rows, "contract_volume", 3);
    expect(leaders[0]?.id).toBe("LA");
    expect(rankForMetric(rows, "contract_volume", "LA")).toBe(1);
    const max = maxMetric(rows, "contract_volume");
    const lagos = rows.find((row) => row.id === "LA");
    expect(lagos).toBeTruthy();
    if (!lagos) {
      return;
    }
    expect(metricIntensity(lagos, "contract_volume", max)).toBe(1);
    expect(columnFillColor(1, "contract_volume", true)[0]).toBe(184);
  });

  it("picks the row that sets the legend ceiling", () => {
    const rows = listStateMetrics();
    expect(maxMetricRow(rows, "contract_volume")?.id).toBe("LA");
  });

  it("formats archive as-of footnotes", () => {
    expect(
      formatArchiveAsOf({
        id: "AB",
        name: "Abia",
        lat: 0,
        lng: 0,
        contract_volume: 1,
        anomaly_density: 0,
      }),
    ).toBeNull();
    expect(
      formatArchiveAsOf({
        id: "AB",
        name: "Abia",
        lat: 0,
        lng: 0,
        contract_volume: 1,
        anomaly_density: 0,
        ocp_archive_tender_count: 2,
        ocp_retrieved_on_min: "2022-06-03",
        ocp_retrieved_on_max: "2022-06-03",
      }),
    ).toBe("archive as of 2022-06-03");
    expect(
      formatArchiveAsOf({
        id: "AB",
        name: "Abia",
        lat: 0,
        lng: 0,
        contract_volume: 1,
        anomaly_density: 0,
        ocp_archive_tender_count: 2,
        ocp_retrieved_on_min: "2021-01-01",
        ocp_retrieved_on_max: "2023-04-26",
      }),
    ).toBe("archive as of 2021-01-01–2023-04-26");
  });
});
