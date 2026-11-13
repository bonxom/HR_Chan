import React, { useState, useEffect } from 'react';
import { Plus, AlertCircle, Sliders } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { JobPosting, Criterion } from '../../shared/types/models';
import { Button } from '../../shared/components/ui/Button';
import { StatusBadge } from '../../shared/components/ui/Badge';
import { Modal } from '../../shared/components/ui/Modal';
import { Input, Textarea } from '../../shared/components/ui/Input';
import { showToast } from '../../shared/components/ui/Toast';

export const HrJobManagement: React.FC = () => {
  const [jobs, setJobs] = useState<JobPosting[]>(mockStore.getJobs());
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCriteriaModalOpen, setIsCriteriaModalOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobPosting | null>(null);

  // Job form state
  const [title, setTitle] = useState('');
  const [department, setDepartment] = useState('Engineering');
  const [location, setLocation] = useState('Hà Nội (Hybrid)');
  const [employmentType] = useState<'Full-time' | 'Part-time' | 'Contract' | 'Internship'>('Full-time');
  const [salaryRange, setSalaryRange] = useState('');
  const [headcount, setHeadcount] = useState(1);
  const [deadline, setDeadline] = useState('2026-12-31');
  const [description, setDescription] = useState('');
  const [requirements, setRequirements] = useState('');
  const [benefits, setBenefits] = useState('');
  const [autoThreshold, setAutoThreshold] = useState(80);

  // Criteria Set Editor State
  const [criteriaList, setCriteriaList] = useState<Criterion[]>([
    { id: 1, name: 'Kinh nghiệm chuyên môn', description: 'Có từ 3 năm kinh nghiệm', isMandatory: true, weight: 40 },
    { id: 2, name: 'Cơ sở dữ liệu & Tối ưu hóa', description: 'Nắm vững SQL và quan hệ bảng', isMandatory: true, weight: 30 },
    { id: 3, name: 'Kỹ năng ngoại ngữ', description: 'Đọc hiểu tài liệu chuyên môn', isMandatory: false, weight: 30 },
  ]);

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setJobs(mockStore.getJobs());
    });
    return unsubscribe;
  }, []);

  const totalWeight = criteriaList.reduce((acc, c) => acc + (Number(c.weight) || 0), 0);

  const handleCreateJob = () => {
    if (!title || !description || !requirements) {
      showToast({ type: 'error', message: 'Vui lòng nhập đầy đủ tiêu đề, mô tả và yêu cầu công việc.' });
      return;
    }

    if (totalWeight !== 100) {
      showToast({
        type: 'error',
        message: `Tổng trọng số các tiêu chí phải đúng bằng 100% (Hiện tại: ${totalWeight}%) theo quy tắc BR04.`,
      });
      return;
    }

    mockStore.createJob(
      {
        title,
        department,
        location,
        employmentType,
        salaryRange,
        headcount: Number(headcount),
        deadline,
        description,
        requirements,
        benefits,
        status: 'OPEN',
        autoInviteThreshold: Number(autoThreshold),
      },
      {
        autoInviteThreshold: Number(autoThreshold),
        criteria: criteriaList,
        interviewerIds: [2],
      }
    );

    showToast({
      type: 'success',
      title: 'Tạo tin tuyển dụng thành công',
      message: 'Tin tuyển dụng và bộ tiêu chí phiên bản mới (v1) đã được kích hoạt.',
    });

    setIsCreateModalOpen(false);
    resetForm();
  };

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setRequirements('');
    setBenefits('');
    setHeadcount(1);
    setAutoThreshold(80);
  };

  const handleOpenCriteriaModal = (job: JobPosting) => {
    setSelectedJob(job);
    const existingSet = mockStore.getCriteriaSetForJob(job.id);
    if (existingSet) {
      setCriteriaList(existingSet.criteria);
      setAutoThreshold(existingSet.autoInviteThreshold);
    } else {
      setCriteriaList([
        { id: 1, name: 'Kỹ năng chuyên môn chính', description: 'Kinh nghiệm phù hợp', isMandatory: true, weight: 50 },
        { id: 2, name: 'Khả năng tư duy & giải quyết vấn đề', description: 'Problem solving', isMandatory: false, weight: 50 },
      ]);
      setAutoThreshold(job.autoInviteThreshold || 80);
    }
    setIsCriteriaModalOpen(true);
  };

  const handleSaveCriteria = () => {
    if (!selectedJob) return;
    if (totalWeight !== 100) {
      showToast({
        type: 'error',
        message: `Tổng trọng số các tiêu chí phải đúng bằng 100% (Hiện tại: ${totalWeight}%) theo quy tắc BR04.`,
      });
      return;
    }

    mockStore.saveCriteriaSet(selectedJob.id, criteriaList, Number(autoThreshold), [2]);
    showToast({
      type: 'success',
      title: 'Cập nhật bộ tiêu chí thành công',
      message: 'Phiên bản tiêu chí mới sẽ được áp dụng cho các hồ sơ nộp sau thời điểm này (BR05).',
    });
    setIsCriteriaModalOpen(false);
  };

  const handleCloseJob = (jobId: number) => {
    if (confirm('Bạn có chắc muốn đóng tin tuyển dụng này? Hệ thống sẽ ngừng nhận hồ sơ mới (BR03).')) {
      mockStore.updateJobStatus(jobId, 'CLOSED');
      showToast({ type: 'info', message: 'Tin tuyển dụng đã chuyển sang trạng thái Đã đóng.' });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Quản lý Tin tuyển dụng &amp; Tiêu chí AI</h2>
          <p className="text-xs text-slate-500 mt-1">
            Thiết lập tiêu chí, trọng số, ngưỡng tự động mời và quản lý vòng đời tin đăng (UC1.01 &mdash; UC1.05).
          </p>
        </div>
        <Button onClick={() => setIsCreateModalOpen(true)} leftIcon={<Plus className="w-4 h-4" />}>
          Tạo tin tuyển dụng mới
        </Button>
      </div>

      {/* Jobs Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3.5 px-6">Vị trí &amp; Phòng ban</th>
                <th className="py-3.5 px-4">Trạng thái</th>
                <th className="py-3.5 px-4">Chỉ tiêu</th>
                <th className="py-3.5 px-4">Hạn nộp</th>
                <th className="py-3.5 px-4">Ngưỡng mời AI</th>
                <th className="py-3.5 px-6 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-4 px-6">
                    <div className="font-bold text-slate-900 text-sm">{job.title}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {job.department} &bull; {job.location} &bull; {job.employmentType}
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="py-4 px-4 font-semibold text-slate-800">{job.headcount} nhân sự</td>
                  <td className="py-4 px-4 font-medium">{job.deadline}</td>
                  <td className="py-4 px-4">
                    <span className="font-bold text-emerald-700 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">
                      &ge; {job.autoInviteThreshold}%
                    </span>
                  </td>
                  <td className="py-4 px-6 text-right space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleOpenCriteriaModal(job)}
                      leftIcon={<Sliders className="w-3.5 h-3.5" />}
                    >
                      Bộ tiêu chí AI
                    </Button>
                    {job.status === 'OPEN' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCloseJob(job.id)}
                        className="text-rose-600 hover:bg-rose-50"
                      >
                        Đóng tin
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Job Modal */}
      <Modal isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} title="Đăng tin tuyển dụng mới" maxWidth="2xl">
        <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
          <Input label="Tiêu đề vị trí *" placeholder="Senior Python / FastAPI Engineer" value={title} onChange={(e) => setTitle(e.target.value)} />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">Phòng ban *</label>
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
              >
                <option value="Engineering">Engineering</option>
                <option value="AI Research">AI Research</option>
                <option value="Product Design">Product Design</option>
                <option value="People & Culture">People & Culture</option>
              </select>
            </div>
            <Input label="Địa điểm làm việc *" value={location} onChange={(e) => setLocation(e.target.value)} />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Input label="Số lượng cần tuyển *" type="number" min={1} value={headcount} onChange={(e) => setHeadcount(Number(e.target.value))} />
            <Input label="Hạn nộp hồ sơ *" type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            <Input label="Mức lương" placeholder="35,000,000 - 55,000,000 VND" value={salaryRange} onChange={(e) => setSalaryRange(e.target.value)} />
          </div>

          <Textarea label="Mô tả công việc *" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          <Textarea label="Yêu cầu ứng viên *" rows={3} value={requirements} onChange={(e) => setRequirements(e.target.value)} />
          <Textarea label="Chế độ đãi ngộ & Quyền lợi" rows={2} value={benefits} onChange={(e) => setBenefits(e.target.value)} />

          {/* Quick Criteria Setup in Create Modal */}
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">Cấu hình Ngưỡng &amp; Tiêu chí AI (BR04):</span>
              <span className={`text-xs font-bold ${totalWeight === 100 ? 'text-emerald-700' : 'text-rose-600'}`}>
                Tổng trọng số: {totalWeight}% / 100%
              </span>
            </div>

            <div>
              <label className="block text-xs text-slate-600 mb-1">
                Ngưỡng điểm AI tự động mời phỏng vấn: <strong>{autoThreshold}/100</strong>
              </label>
              <input
                type="range"
                min={50}
                max={95}
                value={autoThreshold}
                onChange={(e) => setAutoThreshold(Number(e.target.value))}
                className="w-full accent-emerald-600"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3">
            <Button variant="outline" onClick={() => setIsCreateModalOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleCreateJob} disabled={totalWeight !== 100}>
              Xuất bản tin tuyển dụng
            </Button>
          </div>
        </div>
      </Modal>

      {/* Criteria Set Editor Modal (UC1.05) */}
      <Modal
        isOpen={isCriteriaModalOpen}
        onClose={() => setIsCriteriaModalOpen(false)}
        title={`Thiết lập Bộ Tiêu chí Chấm điểm AI: ${selectedJob?.title || ''}`}
        maxWidth="2xl"
      >
        <div className="space-y-5">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <span>
              Mỗi lần lưu sẽ tạo một <strong>phiên bản mới (BR05)</strong>, chỉ áp dụng cho các hồ sơ nộp sau đó. Tổng
              trọng số phải bằng 100%. Tiêu chí có cờ bắt buộc nếu trượt sẽ luôn chuyển sang Chờ HR duyệt.
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs">
            <div>
              <span className="text-slate-500">Ngưỡng tự động mời:</span>
              <span className="font-extrabold text-emerald-700 text-sm ml-2">{autoThreshold}/100 điểm</span>
            </div>
            <div className={`font-bold ${totalWeight === 100 ? 'text-emerald-700' : 'text-rose-600'}`}>
              Tổng trọng số hiện tại: {totalWeight}% (Phải = 100%)
            </div>
          </div>

          {/* List of Criteria */}
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {criteriaList.map((crit, index) => (
              <div key={crit.id} className="p-3.5 bg-white border border-slate-200 rounded-xl space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <input
                    type="text"
                    value={crit.name}
                    onChange={(e) => {
                      const newList = [...criteriaList];
                      newList[index].name = e.target.value;
                      setCriteriaList(newList);
                    }}
                    placeholder="Tên tiêu chí"
                    className="font-bold text-xs text-slate-800 border-b border-slate-200 pb-1 flex-1 focus:outline-none focus:border-emerald-500"
                  />
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="text-[11px] text-slate-400">Trọng số:</span>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={crit.weight}
                      onChange={(e) => {
                        const newList = [...criteriaList];
                        newList[index].weight = Number(e.target.value);
                        setCriteriaList(newList);
                      }}
                      className="w-16 text-center text-xs font-bold border border-slate-300 rounded p-1"
                    />
                    <span className="text-xs font-semibold">%</span>
                  </div>
                </div>

                <input
                  type="text"
                  value={crit.description}
                  onChange={(e) => {
                    const newList = [...criteriaList];
                    newList[index].description = e.target.value;
                    setCriteriaList(newList);
                  }}
                  placeholder="Mô tả tiêu chí chi tiết cho AI đánh giá..."
                  className="w-full text-xs text-slate-600 border border-slate-200 rounded p-1.5"
                />

                <div className="flex items-center justify-between pt-1 text-[11px]">
                  <label className="flex items-center gap-1.5 text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={crit.isMandatory}
                      onChange={(e) => {
                        const newList = [...criteriaList];
                        newList[index].isMandatory = e.target.checked;
                        setCriteriaList(newList);
                      }}
                      className="rounded text-emerald-600"
                    />
                    <span>Tiêu chí bắt buộc (Trượt tiêu chí này thì không tự động mời)</span>
                  </label>

                  {criteriaList.length > 1 && (
                    <button
                      onClick={() => setCriteriaList(criteriaList.filter((_, i) => i !== index))}
                      className="text-rose-600 hover:underline cursor-pointer"
                    >
                      Xóa tiêu chí
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              setCriteriaList([
                ...criteriaList,
                { id: Date.now(), name: 'Tiêu chí mới', description: '', isMandatory: false, weight: 10 },
              ])
            }
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            Thêm tiêu chí
          </Button>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsCriteriaModalOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleSaveCriteria} disabled={totalWeight !== 100}>
              Lưu phiên bản tiêu chí mới
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
