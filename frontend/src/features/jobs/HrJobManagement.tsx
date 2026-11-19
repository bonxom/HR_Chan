import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Sliders } from "lucide-react";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/shared/services/client";
import { Button } from "@/shared/components/ui/Button";
import { StatusBadge } from "@/shared/components/ui/Badge";
import { showToast } from "@/shared/components/ui/Toast";
import { closeJob, deleteDraftJob, describeJobError, listDepartments, listInterviewers, listJobs, publishJob } from "./api";
import { CriteriaModal } from "./CriteriaModal";
import { formatDate } from "./format";
import { JobFormModal } from "./JobFormModal";
import type { JobStatus, JobSummary } from "./types";
import { companyToday } from "./validation";

const PAGE_SIZE = 20;

const STATUS_OPTIONS: { value: JobStatus; label: string }[] = [
  { value: "DRAFT", label: "Bản nháp" },
  { value: "OPEN", label: "Đang mở" },
  { value: "CLOSED", label: "Đã đóng" },
];

interface Filters {
  page: number;
  q: string;
  status: JobStatus | "";
  departmentId: string;
}

// Trang HR dùng API thật: query đọc danh mục/tin, mutation ghi rồi làm mới cache.
export function HrJobManagement() {
  const { authorized } = useAuth();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<Filters>({ page: 1, q: "", status: "", departmentId: "" });
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<{ open: boolean; jobId: number | null }>({ open: false, jobId: null });
  const [criteriaJob, setCriteriaJob] = useState<JobSummary | null>(null);

  const jobsQuery = useQuery({
    queryKey: ["jobs", filters],
    queryFn: () =>
      authorized((token) =>
        listJobs(token, {
          page: filters.page,
          pageSize: PAGE_SIZE,
          q: filters.q,
          status: filters.status || undefined,
          departmentId: filters.departmentId ? Number(filters.departmentId) : undefined,
        }),
      ),
  });
  const departmentsQuery = useQuery({
    queryKey: ["departments"],
    queryFn: () => authorized((token) => listDepartments(token)),
    staleTime: 5 * 60_000,
  });
  const interviewersQuery = useQuery({
    queryKey: ["interviewers"],
    queryFn: () => authorized((token) => listInterviewers(token)),
    staleTime: 60_000,
  });

  // Một tin thay đổi ảnh hưởng cả danh sách, chi tiết và lịch sử tiêu chí đang cache.
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      queryClient.invalidateQueries({ queryKey: ["job"] }),
      queryClient.invalidateQueries({ queryKey: ["criteria-versions"] }),
    ]);

  const reportFailure = (failure: unknown) => {
    setNotice(describeJobError(failure));
    if (failure instanceof ApiError && failure.status === 409) void refresh();
  };

  const handleSaved = (message: string) => {
    setForm({ open: false, jobId: null });
    setCriteriaJob(null);
    setNotice(null);
    showToast({ type: "success", message });
    void refresh();
  };

  const handleConflict = (message: string) => {
    setForm({ open: false, jobId: null });
    setCriteriaJob(null);
    setNotice(message);
    void refresh();
  };

  const publishMutation = useMutation({
    mutationFn: (job: JobSummary) => authorized((token) => publishJob(token, job.id, job.version)),
    onSuccess: () => handleSaved("Đã đăng tin tuyển dụng."),
    onError: reportFailure,
  });
  const closeMutation = useMutation({
    mutationFn: (job: JobSummary) => authorized((token) => closeJob(token, job.id, job.version)),
    onSuccess: () => handleSaved("Đã đóng tin tuyển dụng. Hệ thống ngừng nhận hồ sơ mới cho vị trí này."),
    onError: reportFailure,
  });
  // Chỉ bỏ hàng sau khi API xác nhận204; lỗi vẫn giữ dữ liệu để người dùng thử lại.
  const deleteMutation = useMutation({
    mutationFn: (job: JobSummary) => authorized((token) => deleteDraftJob(token, job.id, job.version)),
    onSuccess: () => {
      setNotice(null);
      showToast({ type: "success", message: "Đã xóa bản nháp." });
      void refresh();
    },
    onError: (failure) => {
      reportFailure(failure);
      if (failure instanceof ApiError && failure.status === 404) void refresh();
    },
  });

  // Hủy xác nhận không gọi API. Backend vẫn tự kiểm trạng thái/version sau xác nhận.
  const handleDelete = (job: JobSummary) => {
    if (deleteMutation.isPending) return;
    if (window.confirm(`Xóa vĩnh viễn bản nháp "${job.title}"? Thao tác này không thể khôi phục.`)) {
      setNotice(null);
      deleteMutation.mutate(job);
    }
  };

  const handleClose = (job: JobSummary) => {
    if (window.confirm(`Đóng tin "${job.title}"? Hệ thống sẽ ngừng nhận hồ sơ mới cho vị trí này.`)) {
      setNotice(null);
      closeMutation.mutate(job);
    }
  };

  const applySearch = (event: FormEvent) => {
    event.preventDefault();
    setFilters((current) => ({ ...current, q: search.trim(), page: 1 }));
  };

  const data = jobsQuery.data;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  // Khi xóa hết hàng cuối trang hoặc tổng số thay đổi, quay về trang còn hợp lệ.
  useEffect(() => {
    if (data && filters.page > totalPages) {
      setFilters((current) => ({ ...current, page: totalPages }));
    }
  }, [data, filters.page, totalPages]);
  const departments = departmentsQuery.data ?? [];
  const interviewers = interviewersQuery.data ?? [];
  const busy = publishMutation.isPending || closeMutation.isPending || deleteMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Quản lý tin tuyển dụng</h2>
          <p className="text-xs text-slate-500 mt-1">
            Tạo, đăng, cập nhật và đóng tin; thiết lập tiêu chí chấm điểm, ngưỡng tự động mời và người phỏng vấn.
          </p>
        </div>
        <Button onClick={() => setForm({ open: true, jobId: null })} leftIcon={<Plus className="w-4 h-4" />}>
          Tạo tin tuyển dụng
        </Button>
      </div>

      {notice && (
        <div role="alert" className="p-3 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl">
          {notice}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-3">
        <form onSubmit={applySearch} className="flex gap-2 flex-1">
          <input
            aria-label="Tìm theo tên vị trí"
            value={search}
            maxLength={200}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tìm theo tên vị trí"
            className="flex-1 bg-white border border-slate-300 rounded-lg px-3 py-2 text-sm"
          />
          <Button type="submit" variant="outline" leftIcon={<Search className="w-4 h-4" />}>
            Tìm
          </Button>
        </form>
        <select
          aria-label="Lọc trạng thái"
          value={filters.status}
          onChange={(event) =>
            setFilters((current) => ({ ...current, status: event.target.value as JobStatus | "", page: 1 }))
          }
          className="bg-white border border-slate-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Tất cả trạng thái</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Lọc phòng ban"
          value={filters.departmentId}
          onChange={(event) => setFilters((current) => ({ ...current, departmentId: event.target.value, page: 1 }))}
          className="bg-white border border-slate-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Tất cả phòng ban</option>
          {departments.map((item) => (
            <option key={item.id} value={String(item.id)}>
              {item.name}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        {jobsQuery.isPending ? (
          <p className="p-6 text-sm text-slate-500">Đang tải danh sách tin tuyển dụng...</p>
        ) : jobsQuery.isError || !data ? (
          <div className="p-6 space-y-3">
            <p className="text-sm text-rose-600">Không tải được danh sách tin tuyển dụng.</p>
            <Button variant="outline" size="sm" onClick={() => void jobsQuery.refetch()}>
              Thử lại
            </Button>
          </div>
        ) : data.items.length === 0 ? (
          <p className="p-6 text-sm text-slate-500">Chưa có tin tuyển dụng nào.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="py-3.5 px-6">Vị trí</th>
                  <th className="py-3.5 px-4">Phòng ban</th>
                  <th className="py-3.5 px-4">Trạng thái</th>
                  <th className="py-3.5 px-4">Số lượng</th>
                  <th className="py-3.5 px-4">Hạn nộp</th>
                  <th className="py-3.5 px-6 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {data.items.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-4 px-6">
                      <div className="font-bold text-slate-900 text-sm">{job.title}</div>
                      {(job.workMode || job.location) && (
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {[job.workMode, job.location].filter(Boolean).join(" • ")}
                        </div>
                      )}
                    </td>
                    <td className="py-4 px-4">{job.departmentName}</td>
                    <td className="py-4 px-4">
                      <StatusBadge status={job.status} />
                      {job.status === "CLOSED" && job.deletionDueDate && (
                        <p className="mt-1 text-[11px] text-slate-500 max-w-48">
                          {job.deletionDueDate <= companyToday()
                            ? `Đang chờ dọn dẹp (đủ hạn từ ${formatDate(job.deletionDueDate)})`
                            : `Tự động xóa từ ngày ${formatDate(job.deletionDueDate)}`}
                        </p>
                      )}
                    </td>
                    <td className="py-4 px-4">{job.headcount === null ? "—" : `${job.headcount} người`}</td>
                    <td className="py-4 px-4">{formatDate(job.deadline)}</td>
                    <td className="py-4 px-6 text-right space-x-2 whitespace-nowrap">
                      {job.status === "CLOSED" ? (
                        <Button variant="outline" size="sm" onClick={() => setCriteriaJob(job)}>
                          Xem tiêu chí
                        </Button>
                      ) : (
                        <>
                          <Button variant="outline" size="sm" onClick={() => setForm({ open: true, jobId: job.id })}>
                            Sửa
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCriteriaJob(job)}
                            leftIcon={<Sliders className="w-3.5 h-3.5" />}
                          >
                            Bộ tiêu chí
                          </Button>
                          {job.status === "DRAFT" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={busy}
                              onClick={() => handleDelete(job)}
                              className="text-rose-600 hover:bg-rose-50"
                            >
                              Xóa bản nháp
                            </Button>
                          )}
                          {job.status === "DRAFT" && (
                            <Button
                              size="sm"
                              disabled={busy}
                              onClick={() => {
                                setNotice(null);
                                publishMutation.mutate(job);
                              }}
                            >
                              Đăng tin
                            </Button>
                          )}
                          {job.status === "OPEN" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={busy}
                              onClick={() => handleClose(job)}
                              className="text-rose-600 hover:bg-rose-50"
                            >
                              Đóng tin
                            </Button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-3 text-xs text-slate-600">
        <span>Trang {filters.page} / {totalPages}</span>
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
          disabled={filters.page >= totalPages}
          onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}
        >
          Trang sau
        </Button>
      </div>

      <JobFormModal
        isOpen={form.open}
        jobId={form.jobId}
        departments={departments}
        interviewers={interviewers}
        onClose={() => setForm({ open: false, jobId: null })}
        onSaved={handleSaved}
        onConflict={handleConflict}
      />
      <CriteriaModal
        job={criteriaJob}
        interviewers={interviewers}
        onClose={() => setCriteriaJob(null)}
        onSaved={handleSaved}
        onConflict={handleConflict}
      />
    </div>
  );
}
