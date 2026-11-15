export const isDevBuild = import.meta.env.DEV;

export const env = {
  // Empty value means same-origin requests, which is the supported deployment shape.
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, ""),
};
