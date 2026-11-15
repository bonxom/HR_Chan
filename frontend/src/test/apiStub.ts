import { vi } from "vitest";

export interface RecordedRequest {
  method: string;
  path: string;
  body: unknown;
  headers: Record<string, string>;
}

export type RouteHandler = (request: RecordedRequest) => Response | Promise<Response>;

export function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function errorResponse(status: number, code: string, message: string): Response {
  return jsonResponse({ error: { code, message } }, status);
}

/** Stub the global fetch with explicit method+path routes and record calls. */
export function stubFetch(routes: Record<string, RouteHandler>) {
  const calls: RecordedRequest[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString(), "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const headers = new Headers(init?.headers as HeadersInit | undefined);
    const request: RecordedRequest = {
      method,
      path: url.pathname + url.search,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      headers: Object.fromEntries(headers.entries()),
    };
    calls.push(request);
    const handler = routes[`${method} ${url.pathname}`];
    if (!handler) return errorResponse(404, "unexpected_request", request.path);
    return handler(request);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export const CSRF_ROUTE = {
  "GET /api/v1/auth/csrf": () => jsonResponse({ csrf_token: "token-value.signature" }),
};
