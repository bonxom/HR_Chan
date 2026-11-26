// This module is evaluated before the router and retains the secret across remounts.
let responseToken: string | null = null;

if (typeof window !== "undefined") {
  const match = /^\/r\/([^/]+)\/?$/.exec(window.location.pathname);
  if (match) {
    try {
      responseToken = decodeURIComponent(match[1]);
    } catch {
      responseToken = null;
    }
    window.history.replaceState(window.history.state, "", "/r");
  }
}

export function getResponseToken(): string | null {
  return responseToken;
}
