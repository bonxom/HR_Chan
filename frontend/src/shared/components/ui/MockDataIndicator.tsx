import type { FC } from "react";
import { FlaskConical } from "lucide-react";

interface MockDataBadgeProps {
  variant?: "inline" | "sidebar";
  label?: string;
  className?: string;
}

/**
 * Compact badge marking UI flows or navigation entries backed by local mock data.
 * Remove this component from a feature once it connects to real backend APIs.
 */
export const MockDataBadge: FC<MockDataBadgeProps> = ({
  variant = "inline",
  label,
  className = "",
}) => {
  if (variant === "sidebar") {
    return (
      <span
        data-testid="mock-data-badge"
        className={`ml-auto shrink-0 rounded-full bg-warning-soft px-1.5 py-px text-[10px] font-semibold tracking-wide text-warning-ink ring-1 ring-inset ring-warning-ink/15 ${className}`}
      >
        {label ?? "MOCK"}
      </span>
    );
  }

  return (
    <span
      data-testid="mock-data-badge"
      className={`inline-flex shrink-0 items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-xs font-medium text-warning-ink ring-1 ring-inset ring-warning-ink/15 ${className}`}
    >
      <FlaskConical className="h-3 w-3" />
      <span>{label ?? "DỮ LIỆU MOCK"}</span>
    </span>
  );
};

interface MockDataBannerProps {
  description?: string;
  className?: string;
}

/**
 * Contextual banner shown on screens/dialogs that still rely on bundled mock data.
 * Remove once the corresponding screen is backed by real backend endpoints.
 */
export const MockDataBanner: FC<MockDataBannerProps> = ({
  description = "Màn hình này đang sử dụng dữ liệu giả lập (mock) trên trình duyệt, chưa kết nối API backend thật.",
  className = "",
}) => {
  return (
    <div
      role="note"
      data-testid="mock-data-banner"
      className={`flex flex-wrap items-center gap-2.5 rounded-panel border border-warning-ink/15 bg-warning-soft/80 px-4 py-2.5 text-[13px] text-warning-ink backdrop-blur-xl ${className}`}
    >
      <MockDataBadge />
      <span className="leading-relaxed">{description}</span>
    </div>
  );
};
