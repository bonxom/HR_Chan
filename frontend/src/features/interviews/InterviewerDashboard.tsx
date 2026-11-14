import React, { useState, useEffect } from 'react';
import { Video, Calendar, UserCheck, Eye, ExternalLink } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { StatusBadge } from '../../shared/components/ui/Badge';
import { InterviewerEvaluationModal } from './InterviewerEvaluationModal';
import { ApplicationReviewModal } from '../applications/ApplicationReviewModal';

export const InterviewerDashboard: React.FC = () => {
  const [currentUser] = useState(mockStore.getCurrentUser());
  const [interviews, setInterviews] = useState<any[]>([]);
  const [selectedInterview, setSelectedInterview] = useState<any | null>(null);
  const [isEvaluationOpen, setIsEvaluationOpen] = useState(false);
  const [isDossierOpen, setIsDossierOpen] = useState(false);

  useEffect(() => {
    const update = () => {
      // Filter interviews assigned to current interviewer (NFR36)
      const all = mockStore.getInterviews();
      const myInterviews = all.filter(
        (i) => i.interviewerId === currentUser.id || currentUser.roles.includes('HR') || currentUser.roles.includes('ADMIN')
      );
      setInterviews(myInterviews);
    };

    update();
    return mockStore.subscribe(update);
  }, [currentUser]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-slate-900">Lịch Phỏng Vấn Của Tôi (UC3.07)</h2>
        <p className="text-xs text-slate-500 mt-1">
          Danh sách các buổi phỏng vấn bạn được chỉ định làm chuyên gia đánh giá. Chỉ truy cập hồ sơ trong phạm vi được giao (NFR36).
        </p>
      </div>

      <div className="space-y-4">
        {interviews.map((itv) => (
          <Card key={itv.id} className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-sm text-slate-900">
                  {itv.application?.candidateName || 'Ứng viên'}
                </span>
                <StatusBadge status={itv.status} />
                {itv.result && (
                  <span className="text-[11px] font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                    Kết quả: {itv.result === 'PASSED' ? 'Đạt' : itv.result === 'ABSENT' ? 'Vắng mặt' : 'Không đạt'}
                  </span>
                )}
              </div>

              <div className="text-xs text-emerald-700 font-semibold">
                {itv.application?.jobTitle} &bull; {itv.application?.department}
              </div>

              <div className="flex items-center gap-4 text-xs text-slate-500 pt-1">
                <span className="flex items-center gap-1.5 font-medium">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  {new Date(itv.startAt).toLocaleString('vi-VN')}
                </span>
                <a
                  href={itv.meetLink}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-sky-700 font-bold hover:underline"
                >
                  <Video className="w-3.5 h-3.5 text-sky-600" />
                  <span>Google Meet</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSelectedInterview(itv);
                  setIsDossierOpen(true);
                }}
                leftIcon={<Eye className="w-3.5 h-3.5" />}
              >
                Hồ sơ &amp; Điểm AI
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setSelectedInterview(itv);
                  setIsEvaluationOpen(true);
                }}
                leftIcon={<UserCheck className="w-3.5 h-3.5" />}
              >
                {itv.result ? 'Sửa đánh giá' : 'Nhập kết quả phỏng vấn'}
              </Button>
            </div>
          </Card>
        ))}

        {interviews.length === 0 && (
          <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-slate-300">
            <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-700">Hiện tại bạn chưa có buổi phỏng vấn nào</h4>
            <p className="text-xs text-slate-400 mt-1">Khi HR gán bạn vào tin tuyển dụng và ứng viên xác nhận, lịch sẽ hiển thị tại đây.</p>
          </div>
        )}
      </div>

      <InterviewerEvaluationModal
        isOpen={isEvaluationOpen}
        onClose={() => setIsEvaluationOpen(false)}
        interview={selectedInterview}
      />

      <ApplicationReviewModal
        isOpen={isDossierOpen}
        onClose={() => setIsDossierOpen(false)}
        application={selectedInterview?.application}
      />
    </div>
  );
};

