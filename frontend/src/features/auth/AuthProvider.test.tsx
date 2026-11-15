import { renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthProvider";
import {
  CSRF_ROUTE,
  errorResponse,
  jsonResponse,
  stubFetch,
} from "@/test/apiStub";
import { accountJson, adminAccountJson } from "@/test/fixtures";
import { currentAccessToken, endSession } from "./session";
import { refreshSession } from "./refreshCoordinator";

function wrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    );
  };
}

function testQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function sessionResponse() {
  return jsonResponse({
    access_token: "access-token-from-refresh",
    token_type: "bearer",
    expires_in: 300,
    account: adminAccountJson(),
  });
}

describe("AuthProvider bootstrap", () => {
  it("reports anonymous after startup when no refresh cookie is valid", async () => {
    const { calls } = stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": () =>
        errorResponse(401, "invalid_session", "The session is no longer valid"),
    });
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(testQueryClient()) });

    await waitFor(() => expect(result.current.status).toBe("anonymous"));
    expect(calls.some((call) => call.path === "/api/v1/auth/refresh")).toBe(true);
    expect(currentAccessToken()).toBeNull();
  });

  it("restores the session from the refresh cookie and loads the account", async () => {
    stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": sessionResponse,
      "GET /api/v1/auth/me": () => jsonResponse(adminAccountJson()),
    });
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(testQueryClient()) });

    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(result.current.account?.email).toBe("admin@sis.hust.edu.vn");
    expect(result.current.account?.accountType).toBe("ADMIN");
  });

  it("authenticates on login and keeps the token in memory", async () => {
    stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": () => errorResponse(401, "invalid_session", "expired"),
      "POST /api/v1/auth/login": () =>
        jsonResponse({
          access_token: "login-token",
          token_type: "bearer",
          expires_in: 300,
          account: accountJson({ roles: ["HR", "INTERVIEWER"] }),
        }),
    });
    const queryClient = testQueryClient();
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(queryClient) });
    await waitFor(() => expect(result.current.status).toBe("anonymous"));

    await result.current.login("employee@sis.hust.edu.vn", "password-value");
    await waitFor(() => expect(result.current.status).toBe("authenticated"));
    expect(currentAccessToken()).toBe("login-token");
    expect(window.localStorage.length).toBe(0);
  });

  it("clears the identity and caches on logout", async () => {
    stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": sessionResponse,
      "GET /api/v1/auth/me": () => jsonResponse(adminAccountJson()),
      "POST /api/v1/auth/logout": () => jsonResponse(null, 204),
    });
    const queryClient = testQueryClient();
    queryClient.setQueryData(["accounts"], [{ id: "cached" }]);
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(queryClient) });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    await result.current.logout();
    await waitFor(() => expect(result.current.status).toBe("anonymous"));
    expect(currentAccessToken()).toBeNull();
    expect(queryClient.getQueryData(["accounts"])).toBeUndefined();
  });

  it("does not apply a refresh result that arrives after logout", async () => {
    const gate = Promise.withResolvers<void>();
    stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": async () => {
        await gate.promise;
        return sessionResponse();
      },
    });

    const refreshPromise = refreshSession();
    endSession();
    gate.resolve();

    await expect(refreshPromise).resolves.toBe(false);
    expect(currentAccessToken()).toBeNull();
  });

  it("requests a fresh CSRF proof for cookie-based operations", async () => {
    const { calls } = stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": sessionResponse,
      "GET /api/v1/auth/me": () => jsonResponse(adminAccountJson()),
      "POST /api/v1/auth/logout": () => jsonResponse(null, 204),
    });
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(testQueryClient()) });
    await waitFor(() => expect(result.current.status).toBe("authenticated"));

    await result.current.logout();
    const logoutCall = calls.find((call) => call.path === "/api/v1/auth/logout");
    expect(logoutCall?.headers["x-csrf-token"]).toBe("token-value.signature");
  });
});

describe("unsupported browsers", () => {
  it("exposes an explicit unsupported state instead of unsafe fallbacks", async () => {
    const original = Object.getOwnPropertyDescriptor(navigator, "locks");
    Object.defineProperty(navigator, "locks", { configurable: true, value: undefined });
    stubFetch({ ...CSRF_ROUTE });
    try {
      const { result } = renderHook(() => useAuth(), { wrapper: wrapper(testQueryClient()) });
      await waitFor(() => expect(result.current.status).toBe("unsupported"));
    } finally {
      if (original) Object.defineProperty(navigator, "locks", original);
      vi.restoreAllMocks();
    }
  });
});
