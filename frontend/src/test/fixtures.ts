import type { AccountReadJson, AuthAccount } from "@/features/auth/types";

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
