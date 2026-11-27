import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthProvider";
import { getApplicationCounts } from "./api";
import type { AiScoreStatus, ApplicationCounts, ApplicationStatus, ApplicationSummary } from "./types";

const INTERVIEWING: ApplicationStatus[] = ["INTERVIEW_INVITED", "INTERVIEW_CONFIRMED", "AWAITING_INTERVIEW_RESULT"];

/** Counts per status (one request), shared by the pipeline cards and the HR overview. */
export function useApplicationCounts() {
  const { authorized } = useAuth();
  return useQuery({
    queryKey: ["applications", "counts"],
    queryFn: () => authorized((token) => getApplicationCounts(token)),
  });
}

export function countOf(counts: ApplicationCounts, statuses: ApplicationStatus[]): number {
  return statuses.reduce((sum, status) => sum + (counts.byStatus[status] ?? 0), 0);
}

/** Invited, confirmed or awaiting the interview result. */
export const interviewingCount = (counts: ApplicationCounts) => countOf(counts, INTERVIEWING);

const AI_STATUS_LABELS: Record<Exclude<AiScoreStatus, "SCORED">, string> = {
  PENDING: "Đang chấm điểm",
  NEEDS_REVIEW: "AI không chấm được",
  FAILED: "Lỗi chấm điểm",
};

/** Pending review whose working-day deadline has passed. */
export function isOverdue(application: Pick<ApplicationSummary, "status" | "reviewDueAt">, now = Date.now()) {
  if (application.status !== "PENDING_HR_REVIEW" || !application.reviewDueAt) return false;
  const due = new Date(application.reviewDueAt).getTime();
  return !Number.isNaN(due) && due < now;
}

/** Total AI score, or a label when there is none (never shows a fake 0). */
export function ScoreCell({ application }: { application: Pick<ApplicationSummary, "aiTotalScore" | "aiStatus"> }) {
  if (application.aiTotalScore === null) {
    const label = application.aiStatus === "SCORED" ? "Chưa có điểm" : AI_STATUS_LABELS[application.aiStatus];
    return <span className="text-xs font-semibold text-slate-500">{label}</span>;
  }
  return (
    <span className="font-extrabold text-sm px-2.5 py-1 rounded-md border bg-slate-50 text-slate-800 border-slate-200">
      {application.aiTotalScore}/100
    </span>
  );
}

/** score × weight / 100 rounded half-up to one decimal ("34.7" for 99 × 35). */
export function contribution(score: number, weight: number): string {
  return (Math.round((score * weight) / 10 + 1e-9) / 10).toFixed(1);
}
