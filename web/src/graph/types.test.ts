import { describe, expect, it } from "vitest";
import { getDemoGraph } from "./fixtures";
import { toForceGraphData } from "./types";

describe("graph fixtures", () => {
  it("provides a demo graph with party and tender nodes", () => {
    const doc = getDemoGraph();
    expect(doc.demo).toBe(true);
    expect(doc.nodes.length).toBeGreaterThanOrEqual(3);
    expect(doc.links.length).toBeGreaterThanOrEqual(2);
    expect(doc.nodes.some((node) => node.kind === "party")).toBe(true);
    expect(doc.nodes.some((node) => node.kind === "tender")).toBe(true);
  });

  it("maps to force-graph data", () => {
    const data = toForceGraphData(getDemoGraph());
    expect(data.nodes.map((node) => node.id)).toContain("agency-1");
    expect(data.links[0]?.rel_type).toBe("ISSUED");
  });
});
