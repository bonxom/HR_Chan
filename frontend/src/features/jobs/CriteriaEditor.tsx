import { Plus } from "lucide-react";
import { Button } from "@/shared/components/ui/Button";
import type { CriteriaInput, CriteriaSet, Criterion, Interviewer } from "./types";
import { criteriaFieldId, errorMessage, rowErrorKey, type FieldErrors, type RowField } from "./validation";

/** key nhận diện hàng trong form; không gửi lên API và không đổi khi xóa hàng khác. */
export interface CriteriaDraftRow extends Criterion {
  key: string;
}

export interface CriteriaDraft {
  useDefaultThreshold: boolean;
  threshold: number;
  criteria: CriteriaDraftRow[];
  interviewerIds: string[];
}

// Starting values of a new criteria set. The slider value is only a starting point; with
// "use system default" ticked the backend decides the threshold.
const SLIDER_START = 50;
const FIRST_ROW_WEIGHT = 100;
const ADDED_ROW_WEIGHT = 0;

let rowCounter = 0;
function newRowKey(): string {
  rowCounter += 1;
  return `c${rowCounter}`;
}

function blankRow(weight: number): CriteriaDraftRow {
  return { key: newRowKey(), name: "", description: "", isMandatory: false, weight };
}

export function emptyCriteriaDraft(): CriteriaDraft {
  return {
    useDefaultThreshold: true,
    threshold: SLIDER_START,
    criteria: [blankRow(FIRST_ROW_WEIGHT)],
    interviewerIds: [],
  };
}

/**
 * Chỉ coi là trống khi các giá trị khớp trạng thái ban đầu do emptyCriteriaDraft tạo.
 * So cả ngưỡng, checkbox, trọng số và số hàng để không bỏ dữ liệu đang nhập dở.
 * Đây là so giá trị hiện tại, không phải cờ ghi nhớ người dùng đã từng tương tác.
 */
export function isCriteriaDraftPristine(draft: CriteriaDraft): boolean {
  const [row, ...rest] = draft.criteria;
  return (
    draft.useDefaultThreshold &&
    draft.threshold === SLIDER_START &&
    draft.interviewerIds.length === 0 &&
    rest.length === 0 &&
    row !== undefined &&
    row.name === "" &&
    row.description === "" &&
    !row.isMandatory &&
    row.weight === FIRST_ROW_WEIGHT
  );
}

export function criteriaDraftFrom(set: CriteriaSet | null, interviewers: Interviewer[]): CriteriaDraft {
  if (!set) return { ...emptyCriteriaDraft(), interviewerIds: interviewers.map((item) => item.id) };
  return {
    useDefaultThreshold: false,
    threshold: set.autoInviteThreshold,
    criteria: set.criteria.map((item) => ({ ...item, key: newRowKey() })),
    interviewerIds: interviewers.map((item) => item.id),
  };
}

export function criteriaInputFrom(draft: CriteriaDraft): CriteriaInput {
  // Bỏ key nội bộ và chuẩn hóa chuỗi; null ngưỡng yêu cầu backend lấy cấu hình chung.
  return {
    autoInviteThreshold: draft.useDefaultThreshold ? null : draft.threshold,
    criteria: draft.criteria.map((item) => ({
      name: item.name.trim(),
      description: item.description.trim(),
      isMandatory: item.isMandatory,
      ...(item.isMandatory && { minScore: item.minScore }),
      weight: item.weight,
    })),
    interviewerIds: draft.interviewerIds,
  };
}

interface CriteriaEditorProps {
  value: CriteriaDraft;
  /** `touched` lists the error keys whose input changed, so only those get re-checked. */
  onChange: (value: CriteriaDraft, touched: string[]) => void;
  interviewers: Interviewer[];
  disabled?: boolean;
  errors?: FieldErrors;
  /** Prefix for element ids; the form's error summary uses the same ids to move focus. */
  idPrefix: string;
}

/** Red border of an invalid group (threshold, interviewers, criteria list). */
const RED = "border-rose-400";
/** An invalid input keeps a red border all around, also while focused (no green focus). */
const INVALID_FIELD = "border border-rose-400 focus:outline-none focus:border-rose-400 focus:ring-1 focus:ring-rose-400";

export function CriteriaEditor({
  value,
  onChange,
  interviewers,
  disabled = false,
  errors = {},
  idPrefix,
}: CriteriaEditorProps) {
  const totalWeight = value.criteria.reduce((sum, item) => sum + (Number(item.weight) || 0), 0);
  const idOf = (key: string) => criteriaFieldId(idPrefix, key);
  const messageOf = (key: string) => (errors[key] ? errorMessage(key, errors[key], value.criteria) : undefined);
  /** aria props for a field or group plus the id its message is rendered under. */
  const aria = (key: string) => {
    const message = messageOf(key);
    return {
      "aria-invalid": message ? true : undefined,
      "aria-describedby": message ? `${idOf(key)}-error` : undefined,
    };
  };
  const errorText = (key: string, className = "text-xs") => {
    const message = messageOf(key);
    return message ? (
      <p id={`${idOf(key)}-error`} className={`${className} text-rose-600`}>
        {message}
      </p>
    ) : null;
  };

  const updateCriterion = (index: number, patch: Partial<Criterion>, touched: string[]) =>
    onChange(
      {
        ...value,
        criteria: value.criteria.map((item, position) => (position === index ? { ...item, ...patch } : item)),
      },
      touched,
    );

  const toggleInterviewer = (id: string, checked: boolean) =>
    onChange(
      {
        ...value,
        interviewerIds: checked
          ? [...value.interviewerIds, id]
          : value.interviewerIds.filter((item) => item !== id),
      },
      ["interviewers"],
    );

  const thresholdInvalid = Boolean(messageOf("threshold"));
  const interviewersInvalid = Boolean(messageOf("interviewers"));
  const criteriaInvalid = Boolean(messageOf("criteria"));

  return (
    <fieldset disabled={disabled} className="space-y-4">
      <div
        className={`p-3 bg-slate-50 border rounded-xl space-y-2 ${thresholdInvalid ? RED : "border-slate-200"}`}
      >
        <label className="flex items-center gap-2 text-xs text-slate-700">
          <input
            type="checkbox"
            checked={value.useDefaultThreshold}
            onChange={(event) => onChange({ ...value, useDefaultThreshold: event.target.checked }, ["threshold"])}
            className="rounded text-emerald-600"
          />
          Dùng ngưỡng mặc định của hệ thống
        </label>
        <label htmlFor={idOf("threshold")} className="block text-xs text-slate-600">
          Ngưỡng điểm tự động mời phỏng vấn:{" "}
          <strong>{value.useDefaultThreshold ? "theo cấu hình hệ thống" : `${value.threshold}/100`}</strong>
        </label>
        <input
          id={idOf("threshold")}
          aria-label="Ngưỡng tự động mời phỏng vấn"
          type="range"
          min={0}
          max={100}
          step={1}
          value={value.threshold}
          disabled={disabled || value.useDefaultThreshold}
          onChange={(event) => onChange({ ...value, threshold: Number(event.target.value) }, ["threshold"])}
          className="w-full accent-emerald-600 disabled:opacity-40"
          {...aria("threshold")}
        />
        {errorText("threshold")}
      </div>

      <fieldset
        id={idOf("interviewers")}
        tabIndex={-1}
        className={`border rounded-lg ${interviewersInvalid ? `${RED} p-2` : "border-transparent"}`}
        {...aria("interviewers")}
      >
        <legend className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">Người phỏng vấn</legend>
        {interviewers.length === 0 ? (
          <p className="text-xs text-slate-500">Chưa có nhân viên nào giữ vai trò người phỏng vấn.</p>
        ) : (
          <div className="flex flex-wrap gap-3">
            {interviewers.map((item) => (
              <label key={item.id} className="flex items-center gap-1.5 text-xs text-slate-700">
                <input
                  type="checkbox"
                  aria-label={`Người phỏng vấn: ${item.fullName}`}
                  checked={value.interviewerIds.includes(item.id)}
                  onChange={(event) => toggleInterviewer(item.id, event.target.checked)}
                  className="rounded text-emerald-600"
                />
                {item.fullName}
              </label>
            ))}
          </div>
        )}
        {errorText("interviewers", "mt-1.5 text-xs")}
      </fieldset>

      <div
        id={idOf("criteria")}
        role="group"
        aria-label="Tiêu chí chấm điểm"
        className={`space-y-3 border rounded-xl ${criteriaInvalid ? `${RED} p-2` : "border-transparent"}`}
        {...aria("criteria")}
      >
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-slate-800">Tiêu chí chấm điểm</span>
          <span className={`font-bold ${totalWeight === 100 ? "text-emerald-700" : "text-rose-600"}`}>
            Tổng trọng số: {totalWeight}/100
          </span>
        </div>
        {errorText("criteria")}

        {value.criteria.map((item, index) => {
          const number = index + 1;
          const keyOf = (field: RowField) => rowErrorKey(item.key, field);
          const nameKey = keyOf("name");
          const weightKey = keyOf("weight");
          const descriptionKey = keyOf("description");
          const floorKey = keyOf("minScore");
          return (
            <div key={item.key} className="p-3.5 bg-white border border-slate-200 rounded-xl space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <input
                    id={idOf(nameKey)}
                    type="text"
                    aria-label={`Tên tiêu chí ${number}`}
                    value={item.name}
                    maxLength={150}
                    onChange={(event) => updateCriterion(index, { name: event.target.value }, [nameKey])}
                    placeholder="Tên tiêu chí"
                    className={`w-full font-bold text-xs text-slate-800 pb-1 ${
                      messageOf(nameKey)
                        ? `${INVALID_FIELD} rounded px-1.5 pt-1`
                        : "border-b border-slate-200 focus:outline-none focus:border-emerald-500"
                    }`}
                    {...aria(nameKey)}
                  />
                  {errorText(nameKey, "mt-1 text-[11px]")}
                </div>
                <div className="shrink-0 text-right">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-slate-400">Trọng số:</span>
                    <input
                      id={idOf(weightKey)}
                      type="number"
                      aria-label={`Trọng số tiêu chí ${number}`}
                      min={0.01}
                      max={100}
                      step={0.01}
                      value={item.weight}
                      data-error-focus={index === 0 ? "" : undefined}
                      onChange={(event) =>
                        updateCriterion(index, { weight: Number(event.target.value) }, [weightKey, "criteria"])
                      }
                      className={`w-16 text-center text-xs font-bold rounded p-1 ${
                        messageOf(weightKey) ? INVALID_FIELD : "border border-slate-300"
                      }`}
                      {...aria(weightKey)}
                    />
                  </div>
                  {errorText(weightKey, "mt-1 max-w-48 text-[11px]")}
                </div>
              </div>
              <input
                id={idOf(descriptionKey)}
                type="text"
                aria-label={`Mô tả tiêu chí ${number}`}
                value={item.description}
                maxLength={1000}
                onChange={(event) => updateCriterion(index, { description: event.target.value }, [descriptionKey])}
                placeholder="Mô tả chi tiết để AI đánh giá"
                className={`w-full text-xs text-slate-600 rounded p-1.5 ${
                  messageOf(descriptionKey) ? INVALID_FIELD : "border border-slate-200"
                }`}
                {...aria(descriptionKey)}
              />
              {errorText(descriptionKey, "text-[11px]")}
              <div className="flex items-center justify-between pt-1 text-[11px]">
                <label className="flex items-center gap-1.5 text-slate-700">
                  <input
                    type="checkbox"
                    aria-label={`Tiêu chí bắt buộc ${number}`}
                    checked={item.isMandatory}
                    onChange={(event) => updateCriterion(index, { isMandatory: event.target.checked, minScore: undefined }, [floorKey])}
                    className="rounded text-emerald-600"
                  />
                  Tiêu chí bắt buộc (không đạt thì không tự động mời)
                </label>
                {item.isMandatory && (
                  <div>
                    <label htmlFor={idOf(floorKey)}>Điểm sàn tiêu chí {number}</label>
                    <input
                      id={idOf(floorKey)} type="number" min={0} max={100} step={0.01}
                      value={item.minScore ?? ""}
                      onChange={(event) => updateCriterion(index, {
                        minScore: event.target.value === "" ? undefined : event.target.valueAsNumber,
                      }, [floorKey])}
                      className={`ml-2 w-16 rounded border p-1 ${messageOf(floorKey) ? INVALID_FIELD : "border-slate-300"}`}
                      {...aria(floorKey)}
                    />
                    {errorText(floorKey, "text-[11px]")}
                  </div>
                )}
                {value.criteria.length > 1 && (
                  <button
                    type="button"
                    aria-label={`Xóa tiêu chí ${number}`}
                    onClick={() =>
                      onChange(
                        { ...value, criteria: value.criteria.filter((_, position) => position !== index) },
                        ["criteria"],
                      )
                    }
                    className="text-rose-600 hover:underline cursor-pointer"
                  >
                    Xóa tiêu chí
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() =>
          onChange({ ...value, criteria: [...value.criteria, blankRow(ADDED_ROW_WEIGHT)] }, ["criteria"])
        }
        leftIcon={<Plus className="w-3.5 h-3.5" />}
      >
        Thêm tiêu chí
      </Button>
    </fieldset>
  );
}
