import { ApiError, apiRequest } from "@/shared/services/client";
import type {
  CreateJobInput,
  CriteriaInput,
  CriteriaSet,
  CriteriaSetJson,
  Department,
  DepartmentJson,
  Interviewer,
  InterviewerJson,
  JobDetail,
  JobDetailJson,
  JobFieldsInput,
  JobListFilters,
  JobPage,
  JobPageJson,
  JobSummary,
  JobSummaryJson,
} from "./types";

export function describeJobError(error: unknown): string {
  if (error instanceof ApiError) {
    // FastAPI's default request validation 422 carries no `error.message`.
    if (error.status === 422 && error.code === "request_failed") {
      return "Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại các trường đã nhập.";
    }
    // Business rule (422), stale version (409) and validation (400) messages come from the backend.
    if (error.status === 409 || error.status === 422 || error.status === 400) return error.message;
    if (error.status === 404) return "Không tìm thấy tin tuyển dụng.";
    if (error.status === 403) return "Bạn không có quyền thực hiện thao tác này.";
    if (error.status === 429) return "Thao tác quá nhanh. Vui lòng thử lại sau ít phút.";
  }
  return "Không thể hoàn tất thao tác. Vui lòng thử lại.";
}

function queryString(values: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : "";
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

// Biên chuyển dữ liệu: backend dùng snake_case, phần giao diện dùng camelCase.
// Ngày đủ hạn xóa được nhận từ backend để không tự tính lệch quy tắc lưu trữ.
function mapSummary(data: JobSummaryJson): JobSummary {
  return {
    id: data.id,
    title: data.title,
    departmentId: data.department_id,
    departmentName: data.department_name,
    status: data.status,
    headcount: data.headcount,
    workMode: data.work_mode,
    location: data.location,
    deadline: data.deadline,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
    closedAt: data.closed_at,
    deletionDueDate: data.deletion_due_date ?? null,
    version: data.version,
  };
}

// Decimal trong JSON có thể là chuỗi; đổi sang number trước khi dùng trong form.
function mapCriteriaSet(data: CriteriaSetJson): CriteriaSet {
  return {
    id: data.id,
    versionNo: data.version_no,
    autoInviteThreshold: Number(data.auto_invite_threshold),
    createdBy: data.created_by,
    createdAt: data.created_at,
    criteria: data.criteria.map((item) => ({
      id: item.id,
      name: item.name,
      description: item.description,
      isMandatory: item.is_mandatory,
      weight: Number(item.weight),
    })),
  };
}

function mapInterviewer(data: InterviewerJson): Interviewer {
  return { id: data.id, fullName: data.full_name };
}

function mapDetail(data: JobDetailJson): JobDetail {
  return {
    ...mapSummary(data),
    description: data.description,
    requirements: data.requirements,
    benefits: data.benefits,
    createdBy: data.created_by,
    currentCriteria: data.current_criteria ? mapCriteriaSet(data.current_criteria) : null,
    interviewers: data.interviewers.map(mapInterviewer),
  };
}

// Các trường văn bản tùy chọn rỗng thành null theo hợp đồng Pydantic của backend.
function fieldsBody(input: JobFieldsInput) {
  return {
    title: input.title.trim(),
    department_id: input.departmentId,
    description: blankToNull(input.description),
    requirements: blankToNull(input.requirements),
    benefits: blankToNull(input.benefits),
    headcount: input.headcount,
    work_mode: blankToNull(input.workMode),
    location: blankToNull(input.location),
    deadline: input.deadline || null,
  };
}

function criteriaBody(input: CriteriaInput) {
  return {
    auto_invite_threshold: input.autoInviteThreshold,
    criteria: input.criteria.map((item) => ({
      name: item.name,
      description: item.description,
      is_mandatory: item.isMandatory,
      weight: item.weight,
    })),
    interviewer_ids: input.interviewerIds,
  };
}

export async function listJobs(accessToken: string, filters: JobListFilters = {}): Promise<JobPage> {
  const query = queryString({
    page: filters.page,
    page_size: filters.pageSize,
    q: filters.q?.trim(),
    status: filters.status,
    department_id: filters.departmentId,
    sort: filters.sort,
    order: filters.order,
  });
  const data = await apiRequest<JobPageJson>(`/api/v1/jobs${query}`, { accessToken });
  return {
    items: data.items.map(mapSummary),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

export async function getJob(accessToken: string, jobId: number): Promise<JobDetail> {
  return mapDetail(await apiRequest<JobDetailJson>(`/api/v1/jobs/${jobId}`, { accessToken }));
}

export async function deleteDraftJob(accessToken: string, jobId: number, version: number): Promise<void> {
  // Gửi version đã hiển thị để API phát hiện tin vừa bị sửa/đăng ở phiên khác.
  return apiRequest<void>(`/api/v1/jobs/${jobId}`, {
    method: "DELETE", accessToken, body: { version },
  });
}

export async function createJob(accessToken: string, input: CreateJobInput): Promise<JobDetail> {
  // publish chọn lưu nháp/đăng ngay; criteria null giữ khả năng bổ sung tiêu chí sau.
  const data = await apiRequest<JobDetailJson>("/api/v1/jobs", {
    method: "POST",
    accessToken,
    body: {
      ...fieldsBody(input),
      publish: input.publish,
      criteria: input.criteria ? criteriaBody(input.criteria) : null,
    },
  });
  return mapDetail(data);
}

export async function updateJob(
  accessToken: string,
  jobId: number,
  input: JobFieldsInput,
  version: number,
): Promise<JobDetail> {
  const data = await apiRequest<JobDetailJson>(`/api/v1/jobs/${jobId}`, {
    method: "PUT",
    accessToken,
    body: { ...fieldsBody(input), version },
  });
  return mapDetail(data);
}

export async function publishJob(accessToken: string, jobId: number, version: number): Promise<JobDetail> {
  const data = await apiRequest<JobDetailJson>(`/api/v1/jobs/${jobId}/publish`, {
    method: "POST",
    accessToken,
    body: { version },
  });
  return mapDetail(data);
}

export async function closeJob(accessToken: string, jobId: number, version: number): Promise<JobDetail> {
  const data = await apiRequest<JobDetailJson>(`/api/v1/jobs/${jobId}/close`, {
    method: "POST",
    accessToken,
    body: { version },
  });
  return mapDetail(data);
}

export async function saveCriteria(
  accessToken: string,
  jobId: number,
  input: CriteriaInput,
  version: number,
): Promise<JobDetail> {
  const data = await apiRequest<JobDetailJson>(`/api/v1/jobs/${jobId}/criteria`, {
    method: "PUT",
    accessToken,
    body: { version, ...criteriaBody(input) },
  });
  return mapDetail(data);
}

export async function listCriteriaVersions(accessToken: string, jobId: number): Promise<CriteriaSet[]> {
  const data = await apiRequest<CriteriaSetJson[]>(`/api/v1/jobs/${jobId}/criteria/versions`, {
    accessToken,
  });
  return data.map(mapCriteriaSet);
}

export async function listDepartments(accessToken: string): Promise<Department[]> {
  const data = await apiRequest<DepartmentJson[]>("/api/v1/departments", { accessToken });
  return data.map((item) => ({ id: item.id, name: item.name, isActive: item.is_active }));
}

export async function listInterviewers(accessToken: string): Promise<Interviewer[]> {
  const data = await apiRequest<InterviewerJson[]>("/api/v1/interviewers", { accessToken });
  return data.map(mapInterviewer);
}
