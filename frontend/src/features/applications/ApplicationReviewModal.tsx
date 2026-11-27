import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Download, Mail, Phone, Sparkles, User, XCircle } from "lucide-react";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/shared/services/client";
import { StatusBadge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { Modal } from "@/shared/components/ui/Modal";
import { showToast } from "@/shared/components/ui/Toast";
import { describeApplicationError, downloadApplicationCv, getApplication } from "./api";
import { ScoreCell, contribution } from "./display";
import { formatCompanyDate, formatCompanyDateTime } from "./format";
import { InvitePanel } from "./InvitePanel";
import { RejectPanel } from "./RejectPanel";
import type { ApplicationDetail, CriterionScore } from "./types";

interface ApplicationReviewModalProps {
  applicationId: number;
  onClose: () => void;
}

// 409 do trạng thái/version: dữ liệu đã cũ, cần tải lại chi tiết, danh sách và thẻ đếm.
const STALE_CODES = new Set(["version_conflict", "invalid_application_state", "invalid_state"]);

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Thu hồi sau khi trình duyệt đã nhận lệnh tải.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function CriterionRow({ score }: { score: CriterionScore }) {
  return (
    <div data-testid={`criterion-${score.criterionId}`} className="p-4 bg-white border border-slate-200 rounded-xl space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-bold text-xs text-slate-900">{score.name}</span>
          <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">Trọng số {score.weight}%</span>
          {score.isMandatory && (
            <>
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">
                Điểm sàn {score.minScore ?? "—"}
              </span>
              {score.meetsMandatory === true && (
                <span className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded font-semibold border border-teal-200">
                  Đạt tiêu chí bắt buộc
                </span>
              )}
              {score.meetsMandatory === false && (
                <span className="text-xs bg-rose-50 text-rose-700 px-2 py-0.5 rounded font-semibold border border-rose-200">
                  Chưa đạt tiêu chí bắt buộc
                </span>
              )}
            </>
          )}
        </div>
        <div className="text-right">
          <span className="text-sm font-extrabold text-emerald-700">{score.score}/100</span>
          <span className="text-xs text-slate-400 block">Đóng góp {contribution(score.score, score.weight)} điểm</span>
        </div>
      </div>
      {score.aiComment && <p className="text-xs text-slate-600 leading-relaxed">{score.aiComment}</p>}
    </div>
  );
}

function DetailBody({ detail }: { detail: ApplicationDetail }) {
  return (
    <>
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <span className="text-slate-400 block mb-0.5">Ứng viên</span>
            <span className="font-bold text-slate-800 text-sm flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-slate-500" /> {detail.candidate.fullName}
            </span>
          </div>
          <div>
            <span className="text-slate-400 block mb-0.5">Liên hệ</span>
            <span className="font-medium text-slate-700 flex flex-wrap items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-slate-400" /> <span>{detail.candidate.email}</span>
              {detail.candidate.phone && (
                <>
                  <Phone className="w-3.5 h-3.5 text-slate-400" /> <span>{detail.candidate.phone}</span>
                </>
              )}
            </span>
          </div>
          <div>
            <span className="text-slate-400 block mb-0.5">Ngày nộp</span>
            <span className="font-medium text-slate-700">{formatCompanyDate(detail.submittedAt)}</span>
          </div>
          <div>
            <span className="text-slate-400 block mb-0.5">Hạn xét duyệt</span>
            <span className="font-medium text-slate-700">{formatCompanyDateTime(detail.reviewDueAt)}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-xs text-slate-400 block">Tổng điểm AI</span>
            <ScoreCell application={detail} />
          </div>
          <StatusBadge status={detail.status} />
        </div>
      </div>

      {detail.hrNote && (
        <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Ghi chú hệ thống / HR:</span>
            <p className="mt-0.5">{detail.hrNote}</p>
          </div>
        </div>
      )}
      {detail.aiFailureReason && (
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-700">
          <span className="font-bold">AI không chấm được hồ sơ này.</span> Mã lý do: {detail.aiFailureReason}. HR xét
          duyệt thủ công.
        </div>
      )}
      {detail.emailIssue && (
        <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800">
          Có lỗi khi gửi email cho ứng viên ({detail.emailIssue}).
        </div>
      )}
      {detail.interview && (
        <div className="p-3.5 bg-sky-50 border border-sky-200 rounded-xl text-xs text-sky-800">
          Buổi phỏng vấn #{detail.interview.id}: {detail.interview.status}
          {detail.interview.needsManualCalendarFix && " — cần sửa lịch thủ công"}
        </div>
      )}

      <div>
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-emerald-600" />
          Điểm AI theo từng tiêu chí
        </h3>
        <div className="space-y-3">
          {detail.scores.length > 0 ? (
            detail.scores.map((score) => <CriterionRow key={score.criterionId} score={score} />)
          ) : (
            <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
              Chưa có điểm tiêu chí cho hồ sơ này.
            </div>
          )}
        </div>
        <p className="mt-2 text-xs text-slate-500">Tổng điểm do hệ thống tính từ điểm và trọng số, không do AI tự cộng.</p>
      </div>

      <div data-testid="status-history">
        <h3 className="text-sm font-bold text-slate-900 mb-2">Lịch sử trạng thái</h3>
        <ol className="space-y-1.5 text-xs">
          {detail.statusHistory.map((event, index) => (
            <li key={`${event.at}-${index}`} className="flex items-center gap-2">
              <span className="text-slate-500 w-32 shrink-0">{formatCompanyDateTime(event.at)}</span>
              {event.after ? <StatusBadge status={event.after} /> : <span>—</span>}
            </li>
          ))}
        </ol>
      </div>
    </>
  );
}

// Chi tiết hồ sơ luôn đọc lại từ API khi mở để mỗi lượt xem được ghi nhật ký truy cập.
export function ApplicationReviewModal({ applicationId, onClose }: ApplicationReviewModalProps) {
  const { authorized } = useAuth();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"none" | "reject" | "invite">("none");
  const [notice, setNotice] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const detailQuery = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => authorized((token) => getApplication(token, applicationId)),
    staleTime: 0,
    refetchOnMount: "always",
  });
  const detail = detailQuery.data;
  const canDecide = detail?.status === "PENDING_HR_REVIEW";
  // Bản cache có thể cũ (version khác): chỉ cho quyết định khi bản vừa tải đã về.
  const decisionsLocked = deciding || detailQuery.isFetching;
  // Không đóng khi đang gửi, để không mở lại rồi gửi quyết định lần hai.
  const requestClose = () => {
    if (!deciding) onClose();
  };

  const refreshAll = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["applications"] }),
      queryClient.invalidateQueries({ queryKey: ["application", applicationId], exact: true }),
    ]);

  const handleSuccess = (message: string) => {
    showToast({ type: "success", message });
    void queryClient.invalidateQueries({ queryKey: ["applications"] });
    void queryClient.removeQueries({ queryKey: ["application", applicationId] });
    onClose();
  };

  const handleFailure = (error: unknown) => {
    setNotice(describeApplicationError(error));
    if (error instanceof ApiError && STALE_CODES.has(error.code)) {
      setMode("none");
      void refreshAll();
    }
  };

  const downloadCv = async () => {
    setDownloading(true);
    setNotice(null);
    try {
      const file = await authorized((token) => downloadApplicationCv(token, applicationId));
      saveBlob(file.blob, file.filename);
    } catch (error) {
      setNotice(describeApplicationError(error));
    } finally {
      setDownloading(false);
    }
  };

  const panelProps = {
    applicationId,
    version: detail?.version ?? 0,
    locked: detailQuery.isFetching,
    onCancel: () => setMode("none"),
    onFailure: handleFailure,
    onPendingChange: setDeciding,
  };

  return (
    <Modal
      isOpen
      onClose={requestClose}
      title={detail ? `Hồ sơ: ${detail.candidate.fullName} (#${detail.id})` : "Hồ sơ ứng tuyển"}
      subtitle={detail ? `Ứng tuyển vị trí: ${detail.jobTitle}` : undefined}
      maxWidth="4xl"
    >
      <div className="space-y-6 max-h-[75vh] overflow-y-auto pr-1">
        {notice && (
          <div role="alert" className="p-3 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
            {notice}
          </div>
        )}

        {detailQuery.isPending ? (
          <p className="text-sm text-slate-500">Đang tải hồ sơ...</p>
        ) : detailQuery.isError || !detail ? (
          <div className="space-y-3">
            <p className="text-sm text-rose-600">{describeApplicationError(detailQuery.error)}</p>
            <Button variant="outline" size="sm" onClick={() => void detailQuery.refetch()}>
              Thử lại
            </Button>
          </div>
        ) : (
          <>
            <div className="flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void downloadCv()}
                isLoading={downloading}
                leftIcon={<Download className="w-3.5 h-3.5" />}
              >
                Tải CV
              </Button>
            </div>

            <DetailBody detail={detail} />

            {canDecide && (
              <div className="p-5 bg-slate-50 border border-slate-200 rounded-2xl space-y-4">
                <h4 className="text-xs font-bold text-slate-700">Quyết định xét duyệt của HR</h4>
                {mode === "none" && (
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button
                      variant="danger"
                      disabled={decisionsLocked}
                      onClick={() => {
                        setNotice(null);
                        setMode("reject");
                      }}
                      leftIcon={<XCircle className="w-4 h-4" />}
                    >
                      Từ chối hồ sơ
                    </Button>
                    <Button
                      disabled={decisionsLocked}
                      onClick={() => {
                        setNotice(null);
                        setMode("invite");
                      }}
                      leftIcon={<CheckCircle2 className="w-4 h-4" />}
                    >
                      Mời phỏng vấn
                    </Button>
                  </div>
                )}
                {mode === "reject" && (
                  <RejectPanel
                    {...panelProps}
                    onSuccess={() => handleSuccess("Đã từ chối hồ sơ. Thư cảm ơn đã được xếp hàng gửi tới ứng viên.")}
                  />
                )}
                {mode === "invite" && (
                  <InvitePanel
                    {...panelProps}
                    jobId={detail.jobId}
                    onSuccess={() => handleSuccess("Đã mời phỏng vấn. Thư mời đã được xếp hàng gửi tới ứng viên.")}
                  />
                )}
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
