import { apiGet } from "./client";
import { buildQuery, type Page } from "./types";

export type PublicSource = {
  id: string;
  name: string;
  url: string;
  jurisdiction: string;
  region: string | null;
  category: string;
  format: string;
  fetch_method: string;
  status: string;
  health_status: string;
  expected_cadence: number | null;
  created_at: string;
  updated_at: string;
};

export type SourcesPage = Page<PublicSource>;

export function fetchSources(
  params: { status?: string; state?: string; limit?: number; offset?: number } = {},
): Promise<SourcesPage> {
  return apiGet<SourcesPage>(`/v1/sources${buildQuery(params)}`);
}

export function fetchSource(id: string): Promise<PublicSource> {
  return apiGet<PublicSource>(`/v1/sources/${id}`);
}
