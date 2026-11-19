import { useEffect, useRef } from "react";

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface TurnstileApi {
  render(
    container: HTMLElement,
    options: {
      sitekey: string;
      action?: string;
      callback: (token: string) => void;
      "expired-callback": () => void;
      "error-callback": () => void;
    },
  ): string;
  reset(widgetId: string): void;
  remove(widgetId: string): void;
}

const getTurnstile = () => (window as unknown as { turnstile?: TurnstileApi }).turnstile;

interface TurnstileWidgetProps {
  siteKey: string;
  action?: string;
  /** Đổi giá trị để đặt lại widget (token Turnstile chỉ dùng được một lần). */
  resetKey?: number;
  onToken: (token: string | null) => void;
}

/** Widget Cloudflare Turnstile. Không có siteKey thì không tải gì và không có cách bỏ qua CAPTCHA. */
export function TurnstileWidget({ siteKey, action, resetKey = 0, onToken }: TurnstileWidgetProps) {
  const container = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  const onTokenRef = useRef(onToken);
  const lastReset = useRef(resetKey);
  onTokenRef.current = onToken;

  useEffect(() => {
    if (!siteKey || !container.current) return;
    const target = container.current;
    let cancelled = false;

    const renderWidget = () => {
      const api = getTurnstile();
      if (cancelled || !api || widgetId.current !== null) return;
      widgetId.current = api.render(target, {
        sitekey: siteKey,
        action,
        callback: (token) => onTokenRef.current(token),
        "expired-callback": () => onTokenRef.current(null),
        "error-callback": () => onTokenRef.current(null),
      });
    };

    let script: HTMLScriptElement | null = null;
    if (getTurnstile()) {
      renderWidget();
    } else {
      script = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_SRC}"]`);
      if (!script) {
        script = document.createElement("script");
        script.src = SCRIPT_SRC;
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
      }
      script.addEventListener("load", renderWidget);
    }

    return () => {
      cancelled = true;
      script?.removeEventListener("load", renderWidget);
      const api = getTurnstile();
      if (api && widgetId.current !== null) api.remove(widgetId.current);
      widgetId.current = null;
    };
  }, [siteKey, action]);

  useEffect(() => {
    if (resetKey === lastReset.current) return;
    lastReset.current = resetKey;
    const api = getTurnstile();
    if (api && widgetId.current !== null) api.reset(widgetId.current);
    onTokenRef.current(null);
  }, [resetKey]);

  if (!siteKey) {
    return (
      <p role="status" className="text-xs text-rose-600">
        CAPTCHA chưa được cấu hình nên chưa thể nộp hồ sơ. Vui lòng liên hệ quản trị viên.
      </p>
    );
  }
  return <div ref={container} data-testid="turnstile-container" />;
}
