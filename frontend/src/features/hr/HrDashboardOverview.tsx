import React, { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { ArrowDownUp, CheckCircle2, FileText, Plus, Video } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import type { ApplicationStatus } from '../../shared/types/models';
import { Card } from '../../shared/components/ui/Card';
import { StatusBadge, Badge } from '../../shared/components/ui/Badge';
import { MockDataBanner } from '../../shared/components/ui/MockDataIndicator';

type ApplicationRow = ReturnType<typeof mockStore.getApplications>[number];
type InterviewRow = ReturnType<typeof mockStore.getInterviews>[number];

const STAGES: { label: string; statuses: ApplicationStatus[] }[] = [
  { label: 'Sàng lọc', statuses: ['SCORING', 'PENDING_HR_REVIEW'] },
  {
    label: 'Phỏng vấn',
    statuses: ['INTERVIEW_INVITED', 'INTERVIEW_CONFIRMED', 'AWAITING_INTERVIEW_RESULT', 'INTERVIEW_PASSED'],
  },
  { label: 'Thử việc', statuses: ['AWAITING_ACCOUNT', 'ON_PROBATION', 'PROBATION_PASSED'] },
  {
    label: 'Đã kết thúc',
    statuses: ['REJECTED', 'INTERVIEW_DECLINED', 'INTERVIEW_FAILED', 'PROBATION_DECLINED', 'PROBATION_FAILED'],
  },
];

const linkButton =
  'inline-flex h-9 items-center gap-2 rounded-control px-3.5 text-sm font-medium transition-colors';
const smallLinkButton =
  'inline-flex h-8 items-center gap-1.5 rounded-control border border-line-strong bg-surface/80 px-3 text-[13px] font-medium text-ink transition-colors hover:bg-surface';

const dateFormatter = new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
const timeFormatter = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' });

function formatDate(value?: string) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

const PanelHeader: React.FC<{ title: string; description?: string; action?: React.ReactNode }> = ({
  title,
  description,
  action,
}) => (
  <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
    <div>
      <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
      {description && <p className="mt-0.5 text-[13px] text-ink-muted">{description}</p>}
    </div>
    {action}
  </div>
);

const StatTile: React.FC<{ label: string; value: number; hint: string; emphasis?: boolean }> = ({
  label,
  value,
  hint,
  emphasis,
}) => (
  <Card className="px-5! py-4!">
    <p className="text-[13px] font-medium text-ink-muted">{label}</p>
    <p className={`mt-1.5 text-[28px] font-semibold leading-none tabular-nums ${emphasis ? 'text-warning-ink' : 'text-ink'}`}>
      {value}
    </p>
    <p className="mt-2 text-xs text-ink-subtle">{hint}</p>
  </Card>
);

const ScoreCell: React.FC<{ score?: number }> = ({ score }) => {
  if (score === undefined) return <span className="text-ink-subtle">—</span>;
  return (
    <div className="flex items-center gap-2">
      <span className="w-7 text-right font-medium tabular-nums text-ink">{score}</span>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-ink/5">
        <span className="block h-full rounded-full bg-brand" style={{ width: `${Math.min(100, score)}%` }} />
      </span>
    </div>
  );
};

const ApplicationsPanel: React.FC<{ applications: ApplicationRow[] }> = ({ applications }) => {
  const [tab, setTab] = useState<'pending' | 'all'>('pending');
  const [sortDesc, setSortDesc] = useState(true);
  const pending = applications.filter((app) => app.status === 'PENDING_HR_REVIEW');
  const rows = [...(tab === 'pending' ? pending : applications)].sort(
    (a, b) => (sortDesc ? -1 : 1) * ((a.aiTotalScore ?? -1) - (b.aiTotalScore ?? -1)),
  );
  const tabs = [
    { key: 'pending' as const, label: 'Chờ duyệt', count: pending.length },
    { key: 'all' as const, label: 'Tất cả', count: applications.length },
  ];

  return (
    <Card className="overflow-hidden p-0!">
      <PanelHeader
        title="Hồ sơ ứng tuyển"
        description="Hồ sơ dưới ngưỡng AI hoặc lỗi chấm điểm cần HR xem xét trong 5 ngày làm việc."
        action={
          <Link to="/app/hr/applications" className="shrink-0 text-[13px] font-medium text-brand hover:underline">
            Xem tất cả
          </Link>
        }
      />
      <div className="flex gap-5 border-b border-line px-5" role="tablist">
        {tabs.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
            className={`-mb-px flex cursor-pointer items-center gap-1.5 border-b-2 px-0.5 py-2.5 text-sm transition-colors ${
              tab === item.key ? 'border-brand font-medium text-ink' : 'border-transparent text-ink-muted hover:text-ink'
            }`}
          >
            {item.label}
            <span className="rounded-full bg-ink/5 px-1.5 text-xs tabular-nums text-ink-muted">{item.count}</span>
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="flex flex-col items-center px-6 py-14 text-center">
          <CheckCircle2 className="mb-3 h-8 w-8 text-brand" />
          <p className="text-sm font-medium text-ink">Tất cả hồ sơ đã được xử lý</p>
          <p className="mt-1 text-[13px] text-ink-muted">Không có mục nào quá hạn.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-ink/[0.025] text-xs text-ink-muted">
              <tr>
                <th scope="col" className="px-5 py-2.5 font-medium">Ứng viên</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Vị trí</th>
                <th scope="col" className="px-3 py-2.5 font-medium">
                  <button
                    type="button"
                    onClick={() => setSortDesc((value) => !value)}
                    className="inline-flex cursor-pointer items-center gap-1 hover:text-ink"
                  >
                    Điểm AI <ArrowDownUp className="h-3 w-3" />
                  </button>
                </th>
                <th scope="col" className="px-3 py-2.5 font-medium">Hạn duyệt</th>
                <th scope="col" className="px-3 py-2.5 font-medium">Trạng thái</th>
                <th scope="col" className="px-5 py-2.5"><span className="sr-only">Thao tác</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((app) => (
                <tr key={app.id} className="transition-colors hover:bg-white/60">
                  <td className="px-5 py-3">
                    <p className="font-medium text-ink">{app.candidateName}</p>
                    <p className="text-xs text-ink-subtle">{app.candidateEmail}</p>
                  </td>
                  <td className="px-3 py-3">
                    <p className="text-ink">{app.jobTitle}</p>
                    <p className="text-xs text-ink-subtle">{app.department}</p>
                  </td>
                  <td className="px-3 py-3"><ScoreCell score={app.aiTotalScore} /></td>
                  <td className="px-3 py-3 tabular-nums text-ink-muted">{formatDate(app.reviewDueAt)}</td>
                  <td className="px-3 py-3"><StatusBadge status={app.status} /></td>
                  <td className="px-5 py-3 text-right">
                    <Link to="/app/hr/applications" className={smallLinkButton}>
                      Xét duyệt
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};

const UpcomingInterviews: React.FC<{ interviews: InterviewRow[] }> = ({ interviews }) => (
  <Card className="overflow-hidden p-0!">
    <PanelHeader
      title="Phỏng vấn sắp tới"
      description={`${interviews.length} buổi qua Google Meet`}
      action={
        <Link to="/app/hr/interviews" className="shrink-0 text-[13px] font-medium text-brand hover:underline">
          Mở lịch
        </Link>
      }
    />
    {interviews.length === 0 ? (
      <p className="px-5 py-10 text-center text-[13px] text-ink-muted">Chưa có lịch phỏng vấn nào được lên lịch.</p>
    ) : (
      <ul className="divide-y divide-line">
        {interviews.slice(0, 5).map((item) => {
          const start = new Date(item.startAt);
          return (
            <li key={item.id} className="flex gap-3.5 px-5 py-3.5">
              <div className="flex h-11 w-11 shrink-0 flex-col items-center justify-center rounded-control border border-line bg-surface/70">
                <span className="text-[15px] font-semibold leading-none tabular-nums text-ink">
                  {String(start.getDate()).padStart(2, '0')}
                </span>
                <span className="mt-0.5 text-[10px] font-medium uppercase text-ink-subtle">Th{start.getMonth() + 1}</span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate text-sm font-medium text-ink">
                    {item.application?.candidate?.fullName ?? 'Ứng viên'}
                  </p>
                  <Badge variant={item.status === 'CONFIRMED' ? 'success' : 'neutral'} size="sm">
                    {item.status === 'CONFIRMED' ? 'Đã xác nhận' : 'Đã lên lịch'}
                  </Badge>
                </div>
                <p className="truncate text-xs text-ink-muted">{item.application?.job?.title}</p>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <p className="truncate text-xs tabular-nums text-ink-subtle">
                    {timeFormatter.format(start)} · {item.interviewerName}
                  </p>
                  <a
                    href={item.meetLink}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-brand hover:underline"
                  >
                    <Video className="h-3.5 w-3.5" /> Vào phòng Meet
                  </a>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    )}
  </Card>
);

const StageBreakdown: React.FC<{ applications: ApplicationRow[] }> = ({ applications }) => {
  const counts = STAGES.map((stage) => ({
    label: stage.label,
    value: applications.filter((app) => stage.statuses.includes(app.status)).length,
  }));
  const max = Math.max(1, ...counts.map((item) => item.value));
  return (
    <Card className="overflow-hidden p-0!">
      <PanelHeader title="Hồ sơ theo giai đoạn" description={`${applications.length} hồ sơ`} />
      <ul className="space-y-3 px-5 py-4">
        {counts.map((item) => (
          <li key={item.label} className="grid grid-cols-[88px_1fr_28px] items-center gap-3 text-[13px]">
            <span className="text-ink-muted">{item.label}</span>
            <span className="h-2 overflow-hidden rounded-full bg-ink/5">
              <span className="block h-full rounded-full bg-brand" style={{ width: `${(item.value / max) * 100}%` }} />
            </span>
            <span className="text-right font-medium tabular-nums text-ink">{item.value}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
};

export const HrDashboardOverview: React.FC = () => {
  const [jobs, setJobs] = useState(mockStore.getJobs('OPEN'));
  const [applications, setApplications] = useState<ApplicationRow[]>(mockStore.getApplications());
  const [interviews, setInterviews] = useState<InterviewRow[]>(mockStore.getInterviews());

  useEffect(() => {
    const update = () => {
      setJobs(mockStore.getJobs('OPEN'));
      setApplications(mockStore.getApplications());
      setInterviews(mockStore.getInterviews());
    };
    return mockStore.subscribe(update);
  }, []);

  const pendingReviewApps = applications.filter((a) => a.status === 'PENDING_HR_REVIEW');
  const upcomingInterviews = interviews
    .filter((i) => i.status === 'SCHEDULED' || i.status === 'CONFIRMED')
    .sort((a, b) => a.startAt.localeCompare(b.startAt));
  const departmentCount = new Set(jobs.map((job) => job.department)).size;
  const confirmedCount = upcomingInterviews.filter((item) => item.status === 'CONFIRMED').length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Tổng quan tuyển dụng</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Hôm nay có {pendingReviewApps.length} hồ sơ chờ duyệt và {upcomingInterviews.length} buổi phỏng vấn sắp diễn ra.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/app/hr/reports" className={`${linkButton} border border-line-strong bg-surface/80 text-ink hover:bg-surface`}>
            <FileText className="h-4 w-4" /> Báo cáo
          </Link>
          <Link to="/app/hr/applications" className={`${linkButton} border border-line-strong bg-surface/80 text-ink hover:bg-surface`}>
            Xem Pipeline
          </Link>
          <Link to="/app/hr/jobs" className={`${linkButton} bg-brand text-white hover:bg-brand-hover`}>
            <Plus className="h-4 w-4" /> Đăng tin tuyển dụng
          </Link>
        </div>
      </div>

      <MockDataBanner description="Số liệu tổng quan, danh sách hồ sơ chờ duyệt và lịch phỏng vấn đang dùng dữ liệu giả lập (mockStore)." />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Tin đang mở" value={jobs.length} hint={`Đang nhận hồ sơ · ${departmentCount} phòng ban`} />
        <StatTile
          label="Hồ sơ chờ duyệt"
          value={pendingReviewApps.length}
          hint="Cần xử lý trong 5 ngày làm việc"
          emphasis={pendingReviewApps.length > 0}
        />
        <StatTile label="Phỏng vấn sắp tới" value={upcomingInterviews.length} hint={`${confirmedCount} buổi ứng viên đã xác nhận`} />
        <StatTile label="Tổng hồ sơ" value={applications.length} hint="Trên tất cả các tin" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_360px]">
        <ApplicationsPanel applications={applications} />
        <div className="space-y-6">
          <UpcomingInterviews interviews={upcomingInterviews} />
          <StageBreakdown applications={applications} />
        </div>
      </div>
    </div>
  );
};
