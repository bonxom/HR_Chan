import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it } from "vitest";
import { AuthProvider } from "./AuthProvider";
import { AccountPage } from "./AccountPage";
import { CompletePasswordPage } from "./CompletePasswordPage";
import { LoginPage } from "./LoginPage";
import { RecoveryPage } from "./RecoveryPage";
import { CSRF_ROUTE, errorResponse, jsonResponse, stubFetch } from "@/test/apiStub";
import { accountJson, adminAccountJson } from "@/test/fixtures";

function renderRoutes(routes: ReactNode, initialEntries: string[] = ["/login"]) {
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

const anonymousRefresh = {
  "POST /api/v1/auth/refresh": () => errorResponse(401, "invalid_session", "expired"),
};

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

describe("LoginPage", () => {
  it("signs in and navigates to the landing workspace for the account type", async () => {
    const user = userEvent.setup();
    const { calls } = stubFetch({
      ...CSRF_ROUTE,
      ...anonymousRefresh,
      "POST /api/v1/auth/login": () =>
        jsonResponse({
          access_token: "login-token",
          token_type: "bearer",
          expires_in: 300,
          account: adminAccountJson(),
        }),
    });

    renderRoutes(
      <>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app/admin/users" element={<div>admin workspace</div>} />
      </>,
    );

    await user.type(screen.getByLabelText("Email công việc"), "admin@sis.hust.edu.vn");
    await user.type(screen.getByLabelText("Mật khẩu"), "administrator-password-value");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByText("admin workspace")).toBeInTheDocument();
    const loginCall = calls.find((call) => call.path === "/api/v1/auth/login");
    expect(loginCall?.body).toEqual({
      email: "admin@sis.hust.edu.vn",
      password: "administrator-password-value",
    });
  });

  it("offers one-click development logins through the dev endpoint", async () => {
    const user = userEvent.setup();
    const { calls } = stubFetch({
      ...CSRF_ROUTE,
      ...anonymousRefresh,
      "POST /api/v1/auth/dev-login": () =>
        jsonResponse({
          access_token: "dev-hr-token",
          token_type: "bearer",
          expires_in: 300,
          account: accountJson(),
        }),
    });

    renderRoutes(
      <>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app/hr" element={<div>hr workspace</div>} />
      </>,
    );

    await user.click(screen.getByRole("button", { name: "Đăng nhập nhanh HR" }));
    expect(await screen.findByText("hr workspace")).toBeInTheDocument();

    const loginCall = calls.find((call) => call.path === "/api/v1/auth/dev-login");
    expect(loginCall?.body).toEqual({ persona: "hr" });
  });

  it("explains how to enable the dev endpoint when it is switched off", async () => {
    const user = userEvent.setup();
    stubFetch({
      ...CSRF_ROUTE,
      ...anonymousRefresh,
      "POST /api/v1/auth/dev-login": () => errorResponse(404, "not_found", "Not found"),
    });

    renderRoutes(<Route path="/login" element={<LoginPage />} />);
    await user.click(screen.getByRole("button", { name: "Đăng nhập nhanh Manager" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("DEV_LOGIN_ENABLED");
  });

  it("surfaces the account status when a dev persona is not active", async () => {
    const user = userEvent.setup();
    stubFetch({
      ...CSRF_ROUTE,
      ...anonymousRefresh,
      "POST /api/v1/auth/dev-login": () =>
        errorResponse(
          409,
          "invalid_status_transition",
          "Dev account dev.trainee@sis.hust.edu.vn is PASSWORD_RESET_REQUIRED; unlock it or run seed-dev-accounts.",
        ),
    });

    renderRoutes(<Route path="/login" element={<LoginPage />} />);
    await user.click(screen.getByRole("button", { name: "Đăng nhập nhanh Trainee" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("PASSWORD_RESET_REQUIRED");
  });

  it("shows a generic message for rejected credentials", async () => {
    const user = userEvent.setup();
    stubFetch({
      ...CSRF_ROUTE,
      ...anonymousRefresh,
      "POST /api/v1/auth/login": () =>
        errorResponse(401, "invalid_credentials", "Incorrect email or password"),
    });

    renderRoutes(<Route path="/login" element={<LoginPage />} />);
    await user.type(screen.getByLabelText("Email công việc"), "nobody@sis.hust.edu.vn");
    await user.type(screen.getByLabelText("Mật khẩu"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email hoặc mật khẩu không đúng.",
    );
  });

  it("points to the missing backend secrets when authentication is unconfigured", async () => {
    const user = userEvent.setup();
    stubFetch({
      ...CSRF_ROUTE,
      ...anonymousRefresh,
      "POST /api/v1/auth/login": () =>
        errorResponse(
          503,
          "authentication_unavailable",
          "Authentication is not configured: add JWT_SECRET",
        ),
    });

    renderRoutes(<Route path="/login" element={<LoginPage />} />);
    await user.type(screen.getByLabelText("Email công việc"), "dev.hr@sis.hust.edu.vn");
    await user.type(screen.getByLabelText("Mật khẩu"), "dev-only-password");
    await user.click(screen.getByRole("button", { name: /^Đăng nhập$/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("JWT_SECRET");
  });

  it("validates required fields before calling the API", async () => {
    const user = userEvent.setup();
    const { calls } = stubFetch({ ...CSRF_ROUTE, ...anonymousRefresh });
    renderRoutes(<Route path="/login" element={<LoginPage />} />);

    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Vui lòng nhập email và mật khẩu.",
    );
    expect(calls.some((call) => call.path === "/api/v1/auth/login")).toBe(false);
  });
});

describe("RecoveryPage", () => {
  it("shows the same generic outcome for any address", async () => {
    const user = userEvent.setup();
    const { calls } = stubFetch({
      "POST /api/v1/auth/password/recovery": () => jsonResponse({ status: "accepted" }, 202),
    });
    renderRoutes(<Route path="/forgot-password" element={<RecoveryPage />} />, [
      "/forgot-password",
    ]);
    await waitFor(() => expect(calls.length).toBe(0));

    await user.type(screen.getByLabelText("Email công việc"), "unknown@sis.hust.edu.vn");
    await user.click(screen.getByRole("button", { name: "Gửi liên kết đặt lại" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Nếu email hợp lệ và thuộc tài khoản đang hoạt động",
    );
  });

  it("keeps the generic outcome even when the request is throttled", async () => {
    const user = userEvent.setup();
    stubFetch({
      "POST /api/v1/auth/password/recovery": () =>
        errorResponse(429, "rate_limited", "Too many requests"),
    });
    renderRoutes(<Route path="/forgot-password" element={<RecoveryPage />} />, [
      "/forgot-password",
    ]);

    await user.type(screen.getByLabelText("Email công việc"), "person@sis.hust.edu.vn");
    await user.click(screen.getByRole("button", { name: "Gửi liên kết đặt lại" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Nếu email hợp lệ");
    expect(screen.getByText(/Bạn đã gửi quá nhiều yêu cầu/)).toBeInTheDocument();
  });
});

describe("CompletePasswordPage", () => {
  it("removes the fragment token from the URL and submits it once", async () => {
    window.history.replaceState(null, "", "/set-password#token=single-use-token");
    const user = userEvent.setup();
    const { calls } = stubFetch({
      "POST /api/v1/auth/password/complete": () => jsonResponse(null, 204),
    });

    renderRoutes(<Route path="/set-password" element={<CompletePasswordPage />} />, [
      "/set-password",
    ]);
    expect(window.location.hash).toBe("");

    await user.type(screen.getByLabelText("Mật khẩu mới"), "brand-new-password");
    await user.type(screen.getByLabelText("Xác nhận mật khẩu"), "brand-new-password");
    await user.click(screen.getByRole("button", { name: "Lưu mật khẩu" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Mật khẩu đã được cập nhật",
    );
    const completeCall = calls.find((call) => call.path === "/api/v1/auth/password/complete");
    expect(completeCall?.body).toEqual({
      token: "single-use-token",
      new_password: "brand-new-password",
    });
  });

  it("shows a safe message when the link cannot be used", async () => {
    window.history.replaceState(null, "", "/set-password#token=expired-token");
    const user = userEvent.setup();
    stubFetch({
      "POST /api/v1/auth/password/complete": () =>
        errorResponse(400, "invalid_password_link", "This password link is invalid"),
    });

    renderRoutes(<Route path="/set-password" element={<CompletePasswordPage />} />, [
      "/set-password",
    ]);
    await user.type(screen.getByLabelText("Mật khẩu mới"), "brand-new-password");
    await user.type(screen.getByLabelText("Xác nhận mật khẩu"), "brand-new-password");
    await user.click(screen.getByRole("button", { name: "Lưu mật khẩu" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Liên kết không hợp lệ hoặc đã hết hạn",
    );
    expect(screen.getByRole("link", { name: "Yêu cầu liên kết mới" })).toBeInTheDocument();
  });

  it("validates password length and confirmation locally", async () => {
    window.history.replaceState(null, "", "/set-password#token=some-token");
    const user = userEvent.setup();
    const { calls } = stubFetch({});
    renderRoutes(<Route path="/set-password" element={<CompletePasswordPage />} />, [
      "/set-password",
    ]);

    await user.type(screen.getByLabelText("Mật khẩu mới"), "short");
    await user.type(screen.getByLabelText("Xác nhận mật khẩu"), "short");
    await user.click(screen.getByRole("button", { name: "Lưu mật khẩu" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("8 đến 128 ký tự");

    await user.clear(screen.getByLabelText("Mật khẩu mới"));
    await user.type(screen.getByLabelText("Mật khẩu mới"), "long-enough-password");
    await user.click(screen.getByRole("button", { name: "Lưu mật khẩu" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Xác nhận mật khẩu không khớp");
    expect(calls.some((call) => call.path === "/api/v1/auth/password/complete")).toBe(false);
  });
});

describe("AccountPage", () => {
  it("changes the password and reports the revoked sessions", async () => {
    const user = userEvent.setup();
    stubFetch({
      ...CSRF_ROUTE,
      "POST /api/v1/auth/refresh": () =>
        jsonResponse({
          access_token: "session-token",
          token_type: "bearer",
          expires_in: 300,
          account: accountJson(),
        }),
      "GET /api/v1/auth/me": () => jsonResponse(accountJson()),
      "POST /api/v1/auth/password/change": () =>
        jsonResponse({
          access_token: "rotated-token",
          token_type: "bearer",
          expires_in: 300,
          account: accountJson(),
        }),
    });

    renderRoutes(<Route path="/app/account" element={<AccountPage />} />, ["/app/account"]);
    expect(await screen.findByText("employee@sis.hust.edu.vn")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Mật khẩu hiện tại"), "employee-password-value");
    await user.type(screen.getByLabelText("Mật khẩu mới"), "replacement-password");
    await user.type(screen.getByLabelText("Xác nhận mật khẩu mới"), "replacement-password");
    await user.click(screen.getByRole("button", { name: "Cập nhật mật khẩu" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Các phiên đăng nhập khác đã bị thu hồi",
    );
  });
});
