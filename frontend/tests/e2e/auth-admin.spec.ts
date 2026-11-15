import { expect, test } from "@playwright/test";
import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  apiBaseUrl,
  completePassword,
  latestTokenFor,
  loginViaApi,
  postJson,
} from "./support";

const EMPLOYEE_EMAIL = "e2e.employee@sis.hust.edu.vn";
const EMPLOYEE_PASSWORD = "e2e-employee-password";
const RESET_PASSWORD = "e2e-reset-password";

test("administers an employee lifecycle end to end", async ({ browser, page }) => {
  await page.goto("/login");
  await page.getByLabel("Email công việc").fill(ADMIN_EMAIL);
  await page.getByLabel("Mật khẩu").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/admin\/users/);

  await page.getByRole("button", { name: "Thêm tài khoản mới" }).click();
  await page.getByLabel("Họ và tên").fill("E2E Employee");
  await page.getByLabel("Email công ty").fill(EMPLOYEE_EMAIL);
  await page.getByRole("button", { name: "Tạo & gửi lời mời" }).click();

  const row = page.getByTestId(`account-row-${EMPLOYEE_EMAIL}`);
  await expect(row).toBeVisible();
  await expect(row.getByText("Chờ thiết lập")).toBeVisible();

  // Activate the invitation from the local mailbox in a separate browser context.
  const employeeContext = await browser.newContext();
  const employeePage = await employeeContext.newPage();
  await completePassword(await latestTokenFor(EMPLOYEE_EMAIL), EMPLOYEE_PASSWORD);

  await employeePage.goto("/login");
  await employeePage.getByLabel("Email công việc").fill(EMPLOYEE_EMAIL);
  await employeePage.getByLabel("Mật khẩu").fill(EMPLOYEE_PASSWORD);
  await employeePage.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(employeePage).toHaveURL(/\/app\/hr/);

  const employeeToken = await loginViaApi(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD);

  // Replace the whole role set; the change applies to the next authorization check.
  await row.getByRole("button", { name: "Vai trò" }).click();
  await page.getByLabel("Tuyển dụng (HR)").uncheck();
  await page.getByLabel("Người phỏng vấn").check();
  await page.getByRole("button", { name: "Lưu vai trò" }).click();
  await expect(row.getByText("Người phỏng vấn")).toBeVisible();

  await employeePage.goto("/app/interviewer");
  await expect(employeePage).toHaveURL(/\/app\/interviewer/);
  await expect(employeePage.getByText("Không có quyền truy cập")).toHaveCount(0);

  // Locking revokes sessions: the previously issued JWT is rejected by the backend.
  await row.getByRole("button", { name: "Khóa" }).click();
  await page.getByLabel("Lý do (bắt buộc)").fill("E2E security review");
  await page.getByRole("button", { name: "Xác nhận" }).click();
  await expect(row.getByText("Đã khóa")).toBeVisible();

  const denied = await fetch(`${apiBaseUrl}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${employeeToken}` },
  });
  expect(denied.status).toBe(401);
  await employeePage.goto("/app/interviewer");
  await expect(employeePage).toHaveURL(/\/login/);

  // Unlock requires a fresh reset before the account works again.
  await row.getByRole("button", { name: "Mở khóa" }).click();
  await expect(row.getByText("Cần đặt lại mật khẩu")).toBeVisible();

  const resetResponse = await postJson("/api/v1/auth/password/recovery", {
    email: EMPLOYEE_EMAIL,
  });
  expect(resetResponse.status).toBe(202);
  await new Promise((resolve) => setTimeout(resolve, 1500));
  const resetToken = await latestTokenFor(EMPLOYEE_EMAIL);
  await employeePage.goto(`/set-password#token=${resetToken}`);
  await employeePage.getByLabel("Mật khẩu mới").fill(RESET_PASSWORD);
  await employeePage.getByLabel("Xác nhận mật khẩu").fill(RESET_PASSWORD);
  await employeePage.getByRole("button", { name: "Lưu mật khẩu" }).click();
  await expect(employeePage.getByRole("status")).toContainText("Mật khẩu đã được cập nhật");

  await employeePage.goto("/login");
  await employeePage.getByLabel("Email công việc").fill(EMPLOYEE_EMAIL);
  await employeePage.getByLabel("Mật khẩu").fill(RESET_PASSWORD);
  await employeePage.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(employeePage).toHaveURL(/\/app\/interviewer/);

  await employeeContext.close();
});
