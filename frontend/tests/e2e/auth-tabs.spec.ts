import { expect, test } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD } from "./support";

test("shares one session across tabs and isolates credentials from storage", async ({
  context,
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Email công việc").fill(ADMIN_EMAIL);
  await page.getByLabel("Mật khẩu").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/admin\/users/);

  const storage = await page.evaluate(() => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
  }));
  expect(storage.local).toHaveLength(0);
  expect(storage.session).toHaveLength(0);

  const second = await context.newPage();
  await second.goto("/app/admin/logs");
  await expect(second.getByRole("heading", { name: /Nhật ký kiểm toán/ })).toBeVisible();

  // Concurrent reloads rotate the refresh cookie; replay protection must not fire.
  await Promise.all([page.reload(), second.reload()]);
  await expect(page).toHaveURL(/\/app\/admin\/users/);
  await expect(second.getByRole("heading", { name: /Nhật ký kiểm toán/ })).toBeVisible();

  await page.getByRole("button", { name: "Đăng xuất" }).first().click();
  await expect(page).toHaveURL(/\/login/);
  await expect(second).toHaveURL(/\/login/, { timeout: 20_000 });
});
