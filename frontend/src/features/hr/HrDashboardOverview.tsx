import React, { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { Briefcase, Users, Calendar, Clock, AlertTriangle, Sparkles, CheckCircle2 } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { Card } from '../../shared/components/ui/Card';
import { Button } from '../../shared/components/ui/Button';

export const HrDashboardOverview: React.FC = () => {
  const [jobs, setJobs] = useState(mockStore.getJobs('OPEN'));
  const [applications, setApplications] = useState<any[]>(mockStore.getApplications());
  const [interviews, setInterviews] = useState<any[]>(mockStore.getInterviews());

  useEffect(() => {
    const update = () => {
      setJobs(mockStore.getJobs('OPEN'));
      setApplications(mockStore.getApplications());
      setInterviews(mockStore.getInterviews());
    };
    return mockStore.subscribe(update);
  }, []);

  const pendingReviewApps = applications.filter((a) => a.status === 'PENDING_HR_REVIEW');
  const upcomingInterviews = interviews.filter((i) => i.status === 'SCHEDULED' || i.status === 'CONFIRMED');

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-emerald-900 via-slate-900 to-slate-900 text-white rounded-2xl p-8 border border-emerald-800/40 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Automated Recruitment Workspace</span>
          </div>
          <h2 className="text-2xl font-extrabold tracking-tight text-white">
            Chào mừng trở lại, Ban Tuyển Dụng &amp; Nhân Sự!
          </h2>
          <p className="text-xs text-slate-300 leading-relaxed font-normal">
            Hôm nay hệ thống ghi nhận{' '}
            <strong className="text-emerald-400 font-bold">{pendingReviewApps.length} hồ sơ đang chờ duyệt</strong> và{' '}
            <strong className="text-sky-300 font-bold">{upcomingInterviews.length} buổi phỏng vấn sắp diễn ra</strong>.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Link to="/app/hr/jobs">
            <Button size="md" className="shadow-md">
              + Đăng tin tuyển dụng mới
            </Button>
          </Link>
          <Link to="/app/hr/applications">
            <Button variant="outline" size="md" className="bg-slate-800/80 text-white border-slate-700 hover:bg-slate-800">
              Xem Pipeline
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card className="p-5 flex items-center justify-between">
          <div>
            <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Tin đang mở</span>
            <div className="text-3xl font-extrabold text-slate-900 mt-1">{jobs.length}</div>
            <span className="text-[11px] text-emerald-700 font-semibold mt-0.5 block">Đang nhận hồ sơ &bull; BR01</span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
            <Briefcase className="w-6 h-6" />
          </div>
        </Card>

        <Card className="p-5 flex items-center justify-between border-amber-200 bg-amber-50/15">
          <div>
            <span className="text-amber-700 text-xs font-bold uppercase tracking-wider">Chờ HR Duyệt</span>
            <div className="text-3xl font-extrabold text-amber-800 mt-1">{pendingReviewApps.length}</div>
            <span className="text-[11px] text-amber-700 font-semibold mt-0.5 block">Hạn 5 ngày làm việc &bull; BR25</span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center">
            <Clock className="w-6 h-6" />
          </div>
        </Card>

        <Card className="p-5 flex items-center justify-between border-sky-200 bg-sky-50/15">
          <div>
            <span className="text-sky-700 text-xs font-bold uppercase tracking-wider">Lịch Phỏng Vấn</span>
            <div className="text-3xl font-extrabold text-sky-800 mt-1">{upcomingInterviews.length}</div>
            <span className="text-[11px] text-sky-700 font-semibold mt-0.5 block">Google Meet trực tuyến</span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-sky-100 text-sky-700 flex items-center justify-center">
            <Calendar className="w-6 h-6" />
          </div>
        </Card>

        <Card className="p-5 flex items-center justify-between">
          <div>
            <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Tổng ứng viên</span>
            <div className="text-3xl font-extrabold text-slate-900 mt-1">{applications.length}</div>
            <span className="text-[11px] text-teal-700 font-semibold mt-0.5 block">Tỷ lệ mời AI: 48.6%</span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-700 flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
        </Card>
      </div>

      {/* Two Columns: Actionable Attention Items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Urgent Applications Pending Review */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <h3 className="font-bold text-slate-900 text-sm">Hồ sơ cần xét duyệt gấp (Dưới ngưỡng AI hoặc Lỗi AI)</h3>
            </div>
            <Link to="/app/hr/applications" className="text-xs font-semibold text-emerald-700 hover:underline">
              Xem tất cả
            </Link>
          </div>

          <div className="space-y-3">
            {pendingReviewApps.map((app) => (
              <div key={app.id} className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-xl flex items-center justify-between text-xs">
                <div>
                  <div className="font-bold text-slate-900">{app.candidateName}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {app.jobTitle} &bull; Điểm AI: <strong className="text-amber-700">{app.aiTotalScore}/100</strong>
                  </div>
                </div>
                <Link to="/app/hr/applications">
                  <Button size="sm" variant="outline">
                    Xét duyệt
                  </Button>
                </Link>
              </div>
            ))}

            {pendingReviewApps.length === 0 && (
              <div className="text-center py-8 text-xs text-slate-400">
                <CheckCircle2 className="w-8 h-8 text-teal-500 mx-auto mb-2" />
                Tất cả hồ sơ đã được xử lý. Không có mục nào quá hạn.
              </div>
            )}
          </div>
        </Card>

        {/* Upcoming Interviews Schedule */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-emerald-600" />
              <h3 className="font-bold text-slate-900 text-sm">Lịch phỏng vấn sắp tới (Google Meet)</h3>
            </div>
            <Link to="/app/hr/interviews" className="text-xs font-semibold text-emerald-700 hover:underline">
              Mở lịch
            </Link>
          </div>

          <div className="space-y-3">
            {upcomingInterviews.map((itv) => (
              <div key={itv.id} className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-xl flex items-center justify-between text-xs">
                <div>
                  <div className="font-bold text-slate-900">{itv.application?.candidateName || 'Ứng viên'}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {new Date(itv.startAt).toLocaleString('vi-VN')} &bull; Người PV: <strong>{itv.interviewerName}</strong>
                  </div>
                </div>
                <a href={itv.meetLink} target="_blank" rel="noreferrer">
                  <Button size="sm" variant="outline" className="text-sky-700 border-sky-300 hover:bg-sky-50">
                    Vào phòng Meet
                  </Button>
                </a>
              </div>
            ))}

            {upcomingInterviews.length === 0 && (
              <div className="text-center py-8 text-xs text-slate-400">
                Chưa có lịch phỏng vấn nào được lên lịch.
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};
