import React, { useState } from 'react';
import { Star, CheckCircle2, XCircle, UserX } from 'lucide-react';
import { Modal } from '../../shared/components/ui/Modal';
import { Button } from '../../shared/components/ui/Button';
import { mockStore } from '../../shared/services/mockStore';
import { showToast } from '../../shared/components/ui/Toast';

interface InterviewerEvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
  interview: any | null;
}

export const InterviewerEvaluationModal: React.FC<InterviewerEvaluationModalProps> = ({
  isOpen,
  onClose,
  interview,
}) => {
  const [result, setResult] = useState<'PASSED' | 'FAILED' | 'ABSENT'>('PASSED');
  const [generalFeedback, setGeneralFeedback] = useState('');
  const [ratings, setRatings] = useState<Record<number, number>>({
    1: 4,
    2: 4,
    3: 5,
  });

  if (!interview) return null;

  const handleSubmit = () => {
    if (result !== 'ABSENT' && !generalFeedback) {
      showToast({ type: 'error', message: 'Vui lòng nhập nhận xét đánh giá tổng quan (BR52).' });
      return;
    }

    mockStore.submitInterviewEvaluation(interview.id, result, generalFeedback);
    showToast({
      type: 'success',
      title: 'Đã hoàn tất đánh giá phỏng vấn',
      message: `Kết quả ${result === 'PASSED' ? 'Đạt' : result === 'ABSENT' ? 'Vắng mặt' : 'Không đạt'} đã được lưu và khóa lại theo quy định BR52.`,
    });
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Phiếu Đánh Giá Kết Quả Phỏng Vấn (UC3.08)"
      subtitle={`Ứng viên: ${interview.application?.candidateName || 'N/A'} • ${interview.application?.jobTitle || 'N/A'}`}
      maxWidth="xl"
    >
      <div className="space-y-6">
        {/* Outcome Selector */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
            Kết luận phỏng vấn:
          </label>
          <div className="grid grid-cols-3 gap-3">
            {[
              { val: 'PASSED', label: 'Đạt yêu cầu', icon: CheckCircle2, color: 'text-teal-600 border-teal-500 bg-teal-50/50' },
              { val: 'FAILED', label: 'Không đạt', icon: XCircle, color: 'text-rose-600 border-rose-500 bg-rose-50/50' },
              { val: 'ABSENT', label: 'Ứng viên vắng mặt', icon: UserX, color: 'text-amber-600 border-amber-500 bg-amber-50/50' },
            ].map(({ val, label, icon: Icon, color }) => (
              <button
                key={val}
                type="button"
                onClick={() => setResult(val as any)}
                className={`p-3 rounded-xl border flex flex-col items-center justify-center gap-1.5 transition-all cursor-pointer ${
                  result === val ? color + ' font-bold ring-2 ring-offset-1' : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="text-xs">{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* 1-5 Star Criteria Ratings if not absent */}
        {result !== 'ABSENT' && (
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">Đánh giá theo tiêu chí chuyên môn:</h4>

            {[
              { id: 1, title: 'Kiến thức nền tảng & Chuyên môn kỹ thuật' },
              { id: 2, title: 'Khả năng tư duy logic & Xử lý vấn đề' },
              { id: 3, title: 'Kỹ năng giao tiếp & Thái độ làm việc nhóm' },
            ].map((crit) => (
              <div key={crit.id} className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <span className="text-xs font-medium text-slate-800">{crit.title}</span>
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setRatings({ ...ratings, [crit.id]: star })}
                      className="p-1 text-amber-400 hover:scale-110 transition-transform cursor-pointer"
                    >
                      <Star
                        className={`w-4 h-4 ${
                          (ratings[crit.id] || 0) >= star ? 'fill-amber-400 text-amber-400' : 'text-slate-300'
                        }`}
                      />
                    </button>
                  ))}
                  <span className="text-xs font-bold text-slate-700 ml-1.5">{ratings[crit.id] || 0}/5</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Overall comments */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
            Nhận xét chi tiết của người phỏng vấn *
          </label>
          <textarea
            rows={3}
            value={generalFeedback}
            onChange={(e) => setGeneralFeedback(e.target.value)}
            placeholder="Nêu nhận định về điểm mạnh, hạn chế cần cải thiện và tiềm năng phát triển của ứng viên..."
            className="w-full bg-white border border-slate-300 rounded-xl p-3 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
          <Button variant="outline" onClick={onClose}>
            Hủy
          </Button>
          <Button onClick={handleSubmit}>
            Lưu &amp; Khóa kết quả phỏng vấn (BR52)
          </Button>
        </div>
      </div>
    </Modal>
  );
};

