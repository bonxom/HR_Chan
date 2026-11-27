import React, { useState } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowDownUp, Calendar, CheckCircle2, FileText, Plus } from 'lucide-react';
import { useAuth } from '@/features/auth/AuthProvider';
import { listApplications } from '@/features/applications/api';
import { ScoreCell, countOf, interviewingCount, useApplicationCounts } from '@/features/applications/display';
import { formatCompanyDateTime } from '@/features/applications/format';
import type { ApplicationCounts, ApplicationStatus } from '@/features/applications/types';
import { listJobs } from '@/features/jobs/api';
import { Card } from '@/shared/components/ui/Card';
import { StatusBadge } from '@/shared/components/ui/Badge';

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

const PANEL_SIZE = 8;

const linkButton =
  'inline-flex h-9 items-center gap-2 rounded-control px-3.5 text-sm font-medium transition-colors';
const smallLinkButton =
  'inline-flex h-8 items-center gap-1.5 rounded-control border border-line-strong bg-surface/80 px-3 text-[13px] font-medium text-ink transition-colors hover:bg-surface';

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

const ErrorBlock: React.FC<{ message: string; onRetry: () => void }> = ({ message, onRetry }) => (
  <div className="space-y-2 px-5 py-8 text-center">
    <p className="text-[13px] text-danger-ink">{message}</p>
    <button type="button" onClick={onRetry} className={smallLinkButton}>
      Thử lại
    </button>
  </div>
);

/** Value, loading placeholder, or error marker — never a fake 0. */
const StatTile: React.FC<{
  testId: string;
  label: string;
  value: number | undefined;
  failed: boolean;
  /** Undefined while the source is loading. */
  hint: string | undefined;
  emphasis?: boolean;
  onRetry: () => void;
}> = ({ testId, label, value, failed, hint, emphasis, onRetry }) => (
  <Card className="px-5! py-4!">
    <div data-testid={testId}>
      <p className="text-[13px] font-medium text-ink-muted">{label}</p>
      <p className={`mt-1.5 text-[28px] font-semibold leading-none tabular-nums ${emphasis ? 'text-warning-ink' : 'text-ink'}`}>
        {failed ? <span className="text-sm font-medium text-danger-ink">Lỗi tải</span> : value ?? <span className="text-ink-subtle">…</span>}
      </p>
      {failed ? (
        <button type="button" onClick={onRetry} className="mt-2 text-xs font-medium text-brand hover:underline">
          Thử lại
        </button>
      ) : (
        <p className="mt-2 text-xs text-ink-subtle">{hint ?? '…'}</p>
      )}
    </div>
  </Card>
);

const ApplicationsPanel: React.FC<{ counts: ApplicationCounts | undefined }> = ({ counts }) => {
  const { authorized } = useAuth();
  const [tab, setTab] = useState<'pending' | 'all'>('pending');
  const [order, setOrder] = useState<'desc' | 'asc'>('desc');
  const query = useQuery({
    queryKey: ['applications', 'overview', tab, order],
    queryFn: () =>
      authorized((token) =>
        listApplications(token, {
          page: 1,
          pageSize: PANEL_SIZE,
          status: tab === 'pending' ? 'PENDING_HR_REVIEW' : undefined,
          sort: 'ai_total_score',
          order,
        }),
      ),
  });
  const tabs = [
    { key: 'pending' as const, label: 'Chờ duyệt', count: counts ? countOf(counts, ['PENDING_HR_REVIEW']) : undefined },
    { key: 'all' as const, label: 'Tất cả', count: counts?.total },
  ];
  const rows = query.data?.items ?? [];

  return (
    <Card className="overflow-hidden p-0!">
      <PanelHeader
        title="Hồ sơ ứng tuyển"
        description="Hồ sơ dưới ngưỡng, không đạt tiêu chí bắt buộc hoặc AI không chấm được cần HR xem xét."
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
            {item.count !== undefined && (
              <span className="rounded-full bg-ink/5 px-1.5 text-xs tabular-nums text-ink-muted">{item.count}</span>
            )}
          </button>
        ))}
      </div>

      {query.isPending ? (
        <p className="px-5 py-10 text-center text-[13px] text-ink-muted">Đang tải hồ sơ...</p>
      ) : query.isError ? (
        <ErrorBlock message="Không tải được danh sách hồ sơ." onRetry={() => void query.refetch()} />
      ) : rows.length === 0 ? (
        <div className="flex flex-col items-center px-6 py-14 text-center">
          <CheckCircle2 className="mb-3 h-8 w-8 text-brand" />
          <p className="text-sm font-medium text-ink">
            {tab === 'pending' ? 'Không có hồ sơ chờ duyệt.' : 'Chưa có hồ sơ nào.'}
          </p>
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
                    onClick={() => setOrder((value) => (value === 'desc' ? 'asc' : 'desc'))}
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
                    <p className="font-medium text-ink">{app.fullName}</p>
                    <p className="text-xs text-ink-subtle">{app.email}</p>
                  </td>
                  <td className="px-3 py-3 text-ink">{app.jobTitle}</td>
                  <td className="px-3 py-3"><ScoreCell application={app} /></td>
                  <td className="px-3 py-3 tabular-nums text-ink-muted">{formatCompanyDateTime(app.reviewDueAt)}</td>
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

const StageBreakdown: React.FC<{ counts: ReturnType<typeof useApplicationCounts> }> = ({ counts }) => {
  // Không hiện tổng cũ cạnh thông báo lỗi khi lần tải lại thất bại.
  const data = counts.isError ? undefined : counts.data;
  const items = data ? STAGES.map((stage) => ({ label: stage.label, value: countOf(data, stage.statuses) })) : [];
  const max = Math.max(1, ...items.map((item) => item.value));
  return (
    <Card className="overflow-hidden p-0!">
      <div data-testid="stage-chart">
        <PanelHeader
          title="Hồ sơ theo giai đoạn (hiện tại)"
          description={data ? `${data.total} hồ sơ` : undefined}
        />
        {counts.isError ? (
          <ErrorBlock message="Không tải được số liệu." onRetry={() => void counts.refetch()} />
        ) : !data ? (
          <p className="px-5 py-8 text-center text-[13px] text-ink-muted">Đang tải...</p>
        ) : (
          <ul className="space-y-3 px-5 py-4">
            {items.map((item) => (
              <li
                key={item.label}
                data-testid={`stage-${item.label}`}
                className="grid grid-cols-[88px_1fr_28px] items-center gap-3 text-[13px]"
              >
                <span className="text-ink-muted">{item.label}</span>
                <span className="h-2 overflow-hidden rounded-full bg-ink/5">
                  <span className="block h-full rounded-full bg-brand" style={{ width: `${(item.value / max) * 100}%` }} />
                </span>
                <span className="text-right font-medium tabular-nums text-ink">{item.value}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
};

// Tổng quan HR dùng API thật; chưa có API danh sách phỏng vấn nên chỉ dẫn sang trang lịch.
export const HrDashboardOverview: React.FC = () => {
  const { authorized } = useAuth();
  const counts = useApplicationCounts();
  const openJobs = useQuery({
    queryKey: ['jobs', 'open-count'],
    queryFn: () => authorized((token) => listJobs(token, { page: 1, pageSize: 1, status: 'OPEN' })),
  });
  // Khi lần tải lại lỗi, Query vẫn giữ data cũ; không hiện số cũ cạnh thẻ báo lỗi.
  const data = counts.isError ? undefined : counts.data;
  const retryCounts = () => void counts.refetch();
  const pending = data ? countOf(data, ['PENDING_HR_REVIEW']) : undefined;
  const interviewing = data ? interviewingCount(data) : undefined;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Tổng quan tuyển dụng</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {data
              ? `Hôm nay có ${pending} hồ sơ chờ duyệt và ${interviewing} hồ sơ đang phỏng vấn.`
              : 'Tổng quan hồ sơ và tin tuyển dụng.'}
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

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          testId="tile-open-jobs"
          label="Tin đang mở"
          value={openJobs.data?.total}
          failed={openJobs.isError}
          hint="Đang nhận hồ sơ"
          onRetry={() => void openJobs.refetch()}
        />
        <StatTile
          testId="tile-pending"
          label="Hồ sơ chờ duyệt"
          value={pending}
          failed={counts.isError}
          hint={data ? `${data.overdue} hồ sơ quá hạn xét duyệt` : undefined}
          emphasis={(data?.overdue ?? 0) > 0}
          onRetry={retryCounts}
        />
        <StatTile
          testId="tile-interviewing"
          label="Đang phỏng vấn"
          value={interviewing}
          failed={counts.isError}
          hint="Đã mời, đã xác nhận hoặc chờ kết quả"
          onRetry={retryCounts}
        />
        <StatTile
          testId="tile-total"
          label="Tổng hồ sơ"
          value={data?.total}
          failed={counts.isError}
          hint="Trên tất cả các tin"
          onRetry={retryCounts}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_360px]">
        <ApplicationsPanel counts={data} />
        <div className="space-y-6">
          <Card className="px-5! py-4!">
            <Link to="/app/hr/interviews" className="flex items-center gap-2 text-sm font-medium text-brand hover:underline">
              <Calendar className="h-4 w-4" /> Lịch phỏng vấn
            </Link>
          </Card>
          <StageBreakdown counts={counts} />
        </div>
      </div>
    </div>
  );
};
