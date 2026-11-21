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
        className={`ml-auto shrink-0 rounded border border-amber-400/30 bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300 ${className}`}
      >
        {label ?? "MOCK"}
      </span>
    );
  }

  return (
    <span
      data-testid="mock-data-badge"
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-amber-800 ${className}`}
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
      className={`flex flex-wrap items-center gap-2.5 rounded-xl border border-amber-300/80 bg-amber-50 px-4 py-2.5 text-xs text-amber-900 ${className}`}
    >
      <MockDataBadge />
      <span className="leading-relaxed">{description}</span>
    </div>
  );
};
