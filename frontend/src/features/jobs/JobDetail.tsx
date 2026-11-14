import React, { useState } from 'react';
import { useParams, Link } from 'react-router';
import { ArrowLeft, MapPin, Calendar, Users, CheckCircle2, Gift, Building } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { ApplyModal } from '../candidates/ApplyModal';

export const JobDetail: React.FC = () => {
  const { id } = useParams();
  const job = mockStore.getJobById(Number(id));
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);

  if (!job) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-slate-800">Không tìm thấy vị trí tuyển dụng</h2>
        <Link to="/" className="text-emerald-600 hover:underline mt-4 inline-block text-sm">
          Quay lại danh sách việc làm
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-emerald-700 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Quay lại tất cả cơ hội việc làm</span>
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Job Content */}
        <div className="lg:col-span-2 space-y-8">
          <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-xs">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-100 px-3 py-1 rounded-md">
                {job.department}
              </span>
              <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
                {job.employmentType}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mb-4">{job.title}</h1>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4 bg-slate-50 rounded-xl text-xs text-slate-600 border border-slate-100 mb-8">
              <div>
                <span className="text-slate-400 block mb-0.5">Địa điểm</span>
                <span className="font-semibold text-slate-800 flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-500" /> {job.location}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Mức lương</span>
                <span className="font-semibold text-emerald-700">{job.salaryRange || 'Thỏa thuận'}</span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Hạn nhận hồ sơ</span>
                <span className="font-semibold text-slate-800 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" /> {job.deadline}
                </span>
              </div>
            </div>

            <div className="space-y-6 text-sm text-slate-700">
              <div>
                <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                  <Building className="w-4 h-4 text-emerald-600" />
                  Mô tả công việc
                </h3>
                <p className="whitespace-pre-line leading-relaxed text-slate-600">{job.description}</p>
              </div>

              <div>
                <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  Yêu cầu ứng viên
                </h3>
                <div className="whitespace-pre-line leading-relaxed text-slate-600 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                  {job.requirements}
                </div>
              </div>

              {job.benefits && (
                <div>
                  <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
                    <Gift className="w-4 h-4 text-emerald-600" />
                    Chế độ đãi ngộ &amp; Quyền lợi
                  </h3>
                  <div className="whitespace-pre-line leading-relaxed text-slate-600">{job.benefits}</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar Summary & Instant Apply */}
        <div className="space-y-6">
          <Card className="sticky top-24 border-emerald-100 bg-gradient-to-b from-white to-emerald-50/30">
            <h3 className="text-base font-bold text-slate-900 mb-2">Sẵn sàng ứng tuyển?</h3>
            <p className="text-xs text-slate-600 mb-6 leading-relaxed">
              Tải CV của bạn lên, hệ thống AI sẽ tự động phân tích độ phù hợp với vị trí này và điều phối phỏng vấn nhanh chóng.
            </p>

            <Button
              size="lg"
              className="w-full shadow-md shadow-emerald-700/20 mb-4"
              onClick={() => setIsApplyModalOpen(true)}
            >
              Nộp hồ sơ ngay
            </Button>

            <div className="text-[11px] text-slate-500 space-y-2 pt-4 border-t border-slate-200">
              <div className="flex items-center gap-2">
                <Users className="w-3.5 h-3.5 text-slate-400" />
                <span>Số lượng tuyển dụng: {job.headcount} nhân sự</span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>Hạn ứng tuyển: {job.deadline}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <ApplyModal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        preselectedJob={job}
      />
    </div>
  );
};

