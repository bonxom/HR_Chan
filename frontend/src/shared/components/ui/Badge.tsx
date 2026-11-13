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
    sm: 'text-[11px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
  };

  const variantStyles = {
    default: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    success: 'bg-teal-50 text-teal-700 border border-teal-200',
    warning: 'bg-amber-50 text-amber-700 border border-amber-200',
    danger: 'bg-rose-50 text-rose-700 border border-rose-200',
    info: 'bg-sky-50 text-sky-700 border border-sky-200',
    purple: 'bg-indigo-50 text-indigo-700 border border-indigo-200',
    neutral: 'bg-slate-100 text-slate-700 border border-slate-200',
  };

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
};

export const StatusBadge: React.FC<{ status: ApplicationStatus | JobStatus | UserRole | string }> = ({
  status,
}) => {
  const statusConfig: Record<
    string,
    { label: string; variant: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'neutral' }
  > = {
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

  const config = statusConfig[status] || { label: status, variant: 'neutral' };

  return <Badge variant={config.variant}>{config.label}</Badge>;
};

