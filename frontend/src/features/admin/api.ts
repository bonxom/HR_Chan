import { ApiError, apiRequest } from "@/shared/services/client";
import { mapAccount, type AccountDeliveryJson, type AccountReadJson } from "@/features/auth/types";
import type {
  AccountDeliveryResult,
  AccountListFilters,
  AccountPage,
  AccountPageJson,
  AuditEventJson,
  AuditEventPage,
  AuditEventPageJson,
  AuditFilters,
  CreateAccountInput,
} from "./types";

export function describeAdminError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Thao tác quá nhanh. Vui lòng thử lại sau ít phút.";
    if (error.status === 409 || error.status === 400 || error.status === 422) return error.message;
    if (error.status === 404) return "Không tìm thấy tài khoản.";
    if (error.status === 403) return "Bạn không có quyền thực hiện thao tác này.";
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

export async function listAccounts(
  accessToken: string,
  filters: AccountListFilters = {},
): Promise<AccountPage> {
  const query = queryString({
    status: filters.status,
    account_type: filters.accountType,
    cursor: filters.cursor,
    limit: filters.limit,
  });
  const data = await apiRequest<AccountPageJson>(`/api/v1/accounts${query}`, { accessToken });
  return {
    items: data.items.map((item: AccountReadJson) => mapAccount(item)),
    nextCursor: data.next_cursor,
  };
}

function toDelivery(data: AccountDeliveryJson): AccountDeliveryResult {
  return { account: mapAccount(data.account), emailDelivery: data.email_delivery };
}

export async function createAccount(
  accessToken: string,
  input: CreateAccountInput,
): Promise<AccountDeliveryResult> {
  const data = await apiRequest<AccountDeliveryJson>("/api/v1/accounts", {
    method: "POST",
    accessToken,
    body: {
      full_name: input.fullName,
      email: input.email,
      account_type: input.accountType,
      roles: input.roles,
    },
  });
  return toDelivery(data);
}

export async function replaceRoles(
  accessToken: string,
  accountId: string,
  roles: string[],
) {
  const data = await apiRequest<AccountReadJson>(`/api/v1/accounts/${accountId}/roles`, {
    method: "PUT",
    accessToken,
    body: { roles },
  });
  return mapAccount(data);
}

export async function lockAccount(accessToken: string, accountId: string, reason: string) {
  const data = await apiRequest<AccountReadJson>(`/api/v1/accounts/${accountId}/lock`, {
    method: "POST",
    accessToken,
    body: { reason },
  });
  return mapAccount(data);
}

export async function unlockAccount(
  accessToken: string,
  accountId: string,
): Promise<AccountDeliveryResult> {
  const data = await apiRequest<AccountDeliveryJson>(`/api/v1/accounts/${accountId}/unlock`, {
    method: "POST",
    accessToken,
  });
  return toDelivery(data);
}

export async function disableAccount(
  accessToken: string,
  accountId: string,
  reason: string,
) {
  const data = await apiRequest<AccountReadJson>(`/api/v1/accounts/${accountId}/disable`, {
    method: "POST",
    accessToken,
    body: { reason },
  });
  return mapAccount(data);
}

export async function resendInvitation(
  accessToken: string,
  accountId: string,
): Promise<AccountDeliveryResult> {
  const data = await apiRequest<AccountDeliveryJson>(
    `/api/v1/accounts/${accountId}/invitation`,
    { method: "POST", accessToken },
  );
  return toDelivery(data);
}

export async function listAuditEvents(
  accessToken: string,
  filters: AuditFilters = {},
): Promise<AuditEventPage> {
  const query = queryString({
    action: filters.action,
    actor_id: filters.actorId,
    target_type: filters.targetType,
    target_id: filters.targetId,
    from: filters.from,
    to: filters.to,
    cursor: filters.cursor,
    limit: filters.limit,
  });
  const data = await apiRequest<AuditEventPageJson>(`/api/v1/audit-events${query}`, {
    accessToken,
  });
  return {
    items: data.items.map((item: AuditEventJson) => ({
      id: item.id,
      actorId: item.actor_id,
      action: item.action,
      outcome: item.outcome,
      timestamp: item.timestamp,
      targetType: item.target_type,
      targetId: item.target_id,
      metadata: item.metadata,
    })),
    nextCursor: data.next_cursor,
  };
}
