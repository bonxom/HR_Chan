export type ResponseAction = "ACCEPTED" | "DECLINED" | "RESCHEDULE_REQUESTED";
export type ResponseOutcome = ResponseAction | "EXPIRED";

export interface ResponseView {
  completed: false;
  purpose: "CONFIRM_INTERVIEW" | "TALENT_POOL_CONSENT";
  job_title: string;
  expires_at: string;
  allowed_actions: ResponseAction[];
  start_at?: string;
  meet_link?: string;
  can_reschedule?: boolean;
  consent_mode?: "GRANT" | "ACKNOWLEDGE";
  policy_ver?: string;
  policy_text?: string;
  retention_months?: number;
  consent_snapshot?: string;
  consent_expires_at?: string | null;
}

export interface ResponseReceipt {
  completed: true;
  outcome: ResponseOutcome;
  completed_at: string;
}

export interface ResponseSubmission {
  token: string;
  action: ResponseAction;
  note?: string;
  policy_ver?: string;
  consent_snapshot?: string;
}

export interface ResponseResult {
  outcome: ResponseOutcome;
  message: string;
  application_status?: string;
  interview_status?: string;
}
