import { StrictMode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "@/shared/services/client";
import { ResponsePage } from "./ResponsePage";
import { resolveResponse, submitResponse } from "./api";
import type { ResponseView } from "./types";

vi.mock("./api", () => ({ resolveResponse: vi.fn(), submitResponse: vi.fn() }));
vi.mock("./tokenBootstrap", () => ({ getResponseToken: () => "private-token" }));

const interview: ResponseView = {
  completed: false, purpose: "CONFIRM_INTERVIEW", job_title: "Kỹ sư phần mềm",
  expires_at: "2026-12-01T10:30:00Z", start_at: "2026-12-02T03:00:00Z",
  meet_link: "https://meet.google.com/abc-defg-hij", can_reschedule: true,
  allowed_actions: ["ACCEPTED", "DECLINED", "RESCHEDULE_REQUESTED"],
};
const consent: ResponseView = {
  completed: false, purpose: "TALENT_POOL_CONSENT", job_title: "Kỹ sư phần mềm",
  expires_at: interview.expires_at, allowed_actions: ["ACCEPTED", "DECLINED"],
  consent_mode: "GRANT", policy_ver: "talent-pool-v1", policy_text: "Cho phép lưu hồ sơ trong 12 tháng.",
  retention_months: 12, consent_snapshot: "snapshot", consent_expires_at: null,
};

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<StrictMode><QueryClientProvider client={client}><ResponsePage /></QueryClientProvider></StrictMode>);
}
beforeEach(() => {
  vi.mocked(resolveResponse).mockReset().mockResolvedValue(interview);
  vi.mocked(submitResponse).mockReset().mockResolvedValue({ outcome: "ACCEPTED", message: "Đã xác nhận lịch phỏng vấn." });
});

it("opening only resolves; explicit confirmation submits exactly once", async () => {
  const user = userEvent.setup();
  show();
  await screen.findByRole("heading", { name: "Phản hồi lịch phỏng vấn" });
  expect(submitResponse).not.toHaveBeenCalled();
  expect(screen.getByText(/02\/12\/2026/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Xác nhận tham dự" }));
  await screen.findByText("Đã xác nhận lịch phỏng vấn.");
  expect(submitResponse).toHaveBeenCalledExactlyOnceWith({ token: "private-token", action: "ACCEPTED" });
});

it("requires the reschedule note and omits unavailable rescheduling", async () => {
  const user = userEvent.setup();
  const view = show();
  await user.click(await screen.findByRole("button", { name: "Yêu cầu đổi lịch" }));
  await user.click(screen.getByRole("button", { name: "Gửi yêu cầu đổi lịch" }));
  expect(await screen.findByText("Vui lòng nhập ghi chú từ 1 đến 500 ký tự.")).toBeInTheDocument();
  expect(submitResponse).not.toHaveBeenCalled();
  await user.type(screen.getByLabelText("Ghi chú đổi lịch"), "Tôi bận buổi sáng.");
  await user.click(screen.getByRole("button", { name: "Gửi yêu cầu đổi lịch" }));
  await waitFor(() => expect(submitResponse).toHaveBeenCalledWith({ token: "private-token", action: "RESCHEDULE_REQUESTED", note: "Tôi bận buổi sáng." }));
  view.unmount();
  vi.mocked(resolveResponse).mockResolvedValue({ ...interview, can_reschedule: false, allowed_actions: ["ACCEPTED", "DECLINED"] });
  show();
  await screen.findByRole("heading", { name: "Phản hồi lịch phỏng vấn" });
  expect(screen.queryByRole("button", { name: "Yêu cầu đổi lịch" })).not.toBeInTheDocument();
});

it("requires an unchecked consent box and includes policy expectation", async () => {
  const user = userEvent.setup();
  vi.mocked(resolveResponse).mockResolvedValue(consent);
  show();
  const box = await screen.findByRole("checkbox");
  expect(box).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Đồng ý lưu hồ sơ" })).toBeDisabled();
  await user.click(box);
  await user.click(screen.getByRole("button", { name: "Đồng ý lưu hồ sơ" }));
  await waitFor(() => expect(submitResponse).toHaveBeenCalledWith({ token: "private-token", action: "ACCEPTED", policy_ver: "talent-pool-v1", consent_snapshot: "snapshot" }));
});

it("valid consent offers acknowledgement with its actual expiry", async () => {
  vi.mocked(resolveResponse).mockResolvedValue({ ...consent, consent_mode: "ACKNOWLEDGE", allowed_actions: ["ACCEPTED"], consent_expires_at: "2027-05-01T03:00:00Z" });
  show();
  await screen.findByRole("button", { name: "Đã hiểu" });
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Không đồng ý" })).not.toBeInTheDocument();
  expect(screen.getByText(/01\/05\/2027/)).toBeInTheDocument();
});

it("a stale consent reloads and requires a fresh choice", async () => {
  const user = userEvent.setup();
  vi.mocked(resolveResponse).mockResolvedValue(consent);
  vi.mocked(submitResponse).mockRejectedValue(new ApiError(409, "consent_changed", "Thông tin đã thay đổi."));
  show();
  await user.click(await screen.findByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Đồng ý lưu hồ sơ" }));
  await screen.findByText(/Thông tin đã thay đổi/);
  await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
  expect(submitResponse).toHaveBeenCalledTimes(1);
});

it("a lost submission is not retried and offers an explicit status check", async () => {
  const user = userEvent.setup();
  vi.mocked(submitResponse).mockRejectedValue(new TypeError("network failed"));
  show();
  await user.click(await screen.findByRole("button", { name: "Xác nhận tham dự" }));
  const check = await screen.findByRole("button", { name: "Kiểm tra kết quả" });
  expect(submitResponse).toHaveBeenCalledTimes(1);
  vi.mocked(resolveResponse).mockResolvedValue({ completed: true, outcome: "ACCEPTED", completed_at: "2026-11-25T03:00:00Z" });
  await user.click(check);
  await screen.findByText("Đường dẫn đã ghi nhận xác nhận.");
  expect(submitResponse).toHaveBeenCalledTimes(1);
});
