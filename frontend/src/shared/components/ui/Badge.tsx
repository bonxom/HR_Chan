import React from 'react';
import { ApplicationStatus, JobStatus, UserRole } from '../../types/models';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'neutral';
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
}) => {
  const sizeStyles = {
    sm: 'text-xs px-1.5 py-px',
    md: 'text-xs px-2 py-0.5',
  };

  const variantStyles = {
    default: 'bg-brand-soft text-brand-ink ring-brand/15',
    success: 'bg-brand-soft text-brand-ink ring-brand/15',
    warning: 'bg-warning-soft text-warning-ink ring-warning-ink/15',
    danger: 'bg-danger-soft text-danger-ink ring-danger-ink/15',
    info: 'bg-info-soft text-info-ink ring-info-ink/15',
    purple: 'bg-violet-50 text-violet-800 ring-violet-800/15',
    neutral: 'bg-ink/5 text-ink-muted ring-ink/10',
  };

  return (
    <span
      className={`inline-flex items-center whitespace-nowrap font-medium rounded-full ring-1 ring-inset ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
};

type StatusVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'neutral';

/** Vietnamese labels for application/job statuses and roles, shared with filters. */
export const STATUS_CONFIG: Record<string, { label: string; variant: StatusVariant }> = {
  // Application States
  SCORING: { label: 'Đang chấm điểm AI', variant: 'purple' },
  PENDING_HR_REVIEW: { label: 'Chờ HR duyệt', variant: 'warning' },
  INTERVIEW_INVITED: { label: 'Đã mời phỏng vấn', variant: 'info' },
  INTERVIEW_CONFIRMED: { label: 'Đã xác nhận lịch', variant: 'success' },
  INTERVIEW_DECLINED: { label: 'Từ chối phỏng vấn', variant: 'danger' },
  AWAITING_INTERVIEW_RESULT: { label: 'Chờ kết quả PV', variant: 'warning' },
  INTERVIEW_PASSED: { label: 'Đạt phỏng vấn', variant: 'success' },
  INTERVIEW_FAILED: { label: 'Không đạt phỏng vấn', variant: 'danger' },
  REJECTED: { label: 'Đã từ chối', variant: 'danger' },
  AWAITING_ACCOUNT: { label: 'Chờ cấp tài khoản', variant: 'info' },
  ON_PROBATION: { label: 'Đang thử việc', variant: 'default' },
  PROBATION_DECLINED: { label: 'Từ chối thử việc', variant: 'danger' },
  PROBATION_PASSED: { label: 'Đạt thử việc', variant: 'success' },
  PROBATION_FAILED: { label: 'Không đạt thử việc', variant: 'danger' },

  // Job States
  DRAFT: { label: 'Bản nháp', variant: 'neutral' },
  OPEN: { label: 'Đang mở', variant: 'success' },
  CLOSED: { label: 'Đã đóng', variant: 'neutral' },

  // Roles
  HR: { label: 'Tuyển dụng (HR)', variant: 'purple' },
  INTERVIEWER: { label: 'Người phỏng vấn', variant: 'info' },
  DEPT_MANAGER: { label: 'Quản lý bộ phận', variant: 'default' },
  PROBATION: { label: 'Thử việc', variant: 'warning' },
  ADMIN: { label: 'Quản trị hệ thống', variant: 'danger' },
};

export function statusLabel(status: string): string {
  return STATUS_CONFIG[status]?.label ?? status;
}

export const StatusBadge: React.FC<{ status: ApplicationStatus | JobStatus | UserRole | string }> = ({
  status,
}) => {
  const config = STATUS_CONFIG[status] || { label: status, variant: 'neutral' };

  return <Badge variant={config.variant}>{config.label}</Badge>;
};

