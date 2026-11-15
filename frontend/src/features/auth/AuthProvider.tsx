import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/shared/services/client";
import * as authApi from "./api";
import { startActivityReporting } from "./activity";
import {
  broadcastAuthEvent,
  locksSupported,
  refreshSession,
  subscribeAuthEvents,
  withAuthLock,
} from "./refreshCoordinator";
import {
  currentAccessToken,
  endSession,
  startSession,
  updateAccount,
  updateTokens,
  useAuthState,
} from "./session";
import type { AuthAccount } from "./types";

export type AuthStatus = "loading" | "authenticated" | "anonymous" | "unsupported";

export interface AuthContextValue {
  status: AuthStatus;
  account: AuthAccount | null;
  login: (email: string, password: string) => Promise<AuthAccount>;
  devLogin: (persona: string) => Promise<AuthAccount>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  refreshAccount: () => Promise<void>;
  authorized: <T>(operation: (accessToken: string) => Promise<T>) => Promise<T>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const state = useAuthState();
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<"loading" | "ready" | "unsupported">("loading");

  const refreshAccount = useCallback(async () => {
    const token = currentAccessToken();
    if (!token) return;
    try {
      updateAccount(await authApi.fetchCurrentAccount(token));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        const restored = await refreshSession();
        const refreshedToken = currentAccessToken();
        if (restored && refreshedToken) {
          updateAccount(await authApi.fetchCurrentAccount(refreshedToken));
          return;
        }
        endSession();
        queryClient.clear();
      }
    }
  }, [queryClient]);

  const authorized = useCallback(
    async <T,>(operation: (accessToken: string) => Promise<T>): Promise<T> => {
      let token = currentAccessToken();
      if (!token) {
        const restored = await refreshSession();
        token = currentAccessToken();
        if (!restored || !token) throw new ApiError(401, "invalid_session", "Session expired");
      }
      try {
        return await operation(token);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          const restored = await refreshSession();
          const refreshedToken = currentAccessToken();
          if (restored && refreshedToken) return await operation(refreshedToken);
          endSession();
          queryClient.clear();
        }
        throw error;
      }
    },
    [queryClient],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await withAuthLock(() => authApi.loginRequest(email, password));
      startSession(session.accessToken, session.account);
      queryClient.clear();
      broadcastAuthEvent({ type: "identity-changed" });
      return session.account;
    },
    [queryClient],
  );

  const devLogin = useCallback(
    async (persona: string) => {
      const session = await withAuthLock(() => authApi.devLoginRequest(persona));
      startSession(session.accessToken, session.account);
      queryClient.clear();
      broadcastAuthEvent({ type: "identity-changed" });
      return session.account;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await withAuthLock(() => authApi.logoutRequest());
    } catch {
      // Local state still ends when the network or browser support fails.
    }
    endSession();
    queryClient.clear();
    broadcastAuthEvent({ type: "logout" });
  }, [queryClient]);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const session = await withAuthLock(() => {
        const token = currentAccessToken();
        if (!token) throw new ApiError(401, "invalid_session", "Session expired");
        return authApi.changePasswordRequest(token, currentPassword, newPassword);
      });
      updateTokens(session.accessToken, session.account);
    },
    [],
  );

  // Bootstrap once from the refresh cookie, then load the current account.
  useEffect(() => {
    let cancelled = false;
    if (!locksSupported()) {
      setPhase("unsupported");
      return;
    }
    void (async () => {
      const restored = await refreshSession();
      if (cancelled) return;
      if (restored) {
        const token = currentAccessToken();
        if (token) {
          try {
            updateAccount(await authApi.fetchCurrentAccount(token));
          } catch {
            endSession();
          }
        }
      }
      if (!cancelled) setPhase("ready");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Cross-tab invalidation: logout and identity changes.
  useEffect(
    () =>
      subscribeAuthEvents((event) => {
        if (event.type === "logout") {
          endSession();
          queryClient.clear();
          return;
        }
        queryClient.clear();
        void refreshAccount();
      }),
    [queryClient, refreshAccount],
  );

  useEffect(() => {
    if (state.account === null) return undefined;
    return startActivityReporting(currentAccessToken);
  }, [state.account]);

  // Reconcile roles when the tab regains focus.
  useEffect(() => {
    if (!state.account) return undefined;
    const onFocus = () => {
      void refreshAccount();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [state.account, refreshAccount]);

  const status: AuthStatus = useMemo(() => {
    if (phase === "unsupported") return "unsupported";
    if (state.account) return "authenticated";
    if (phase === "loading") return "loading";
    return "anonymous";
  }, [phase, state.account]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      account: state.account,
      login,
      devLogin,
      logout,
      changePassword,
      refreshAccount,
      authorized,
    }),
    [
      status,
      state.account,
      login,
      devLogin,
      logout,
      changePassword,
      refreshAccount,
      authorized,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
