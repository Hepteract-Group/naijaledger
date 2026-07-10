import { apiGet } from "./client";
import { buildQuery, type Page } from "./types";

export type PublicFlag = {
  id: string;
  subject_type: string;
  subject_id: string;
  rule: string;
  severity: string;
  evidence: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
};

export type FlagsPage = Page<PublicFlag>;

export function fetchFlags(limit = 50): Promise<FlagsPage> {
  return apiGet<FlagsPage>(`/v1/flags${buildQuery({ limit })}`);
}

export function fetchFlag(id: string): Promise<PublicFlag> {
  return apiGet<PublicFlag>(`/v1/flags/${id}`);
}
