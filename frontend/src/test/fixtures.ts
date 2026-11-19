import type { AccountReadJson, AuthAccount } from "@/features/auth/types";
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
        { id: 1, name: "Python", description: "Kinh nghiệm Python", is_mandatory: true, weight: "60.00" },
        { id: 2, name: "SQL", description: "Thiết kế CSDL", is_mandatory: false, weight: "40.00" },
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
