import { env } from "@/configs/env";

/**
 * Chi tiết lỗi422 của FastAPI, chỉ giữ vị trí/loại lỗi và giới hạn cần cho form.
 * Không giữ input người dùng hoặc nguyên payload, vì client cũng phục vụ đăng nhập.
 */
export interface ApiValidationIssue {
  type: string;
  loc: (string | number)[];
  msg: string;
  /** Numeric limits only (e.g. max_length, gt, le, decimal_places). */
  ctx?: Record<string, number>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly retryAfter?: number,
    public readonly validationIssues?: ApiValidationIssue[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  accessToken?: string | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

const LIMIT_KEYS = [
  "min_length",
  "max_length",
  "gt",
  "ge",
  "lt",
  "le",
  "max_digits",
  "decimal_places",
  "whole_digits",
] as const;

function numericLimit(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  // Decimal bounds may be serialized as strings.
  if (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return undefined;
}

function toValidationIssue(entry: unknown): ApiValidationIssue | null {
  // JSON lỗi có thể sai cấu trúc; bỏ mục hỏng để phần báo lỗi không tự gây crash.
  if (typeof entry !== "object" || entry === null) return null;
  const { type, loc, msg, ctx } = entry as Record<string, unknown>;
  if (typeof type !== "string" || typeof msg !== "string" || !Array.isArray(loc) || loc.length === 0) return null;
  if (!loc.every((part) => typeof part === "string" || typeof part === "number")) return null;

  const issue: ApiValidationIssue = { type, loc: [...(loc as (string | number)[])], msg };
  if (typeof ctx === "object" && ctx !== null) {
    const limits: Record<string, number> = {};
    for (const key of LIMIT_KEYS) {
      const value = numericLimit((ctx as Record<string, unknown>)[key]);
      if (value !== undefined) limits[key] = value;
    }
    if (Object.keys(limits).length > 0) issue.ctx = limits;
  }
  return issue;
}

/** Well-formed entries of a FastAPI 422 `detail` list; malformed entries are dropped. */
function validationIssuesFrom(payload: unknown): ApiValidationIssue[] | undefined {
  const detail = (payload as { detail?: unknown } | undefined)?.detail;
  if (!Array.isArray(detail)) return undefined;
  const issues = detail.map(toValidationIssue).filter((issue): issue is ApiValidationIssue => issue !== null);
  return issues.length > 0 ? issues : undefined;
}

// Response types describe the API contract; they are not runtime validation.
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  // FormData: để trình duyệt tự đặt Content-Type multipart kèm boundary.
  if (options.body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (options.accessToken) headers.Authorization = `Bearer ${options.accessToken}`;

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : isForm ? (options.body as FormData) : JSON.stringify(options.body),
    credentials: "include",
    signal: options.signal,
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let payload: unknown;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = undefined;
    }
  }
  if (!response.ok) {
    const error = (payload as { error?: { code?: string; message?: string } } | undefined)?.error;
    const retryAfter = Number(response.headers.get("Retry-After")) || undefined;
    throw new ApiError(
      response.status,
      error?.code ?? "request_failed",
      error?.message ?? `Request failed (${response.status})`,
      retryAfter,
      response.status === 422 ? validationIssuesFrom(payload) : undefined,
    );
  }
  return payload as T;
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { signal });
}
