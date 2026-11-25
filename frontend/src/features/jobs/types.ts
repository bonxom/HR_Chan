// Contracts for the HR job posting API (`/api/v1/jobs`, `/departments`, `/interviewers`).
// Response types describe the API; they do not validate runtime JSON.

export type JobStatus = "DRAFT" | "OPEN" | "CLOSED";
export type JobSort = "created_at" | "deadline" | "title";
export type SortOrder = "asc" | "desc";

// ---- JSON shapes (snake_case, decimals as strings) ----

// Kiểu JSON mô tả hợp đồng truyền qua HTTP; không tự kiểm chứng dữ liệu lúc chạy.
export interface JobSummaryJson {
  id: number;
  title: string;
  department_id: number;
  department_name: string;
  status: JobStatus;
  headcount: number | null;
  work_mode: string | null;
  location: string | null;
  deadline: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  // Chỉ CLOSED có ngày đủ hạn; worker có thể xử lý sau ngày này tùy lúc chạy.
  deletion_due_date: string | null;
  version: number;
}

export interface JobPageJson {
  items: JobSummaryJson[];
  total: number;
  page: number;
  page_size: number;
}

export interface CriterionJson {
  id: number;
  name: string;
  description: string;
  is_mandatory: boolean;
  min_score: string | number | null;
  weight: string | number;
}

export interface CriteriaSetJson {
  id: number;
  version_no: number;
  auto_invite_threshold: string | number;
  created_by: string;
  created_at: string;
  criteria: CriterionJson[];
}

export interface InterviewerJson {
  id: string;
  full_name: string;
}

export interface JobDetailJson extends JobSummaryJson {
  description: string | null;
  requirements: string | null;
  benefits: string | null;
  created_by: string;
  current_criteria: CriteriaSetJson | null;
  interviewers: InterviewerJson[];
}

export interface DepartmentJson {
  id: number;
  name: string;
  is_active: boolean;
}

// ---- Application shapes ----

// Dữ liệu sau mapSummary, được các component HR dùng để render và gửi version.
export interface JobSummary {
  id: number;
  title: string;
  departmentId: number;
  departmentName: string;
  status: JobStatus;
  headcount: number | null;
  workMode: string | null;
  location: string | null;
  deadline: string | null;
  createdAt: string;
  updatedAt: string;
  closedAt: string | null;
  deletionDueDate: string | null;
  version: number;
}

export interface JobPage {
  items: JobSummary[];
  total: number;
  page: number;
  pageSize: number;
}

export interface Criterion {
  id?: number;
  name: string;
  description: string;
  isMandatory: boolean;
  minScore?: number;
  weight: number;
}

export interface CriteriaSet {
  id: number;
  versionNo: number;
  autoInviteThreshold: number;
  createdBy: string;
  createdAt: string;
  criteria: Criterion[];
}

export interface Interviewer {
  id: string;
  fullName: string;
}

export interface JobDetail extends JobSummary {
  description: string | null;
  requirements: string | null;
  benefits: string | null;
  createdBy: string;
  currentCriteria: CriteriaSet | null;
  interviewers: Interviewer[];
}

export interface Department {
  id: number;
  name: string;
  isActive: boolean;
}

export interface JobListFilters {
  page?: number;
  pageSize?: number;
  q?: string;
  status?: JobStatus;
  departmentId?: number;
  sort?: JobSort;
  order?: SortOrder;
}

export interface JobFieldsInput {
  title: string;
  departmentId: number;
  description: string;
  requirements: string;
  benefits: string;
  headcount: number | null;
  workMode: string;
  location: string;
  deadline: string;
}

export interface CriteriaInput {
  /** null lets the backend use the system default threshold. */
  autoInviteThreshold: number | null;
  criteria: Criterion[];
  interviewerIds: string[];
}

export interface CreateJobInput extends JobFieldsInput {
  publish: boolean;
  criteria: CriteriaInput | null;
}
