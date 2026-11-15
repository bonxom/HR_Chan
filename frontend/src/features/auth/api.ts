import { apiRequest } from "@/shared/services/client";
import {
  mapAccount,
  mapSession,
  type AccountReadJson,
  type AuthAccount,
  type AuthSession,
  type TokenResponseJson,
} from "./types";

export async function fetchCsrfProof(): Promise<string> {
  const data = await apiRequest<{ csrf_token: string }>("/api/v1/auth/csrf");
  return data.csrf_token;
}

async function csrfHeaders(): Promise<Record<string, string>> {
  return { "X-CSRF-Token": await fetchCsrfProof() };
}

export async function loginRequest(email: string, password: string): Promise<AuthSession> {
  const data = await apiRequest<TokenResponseJson>("/api/v1/auth/login", {
    method: "POST",
    body: { email, password },
  });
  return mapSession(data);
}

export async function devLoginRequest(persona: string): Promise<AuthSession> {
  const data = await apiRequest<TokenResponseJson>("/api/v1/auth/dev-login", {
    method: "POST",
    body: { persona },
  });
  return mapSession(data);
}

export async function refreshRequest(): Promise<AuthSession> {
  const data = await apiRequest<TokenResponseJson>("/api/v1/auth/refresh", {
    method: "POST",
    headers: await csrfHeaders(),
  });
  return mapSession(data);
}

export async function logoutRequest(): Promise<void> {
  let headers: Record<string, string> = {};
  try {
    headers = await csrfHeaders();
  } catch {
    // Without a CSRF proof the request only clears cookies server-side.
  }
  await apiRequest<void>("/api/v1/auth/logout", { method: "POST", headers });
}

export async function fetchCurrentAccount(accessToken: string): Promise<AuthAccount> {
  const data = await apiRequest<AccountReadJson>("/api/v1/auth/me", { accessToken });
  return mapAccount(data);
}

export async function reportActivity(accessToken: string): Promise<void> {
  await apiRequest<void>("/api/v1/auth/activity", { method: "POST", accessToken });
}

export async function changePasswordRequest(
  accessToken: string,
  currentPassword: string,
  newPassword: string,
): Promise<AuthSession> {
  const data = await apiRequest<TokenResponseJson>("/api/v1/auth/password/change", {
    method: "POST",
    accessToken,
    headers: await csrfHeaders(),
    body: { current_password: currentPassword, new_password: newPassword },
  });
  return mapSession(data);
}

export async function requestPasswordRecovery(email: string): Promise<void> {
  await apiRequest<{ status: string }>("/api/v1/auth/password/recovery", {
    method: "POST",
    body: { email },
  });
}

export async function completePassword(token: string, newPassword: string): Promise<void> {
  await apiRequest<void>("/api/v1/auth/password/complete", {
    method: "POST",
    body: { token, new_password: newPassword },
  });
}
