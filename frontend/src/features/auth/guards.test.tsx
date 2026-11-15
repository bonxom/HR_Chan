import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "./AuthProvider";
import {
  RequireAccess,
  RequireAuth,
  canAccess,
  landingPathFor,
} from "./RequireAuth";
import { CSRF_ROUTE, errorResponse, jsonResponse, stubFetch } from "@/test/apiStub";
import { accountJson, authAccount } from "@/test/fixtures";

function renderGuards(routes: ReactNode, initialEntries: string[] = ["/app/hr"]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>{routes}</Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

function authenticatedAs(account = accountJson()) {
  return {
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({
        access_token: "guard-token",
        token_type: "bearer",
        expires_in: 300,
        account,
      }),
    "GET /api/v1/auth/me": () => jsonResponse(account),
  };
}

describe("RequireAuth", () => {
  it("shows a loading state before the session is known", () => {
    stubFetch(authenticatedAs());
    renderGuards(
      <>
        <Route
          path="/app/hr"
          element={
            <RequireAuth>
              <div>protected content</div>
            </RequireAuth>
          }
        />
        <Route path="/login" element={<div>login page</div>} />
      </>,
    );
    expect(screen.getByText("Đang xác thực phiên làm việc…")).toBeInTheDocument();
  });

  it("redirects anonymous visitors to login", async () => {
    stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": () => errorResponse(401, "invalid_session", "expired"),
    });
    renderGuards(
      <>
        <Route
          path="/app/hr"
          element={
            <RequireAuth>
              <div>protected content</div>
            </RequireAuth>
          }
        />
        <Route path="/login" element={<div>login page</div>} />
      </>,
    );
    expect(await screen.findByText("login page")).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("renders children for an authenticated reload", async () => {
    stubFetch(authenticatedAs());
    renderGuards(
      <Route
        path="/app/hr"
        element={
          <RequireAuth>
            <div>protected content</div>
          </RequireAuth>
        }
      />,
    );
    expect(await screen.findByText("protected content")).toBeInTheDocument();
  });
});

describe("RequireAccess", () => {
  it("shows an explicit denial for an unauthorized deep link", async () => {
    stubFetch(authenticatedAs(accountJson({ roles: ["INTERVIEWER"] })));
    renderGuards(
      <Route
        path="/app/hr"
        element={
          <RequireAccess roles={["HR"]}>
            <div>hr section</div>
          </RequireAccess>
        }
      />,
    );

    expect(await screen.findByText("Không có quyền truy cập")).toBeInTheDocument();
    expect(screen.queryByText("hr section")).not.toBeInTheDocument();
  });

  it("allows every section matching the union of employee roles", async () => {
    stubFetch(authenticatedAs(accountJson({ roles: ["HR", "INTERVIEWER"] })));
    renderGuards(
      <>
        <Route
          path="/app/hr"
          element={
            <RequireAccess roles={["HR"]}>
              <div>hr section</div>
            </RequireAccess>
          }
        />
        <Route
          path="/app/interviewer"
          element={
            <RequireAccess roles={["INTERVIEWER"]}>
              <div>interviewer section</div>
            </RequireAccess>
          }
        />
        <Route
          path="/app/admin"
          element={
            <RequireAccess accountType="ADMIN">
              <div>admin section</div>
            </RequireAccess>
          }
        />
      </>,
      ["/app/hr"],
    );

    expect(await screen.findByText("hr section")).toBeInTheDocument();
    expect(canAccess(authAccount({ roles: ["HR", "INTERVIEWER"] }), { roles: ["INTERVIEWER"] })).toBe(
      true,
    );
    expect(canAccess(authAccount({ roles: ["HR"] }), { accountType: "ADMIN" })).toBe(false);
  });

  it("keeps admin sections closed to employees and employee sections closed to admins", async () => {
    stubFetch(authenticatedAs(accountJson()));
    renderGuards(
      <Route
        path="/app/hr"
        element={
          <RequireAccess roles={["HR"]}>
            <div>hr section</div>
          </RequireAccess>
        }
      />,
      ["/app/hr"],
    );
    expect(await screen.findByText("hr section")).toBeInTheDocument();
    expect(canAccess(authAccount({ accountType: "ADMIN", roles: [] }), { roles: ["HR"] })).toBe(
      false,
    );
    expect(canAccess(authAccount({ accountType: "ADMIN", roles: [] }), { accountType: "ADMIN" })).toBe(
      true,
    );
  });
});

describe("landingPathFor", () => {
  it("chooses the landing section from account type and roles", () => {
    expect(landingPathFor(authAccount({ accountType: "ADMIN", roles: [] }))).toBe(
      "/app/admin/users",
    );
    expect(landingPathFor(authAccount({ roles: ["HR", "PROBATION"] }))).toBe("/app/hr");
    expect(landingPathFor(authAccount({ roles: ["INTERVIEWER"] }))).toBe("/app/interviewer");
    expect(landingPathFor(authAccount({ roles: ["DEPT_MANAGER"] }))).toBe("/app/manager");
    expect(landingPathFor(authAccount({ roles: ["PROBATION"] }))).toBe("/app/trainee");
    expect(
      landingPathFor(authAccount({ accountType: "ADMIN", roles: [] })),
    ).toBe("/app/admin/users");
  });

  it("falls back to the account page for an unidentified employee role set", () => {
    expect(landingPathFor(authAccount({ roles: [] }))).toBe("/app/account");
  });
});
