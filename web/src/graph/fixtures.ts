import type { GraphDocument } from "./types";

/** Illustrative demo — not a live Memgraph projection. */
export const DEMO_GRAPH: GraphDocument = {
  id: "demo-procurement",
  title: "Sample procurement graph",
  demo: true,
  nodes: [
    {
      id: "agency-1",
      labels: ["Agency", "FinanceParty"],
      name: "Federal Ministry of Works",
      kind: "party",
    },
    {
      id: "company-1",
      labels: ["Company", "FinanceParty"],
      name: "Sahel Construction Ltd",
      kind: "party",
    },
    {
      id: "tender-1",
      labels: ["Tender"],
      name: "Lagos–Ibadan expressway maintenance",
      kind: "tender",
    },
    {
      id: "award-1",
      labels: ["Award"],
      name: "Award · NGN 4.2bn",
      kind: "award",
    },
    {
      id: "contract-1",
      labels: ["Contract"],
      name: "Contract · signed 2024",
      kind: "contract",
    },
  ],
  links: [
    {
      id: "l1",
      source: "agency-1",
      target: "tender-1",
      rel_type: "ISSUED",
    },
    {
      id: "l2",
      source: "tender-1",
      target: "award-1",
      rel_type: "RESULTED_IN",
    },
    {
      id: "l3",
      source: "award-1",
      target: "company-1",
      rel_type: "AWARDED_TO",
    },
    {
      id: "l4",
      source: "award-1",
      target: "contract-1",
      rel_type: "FROM_AWARD",
    },
    {
      id: "l5",
      source: "agency-1",
      target: "contract-1",
      rel_type: "CONTRACTED",
    },
    {
      id: "l6",
      source: "company-1",
      target: "contract-1",
      rel_type: "SUPPLIED",
    },
  ],
};

export function getDemoGraph(): GraphDocument {
  return DEMO_GRAPH;
}
