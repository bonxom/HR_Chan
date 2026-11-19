// Widget Cloudflare Turnstile: tải script chính thức một lần, render tường minh với sitekey
// công khai, token mới/hết hạn/lỗi báo lên parent, reset theo resetKey, gỡ khi unmount.
// window.turnstile được giả lập trong test; production không có đường bỏ qua CAPTCHA.
/**
 * Contract (src/features/candidates/TurnstileWidget.tsx):
 *   <TurnstileWidget siteKey action? resetKey? onToken={(token: string | null) => void} />
 *  - Appends <script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit">
 *    once if window.turnstile is absent, then renders when the script loads.
 *  - turnstile.render(container, { sitekey, action, callback, "expired-callback",
 *    "error-callback" }) -> widgetId; callback(token) -> onToken(token);
 *    expired/error -> onToken(null).
 *  - resetKey change -> turnstile.reset(widgetId) and onToken(null).
 *  - unmount -> turnstile.remove(widgetId).
 *  - Without a siteKey nothing is rendered or loaded and a Vietnamese notice is shown.
 */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TurnstileWidget } from "./TurnstileWidget";

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface RenderOptions {
  sitekey: string;
  action?: string;
  callback: (token: string) => void;
  "expired-callback": () => void;
  "error-callback": () => void;
}

function fakeTurnstile() {
  const state: { options?: RenderOptions; container?: HTMLElement } = {};
  const api = {
    render: vi.fn((container: HTMLElement, options: RenderOptions) => {
      state.container = container;
      state.options = options;
      return "widget-1";
    }),
    reset: vi.fn(),
    remove: vi.fn(),
  };
  return { api, state };
}

function installed() {
  return document.querySelectorAll(`script[src="${SCRIPT_SRC}"]`);
}

beforeEach(() => {
  delete (window as unknown as { turnstile?: unknown }).turnstile;
  for (const script of installed()) script.remove();
});

afterEach(() => {
  delete (window as unknown as { turnstile?: unknown }).turnstile;
});

describe("TurnstileWidget", () => {
  it("tải script chính thức một lần rồi render khi script sẵn sàng", async () => {
    const { api, state } = fakeTurnstile();
    const onToken = vi.fn();
    const { rerender } = render(
      <TurnstileWidget siteKey="0x4AAA-public-site-key" action="apply" onToken={onToken} />,
    );
    rerender(<TurnstileWidget siteKey="0x4AAA-public-site-key" action="apply" onToken={onToken} />);

    expect(installed()).toHaveLength(1);
    expect(api.render).not.toHaveBeenCalled();

    await act(async () => {
      (window as unknown as { turnstile: unknown }).turnstile = api;
      installed()[0].dispatchEvent(new Event("load"));
    });

    expect(api.render).toHaveBeenCalledTimes(1);
    expect(state.options?.sitekey).toBe("0x4AAA-public-site-key");
    expect(state.options?.action).toBe("apply");
  });

  it("báo token mới, rồi null khi hết hạn hoặc lỗi", async () => {
    const { api, state } = fakeTurnstile();
    (window as unknown as { turnstile: unknown }).turnstile = api;
    const onToken = vi.fn();
    render(<TurnstileWidget siteKey="site" onToken={onToken} />);

    expect(api.render).toHaveBeenCalledTimes(1);
    expect(installed()).toHaveLength(0); // đã có sẵn: không chèn thêm script

    act(() => state.options?.callback("token-1"));
    expect(onToken).toHaveBeenLastCalledWith("token-1");
    act(() => state.options?.["expired-callback"]());
    expect(onToken).toHaveBeenLastCalledWith(null);
    act(() => state.options?.callback("token-2"));
    act(() => state.options?.["error-callback"]());
    expect(onToken).toHaveBeenLastCalledWith(null);
  });

  it("reset khi resetKey đổi và gỡ widget khi unmount", () => {
    const { api } = fakeTurnstile();
    (window as unknown as { turnstile: unknown }).turnstile = api;
    const onToken = vi.fn();
    const { rerender, unmount } = render(
      <TurnstileWidget siteKey="site" resetKey={0} onToken={onToken} />,
    );

    rerender(<TurnstileWidget siteKey="site" resetKey={1} onToken={onToken} />);
    expect(api.reset).toHaveBeenCalledWith("widget-1");
    expect(onToken).toHaveBeenLastCalledWith(null);

    unmount();
    expect(api.remove).toHaveBeenCalledWith("widget-1");
  });

  it("không có sitekey thì không tải script và báo CAPTCHA chưa sẵn sàng", () => {
    const onToken = vi.fn();
    render(<TurnstileWidget siteKey="" onToken={onToken} />);
    expect(installed()).toHaveLength(0);
    expect(screen.getByText(/CAPTCHA/)).toBeInTheDocument();
    expect(onToken).not.toHaveBeenCalledWith(expect.any(String));
  });
});
