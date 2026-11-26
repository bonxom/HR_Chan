import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, Clock3, Mail, Video } from "lucide-react";
import { Button } from "@/shared/components/ui/Button";
import { ApiError } from "@/shared/services/client";
import { resolveResponse, submitResponse } from "./api";
import { getResponseToken } from "./tokenBootstrap";
import type { ResponseAction, ResponseOutcome, ResponseSubmission } from "./types";

function localTime(value: string): string {
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(value));
}

const receiptText: Record<ResponseOutcome, string> = {
  ACCEPTED: "Đường dẫn đã ghi nhận xác nhận.",
  DECLINED: "Đường dẫn đã ghi nhận từ chối.",
  RESCHEDULE_REQUESTED: "Đường dẫn đã ghi nhận yêu cầu đổi lịch.",
  EXPIRED: "Đường dẫn đã hết hạn phản hồi.",
};

export function ResponsePage() {
  const token = getResponseToken();
  const [action, setAction] = useState<ResponseAction | null>(null);
  const [note, setNote] = useState("");
  const [checked, setChecked] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const query = useQuery({
    queryKey: ["candidate-response"],
    queryFn: () => resolveResponse(token!),
    enabled: token !== null,
    retry: false,
    gcTime: 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const mutation = useMutation({
    mutationFn: (payload: ResponseSubmission) => submitResponse(payload),
    retry: false,
    onError: async (error) => {
      if (error instanceof ApiError) {
        if (error.status === 409) {
          setChecked(false);
          setAction(null);
          setNote("");
          setFeedback("Thông tin đã thay đổi. Vui lòng đọc lại và chọn phản hồi mới.");
          await query.refetch();
        } else if (error.code === "invalid_response_link") {
          setUncertain(true);
          setFeedback("Chưa xác định được kết quả của yêu cầu. Hãy kiểm tra kết quả đã ghi nhận.");
          await query.refetch();
        } else {
          setFeedback(error.status === 422
            ? "Phản hồi chưa hợp lệ. Vui lòng kiểm tra lựa chọn và nội dung đã nhập."
            : "Chưa thể xử lý phản hồi. Vui lòng thử lại sau.");
        }
      } else {
        setUncertain(true);
        setFeedback("Chưa xác định được kết quả do mất kết nối. Hãy kiểm tra trước khi gửi lại.");
      }
    },
  });
  const view = query.data && !query.data.completed ? query.data : null;
  const isConsent = view?.purpose === "TALENT_POOL_CONSENT";
  const acknowledge = view?.consent_mode === "ACKNOWLEDGE";
  const busy = mutation.isPending || query.isFetching;

  function send(nextAction: ResponseAction) {
    if (!token || !view || busy || uncertain) return;
    const payload: ResponseSubmission = { token, action: nextAction };
    if (isConsent) {
      if (nextAction === "ACCEPTED" && !acknowledge && !checked) return;
      payload.policy_ver = view.policy_ver;
      payload.consent_snapshot = view.consent_snapshot;
    } else if (nextAction !== "ACCEPTED") {
      const cleanNote = note.trim();
      if (!cleanNote || cleanNote.length > 500) {
        setFeedback(nextAction === "RESCHEDULE_REQUESTED"
          ? "Vui lòng nhập ghi chú từ 1 đến 500 ký tự."
          : "Vui lòng nhập lý do từ 1 đến 500 ký tự.");
        return;
      }
      payload.note = cleanNote;
    }
    setFeedback("");
    mutation.mutate(payload);
  }

  async function checkResult() {
    const result = await query.refetch();
    if (result.data && !result.data.completed && !result.isError) {
      setUncertain(false);
      setFeedback("Chưa có phản hồi được ghi nhận. Bạn có thể chọn và gửi lại.");
    }
  }

  let content;
  if (!token) {
    content = <Notice title="Mở lại đường dẫn trong email" text="Phiên phản hồi đã kết thúc. Vui lòng mở lại email để tiếp tục." />;
  } else if (query.isPending) {
    content = <p role="status" className="py-12 text-center text-slate-600">Đang tải thông tin phản hồi…</p>;
  } else if (mutation.isSuccess) {
    content = <Notice title="Đã ghi nhận phản hồi" text={mutation.data.message} success />;
  } else if (query.data?.completed) {
    content = <Notice title="Phản hồi đã được ghi nhận" text={receiptText[query.data.outcome]} detail={localTime(query.data.completed_at)} success />;
  } else if (query.isError) {
    content = (
      <div className="space-y-5">
        <Notice title="Chưa thể mở phản hồi" text={query.error instanceof ApiError && query.error.status === 422
          ? "Đường dẫn đã hết hạn, bị thay thế hoặc không còn sử dụng được. Vui lòng kiểm tra email mới nhất."
          : "Chưa tải được thông tin. Vui lòng kiểm tra kết nối và thử lại."} />
        <Button variant="outline" onClick={() => void checkResult()} disabled={busy}>
          {uncertain ? "Kiểm tra kết quả" : "Thử tải lại"}
        </Button>
      </div>
    );
  } else if (view) {
    content = (
      <div className="space-y-7">
        <header className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
            {isConsent ? "Lưu hồ sơ cho cơ hội tiếp theo" : "Phản hồi lịch phỏng vấn"}
          </h1>
          <p className="text-lg font-medium text-emerald-800">{view.job_title}</p>
        </header>
        <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm sm:p-5">
          {!isConsent && view.start_at && <p className="flex items-center gap-3"><CalendarDays className="h-4 w-4 shrink-0 text-emerald-700" /><span>{localTime(view.start_at)} · Giờ Việt Nam</span></p>}
          <p className="flex items-center gap-3"><Clock3 className="h-4 w-4 shrink-0 text-slate-500" /><span>Hạn phản hồi {localTime(view.expires_at)} · Giờ Việt Nam</span></p>
          {!isConsent && view.meet_link && <a href={view.meet_link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-3 font-medium text-emerald-800 underline underline-offset-4"><Video className="h-4 w-4" />Mở Google Meet</a>}
        </div>
        {isConsent ? (
          <div className="space-y-5">
            <p className="whitespace-pre-line leading-relaxed text-slate-700">{view.policy_text}</p>
            {acknowledge ? (
              <>
                {view.consent_expires_at && <p className="font-medium text-slate-800">Có hiệu lực đến {localTime(view.consent_expires_at)}.</p>}
                <p className="text-sm text-slate-500">Phiên bản chính sách {view.policy_ver}</p>
                <Button onClick={() => send("ACCEPTED")} disabled={busy || uncertain}>Đã hiểu</Button>
              </>
            ) : (
              <>
                <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-emerald-200 p-4 text-sm leading-6 text-slate-800">
                  <input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} disabled={busy || uncertain} className="mt-1 h-4 w-4 shrink-0 accent-emerald-700" />
                  <span>Tôi đã đọc và đồng ý với nội dung lưu hồ sơ ở trên.</span>
                </label>
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => send("ACCEPTED")} disabled={!checked || busy || uncertain}>Đồng ý lưu hồ sơ</Button>
                  <Button variant="outline" onClick={() => send("DECLINED")} disabled={busy || uncertain}>Không đồng ý</Button>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => send("ACCEPTED")} disabled={busy || uncertain}>Xác nhận tham dự</Button>
              {view.can_reschedule && view.allowed_actions.includes("RESCHEDULE_REQUESTED") && <Button variant="outline" onClick={() => { setAction("RESCHEDULE_REQUESTED"); setFeedback(""); }} disabled={busy || uncertain}>Yêu cầu đổi lịch</Button>}
              <Button variant="ghost" onClick={() => { setAction("DECLINED"); setFeedback(""); }} disabled={busy || uncertain}>Từ chối tham dự</Button>
            </div>
            {action && (
              <div className="space-y-3 border-t border-slate-200 pt-5">
                <label htmlFor="response-note" className="block text-sm font-semibold text-slate-800">{action === "DECLINED" ? "Lý do từ chối" : "Ghi chú đổi lịch"}</label>
                <textarea id="response-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} rows={4} disabled={busy || uncertain} className="w-full rounded-xl border border-slate-300 p-3 text-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100" />
                <p className="text-xs text-slate-500">{note.length}/500 ký tự</p>
                <Button onClick={() => send(action)} disabled={busy || uncertain}>{action === "DECLINED" ? "Gửi từ chối" : "Gửi yêu cầu đổi lịch"}</Button>
              </div>
            )}
          </div>
        )}
        {mutation.isPending && <p role="status" className="text-sm text-slate-600">Đang ghi nhận phản hồi…</p>}
        {feedback && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">{feedback}</p>}
        {uncertain && <Button variant="outline" onClick={() => void checkResult()} disabled={busy}>Kiểm tra kết quả</Button>}
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:py-14">
      <div className="mx-auto max-w-2xl">
        <a href="/" className="mb-8 inline-flex items-center gap-2 text-lg font-extrabold tracking-tight text-emerald-800"><Mail className="h-5 w-5" />HR_Chan</a>
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10" aria-live="polite">{content}</section>
      </div>
    </main>
  );
}

function Notice({ title, text, detail, success }: { title: string; text: string; detail?: string; success?: boolean }) {
  return <div className="space-y-4 py-5">{success && <CheckCircle2 className="h-10 w-10 text-emerald-700" />}<h1 className="text-2xl font-bold text-slate-950">{title}</h1><p className="leading-relaxed text-slate-700">{text}</p>{detail && <p className="text-sm text-slate-500">{detail} · Giờ Việt Nam</p>}</div>;
}
