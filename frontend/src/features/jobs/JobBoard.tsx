import React, { useState } from 'react';
import { Link } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { ArrowRight, ArrowUpRight, ImageIcon, Search, UploadCloud } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { GLASS_BAR, GLASS_PANEL } from '../../shared/components/ui/Glass';
import { ApplyModal } from '../candidates/ApplyModal';
import { listPublicJobs } from './publicApi';
import type { PublicJobSummary } from './publicTypes';
import { formatDate } from './format';
import eventPhoto from '@/assets/careers/event.webp';
import officePhoto from '@/assets/careers/office.jpg';
import teamPhoto from '@/assets/careers/team.jpg';

const PAGE_SIZE = 12;

const STEPS = [
  { title: 'Nộp CV', body: 'Tải CV lên và xác thực email bằng mã OTP. Không cần tạo tài khoản.' },
  { title: 'Sàng lọc', body: 'Bộ phận tuyển dụng xem xét hồ sơ theo yêu cầu của vị trí và phản hồi qua email.' },
  { title: 'Phỏng vấn', body: 'Lịch phỏng vấn gửi qua email. Bạn xác nhận hoặc đề nghị đổi lịch ngay trong email.' },
  { title: 'Thử việc', body: 'Ứng viên đạt phỏng vấn nhận thư mời thử việc và tài khoản nội bộ.' },
];

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

/** Nhóm các tin trên trang hiện tại theo phòng ban, giữ thứ tự server trả về. */
function groupByDepartment(jobs: PublicJobSummary[]) {
  const groups = new Map<string, PublicJobSummary[]>();
  for (const job of jobs) {
    const list = groups.get(job.departmentName) ?? [];
    list.push(job);
    groups.set(job.departmentName, list);
  }
  return Array.from(groups, ([name, items]) => ({ name, jobs: items }));
}

export const JobBoard: React.FC = () => {
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [selectedJob, setSelectedJob] = useState<PublicJobSummary | null>(null);
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);

  // Danh sách, tìm kiếm và phân trang đều do API công khai xử lý.
  const jobsQuery = useQuery({
    queryKey: ['public-jobs', page, query],
    queryFn: ({ signal }) => listPublicJobs({ page, pageSize: PAGE_SIZE, q: query }, signal),
    placeholderData: keepPreviousData,
  });

  const data = jobsQuery.data;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    setQuery(searchInput.trim());
    setPage(1);
  };

  const openApply = (job: PublicJobSummary | null) => {
    setSelectedJob(job);
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
              Chọn vị trí đang mở nhận hồ sơ và nộp CV trực tuyến. Bạn được thông báo qua email ở mỗi bước của quá
              trình tuyển dụng.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a
                href="#jobs-list"
                className="inline-flex h-11 items-center gap-2 rounded-control bg-brand px-5 text-[15px] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] transition-colors hover:bg-brand-hover"
              >
                {data && !query ? `Xem ${data.total} vị trí đang tuyển` : 'Xem vị trí đang tuyển'}
                <ArrowRight className="h-4 w-4" />
              </a>
              <Button
                variant="outline"
                size="lg"
                leftIcon={<UploadCloud className="h-4 w-4" />}
                onClick={() => openApply(null)}
              >
                Tải CV lên
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
      </section>

      {/* Open positions */}
      <section id="jobs-list" className="scroll-mt-24 py-16">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <div className="mb-6">
            <h2 className="text-[32px] font-bold tracking-tight">Vị trí đang tuyển</h2>
            <p className="mt-2 text-ink-muted">Chọn một vị trí để xem mô tả công việc và yêu cầu chi tiết.</p>
          </div>

          <form onSubmit={submitSearch} className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <label className="relative sm:w-96">
              <span className="sr-only">Tìm kiếm vị trí</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
              <input
                type="text"
                aria-label="Tìm kiếm vị trí"
                placeholder="Tìm theo tên vị trí"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                className="h-10 w-full rounded-control border border-white/80 bg-white/60 pl-9 pr-3 text-sm backdrop-blur-xl placeholder:text-ink-subtle focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15"
              />
            </label>
            <Button type="submit" variant="outline" className="self-start sm:self-auto">
              Tìm
            </Button>
          </form>

          {jobsQuery.isPending && (
            <p role="status" className={`rounded-2xl px-6 py-16 text-center text-sm text-ink-muted ${GLASS_PANEL}`}>
              Đang tải danh sách vị trí...
            </p>
          )}

          {jobsQuery.isError && !data && (
            <div role="alert" className={`space-y-3 rounded-2xl px-6 py-12 text-center ${GLASS_PANEL}`}>
              <p className="text-sm text-danger-ink">Không thể tải danh sách vị trí. Vui lòng thử lại.</p>
              <Button variant="outline" size="sm" onClick={() => jobsQuery.refetch()}>
                Thử lại
              </Button>
            </div>
          )}

          {data && data.items.length === 0 && (
            <div className={`rounded-2xl px-6 py-16 text-center ${GLASS_PANEL}`}>
              <p className="font-medium">{query ? 'Không tìm thấy vị trí phù hợp' : 'Chưa có vị trí đang tuyển'}</p>
              {query && <p className="mt-1 text-sm text-ink-muted">Hãy thử từ khóa khác.</p>}
            </div>
          )}

          {data && data.items.length > 0 && (
            <>
              <div className="space-y-10">
                {groupByDepartment(data.items).map((group) => (
                  <div key={group.name}>
                    <h3 className="mb-3 flex items-baseline gap-2 text-sm font-semibold">
                      {group.name}
                      <span className="font-normal text-ink-subtle">{group.jobs.length} vị trí</span>
                    </h3>
                    <ul className={`divide-y divide-line overflow-hidden rounded-2xl ${GLASS_PANEL}`}>
                      {group.jobs.map((job) => (
                        <li key={job.id}>
                          <article className="flex flex-col gap-3 px-5 py-5 transition-colors hover:bg-white/60 sm:flex-row sm:items-center sm:gap-6">
                            <header className="min-w-0 flex-1">
                              <h4 className="text-[17px] font-semibold text-ink">{job.title}</h4>
                              <p className="mt-1 text-sm text-ink-muted">
                                {job.location} · {job.workMode} · Tuyển {job.headcount} · Hạn nộp{' '}
                                {formatDate(job.deadline)}
                              </p>
                            </header>
                            <div className="flex flex-wrap items-center gap-3">
                              <Link
                                to={`/jobs/${job.id}`}
                                className="inline-flex items-center gap-1 text-sm font-medium text-ink-muted transition-colors hover:text-brand"
                              >
                                Chi tiết vị trí
                                <ArrowUpRight className="h-4 w-4" />
                              </Link>
                              <Button variant="outline" onClick={() => openApply(job)}>
                                Ứng tuyển ngay
                              </Button>
                            </div>
                          </article>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              <nav aria-label="Phân trang" className="flex items-center justify-center gap-4 pt-8">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Trang trước
                </Button>
                <span className="text-sm tabular-nums text-ink-muted">
                  Trang {data.page} / {totalPages}
                </span>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                  Trang sau
                </Button>
              </nav>
            </>
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
        preselectedJob={selectedJob}
      />
    </div>
  );
};
