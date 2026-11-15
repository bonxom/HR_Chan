import { ApiError } from "@/shared/services/client";
import * as authApi from "./api";
import { currentGeneration, updateTokens } from "./session";

export const AUTH_LOCK_NAME = "hr-chan-auth";
export const AUTH_CHANNEL_NAME = "hr-chan-auth-events";

export type AuthBroadcast = { type: "logout" } | { type: "identity-changed" };

export class UnsupportedBrowserError extends Error {
  constructor() {
    super("This browser does not support the Web Locks API");
    this.name = "UnsupportedBrowserError";
  }
}

export function locksSupported(): boolean {
  return typeof navigator !== "undefined" && "locks" in navigator && Boolean(navigator.locks);
}

/** Every credential-changing operation runs inside this origin-wide lock. */
export async function withAuthLock<T>(operation: () => Promise<T>): Promise<T> {
  if (!locksSupported()) throw new UnsupportedBrowserError();
  return navigator.locks.request(AUTH_LOCK_NAME, operation) as Promise<T>;
}

let pendingRefresh: Promise<boolean> | null = null;

/** Rotate the refresh cookie once per tab, serialized across tabs by the lock. */
export function refreshSession(): Promise<boolean> {
  if (pendingRefresh) return pendingRefresh;
  pendingRefresh = (async () => {
    const generation = currentGeneration();
    try {
      return await withAuthLock(async () => {
        const session = await authApi.refreshRequest();
        // A logout or new identity while the request was in flight wins.
        if (currentGeneration() !== generation) return false;
        updateTokens(session.accessToken, session.account);
        return true;
      });
    } catch (error) {
      if (error instanceof ApiError || error instanceof UnsupportedBrowserError) return false;
      return false;
    } finally {
      pendingRefresh = null;
    }
  })();
  return pendingRefresh;
}

export function broadcastAuthEvent(event: AuthBroadcast): void {
  if (typeof BroadcastChannel === "undefined") return;
  const channel = new BroadcastChannel(AUTH_CHANNEL_NAME);
  channel.postMessage(event);
  channel.close();
}

export function subscribeAuthEvents(handler: (event: AuthBroadcast) => void): () => void {
  if (typeof BroadcastChannel === "undefined") return () => {};
  const channel = new BroadcastChannel(AUTH_CHANNEL_NAME);
  channel.onmessage = (message: MessageEvent<AuthBroadcast>) => handler(message.data);
  return () => channel.close();
}
