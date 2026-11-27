import { ApiError, apiBlob, apiRequest } from "@/shared/services/client";
import type {
  ApplicationCounts,
  ApplicationCountsJson,
  ApplicationDetail,
  ApplicationDetailJson,
  ApplicationListFilters,
  ApplicationPage,
  ApplicationPageJson,
  ApplicationSummary,
  ApplicationSummaryJson,
  CriterionScore,
  CriterionScoreJson,
  CvDownload,
  InterviewSlot,
  InterviewSlotJson,
  InviteInput,
  RejectInput,
  SlotQuery,
} from "./types";

const GENERIC_ERROR = "Không thể hoàn tất thao tác. Vui lòng thử lại.";

export function describeApplicationError(error: unknown): string {
  if (error instanceof ApiError) {
    // 422 do FastAPI kiểm tra request không có error.message (code mặc định request_failed).
    if (error.status === 422 && error.code === "request_failed") {
      return "Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại.";
    }
    // 409 (trạng thái/version/khung giờ), 422 nghiệp vụ và 503 có thông điệp tiếng Việt của backend.
    if (error.status === 409 || error.status === 422 || error.status === 503) return error.message;
    if (error.status === 404) return "Không tìm thấy hồ sơ ứng tuyển.";
    if (error.status === 403) return "Bạn không có quyền thực hiện thao tác này.";
    if (error.status === 429) return "Thao tác quá nhanh. Vui lòng thử lại sau ít phút.";
  }
  return GENERIC_ERROR;
}

function queryString(values: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}

/** Decimal từ JSON (số hoặc chuỗi); giữ null là null để không hiển thị nhầm thành 0. */
function toNumber(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  return Number(value);
}

function mapSummary(data: ApplicationSummaryJson): ApplicationSummary {
  return {
    id: data.id,
    jobId: data.job_id,
    jobTitle: data.job_title,
    fullName: data.full_name,
    email: data.email,
    submittedAt: data.submitted_at,
    status: data.status,
    aiStatus: data.ai_status,
    aiTotalScore: toNumber(data.ai_total_score),
    reviewDueAt: data.review_due_at,
    emailIssue: data.email_issue,
    version: data.version,
  };
}

function mapScore(data: CriterionScoreJson): CriterionScore {
  const score: CriterionScore = {
    criterionId: data.criterion_id,
    name: data.name,
    isMandatory: data.is_mandatory,
    score: Number(data.score),
    weight: Number(data.weight_snapshot),
    aiComment: data.ai_comment,
  };
  // Backend chỉ gửi điểm sàn/kết quả cho tiêu chí bắt buộc; tiêu chí tùy chọn không có đạt/trượt.
  if (data.is_mandatory) {
    score.minScore = toNumber(data.min_score);
    score.meetsMandatory = data.meets_mandatory ?? null;
  }
  return score;
}

function mapDetail(data: ApplicationDetailJson): ApplicationDetail {
  return {
    ...mapSummary(data),
    candidate: {
      id: data.candidate.id,
      fullName: data.candidate.full_name,
      email: data.candidate.email,
      phone: data.candidate.phone,
    },
    aiFailureReason: data.ai_failure_reason,
    hrNote: data.hr_note,
    scores: data.scores.map(mapScore),
    statusHistory: data.status_history.map((event) => ({
      at: event.at,
      actorId: event.actor_id,
      before: event.before ?? null,
      after: event.after ?? null,
    })),
    interview: data.interview
      ? {
          id: data.interview.id,
          status: data.interview.status,
          needsManualCalendarFix: data.interview.needs_manual_calendar_fix,
        }
      : null,
  };
}

export async function listApplications(
  accessToken: string,
  filters: ApplicationListFilters,
): Promise<ApplicationPage> {
  const query = queryString({
    page: filters.page,
    page_size: filters.pageSize,
    q: filters.q?.trim(),
    status: filters.status,
    sort: filters.sort,
    order: filters.order,
  });
  const data = await apiRequest<ApplicationPageJson>(`/api/v1/applications${query}`, { accessToken });
  return { items: data.items.map(mapSummary), total: data.total, page: data.page, pageSize: data.page_size };
}

/** Counts per status, total and overdue in one request. */
export async function getApplicationCounts(accessToken: string): Promise<ApplicationCounts> {
  const data = await apiRequest<ApplicationCountsJson>("/api/v1/applications/counts", { accessToken });
  return { total: data.total, overdue: data.overdue, byStatus: data.by_status };
}

export async function getApplication(accessToken: string, applicationId: number): Promise<ApplicationDetail> {
  return mapDetail(await apiRequest<ApplicationDetailJson>(`/api/v1/applications/${applicationId}`, { accessToken }));
}

export async function rejectApplication(
  accessToken: string,
  applicationId: number,
  input: RejectInput,
): Promise<void> {
  const reasonText = input.reasonText?.trim();
  await apiRequest<unknown>(`/api/v1/applications/${applicationId}/reject`, {
    method: "POST",
    accessToken,
    body: {
      reason_code: input.reasonCode,
      ...(reasonText ? { reason_text: reasonText } : {}),
      version: input.version,
    },
  });
}

export async function getInterviewSlots(
  accessToken: string,
  applicationId: number,
  slotQuery: SlotQuery,
): Promise<InterviewSlot[]> {
  const query = queryString({
    date_from: slotQuery.dateFrom,
    date_to: slotQuery.dateTo,
    interviewer_id: slotQuery.interviewerId,
  });
  const data = await apiRequest<InterviewSlotJson[]>(
    `/api/v1/applications/${applicationId}/interview-slots${query}`,
    { accessToken },
  );
  return data.map((slot) => ({ startAt: slot.start_at, endAt: slot.end_at }));
}

export async function inviteApplication(
  accessToken: string,
  applicationId: number,
  input: InviteInput,
): Promise<void> {
  // start_at gửi nguyên chuỗi có múi giờ mà backend đã gợi ý.
  await apiRequest<unknown>(`/api/v1/applications/${applicationId}/invite`, {
    method: "POST",
    accessToken,
    body: {
      start_at: input.startAt,
      version: input.version,
      ...(input.interviewerId ? { interviewer_id: input.interviewerId } : {}),
    },
  });
}

const CV_EXTENSIONS: Record<string, string> = {
  "application/pdf": ".pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
};

export async function downloadApplicationCv(accessToken: string, applicationId: number): Promise<CvDownload> {
  const { blob, filename } = await apiBlob(`/api/v1/applications/${applicationId}/cv`, { accessToken });
  if (filename) return { blob, filename };
  // Khác origin thì không đọc được tên gốc; đặt tên dự phòng theo loại tệp.
  const mime = blob.type.split(";")[0].trim().toLowerCase();
  return { blob, filename: `CV-hoso-${applicationId}${CV_EXTENSIONS[mime] ?? ""}` };
}
