import { apiGet } from "./client";

export type PublicParty = {
  id: string;
  party_type: string;
  canonical_name: string;
  aliases: string[];
  merged_into_id: string | null;
  created_at: string;
  updated_at: string;
};

export type PartiesPage = {
  items: PublicParty[];
  limit: number;
  offset: number;
  count: number;
};

export function fetchParties(limit = 50): Promise<PartiesPage> {
  return apiGet<PartiesPage>(`/v1/parties?limit=${limit}`);
}
