import { apiGet } from "./client";
import { buildQuery, type Page } from "./types";

export type PublicParty = {
  id: string;
  party_type: string;
  canonical_name: string;
  aliases: string[];
  merged_into_id: string | null;
  created_at: string;
  updated_at: string;
};

export type PartiesPage = Page<PublicParty>;

export type FetchPartiesParams = {
  party_type?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

export function fetchParties(params: FetchPartiesParams = {}): Promise<PartiesPage> {
  return apiGet<PartiesPage>(`/v1/parties${buildQuery(params)}`);
}

export function fetchParty(id: string): Promise<PublicParty> {
  return apiGet<PublicParty>(`/v1/parties/${id}`);
}
