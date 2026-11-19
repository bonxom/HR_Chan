export interface SubmissionInput {
  fullName: string;
  email: string;
  phone: string;
  consent: boolean;
  captchaToken: string;
  file: File;
}

export interface SubmissionJson {
  submission_id: number;
  submission_token: string;
  expires_at: string;
}

/** Capability nằm trong bộ nhớ của form; không lưu storage, không đưa vào URL. */
export interface Submission {
  submissionId: number;
  submissionToken: string;
  expiresAt: string;
}

export interface ApplicationCapability {
  submissionId: number;
  submissionToken: string;
  jobId: number;
}

export interface OtpIssuedJson {
  expires_at: string;
  resend_available_at: string;
}

export interface OtpIssued {
  expiresAt: string;
  resendAvailableAt: string;
}

export interface ApplicationCreatedJson {
  application_id: number;
  submitted_at: string;
  message: string;
}

export interface ApplicationCreated {
  applicationId: number;
  submittedAt: string;
  message: string;
}
