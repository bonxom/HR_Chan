// Mục menu của trang dùng API thật không được gắn nhãn MOCK; trang còn dữ liệu giả thì có.
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { CSRF_ROUTE, jsonResponse, stubFetch } from "@/test/apiStub";
import { accountJson } from "@/test/fixtures";
import { DashboardLayout } from "./DashboardLayout";

function renderLayout() {
  const account = accountJson({ roles: ["HR"] });
  stubFetch({
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({ access_token: "hr-token", token_type: "bearer", expires_in: 300, account }),
    "GET /api/v1/auth/me": () => jsonResponse(account),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/app/hr/jobs"]}>
          <Routes>
            <Route path="/app" element={<DashboardLayout />}>
              <Route path="*" element={<p>Nội dung trang</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("DashboardLayout — nhãn dữ liệu MOCK", () => {
  it("không gắn MOCK cho trang tin tuyển dụng dùng API thật", async () => {
    renderLayout();
    await screen.findByText("Nội dung trang");
    const nav = screen.getByRole("navigation");
    const jobsLink = within(nav).getByRole("link", { name: /Tin tuyển dụng & Tiêu chí/ });
    expect(within(jobsLink).queryByText("MOCK")).not.toBeInTheDocument();
  });

  it("không còn gắn MOCK cho pipeline hồ sơ đã dùng API thật", async () => {
    renderLayout();
    await screen.findByText("Nội dung trang");
    const nav = screen.getByRole("navigation");
    const pipelineLink = within(nav).getByRole("link", { name: /Pipeline Hồ sơ ứng tuyển/ });
    expect(within(pipelineLink).queryByText("MOCK")).not.toBeInTheDocument();
  });
});
