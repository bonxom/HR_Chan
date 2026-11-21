import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { AccountPage } from "@/features/auth/AccountPage";
import { HrDashboardOverview } from "@/features/hr/HrDashboardOverview";
import { JobBoard } from "@/features/jobs/JobBoard";
import { DashboardLayout } from "@/shared/layouts/DashboardLayout";
import { CSRF_ROUTE, jsonResponse, stubFetch } from "@/test/apiStub";
import { accountJson } from "@/test/fixtures";
import { MockDataBadge, MockDataBanner } from "./MockDataIndicator";

function renderWithAuth(ui: ReactNode, initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/app" element={<DashboardLayout />}>
              <Route path="hr" element={<HrDashboardOverview />} />
              <Route path="account" element={<AccountPage />} />
            </Route>
            <Route path="/" element={ui} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

function stubEmployeeSession() {
  const account = accountJson({ roles: ["HR"] });
  stubFetch({
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({
        access_token: "token",
        token_type: "bearer",
        expires_in: 300,
        account,
      }),
    "GET /api/v1/auth/me": () => jsonResponse(account),
  });
}

describe("MockDataIndicator", () => {
  it("renders MockDataBadge variants and MockDataBanner with custom description", () => {
    render(
      <div>
        <MockDataBadge variant="sidebar" />
        <MockDataBanner description="Đang dùng dữ liệu giả lập từ mockStore." />
      </div>,
    );

    expect(screen.getByText("MOCK")).toBeInTheDocument();
    expect(screen.getByTestId("mock-data-banner")).toHaveTextContent("DỮ LIỆU MOCK");
    expect(screen.getByTestId("mock-data-banner")).toHaveTextContent(
      "Đang dùng dữ liệu giả lập từ mockStore.",
    );
  });

  it("marks only mocked navigation items and omits the mock banner on real API pages", async () => {
    stubEmployeeSession();
    renderWithAuth(null, "/app/account");

    const accountHeading = await screen.findByRole("heading", { name: "Tài khoản của tôi" });
    expect(accountHeading).toBeInTheDocument();
    expect(screen.queryByTestId("mock-data-banner")).not.toBeInTheDocument();

    const nav = screen.getByRole("navigation");
    const hrLink = within(nav).getByRole("link", { name: /Tổng quan Tuyển dụng/ });
    const accountLink = within(nav).getByRole("link", { name: /Tài khoản của tôi/ });

    expect(within(hrLink).getByText("MOCK")).toBeInTheDocument();
    expect(within(accountLink).queryByText("MOCK")).not.toBeInTheDocument();
  });

  it("renders the mock data banner on mocked workspace and candidate pages", async () => {
    stubEmployeeSession();
    renderWithAuth(null, "/app/hr");

    expect(await screen.findByTestId("mock-data-banner")).toBeInTheDocument();
  });

  it("renders the mock data banner on the candidate job board", () => {
    render(
      <MemoryRouter>
        <JobBoard />
      </MemoryRouter>,
    );

    expect(screen.getByTestId("mock-data-banner")).toBeInTheDocument();
  });
});
