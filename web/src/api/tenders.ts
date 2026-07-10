import { apiGet } from "./client";
import { buildQuery, type Page } from "./types";

export type PublicTender = {
  id: string;
  ocid: string | null;
  agency_id: string;
  title: string;
  method: string | null;
  value_amount: number | null;
  currency: string;
  bidding_opens_at: string | null;
  bidding_closes_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TendersPage = Page<PublicTender>;

export function fetchTenders(limit = 50, offset = 0): Promise<TendersPage> {
  return apiGet<TendersPage>(`/v1/tenders${buildQuery({ limit, offset })}`);
}

export function fetchTender(id: string): Promise<PublicTender> {
  return apiGet<PublicTender>(`/v1/tenders/${id}`);
}
