export const apiBase = import.meta.env.VITE_API_BASE_URL ?? "/api";

export type ApiFailure = Error & { status: number };

export function apiFailure(status: number): ApiFailure {
  const error = new Error(`HTTP ${status}`) as ApiFailure;
  error.name = "ApiFailure";
  error.status = status;
  return error;
}

export function isApiFailure(error: unknown): error is ApiFailure {
  return error instanceof Error && typeof (error as ApiFailure).status === "number";
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase}${path}`);
  if (!response.ok) {
    throw apiFailure(response.status);
  }
  return (await response.json()) as T;
}
