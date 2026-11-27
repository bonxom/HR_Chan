import type { AccountReadJson, AuthAccount } from "@/features/auth/types";
import type { ApplicationDetailJson, ApplicationSummaryJson } from "@/features/applications/types";
import type { JobDetailJson, JobSummaryJson } from "@/features/jobs/types";

// Dữ liệu giả theo hợp đồng JSON để test UI/API mapping; không được dùng để
// bỏ qua xác thực hoặc thay dữ liệu API thật trong các màn hình đã tích hợp.
export function jobSummaryJson(overrides: Partial<JobSummaryJson> = {}): JobSummaryJson {
  return {
    id: 1,
    title: "Lập trình viên Backend Python",
    department_id: 1,
    department_name: "Phòng Kỹ thuật",
    status: "DRAFT",
    headcount: 2,
    work_mode: "Hybrid",
    location: "Hà Nội",
    deadline: "2026-12-17",
    created_at: "2026-11-17T02:00:00Z",
    updated_at: "2026-11-17T02:00:00Z",
    closed_at: null,
    deletion_due_date: null,
    version: 1,
    ...overrides,
  };
}

export function jobDetailJson(overrides: Partial<JobDetailJson> = {}): JobDetailJson {
  return {
    ...jobSummaryJson(),
    description: "Phát triển API",
    requirements: "Python, SQL",
    benefits: null,
    created_by: "11111111-1111-4111-8111-111111111111",
    current_criteria: {
      id: 1,
      version_no: 1,
      auto_invite_threshold: "75.00",
      created_by: "11111111-1111-4111-8111-111111111111",
      created_at: "2026-11-17T02:00:00Z",
      criteria: [
        { id: 1, name: "Python", description: "Kinh nghiệm Python", is_mandatory: true, min_score: "50.00", weight: "60.00" },
        { id: 2, name: "SQL", description: "Thiết kế CSDL", is_mandatory: false, min_score: null, weight: "40.00" },
      ],
    },
    interviewers: [{ id: "iv-1", full_name: "Người Phỏng Vấn" }],
    ...overrides,
  };
}

export function accountJson(overrides: Partial<AccountReadJson> = {}): AccountReadJson {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    full_name: "Nguyễn Văn Nhân Viên",
    email: "employee@sis.hust.edu.vn",
    account_type: "EMPLOYEE",
    roles: ["HR"],
    status: "ACTIVE",
    created_at: "2026-11-01T08:00:00Z",
    last_login_at: "2026-11-14T09:30:00Z",
    ...overrides,
  };
}

export function adminAccountJson(overrides: Partial<AccountReadJson> = {}): AccountReadJson {
  return accountJson({
    id: "22222222-2222-4222-8222-222222222222",
    full_name: "Quản Trị Viên",
    email: "admin@sis.hust.edu.vn",
    account_type: "ADMIN",
    roles: [],
    ...overrides,
  });
}

export function authAccount(overrides: Partial<AuthAccount> = {}): AuthAccount {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    fullName: "Nguyễn Văn Nhân Viên",
    email: "employee@sis.hust.edu.vn",
    accountType: "EMPLOYEE",
    roles: ["HR"],
    status: "ACTIVE",
    createdAt: "2026-11-01T08:00:00Z",
    lastLoginAt: "2026-11-14T09:30:00Z",
    ...overrides,
  };
}

export function adminAccount(overrides: Partial<AuthAccount> = {}): AuthAccount {
  return authAccount({
    id: "22222222-2222-4222-8222-222222222222",
    fullName: "Quản Trị Viên",
    email: "admin@sis.hust.edu.vn",
    accountType: "ADMIN",
    roles: [],
    ...overrides,
  });
}

export function applicationSummaryJson(
  overrides: Partial<ApplicationSummaryJson> = {},
): ApplicationSummaryJson {
  return {
    id: 1,
    job_id: 1,
    job_title: "Lập trình viên Backend Python",
    full_name: "Trần Thị Ứng Viên",
    email: "ung.vien@example.com",
    submitted_at: "2026-11-27T00:25:19.606934+00:00",
    status: "PENDING_HR_REVIEW",
    ai_status: "SCORED",
    ai_total_score: 43.4,
    review_due_at: "2026-12-04T10:30:00+00:00",
    email_issue: null,
    version: 2,
    ...overrides,
  };
}

export function applicationDetailJson(
  overrides: Partial<ApplicationDetailJson> = {},
): ApplicationDetailJson {
  return {
    ...applicationSummaryJson(),
    candidate: { id: 1, full_name: "Trần Thị Ứng Viên", email: "ung.vien@example.com", phone: "0900000000" },
    criteria_set_id: 1,
    ai_failure_reason: null,
    hr_note: null,
    scores: [
      {
        criterion_id: 1,
        name: "Kinh nghiệm Python",
        is_mandatory: true,
        score: 5,
        weight_snapshot: 40,
        ai_comment: "Chưa thấy dự án Python thực tế.",
        min_score: 50,
        meets_mandatory: false,
      },
      {
        criterion_id: 2,
        name: "Cơ sở dữ liệu",
        is_mandatory: false,
        score: 99,
        weight_snapshot: 35,
        ai_comment: "Thành thạo PostgreSQL.",
      },
      {
        criterion_id: 3,
        name: "Công cụ và quy trình",
        is_mandatory: false,
        score: 27,
        weight_snapshot: 25,
        ai_comment: "Có dùng Git.",
      },
    ],
    status_history: [
      { at: "2026-11-27T00:25:19.630730+00:00", actor_id: null, before: null, after: "SCORING" },
      { at: "2026-11-27T00:25:48.323301+00:00", actor_id: null, before: "SCORING", after: "PENDING_HR_REVIEW" },
    ],
    interview: null,
    ...overrides,
  };
}
