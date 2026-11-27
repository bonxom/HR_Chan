import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthProvider";
import { Button } from "@/shared/components/ui/Button";
import { rejectApplication } from "./api";
import type { RejectReason } from "./types";

export const REJECT_REASONS: { value: RejectReason; label: string }[] = [
  { value: "NOT_QUALIFIED", label: "Không đáp ứng yêu cầu" },
  { value: "SKILL_MISMATCH", label: "Kỹ năng chưa phù hợp" },
  { value: "INSUFFICIENT_EXPERIENCE", label: "Chưa đủ kinh nghiệm" },
  { value: "POSITION_FILLED", label: "Vị trí đã tuyển đủ" },
  { value: "OTHER", label: "Lý do khác" },
];

const REASON_TEXT_MAX = 500;

interface RejectPanelProps {
  applicationId: number;
  version: number;
  /** True while the detail is reloading; the version may be about to change. */
  locked: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  onFailure: (error: unknown) => void;
  onPendingChange: (pending: boolean) => void;
}

// Lý do chỉ lưu nội bộ; thư gửi ứng viên chỉ là thư cảm ơn kèm link đồng ý lưu hồ sơ.
export function RejectPanel({
  applicationId,
  version,
  locked,
  onCancel,
  onSuccess,
  onFailure,
  onPendingChange,
}: RejectPanelProps) {
  const { authorized } = useAuth();
  const [reason, setReason] = useState<RejectReason>("NOT_QUALIFIED");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      authorized((token) => rejectApplication(token, applicationId, { reasonCode: reason, reasonText: text, version })),
    retry: false,
    onMutate: () => onPendingChange(true),
    onSettled: () => onPendingChange(false),
    onSuccess,
    onError: onFailure,
  });

  const submit = () => {
    if (mutation.isPending || locked) return;
    if (reason === "OTHER" && !text.trim()) {
      setError("Vui lòng nhập lý do khác.");
      return;
    }
    if (text.trim().length > REASON_TEXT_MAX) {
      setError(`Lý do tối đa ${REASON_TEXT_MAX} ký tự.`);
      return;
    }
    setError(null);
    mutation.mutate();
  };

  return (
    <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-3">
      <span className="block text-xs font-bold text-rose-900">Lý do từ chối nội bộ (không gửi cho ứng viên)</span>
      <select
        aria-label="Lý do từ chối"
        value={reason}
        onChange={(event) => {
          setReason(event.target.value as RejectReason);
          setError(null);
        }}
        className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
      >
        {REJECT_REASONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <textarea
        aria-label="Ghi chú lý do"
        rows={2}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setError(null);
        }}
        placeholder={reason === "OTHER" ? "Bắt buộc: mô tả lý do (tối đa 500 ký tự)" : "Ghi chú thêm (tùy chọn, tối đa 500 ký tự)"}
        className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
      />
      <div className="flex items-center justify-between text-xs">
        <span className={text.trim().length > REASON_TEXT_MAX ? "text-rose-600" : "text-slate-400"}>
          {text.trim().length}/{REASON_TEXT_MAX}
        </span>
        {error && (
          <span role="alert" className="text-rose-700 font-semibold">
            {error}
          </span>
        )}
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={mutation.isPending}>
          Hủy
        </Button>
        <Button
          variant="danger"
          size="sm"
          onClick={submit}
          disabled={mutation.isPending || locked}
          isLoading={mutation.isPending}
        >
          Xác nhận từ chối
        </Button>
      </div>
    </div>
  );
}
