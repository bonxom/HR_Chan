/** "2026-12-17" → "17/12/2026"; null or malformed values render as "—". */
export function formatDate(value: string | null): string {
  // Ngày nghiệp vụ yyyy-mm-dd được tách trực tiếp, tránh Date làm lệch múi giờ.
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : value;
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
}
