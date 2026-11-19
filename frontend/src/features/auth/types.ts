export type AccountType = "ADMIN" | "EMPLOYEE";
export type EmployeeRole = "HR" | "INTERVIEWER" | "DEPT_MANAGER" | "PROBATION";
export type AccountStatus =
  | "PENDING_SETUP"
  | "ACTIVE"
  | "LOCKED"
  | "PASSWORD_RESET_REQUIRED"
  | "DISABLED";

export interface AuthAccount {
  id: string;
  fullName: string;
  email: string;
  accountType: AccountType;
  roles: EmployeeRole[];
  status: AccountStatus;
  createdAt: string;
  lastLoginAt: string | null;
}

export interface AccountReadJson {
  id: string;
  full_name: string;
  email: string;
  account_type: AccountType;
  roles: EmployeeRole[];
  status: AccountStatus;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponseJson {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  account: AccountReadJson;
}

export interface AuthSession {
  accessToken: string;
  expiresIn: number;
  account: AuthAccount;
}

export interface AccountDeliveryJson {
  account: AccountReadJson;
  email_delivery: "sent" | "failed" | "queued";
}

export function mapAccount(json: AccountReadJson): AuthAccount {
  return {
    id: json.id,
    fullName: json.full_name,
    email: json.email,
    accountType: json.account_type,
    roles: json.roles,
    status: json.status,
    createdAt: json.created_at,
    lastLoginAt: json.last_login_at,
  };
}

export function mapSession(json: TokenResponseJson): AuthSession {
  return {
    accessToken: json.access_token,
    expiresIn: json.expires_in,
    account: mapAccount(json.account),
  };
}
