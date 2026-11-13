import React, { useState, useEffect } from 'react';
import { CheckSquare, Clock, Send } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Modal } from '../../shared/components/ui/Modal';
import { Input } from '../../shared/components/ui/Input';
import { showToast } from '../../shared/components/ui/Toast';

export const TraineeDashboard: React.FC = () => {
  const [tasks, setTasks] = useState<any[]>(mockStore.getTasksForProbation(1));
  const [selectedTask, setSelectedTask] = useState<any | null>(null);
  const [isSubmitOpen, setIsSubmitOpen] = useState(false);
  const [submissionContent, setSubmissionContent] = useState('');

  useEffect(() => {
    const update = () => {
      setTasks(mockStore.getTasksForProbation(1));
    };
    return mockStore.subscribe(update);
  }, []);

  const handleOpenSubmit = (task: any) => {
    setSelectedTask(task);
    setSubmissionContent(task.submission?.content || '');
    setIsSubmitOpen(true);
  };

  const handleSubmitTask = () => {
    if (!submissionContent) {
      showToast({ type: 'error', message: 'Vui lòng cung cấp đường dẫn bài nộp (HTTPS link) hoặc tên tài liệu (BR62).' });
      return;
    }

    mockStore.submitTaskDeliverable(selectedTask.id, submissionContent);
    showToast({
      type: 'success',
      title: 'Đã nộp bài thành công (UC4.09)',
      message: 'Email thông báo bài nộp mới đã được gửi tự động tới Quản lý phụ trách.',
    });

    setIsSubmitOpen(false);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-slate-900">Nhiệm Vụ Thử Việc Của Tôi (Trainee Workspace)</h2>
        <p className="text-xs text-slate-500 mt-1">
          Theo dõi hạn nộp, gửi bài làm và xem phản hồi đánh giá trực tiếp từ quản lý (UC4.08 &mdash; UC4.10).
        </p>
      </div>

      <div className="space-y-4">
        {tasks.map((task) => (
          <Card key={task.id} className="p-6 space-y-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
              <h3 className="text-base font-bold text-slate-900">{task.title}</h3>
              {task.result ? (
                <span
                  className={`text-xs font-bold px-3 py-1 rounded-full border ${
                    task.result === 'PASSED'
                      ? 'bg-teal-50 text-teal-700 border-teal-200'
                      : 'bg-rose-50 text-rose-700 border-rose-200'
                  }`}
                >
                  Kết quả: {task.result === 'PASSED' ? 'Đạt' : 'Không đạt'}
                </span>
              ) : task.submission ? (
                <span className="text-xs font-bold bg-amber-50 text-amber-700 px-3 py-1 rounded-full border border-amber-200">
                  Đã nộp bài &mdash; Đang chờ quản lý chấm
                </span>
              ) : (
                <span className="text-xs font-bold bg-slate-100 text-slate-600 px-3 py-1 rounded-full">
                  Chưa nộp bài
                </span>
              )}
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">{task.description}</p>

            <div className="flex items-center gap-4 text-xs text-slate-500 pt-2 border-t border-slate-100">
              <span className="flex items-center gap-1.5 font-medium text-slate-700">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                Hạn nộp: {new Date(task.dueAt).toLocaleString('vi-VN')}
              </span>
              {task.submission && (
                <span className="text-slate-600">
                  Đã nộp: <strong className="text-emerald-700">{task.submission.content}</strong>{' '}
                  {task.submission.isLate && <span className="text-rose-600 font-bold">(Nộp muộn)</span>}
                </span>
              )}
            </div>

            {task.feedback && (
              <div className="p-3 bg-slate-50 border-l-2 border-slate-400 rounded-r-lg text-xs text-slate-700 mt-2">
                <span className="font-bold text-slate-900">Phản hồi của Quản lý: </span>
                <span>{task.feedback}</span>
              </div>
            )}

            {!task.result && (
              <div className="pt-2 flex justify-end">
                <Button
                  size="sm"
                  onClick={() => handleOpenSubmit(task)}
                  leftIcon={<Send className="w-3.5 h-3.5" />}
                >
                  {task.submission ? 'Cập nhật lại bài nộp (UC4.10)' : 'Nộp bài làm (UC4.09)'}
                </Button>
              </div>
            )}
          </Card>
        ))}

        {tasks.length === 0 && (
          <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-slate-300">
            <CheckSquare className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-700">Bạn chưa có task nào</h4>
            <p className="text-xs text-slate-400 mt-1">Khi quản lý giao việc, thông báo và mô tả task sẽ xuất hiện tại đây.</p>
          </div>
        )}
      </div>

      {/* Submit Deliverable Modal (UC4.09 & UC4.10) */}
      <Modal
        isOpen={isSubmitOpen}
        onClose={() => setIsSubmitOpen(false)}
        title="Nộp bài làm thử việc (UC4.09 / UC4.10)"
        subtitle={`Task: ${selectedTask?.title || ''}`}
      >
        <div className="space-y-4">
          <Input
            label="Đường dẫn bài nộp (Link GitHub PR, Google Drive, tài liệu HTTPS) *"
            placeholder="https://github.com/company/project/pull/123"
            value={submissionContent}
            onChange={(e) => setSubmissionContent(e.target.value)}
          />

          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-[11px] text-slate-500 space-y-1">
            <p>&bull; Bài nộp được quản lý nhận và đánh giá một lần duy nhất (BR59).</p>
            <p>&bull; Bạn có thể cập nhật lại bài nộp trước khi quản lý tiến hành đánh giá (UC4.10).</p>
            <p>&bull; Nộp sau hạn quy định sẽ được tự động gắn nhãn "Nộp muộn" (BR62).</p>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsSubmitOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleSubmitTask}>
              Xác nhận nộp bài
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
