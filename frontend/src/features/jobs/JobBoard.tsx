import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { ArrowRight, ArrowUpRight, ImageIcon, Search, UploadCloud } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { JobPosting } from '../../shared/types/models';
import { Button } from '../../shared/components/ui/Button';
import { GLASS_BAR, GLASS_PANEL } from '../../shared/components/ui/Glass';
import { MockDataBanner } from '../../shared/components/ui/MockDataIndicator';
import { ApplyModal } from '../candidates/ApplyModal';
import eventPhoto from '@/assets/careers/event.webp';
import officePhoto from '@/assets/careers/office.jpg';
import teamPhoto from '@/assets/careers/team.jpg';

const STEPS = [
  { title: 'Nộp CV', body: 'Tải CV lên và xác thực email bằng mã OTP. Không cần tạo tài khoản.' },
  { title: 'Sàng lọc', body: 'Hệ thống chấm điểm CV theo tiêu chí của vị trí, sau đó HR xem xét hồ sơ.' },
  { title: 'Phỏng vấn', body: 'Lịch phỏng vấn gửi qua email. Bạn xác nhận hoặc đề nghị đổi lịch ngay trong email.' },
  { title: 'Thử việc', body: 'Ứng viên đạt phỏng vấn nhận thư mời thử việc và tài khoản nội bộ.' },
];

const dateFormatter = new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

/**
 * Company photo with its caption on a glass chip. Without `src` it shows a placeholder,
 * so a missing photo never breaks the layout. Photos are cropped to fill the slot.
 */
const PhotoSlot: React.FC<{ className?: string; label: string; src?: string; alt?: string }> = ({
  className = '',
  label,
  src,
  alt = '',
}) => (
  <div
    className={`relative flex items-center justify-center overflow-hidden rounded-2xl bg-[linear-gradient(135deg,var(--color-brand-soft),#dff3f7_55%,#fbf0d9)] text-ink-subtle shadow-[0_12px_32px_-14px_rgba(15,60,50,0.35)] ${className}`}
  >
    {src ? (
      <img src={src} alt={alt} decoding="async" className="absolute inset-0 h-full w-full object-cover" />
    ) : (
      <ImageIcon className="h-5 w-5" />
    )}
    <span className={`absolute bottom-3 left-3 rounded-full px-3 py-1 text-xs font-medium text-ink ${GLASS_BAR}`}>{label}</span>
  </div>
);

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

  const departments = useMemo(() => Array.from(new Set(jobs.map((job) => job.department))).sort(), [jobs]);
  const locationCount = new Set(jobs.map((job) => job.location)).size;

  const filteredJobs = jobs.filter((job) => {
    const query = search.toLowerCase();
    const matchesSearch =
      job.title.toLowerCase().includes(query) ||
      job.description.toLowerCase().includes(query) ||
      job.requirements.toLowerCase().includes(query);
    const matchesDept = selectedDept === 'ALL' || job.department === selectedDept;
    return matchesSearch && matchesDept;
  });
  const grouped = departments
    .map((name) => ({ name, jobs: filteredJobs.filter((job) => job.department === name) }))
    .filter((group) => group.jobs.length > 0);

  const openApply = (job: JobPosting | null) => {
    setSelectedJobForApply(job);
    setIsApplyModalOpen(true);
  };

  return (
    <div>
      {/* Hero */}
      <section className="mx-auto max-w-6xl px-5 pb-16 pt-16 sm:px-8 sm:pt-24">
        <div className="grid items-end gap-12 lg:grid-cols-[1.25fr_1fr]">
          <div>
            <p className="mb-5 text-sm font-medium text-brand">Cơ hội nghề nghiệp</p>
            <h1 className="text-[40px] font-bold leading-[1.08] tracking-[-0.02em] sm:text-[56px]">
              Gia nhập đội ngũ tiên phong, kiến tạo công nghệ doanh nghiệp.
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-ink-muted">
              Nộp CV một lần, hệ thống phân tích hồ sơ và gợi ý các vị trí phù hợp với kinh nghiệm của bạn. Bạn được
              thông báo rõ ràng ở mỗi bước của quá trình tuyển dụng.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a
                href="#jobs-list"
                className="inline-flex h-11 items-center gap-2 rounded-control bg-brand px-5 text-[15px] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] transition-colors hover:bg-brand-hover"
              >
                Xem {jobs.length} vị trí đang tuyển <ArrowRight className="h-4 w-4" />
              </a>
              <Button
                variant="outline"
                size="lg"
                leftIcon={<UploadCloud className="h-4 w-4" />}
                onClick={() => openApply(null)}
              >
                Tải CV để được gợi ý việc làm
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <PhotoSlot
              label="Văn phòng"
              src={officePhoto}
              alt="Khu làm việc mở với bàn làm việc, ghế công thái học và buồng gọi điện riêng"
              className="col-span-2 aspect-[16/9]"
            />
            <PhotoSlot
              label="Đội ngũ"
              src={teamPhoto}
              alt="Các thành viên trong nhóm đặt tay chồng lên nhau quanh bàn họp"
              className="aspect-square"
            />
            <PhotoSlot
              label="Sự kiện"
              src={eventPhoto}
              alt="Đồng nghiệp vỗ tay chúc mừng tại buổi trao giải cuối năm"
              className="aspect-square"
            />
          </div>
        </div>

        <dl className={`mt-16 grid grid-cols-3 divide-x divide-line rounded-2xl px-2 ${GLASS_PANEL}`}>
          {[
            { label: 'Vị trí đang mở', value: jobs.length },
            { label: 'Phòng ban', value: departments.length },
            { label: 'Địa điểm làm việc', value: locationCount },
          ].map((fact) => (
            <div key={fact.label} className="px-4 py-6 sm:px-8">
              <dt className="text-sm text-ink-muted">{fact.label}</dt>
              <dd className="mt-1 text-3xl font-semibold tabular-nums">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* Open positions */}
      <section id="jobs-list" className="scroll-mt-24 py-16">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <div className="mb-6">
            <h2 className="text-[32px] font-bold tracking-tight">Vị trí đang tuyển</h2>
            <p className="mt-2 text-ink-muted">Chọn một vị trí để xem mô tả công việc và yêu cầu chi tiết.</p>
          </div>

          <MockDataBanner
            className="mb-6"
            description="Danh sách tin tuyển dụng và quy trình nộp CV gợi ý AI hiện đang dùng dữ liệu giả lập (mockStore) trên trình duyệt."
          />

          <div className="mb-8 flex flex-col gap-3 md:flex-row md:items-center">
            <label className="relative md:w-80">
              <span className="sr-only">Tìm kiếm vị trí</span>
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
              <input
                type="search"
                placeholder="Tìm theo vị trí, kỹ năng, công nghệ…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="h-10 w-full rounded-control border border-white/80 bg-white/60 pl-9 pr-3 text-sm backdrop-blur-xl placeholder:text-ink-subtle focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              {['ALL', ...departments].map((dept) => (
                <button
                  key={dept}
                  type="button"
                  aria-pressed={selectedDept === dept}
                  onClick={() => setSelectedDept(dept)}
                  className={`h-9 cursor-pointer rounded-full border px-3.5 text-sm transition-colors ${
                    selectedDept === dept
                      ? 'border-ink bg-ink text-white'
                      : 'border-white/80 bg-white/50 text-ink-muted backdrop-blur-xl hover:bg-white/80 hover:text-ink'
                  }`}
                >
                  {dept === 'ALL' ? 'Tất cả phòng ban' : dept}
                </button>
              ))}
            </div>
          </div>

          {grouped.length === 0 ? (
            <div className={`rounded-2xl px-6 py-16 text-center ${GLASS_PANEL}`}>
              <p className="font-medium">Không tìm thấy vị trí tuyển dụng phù hợp</p>
              <p className="mt-1 text-sm text-ink-muted">
                Hãy thử từ khóa khác, hoặc{' '}
                <button
                  type="button"
                  onClick={() => openApply(null)}
                  className="cursor-pointer font-medium text-brand underline-offset-4 hover:underline"
                >
                  tải CV để được gợi ý vị trí
                </button>
                .
              </p>
            </div>
          ) : (
            <div className="space-y-10">
              {grouped.map((group) => (
                <div key={group.name}>
                  <h3 className="mb-3 flex items-baseline gap-2 text-sm font-semibold">
                    {group.name}
                    <span className="font-normal text-ink-subtle">{group.jobs.length} vị trí</span>
                  </h3>
                  <ul className={`divide-y divide-line overflow-hidden rounded-2xl ${GLASS_PANEL}`}>
                    {group.jobs.map((job) => (
                      <li
                        key={job.id}
                        className="group flex flex-col gap-3 px-5 py-5 transition-colors hover:bg-white/60 sm:flex-row sm:items-center sm:gap-6"
                      >
                        <div className="min-w-0 flex-1">
                          <Link
                            to={`/jobs/${job.id}`}
                            className="inline-flex items-center gap-1.5 text-[17px] font-semibold text-ink hover:text-brand"
                          >
                            {job.title}
                            <ArrowUpRight className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" />
                          </Link>
                          <p className="mt-1 text-sm text-ink-muted">
                            {job.location} · {job.employmentType} · Tuyển {job.headcount} · Hạn nộp {formatDate(job.deadline)}
                          </p>
                        </div>
                        {job.salaryRange && (
                          <p className="text-sm font-medium tabular-nums text-ink sm:w-44 sm:text-right">{job.salaryRange}</p>
                        )}
                        <Button variant="outline" onClick={() => openApply(job)} className="self-start sm:self-auto">
                          Ứng tuyển ngay
                        </Button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Process */}
      <section className="py-16">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <h2 className="text-[32px] font-bold tracking-tight">Quy trình ứng tuyển</h2>
          <p className="mt-2 max-w-xl text-ink-muted">Bốn bước, và bạn luôn biết hồ sơ của mình đang ở đâu.</p>
          <ol className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, index) => (
              <li key={step.title} className={`rounded-2xl p-5 ${GLASS_PANEL}`}>
                <span className="text-sm font-medium tabular-nums text-ink-subtle">0{index + 1}</span>
                <h3 className="mt-2 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <ApplyModal
        isOpen={isApplyModalOpen}
        onClose={() => setIsApplyModalOpen(false)}
        preselectedJob={selectedJobForApply}
      />
    </div>
  );
};
