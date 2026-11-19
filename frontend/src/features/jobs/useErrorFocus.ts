import { useEffect, useRef } from "react";

/** Cuộn tới ô/nhóm lỗi; nhóm nhận focus ở control ưu tiên hoặc control đầu còn bật. */
export function focusErrorTarget(id: string): boolean {
  const element = document.getElementById(id);
  if (!element) return false;
  const target = element.matches("input, select, textarea, button")
    ? element
    : (element.querySelector<HTMLElement>("[data-error-focus]") ??
      element.querySelector<HTMLElement>("input:not([disabled]), select:not([disabled]), textarea:not([disabled])") ??
      element);
  element.scrollIntoView?.({ block: "center" });
  target.focus();
  return true;
}

/**
 * request tăng sau lần lưu lỗi: chỉ lúc đó mới chuyển focus tới ô sai đầu tiên.
 * Không chuyển focus khi đang gõ; không tìm được ô thì đưa tới phần tổng hợp lỗi.
 */
export function useFocusFirstError(request: number, firstTargetId: string | undefined, summaryId: string) {
  const handled = useRef(request);
  useEffect(() => {
    if (request === handled.current) return;
    handled.current = request;
    if (firstTargetId && focusErrorTarget(firstTargetId)) return;
    const summary = document.getElementById(summaryId);
    summary?.scrollIntoView?.({ block: "nearest" });
    summary?.focus();
  }, [request, firstTargetId, summaryId]);
}
