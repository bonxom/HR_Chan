import { useEffect, useId, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/shared/services/client";
import { Button } from "@/shared/components/ui/Button";
import { Input, Textarea } from "@/shared/components/ui/Input";
import { Modal } from "@/shared/components/ui/Modal";
import { createJob, describeJobError, getJob, updateJob } from "./api";
import {
  CriteriaEditor,
  criteriaInputFrom,
  emptyCriteriaDraft,
  isCriteriaDraftPristine,
  type CriteriaDraft,
} from "./CriteriaEditor";
import { FormErrorSummary } from "./FormErrorSummary";
import type { Department, Interviewer, JobDetail, JobFieldsInput } from "./types";
import { useFocusFirstError } from "./useErrorFocus";
import {
  LIMITS,
  UNMAPPED_SERVER_MESSAGE,
  criteriaFieldId,
  errorMessage,
  errorSummaryItems,
  mapServerIssues,
  refreshErrors,
  validateCriteria,
  validateJobFields,
  type FieldErrors,
  type JobFieldKey,
  type JobFormValues,
  type JobRule,
  type ServerIssueTarget,
} from "./validation";

type FormState = JobFormValues;

const EMPTY_FORM: FormState = {
  title: "",
  departmentId: "",
  description: "",
  requirements: "",
  benefits: "",
  headcount: "1",
  workMode: "",
  location: "",
  deadline: "",
};

const FIELD_IDS: Record<JobFieldKey, string> = {
  title: "job-title",
  departmentId: "job-department",
  workMode: "job-work-mode",
  headcount: "job-headcount",
  deadline: "job-deadline",
  location: "job-location",
  description: "job-description",
  requirements: "job-requirements",
  benefits: "job-benefits",
};

function formFrom(job: JobDetail): FormState {
  return {
    title: job.title,
    departmentId: String(job.departmentId),
    description: job.description ?? "",
    requirements: job.requirements ?? "",
    benefits: job.benefits ?? "",
    headcount: job.headcount === null ? "" : String(job.headcount),
    workMode: job.workMode ?? "",
    location: job.location ?? "",
    deadline: job.deadline ?? "",
  };
}

// Input số/ngày vẫn giữ chuỗi trong state để người dùng xóa/gõ dở được; chỉ
// chuyển sang dạng payload lúc gửi, sau khi validate theo thao tác lưu/đăng.
function fieldsFrom(form: FormState): JobFieldsInput {
  return {
    title: form.title,
    departmentId: Number(form.departmentId),
    description: form.description,
    requirements: form.requirements,
    benefits: form.benefits,
    headcount: form.headcount.trim() === "" ? null : Number(form.headcount),
    workMode: form.workMode,
    location: form.location,
    deadline: form.deadline,
  };
}

/** Rules of the last save attempt; edits re-check shown errors against the same rules. */
interface ValidationMode {
  job: JobRule;
  /** Creating includes the criteria editor; editing a posting does not. */
  withCriteria: boolean;
}

function computeErrors(form: FormState, criteria: CriteriaDraft, mode: ValidationMode): FieldErrors {
  const errors = validateJobFields(form, mode.job);
  if (!mode.withCriteria) return errors;
  // The backend checks any criteria set it receives, draft or not; only a draft whose editor
  // is still untouched may omit it.
  if (mode.job === "draft" && isCriteriaDraftPristine(criteria)) return errors;
  return { ...errors, ...validateCriteria(criteria) };
}

interface JobFormModalProps {
  /** null creates a new posting; a job id edits that posting. */
  jobId: number | null;
  isOpen: boolean;
  departments: Department[];
  interviewers: Interviewer[];
  onClose: () => void;
  onSaved: (message: string) => void;
  /** Stale version (409): the page reports it and reloads. */
  onConflict: (message: string) => void;
}

export function JobFormModal({
  jobId,
  isOpen,
  departments,
  interviewers,
  onClose,
  onSaved,
  onConflict,
}: JobFormModalProps) {
  const { authorized } = useAuth();
  const editing = jobId !== null;
  const idPrefix = useId();
  const summaryId = `${idPrefix}-summary`;
  const criteriaPrefix = `${idPrefix}-criteria`;
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [criteria, setCriteria] = useState<CriteriaDraft>(emptyCriteriaDraft);
  // Thông báo chung cho lỗi nghiệp vụ/mạng hoặc lỗi không xác định được ô.
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [mode, setMode] = useState<ValidationMode | null>(null);
  const [focusRequest, setFocusRequest] = useState(0);
  // Giữ thứ tự hàng của lần gửi để loc trong lỗi422 trỏ đúng tiêu chí đã gửi.
  const submitted = useRef<ServerIssueTarget>({ jobFields: true, criteriaPath: null, rows: [] });
  // Giữ version lúc mở form, không thay theo lần refetch. Lưu gửi version này
  // để backend trả409 nếu người khác đã sửa, thay vì âm thầm ghi đè dữ liệu mới.
  const [baseVersion, setBaseVersion] = useState<number | null>(null);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => authorized((token) => getJob(token, jobId as number)),
    enabled: isOpen && editing,
  });

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    setFieldErrors({});
    setMode(null);
    setBaseVersion(null);
    if (!editing) {
      setForm(EMPTY_FORM);
      setCriteria(emptyCriteriaDraft());
    }
  }, [isOpen, editing, jobId]);

  // Mỗi lần mở chỉ nạp form một lần; refetch nền không được xóa nội dung đang sửa.
  useEffect(() => {
    if (isOpen && editing && jobQuery.data && baseVersion === null) {
      setForm(formFrom(jobQuery.data));
      setBaseVersion(jobQuery.data.version);
    }
  }, [isOpen, editing, jobQuery.data, baseVersion]);

  // Danh sách có thể cũ; lấy trạng thái chi tiết mới nhất để khóa tin vừa đóng.
  const closed = editing && jobQuery.data?.status === "CLOSED";

  // Lỗi422 có loc được ghép vào đúng ô; lỗi không có vị trí giữ ở tổng hợp.
  // Không reset form khi thất bại để người dùng sửa tiếp dữ liệu đang nhập.
  const handleFailure = (failure: unknown) => {
    if (failure instanceof ApiError && failure.status === 409) {
      onConflict(describeJobError(failure));
      return;
    }
    if (failure instanceof ApiError && failure.validationIssues?.length) {
      const mapped = mapServerIssues(failure.validationIssues, submitted.current);
      setFieldErrors(mapped.errors);
      setError(mapped.unmapped > 0 ? UNMAPPED_SERVER_MESSAGE : null);
    } else {
      setError(describeJobError(failure));
    }
    setFocusRequest((count) => count + 1);
  };

  const createMutation = useMutation({
    mutationFn: ({ publish, withCriteria }: { publish: boolean; withCriteria: boolean }) =>
      authorized((token) =>
        createJob(token, {
          ...fieldsFrom(form),
          publish,
          criteria: withCriteria ? criteriaInputFrom(criteria) : null,
        }),
      ),
    onSuccess: (job) => onSaved(job.status === "OPEN" ? "Đã đăng tin tuyển dụng." : "Đã lưu tin nháp."),
    onError: handleFailure,
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      authorized((token) =>
        updateJob(token, jobId as number, fieldsFrom(form), baseVersion as number),
      ),
    onSuccess: () => onSaved("Đã cập nhật tin tuyển dụng."),
    onError: handleFailure,
  });

  const busy = createMutation.isPending || updateMutation.isPending;

  const submit = (kind: "draft" | "publish" | "update") => {
    if (closed) return;
    // Editing an open posting keeps it publishable; a draft keeps its optional fields optional.
    const job: JobRule =
      kind === "update" ? (jobQuery.data?.status === "OPEN" ? "publish" : "draft") : kind;
    const nextMode: ValidationMode = { job, withCriteria: !editing };
    const found = computeErrors(form, criteria, nextMode);
    setMode(nextMode);
    setFieldErrors(found);
    setError(null);
    if (Object.keys(found).length > 0) {
      setFocusRequest((count) => count + 1);
      return;
    }
    if (kind === "update") {
      submitted.current = { jobFields: true, criteriaPath: null, rows: [] };
      updateMutation.mutate();
      return;
    }
    // Nháp có bộ tiêu chí còn đúng trạng thái trống ban đầu được gửi null.
    // Nếu đã nhập một phần thì giữ và kiểm tra đủ, không âm thầm bỏ nội dung đó.
    const withCriteria = kind === "publish" || !isCriteriaDraftPristine(criteria);
    submitted.current = { jobFields: true, criteriaPath: withCriteria ? ["criteria"] : null, rows: criteria.criteria };
    createMutation.mutate({ publish: kind === "publish", withCriteria });
  };

  // Sửa một ô chỉ kiểm tra lại lỗi liên quan, giữ lỗi các ô khác cho tới khi sửa.
  const set = (key: JobFieldKey) => (event: { target: { value: string } }) => {
    const next = { ...form, [key]: event.target.value };
    setForm(next);
    if (mode) {
      setFieldErrors((current) => refreshErrors(current, computeErrors(next, criteria, mode), [key], criteria.criteria));
    }
  };

  const changeCriteria = (next: CriteriaDraft, touched: string[]) => {
    setCriteria(next);
    if (mode) {
      setFieldErrors((current) => refreshErrors(current, computeErrors(form, next, mode), touched, next.criteria));
    }
  };

  const fieldError = (key: JobFieldKey) =>
    fieldErrors[key] ? errorMessage(key, fieldErrors[key]) : undefined;
  const idOf = (key: string) =>
    Object.hasOwn(FIELD_IDS, key) ? FIELD_IDS[key as JobFieldKey] : criteriaFieldId(criteriaPrefix, key);
  const summaryItems = errorSummaryItems(fieldErrors, editing ? [] : criteria.criteria, idOf);
  useFocusFirstError(focusRequest, summaryItems[0]?.targetId, summaryId);

  // A posting keeps its department even if that department was deactivated later.
  const departmentOptions = departments.filter(
    (item) => item.isActive || String(item.id) === form.departmentId,
  );
  const departmentError = fieldError("departmentId");

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={editing ? "Sửa tin tuyển dụng" : "Tạo tin tuyển dụng"}
      maxWidth="2xl"
    >
      {editing && (jobQuery.isPending || (jobQuery.data && baseVersion === null)) ? (
        <p className="text-sm text-slate-500">Đang tải tin tuyển dụng...</p>
      ) : editing && jobQuery.isError ? (
        <p role="alert" className="text-sm text-rose-600">
          {describeJobError(jobQuery.error)}
        </p>
      ) : (
        <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
          {closed && (
            <p className="p-3 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg">
              Tin đã đóng nên không thể sửa.
            </p>
          )}
          <FormErrorSummary id={summaryId} items={summaryItems} message={error} />
          <fieldset disabled={closed} className="space-y-4">
          <Input
            id={FIELD_IDS.title}
            label="Tên vị trí *"
            maxLength={LIMITS.title}
            value={form.title}
            onChange={set("title")}
            error={fieldError("title")}
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label
                htmlFor={FIELD_IDS.departmentId}
                className="block text-xs font-semibold text-slate-600 mb-1.5"
              >
                Phòng ban *
              </label>
              <select
                id={FIELD_IDS.departmentId}
                value={form.departmentId}
                onChange={set("departmentId")}
                aria-invalid={departmentError ? true : undefined}
                aria-describedby={departmentError ? `${FIELD_IDS.departmentId}-error` : undefined}
                className={`w-full bg-white border rounded-lg p-2 text-sm ${
                  departmentError
                    ? "border-rose-400 focus:outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-400"
                    : "border-slate-300"
                }`}
              >
                <option value="">Chọn phòng ban</option>
                {departmentOptions.map((item) => (
                  <option key={item.id} value={String(item.id)}>
                    {item.name}
                  </option>
                ))}
              </select>
              {departmentError && (
                <p id={`${FIELD_IDS.departmentId}-error`} className="mt-1 text-xs text-rose-600">
                  {departmentError}
                </p>
              )}
            </div>
            <Input
              id={FIELD_IDS.workMode}
              label="Hình thức làm việc"
              maxLength={LIMITS.workMode}
              placeholder="Toàn thời gian – Hybrid"
              value={form.workMode}
              onChange={set("workMode")}
              error={fieldError("workMode")}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input
              id={FIELD_IDS.headcount}
              label="Số lượng cần tuyển"
              type="number"
              min={1}
              value={form.headcount}
              onChange={set("headcount")}
              error={fieldError("headcount")}
            />
            <Input
              id={FIELD_IDS.deadline}
              label="Hạn nộp hồ sơ"
              type="date"
              value={form.deadline}
              onChange={set("deadline")}
              error={fieldError("deadline")}
            />
            <Input
              id={FIELD_IDS.location}
              label="Địa điểm làm việc"
              maxLength={LIMITS.location}
              value={form.location}
              onChange={set("location")}
              error={fieldError("location")}
            />
          </div>

          <Textarea
            id={FIELD_IDS.description}
            label="Mô tả công việc"
            rows={3}
            maxLength={LIMITS.description}
            value={form.description}
            onChange={set("description")}
            error={fieldError("description")}
          />
          <Textarea
            id={FIELD_IDS.requirements}
            label="Yêu cầu ứng viên"
            rows={3}
            maxLength={LIMITS.requirements}
            value={form.requirements}
            onChange={set("requirements")}
            error={fieldError("requirements")}
          />
          <Textarea
            id={FIELD_IDS.benefits}
            label="Quyền lợi"
            rows={2}
            maxLength={LIMITS.benefits}
            helperText="Có thể ghi mức lương tại đây."
            value={form.benefits}
            onChange={set("benefits")}
            error={fieldError("benefits")}
          />

          {!editing && (
            <div className="pt-2 border-t border-slate-100 space-y-2">
              <p className="text-sm font-bold text-slate-800">Bộ tiêu chí chấm điểm</p>
              <p className="text-xs text-slate-500">
                Khi đăng tin, tổng trọng số phải bằng 100 và cần ít nhất một người phỏng vấn. Tin nháp có thể
                hoàn thiện bộ tiêu chí sau.
              </p>
              <CriteriaEditor
                value={criteria}
                onChange={changeCriteria}
                interviewers={interviewers}
                errors={fieldErrors}
                idPrefix={criteriaPrefix}
              />
            </div>
          )}
          </fieldset>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button variant="outline" onClick={onClose} disabled={busy}>
              Hủy
            </Button>
            {editing ? (
              !closed && (
                <Button onClick={() => submit("update")} disabled={busy}>
                  Lưu thay đổi
                </Button>
              )
            ) : (
              <>
                <Button variant="secondary" onClick={() => submit("draft")} disabled={busy}>
                  Lưu nháp
                </Button>
                <Button onClick={() => submit("publish")} disabled={busy}>
                  Đăng tin
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
