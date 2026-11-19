// Stub fetch cho luồng ứng viên công khai: ghi lại body thô (FormData hoặc JSON) và header,
// vì stubFetch dùng chung JSON.parse body nên không đọc được multipart.
import { vi } from "vitest";
import { jsonResponse } from "@/test/apiStub";

export interface FlowRequest {
  method: string;
  path: string;
  /** Parsed JSON body when the request body was a string; undefined otherwise. */
  json: unknown;
  /** The FormData instance when the request was multipart. */
  form: FormData | undefined;
  rawBody: unknown;
  headers: Record<string, string>;
}

export type FlowHandler = (request: FlowRequest) => Response | Promise<Response>;

export function stubFlowFetch(routes: Record<string, FlowHandler>) {
  const calls: FlowRequest[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString(), "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const rawBody = init?.body;
    const request: FlowRequest = {
      method,
      path: url.pathname + url.search,
      json: typeof rawBody === "string" ? JSON.parse(rawBody) : undefined,
      form: rawBody instanceof FormData ? rawBody : undefined,
      rawBody,
      headers: Object.fromEntries(new Headers(init?.headers as HeadersInit | undefined).entries()),
    };
    calls.push(request);
    const handler = routes[`${method} ${url.pathname}`];
    if (!handler) {
      return jsonResponse({ error: { code: "unexpected_request", message: request.path } }, 404);
    }
    return handler(request);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export function validationResponse(field: string, msg: string): Response {
  return jsonResponse(
    { detail: [{ type: "value_error", loc: ["body", field], msg, input: null }] },
    422,
  );
}

export function appError(
  status: number,
  code: string,
  message: string,
  headers: Record<string, string> = {},
): Response {
  return jsonResponse({ error: { code, message } }, status, headers);
}

/** Public job DTOs exactly as the backend returns them (test_public_jobs.py). */
export function publicJobJson(overrides: Record<string, unknown> = {}) {
  return {
    id: 11,
    title: "Kỹ sư dữ liệu",
    department_id: 3,
    department_name: "Phòng Kỹ thuật",
    headcount: 2,
    work_mode: "Toàn thời gian",
    location: "Hà Nội",
    deadline: "2026-12-30",
    ...overrides,
  };
}

export function publicJobDetailJson(overrides: Record<string, unknown> = {}) {
  return {
    ...publicJobJson(),
    description: "Xây dựng pipeline dữ liệu.",
    requirements: "Python, SQL.",
    benefits: "Bảo hiểm đầy đủ.",
    ...overrides,
  };
}

export function publicPage(items: unknown[], extra: Record<string, unknown> = {}) {
  return { items, total: items.length, page: 1, page_size: 12, ...extra };
}

export const SUBMISSION_JSON = {
  submission_id: 501,
  submission_token: "1767225600.nonce.signature-value-0123456789",
  expires_at: "2026-11-19T03:00:00Z",
};

export const OTP_ISSUED_JSON = {
  expires_at: "2026-11-18T03:05:00Z",
  resend_available_at: "2026-11-18T03:01:00Z",
};

export const APPLICATION_CREATED_JSON = {
  application_id: 9001,
  submitted_at: "2026-11-18T03:02:00Z",
  message: "Cảm ơn bạn đã ứng tuyển. Hồ sơ đã được tiếp nhận và đang chờ xử lý.",
};

export function cvFile(name = "cv.pdf", size = 2048, type = "application/pdf"): File {
  const file = new File([new Uint8Array(Math.min(size, 4096))], name, { type });
  // Kích thước thật không cần cấp phát: chỉ ghi đè thuộc tính size cho kiểm tra giới hạn.
  Object.defineProperty(file, "size", { value: size });
  return file;
}
