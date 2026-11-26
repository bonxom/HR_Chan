import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { apiBaseUrl, createOpenJob, loginViaApi, psql } from "./support";

test.use({ trace: "off", video: "off", screenshot: "off" });

async function pendingApplication() {
  const stamp = randomUUID().replaceAll("-", "");
  const email = `response.${stamp}@example.test`;
  const jobId = await createOpenJob(`E2E response ${stamp.slice(0, 8)}`);
  // Setup only. The invitation and rejection use their normal HR HTTP entry points.
  const id = Number(psql(`
    WITH candidate AS (
      INSERT INTO candidates(email,full_name,phone) VALUES
      ('${email}','Browser Candidate','0912345678') RETURNING id
    ), submission AS (
      INSERT INTO cv_submissions(candidate_id,cv_storage_key,cv_original_name,cv_mime_type,
        cv_size_bytes,cv_sha256,cv_scan_status,consent_at,consent_policy_ver,parse_status,
        created_at,expires_at)
      SELECT id,'response-${stamp}','cv.pdf','application/pdf',20,repeat('0',64),
        'CLEAN',now(),'e2e','PENDING',now(),now()+interval '1 day'
      FROM candidate RETURNING id,candidate_id
    ), application AS (
      INSERT INTO applications(candidate_id,job_id,submission_id,status,submitted_at,
        criteria_set_id,ai_status,updated_at)
      SELECT candidate_id,${jobId},id,'PENDING_HR_REVIEW',now(),
        (SELECT current_criteria_set_id FROM job_postings WHERE id=${jobId}),
        'NEEDS_REVIEW',now() FROM submission RETURNING id
    ) SELECT id FROM application;
  `));
  const token = await loginViaApi("dev.hr@sis.hust.edu.vn", "dev-only-password");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  return { id, email, headers };
}

async function emailedResponseUrl(email: string): Promise<string> {
  const mailpit = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const list = await (await fetch(`${mailpit}/api/v1/search?query=${encodeURIComponent("to:" + email)}`)).json();
    for (const item of list.messages ?? []) {
      const mail = await (await fetch(`${mailpit}/api/v1/message/${item.ID}`)).json();
      const url = mail.Text?.match(/https?:\/\/[^\s"<>]+\/r\/[A-Za-z0-9_-]+/)?.[0];
      if (url) return url;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("Candidate response email did not arrive");
}

test("candidate opens emailed interview URL, confirms and sees the receipt", async ({ page }) => {
  const { id, email, headers } = await pendingApplication();
  const slots = await fetch(`${apiBaseUrl}/api/applications/${id}/interview-slots?date_from=${new Date().toISOString().slice(0, 10)}&date_to=${new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10)}`, { headers });
  expect(slots.ok).toBeTruthy();
  const starts = await slots.json();
  const invite = await fetch(`${apiBaseUrl}/api/applications/${id}/invite`, {
    method: "POST", headers, body: JSON.stringify({ start_at: starts[0].start_at, version: 1 }),
  });
  expect(invite.ok).toBeTruthy();
  const url = await emailedResponseUrl(email);
  await page.setViewportSize({ width: 360, height: 740 });
  await page.goto(url);
  await expect(page).toHaveURL(/\/r$/);
  await expect(page.getByRole("heading", { name: "Phản hồi lịch phỏng vấn" })).toBeVisible();
  expect(psql(`SELECT status FROM applications WHERE id=${id}`)).toBe("INTERVIEW_INVITED");
  await page.getByRole("button", { name: "Xác nhận tham dự" }).click();
  await expect(page.getByRole("heading", { name: "Đã ghi nhận phản hồi" })).toBeVisible();
  expect(psql(`SELECT status FROM applications WHERE id=${id}`)).toBe("INTERVIEW_CONFIRMED");
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Mở lại đường dẫn trong email" })).toBeVisible();
  await page.goto(url);
  await expect(page.getByText("Đường dẫn đã ghi nhận xác nhận.")).toBeVisible();
});

test("consent email requires a deliberate checkbox before saving", async ({ page }) => {
  const { id, email, headers } = await pendingApplication();
  const rejected = await fetch(`${apiBaseUrl}/api/applications/${id}/reject`, {
    method: "POST", headers, body: JSON.stringify({ reason_code: "NOT_QUALIFIED", version: 1 }),
  });
  expect(rejected.ok).toBeTruthy();
  await page.goto(await emailedResponseUrl(email));
  await expect(page).toHaveURL(/\/r$/);
  const checkbox = page.getByRole("checkbox");
  await expect(checkbox).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Đồng ý lưu hồ sơ" })).toBeDisabled();
  expect(psql(`SELECT count(*) FROM talent_pool_consents WHERE application_id=${id}`)).toBe("0");
  await checkbox.check();
  await page.getByRole("button", { name: "Đồng ý lưu hồ sơ" }).click();
  await expect(page.getByRole("heading", { name: "Đã ghi nhận phản hồi" })).toBeVisible();
  expect(psql(`SELECT count(*) FROM talent_pool_consents WHERE application_id=${id}`)).toBe("1");
});
