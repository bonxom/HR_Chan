// API ứng viên: upload CV bằng FormData thật, yêu cầu OTP và nộp hồ sơ bằng JSON; capability
// chỉ nằm trong body, không trong URL; không lưu token vào storage.
/**
 * Contract (src/features/candidates/api.ts + types.ts):
 *  - createSubmission({ fullName, email, phone, consent, captchaToken, file })
 *      POST /api/v1/candidates/submissions, FormData fields full_name, email, phone,
 *      consent ("true"/"false"), captcha_token, file -> { submissionId, submissionToken, expiresAt }
 *  - requestApplicationOtp({ submissionId, submissionToken, jobId })
 *      POST /api/v1/applications/otp JSON snake_case -> { expiresAt, resendAvailableAt }
 *  - submitApplication({ submissionId, submissionToken, jobId, otpCode })
 *      POST /api/v1/applications JSON snake_case -> { applicationId, submittedAt, message }
 *  Errors are the shared ApiError (status, code, retryAfter, validationIssues).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/shared/services/client";
import { jsonResponse } from "@/test/apiStub";
import {
  APPLICATION_CREATED_JSON,
  OTP_ISSUED_JSON,
  SUBMISSION_JSON,
  appError,
  cvFile,
  stubFlowFetch,
} from "@/test/publicFlowStub";
import { createSubmission, requestApplicationOtp, submitApplication } from "./api";

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe("createSubmission", () => {
  it("gửi multipart FormData đúng tên trường backend", async () => {
    const { calls } = stubFlowFetch({
      "POST /api/v1/candidates/submissions": () => jsonResponse(SUBMISSION_JSON, 201),
    });
    const file = cvFile("Hồ sơ.pdf");

    const result = await createSubmission({
      fullName: "Nguyễn Văn A",
      email: "ung.vien@example.test",
      phone: "0912345678",
      consent: true,
      captchaToken: "turnstile-token",
      file,
    });

    const [call] = calls;
    expect(call.method).toBe("POST");
    expect(call.path).toBe("/api/v1/candidates/submissions");
    expect(call.form).toBeInstanceOf(FormData);
    expect(call.json).toBeUndefined();
    expect(call.headers["content-type"]).toBeUndefined();
    expect(call.form?.get("full_name")).toBe("Nguyễn Văn A");
    expect(call.form?.get("email")).toBe("ung.vien@example.test");
    expect(call.form?.get("phone")).toBe("0912345678");
    expect(call.form?.get("consent")).toBe("true");
    expect(call.form?.get("captcha_token")).toBe("turnstile-token");
    expect((call.form?.get("file") as File).name).toBe("Hồ sơ.pdf");
    expect(result).toEqual({
      submissionId: 501,
      submissionToken: SUBMISSION_JSON.submission_token,
      expiresAt: "2026-11-19T03:00:00Z",
    });
  });

  it("413 giữ status/code để form gắn lỗi vào ô tệp", async () => {
    stubFlowFetch({
      "POST /api/v1/candidates/submissions": () =>
        appError(413, "cv_too_large", "Tệp CV vượt quá dung lượng tối đa 5 MB."),
    });
    const caught = await createSubmission({
      fullName: "A",
      email: "a@example.test",
      phone: "0912345678",
      consent: true,
      captchaToken: "t",
      file: cvFile(),
    }).catch((error: unknown) => error);
    expect(caught).toBeInstanceOf(ApiError);
    expect(caught).toMatchObject({ status: 413, code: "cv_too_large" });
  });
});

describe("requestApplicationOtp / submitApplication", () => {
  it("gửi capability trong body JSON, không trong URL", async () => {
    const { calls } = stubFlowFetch({
      "POST /api/v1/applications/otp": () => jsonResponse(OTP_ISSUED_JSON),
      "POST /api/v1/applications": () => jsonResponse(APPLICATION_CREATED_JSON, 201),
    });
    const capability = {
      submissionId: 501,
      submissionToken: SUBMISSION_JSON.submission_token,
      jobId: 11,
    };

    const issued = await requestApplicationOtp(capability);
    const created = await submitApplication({ ...capability, otpCode: "482913" });

    expect(calls[0].path).toBe("/api/v1/applications/otp");
    expect(calls[0].json).toEqual({
      submission_id: 501,
      submission_token: SUBMISSION_JSON.submission_token,
      job_id: 11,
    });
    expect(calls[1].path).toBe("/api/v1/applications");
    expect(calls[1].json).toEqual({
      submission_id: 501,
      submission_token: SUBMISSION_JSON.submission_token,
      job_id: 11,
      otp_code: "482913",
    });
    for (const call of calls) expect(call.path).not.toContain(SUBMISSION_JSON.submission_token);
    expect(issued).toEqual({
      expiresAt: "2026-11-18T03:05:00Z",
      resendAvailableAt: "2026-11-18T03:01:00Z",
    });
    expect(created).toEqual({
      applicationId: 9001,
      submittedAt: "2026-11-18T03:02:00Z",
      message: APPLICATION_CREATED_JSON.message,
    });
  });

  it("không ghi token/mã vào localStorage hoặc sessionStorage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    stubFlowFetch({
      "POST /api/v1/applications/otp": () => jsonResponse(OTP_ISSUED_JSON),
      "POST /api/v1/applications": () => jsonResponse(APPLICATION_CREATED_JSON, 201),
    });
    await requestApplicationOtp({ submissionId: 1, submissionToken: "tok", jobId: 2 });
    await submitApplication({ submissionId: 1, submissionToken: "tok", jobId: 2, otpCode: "111111" });
    expect(setItem).not.toHaveBeenCalled();
  });

  it("429 giữ Retry-After của server", async () => {
    stubFlowFetch({
      "POST /api/v1/applications/otp": () =>
        appError(429, "rate_limited", "Vui lòng chờ.", { "Retry-After": "42" }),
    });
    const caught = await requestApplicationOtp({
      submissionId: 1,
      submissionToken: "tok",
      jobId: 2,
    }).catch((error: unknown) => error);
    expect(caught).toMatchObject({ status: 429, code: "rate_limited", retryAfter: 42 });
  });
});
