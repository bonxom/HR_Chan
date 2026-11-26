import { apiRequest } from "@/shared/services/client";
import type { ResponseReceipt, ResponseResult, ResponseSubmission, ResponseView } from "./types";

export function resolveResponse(token: string): Promise<ResponseView | ResponseReceipt> {
  return apiRequest("/api/v1/responses/resolve", { method: "POST", body: { token } });
}

export function submitResponse(payload: ResponseSubmission): Promise<ResponseResult> {
  return apiRequest("/api/v1/responses/submit", { method: "POST", body: payload });
}
