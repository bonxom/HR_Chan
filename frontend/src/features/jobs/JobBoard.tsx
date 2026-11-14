import React, { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { Search, MapPin, Building, Calendar, Sparkles, UploadCloud, Users, ArrowUpRight } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { JobPosting } from '../../shared/types/models';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { ApplyModal } from '../candidates/ApplyModal';

export const JobBoard: React.FC = () => {
  const [jobs, setJobs] = useState<JobPosting[]>(mockStore.getJobs('OPEN'));
  const [search, setSearch] = useState('');
  const [selectedDept, setSelectedDept] = useState('ALL');
  const [selectedJobForApply, setSelectedJobForApply] = useState<JobPosting | null>(null);
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setJobs(mockStore.getJobs('OPEN'));
    });
    return unsubscribe;
  }, []);

  const departments = ['ALL', ...Array.from(new Set(jobs.map((j) => j.department)))];

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.title.toLowerCase().includes(search.toLowerCase()) ||
      job.description.toLowerCase().includes(search.toLowerCase()) ||
      job.requirements.toLowerCase().includes(search.toLowerCase());
    const matchesDept = selectedDept === 'ALL' || job.department === selectedDept;
    return matchesSearch && matchesDept;
  });

  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-b from-emerald-950 via-slate-900 to-slate-900 text-white py-20 px-4 sm:px-6 lg:px-8 border-b border-slate-800">
        <div className="max-w-5xl mx-auto text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>AI Semantic Matching &amp; Fast-Track Interview</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Gia nhập Đội ngũ Tiên phong <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-200">
              Kiến tạo Công nghệ Doanh nghiệp
            </span>
          </h1>

          <p className="text-slate-300 text-sm sm:text-base max-w-2xl mx-auto font-normal leading-relaxed">
            Hệ thống tuyển dụng thông minh phân tích hồ sơ chuẩn hóa, so khớp vị trí phù hợp tức thì và tự động điều phối lịch phỏng vấn linh hoạt.
          </p>

          {/* Quick AI CV Matching Banner Action */}
          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              size="lg"
              onClick={() => {
                setSelectedJobForApply(null);
                setIsApplyModalOpen(true);
              }}
              leftIcon={<UploadCloud className="w-5 h-5" />}
              className="w-full sm:w-auto shadow-lg shadow-emerald-900/40"
            >
              Tải CV để AI Gợi ý Việc làm
            </Button>
            <a
              href="#jobs-list"
              className="w-full sm:w-auto text-xs font-medium text-slate-300 hover:text-white px-5 py-3 rounded-lg border border-slate-700/80 hover:bg-slate-800/80 transition-all text-center"
            >
              Khám phá tất cả vị trí ({jobs.length})
            </a>
          </div>
        </div>
      </section>

      {/* Main Filter & Job List Section */}
      <div id="jobs-list" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Search & Department Filters */}
        <div className="bg-white rounded-2xl shadow-xs border border-slate-200 p-6 mb-8 flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Tìm kiếm theo vị trí, kỹ năng, công nghệ..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all"
            />
          </div>

          <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
            {departments.map((dept) => (
              <button
                key={dept}
                onClick={() => setSelectedDept(dept)}
                className={`px-3.5 py-2 text-xs font-semibold rounded-xl whitespace-nowrap transition-all cursor-pointer ${
                  selectedDept === dept
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {dept === 'ALL' ? 'Tất cả phòng ban' : dept}
              </button>
            ))}
          </div>
        </div>

        {/* Jobs Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredJobs.map((job) => (
            <Card key={job.id} hoverEffect className="flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded-md">
                    {job.department}
                  </span>
                  <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                    {job.employmentType}
                  </span>
                </div>

                <h3 className="text-lg font-bold text-slate-900 group-hover:text-emerald-700 transition-colors mb-2">
                  {job.title}
                </h3>

                <p className="text-slate-600 text-xs line-clamp-3 mb-4 leading-relaxed">{job.description}</p>

                <div className="space-y-2 text-xs text-slate-500 mb-6">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span>{job.location}</span>
                  </div>
                  {job.salaryRange && (
                    <div className="flex items-center gap-2 font-semibold text-emerald-700">
                      <span>💰 {job.salaryRange}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-4 pt-1 text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <Users className="w-3 h-3" /> Tuyển {job.headcount} nhân sự
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" /> Hạn: {job.deadline}
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-3">
                <Link
                  to={`/jobs/${job.id}`}
                  className="text-xs font-semibold text-slate-700 hover:text-emerald-700 inline-flex items-center gap-1 transition-colors"
                >
                  <span>Chi tiết vị trí</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
                <Button
                  size="sm"
                  onClick={() => {
                    setSelectedJobForApply(job);
                    setIsApplyModalOpen(true);
                  }}
                >
                  Ứng tuyển ngay
                </Button>
              </div>
            </Card>
          ))}
        </div>

        {filteredJobs.length === 0 && (
          <div className="text-center py-16 bg-white rounded-2xl border border-dashed border-slate-300">
            <Building className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h4 className="text-base font-bold text-slate-700">Không tìm thấy vị trí tuyển dụng phù hợp</h4>
            <p className="text-xs text-slate-500 mt-1">Hãy thử tìm kiếm với từ khóa khác hoặc xóa bộ lọc.</p>
          </div>
        )}
      </div>

      {/* Unified Apply & AI Match Modal */}
      <ApplyModal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        preselectedJob={selectedJobForApply}
      />
    </div>
  );
};

