// OtpModal thật: nộp qua API applications, không mã cố định, lỗi tại ô mã, khóa/cooldown theo
// thời điểm của server và Retry-After, gửi lại không báo thành công giả, chặn double-click.
/**
 * Contract (src/features/candidates/OtpModal.tsx):
 *   <OtpModal
 *     isOpen email submissionId submissionToken jobId
 *     expiresAt resendAvailableAt          // ISO times returned by the server
 *     onClose onSubmitted={(result: ApplicationCreated) => void} />
 *  - The parent owns the first OTP request; mounting/opening never calls the API.
 *  - Code input labelled /mã xác thực/i (6 digits, inputMode numeric); confirm button
 *    /xác nhận/i; resend button /gửi lại mã/i disabled until resendAvailableAt.
 *  - 201 -> onSubmitted(result) once. 422 on otp_code -> message under the input with
 *    aria-invalid; 429 otp_locked -> Retry-After shown, confirm disabled.
 *  - Resend success only after the server answers 200 (new times from the server).
 * Uses a QueryClientProvider (TanStack mutations).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "@/test/apiStub";
import {
  APPLICATION_CREATED_JSON,
  OTP_ISSUED_JSON,
  appError,
  stubFlowFetch,
  validationResponse,
  type FlowRequest,
} from "@/test/publicFlowStub";
import { OtpModal } from "./OtpModal";

const PAST = "2000-01-01T00:00:00Z";
const FUTURE = "2999-01-01T00:00:00Z";

function renderOtp(overrides: Partial<ComponentProps<typeof OtpModal>> = {}) {
  const props: ComponentProps<typeof OtpModal> = {
    isOpen: true,
    email: "ung.vien@example.test",
    submissionId: 501,
    submissionToken: "capability-token",
    jobId: 11,
    expiresAt: FUTURE,
    resendAvailableAt: FUTURE,
    onClose: vi.fn(),
    onSubmitted: vi.fn(),
    ...overrides,
  };
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <OtpModal {...props} />
    </QueryClientProvider>,
  );
  return props;
}

function submits(calls: FlowRequest[]) {
  return calls.filter((call) => call.method === "POST" && call.path === "/api/v1/applications");
}

describe("OtpModal", () => {
  it("không gọi API khi mở và không hiển thị mã thử nghiệm cố định", () => {
    const { calls } = stubFlowFetch({});
    renderOtp();
    expect(calls).toHaveLength(0);
    expect(screen.getByText(/ung\.vien@example\.test/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/123456|999999/);
  });

  it("chỉ báo thành công khi API trả 201", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch({
      "POST /api/v1/applications": () => jsonResponse(APPLICATION_CREATED_JSON, 201),
    });
    const props = renderOtp();

    await user.type(screen.getByLabelText(/mã xác thực/i), "482913");
    await user.click(screen.getByRole("button", { name: /xác nhận/i }));

    await waitFor(() => expect(props.onSubmitted).toHaveBeenCalledTimes(1));
    expect(props.onSubmitted).toHaveBeenCalledWith({
      applicationId: 9001,
      submittedAt: "2026-11-18T03:02:00Z",
      message: APPLICATION_CREATED_JSON.message,
    });
    expect(submits(calls)[0].json).toEqual({
      submission_id: 501,
      submission_token: "capability-token",
      job_id: 11,
      otp_code: "482913",
    });
  });

  it("mã cố định cũ không được tự chấp nhận: lỗi hiển thị ngay tại ô mã", async () => {
    const user = userEvent.setup();
    stubFlowFetch({
      "POST /api/v1/applications": () =>
        validationResponse("otp_code", "Mã xác thực không đúng hoặc đã hết hạn."),
    });
    const props = renderOtp();
    const input = screen.getByLabelText(/mã xác thực/i);

    await user.type(input, "123456");
    await user.click(screen.getByRole("button", { name: /xác nhận/i }));

    await waitFor(() => expect(input).toHaveAttribute("aria-invalid", "true"));
    expect(input).toHaveAccessibleDescription("Mã xác thực không đúng hoặc đã hết hạn.");
    expect(props.onSubmitted).not.toHaveBeenCalled();
    expect(screen.queryByText(/cảm ơn/i)).not.toBeInTheDocument();
  });

  it("mã chưa đủ 6 chữ số bị chặn tại client, không gọi API", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch({});
    renderOtp();
    const input = screen.getByLabelText(/mã xác thực/i);
    await user.type(input, "12a3");
    await user.click(screen.getByRole("button", { name: /xác nhận/i }));
    expect(submits(calls)).toHaveLength(0);
    expect((input as HTMLInputElement).value).toMatch(/^\d{0,6}$/);
  });

  it("double-click chỉ tạo một yêu cầu nộp", async () => {
    const user = userEvent.setup();
    let release: () => void = () => {};
    const { calls } = stubFlowFetch({
      "POST /api/v1/applications": () =>
        new Promise<Response>((resolve) => {
          release = () => resolve(jsonResponse(APPLICATION_CREATED_JSON, 201));
        }),
    });
    const props = renderOtp();
    await user.type(screen.getByLabelText(/mã xác thực/i), "482913");
    const confirm = screen.getByRole("button", { name: /xác nhận/i });

    await user.dblClick(confirm);
    await user.click(confirm);

    expect(submits(calls)).toHaveLength(1);
    release();
    await waitFor(() => expect(props.onSubmitted).toHaveBeenCalledTimes(1));
  });

  it("bị khóa: hiển thị thời gian chờ của server và vô hiệu nút xác nhận", async () => {
    const user = userEvent.setup();
    stubFlowFetch({
      "POST /api/v1/applications": () =>
        appError(429, "otp_locked", "Bạn đã nhập sai mã quá 5 lần.", { "Retry-After": "900" }),
    });
    const props = renderOtp();
    await user.type(screen.getByLabelText(/mã xác thực/i), "000000");
    await user.click(screen.getByRole("button", { name: /xác nhận/i }));

    expect(await screen.findByText(/15 phút|900 giây|14:59|15:00/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /xác nhận/i })).toBeDisabled();
    expect(props.onSubmitted).not.toHaveBeenCalled();
  });

  it("nút gửi lại bị khóa đến thời điểm server cho phép", () => {
    stubFlowFetch({});
    renderOtp({ resendAvailableAt: FUTURE });
    expect(screen.getByRole("button", { name: /gửi lại mã/i })).toBeDisabled();
  });

  it("gửi lại thành công chỉ sau khi API trả 200, dùng thời gian mới của server", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch({
      "POST /api/v1/applications/otp": () =>
        jsonResponse({ ...OTP_ISSUED_JSON, resend_available_at: FUTURE }),
    });
    renderOtp({ resendAvailableAt: PAST });

    await user.click(screen.getByRole("button", { name: /gửi lại mã/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /gửi lại mã/i })).toBeDisabled(),
    );
    const resend = calls.filter((call) => call.path === "/api/v1/applications/otp");
    expect(resend).toHaveLength(1);
    expect(resend[0].json).toEqual({
      submission_id: 501,
      submission_token: "capability-token",
      job_id: 11,
    });
    expect(await screen.findByText(/đã gửi mã mới/i)).toBeInTheDocument();
  });

  it.each([
    ["429", () => appError(429, "rate_limited", "Vui lòng chờ.", { "Retry-After": "40" })],
    ["503", () => appError(503, "email_unavailable", "Không gửi được email mã xác thực lúc này.")],
  ])("gửi lại lỗi %s không báo đã gửi", async (_label, respond) => {
    const user = userEvent.setup();
    stubFlowFetch({ "POST /api/v1/applications/otp": respond });
    renderOtp({ resendAvailableAt: PAST });

    await user.click(screen.getByRole("button", { name: /gửi lại mã/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(/đã gửi mã mới/i)).not.toBeInTheDocument();
  });
});
