import { expect, test } from "@playwright/test";
import { createOpenJob, latestOtpFor, minimalPdf, psql } from "./support";

// Trace/video/screenshot would record the typed OTP and capability token: keep them off here.
test.use({ trace: "off", video: "off", screenshot: "off" });

// Needs the API with real SMTP (Mailpit), ClamAV, CV storage and Turnstile test keys, a worker,
// and the frontend built with VITE_TURNSTILE_SITE_KEY set to the matching test site key.
test("candidate applies with a real CV and email OTP", async ({ page }) => {
  const stamp = Date.now();
  const title = `E2E Kỹ sư dữ liệu ${stamp}`;
  const email = `e2e.candidate.${stamp}@example.test`;
  await createOpenJob(title);

  await page.goto("/");
  const card = page.getByRole("article").filter({ hasText: title });
  await card.getByRole("button", { name: "Ứng tuyển ngay" }).click();

  await page.getByLabel(/họ và tên/i).fill("Nguyen Van E2E");
  await page.getByLabel(/^email/i).fill(email);
  await page.getByLabel(/số điện thoại/i).fill("0912345678");
  await page.getByLabel(/tệp cv/i).setInputFiles({
    name: "cv.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf("Nguyen Van E2E Backend Developer"),
  });
  await page.getByLabel(/đồng ý/i).check();
  await expect(page.locator('input[name="cf-turnstile-response"]')).not.toHaveValue("", {
    timeout: 30_000,
  });
  // The hero also has a "Tải CV lên" button; scope to the modal form.
  await page.locator("#apply-top").getByRole("button", { name: "Tải CV lên" }).click();

  const code = page.getByLabel(/mã xác thực/i);
  await expect(code).toBeVisible();
  await code.fill(await latestOtpFor(email));
  await page.getByRole("button", { name: /xác nhận/i }).click();
  await expect(page.getByText(/cảm ơn/i)).toBeVisible();

  const count = (sql: string) => Number(psql(sql));
  const byEmail = `c.email = '${email}'`;
  expect(
    count(`SELECT count(*) FROM applications a JOIN candidates c ON c.id = a.candidate_id WHERE ${byEmail}`),
  ).toBe(1);
  // OTP is masked in the outbox and no thank-you email is queued.
  // Chỉ nhận chuỗi đúng sáu chữ số; timestamp dài trong tên tin không phải mã OTP.
  expect(count(`SELECT count(*) FROM email_outbox WHERE to_email = '${email}' AND body ~ '(^|[^0-9])[0-9]{6}([^0-9]|$)'`)).toBe(0);
  expect(count(`SELECT count(*) FROM email_outbox WHERE to_email = '${email}' AND template_code <> 'OTP_APPLY'`)).toBe(0);
});

test("job board fits a 360px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto("/");
  await expect(page.getByRole("textbox", { name: /tìm kiếm/i })).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});
