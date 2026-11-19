import { ApiError } from "@/shared/services/client";

export const MAX_CV_BYTES = 5 * 1024 * 1024;

export type ApplyField = "fullName" | "email" | "phone" | "file" | "consent" | "captcha";
export type ApplyErrors = Partial<Record<ApplyField, string>>;

/** Thứ tự hiển thị trên form, dùng để focus ô lỗi đầu tiên. */
export const APPLY_FIELD_ORDER: ApplyField[] = ["fullName", "email", "phone", "file", "consent", "captcha"];

export interface ApplyValues {
  fullName: string;
  email: string;
  phone: string;
  file: File | null;
  consent: boolean;
  captchaToken: string | null;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const FILE_TYPE_MESSAGE = "Chỉ chấp nhận CV định dạng PDF hoặc DOCX.";
export const FILE_SIZE_MESSAGE = "Tệp CV vượt quá dung lượng tối đa 5 MB.";

export function normalizePhone(value: string): string {
  return value.replace(/\s+/g, "");
}

export function validateCvFile(file: File | null): string | undefined {
  if (!file) return "Vui lòng chọn tệp CV (PDF hoặc DOCX).";
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx")) return FILE_TYPE_MESSAGE;
  if (file.size > MAX_CV_BYTES) return FILE_SIZE_MESSAGE;
  return undefined;
}

export function validateApply(values: ApplyValues): ApplyErrors {
  const errors: ApplyErrors = {};
  if (!values.fullName.trim()) errors.fullName = "Vui lòng nhập họ tên.";
  if (!values.email.trim()) errors.email = "Vui lòng nhập email.";
  else if (!EMAIL_PATTERN.test(values.email.trim())) errors.email = "Email không hợp lệ.";
  if (!values.phone.trim()) errors.phone = "Vui lòng nhập số điện thoại.";
  else if (!/^\d{10}$/.test(normalizePhone(values.phone))) errors.phone = "Số điện thoại phải gồm đúng 10 chữ số.";
  const fileError = validateCvFile(values.file);
  if (fileError) errors.file = fileError;
  if (!values.consent) errors.consent = "Bạn cần đồng ý cho phép xử lý dữ liệu cá nhân để tiếp tục.";
  if (!values.captchaToken) errors.captcha = "Vui lòng hoàn thành CAPTCHA.";
  return errors;
}

const SERVER_FIELDS: Record<string, ApplyField> = {
  full_name: "fullName",
  email: "email",
  phone: "phone",
  file: "file",
  consent: "consent",
  captcha_token: "captcha",
};

/** Lỗi server gắn được vào ô nào; phần còn lại trả về `general` để hiện ở vùng thông báo chung. */
export function mapServerError(error: unknown): { fields: ApplyErrors; general?: string } {
  if (!(error instanceof ApiError)) {
    return { fields: {}, general: "Không kết nối được máy chủ. Vui lòng thử lại." };
  }
  if (error.status === 413 || error.status === 415) return { fields: { file: error.message } };
  if (error.status === 422 && error.validationIssues) {
    const fields: ApplyErrors = {};
    for (const issue of error.validationIssues) {
      const target = SERVER_FIELDS[String(issue.loc[issue.loc.length - 1])];
      if (target && !fields[target]) fields[target] = issue.msg;
    }
    if (Object.keys(fields).length > 0) return { fields };
  }
  if (error.status === 422) return { fields: {}, general: "Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại các trường đã nhập." };
  return { fields: {}, general: withRetry(error.message, error.retryAfter, error.status === 429) };
}

export function formatWait(seconds: number): string {
  const safe = Math.max(1, Math.ceil(seconds));
  return safe >= 60 ? `${Math.ceil(safe / 60)} phút` : `${safe} giây`;
}

export function withRetry(message: string, retryAfter: number | undefined, enabled = true): string {
  return enabled && retryAfter ? `${message} Vui lòng thử lại sau ${formatWait(retryAfter)}.` : message;
}
