import { useEffect, useId, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/shared/services/client";
import { Button } from "@/shared/components/ui/Button";
import { Modal } from "@/shared/components/ui/Modal";
import { describeJobError, getJob, listCriteriaVersions, saveCriteria } from "./api";
import {
  CriteriaEditor,
  criteriaDraftFrom,
  criteriaInputFrom,
  emptyCriteriaDraft,
  type CriteriaDraft,
  type CriteriaDraftRow,
} from "./CriteriaEditor";
import { FormErrorSummary } from "./FormErrorSummary";
import { formatDateTime } from "./format";
import type { Interviewer, JobSummary } from "./types";
import { useFocusFirstError } from "./useErrorFocus";
import {
  UNMAPPED_SERVER_MESSAGE,
  criteriaFieldId,
  errorSummaryItems,
  mapServerIssues,
  refreshErrors,
  validateCriteria,
  type FieldErrors,
} from "./validation";

interface CriteriaModalProps {
  job: JobSummary | null;
  interviewers: Interviewer[];
  onClose: () => void;
  onSaved: (message: string) => void;
  onConflict: (message: string) => void;
}

type Tab = "edit" | "history";

export function CriteriaModal({ job, interviewers, onClose, onSaved, onConflict }: CriteriaModalProps) {
  const { authorized } = useAuth();
  const jobId = job?.id ?? null;
  const [tab, setTab] = useState<Tab>("edit");
  const [draft, setDraft] = useState<CriteriaDraft>(emptyCriteriaDraft);
  // Lỗi chung được giữ riêng với map lỗi theo từng ô.
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  // Sau lần bấm lưu đầu, việc gõ chỉ kiểm tra lại các lỗi đã xuất hiện.
  const [validated, setValidated] = useState(false);
  const [focusRequest, setFocusRequest] = useState(0);
  // Snapshot hàng đã gửi giúp ghép chỉ số trong lỗi422 với key hàng tương ứng.
  const submittedRows = useRef<CriteriaDraftRow[]>([]);
  const idPrefix = useId();
  const summaryId = `${idPrefix}-summary`;
  const criteriaPrefix = `${idPrefix}-criteria`;

  const detailQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => authorized((token) => getJob(token, jobId as number)),
    enabled: jobId !== null,
  });
  const versionsQuery = useQuery({
    queryKey: ["criteria-versions", jobId],
    queryFn: () => authorized((token) => listCriteriaVersions(token, jobId as number)),
    enabled: jobId !== null && tab === "history",
  });

  // Giữ version lúc mở để backend phát hiện xung đột khi lưu phiên bản tiêu chí.
  const [baseVersion, setBaseVersion] = useState<number | null>(null);

  useEffect(() => {
    setTab("edit");
    setError(null);
    setFieldErrors({});
    setValidated(false);
    setBaseVersion(null);
  }, [jobId]);

  // Nạp một lần khi mở; dữ liệu nền mới về không ghi đè phần người dùng đang sửa.
  useEffect(() => {
    if (detailQuery.data && baseVersion === null) {
      setDraft(criteriaDraftFrom(detailQuery.data.currentCriteria, detailQuery.data.interviewers));
      setBaseVersion(detailQuery.data.version);
    }
  }, [detailQuery.data, baseVersion]);

  const saveMutation = useMutation({
    mutationFn: () =>
      authorized((token) => saveCriteria(token, jobId as number, criteriaInputFrom(draft), baseVersion as number)),
    onSuccess: () => onSaved("Đã lưu phiên bản tiêu chí mới. Phiên bản này áp dụng cho hồ sơ nộp sau thời điểm lưu."),
    onError: (failure) => {
      if (failure instanceof ApiError && failure.status === 409) {
        onConflict(describeJobError(failure));
        return;
      }
      if (failure instanceof ApiError && failure.validationIssues?.length) {
        // The standalone endpoint takes the criteria set at the body root: `criteria[0].name`.
        const mapped = mapServerIssues(failure.validationIssues, {
          jobFields: false,
          criteriaPath: [],
          rows: submittedRows.current,
        });
        setFieldErrors(mapped.errors);
        setError(mapped.unmapped > 0 ? UNMAPPED_SERVER_MESSAGE : null);
      } else {
        setError(describeJobError(failure));
      }
      setFocusRequest((count) => count + 1);
    },
  });

  // Endpoint lưu bộ tiêu chí luôn yêu cầu bộ hoàn chỉnh, kể cả tin vẫn là nháp.
  // Lỗi422 ở đây có đường body.criteria[i], khác đường lồng lúc tạo cả tin.
  const save = () => {
    const found = validateCriteria(draft);
    setValidated(true);
    setFieldErrors(found);
    setError(null);
    if (Object.keys(found).length > 0) {
      setFocusRequest((count) => count + 1);
      return;
    }
    submittedRows.current = draft.criteria;
    saveMutation.mutate();
  };

  // Khóa hàng ổn định giúp lỗi vẫn gắn đúng tiêu chí khi thêm/xóa/sắp lại chỉ số.
  const changeDraft = (next: CriteriaDraft, touched: string[]) => {
    setDraft(next);
    if (validated) {
      setFieldErrors((current) =>
        refreshErrors(current, validateCriteria(next), touched, next.criteria),
      );
    }
  };

  const summaryItems = errorSummaryItems(fieldErrors, draft.criteria, (key) => criteriaFieldId(criteriaPrefix, key));
  useFocusFirstError(focusRequest, summaryItems[0]?.targetId, summaryId);

  const closed = detailQuery.data?.status === "CLOSED";
  const tabClass = (value: Tab) =>
    `px-3 py-1.5 text-xs font-semibold rounded-lg ${
      tab === value ? "bg-emerald-50 text-emerald-700" : "text-slate-500 hover:text-slate-800"
    }`;

  return (
    <Modal isOpen={job !== null} onClose={onClose} title={`Bộ tiêu chí: ${job?.title ?? ""}`} maxWidth="2xl">
      <div className="space-y-4">
        <div className="flex gap-2 border-b border-slate-100 pb-2">
          <button type="button" className={tabClass("edit")} onClick={() => setTab("edit")}>
            Thiết lập
          </button>
          <button type="button" className={tabClass("history")} onClick={() => setTab("history")}>
            Lịch sử phiên bản
          </button>
        </div>

        {tab === "edit" &&
          (detailQuery.isPending || (detailQuery.data && baseVersion === null) ? (
            <p className="text-sm text-slate-500">Đang tải bộ tiêu chí...</p>
          ) : detailQuery.isError ? (
            <p role="alert" className="text-sm text-rose-600">
              {describeJobError(detailQuery.error)}
            </p>
          ) : (
            <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <span>
                  {closed
                    ? "Tin đã đóng nên không thể thay đổi bộ tiêu chí."
                    : "Mỗi lần lưu tạo một phiên bản mới, chỉ áp dụng cho hồ sơ nộp sau đó. Tổng trọng số phải bằng 100."}
                </span>
              </div>
              <FormErrorSummary id={summaryId} items={summaryItems} message={error} />
              <CriteriaEditor
                value={draft}
                onChange={changeDraft}
                interviewers={interviewers}
                disabled={closed}
                errors={fieldErrors}
                idPrefix={criteriaPrefix}
              />
              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <Button variant="outline" onClick={onClose}>
                  Đóng
                </Button>
                {!closed && (
                  <Button onClick={save} disabled={saveMutation.isPending}>
                    Lưu phiên bản mới
                  </Button>
                )}
              </div>
            </div>
          ))}

        {tab === "history" &&
          (versionsQuery.isPending ? (
            <p className="text-sm text-slate-500">Đang tải lịch sử...</p>
          ) : versionsQuery.isError ? (
            <p role="alert" className="text-sm text-rose-600">
              {describeJobError(versionsQuery.error)}
            </p>
          ) : versionsQuery.data.length === 0 ? (
            <p className="text-sm text-slate-500">Tin này chưa có bộ tiêu chí nào.</p>
          ) : (
            <ol className="space-y-3 max-h-[65vh] overflow-y-auto pr-1">
              {versionsQuery.data.map((set) => (
                <li key={set.id} className="p-3.5 border border-slate-200 rounded-xl space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-900">Phiên bản {set.versionNo}</span>
                    <span className="text-slate-500">{formatDateTime(set.createdAt)}</span>
                  </div>
                  <p className="text-xs text-slate-600">Ngưỡng tự động mời: {set.autoInviteThreshold}/100</p>
                  <ul className="text-xs text-slate-700 list-disc pl-5">
                    {set.criteria.map((item) => (
                      <li key={item.id ?? item.name}>
                        {item.name} — {item.weight}
                        {item.isMandatory ? " (bắt buộc)" : ""}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          ))}
      </div>
    </Modal>
  );
}
