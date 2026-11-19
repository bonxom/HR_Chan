import React, { useState } from 'react';
import { useParams, Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, MapPin, Calendar, Users, CheckCircle2, Gift, Building } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { ApiError } from '../../shared/services/client';
import { ApplyModal } from '../candidates/ApplyModal';
import { getPublicJob } from './publicApi';
import { formatDate } from './format';

export const JobDetail: React.FC = () => {
  const { id } = useParams();
  const jobId = Number(id);
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);

  const jobQuery = useQuery({
    queryKey: ['public-job', jobId],
    queryFn: ({ signal }) => getPublicJob(jobId, signal),
    enabled: Number.isInteger(jobId) && jobId > 0,
    retry: false,
  });
  const job = jobQuery.data;

  const backLink = (
    <Link to="/" className="text-emerald-600 hover:underline mt-4 inline-block text-sm">
      Quay lại danh sách việc làm
    </Link>
  );

  if (jobQuery.isPending && jobQuery.fetchStatus !== 'idle') {
    return (
      <p role="status" className="max-w-4xl mx-auto px-4 py-20 text-center text-sm text-slate-500">
        Đang tải thông tin vị trí...
      </p>
    );
  }

  const notFound =
    !Number.isInteger(jobId) ||
    jobId <= 0 ||
    (jobQuery.error instanceof ApiError && jobQuery.error.status === 404);
  if (notFound) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-slate-800">Không tìm thấy vị trí tuyển dụng</h2>
        {backLink}
      </div>
    );
  }

  if (!job) {
    return (
      <div role="alert" className="max-w-4xl mx-auto px-4 py-20 text-center space-y-3">
        <p className="text-sm text-rose-600">Không thể tải thông tin vị trí. Vui lòng thử lại.</p>
        <Button variant="outline" size="sm" onClick={() => jobQuery.refetch()}>
          Thử lại
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-emerald-700 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Quay lại danh sách</span>
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl p-5 sm:p-8 border border-slate-200 shadow-xs">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-100 px-3 py-1 rounded-md">
                {job.departmentName}
              </span>
              <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
                {job.workMode}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mb-4">{job.title}</h1>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 bg-slate-50 rounded-xl text-xs text-slate-600 border border-slate-100 mb-8">
              <div>
                <span className="text-slate-400 block mb-0.5">Địa điểm</span>
                <span className="font-semibold text-slate-800 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-500" /> {job.location}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Hạn nhận hồ sơ</span>
                <span className="font-semibold text-slate-800 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" /> {formatDate(job.deadline)}
                </span>
              </div>
            </div>

            <div className="space-y-6 text-sm text-slate-700">
              <section>
                <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                  <Building className="w-4 h-4 text-emerald-600" />
                  Mô tả công việc
                </h3>
                <p className="whitespace-pre-line leading-relaxed text-slate-600">{job.description}</p>
              </section>

              <section>
                <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  Yêu cầu ứng viên
                </h3>
                <p className="whitespace-pre-line leading-relaxed text-slate-600 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                  {job.requirements}
                </p>
              </section>

              {job.benefits && (
                <section>
                  <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                    <Gift className="w-4 h-4 text-emerald-600" />
                    Quyền lợi
                  </h3>
                  <p className="whitespace-pre-line leading-relaxed text-slate-600">{job.benefits}</p>
                </section>
              )}
            </div>
          </div>
        </div>

        <aside>
          <div className="lg:sticky lg:top-24 bg-white rounded-2xl p-5 border border-emerald-100 space-y-4">
            <Button size="lg" className="w-full" onClick={() => setIsApplyModalOpen(true)}>
              Nộp hồ sơ ngay
            </Button>
            <div className="text-[11px] text-slate-500 space-y-2 pt-4 border-t border-slate-200">
              <div className="flex items-center gap-2">
                <Users className="w-3.5 h-3.5 text-slate-400" />
                <span>Số lượng tuyển: {job.headcount} nhân sự</span>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <ApplyModal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        preselectedJob={{ id: job.id, title: job.title }}
      />
    </div>
  );
};
