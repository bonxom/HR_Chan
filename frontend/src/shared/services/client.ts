import { env } from "@/configs/env";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// Response types describe the API contract; they are not runtime validation.
export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) throw new ApiError(response.status, `Request failed (${response.status})`);
  return response.json() as Promise<T>;
}
