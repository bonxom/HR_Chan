// Kiểm tra và ánh xạ lỗi theo từng ô cho form tin tuyển dụng/bộ tiêu chí.
// Quy tắc phía client hỗ trợ nhập liệu; backend vẫn kiểm tra dữ liệu cuối cùng.
// Lỗi hàng tiêu chí gắn với key ổn định, không gắn với chỉ số hiển thị. Khi xóa
// hàng, số thứ tự trong thông báo được tính lại mà không chuyển lỗi sang hàng khác.
import type { ApiValidationIssue } from "@/shared/services/client";
import type { CriteriaDraft, CriteriaDraftRow } from "./CriteriaEditor";

export const LIMITS = {
  title: 200,
  description: 5000,
  requirements: 5000,
  benefits: 3000,
  workMode: 50,
  location: 200,
  criterionName: 150,
  criterionDescription: 1000,
  int32Max: 2_147_483_647,
} as const;

export type Reason =
  | "required"
  | "tooShort"
  | "tooLong"
  | "gt"
  | "ge"
  | "lt"
  | "le"
  | "integer"
  | "number"
  | "decimals"
  | "maxDigits"
  | "date"
  | "pastDate"
  | "duplicate"
  | "totalWeight"
  | "invalid";

export interface FieldIssue {
  reason: Reason;
  /** Giới hạn dài/số/thập phân; riêng totalWeight là tổng trọng số đang có. */
  limit?: number;
}

/**
 * Khóa lỗi: trường tin (title, departmentId...), nhóm (threshold, interviewers,
 * criteria) hoặc ô tiêu chí theo dạng row:<draftKey>:name|description|weight.
 */
export type FieldErrors = Record<string, FieldIssue>;

export interface JobFormValues {
  title: string;
  departmentId: string;
  description: string;
  requirements: string;
  benefits: string;
  headcount: string;
  workMode: string;
  location: string;
  deadline: string;
}

export type JobFieldKey = keyof JobFormValues;
/** draft kiểm tra dữ liệu nháp; publish bổ sung các trường phải có khi tin mở. */
export type JobRule = "draft" | "publish";
export type RowField = "name" | "description" | "weight" | "minScore";

const REQUIRED: FieldIssue = { reason: "required" };

export function rowErrorKey(rowKey: string, field: RowField): string {
  return `row:${rowKey}:${field}`;
}

function parseRowErrorKey(key: string): { rowKey: string; field: RowField } | null {
  const match = /^row:(.+):(name|description|weight|minScore)$/.exec(key);
  return match ? { rowKey: match[1], field: match[2] as RowField } : null;
}

/** Ngày hiện tại yyyy-mm-dd theo UTC+7 để so hạn nộp giống backend. */
export function companyToday(now: Date = new Date()): string {
  return new Date(now.getTime() + 7 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

function decimalPlaces(value: number): number {
  const [mantissa, exponent] = String(value).split("e");
  const fraction = mantissa.split(".")[1]?.length ?? 0;
  return Math.max(0, fraction - Number(exponent ?? 0));
}

function checkText(value: string, max: number, required: boolean): FieldIssue | null {
  const trimmed = value.trim();
  if (!trimmed) return required ? REQUIRED : null;
  // The backend counts Unicode code points; `length` counts UTF-16 units (an emoji is 2).
  return Array.from(trimmed).length > max ? { reason: "tooLong", limit: max } : null;
}

export function validateJobFields(values: JobFormValues, rule: JobRule, today = companyToday()): FieldErrors {
  const publish = rule === "publish";
  const errors: FieldErrors = {};
  const put = (key: JobFieldKey, issue: FieldIssue | null) => {
    if (issue) errors[key] = issue;
  };

  put("title", checkText(values.title, LIMITS.title, true));
  put("departmentId", values.departmentId ? null : REQUIRED);
  put("workMode", checkText(values.workMode, LIMITS.workMode, false));
  put("location", checkText(values.location, LIMITS.location, false));
  put("description", checkText(values.description, LIMITS.description, publish));
  put("requirements", checkText(values.requirements, LIMITS.requirements, publish));
  put("benefits", checkText(values.benefits, LIMITS.benefits, false));

  const headcount = values.headcount.trim();
  if (!headcount) {
    put("headcount", publish ? REQUIRED : null);
  } else {
    const count = Number(headcount);
    if (!Number.isFinite(count)) put("headcount", { reason: "number" });
    else if (!Number.isInteger(count)) put("headcount", { reason: "integer" });
    else if (count <= 0) put("headcount", { reason: "gt", limit: 0 });
    else if (count > LIMITS.int32Max) put("headcount", { reason: "le", limit: LIMITS.int32Max });
  }

  if (!values.deadline) put("deadline", publish ? REQUIRED : null);
  else if (!/^\d{4}-\d{2}-\d{2}$/.test(values.deadline)) put("deadline", { reason: "date" });
  else if (publish && values.deadline < today) put("deadline", { reason: "pastDate" });

  return errors;
}

function checkDecimal(value: number, min: { reason: "gt" | "ge"; limit: number }, max: number): FieldIssue | null {
  if (!Number.isFinite(value)) return { reason: "number" };
  if (min.reason === "gt" ? value <= min.limit : value < min.limit) return min;
  if (value > max) return { reason: "le", limit: max };
  if (decimalPlaces(value) > 2) return { reason: "decimals", limit: 2 };
  return null;
}

/**
 * Hễ gửi bộ tiêu chí thì phải đủ: tên/mô tả, tên không trùng, tổng trọng số100,
 * ít nhất một tiêu chí và người phỏng vấn. Áp dụng cả nháp đã nhập bộ tiêu chí.
 */
export function validateCriteria(draft: CriteriaDraft): FieldErrors {
  const errors: FieldErrors = {};

  // Chọn ngưỡng mặc định thì gửi null, nên giá trị slider không cần kiểm tra.
  if (!draft.useDefaultThreshold) {
    const issue = checkDecimal(draft.threshold, { reason: "ge", limit: 0 }, 100);
    if (issue) errors.threshold = issue;
  }
  if (draft.interviewerIds.length === 0) errors.interviewers = REQUIRED;
  if (draft.criteria.length === 0) errors.criteria = REQUIRED;

  const seenNames = new Set<string>();
  for (const row of draft.criteria) {
    const nameIssue = checkText(row.name, LIMITS.criterionName, true);
    if (nameIssue) {
      errors[rowErrorKey(row.key, "name")] = nameIssue;
    } else {
      const folded = row.name.trim().toLowerCase();
      if (seenNames.has(folded)) errors[rowErrorKey(row.key, "name")] = { reason: "duplicate" };
      seenNames.add(folded);
    }
    const descriptionIssue = checkText(row.description, LIMITS.criterionDescription, true);
    if (descriptionIssue) errors[rowErrorKey(row.key, "description")] = descriptionIssue;
    const weightIssue = checkDecimal(row.weight, { reason: "gt", limit: 0 }, 100);
    if (weightIssue) errors[rowErrorKey(row.key, "weight")] = weightIssue;
    if (row.isMandatory) {
      const issue = row.minScore == null ? REQUIRED : checkDecimal(row.minScore, { reason: "ge", limit: 0 }, 100);
      if (issue) errors[rowErrorKey(row.key, "minScore")] = issue;
    }
  }

  if (draft.criteria.length > 0) {
    // Cộng theo phần trăm của một điểm để tránh sai số số thực, ví dụ
    // 33.33 + 33.33 + 33.34. Mỗi trọng số được phép tối đa hai chữ số thập phân.
    const cents = draft.criteria.reduce(
      (sum, row) => sum + (Number.isFinite(row.weight) ? Math.round(row.weight * 100) : 0),
      0,
    );
    if (cents !== 10_000) errors.criteria = { reason: "totalWeight", limit: cents / 100 };
  }
  return errors;
}

// Lỗi phụ thuộc nhiều ô phải tính lại khi dữ liệu liên quan thay đổi.
const CROSS_FIELD: ReadonlySet<Reason> = new Set<Reason>(["duplicate", "totalWeight"]);

/**
 * Chỉ cập nhật lỗi đang hiển thị: xét lại ô vừa sửa và lỗi liên quan nhiều ô,
 * bỏ lỗi của hàng đã xóa; giữ lỗi các ô khác, kể cả lỗi server, tới khi ô đó được sửa.
 */
export function refreshErrors(
  current: FieldErrors,
  computed: FieldErrors,
  touched: readonly string[],
  rows: readonly CriteriaDraftRow[],
): FieldErrors {
  const rowKeys = new Set(rows.map((row) => row.key));
  const next: FieldErrors = {};
  for (const [key, issue] of Object.entries(current)) {
    const row = parseRowErrorKey(key);
    if (row && !rowKeys.has(row.rowKey)) continue;
    if (touched.includes(key) || CROSS_FIELD.has(issue.reason)) {
      if (computed[key]) next[key] = computed[key];
    } else {
      next[key] = issue;
    }
  }
  return next;
}

// ---- Server (FastAPI 422) issues ----

const API_JOB_FIELDS: Record<string, JobFieldKey> = {
  title: "title",
  department_id: "departmentId",
  description: "description",
  requirements: "requirements",
  benefits: "benefits",
  headcount: "headcount",
  work_mode: "workMode",
  location: "location",
  deadline: "deadline",
};

const API_ROW_FIELDS: Record<string, RowField> = { name: "name", description: "description", weight: "weight", min_score: "minScore" };

export interface ServerIssueTarget {
  /** Whether the request carried the job posting fields (create/update). */
  jobFields: boolean;
  /** Body path of the criteria set: `["criteria"]` when nested in create, `[]` when standalone. */
  criteriaPath: readonly string[] | null;
  /** Criteria rows as submitted; row indices in `loc` refer to this order. */
  rows: readonly CriteriaDraftRow[];
}

function fieldKeyFor(loc: readonly (string | number)[], target: ServerIssueTarget): string | null {
  // Tạo cả tin: body.criteria.criteria[0].name; lưu bộ tiêu chí riêng:
  // body.criteria[0].name. Đổi chỉ số API sang key hàng của lần gửi tương ứng.
  const path = loc[0] === "body" ? loc.slice(1) : loc;
  const [head] = path;
  if (target.jobFields && typeof head === "string" && Object.hasOwn(API_JOB_FIELDS, head)) {
    return API_JOB_FIELDS[head];
  }

  const base = target.criteriaPath;
  if (!base || path.length <= base.length || !base.every((part, index) => path[index] === part)) return null;
  const [group, index, field] = path.slice(base.length);
  if (group === "auto_invite_threshold") return "threshold";
  if (group === "interviewer_ids") return "interviewers";
  if (group !== "criteria") return null;
  if (index === undefined) return "criteria";
  const row = typeof index === "number" ? target.rows[index] : undefined;
  const rowField = typeof field === "string" && Object.hasOwn(API_ROW_FIELDS, field) ? API_ROW_FIELDS[field] : undefined;
  return row && rowField ? rowErrorKey(row.key, rowField) : null;
}

function issueFromServer(issue: ApiValidationIssue): FieldIssue {
  const ctx = issue.ctx ?? {};
  switch (issue.type) {
    case "missing":
      return REQUIRED;
    case "string_too_short":
      return (ctx.min_length ?? 1) <= 1 ? REQUIRED : { reason: "tooShort", limit: ctx.min_length };
    case "string_too_long":
      return { reason: "tooLong", limit: ctx.max_length };
    case "greater_than":
      return { reason: "gt", limit: ctx.gt };
    case "greater_than_equal":
      return { reason: "ge", limit: ctx.ge };
    case "less_than":
      return { reason: "lt", limit: ctx.lt };
    case "less_than_equal":
      return { reason: "le", limit: ctx.le };
    case "decimal_max_places":
      return { reason: "decimals", limit: ctx.decimal_places };
    case "decimal_max_digits":
    case "decimal_whole_digits":
      return { reason: "maxDigits", limit: ctx.max_digits ?? ctx.whole_digits };
    case "int_parsing":
    case "int_from_float":
    case "int_type":
      return { reason: "integer" };
    case "float_parsing":
    case "float_type":
    case "decimal_parsing":
    case "decimal_type":
    case "finite_number":
      return { reason: "number" };
    default:
      return issue.type.startsWith("date") ? { reason: "date" } : { reason: "invalid" };
  }
}

/** Ghép lỗi422 vào ô đã biết; đường dẫn lạ chỉ báo tổng hợp, không đoán nhầm ô. */
export function mapServerIssues(
  issues: readonly ApiValidationIssue[],
  target: ServerIssueTarget,
): { errors: FieldErrors; unmapped: number } {
  const errors: FieldErrors = {};
  let unmapped = 0;
  for (const issue of issues) {
    const key = fieldKeyFor(issue.loc, target);
    if (!key) unmapped += 1;
    else if (!errors[key]) errors[key] = issueFromServer(issue);
  }
  return { errors, unmapped };
}

export const UNMAPPED_SERVER_MESSAGE =
  "Có dữ liệu chưa hợp lệ nhưng không xác định được ô tương ứng. Vui lòng kiểm tra lại các thông tin đã nhập.";

// ---- Messages ----

interface FieldLabel {
  label: string;
  missing: string;
}

const JOB_LABELS: Record<JobFieldKey, FieldLabel> = {
  title: { label: "Tên vị trí", missing: "Chưa nhập tên vị trí" },
  departmentId: { label: "Phòng ban", missing: "Chưa chọn phòng ban" },
  workMode: { label: "Hình thức làm việc", missing: "Chưa nhập hình thức làm việc" },
  headcount: { label: "Số lượng cần tuyển", missing: "Chưa nhập số lượng cần tuyển" },
  deadline: { label: "Hạn nộp hồ sơ", missing: "Chưa chọn hạn nộp hồ sơ" },
  location: { label: "Địa điểm làm việc", missing: "Chưa nhập địa điểm làm việc" },
  description: { label: "Mô tả công việc", missing: "Chưa nhập mô tả công việc" },
  requirements: { label: "Yêu cầu ứng viên", missing: "Chưa nhập yêu cầu ứng viên" },
  benefits: { label: "Quyền lợi", missing: "Chưa nhập quyền lợi" },
};

const GROUP_LABELS: Record<string, FieldLabel> = {
  threshold: { label: "Ngưỡng tự động mời phỏng vấn", missing: "Chưa nhập ngưỡng tự động mời phỏng vấn" },
  interviewers: { label: "Người phỏng vấn", missing: "Chọn ít nhất một người phỏng vấn" },
  criteria: { label: "Bộ tiêu chí", missing: "Cần ít nhất một tiêu chí chấm điểm" },
};

function rowLabel(field: RowField, number: number): FieldLabel {
  const noun = { name: "tên", description: "mô tả", weight: "trọng số", minScore: "điểm sàn" }[field];
  const label = `${noun[0].toUpperCase()}${noun.slice(1)} tiêu chí ${number}`;
  return { label, missing: `Chưa nhập ${noun} tiêu chí ${number}` };
}

function describeIssue({ label, missing }: FieldLabel, issue: FieldIssue): string {
  const limit = issue.limit;
  const known = limit !== undefined;
  switch (issue.reason) {
    case "required":
      return missing;
    case "tooShort":
      return known ? `${label} cần ít nhất ${limit} ký tự` : `${label} quá ngắn`;
    case "tooLong":
      return known ? `${label} tối đa ${limit} ký tự` : `${label} vượt quá độ dài cho phép`;
    case "gt":
      return known ? `${label} phải lớn hơn ${limit}` : `${label} nằm ngoài khoảng cho phép`;
    case "ge":
      return known ? `${label} phải từ ${limit} trở lên` : `${label} nằm ngoài khoảng cho phép`;
    case "lt":
      return known ? `${label} phải nhỏ hơn ${limit}` : `${label} nằm ngoài khoảng cho phép`;
    case "le":
      return known ? `${label} không được lớn hơn ${limit}` : `${label} nằm ngoài khoảng cho phép`;
    case "integer":
      return `${label} phải là số nguyên`;
    case "number":
      return `${label} phải là số`;
    case "decimals":
      return `${label} chỉ được có tối đa ${limit ?? 2} chữ số thập phân`;
    case "maxDigits":
      return known ? `${label} chỉ được có tối đa ${limit} chữ số` : `${label} có quá nhiều chữ số`;
    case "date":
      return `${label} không đúng định dạng ngày`;
    case "pastDate":
      return `${label} không được trước ngày hôm nay`;
    case "duplicate":
      return `${label} bị trùng với một tiêu chí khác`;
    case "totalWeight":
      return `Tổng trọng số phải bằng 100${known ? ` (hiện tại ${limit})` : ""}`;
    default:
      return `${label} không hợp lệ`;
  }
}

/** Vietnamese message for an error key; row numbers follow the current row order. */
export function errorMessage(key: string, issue: FieldIssue, rows: readonly CriteriaDraftRow[] = []): string {
  if (Object.hasOwn(JOB_LABELS, key)) return describeIssue(JOB_LABELS[key as JobFieldKey], issue);
  if (Object.hasOwn(GROUP_LABELS, key)) return describeIssue(GROUP_LABELS[key], issue);
  const row = parseRowErrorKey(key);
  const index = row ? rows.findIndex((item) => item.key === row.rowKey) : -1;
  if (row && index >= 0) return describeIssue(rowLabel(row.field, index + 1), issue);
  return describeIssue({ label: "Dữ liệu", missing: "Thiếu dữ liệu" }, issue);
}

// ---- Summary order and element ids ----

const JOB_ORDER: JobFieldKey[] = [
  "title",
  "departmentId",
  "workMode",
  "headcount",
  "deadline",
  "location",
  "description",
  "requirements",
  "benefits",
];

/** Error keys in on-screen order: job fields, then the criteria editor top to bottom. */
export function orderedErrorKeys(errors: FieldErrors, rows: readonly CriteriaDraftRow[] = []): string[] {
  const order: string[] = [...JOB_ORDER, "threshold", "interviewers", "criteria"];
  for (const row of rows) {
    order.push(rowErrorKey(row.key, "name"), rowErrorKey(row.key, "weight"), rowErrorKey(row.key, "description"));
  }
  return order.filter((key) => errors[key]);
}

/** Element id of a criteria editor field/group, shared by the editor and the error summary. */
export function criteriaFieldId(idPrefix: string, key: string): string {
  const row = parseRowErrorKey(key);
  return row ? `${idPrefix}-${row.rowKey}-${row.field}` : `${idPrefix}-${key}`;
}

export interface ErrorSummaryItem {
  key: string;
  message: string;
  targetId: string;
}

export function errorSummaryItems(
  errors: FieldErrors,
  rows: readonly CriteriaDraftRow[],
  idOf: (key: string) => string,
): ErrorSummaryItem[] {
  return orderedErrorKeys(errors, rows).map((key) => ({
    key,
    message: errorMessage(key, errors[key], rows),
    targetId: idOf(key),
  }));
}
