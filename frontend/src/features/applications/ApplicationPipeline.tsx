import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock, Eye, MailWarning, RefreshCw, Search, Users } from "lucide-react";
import { useAuth } from "@/features/auth/AuthProvider";
import { STATUS_CONFIG, StatusBadge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { describeApplicationError, listApplications } from "./api";
import { ApplicationReviewModal } from "./ApplicationReviewModal";
import { ScoreCell, countOf, interviewingCount, isOverdue, useApplicationCounts } from "./display";
import { formatCompanyDate, formatCompanyDateTime } from "./format";
import type { ApplicationStatus } from "./types";

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 400;
const SEARCH_MAX = 200;

const APPLICATION_STATUSES: ApplicationStatus[] = [
  "SCORING",
  "PENDING_HR_REVIEW",
  "INTERVIEW_INVITED",
  "INTERVIEW_CONFIRMED",
  "INTERVIEW_DECLINED",
  "AWAITING_INTERVIEW_RESULT",
  "INTERVIEW_PASSED",
  "INTERVIEW_FAILED",
  "REJECTED",
  "AWAITING_ACCOUNT",
  "ON_PROBATION",
  "PROBATION_DECLINED",
  "PROBATION_PASSED",
  "PROBATION_FAILED",
];

interface Filters {
  page: number;
  q: string;
  status: ApplicationStatus | "";
}

function CountCard({
  testId,
  label,
  value,
  failed,
  tone,
  icon,
}: {
  testId: string;
  label: string;
  value: number | undefined;
  failed: boolean;
  tone: string;
  icon: React.ReactNode;
}) {
  return (
    <Card className={`p-4 flex items-center justify-between ${tone}`}>
      <div>
        <span className="text-xs font-semibold uppercase text-slate-500">{label}</span>
        <div data-testid={testId} className="text-2xl font-extrabold text-slate-900 mt-1">
          {failed ? (
            <span className="text-sm font-semibold text-rose-600" title="Không tải được số liệu">
              Lỗi tải
            </span>
          ) : value === undefined ? (
            <span className="text-sm text-slate-400">…</span>
          ) : (
            value
          )}
        </div>
      </div>
      <div className="w-10 h-10 rounded-xl bg-white/70 flex items-center justify-center text-slate-600">{icon}</div>
    </Card>
  );
}

function CountCards() {
  const counts = useApplicationCounts();
  const data = counts.data;
  const failed = counts.isError;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <CountCard
        testId="count-total"
        label="Tổng số hồ sơ"
        value={data?.total}
        failed={failed}
        tone="border-slate-200"
        icon={<Users className="w-5 h-5" />}
      />
      <CountCard
        testId="count-pending"
        label="Chờ HR duyệt"
        value={data ? countOf(data, ["PENDING_HR_REVIEW"]) : undefined}
        failed={failed}
        tone="border-amber-200 bg-amber-50/20"
        icon={<Clock className="w-5 h-5" />}
      />
      <CountCard
        testId="count-interviewing"
        label="Đang phỏng vấn"
        value={data ? interviewingCount(data) : undefined}
        failed={failed}
        tone="border-sky-200 bg-sky-50/20"
        icon={<CheckCircle2 className="w-5 h-5" />}
      />
    </div>
  );
}

// Pipeline HR dùng API xét duyệt thật; mọi quyết định do backend kiểm tra quyền và trạng thái.
export function ApplicationPipeline() {
  const { authorized } = useAuth();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<Filters>({ page: 1, q: "", status: "" });
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);

  // Debounce: chỉ gửi khi ngừng gõ; trim trước khi so sánh để khoảng trắng không gọi API.
  useEffect(() => {
    const term = search.trim();
    const timer = setTimeout(() => {
      setFilters((current) => (current.q === term ? current : { ...current, q: term, page: 1 }));
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const listQuery = useQuery({
    queryKey: ["applications", "list", filters],
    queryFn: () =>
      authorized((token) =>
        listApplications(token, {
          page: filters.page,
          pageSize: PAGE_SIZE,
          q: filters.q,
          status: filters.status || undefined,
        }),
      ),
  });

  const data = listQuery.data;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  // Quyết định làm trống trang cuối thì lùi về trang còn hợp lệ.
  useEffect(() => {
    if (data && filters.page > totalPages) setFilters((current) => ({ ...current, page: totalPages }));
  }, [data, filters.page, totalPages]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["applications"] });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Pipeline hồ sơ ứng tuyển</h2>
          <p className="text-xs text-slate-500 mt-1">
            Xem hồ sơ, điểm AI từng tiêu chí và ra quyết định mời phỏng vấn hoặc từ chối.
          </p>
        </div>
        <Button variant="outline" onClick={() => void refresh()} leftIcon={<RefreshCw className="w-4 h-4" />}>
          Làm mới
        </Button>
      </div>

      <CountCards />

      <div className="bg-white rounded-2xl shadow-xs border border-slate-200 p-4 flex flex-col md:flex-row gap-4 items-center">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            aria-label="Tìm hồ sơ"
            placeholder="Tìm theo tên hoặc email ứng viên"
            value={search}
            maxLength={SEARCH_MAX}
            onChange={(event) => setSearch(event.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <select
          aria-label="Lọc trạng thái"
          value={filters.status}
          onChange={(event) =>
            setFilters((current) => ({ ...current, status: event.target.value as ApplicationStatus | "", page: 1 }))
          }
          className="w-full md:w-auto bg-white border border-slate-300 rounded-lg px-3 py-2 text-xs"
        >
          <option value="">Tất cả trạng thái</option>
          {APPLICATION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {STATUS_CONFIG[status]?.label ?? status}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        {listQuery.isPending ? (
          <p className="p-6 text-sm text-slate-500">Đang tải danh sách hồ sơ...</p>
        ) : listQuery.isError || !data ? (
          <div className="p-6 space-y-3">
            <p className="text-sm text-rose-600">Không tải được danh sách hồ sơ.</p>
            {listQuery.error && (
              <p className="text-xs text-slate-500">{describeApplicationError(listQuery.error)}</p>
            )}
            <Button variant="outline" size="sm" onClick={() => void listQuery.refetch()}>
              Thử lại
            </Button>
          </div>
        ) : data.items.length === 0 ? (
          <p className="p-6 text-sm text-slate-500">Chưa có hồ sơ nào phù hợp.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                <tr>
                  <th className="py-3.5 px-6">Ứng viên</th>
                  <th className="py-3.5 px-4">Vị trí ứng tuyển</th>
                  <th className="py-3.5 px-4">Điểm AI</th>
                  <th className="py-3.5 px-4">Ngày nộp</th>
                  <th className="py-3.5 px-4">Hạn xét duyệt</th>
                  <th className="py-3.5 px-4">Trạng thái</th>
                  <th className="py-3.5 px-6 text-right">Chi tiết</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {data.items.map((application) => (
                  <tr key={application.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6">
                      <div className="font-bold text-slate-900 text-sm">{application.fullName}</div>
                      <div className="text-xs text-slate-400 mt-0.5">{application.email}</div>
                    </td>
                    <td className="py-4 px-4 font-semibold text-slate-800">{application.jobTitle}</td>
                    <td className="py-4 px-4">
                      <ScoreCell application={application} />
                    </td>
                    <td className="py-4 px-4 text-slate-500">{formatCompanyDate(application.submittedAt)}</td>
                    <td className="py-4 px-4 text-slate-500">
                      <div>{formatCompanyDateTime(application.reviewDueAt)}</div>
                      {isOverdue(application) && (
                        <span className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-rose-600">
                          <AlertTriangle className="w-3 h-3" /> Quá hạn
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-4 space-y-1">
                      <StatusBadge status={application.status} />
                      {application.emailIssue && (
                        <div className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700">
                          <MailWarning className="w-3 h-3" /> Lỗi gửi email
                        </div>
                      )}
                    </td>
                    <td className="py-4 px-6 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setOpenId(application.id)}
                        leftIcon={<Eye className="w-3.5 h-3.5" />}
                        aria-label={`Xem chi tiết hồ sơ ${application.fullName}`}
                      >
                        Xem chi tiết
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-3 text-xs text-slate-600">
        <span>
          Trang {filters.page} / {totalPages}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={filters.page <= 1}
          onClick={() => setFilters((current) => ({ ...current, page: current.page - 1 }))}
        >
          Trang trước
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!data || filters.page >= totalPages}
          onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}
        >
          Trang sau
        </Button>
      </div>

      {openId !== null && <ApplicationReviewModal applicationId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}
