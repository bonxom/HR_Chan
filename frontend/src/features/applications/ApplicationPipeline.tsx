import React, { useState, useEffect } from 'react';
import { Search, Eye, Users, Clock, CheckCircle2 } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { StatusBadge } from '../../shared/components/ui/Badge';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { ApplicationReviewModal } from './ApplicationReviewModal';

export const ApplicationPipeline: React.FC = () => {
  const [applications, setApplications] = useState<any[]>(mockStore.getApplications());
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedApp, setSelectedApp] = useState<any | null>(null);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setApplications(mockStore.getApplications());
    });
    return unsubscribe;
  }, []);

  const pendingReviewCount = applications.filter((a) => a.status === 'PENDING_HR_REVIEW').length;
  const interviewCount = applications.filter((a) => a.status.startsWith('INTERVIEW_')).length;
  const probationCount = applications.filter((a) => a.status.startsWith('PROBATION_') || a.status === 'ON_PROBATION').length;

  const filteredApps = applications.filter((app) => {
    const matchesSearch =
      app.candidateName.toLowerCase().includes(search.toLowerCase()) ||
      app.candidateEmail.toLowerCase().includes(search.toLowerCase()) ||
      app.jobTitle.toLowerCase().includes(search.toLowerCase());

    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'PENDING_HR_REVIEW' && app.status === 'PENDING_HR_REVIEW') ||
      (statusFilter === 'INTERVIEWS' && app.status.startsWith('INTERVIEW_')) ||
      (statusFilter === 'PROBATION' && (app.status.startsWith('PROBATION_') || app.status === 'ON_PROBATION'));

    return matchesSearch && matchesStatus;
  });

  const handleOpenReview = (app: any) => {
    setSelectedApp(app);
    setIsReviewModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center justify-between border-slate-200">
          <div>
            <span className="text-slate-400 text-xs font-semibold uppercase">Tổng số hồ sơ</span>
            <div className="text-2xl font-extrabold text-slate-900 mt-1">{applications.length}</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600">
            <Users className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-amber-200 bg-amber-50/20">
          <div>
            <span className="text-amber-700 text-xs font-semibold uppercase">Chờ HR xét duyệt</span>
            <div className="text-2xl font-extrabold text-amber-800 mt-1">{pendingReviewCount}</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center text-amber-700">
            <Clock className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-sky-200 bg-sky-50/20">
          <div>
            <span className="text-sky-700 text-xs font-semibold uppercase">Đang phỏng vấn</span>
            <div className="text-2xl font-extrabold text-sky-800 mt-1">{interviewCount}</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-sky-100 flex items-center justify-center text-sky-700">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between border-teal-200 bg-teal-50/20">
          <div>
            <span className="text-teal-700 text-xs font-semibold uppercase">Đang thử việc</span>
            <div className="text-2xl font-extrabold text-teal-800 mt-1">{probationCount}</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-teal-100 flex items-center justify-center text-teal-700">
            <Users className="w-5 h-5" />
          </div>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-2xl shadow-xs border border-slate-200 p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Tìm theo tên ứng viên, email, vị trí tuyển dụng..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto">
          {[
            { label: 'Tất cả', value: 'ALL' },
            { label: `Chờ HR duyệt (${pendingReviewCount})`, value: 'PENDING_HR_REVIEW' },
            { label: 'Phỏng vấn', value: 'INTERVIEWS' },
            { label: 'Thử việc', value: 'PROBATION' },
          ].map((tab) => (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap ${
                statusFilter === tab.value
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Applications Data Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3.5 px-6">Ứng viên &amp; Liên hệ</th>
                <th className="py-3.5 px-4">Vị trí ứng tuyển</th>
                <th className="py-3.5 px-4">Điểm AI</th>
                <th className="py-3.5 px-4">Ngày nộp</th>
                <th className="py-3.5 px-4">Trạng thái hồ sơ</th>
                <th className="py-3.5 px-6 text-right">Chi tiết</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredApps.map((app) => (
                <tr key={app.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-4 px-6">
                    <div className="font-bold text-slate-900 text-sm">{app.candidateName}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {app.candidateEmail} &bull; {app.candidatePhone}
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <div className="font-semibold text-slate-800">{app.jobTitle}</div>
                    <div className="text-[11px] text-slate-400">{app.department}</div>
                  </td>
                  <td className="py-4 px-4">
                    <span
                      className={`font-extrabold text-sm px-2.5 py-1 rounded-md border ${
                        (app.aiTotalScore || 0) >= 80
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}
                    >
                      {app.aiTotalScore || 0}/100
                    </span>
                  </td>
                  <td className="py-4 px-4 font-medium text-slate-500">
                    {new Date(app.submittedAt).toLocaleDateString('vi-VN')}
                  </td>
                  <td className="py-4 px-4">
                    <StatusBadge status={app.status} />
                  </td>
                  <td className="py-4 px-6 text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleOpenReview(app)}
                      leftIcon={<Eye className="w-3.5 h-3.5" />}
                    >
                      Xét duyệt &amp; Giải trình
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ApplicationReviewModal
        isOpen={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        application={selectedApp}
      />
    </div>
  );
};
