import { useSyncExternalStore } from "react";
import type { AuthAccount } from "./types";

export interface AuthState {
  accessToken: string | null;
  account: AuthAccount | null;
  /** Incremented when the identity changes so late responses cannot restore a session. */
  generation: number;
}

const listeners = new Set<() => void>();

let state: AuthState = { accessToken: null, account: null, generation: 0 };

function emit(): void {
  for (const listener of [...listeners]) listener();
}

export function subscribeToAuth(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getAuthState(): AuthState {
  return state;
}

export function startSession(accessToken: string, account: AuthAccount): void {
  state = { accessToken, account, generation: state.generation + 1 };
  emit();
}

export function updateTokens(accessToken: string, account: AuthAccount | null = null): void {
  state = {
    accessToken,
    account: account ?? state.account,
    generation: state.generation,
  };
  emit();
}

export function updateAccount(account: AuthAccount): void {
  state = { ...state, account };
  emit();
}

export function endSession(): void {
  state = { accessToken: null, account: null, generation: state.generation + 1 };
  emit();
}

export function currentAccessToken(): string | null {
  return state.accessToken;
}

export function currentGeneration(): number {
  return state.generation;
}

export function useAuthState(): AuthState {
  return useSyncExternalStore(subscribeToAuth, getAuthState, getAuthState);
}
