import { apiRequest } from "@/shared/services/client";
import type {
  ApplicationCapability,
  ApplicationCreated,
  ApplicationCreatedJson,
  OtpIssued,
  OtpIssuedJson,
  Submission,
  SubmissionInput,
  SubmissionJson,
} from "./types";

// Không tự thử lại: upload/OTP/nộp hồ sơ không idempotent.
export async function createSubmission(input: SubmissionInput): Promise<Submission> {
  const form = new FormData();
  form.append("full_name", input.fullName);
  form.append("email", input.email);
  form.append("phone", input.phone);
  form.append("consent", input.consent ? "true" : "false");
  form.append("captcha_token", input.captchaToken);
  form.append("file", input.file, input.file.name);
  const data = await apiRequest<SubmissionJson>("/api/v1/candidates/submissions", {
    method: "POST",
    body: form,
  });
  return {
    submissionId: data.submission_id,
    submissionToken: data.submission_token,
    expiresAt: data.expires_at,
  };
}

function capabilityBody(capability: ApplicationCapability) {
  return {
    submission_id: capability.submissionId,
    submission_token: capability.submissionToken,
    job_id: capability.jobId,
  };
}

export async function requestApplicationOtp(capability: ApplicationCapability): Promise<OtpIssued> {
  const data = await apiRequest<OtpIssuedJson>("/api/v1/applications/otp", {
    method: "POST",
    body: capabilityBody(capability),
  });
  return { expiresAt: data.expires_at, resendAvailableAt: data.resend_available_at };
}

export async function submitApplication(
  input: ApplicationCapability & { otpCode: string },
): Promise<ApplicationCreated> {
  const data = await apiRequest<ApplicationCreatedJson>("/api/v1/applications", {
    method: "POST",
    body: { ...capabilityBody(input), otp_code: input.otpCode },
  });
  return {
    applicationId: data.application_id,
    submittedAt: data.submitted_at,
    message: data.message,
  };
}
