/** Web graph document (E10.4 / spec 0029) — aligned with E6.4 labels. */

export type GraphNodeKind = "party" | "tender" | "award" | "contract";

export type GraphNodeDoc = {
  id: string;
  labels: string[];
  name: string;
  kind: GraphNodeKind;
};

export type GraphLinkDoc = {
  id: string;
  source: string;
  target: string;
  rel_type: string;
};

export type GraphDocument = {
  id: string;
  title: string;
  demo: boolean;
  nodes: GraphNodeDoc[];
  links: GraphLinkDoc[];
};

export type ForceGraphNode = {
  id: string;
  name: string;
  labels: string[];
  kind: GraphNodeKind;
};

export type ForceGraphLink = {
  id: string;
  source: string;
  target: string;
  rel_type: string;
};

export type ForceGraphData = {
  nodes: ForceGraphNode[];
  links: ForceGraphLink[];
};

export function toForceGraphData(doc: GraphDocument): ForceGraphData {
  return {
    nodes: doc.nodes.map((node) => ({
      id: node.id,
      name: node.name,
      labels: node.labels,
      kind: node.kind,
    })),
    links: doc.links.map((link) => ({
      id: link.id,
      source: link.source,
      target: link.target,
      rel_type: link.rel_type,
    })),
  };
}
