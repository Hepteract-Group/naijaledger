import { apiGet } from "./client";

export type EngineHealth = {
  status: string;
  service: string;
  version: string;
};

export function fetchEngineHealth(): Promise<EngineHealth> {
  return apiGet<EngineHealth>("/health");
}
