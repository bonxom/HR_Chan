import React, { useState, useEffect } from 'react';
import { Video, Clock, User, UserCheck, ExternalLink } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { StatusBadge } from '../../shared/components/ui/Badge';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Modal } from '../../shared/components/ui/Modal';
import { InterviewerEvaluationModal } from './InterviewerEvaluationModal';
import { showToast } from '../../shared/components/ui/Toast';

export const InterviewCalendar: React.FC = () => {
  const [interviews, setInterviews] = useState<any[]>(mockStore.getInterviews());
  const [selectedInterview, setSelectedInterview] = useState<any | null>(null);
  const [isEvaluationOpen, setIsEvaluationOpen] = useState(false);
  const [isRescheduleOpen, setIsRescheduleOpen] = useState(false);
  const [newSlot, setNewSlot] = useState('2026-11-17T15:00');
  const [rescheduleNote, setRescheduleNote] = useState('');

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setInterviews(mockStore.getInterviews());
    });
    return unsubscribe;
  }, []);

  const handleOpenEvaluation = (itv: any) => {
    setSelectedInterview(itv);
    setIsEvaluationOpen(true);
  };

  const handleOpenReschedule = (itv: any) => {
    setSelectedInterview(itv);
    setIsRescheduleOpen(true);
  };

  const handleConfirmReschedule = () => {
    if (!selectedInterview) return;
    mockStore.updateInterviewStatus(
      selectedInterview.id,
      'SCHEDULED',
      rescheduleNote || 'HR đã xếp lại khung giờ mới trên Google Calendar'
    );
    showToast({
      type: 'success',
      title: 'Đã xếp lại lịch phỏng vấn (UC3.04)',
      message: 'Đường dẫn xác nhận cũ đã bị vô hiệu và đường dẫn mới đã được gửi tới ứng viên (BR51).',
    });
    setIsRescheduleOpen(false);
  };

  const handleCancelInterview = (itvId: number) => {
    const reason = prompt('Nhập lý do hủy buổi phỏng vấn (bắt buộc theo BR55):');
    if (reason) {
      mockStore.updateInterviewStatus(itvId, 'CANCELLED', reason);
      showToast({
        type: 'info',
        title: 'Đã hủy buổi phỏng vấn (UC3.05)',
        message: 'Hồ sơ đã quay về trạng thái Chờ HR duyệt để quyết định mời lại hoặc từ chối.',
      });
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-slate-900">Quản lý Lịch Phỏng vấn (Google Meet &amp; Calendar)</h2>
        <p className="text-xs text-slate-500 mt-1">
          Theo dõi các buổi phỏng vấn, link phòng họp Google Meet và điều phối xếp lại lịch linh hoạt (UC3.01 &mdash; UC3.06).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {interviews.map((itv) => (
          <Card key={itv.id} className="flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-start justify-between gap-2 mb-3">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Cuộc hẹn #{itv.id}
                </span>
                <StatusBadge status={itv.status} />
              </div>

              <h3 className="font-bold text-slate-900 text-sm mb-1">{itv.application?.candidateName || 'Ứng viên'}</h3>
              <p className="text-xs text-emerald-700 font-semibold mb-3">
                {itv.application?.jobTitle || 'Vị trí tuyển dụng'}
              </p>

              <div className="space-y-2 text-xs text-slate-600 p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="font-medium text-slate-800">
                    {new Date(itv.startAt).toLocaleString('vi-VN', {
                      weekday: 'short',
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span>Người phỏng vấn: <strong className="text-slate-800">{itv.interviewerName}</strong></span>
                </div>

                <div className="flex items-center gap-2 pt-1 border-t border-slate-200/60">
                  <Video className="w-3.5 h-3.5 text-sky-600 shrink-0" />
                  <a
                    href={itv.meetLink}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sky-700 font-bold hover:underline inline-flex items-center gap-1"
                  >
                    <span>Vào phòng Google Meet</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>

              {itv.result && (
                <div className="mt-3 p-2.5 bg-teal-50 border border-teal-200 rounded-lg text-xs">
                  <span className="text-slate-500">Kết quả đánh giá: </span>
                  <strong className="text-teal-900">
                    {itv.result === 'PASSED' ? 'Đạt' : itv.result === 'ABSENT' ? 'Vắng mặt' : 'Không đạt'}
                  </strong>
                  {itv.finalNote && <p className="text-[11px] text-teal-800 mt-1 italic">&ldquo;{itv.finalNote}&rdquo;</p>}
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleOpenEvaluation(itv)}
                leftIcon={<UserCheck className="w-3.5 h-3.5" />}
              >
                {itv.result ? 'Xem kết quả' : 'Chấm điểm PV'}
              </Button>

              {itv.status !== 'COMPLETED' && itv.status !== 'CANCELLED' && (
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleOpenReschedule(itv)}
                    className="text-slate-600"
                  >
                    Xếp lại lịch
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCancelInterview(itv.id)}
                    className="text-rose-600 hover:bg-rose-50"
                  >
                    Hủy lịch
                  </Button>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>

      {/* Reschedule Modal (UC3.04) */}
      <Modal
        isOpen={isRescheduleOpen}
        onClose={() => setIsRescheduleOpen(false)}
        title="Xếp lại lịch phỏng vấn (UC3.04)"
        subtitle="Chọn khung giờ mới trên Google Calendar và phát hành đường dẫn xác nhận mới"
        maxWidth="md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Khung giờ mới (Trong giờ làm việc của công ty - BR09):
            </label>
            <input
              type="datetime-local"
              value={newSlot}
              onChange={(e) => setNewSlot(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg p-2.5 text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Ghi chú cho ứng viên:
            </label>
            <textarea
              rows={2}
              value={rescheduleNote}
              onChange={(e) => setRescheduleNote(e.target.value)}
              placeholder="Ví dụ: Người phỏng vấn điều chỉnh lịch bận đột xuất..."
              className="w-full bg-white border border-slate-300 rounded-lg p-2.5 text-xs"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsRescheduleOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleConfirmReschedule}>
              Lưu &amp; Gửi email lịch mới
            </Button>
          </div>
        </div>
      </Modal>

      {/* Interviewer Evaluation Modal */}
      <InterviewerEvaluationModal
        isOpen={isEvaluationOpen}
        onClose={() => setIsEvaluationOpen(false)}
        interview={selectedInterview}
      />
    </div>
  );
};
