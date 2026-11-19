// Trang dùng API thật phải khác trang minh họa ở cảnh báo dữ liệu mẫu.
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { CSRF_ROUTE, jsonResponse, stubFetch } from "@/test/apiStub";
import { accountJson } from "@/test/fixtures";
import { DashboardLayout } from "./DashboardLayout";

const DEMO_NOTICE = /dữ liệu minh họa/;

function renderAt(path: string) {
  stubFetch({
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({ access_token: "hr-token", token_type: "bearer", expires_in: 300, account: accountJson() }),
    "GET /api/v1/auth/me": () => jsonResponse(accountJson()),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
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

describe("DashboardLayout — cảnh báo dữ liệu minh họa", () => {
  it("vẫn hiện trên trang còn dùng dữ liệu giả", async () => {
    renderAt("/app/hr/applications");
    await screen.findByText("Nội dung trang");
    expect(screen.getByText(DEMO_NOTICE)).toBeInTheDocument();
  });

  it.each(["/app/hr/jobs", "/app/account"])("không hiện trên trang đã dùng API thật: %s", async (path) => {
    renderAt(path);
    await screen.findByText("Nội dung trang");
    expect(screen.queryByText(DEMO_NOTICE)).not.toBeInTheDocument();
  });
});
