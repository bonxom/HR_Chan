import type {
  AccountReadJson,
  AccountStatus,
  AccountType,
  AuthAccount,
  EmployeeRole,
} from "@/features/auth/types";

export interface AccountListFilters {
  status?: AccountStatus;
  accountType?: AccountType;
  cursor?: string | null;
  limit?: number;
}

export interface AccountPage {
  items: AuthAccount[];
  nextCursor: string | null;
}

export interface AccountPageJson {
  items: AccountReadJson[];
  next_cursor: string | null;
}

export interface CreateAccountInput {
  fullName: string;
  email: string;
  accountType: AccountType;
  roles: EmployeeRole[];
}

// "queued": thư đã vào hàng đợi và worker sẽ gửi sau; chưa phải đã gửi.
export type EmailDelivery = "sent" | "failed" | "queued";

export interface AccountDeliveryResult {
  account: AuthAccount;
  emailDelivery: EmailDelivery;
}

export type AuditOutcome = "SUCCESS" | "FAILURE";

export interface AuditEvent {
  id: string;
  actorId: string | null;
  action: string;
  outcome: AuditOutcome;
  timestamp: string;
  targetType: string | null;
  targetId: string | null;
  metadata: Record<string, unknown>;
}

export interface AuditEventJson {
  id: string;
  actor_id: string | null;
  action: string;
  outcome: AuditOutcome;
  timestamp: string;
  target_type: string | null;
  target_id: string | null;
  metadata: Record<string, unknown>;
}

export interface AuditEventPage {
  items: AuditEvent[];
  nextCursor: string | null;
}

export interface AuditEventPageJson {
  items: AuditEventJson[];
  next_cursor: string | null;
}

export interface AuditFilters {
  action?: string;
  actorId?: string;
  targetType?: string;
  targetId?: string;
  from?: string;
  to?: string;
  cursor?: string | null;
  limit?: number;
}
