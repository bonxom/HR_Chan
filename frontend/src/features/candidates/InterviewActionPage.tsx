import React, { useState } from 'react';
import { useParams } from 'react-router';
import { Calendar, Video, Clock, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { showToast } from '../../shared/components/ui/Toast';

export const InterviewActionPage: React.FC = () => {
  const { id } = useParams();
  const [status, setStatus] = useState<'PENDING' | 'CONFIRMED' | 'RESCHEDULE_SENT' | 'DECLINED'>('PENDING');
  const [isRescheduling, setIsRescheduling] = useState(false);
  const [rescheduleSlot1, setRescheduleSlot1] = useState('2026-11-18T10:00');
  const [rescheduleSlot2, setRescheduleSlot2] = useState('2026-11-19T14:30');
  const [rescheduleNote, setRescheduleNote] = useState('');
  const [declineReason, setDeclineReason] = useState('');
  const [isDeclining, setIsDeclining] = useState(false);

  const handleConfirm = () => {
    setStatus('CONFIRMED');
    showToast({
      type: 'success',
      title: 'Đã xác nhận lịch phỏng vấn!',
      message: 'Hệ thống đã cập nhật trạng thái tham dự lên Google Calendar của hội đồng phỏng vấn.',
    });
  };

  const handleRescheduleSubmit = () => {
    if (!rescheduleNote) {
      showToast({ type: 'error', message: 'Vui lòng ghi chú lý do đề xuất đổi lịch phỏng vấn.' });
      return;
    }
    setStatus('RESCHEDULE_SENT');
    setIsRescheduling(false);
    showToast({
      type: 'info',
      title: 'Đã gửi yêu cầu đổi lịch',
      message: 'Bộ phận tuyển dụng sẽ kiểm tra lịch khả dụng và phản hồi trong vòng 1 ngày làm việc.',
    });
  };

  const handleDeclineSubmit = () => {
    setStatus('DECLINED');
    setIsDeclining(false);
    showToast({
      type: 'info',
      title: 'Đã từ chối phỏng vấn',
      message: 'Cảm ơn bạn đã phản hồi. Sự kiện lịch đã được tự động hủy.',
    });
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-16">
      <div className="text-center mb-8">
        <span className="text-xs font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
          Xác nhận Lời mời Phỏng vấn (UC3.01)
        </span>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-3">
          Phỏng vấn vị trí Senior Python / FastAPI Engineer
        </h1>
        <p className="text-xs text-slate-500 mt-1">Mã cuộc hẹn: #ITV-{id || '101'}</p>
      </div>

      <Card className="space-y-6">
        {/* Schedule Highlights */}
        <div className="p-5 bg-slate-50 rounded-2xl border border-slate-200 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <span className="text-slate-400 block">Thời gian phỏng vấn</span>
              <span className="font-bold text-slate-800 text-sm">14:00 &mdash; 15:00, Thứ Hai (16/11/2026)</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-sky-100 text-sky-700 flex items-center justify-center shrink-0">
              <Video className="w-5 h-5" />
            </div>
            <div>
              <span className="text-slate-400 block">Hình thức &amp; Phòng họp</span>
              <a
                href="https://meet.google.com/abc-hrchan-xyz"
                target="_blank"
                rel="noreferrer"
                className="font-bold text-sky-700 underline text-sm"
              >
                Google Meet (Link trực tuyến)
              </a>
            </div>
          </div>
        </div>

        {/* Warning Note on 2 business day response (BR23) */}
        <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2.5">
          <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>
            Hạn phản hồi: trong vòng <strong>2 ngày làm việc</strong> kể từ khi nhận thư (hết giờ hành chính ngày 14/11/2026).
            Quá hạn hệ thống sẽ tự động coi như từ chối theo quy tắc <strong>BR23</strong>.
          </span>
        </div>

        {status === 'CONFIRMED' && (
          <div className="p-6 bg-teal-50 border border-teal-200 rounded-xl text-center space-y-2">
            <CheckCircle2 className="w-10 h-10 text-teal-600 mx-auto" />
            <h3 className="text-base font-bold text-teal-900">Bạn đã xác nhận tham dự thành công!</h3>
            <p className="text-xs text-teal-700">
              Lịch phỏng vấn đã được cập nhật. Vui lòng tham gia phòng họp Google Meet đúng giờ.
            </p>
          </div>
        )}

        {status === 'RESCHEDULE_SENT' && (
          <div className="p-6 bg-sky-50 border border-sky-200 rounded-xl text-center space-y-2">
            <RefreshCw className="w-10 h-10 text-sky-600 mx-auto" />
            <h3 className="text-base font-bold text-sky-900">Yêu cầu đổi lịch đã được ghi nhận!</h3>
            <p className="text-xs text-sky-700">
              Bộ phận tuyển dụng sẽ kiểm tra khung giờ đề xuất của bạn và gửi email xác nhận lịch mới.
            </p>
          </div>
        )}

        {status === 'DECLINED' && (
          <div className="p-6 bg-rose-50 border border-rose-200 rounded-xl text-center space-y-2">
            <XCircle className="w-10 h-10 text-rose-600 mx-auto" />
            <h3 className="text-base font-bold text-rose-900">Bạn đã từ chối buổi phỏng vấn</h3>
            <p className="text-xs text-rose-700">
              Cảm ơn bạn đã quan tâm đến công ty. Chúc bạn thành công trên con đường sự nghiệp!
            </p>
          </div>
        )}

        {status === 'PENDING' && !isRescheduling && !isDeclining && (
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
            <Button size="lg" onClick={handleConfirm} leftIcon={<CheckCircle2 className="w-4 h-4" />}>
              Xác nhận tham gia đúng giờ
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => setIsRescheduling(true)}
              leftIcon={<RefreshCw className="w-4 h-4" />}
            >
              Đề xuất đổi khung giờ khác (BR49)
            </Button>
            <Button variant="danger" size="lg" onClick={() => setIsDeclining(true)}>
              Từ chối phỏng vấn
            </Button>
          </div>
        )}

        {/* Reschedule Form (BR49) */}
        {isRescheduling && (
          <div className="p-5 border border-slate-200 rounded-2xl bg-slate-50/50 space-y-4">
            <h4 className="text-sm font-bold text-slate-800">Đề xuất 1–2 khung giờ phù hợp (Giờ hành chính):</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Khung giờ đề xuất 1 *</label>
                <input
                  type="datetime-local"
                  value={rescheduleSlot1}
                  onChange={(e) => setRescheduleSlot1(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Khung giờ đề xuất 2 (tùy chọn)</label>
                <input
                  type="datetime-local"
                  value={rescheduleSlot2}
                  onChange={(e) => setRescheduleSlot2(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Lý do xin đổi lịch *</label>
              <textarea
                rows={2}
                value={rescheduleNote}
                onChange={(e) => setRescheduleNote(e.target.value)}
                placeholder="Ví dụ: Bận lịch bảo vệ đồ án tốt nghiệp vào chiều thứ Hai..."
                className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setIsRescheduling(false)}>
                Hủy
              </Button>
              <Button size="sm" onClick={handleRescheduleSubmit}>
                Gửi đề xuất đổi lịch
              </Button>
            </div>
          </div>
        )}

        {/* Decline Form */}
        {isDeclining && (
          <div className="p-5 border border-rose-200 rounded-2xl bg-rose-50/40 space-y-4">
            <h4 className="text-sm font-bold text-rose-900">Xác nhận từ chối phỏng vấn:</h4>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Lý do từ chối (không bắt buộc)</label>
              <textarea
                rows={2}
                value={declineReason}
                onChange={(e) => setDeclineReason(e.target.value)}
                placeholder="Ví dụ: Đã nhận được offer từ đơn vị khác..."
                className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setIsDeclining(false)}>
                Quay lại
              </Button>
              <Button variant="danger" size="sm" onClick={handleDeclineSubmit}>
                Xác nhận từ chối
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
