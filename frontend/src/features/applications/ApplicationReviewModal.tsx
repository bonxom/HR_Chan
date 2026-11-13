import React, { useState } from 'react';
import { Sparkles, CheckCircle2, XCircle, Quote, AlertTriangle, User, Phone, Mail } from 'lucide-react';
import { Modal } from '../../shared/components/ui/Modal';
import { Button } from '../../shared/components/ui/Button';
import { mockStore } from '../../shared/services/mockStore';
import { StatusBadge } from '../../shared/components/ui/Badge';
import { showToast } from '../../shared/components/ui/Toast';

interface ApplicationReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  application: any | null;
}

export const ApplicationReviewModal: React.FC<ApplicationReviewModalProps> = ({
  isOpen,
  onClose,
  application,
}) => {
  const [rejectMode, setRejectMode] = useState(false);
  const [rejectReasonType, setRejectReasonType] = useState('Kinh nghiệm chuyên môn chưa đáp ứng');
  const [rejectReasonOther, setRejectReasonOther] = useState('');
  const [hrNote, setHrNote] = useState('');

  if (!application) return null;

  const handleApproveInvite = () => {
    mockStore.updateApplicationStatus(
      application.id,
      'INTERVIEW_INVITED',
      hrNote || 'HR đã duyệt đạt và tạo lời mời phỏng vấn'
    );
    showToast({
      type: 'success',
      title: 'Đã duyệt đạt hồ sơ',
      message: 'Hồ sơ chuyển sang trạng thái Đã mời phỏng vấn. Hệ thống tự động tạo lịch Google Meet.',
    });
    onClose();
  };

  const handleReject = () => {
    const finalReason = rejectReasonType === 'Khác' ? rejectReasonOther : rejectReasonType;
    if (rejectReasonType === 'Khác' && !rejectReasonOther) {
      showToast({ type: 'error', message: 'Vui lòng nhập chi tiết lý do từ chối (BR08).' });
      return;
    }

    mockStore.updateApplicationStatus(
      application.id,
      'REJECTED',
      hrNote,
      finalReason
    );
    showToast({
      type: 'info',
      title: 'Đã từ chối hồ sơ',
      message: 'Thư cảm ơn đã được gửi tới ứng viên kèm liên kết đồng ý lưu trữ hồ sơ 12 tháng (BR10).',
    });
    setRejectMode(false);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Xét duyệt Hồ sơ: ${application.candidateName} (#APP-${application.id})`}
      subtitle={`Ứng tuyển vị trí: ${application.jobTitle} • ${application.department}`}
      maxWidth="4xl"
    >
      <div className="space-y-6 max-h-[75vh] overflow-y-auto pr-1">
        {/* Top Header Card */}
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-6">
            <div>
              <span className="text-slate-400 block mb-0.5">Ứng viên</span>
              <span className="font-bold text-slate-800 text-sm flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-slate-500" /> {application.candidateName}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Liên hệ</span>
              <span className="font-medium text-slate-700 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-slate-400" /> {application.candidateEmail} &bull;{' '}
                <Phone className="w-3.5 h-3.5 text-slate-400" /> {application.candidatePhone}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Ngày nộp</span>
              <span className="font-medium text-slate-700">
                {new Date(application.submittedAt).toLocaleDateString('vi-VN')}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <span className="text-[11px] text-slate-400 block">Tổng điểm AI</span>
              <span className="text-xl font-extrabold text-emerald-700">{application.aiTotalScore || 0}/100</span>
            </div>
            <StatusBadge status={application.status} />
          </div>
        </div>

        {/* HR Alert / Note */}
        {application.hrNote && (
          <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Ghi chú từ hệ thống / HR:</span>
              <p className="mt-0.5">{application.hrNote}</p>
            </div>
          </div>
        )}

        {/* AI Scoring Breakdown with Quote Evidence (UC1.08 & NFR09) */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-600" />
              Giải trình Điểm AI &amp; Bằng chứng trích dẫn từ CV (NFR09)
            </h3>
            <span className="text-[11px] text-slate-500 font-medium">
              Thuật toán tính điểm theo code hệ thống, không để AI tự tính tổng (BR06)
            </span>
          </div>

          <div className="space-y-3">
            {application.scores && application.scores.length > 0 ? (
              application.scores.map((score: any) => (
                <div key={score.criterionId} className="p-4 bg-white border border-slate-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-slate-900">{score.criterionName}</span>
                      <span className="text-[11px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">
                        Trọng số: {score.weight}%
                      </span>
                      {score.meetsMandatory ? (
                        <span className="text-[10px] bg-teal-50 text-teal-700 px-2 py-0.5 rounded font-semibold border border-teal-200">
                          Đạt tiêu chí bắt buộc
                        </span>
                      ) : (
                        <span className="text-[10px] bg-rose-50 text-rose-700 px-2 py-0.5 rounded font-semibold border border-rose-200">
                          Chưa đạt tiêu chí bắt buộc
                        </span>
                      )}
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-extrabold text-emerald-700">{score.score}/100</span>
                      <span className="text-[10px] text-slate-400 block">
                        Đóng góp: {((score.score * score.weight) / 100).toFixed(1)}đ
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-600 leading-relaxed italic">&ldquo;{score.aiComment}&rdquo;</p>

                  {/* Evidence quote */}
                  <div className="p-2.5 bg-slate-50 border-l-2 border-emerald-500 rounded-r-lg text-[11px] text-slate-700 flex items-start gap-2">
                    <Quote className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-slate-900">Bằng chứng trích xuất từ CV: </span>
                      <span>{score.evidenceQuote}</span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
                Chưa có dữ liệu điểm tiêu chí chi tiết cho hồ sơ này.
              </div>
            )}
          </div>
        </div>

        {/* HR Decision Form */}
        <div className="p-5 bg-slate-50 border border-slate-200 rounded-2xl space-y-4">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">Quyết định xét duyệt của HR:</h4>

          {!rejectMode ? (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex-1 w-full">
                <input
                  type="text"
                  placeholder="Ghi chú nội bộ cho buổi phỏng vấn (tùy chọn)..."
                  value={hrNote}
                  onChange={(e) => setHrNote(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg p-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
                <Button
                  variant="danger"
                  onClick={() => setRejectMode(true)}
                  leftIcon={<XCircle className="w-4 h-4" />}
                >
                  Từ chối hồ sơ
                </Button>
                <Button
                  onClick={handleApproveInvite}
                  leftIcon={<CheckCircle2 className="w-4 h-4" />}
                >
                  Duyệt Đạt &amp; Mời Phỏng vấn (UC1.09)
                </Button>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-900">Lý do từ chối nội bộ (không gửi ứng viên - BR10):</span>
                <button
                  onClick={() => setRejectMode(false)}
                  className="text-xs text-slate-500 hover:text-slate-800 underline cursor-pointer"
                >
                  Hủy từ chối
                </button>
              </div>

              <select
                value={rejectReasonType}
                onChange={(e) => setRejectReasonType(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
              >
                <option value="Kinh nghiệm chuyên môn chưa đáp ứng">Kinh nghiệm chuyên môn chưa đáp ứng</option>
                <option value="Kỹ năng công nghệ chưa phù hợp định hướng">Kỹ năng công nghệ chưa phù hợp định hướng</option>
                <option value="Mức lương kỳ vọng chưa phù hợp">Mức lương kỳ vọng chưa phù hợp</option>
                <option value="Khác">Lý do khác (Nhập chi tiết bên dưới)</option>
              </select>

              {rejectReasonType === 'Khác' && (
                <textarea
                  rows={2}
                  placeholder="Mô tả lý do từ chối (tối đa 500 ký tự)..."
                  value={rejectReasonOther}
                  onChange={(e) => setRejectReasonOther(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
                />
              )}

              <div className="flex justify-end gap-2 pt-1">
                <Button variant="outline" size="sm" onClick={() => setRejectMode(false)}>
                  Hủy
                </Button>
                <Button variant="danger" size="sm" onClick={handleReject}>
                  Xác nhận Từ chối &amp; Gửi Thư Cảm ơn
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};
