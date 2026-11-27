// Contracts for the HR application review API (`/api/v1/applications`).
// Response types describe the API; they do not validate runtime JSON.
// Review responses are plain dicts, so decimals arrive as JSON numbers; accept strings too.

import type { ApplicationStatus } from "@/shared/types/models";

export type { ApplicationStatus };
export type AiScoreStatus = "PENDING" | "SCORED" | "NEEDS_REVIEW" | "FAILED";
export type RejectReason =
  | "NOT_QUALIFIED"
  | "SKILL_MISMATCH"
  | "INSUFFICIENT_EXPERIENCE"
  | "POSITION_FILLED"
  | "OTHER";

type Decimal = number | string;

export interface ApplicationSummaryJson {
  id: number;
  job_id: number;
  job_title: string;
  full_name: string;
  email: string;
  submitted_at: string;
  status: ApplicationStatus;
  ai_status: AiScoreStatus;
  ai_total_score: Decimal | null;
  review_due_at: string | null;
  email_issue: string | null;
  version: number;
}

export interface ApplicationPageJson {
  items: ApplicationSummaryJson[];
  total: number;
  page: number;
  page_size: number;
}

export interface CriterionScoreJson {
  criterion_id: number;
  name: string;
  is_mandatory: boolean;
  score: Decimal;
  weight_snapshot: Decimal;
  ai_comment: string | null;
  // Present only on mandatory criteria.
  min_score?: Decimal | null;
  meets_mandatory?: boolean | null;
}

export interface StatusChangeJson {
  at: string;
  actor_id: string | null;
  before?: ApplicationStatus | null;
  after?: ApplicationStatus | null;
}

export interface ApplicationDetailJson extends ApplicationSummaryJson {
  candidate: { id: number; full_name: string; email: string; phone: string | null };
  criteria_set_id: number | null;
  ai_failure_reason: string | null;
  hr_note: string | null;
  scores: CriterionScoreJson[];
  status_history: StatusChangeJson[];
  interview: { id: number; status: string; needs_manual_calendar_fix: boolean } | null;
}

export interface InterviewSlotJson {
  start_at: string;
  end_at: string;
}

export interface ApplicationSummary {
  id: number;
  jobId: number;
  jobTitle: string;
  fullName: string;
  email: string;
  submittedAt: string;
  status: ApplicationStatus;
  aiStatus: AiScoreStatus;
  aiTotalScore: number | null;
  reviewDueAt: string | null;
  emailIssue: string | null;
  version: number;
}

export interface ApplicationPage {
  items: ApplicationSummary[];
  total: number;
  page: number;
  pageSize: number;
}

export interface CriterionScore {
  criterionId: number;
  name: string;
  isMandatory: boolean;
  score: number;
  weight: number;
  aiComment: string | null;
  /** Mandatory criteria only; undefined for optional ones. */
  minScore?: number | null;
  meetsMandatory?: boolean | null;
}

export interface StatusChange {
  at: string;
  actorId: string | null;
  before: ApplicationStatus | null;
  after: ApplicationStatus | null;
}

export interface ApplicationDetail extends ApplicationSummary {
  candidate: { id: number; fullName: string; email: string; phone: string | null };
  aiFailureReason: string | null;
  hrNote: string | null;
  scores: CriterionScore[];
  statusHistory: StatusChange[];
  interview: { id: number; status: string; needsManualCalendarFix: boolean } | null;
}

export interface ApplicationListFilters {
  page: number;
  pageSize: number;
  q?: string;
  /** Undefined means all statuses. */
  status?: ApplicationStatus;
  sort?: "submitted_at" | "ai_total_score" | "review_due_at";
  order?: "asc" | "desc";
}

export interface ApplicationCountsJson {
  total: number;
  overdue: number;
  by_status: Partial<Record<ApplicationStatus, number>>;
}

export interface ApplicationCounts {
  total: number;
  overdue: number;
  byStatus: Partial<Record<ApplicationStatus, number>>;
}

export interface InterviewSlot {
  startAt: string;
  endAt: string;
}

export interface SlotQuery {
  dateFrom: string;
  dateTo: string;
  interviewerId?: string;
}

export interface RejectInput {
  reasonCode: RejectReason;
  reasonText?: string;
  version: number;
}

export interface InviteInput {
  startAt: string;
  version: number;
  interviewerId?: string;
}

export interface CvDownload {
  blob: Blob;
  filename: string;
}
