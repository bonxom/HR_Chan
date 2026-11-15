import { describe, expect, it, vi } from "vitest";
import {
  currentAccessToken,
  currentGeneration,
  endSession,
  getAuthState,
  startSession,
  subscribeToAuth,
  updateAccount,
  updateTokens,
} from "./session";
import { authAccount } from "@/test/fixtures";

describe("in-memory auth session", () => {
  it("keeps credentials out of browser storage", () => {
    startSession("access-token-1", authAccount());
    expect(currentAccessToken()).toBe("access-token-1");
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(JSON.stringify(getAuthState())).not.toContain("refresh");
  });

  it("bumps the generation when the identity changes", () => {
    startSession("token-a", authAccount());
    const afterLogin = currentGeneration();
    updateTokens("token-b");
    expect(currentGeneration()).toBe(afterLogin);
    endSession();
    expect(currentGeneration()).toBe(afterLogin + 1);
    expect(getAuthState().account).toBeNull();
  });

  it("keeps the generation stable for token refresh and account updates", () => {
    startSession("token-a", authAccount());
    const generation = currentGeneration();
    updateTokens("token-b", authAccount({ roles: ["INTERVIEWER"] }));
    expect(currentGeneration()).toBe(generation);
    expect(getAuthState().account?.roles).toEqual(["INTERVIEWER"]);
    updateAccount(authAccount({ fullName: "Tên mới" }));
    expect(getAuthState().account?.fullName).toBe("Tên mới");
    expect(currentGeneration()).toBe(generation);
  });

  it("notifies subscribers until they unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToAuth(listener);
    startSession("token-a", authAccount());
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    endSession();
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
