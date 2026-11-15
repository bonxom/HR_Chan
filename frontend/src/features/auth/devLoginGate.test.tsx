import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider } from "./AuthProvider";
import { LoginPage } from "./LoginPage";
import { CSRF_ROUTE, errorResponse, stubFetch } from "@/test/apiStub";

// Simulates the production build, where `import.meta.env.DEV` is false and the
// quick-login panel must never render.
vi.mock("./devLogins", () => ({
  devLoginsEnabled: false,
  DEV_LOGINS: [],
}));

describe("development login gate", () => {
  it("renders no quick-login controls outside development", async () => {
    stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": () => errorResponse(401, "invalid_session", "expired"),
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/login"]}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("button", { name: "Đăng nhập" })).toBeInTheDocument();
    expect(screen.queryByText(/Đăng nhập nhanh/)).not.toBeInTheDocument();
    expect(screen.queryByText(/seed-dev-accounts/)).not.toBeInTheDocument();
  });
});
