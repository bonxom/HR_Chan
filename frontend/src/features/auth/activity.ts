import { reportActivity } from "./api";

export const ACTIVITY_INTERVAL_MS = 60_000;
const ACTIVITY_EVENTS = ["keydown", "click", "scroll"] as const;

/**
 * Report visible-tab interaction at most once per minute.
 * Bootstrap and polling are deliberately not activity.
 */
export function startActivityReporting(getToken: () => string | null): () => void {
  if (typeof document === "undefined") return () => {};
  let lastReport = 0;

  const report = () => {
    if (document.visibilityState !== "visible") return;
    const now = Date.now();
    if (now - lastReport < ACTIVITY_INTERVAL_MS) return;
    const token = getToken();
    if (!token) return;
    lastReport = now;
    void reportActivity(token).catch(() => {
      // Activity is advisory; failures never affect the session.
    });
  };

  for (const name of ACTIVITY_EVENTS) {
    document.addEventListener(name, report, { passive: true });
  }
  return () => {
    for (const name of ACTIVITY_EVENTS) document.removeEventListener(name, report);
  };
}
