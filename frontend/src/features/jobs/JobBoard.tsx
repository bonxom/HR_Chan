import React, { useState } from 'react';
import { Link } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Search, MapPin, Building, Calendar, UploadCloud, Users, ArrowUpRight } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { ApplyModal } from '../candidates/ApplyModal';
import { listPublicJobs } from './publicApi';
import type { PublicJobSummary } from './publicTypes';
import { formatDate } from './format';

const PAGE_SIZE = 12;

export const JobBoard: React.FC = () => {
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [selectedJob, setSelectedJob] = useState<PublicJobSummary | null>(null);
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);

  const jobsQuery = useQuery({
    queryKey: ['public-jobs', page, query],
    queryFn: ({ signal }) => listPublicJobs({ page, pageSize: PAGE_SIZE, q: query }, signal),
    placeholderData: keepPreviousData,
  });

  const data = jobsQuery.data;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    setQuery(searchInput.trim());
    setPage(1);
  };

  const openApply = (job: PublicJobSummary | null) => {
    setSelectedJob(job);
    setIsApplyModalOpen(true);
  };

  return (
    <div>
      <section className="bg-gradient-to-b from-emerald-950 via-slate-900 to-slate-900 text-white py-16 px-4 sm:px-6 lg:px-8 border-b border-slate-800">
        <div className="max-w-5xl mx-auto text-center space-y-6">
          <h1 className="text-2xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Cơ hội nghề nghiệp
          </h1>
          <p className="text-slate-300 text-sm sm:text-base max-w-2xl mx-auto leading-relaxed">
            Chọn vị trí đang mở nhận hồ sơ hoặc tải CV lên để bắt đầu.
          </p>
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              size="lg"
              onClick={() => openApply(null)}
              leftIcon={<UploadCloud className="w-5 h-5" />}
              className="w-full sm:w-auto shadow-lg shadow-emerald-900/40"
            >
              Tải CV lên
            </Button>
          </div>
        </div>
      </section>

      <div id="jobs-list" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <form
          onSubmit={submitSearch}
          className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-6 mb-8 flex flex-col sm:flex-row gap-3"
        >
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              aria-label="Tìm kiếm vị trí"
              placeholder="Tìm kiếm theo tên vị trí"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all"
            />
          </div>
          <Button type="submit" className="w-full sm:w-auto">
            Tìm
          </Button>
        </form>

        {jobsQuery.isPending && (
          <p role="status" className="text-center text-sm text-slate-500 py-16">
            Đang tải danh sách vị trí...
          </p>
        )}

        {jobsQuery.isError && !data && (
          <div role="alert" className="text-center py-12 space-y-3">
            <p className="text-sm text-rose-600">Không thể tải danh sách vị trí. Vui lòng thử lại.</p>
            <Button variant="outline" size="sm" onClick={() => jobsQuery.refetch()}>
              Thử lại
            </Button>
          </div>
        )}

        {data && data.items.length === 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-300">
            <Building className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h4 className="text-base font-bold text-slate-700">
              {query ? 'Không tìm thấy vị trí phù hợp' : 'Chưa có vị trí đang tuyển'}
            </h4>
          </div>
        )}

        {data && data.items.length > 0 && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {data.items.map((job) => (
                <article
                  key={job.id}
                  className="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 flex flex-col gap-3 hover:shadow-md transition-shadow"
                >
                  <h3 className="text-lg font-bold text-slate-900">{job.title}</h3>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="font-semibold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded-md">
                      {job.departmentName}
                    </span>
                    <span className="font-semibold text-slate-500 bg-slate-100 px-2 py-1 rounded">{job.workMode}</span>
                  </div>
                  <div className="space-y-2 text-xs text-slate-500 grow">
                    <div className="flex items-center gap-2">
                      <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span>{job.location}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400">
                      <span className="flex items-center gap-1">
                        <Users className="w-3 h-3" /> Tuyển {job.headcount} nhân sự
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" /> Hạn: {formatDate(job.deadline)}
                      </span>
                    </div>
                  </div>
                  <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-3">
                    <Link
                      to={`/jobs/${job.id}`}
                      className="text-xs font-semibold text-slate-700 hover:text-emerald-700 inline-flex items-center gap-1 transition-colors"
                    >
                      <span>Chi tiết vị trí</span>
                      <ArrowUpRight className="w-3.5 h-3.5" />
                    </Link>
                    <Button size="sm" onClick={() => openApply(job)}>
                      Ứng tuyển ngay
                    </Button>
                  </div>
                </article>
              ))}
            </div>

            <nav aria-label="Phân trang" className="flex items-center justify-center gap-4 pt-8">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Trang trước
              </Button>
              <span className="text-xs text-slate-500">
                Trang {data.page} / {totalPages}
              </span>
              <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                Trang sau
              </Button>
            </nav>
          </>
        )}
      </div>

      <ApplyModal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        preselectedJob={selectedJob}
      />
    </div>
  );
};
