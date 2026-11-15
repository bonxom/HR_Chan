import { expect, test } from "@playwright/test";

test("quick login signs an employee into the matching workspace", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng nhập nhanh HR" }).click();
  await expect(page).toHaveURL(/\/app\/hr/);
  await expect(page.getByText("Dev HR").first()).toBeVisible();

  const storage = await page.evaluate(() => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage),
  }));
  expect(storage.local).toHaveLength(0);
  expect(storage.session).toHaveLength(0);
});

test("quick login reaches the admin workspace", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Đăng nhập nhanh Admin" }).click();
  await expect(page).toHaveURL(/\/app\/admin\/users/);
  await expect(page.getByRole("heading", { name: /Quản lý Tài khoản/ })).toBeVisible();
});
