import { afterEach, expect, it, vi } from "vitest";
import { resolveResponse, submitResponse } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("sends the secret in a POST body on fixed API paths", async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ completed: true, outcome: "ACCEPTED", completed_at: "2026-11-25T03:00:00Z" })));
  vi.stubGlobal("fetch", fetcher);
  await resolveResponse("private-token");
  await submitResponse({ token: "private-token", action: "ACCEPTED" });
  expect(fetcher.mock.calls.map(([url]) => url)).toEqual(["/api/v1/responses/resolve", "/api/v1/responses/submit"]);
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ token: "private-token" });
  expect(fetcher.mock.calls[1][1].method).toBe("POST");
  expect(localStorage.length).toBe(0);
});
