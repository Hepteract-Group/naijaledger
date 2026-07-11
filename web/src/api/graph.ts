import { apiGet } from "./client";
import { buildQuery } from "./types";
import type { GraphDocument, GraphLinkDoc, GraphNodeDoc } from "../graph/types";

export type PublicGraphDocument = GraphDocument & {
  available: boolean;
};

export function fetchGraphSubgraph(
  params: { seed_id?: string; limit?: number } = {},
): Promise<PublicGraphDocument> {
  return apiGet<PublicGraphDocument>(`/v1/graph/subgraph${buildQuery(params)}`);
}

export function toGraphDocument(doc: PublicGraphDocument): GraphDocument {
  return {
    id: doc.id,
    title: doc.title,
    demo: doc.demo,
    nodes: doc.nodes as GraphNodeDoc[],
    links: doc.links as GraphLinkDoc[],
  };
}
