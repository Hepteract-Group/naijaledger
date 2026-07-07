export type EngineHealth = {
  status: string;
  service: string;
  version: string;
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function fetchEngineHealth(): Promise<EngineHealth> {
  const response = await fetch(`${apiBase}/health`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as EngineHealth;
}
