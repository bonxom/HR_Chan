import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { UserManagement, applyRoleSelection } from "./UserManagement";
import { CSRF_ROUTE, jsonResponse, stubFetch } from "@/test/apiStub";
import { accountJson, adminAccountJson } from "@/test/fixtures";

function renderAdmin(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/app/admin/users"]}>
          <Routes>
            <Route path="/app/admin/users" element={ui} />
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

describe("applyRoleSelection", () => {
  it("keeps probation exclusive and preserves the other roles", () => {
    expect(applyRoleSelection(["HR", "INTERVIEWER"], "PROBATION", true)).toEqual(["PROBATION"]);
    expect(applyRoleSelection(["PROBATION"], "HR", true)).toEqual(["HR"]);
    expect(applyRoleSelection(["HR", "PROBATION"], "PROBATION", false)).toEqual(["HR"]);
    expect(applyRoleSelection(["HR"], "INTERVIEWER", true)).toEqual(["HR", "INTERVIEWER"]);
    expect(applyRoleSelection(["HR"], "HR", false)).toEqual([]);
  });
});

describe("UserManagement", () => {
  it("renders each lifecycle status distinctly", async () => {
    const accounts = [
      accountJson({ id: "1", email: "pending@sis.hust.edu.vn", status: "PENDING_SETUP" }),
      accountJson({ id: "2", email: "active@sis.hust.edu.vn", status: "ACTIVE" }),
      accountJson({ id: "3", email: "locked@sis.hust.edu.vn", status: "LOCKED" }),
      accountJson({ id: "4", email: "reset@sis.hust.edu.vn", status: "PASSWORD_RESET_REQUIRED" }),
      accountJson({ id: "5", email: "disabled@sis.hust.edu.vn", status: "DISABLED" }),
    ];
    stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/accounts": () => jsonResponse({ items: accounts, next_cursor: null }),
    });

    renderAdmin(<UserManagement />);
    expect(await screen.findByText("pending@sis.hust.edu.vn")).toBeInTheDocument();
    const table = screen.getByRole("table");
    for (const label of [
      "Chờ thiết lập",
      "Đang hoạt động",
      "Đã khóa",
      "Cần đặt lại mật khẩu",
      "Đã vô hiệu hóa",
    ]) {
      expect(within(table).getByText(label)).toBeInTheDocument();
    }
  });

  it("creates an account with the chosen roles and reports delivery failure", async () => {
    const user = userEvent.setup();
    const { calls } = stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/accounts": () => jsonResponse({ items: [], next_cursor: null }),
      "POST /api/v1/accounts": () =>
        jsonResponse(
          {
            account: accountJson({
              email: "new.hire@sis.hust.edu.vn",
              roles: ["HR", "INTERVIEWER"],
            }),
            email_delivery: "failed",
          },
          201,
        ),
    });

    renderAdmin(<UserManagement />);
    await user.click(await screen.findByRole("button", { name: "Thêm tài khoản mới" }));
    await user.type(screen.getByLabelText("Họ và tên"), "New Hire");
    await user.type(screen.getByLabelText("Email công ty"), "new.hire@sis.hust.edu.vn");
    await user.click(screen.getByLabelText("Người phỏng vấn"));
    await user.click(screen.getByRole("button", { name: "Tạo & gửi lời mời" }));

    const createCall = calls.find(
      (call) => call.method === "POST" && call.path === "/api/v1/accounts",
    );
    expect(createCall?.body).toEqual({
      full_name: "New Hire",
      email: "new.hire@sis.hust.edu.vn",
      account_type: "EMPLOYEE",
      roles: ["HR", "INTERVIEWER"],
    });
    expect(
      await screen.findByText(/email lời mời chưa gửi được/),
    ).toBeInTheDocument();
  });

  it("requires a reason before locking an account", async () => {
    const user = userEvent.setup();
    const active = accountJson({ email: "active@sis.hust.edu.vn", status: "ACTIVE" });
    const { calls } = stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/accounts": () => jsonResponse({ items: [active], next_cursor: null }),
      [`POST /api/v1/accounts/${active.id}/lock`]: () =>
        jsonResponse(accountJson({ ...active, status: "LOCKED" })),
    });

    renderAdmin(<UserManagement />);
    const row = await screen.findByTestId("account-row-active@sis.hust.edu.vn");
    await user.click(within(row).getByRole("button", { name: "Khóa" }));
    await user.click(screen.getByRole("button", { name: "Xác nhận" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Bắt buộc nhập lý do.");

    await user.type(screen.getByLabelText("Lý do (bắt buộc)"), "security review");
    await user.click(screen.getByRole("button", { name: "Xác nhận" }));

    const lockCall = calls.find((call) => call.path.endsWith("/lock"));
    expect(lockCall?.body).toEqual({ reason: "security review" });
  });

  it("disables self-lock and self-disable controls", async () => {
    stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/accounts": () =>
        jsonResponse({ items: [adminAccountJson()], next_cursor: null }),
    });

    renderAdmin(<UserManagement />);
    const row = await screen.findByTestId("account-row-admin@sis.hust.edu.vn");
    expect(within(row).getByRole("button", { name: "Khóa" })).toBeDisabled();
    expect(within(row).getByRole("button", { name: "Vô hiệu hóa" })).toBeDisabled();
    expect(within(row).queryByRole("button", { name: "Vai trò" })).not.toBeInTheDocument();
  });

  it("offers invitation resend only for accounts awaiting setup or reset", async () => {
    const pending = accountJson({
      id: "1",
      email: "pending@sis.hust.edu.vn",
      status: "PENDING_SETUP",
    });
    const active = accountJson({ id: "2", email: "active@sis.hust.edu.vn", status: "ACTIVE" });
    stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/accounts": () => jsonResponse({ items: [pending, active], next_cursor: null }),
    });

    renderAdmin(<UserManagement />);
    const pendingRow = await screen.findByTestId("account-row-pending@sis.hust.edu.vn");
    const activeRow = screen.getByTestId("account-row-active@sis.hust.edu.vn");
    expect(within(pendingRow).getByRole("button", { name: "Gửi lại lời mời" })).toBeInTheDocument();
    expect(within(activeRow).queryByRole("button", { name: "Gửi lại lời mời" })).toBeNull();
  });
});

describe("reset email guidance", () => {
  it("points development operators to the local mailbox after resending", async () => {
    const user = userEvent.setup();
    const pending = accountJson({
      id: "33",
      email: "pending@sis.hust.edu.vn",
      status: "PENDING_SETUP",
    });
    stubFetch({
      ...adminSessionRoutes(),
      "GET /api/v1/accounts": () => jsonResponse({ items: [pending], next_cursor: null }),
      [`POST /api/v1/accounts/${pending.id}/invitation`]: () =>
        jsonResponse({ account: pending, email_delivery: "sent" }),
    });

    renderAdmin(<UserManagement />);
    const row = await screen.findByTestId("account-row-pending@sis.hust.edu.vn");
    await user.click(within(row).getByRole("button", { name: "Gửi lại lời mời" }));
    expect(await screen.findByText(/Mailpit/)).toBeInTheDocument();
  });
});
