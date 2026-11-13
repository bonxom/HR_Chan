import React, { useState, useEffect } from 'react';
import { Plus, CheckSquare, Clock, CheckCircle2, XCircle, AlertCircle, Award } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { StatusBadge } from '../../shared/components/ui/Badge';
import { Modal } from '../../shared/components/ui/Modal';
import { Input, Textarea } from '../../shared/components/ui/Input';
import { showToast } from '../../shared/components/ui/Toast';

export const ManagerProbationDashboard: React.FC = () => {
  const [probations, setProbations] = useState<any[]>(mockStore.getProbations());
  const [selectedProbation] = useState<any | null>(null);

  // Modals
  const [isAssignTaskOpen, setIsAssignTaskOpen] = useState(false);
  const [isGradeTaskOpen, setIsGradeTaskOpen] = useState(false);
  const [isConclusionOpen, setIsConclusionOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<any | null>(null);

  // Form states
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [taskDueAt, setTaskDueAt] = useState('2026-11-25T17:00');

  const [gradeResult, setGradeResult] = useState<'PASSED' | 'FAILED'>('PASSED');
  const [gradeFeedback, setGradeFeedback] = useState('');

  const [conclusionResult, setConclusionResult] = useState<'PASSED' | 'FAILED'>('PASSED');
  const [conclusionNote, setConclusionNote] = useState('');

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setProbations(mockStore.getProbations());
    });
    return unsubscribe;
  }, []);

  const activeProbation = selectedProbation || probations[0];

  const handleAssignTask = () => {
    if (!taskTitle || !taskDueAt) {
      showToast({ type: 'error', message: 'Vui lòng nhập tiêu đề task và hạn nộp (BR57).' });
      return;
    }

    mockStore.createProbationTask(activeProbation.id, {
      title: taskTitle,
      description: taskDesc,
      dueAt: taskDueAt,
    });

    showToast({
      type: 'success',
      title: 'Đã giao task thử việc',
      message: 'Email thông báo kèm mô tả task đã được gửi tự động tới nhân viên thử việc.',
    });

    setIsAssignTaskOpen(false);
    setTaskTitle('');
    setTaskDesc('');
  };

  const handleGradeTask = () => {
    if (!selectedTask) return;
    if (gradeResult === 'FAILED' && !gradeFeedback) {
      showToast({ type: 'error', message: 'Trường hợp Không đạt bắt buộc phải có nhận xét chi tiết (BR59).' });
      return;
    }

    mockStore.gradeTask(selectedTask.id, gradeResult, gradeFeedback);
    showToast({
      type: 'success',
      title: 'Đã hoàn tất đánh giá task',
      message: 'Kết quả đánh giá và bài nộp đã được khóa theo quy định BR58.',
    });

    setIsGradeTaskOpen(false);
  };

  const handleConcludeProbation = () => {
    if (!conclusionNote) {
      showToast({ type: 'error', message: 'Vui lòng nhập nhận xét kết luận thử việc (BR61).' });
      return;
    }

    mockStore.concludeProbation(activeProbation.id, conclusionResult, conclusionNote);
    showToast({
      type: 'success',
      title: 'Đã ban hành kết luận thử việc',
      message: `Đợt thử việc kết luận: ${conclusionResult === 'PASSED' ? 'Đạt' : 'Không đạt'}. Kết quả chuyển sang Admin xử lý tài khoản (BR44).`,
    });

    setIsConclusionOpen(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Quản lý Đợt Thử việc &amp; Giao Việc (Manager)</h2>
          <p className="text-xs text-slate-500 mt-1">
            Giao task, đánh giá bài nộp và kết luận đợt thử việc theo quy định luật lao động (UC4.01 &mdash; UC4.07).
          </p>
        </div>

        {activeProbation && activeProbation.status === 'ONGOING' && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsAssignTaskOpen(true)}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              Giao task mới
            </Button>
            <Button
              size="sm"
              onClick={() => setIsConclusionOpen(true)}
              leftIcon={<Award className="w-3.5 h-3.5" />}
            >
              Kết luận thử việc (BR60)
            </Button>
          </div>
        )}
      </div>

      {activeProbation ? (
        <div className="space-y-6">
          {/* Active Probation Overview Banner */}
          <Card className="p-6 bg-gradient-to-r from-slate-900 to-slate-800 text-white border-slate-700">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                  Đợt thử việc #{activeProbation.id} &bull; {activeProbation.application?.jobTitle}
                </span>
                <h3 className="text-xl font-extrabold text-white mt-1">{activeProbation.traineeName}</h3>
                <p className="text-xs text-slate-300 mt-1">
                  Email công ty: <strong className="text-emerald-300">{activeProbation.traineeEmail}</strong> &bull; Quản lý:{' '}
                  {activeProbation.managerName}
                </p>
              </div>

              <div className="flex items-center gap-6 text-xs bg-slate-800/80 p-4 rounded-xl border border-slate-700">
                <div>
                  <span className="text-slate-400 block mb-0.5">Thời gian thử việc</span>
                  <span className="font-semibold text-white">
                    {activeProbation.startDate} &mdash; {activeProbation.endDate}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Trạng thái đợt</span>
                  <StatusBadge status={activeProbation.status} />
                </div>
              </div>
            </div>
          </Card>

          {/* Tasks List */}
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-3 flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-emerald-600" />
              Danh sách nhiệm vụ thử việc được giao:
            </h3>

            <div className="space-y-3">
              {activeProbation.tasks.map((task: any) => (
                <Card key={task.id} className="p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 text-sm">{task.title}</span>
                      {task.result ? (
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                            task.result === 'PASSED'
                              ? 'bg-teal-50 text-teal-700 border-teal-200'
                              : 'bg-rose-50 text-rose-700 border-rose-200'
                          }`}
                        >
                          {task.result === 'PASSED' ? 'Đạt' : 'Không đạt'}
                        </span>
                      ) : task.submission ? (
                        <span className="text-[10px] font-bold bg-amber-50 text-amber-700 px-2 py-0.5 rounded border border-amber-200">
                          Đã nộp bài &mdash; Chờ đánh giá
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                          Chưa nộp bài
                        </span>
                      )}
                      {task.submission?.isLate && (
                        <span className="text-[10px] font-bold bg-rose-50 text-rose-600 px-1.5 py-0.5 rounded border border-rose-200">
                          Nộp muộn (BR62)
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">{task.description}</p>

                    <div className="flex items-center gap-4 text-[11px] text-slate-500 pt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-slate-400" /> Hạn nộp: {new Date(task.dueAt).toLocaleString('vi-VN')}
                      </span>
                      {task.submission && (
                        <span className="text-slate-700 font-medium">
                          Bài nộp:{' '}
                          <a
                            href={task.submission.content}
                            target="_blank"
                            rel="noreferrer"
                            className="text-emerald-700 underline font-semibold"
                          >
                            {task.submission.content}
                          </a>
                        </span>
                      )}
                    </div>

                    {task.feedback && (
                      <div className="p-2.5 bg-slate-50 border-l-2 border-slate-400 rounded-r-lg text-xs text-slate-700 mt-2">
                        <strong>Nhận xét của Quản lý: </strong>
                        <span>{task.feedback}</span>
                      </div>
                    )}
                  </div>

                  <div className="shrink-0">
                    {task.submission && !task.result && (
                      <Button
                        size="sm"
                        onClick={() => {
                          setSelectedTask(task);
                          setIsGradeTaskOpen(true);
                        }}
                      >
                        Đánh giá bài nộp (UC4.05)
                      </Button>
                    )}
                  </div>
                </Card>
              ))}

              {activeProbation.tasks.length === 0 && (
                <div className="p-10 text-center bg-white rounded-2xl border border-dashed border-slate-300">
                  <CheckSquare className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <h4 className="text-sm font-bold text-slate-700">Chưa có task nào được giao</h4>
                  <p className="text-xs text-slate-400 mt-1">Bấm nút "Giao task mới" ở trên để bắt đầu giao nhiệm vụ.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-slate-300">
          <p className="text-sm text-slate-500">Chưa có đợt thử việc nào thuộc trách nhiệm quản lý của bạn.</p>
        </div>
      )}

      {/* Assign Task Modal (UC4.02) */}
      <Modal isOpen={isAssignTaskOpen} onClose={() => setIsAssignTaskOpen(false)} title="Giao task thử việc mới (UC4.02)">
        <div className="space-y-4">
          <Input
            label="Tiêu đề task (tối đa 200 ký tự - BR57) *"
            placeholder="Ví dụ: Triển khai kiểm thử Unit test cho module Jobs"
            value={taskTitle}
            onChange={(e) => setTaskTitle(e.target.value)}
          />
          <Textarea
            label="Mô tả yêu cầu công việc chi tiết *"
            rows={4}
            placeholder="Nêu rõ mục tiêu công việc, tiêu chí nghiệm thu và tài liệu tham khảo..."
            value={taskDesc}
            onChange={(e) => setTaskDesc(e.target.value)}
          />
          <Input
            label="Hạn nộp bài làm (Không ở quá khứ & không sau ngày kết thúc thử việc - BR57) *"
            type="datetime-local"
            value={taskDueAt}
            onChange={(e) => setTaskDueAt(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsAssignTaskOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleAssignTask}>Giao task cho nhân viên</Button>
          </div>
        </div>
      </Modal>

      {/* Grade Task Modal (UC4.05) */}
      <Modal
        isOpen={isGradeTaskOpen}
        onClose={() => setIsGradeTaskOpen(false)}
        title="Đánh giá bài nộp của nhân viên (UC4.05)"
        subtitle={`Task: ${selectedTask?.title || ''}`}
      >
        <div className="space-y-4">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1">
            <span className="text-slate-400 block">Liên kết bài nộp / Tệp:</span>
            <a
              href={selectedTask?.submission?.content}
              target="_blank"
              rel="noreferrer"
              className="font-bold text-emerald-700 underline break-all"
            >
              {selectedTask?.submission?.content}
            </a>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              Kết quả đánh giá (BR59):
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setGradeResult('PASSED')}
                className={`p-3 rounded-xl border flex items-center justify-center gap-2 cursor-pointer font-bold text-xs transition-all ${
                  gradeResult === 'PASSED'
                    ? 'border-teal-500 bg-teal-50 text-teal-800 ring-2 ring-teal-500'
                    : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                <span>Đạt yêu cầu (Passed)</span>
              </button>
              <button
                type="button"
                onClick={() => setGradeResult('FAILED')}
                className={`p-3 rounded-xl border flex items-center justify-center gap-2 cursor-pointer font-bold text-xs transition-all ${
                  gradeResult === 'FAILED'
                    ? 'border-rose-500 bg-rose-50 text-rose-800 ring-2 ring-rose-500'
                    : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                <XCircle className="w-4 h-4 text-rose-600" />
                <span>Không đạt (Failed)</span>
              </button>
            </div>
          </div>

          <Textarea
            label={`Nhận xét của Quản lý ${gradeResult === 'FAILED' ? '(Bắt buộc khi Không đạt - BR59) *' : ''}`}
            rows={3}
            value={gradeFeedback}
            onChange={(e) => setGradeFeedback(e.target.value)}
            placeholder="Ghi nhận xét và góp ý hoàn thiện..."
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsGradeTaskOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleGradeTask}>Lưu &amp; Khóa kết quả đánh giá (BR58)</Button>
          </div>
        </div>
      </Modal>

      {/* Conclude Probation Modal (UC4.07 & BR60-BR61) */}
      <Modal
        isOpen={isConclusionOpen}
        onClose={() => setIsConclusionOpen(false)}
        title="Ban hành Kết luận Thử việc (UC4.07)"
        subtitle="Sau khi lưu, kết luận không thể chỉnh sửa và mọi task sẽ bị khóa (BR61)"
      >
        <div className="space-y-4">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <span>
              Quản lý được kết luận trong <strong>5 ngày làm việc</strong> trước ngày kết thúc thử việc (BR60). Nếu Đạt,
              hồ sơ chuyển sang Admin để gán vai trò nhân viên chính thức. Nếu Không đạt, tài khoản nhân viên sẽ tự động khóa sau ngày kết thúc.
            </span>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              Kết luận chính thức:
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setConclusionResult('PASSED')}
                className={`p-3 rounded-xl border flex items-center justify-center gap-2 cursor-pointer font-bold text-xs transition-all ${
                  conclusionResult === 'PASSED'
                    ? 'border-teal-500 bg-teal-50 text-teal-800 ring-2 ring-teal-500'
                    : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                <span>Đạt thử việc (Pass)</span>
              </button>
              <button
                type="button"
                onClick={() => setConclusionResult('FAILED')}
                className={`p-3 rounded-xl border flex items-center justify-center gap-2 cursor-pointer font-bold text-xs transition-all ${
                  conclusionResult === 'FAILED'
                    ? 'border-rose-500 bg-rose-50 text-rose-800 ring-2 ring-rose-500'
                    : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                <XCircle className="w-4 h-4 text-rose-600" />
                <span>Không đạt (Fail)</span>
              </button>
            </div>
          </div>

          <Textarea
            label="Nhận xét tổng kết đợt thử việc (Bắt buộc - BR61) *"
            rows={4}
            value={conclusionNote}
            onChange={(e) => setConclusionNote(e.target.value)}
            placeholder="Tổng kết năng lực, sự chủ động và khả năng hòa nhập văn hóa doanh nghiệp..."
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsConclusionOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleConcludeProbation}>
              Lưu &amp; Ban hành Kết luận Thử việc
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
