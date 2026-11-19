export const isDevBuild = import.meta.env.DEV;

export const env = {
  // Empty value means same-origin requests, which is the supported deployment shape.
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, ""),
  // Site key công khai của Turnstile; để trống thì form ứng tuyển không thể gửi (không bỏ qua CAPTCHA).
  turnstileSiteKey: (import.meta.env.VITE_TURNSTILE_SITE_KEY ?? "").trim(),
};
