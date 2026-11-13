import React, { useState } from 'react';
import { UploadCloud, CheckCircle2, Sparkles, FileText, ArrowRight } from 'lucide-react';
import { Modal } from '../../shared/components/ui/Modal';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { JobPosting } from '../../shared/types/models';
import { mockStore } from '../../shared/services/mockStore';
import { OtpModal } from './OtpModal';
import { showToast } from '../../shared/components/ui/Toast';

interface ApplyModalProps {
  isOpen: boolean;
  onClose: () => void;
  preselectedJob?: JobPosting | null;
}

export const ApplyModal: React.FC<ApplyModalProps> = ({ isOpen, onClose, preselectedJob }) => {
  const [step, setStep] = useState<'FORM' | 'AI_MATCHING' | 'SUCCESS'>('FORM');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [isParsing, setIsParsing] = useState(false);

  // Selected job for submission
  const [selectedJob, setSelectedJob] = useState<JobPosting | null>(preselectedJob || null);
  const [isOtpOpen, setIsOtpOpen] = useState(false);
  const [createdApplication, setCreatedApplication] = useState<any>(null);

  // Simulated AI parse output
  const [aiParsedData, setAiParsedData] = useState<any>(null);
  const [suggestedJobs, setSuggestedJobs] = useState<any[]>([]);

  // Update selected job if preselected changes
  React.useEffect(() => {
    if (preselectedJob) setSelectedJob(preselectedJob);
  }, [preselectedJob]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    // Check extension & size (BR14: <= 5MB)
    const validExts = ['.pdf', '.docx'];
    const hasValidExt = validExts.some((ext) => selected.name.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
      setFileError('File phải có định dạng .pdf hoặc .docx theo quy chuẩn BR14.');
      setFile(null);
      return;
    }

    if (selected.size > 5 * 1024 * 1024) {
      setFileError('Dung lượng file tối đa là 5MB theo quy định BR14.');
      setFile(null);
      return;
    }

    setFileError('');
    setFile(selected);
  };

  const handleProceedToAI = () => {
    if (!fullName || !email || !phone) {
      showToast({ type: 'error', message: 'Vui lòng điền đầy đủ Họ tên, Email và Số điện thoại.' });
      return;
    }

    if (!/^\d{10}$/.test(phone.replace(/\s+/g, ''))) {
      showToast({ type: 'error', message: 'Số điện thoại phải bao gồm đúng 10 chữ số theo quy định BR15.' });
      return;
    }

    if (!consent) {
      showToast({ type: 'error', message: 'Vui lòng xác nhận đồng ý xử lý dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP.' });
      return;
    }

    if (!file) {
      showToast({ type: 'error', message: 'Vui lòng tải lên file CV (PDF hoặc DOCX).' });
      return;
    }

    setIsParsing(true);

    // Simulate AI parsing and semantic job matching
    setTimeout(() => {
      setIsParsing(false);
      const openJobs = mockStore.getJobs('OPEN');

      const parsed = {
        skills: ['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'React', 'RESTful API', 'Git'],
        experience: '4 năm kinh nghiệm phát triển hệ thống backend, kiến trúc microservices và tích hợp AI.',
        education: 'Kỹ sư Công nghệ Thông tin - Đại học Bách Khoa Hà Nội',
      };

      const suggestions = openJobs.map((j) => {
        const isSelected = selectedJob?.id === j.id;
        const match = isSelected ? 92 : Math.floor(Math.random() * 25) + 70;
        return {
          job: j,
          score: match,
          reason: `Kỹ năng trích xuất (${parsed.skills.slice(0, 4).join(', ')}) khớp cao với yêu cầu của vị trí này.`,
        };
      });

      // Sort descending by match score
      suggestions.sort((a, b) => b.score - a.score);

      setAiParsedData(parsed);
      setSuggestedJobs(suggestions);
      if (!selectedJob && suggestions.length > 0) {
        setSelectedJob(suggestions[0].job);
      }
      setStep('AI_MATCHING');
    }, 1200);
  };

  const handleConfirmAndOtp = () => {
    if (!selectedJob) {
      showToast({ type: 'error', message: 'Vui lòng chọn một vị trí ứng tuyển.' });
      return;
    }
    setIsOtpOpen(true);
  };

  const handleOtpSuccess = () => {
    setIsOtpOpen(false);
    if (!selectedJob) return;

    const app = mockStore.submitApplication(
      {
        fullName,
        email,
        phone,
      },
      selectedJob.id
    );

    setCreatedApplication(app);
    setStep('SUCCESS');
  };

  const resetAll = () => {
    setStep('FORM');
    setFullName('');
    setEmail('');
    setPhone('');
    setConsent(false);
    setFile(null);
    setFileError('');
    setSelectedJob(null);
    setCreatedApplication(null);
    onClose();
  };

  return (
    <>
      <Modal isOpen={isOpen} onClose={resetAll} title="Nộp hồ sơ ứng tuyển & Phân tích AI" maxWidth="2xl">
        {step === 'FORM' && (
          <div className="space-y-6">
            <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-xl flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div className="text-xs text-emerald-800 leading-relaxed">
                Hệ thống sử dụng mô hình AI trích xuất nội dung tự động từ CV của bạn và gợi ý vị trí phù hợp nhất. Mọi dữ liệu đều được bảo vệ nghiêm ngặt.
              </div>
            </div>

            {/* Target Job Indicator if preselected */}
            {selectedJob && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between text-xs">
                <div>
                  <span className="text-slate-500">Vị trí ứng tuyển mục tiêu:</span>
                  <div className="font-bold text-slate-800 text-sm mt-0.5">{selectedJob.title}</div>
                </div>
                <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-100/70 px-2 py-1 rounded">
                  {selectedJob.department}
                </span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Họ và tên *"
                placeholder="Ví dụ: Nguyễn Văn A"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
              <Input
                label="Địa chỉ Email *"
                type="email"
                placeholder="email@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <Input
              label="Số điện thoại di động (10 chữ số) *"
              placeholder="0987654321"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />

            {/* CV File Upload Dropzone */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
                Tệp CV / Sơ yếu lý lịch (.pdf, .docx, tối đa 5MB) *
              </label>
              <div className="border-2 border-dashed border-slate-300 hover:border-emerald-500 rounded-2xl p-6 text-center bg-slate-50/50 hover:bg-emerald-50/20 transition-all cursor-pointer relative">
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <UploadCloud className="w-10 h-10 text-emerald-600 mx-auto mb-2" />
                {file ? (
                  <div className="space-y-1">
                    <span className="text-sm font-bold text-emerald-700 flex items-center justify-center gap-1.5">
                      <FileText className="w-4 h-4" /> {file.name}
                    </span>
                    <p className="text-[11px] text-slate-500">
                      Dung lượng: {(file.size / (1024 * 1024)).toFixed(2)} MB &mdash; Sẵn sàng phân tích
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-slate-700">Kéo thả file CV vào đây hoặc bấm để chọn tệp</p>
                    <p className="text-[11px] text-slate-400">Định dạng hỗ trợ: PDF, DOCX (Tối đa 5MB)</p>
                  </div>
                )}
              </div>
              {fileError && <p className="mt-1.5 text-xs text-rose-600 font-medium">{fileError}</p>}
            </div>

            {/* Decree 13/2023 Consent Checkbox */}
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 space-y-2">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-0.5 rounded text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                />
                <span className="leading-relaxed">
                  Tôi đồng ý cho công ty thu thập và xử lý dữ liệu cá nhân trong hồ sơ phục vụ mục đích tuyển dụng theo{' '}
                  <strong className="text-slate-800">Nghị định 13/2023/NĐ-CP</strong> về bảo vệ dữ liệu cá nhân.
                </span>
              </label>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={resetAll}>
                Hủy bỏ
              </Button>
              <Button onClick={handleProceedToAI} isLoading={isParsing} rightIcon={<ArrowRight className="w-4 h-4" />}>
                Phân tích CV &amp; Gợi ý vị trí
              </Button>
            </div>
          </div>
        )}

        {step === 'AI_MATCHING' && (
          <div className="space-y-6">
            {/* AI Extracted Profile Highlights */}
            <div className="bg-slate-900 text-white rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4" /> Hồ sơ trích xuất tự động bởi AI (UC2.02)
                </span>
                <span className="text-[10px] text-slate-400">{fullName}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 block mb-1">Học vấn trích xuất:</span>
                  <p className="font-medium text-slate-200">{aiParsedData?.education}</p>
                </div>
                <div>
                  <span className="text-slate-400 block mb-1">Kinh nghiệm nổi bật:</span>
                  <p className="font-medium text-slate-200">{aiParsedData?.experience}</p>
                </div>
              </div>
              <div>
                <span className="text-slate-400 text-xs block mb-1.5">Kỹ năng nhận diện:</span>
                <div className="flex flex-wrap gap-1.5">
                  {aiParsedData?.skills.map((skill: string) => (
                    <span
                      key={skill}
                      className="bg-slate-800 text-emerald-300 border border-slate-700 text-[11px] px-2 py-0.5 rounded-md"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* AI Match Ranking */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
                Các vị trí phù hợp nhất (Gợi ý tối đa 5 vị trí - BR18):
              </h4>
              <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                {suggestedJobs.map(({ job, score, reason }) => {
                  const isChecked = selectedJob?.id === job.id;
                  return (
                    <div
                      key={job.id}
                      onClick={() => setSelectedJob(job)}
                      className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start justify-between gap-4 ${
                        isChecked
                          ? 'border-emerald-500 bg-emerald-50/60 shadow-xs ring-1 ring-emerald-500'
                          : 'border-slate-200 hover:border-slate-300 bg-white'
                      }`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-bold text-slate-900 text-sm">{job.title}</span>
                          <span className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                            {job.department}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 leading-relaxed">{reason}</p>
                      </div>

                      <div className="text-right shrink-0">
                        <div className="text-base font-extrabold text-emerald-700">{score}%</div>
                        <div className="text-[10px] text-slate-400 font-medium">Độ tương thích</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="flex justify-between items-center pt-2">
              <Button variant="outline" size="sm" onClick={() => setStep('FORM')}>
                Quay lại sửa thông tin
              </Button>
              <Button onClick={handleConfirmAndOtp} rightIcon={<ArrowRight className="w-4 h-4" />}>
                Xác thực OTP &amp; Nộp vị trí đã chọn
              </Button>
            </div>
          </div>
        )}

        {step === 'SUCCESS' && createdApplication && (
          <div className="text-center py-6 space-y-5">
            <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-md">
              <CheckCircle2 className="w-10 h-10" />
            </div>

            <div>
              <h3 className="text-xl font-bold text-slate-900">Ứng tuyển thành công!</h3>
              <p className="text-xs text-slate-600 mt-1 max-w-md mx-auto leading-relaxed">
                Cảm ơn bạn đã ứng tuyển vào vị trí <strong className="text-slate-800">{selectedJob?.title}</strong>.
              </p>
            </div>

            <div className="p-5 bg-slate-50 border border-slate-200 rounded-2xl max-w-md mx-auto text-left text-xs space-y-2">
              <div className="flex justify-between py-1 border-b border-slate-200/60">
                <span className="text-slate-500">Mã hồ sơ:</span>
                <span className="font-mono font-bold text-slate-800">#APP-{createdApplication.id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60">
                <span className="text-slate-500">Điểm đánh giá AI:</span>
                <span className="font-bold text-emerald-700">{createdApplication.aiTotalScore}/100</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Trạng thái xử lý:</span>
                <span className="font-semibold text-slate-800">
                  {createdApplication.status === 'INTERVIEW_INVITED'
                    ? '🎉 Đạt ngưỡng AI -> Đã gửi lời mời phỏng vấn'
                    : '⏳ Đang chờ HR xét duyệt (tối đa 5 ngày làm việc)'}
                </span>
              </div>
            </div>

            <Button onClick={resetAll} className="w-full max-w-xs mx-auto">
              Hoàn tất &amp; Quay lại trang chủ
            </Button>
          </div>
        )}
      </Modal>

      {/* OTP Modal */}
      <OtpModal
        isOpen={isOtpOpen}
        onClose={() => setIsOtpOpen(false)}
        email={email}
        onSuccess={handleOtpSuccess}
      />
    </>
  );
};
