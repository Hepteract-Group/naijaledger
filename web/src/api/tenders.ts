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
  state_code: string | null;
  lga: string | null;
  fiscal_year: number | null;
  created_at: string;
  updated_at: string;
};

export type TendersPage = Page<PublicTender>;

export type TenderListParams = {
  limit?: number;
  offset?: number;
  state?: string;
  lga?: string;
  year?: number | string;
};

export function fetchTenders(
  params: TenderListParams | number = 50,
  offset = 0,
): Promise<TendersPage> {
  if (typeof params === "number") {
    return apiGet<TendersPage>(`/v1/tenders${buildQuery({ limit: params, offset })}`);
  }
  return apiGet<TendersPage>(`/v1/tenders${buildQuery(params)}`);
}

export function fetchTender(id: string): Promise<PublicTender> {
  return apiGet<PublicTender>(`/v1/tenders/${id}`);
}
