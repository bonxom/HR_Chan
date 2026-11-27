import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useAuth } from "@/features/auth/AuthProvider";
import { getJob } from "@/features/jobs/api";
import { ApiError } from "@/shared/services/client";
import { Button } from "@/shared/components/ui/Button";
import { describeApplicationError, getInterviewSlots, inviteApplication } from "./api";
import { addDays, companyToday, formatCompanyDate, formatCompanyTime } from "./format";
import type { SlotQuery } from "./types";

const DEFAULT_RANGE_DAYS = 7;

interface InvitePanelProps {
  applicationId: number;
  jobId: number;
  version: number;
  /** True while the detail is reloading; the version may be about to change. */
  locked: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  onFailure: (error: unknown) => void;
  onPendingChange: (pending: boolean) => void;
}

export function slotLabel(startAt: string, endAt: string): string {
  return `${formatCompanyTime(startAt)} – ${formatCompanyTime(endAt)}, ${formatCompanyDate(startAt)}`;
}

// HR chỉ chọn trong các khung giờ backend gợi ý; start_at gửi lại nguyên chuỗi có múi giờ.
export function InvitePanel({
  applicationId,
  jobId,
  version,
  locked,
  onCancel,
  onSuccess,
  onFailure,
  onPendingChange,
}: InvitePanelProps) {
  const { authorized } = useAuth();
  const queryClient = useQueryClient();
  const today = companyToday();
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(addDays(today, DEFAULT_RANGE_DAYS));
  const [chosenInterviewer, setChosenInterviewer] = useState("");
  const [slotQuery, setSlotQuery] = useState<SlotQuery | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => authorized((token) => getJob(token, jobId)),
  });
  const interviewers = jobQuery.data?.interviewers ?? [];
  const single = interviewers.length === 1;
  // Một người phỏng vấn: backend tự suy ra, không gửi interviewer_id.
  const interviewerId = single ? undefined : chosenInterviewer || undefined;
  // Danh sách đang tải lại hoặc lỗi thì không dùng dữ liệu cũ để tìm giờ hay mời.
  const jobUsable = jobQuery.isSuccess && !jobQuery.isFetching;
  const interviewerReady = jobUsable && (single || (interviewers.length > 1 && Boolean(chosenInterviewer)));
  const rangeValid = Boolean(dateFrom && dateTo && dateFrom <= dateTo);

  // Người phỏng vấn của tin thay đổi (ví dụ sau lỗi 422): khung giờ đã tìm cho người cũ không còn
  // hợp lệ, nên bỏ người đã chọn và khung giờ.
  const interviewerKey = interviewers.map((item) => item.id).join(",");
  const previousKey = useRef<string | null>(null);
  useEffect(() => {
    if (!jobQuery.isSuccess) return;
    if (previousKey.current !== null && previousKey.current !== interviewerKey) {
      setChosenInterviewer("");
      setSlotQuery(null);
      setSelected(null);
    }
    previousKey.current = interviewerKey;
  }, [interviewerKey, jobQuery.isSuccess]);

  const slotsQuery = useQuery({
    queryKey: ["application", applicationId, "slots", slotQuery],
    queryFn: () => authorized((token) => getInterviewSlots(token, applicationId, slotQuery as SlotQuery)),
    enabled: slotQuery !== null,
    staleTime: 0,
  });

  // Đổi đầu vào thì khung giờ cũ không còn đúng: bỏ lựa chọn và danh sách đã tìm.
  const resetSlots = () => {
    setSlotQuery(null);
    setSelected(null);
  };

  const mutation = useMutation({
    mutationFn: (startAt: string) =>
      authorized((token) => inviteApplication(token, applicationId, { startAt, version, interviewerId })),
    retry: false,
    onMutate: () => onPendingChange(true),
    onSettled: () => onPendingChange(false),
    onSuccess,
    onError: (error) => {
      if (error instanceof ApiError && error.code === "slot_conflict") {
        setSelected(null);
        void slotsQuery.refetch();
      }
      if (error instanceof ApiError && (error.code === "invalid_interviewer" || error.code === "interviewer_required")) {
        void queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      }
      onFailure(error);
    },
  });

  // Trong lúc tìm lại, danh sách đang hiện là kết quả cũ: không cho chọn hay xác nhận.
  const slotsRefreshing = slotsQuery.isFetching;
  // Chỉ xác nhận khung giờ có trong kết quả mới nhất, tải thành công.
  const selectedIsCurrent =
    selected !== null &&
    slotsQuery.isSuccess &&
    !slotsRefreshing &&
    slotsQuery.data.some((slot) => slot.startAt === selected);
  const canConfirm = selectedIsCurrent && interviewerReady && !locked;

  const findSlots = () => {
    setSelected(null);
    const next: SlotQuery = { dateFrom, dateTo, interviewerId };
    const same =
      slotQuery !== null &&
      slotQuery.dateFrom === next.dateFrom &&
      slotQuery.dateTo === next.dateTo &&
      slotQuery.interviewerId === next.interviewerId;
    // Cùng đầu vào thì query key không đổi; gọi lại trực tiếp để HR thử lại được sau lỗi.
    if (same) void slotsQuery.refetch();
    else setSlotQuery(next);
  };

  return (
    <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded-xl space-y-3 text-xs">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <label className="space-y-1">
          <span className="block font-semibold text-slate-700">Từ ngày</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => {
              setDateFrom(event.target.value);
              resetSlots();
            }}
            className="w-full bg-white border border-slate-300 rounded-lg p-2"
          />
        </label>
        <label className="space-y-1">
          <span className="block font-semibold text-slate-700">Đến ngày</span>
          <input
            type="date"
            value={dateTo}
            onChange={(event) => {
              setDateTo(event.target.value);
              resetSlots();
            }}
            className="w-full bg-white border border-slate-300 rounded-lg p-2"
          />
        </label>
        <div className="space-y-1">
          <span className="block font-semibold text-slate-700">Người phỏng vấn</span>
          {jobQuery.isPending ? (
            <p className="p-2 text-slate-500">Đang tải...</p>
          ) : jobQuery.isError ? (
            <p className="p-2 text-rose-600">{describeApplicationError(jobQuery.error)}</p>
          ) : interviewers.length === 0 ? (
            <p className="p-2 text-rose-600">Tin tuyển dụng chưa có người phỏng vấn nên chưa thể mời.</p>
          ) : single ? (
            <p className="p-2 font-semibold text-slate-800">{interviewers[0].fullName}</p>
          ) : (
            <select
              aria-label="Người phỏng vấn"
              value={chosenInterviewer}
              onChange={(event) => {
                setChosenInterviewer(event.target.value);
                resetSlots();
              }}
              className="w-full bg-white border border-slate-300 rounded-lg p-2"
            >
              <option value="">Chọn người phỏng vấn</option>
              {interviewers.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.fullName}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
      {!rangeValid && <p className="text-rose-600">Khoảng ngày không hợp lệ.</p>}

      <Button
        variant="outline"
        size="sm"
        onClick={findSlots}
        disabled={!rangeValid || !interviewerReady || mutation.isPending}
        leftIcon={<Search className="w-3.5 h-3.5" />}
      >
        Tìm khung giờ
      </Button>

      {slotQuery && (
        <div className="space-y-2">
          {slotsQuery.isPending ? (
            <p className="text-slate-500">Đang tìm khung giờ trống...</p>
          ) : slotsQuery.isError ? (
            <p role="alert" className="text-rose-600">
              {describeApplicationError(slotsQuery.error)}
            </p>
          ) : slotsQuery.data.length === 0 ? (
            <p className="text-slate-600">Không có khung giờ trống</p>
          ) : (
            <fieldset className="space-y-1.5">
              <legend className="font-semibold text-slate-700 mb-1">Khung giờ gợi ý (giờ Việt Nam)</legend>
              {slotsRefreshing && <p className="text-slate-500">Đang tải lại khung giờ...</p>}
              {slotsQuery.data.map((slot) => (
                <label key={slot.startAt} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name={`slot-${applicationId}`}
                    value={slot.startAt}
                    checked={selected === slot.startAt}
                    disabled={slotsRefreshing || mutation.isPending}
                    onChange={() => setSelected(slot.startAt)}
                  />
                  <span>{slotLabel(slot.startAt, slot.endAt)}</span>
                </label>
              ))}
            </fieldset>
          )}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={mutation.isPending}>
          Hủy
        </Button>
        <Button
          size="sm"
          onClick={() => canConfirm && selected && mutation.mutate(selected)}
          disabled={!canConfirm || mutation.isPending}
          isLoading={mutation.isPending}
        >
          Xác nhận mời
        </Button>
      </div>
    </div>
  );
}
