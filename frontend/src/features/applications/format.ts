// Giờ công ty luôn là Asia/Ho_Chi_Minh, không phụ thuộc múi giờ máy của HR.
export const COMPANY_TIME_ZONE = "Asia/Ho_Chi_Minh";

function valid(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** "27/11/2026" in company time; "—" when missing or malformed. */
export function formatCompanyDate(value: string | null | undefined): string {
  const date = valid(value);
  if (!date) return "—";
  return date.toLocaleDateString("vi-VN", {
    timeZone: COMPANY_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** "08:00 02/12/2026" in company time; "—" when missing or malformed. */
export function formatCompanyDateTime(value: string | null | undefined): string {
  const date = valid(value);
  if (!date) return "—";
  const time = date.toLocaleTimeString("vi-VN", {
    timeZone: COMPANY_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${time} ${formatCompanyDate(value)}`;
}

/** "08:00" in company time. */
export function formatCompanyTime(value: string): string {
  const date = valid(value);
  if (!date) return value;
  return date.toLocaleTimeString("vi-VN", {
    timeZone: COMPANY_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** Today's date (yyyy-mm-dd) in company time. */
export function companyToday(now: Date = new Date()): string {
  return now.toLocaleDateString("en-CA", { timeZone: COMPANY_TIME_ZONE });
}

/** Adds whole days to a yyyy-mm-dd date string. */
export function addDays(date: string, days: number): string {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}
