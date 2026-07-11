import { describe, expect, it } from "vitest";
import { getDemoGraph } from "./fixtures";
import { toForceGraphData } from "./types";

describe("graph types", () => {
  it("maps demo document to force-graph data", () => {
    const doc = getDemoGraph();
    const data = toForceGraphData(doc);
    expect(data.nodes.length).toBe(doc.nodes.length);
    expect(data.links.length).toBe(doc.links.length);
    expect(data.nodes.some((node) => node.kind === "party")).toBe(true);
  });

  it("keeps document link endpoints as string ids for related lookups", () => {
    const doc = getDemoGraph();
    const selectedId = "agency-1";
    const ids = new Set<string>();
    for (const link of doc.links) {
      if (link.source === selectedId) {
        ids.add(link.target);
      }
      if (link.target === selectedId) {
        ids.add(link.source);
      }
    }
    expect(ids.has("tender-1")).toBe(true);
    expect(ids.has("contract-1")).toBe(true);
    expect(typeof [...ids][0]).toBe("string");
  });
});
