import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { AuditLogs } from "./AuditLogs";
import { CSRF_ROUTE, jsonResponse, stubFetch } from "@/test/apiStub";
import { adminAccountJson } from "@/test/fixtures";

function renderAudit(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/app/admin/logs"]}>
          <Routes>
            <Route path="/app/admin/logs" element={ui} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

function adminSessionRoutes() {
  return {
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({
        access_token: "admin-token",
        token_type: "bearer",
        expires_in: 300,
        account: adminAccountJson(),
      }),
    "GET /api/v1/auth/me": () => jsonResponse(adminAccountJson()),
  };
}

const event = {
  id: "33333333-3333-4333-8333-333333333333",
  actor_id: adminAccountJson().id,
  action: "account.locked",
  outcome: "SUCCESS",
  timestamp: "2026-11-15T10:00:00Z",
  target_type: "account",
  target_id: "44444444-4444-4444-8444-444444444444",
  metadata: { reason: "security review", previous_status: "ACTIVE" },
};

describe("AuditLogs", () => {
  it("renders genuine event metadata without business payloads", async () => {
    stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/audit-events": () =>
        jsonResponse({ items: [event], next_cursor: null }),
    });

    renderAudit(<AuditLogs />);
    expect(await screen.findByText("account.locked")).toBeInTheDocument();
    expect(screen.getByText("Thành công")).toBeInTheDocument();
    expect(screen.getByText(/reason: security review/)).toBeInTheDocument();
    expect(screen.getByText(/previous_status: ACTIVE/)).toBeInTheDocument();
    expect(screen.queryByText(/password/i)).not.toBeInTheDocument();
  });

  it("sends the selected filters to the API", async () => {
    const user = userEvent.setup();
    const { calls } = stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/audit-events": () => jsonResponse({ items: [], next_cursor: null }),
    });

    renderAudit(<AuditLogs />);
    await screen.findByText("Chưa có sự kiện phù hợp.");
    await user.type(screen.getByLabelText("Hành động"), "account.created");
    await user.type(screen.getByLabelText("Target ID"), "44444444-4444-4444-8444-444444444444");
    await user.click(screen.getByRole("button", { name: "Lọc" }));

    expect(
      calls.some(
        (call) =>
          call.path.includes("action=account.created") &&
          call.path.includes("target_id=44444444-4444-4444-8444-444444444444"),
      ),
    ).toBe(true);
  });

  it("requests the next page with the cursor", async () => {
    const user = userEvent.setup();
    let firstPage = true;
    const { calls } = stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/audit-events": () => {
        if (firstPage) {
          firstPage = false;
          return jsonResponse({ items: [event], next_cursor: "next-page-cursor" });
        }
        return jsonResponse({ items: [], next_cursor: null });
      },
    });

    renderAudit(<AuditLogs />);
    await user.click(await screen.findByRole("button", { name: "Tải thêm" }));
    expect(calls.some((call) => call.path.includes("cursor=next-page-cursor"))).toBe(true);
  });
});
