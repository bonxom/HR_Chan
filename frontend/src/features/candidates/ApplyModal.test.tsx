// ApplyModal thật: nhập liên hệ/CV/đồng ý/CAPTCHA, lỗi đúng ô (viền đỏ qua aria-invalid,
// thông báo tiếng Việt, focus lỗi đầu), gửi FormData thật, chọn tin OPEN thật, yêu cầu OTP
// đúng một lần rồi mở OtpModal; chỉ cảm ơn sau 201; reset/đổi liên hệ vô hiệu submission cũ.
// TurnstileWidget và env được mock tường minh trong test (không có bypass trong production).
/**
 * Contract (src/features/candidates/ApplyModal.tsx):
 *   <ApplyModal isOpen onClose preselectedJob?: { id: number; title: string } | null />
 *  - Fields by label: /họ và tên/i, /^email/i, /số điện thoại/i, /tệp cv/i (input file,
 *    accept .pdf,.docx), checkbox /đồng ý/i, <TurnstileWidget siteKey={env.turnstileSiteKey}
 *    onToken resetKey />. Submit button /tải cv lên/i.
 *  - Client checks: required fields, email format, 10-digit phone, PDF/DOCX extension,
 *    size <= 5 MB, consent, CAPTCHA token. Invalid inputs get aria-invalid="true" and an
 *    aria-describedby Vietnamese message; the first invalid field receives focus.
 *  - Server: 422 detail.loc[-1] -> that field; 413/415 -> file field; 429/503 -> alert.
 *  - After upload: with preselectedJob request the OTP immediately; otherwise list OPEN jobs
 *    from GET /api/v1/public/jobs as radios and request the OTP via /gửi mã xác thực/i.
 *    Exactly one OTP request, then OtpModal (owned state; it never re-requests on mount).
 *  - Thank-you /cảm ơn/i only after POST /api/v1/applications returns 201.
 *  - Closing the modal or going back to edit drops the submission/OTP state; a new upload
 *    is required. Capability stays in memory only (no storage, no URL).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "@/test/apiStub";
import {
  APPLICATION_CREATED_JSON,
  OTP_ISSUED_JSON,
  SUBMISSION_JSON,
  appError,
  cvFile,
  publicJobJson,
  publicPage,
  stubFlowFetch,
  validationResponse,
  type FlowRequest,
} from "@/test/publicFlowStub";
import { ApplyModal } from "./ApplyModal";

vi.mock("@/configs/env", () => ({
  env: { apiBaseUrl: "", turnstileSiteKey: "site-key-test" },
  isDevBuild: false,
}));

vi.mock("./TurnstileWidget", () => ({
  TurnstileWidget: ({
    onToken,
    siteKey,
  }: {
    onToken: (token: string | null) => void;
    siteKey: string;
    resetKey?: number;
  }) => (
    <button type="button" data-sitekey={siteKey} onClick={() => onToken("captcha-ok")}>
      Xác minh CAPTCHA (giả lập)
    </button>
  ),
}));

const JOB = { id: 11, title: "Kỹ sư dữ liệu" };

function Harness({ preselectedJob }: { preselectedJob?: { id: number; title: string } | null }) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Mở lại
      </button>
      <ApplyModal isOpen={open} onClose={() => setOpen(false)} preselectedJob={preselectedJob} />
    </>
  );
}

function renderApply(preselectedJob: { id: number; title: string } | null = JOB) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Harness preselectedJob={preselectedJob} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function happyRoutes(overrides: Record<string, (request: FlowRequest) => Response> = {}) {
  let submission = 0;
  return {
    "POST /api/v1/candidates/submissions": () =>
      jsonResponse(
        {
          ...SUBMISSION_JSON,
          submission_id: SUBMISSION_JSON.submission_id + submission++,
        },
        201,
      ),
    "POST /api/v1/applications/otp": () => jsonResponse(OTP_ISSUED_JSON),
    "POST /api/v1/applications": () => jsonResponse(APPLICATION_CREATED_JSON, 201),
    "GET /api/v1/public/jobs": () =>
      jsonResponse(
        publicPage([publicJobJson(), publicJobJson({ id: 12, title: "Nhân viên kinh doanh" })]),
      ),
    ...overrides,
  };
}

const byPath = (calls: FlowRequest[], method: string, path: string) =>
  calls.filter((call) => call.method === method && call.path.split("?")[0] === path);

async function fillValid(
  user: ReturnType<typeof userEvent.setup>,
  values: Partial<{ name: string; email: string; phone: string; file: File }> = {},
) {
  await user.type(screen.getByLabelText(/họ và tên/i), values.name ?? "Nguyễn Văn A");
  await user.type(screen.getByLabelText(/^email/i), values.email ?? "ung.vien@example.test");
  await user.type(screen.getByLabelText(/số điện thoại/i), values.phone ?? "0912345678");
  await user.upload(screen.getByLabelText(/tệp cv/i), values.file ?? cvFile());
  await user.click(screen.getByLabelText(/đồng ý/i));
  await user.click(screen.getByRole("button", { name: /xác minh captcha/i }));
}

const submitUpload = (user: ReturnType<typeof userEvent.setup>) =>
  user.click(screen.getByRole("button", { name: /tải cv lên/i }));

describe("ApplyModal — kiểm tra tại client", () => {
  it("form trống: mọi ô bắt buộc báo lỗi tiếng Việt, focus ô đầu, không gọi API", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch(happyRoutes());
    renderApply();

    await submitUpload(user);

    const name = screen.getByLabelText(/họ và tên/i);
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name).toHaveAccessibleDescription(/họ tên/i);
    expect(name).toHaveFocus();
    expect(screen.getByLabelText(/^email/i)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(/số điện thoại/i)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(/tệp cv/i)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(/đồng ý/i)).toHaveAttribute("aria-invalid", "true");
    // Thông báo thiếu CAPTCHA (ví dụ "Vui lòng hoàn thành CAPTCHA.").
    // Thông báo ngay dưới widget và trong phần tóm tắt lỗi.
    expect(screen.getAllByText(/hoàn thành CAPTCHA/i)).toHaveLength(2);
    const summary = screen.getByRole("region", { name: /kiểm tra lại các thông tin/i });
    expect(summary).toBeVisible();
    expect(within(summary).getByText(/hoàn thành CAPTCHA/i)).toBeVisible();
    expect(within(summary).getByText(/họ tên/i)).toBeVisible();
    expect(calls).toHaveLength(0);
  });

  it.each([
    ["email sai", { email: "khong-hop-le" }, /^email/i, /email/i],
    ["số điện thoại 9 số", { phone: "091234567" }, /số điện thoại/i, /10 chữ số/],
    ["tệp quá 5 MB", { file: cvFile("cv.pdf", 5 * 1024 * 1024 + 1) }, /tệp cv/i, /5 ?MB/i],
    [
      "tệp ảnh",
      { file: cvFile("anh.png", 1000, "image/png") },
      /tệp cv/i,
      /PDF.*DOCX|DOCX.*PDF/i,
    ],
  ])("%s: lỗi ngay dưới ô, không tải lên", async (_label, values, field, message) => {
    const user = userEvent.setup({ applyAccept: false });
    const { calls } = stubFlowFetch(happyRoutes());
    renderApply();

    await fillValid(user, values);
    await submitUpload(user);

    const input = screen.getByLabelText(field);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(message);
    expect(input).toHaveFocus();
    expect(byPath(calls, "POST", "/api/v1/candidates/submissions")).toHaveLength(0);
  });

  it("tệp đúng 5 MB và DOCX được chấp nhận", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch(happyRoutes());
    renderApply();
    await fillValid(user, {
      file: cvFile(
        "cv.docx",
        5 * 1024 * 1024,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ),
    });
    await submitUpload(user);
    await waitFor(() =>
      expect(byPath(calls, "POST", "/api/v1/candidates/submissions")).toHaveLength(1),
    );
  });
});

describe("ApplyModal — gửi thật và lỗi server", () => {
  it("gửi FormData thật, yêu cầu OTP đúng một lần cho tin đã chọn rồi mở OtpModal", async () => {
    const user = userEvent.setup();
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const { calls } = stubFlowFetch(happyRoutes());
    renderApply();

    await fillValid(user);
    await submitUpload(user);

    expect(await screen.findByLabelText(/mã xác thực/i)).toBeInTheDocument();
    const [upload] = byPath(calls, "POST", "/api/v1/candidates/submissions");
    expect(upload.form).toBeInstanceOf(FormData);
    expect(upload.form?.get("full_name")).toBe("Nguyễn Văn A");
    expect(upload.form?.get("email")).toBe("ung.vien@example.test");
    expect(upload.form?.get("phone")).toBe("0912345678");
    expect(upload.form?.get("consent")).toBe("true");
    expect(upload.form?.get("captcha_token")).toBe("captcha-ok");
    expect((upload.form?.get("file") as File).name).toBe("cv.pdf");

    const otp = byPath(calls, "POST", "/api/v1/applications/otp");
    expect(otp).toHaveLength(1);
    expect(otp[0].json).toEqual({
      submission_id: SUBMISSION_JSON.submission_id,
      submission_token: SUBMISSION_JSON.submission_token,
      job_id: JOB.id,
    });
    expect(screen.getAllByText(/ung\.vien@example\.test/).length).toBeGreaterThan(0);
    // Không còn phân tích/gợi ý AI giả hoặc điểm số.
    expect(document.body.textContent).not.toMatch(/Độ tương thích|Điểm đánh giá AI|AI phân tích/);
    expect(setItem).not.toHaveBeenCalled();
    expect(window.location.href).not.toContain(SUBMISSION_JSON.submission_token);
  });

  it("chưa chọn tin: hiển thị tin OPEN thật từ API, chọn rồi mới gửi mã", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch(happyRoutes());
    renderApply(null);

    await fillValid(user);
    await submitUpload(user);

    const chosen = await screen.findByRole("radio", { name: /nhân viên kinh doanh/i });
    expect(screen.getByRole("radio", { name: /kỹ sư dữ liệu/i })).toBeInTheDocument();
    expect(byPath(calls, "POST", "/api/v1/applications/otp")).toHaveLength(0);
    expect(byPath(calls, "GET", "/api/v1/departments")).toHaveLength(0);

    await user.click(chosen);
    await user.click(screen.getByRole("button", { name: /gửi mã xác thực/i }));

    expect(await screen.findByLabelText(/mã xác thực/i)).toBeInTheDocument();
    const otp = byPath(calls, "POST", "/api/v1/applications/otp");
    expect(otp).toHaveLength(1);
    expect((otp[0].json as { job_id: number }).job_id).toBe(12);
  });

  it("lỗi 422 của server gắn đúng ô, focus và đặt lại CAPTCHA", async () => {
    const user = userEvent.setup();
    stubFlowFetch(
      happyRoutes({
        "POST /api/v1/candidates/submissions": () =>
          validationResponse("phone", "Số điện thoại phải gồm đúng 10 chữ số."),
      }),
    );
    renderApply();
    await fillValid(user);
    await submitUpload(user);

    const phone = screen.getByLabelText(/số điện thoại/i);
    await waitFor(() => expect(phone).toHaveAttribute("aria-invalid", "true"));
    expect(phone).toHaveAccessibleDescription("Số điện thoại phải gồm đúng 10 chữ số.");
    expect(phone).toHaveFocus();
    expect(screen.queryByLabelText(/mã xác thực/i)).not.toBeInTheDocument();
  });

  it.each([
    ["413", () => appError(413, "cv_too_large", "Tệp CV vượt quá dung lượng tối đa 5 MB."), /5 MB/],
    [
      "415",
      () => appError(415, "cv_unsupported_type", "Chỉ chấp nhận CV định dạng PDF hoặc DOCX."),
      /PDF hoặc DOCX/,
    ],
    [
      "422 file",
      () => validationResponse("file", "CV không có lớp chữ đọc được (ví dụ bản scan ảnh)."),
      /lớp chữ/,
    ],
  ])("server %s: lỗi gắn vào ô tệp CV", async (_label, respond, message) => {
    const user = userEvent.setup();
    stubFlowFetch(happyRoutes({ "POST /api/v1/candidates/submissions": respond }));
    renderApply();
    await fillValid(user);
    await submitUpload(user);

    const file = screen.getByLabelText(/tệp cv/i);
    await waitFor(() => expect(file).toHaveAttribute("aria-invalid", "true"));
    expect(file).toHaveAccessibleDescription(message);
  });

  it.each([
    [
      "503 CAPTCHA",
      () => appError(503, "captcha_unavailable", "Không kiểm tra được CAPTCHA lúc này."),
      /Không kiểm tra được CAPTCHA/,
    ],
    [
      "503 quét mã độc",
      () => appError(503, "scanner_unavailable", "Không kiểm tra được an toàn tệp."),
      /an toàn tệp/,
    ],
    [
      "429",
      () => appError(429, "rate_limited", "Bạn đã gửi quá nhiều hồ sơ.", { "Retry-After": "120" }),
      /quá nhiều hồ sơ/,
    ],
  ])("server %s: thông báo chung, không sang bước OTP", async (_label, respond, message) => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch(
      happyRoutes({ "POST /api/v1/candidates/submissions": respond }),
    );
    renderApply();
    await fillValid(user);
    await submitUpload(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(byPath(calls, "POST", "/api/v1/applications/otp")).toHaveLength(0);
    expect(screen.queryByLabelText(/mã xác thực/i)).not.toBeInTheDocument();
  });

  it("lỗi gửi OTP 503 không mở OtpModal và không báo đã gửi mã", async () => {
    const user = userEvent.setup();
    stubFlowFetch(
      happyRoutes({
        "POST /api/v1/applications/otp": () =>
          appError(503, "email_unavailable", "Không gửi được email mã xác thực lúc này."),
      }),
    );
    renderApply();
    await fillValid(user);
    await submitUpload(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(/không gửi được email/i);
    expect(screen.queryByLabelText(/mã xác thực/i)).not.toBeInTheDocument();
  });
});

describe("ApplyModal — hoàn tất, đóng và đổi liên hệ", () => {
  it("chỉ cảm ơn sau khi API nộp hồ sơ trả 201, không hiển thị điểm AI", async () => {
    const user = userEvent.setup();
    stubFlowFetch(happyRoutes());
    renderApply();
    await fillValid(user);
    await submitUpload(user);

    await user.type(await screen.findByLabelText(/mã xác thực/i), "482913");
    expect(screen.queryByText(/cảm ơn/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /xác nhận/i }));

    expect(await screen.findByText(/cảm ơn/i)).toBeInTheDocument();
    expect(screen.getByText(/9001/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\/100|Đạt ngưỡng|lời mời phỏng vấn/i);
  });

  it("nộp thất bại không hiển thị cảm ơn", async () => {
    const user = userEvent.setup();
    stubFlowFetch(
      happyRoutes({
        "POST /api/v1/applications": () =>
          appError(409, "job_not_accepting", "Tin tuyển dụng đã đóng hoặc hết hạn nhận hồ sơ."),
      }),
    );
    renderApply();
    await fillValid(user);
    await submitUpload(user);
    await user.type(await screen.findByLabelText(/mã xác thực/i), "482913");
    await user.click(screen.getByRole("button", { name: /xác nhận/i }));

    expect(await screen.findByText(/đã đóng hoặc hết hạn/i)).toBeInTheDocument();
    expect(screen.queryByText(/cảm ơn/i)).not.toBeInTheDocument();
  });

  it("đóng rồi mở lại: form trống, phải tải CV lại, không dùng submission cũ", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch(happyRoutes());
    renderApply();
    await fillValid(user);
    await submitUpload(user);
    await screen.findByLabelText(/mã xác thực/i);

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByLabelText(/họ và tên/i)).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Mở lại" }));

    expect(screen.getByLabelText(/họ và tên/i)).toHaveValue("");
    expect(screen.queryByLabelText(/mã xác thực/i)).not.toBeInTheDocument();
    await fillValid(user, { email: "moi@example.test" });
    await submitUpload(user);
    await screen.findByLabelText(/mã xác thực/i);

    const uploads = byPath(calls, "POST", "/api/v1/candidates/submissions");
    const otps = byPath(calls, "POST", "/api/v1/applications/otp");
    expect(uploads).toHaveLength(2);
    expect((otps.at(-1)?.json as { submission_id: number }).submission_id).toBe(
      SUBMISSION_JSON.submission_id + 1,
    );
  });

  it("phản hồi upload đến sau khi đóng/mở lại không khôi phục luồng cũ", async () => {
    const user = userEvent.setup();
    let release: () => void = () => {};
    const { calls } = stubFlowFetch(
      happyRoutes({
        "POST /api/v1/candidates/submissions": () =>
          new Promise<Response>((resolve) => {
            release = () => resolve(jsonResponse(SUBMISSION_JSON, 201));
          }) as unknown as Response,
      }),
    );
    renderApply();
    await fillValid(user);
    await submitUpload(user);
    await waitFor(() =>
      expect(byPath(calls, "POST", "/api/v1/candidates/submissions")).toHaveLength(1),
    );

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByLabelText(/họ và tên/i)).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Mở lại" }));
    await user.type(screen.getByLabelText(/^email/i), "moi@example.test");

    await act(async () => {
      release();
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(byPath(calls, "POST", "/api/v1/applications/otp")).toHaveLength(0);
    expect(screen.queryByLabelText(/mã xác thực/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/^email/i)).toHaveValue("moi@example.test");
    expect(screen.getByLabelText(/họ và tên/i)).toHaveValue("");
  });

  it("phản hồi OTP đến sau khi đóng/mở lại không mở OtpModal cho capability cũ", async () => {
    const user = userEvent.setup();
    let release: () => void = () => {};
    const { calls } = stubFlowFetch(
      happyRoutes({
        "POST /api/v1/applications/otp": () =>
          new Promise<Response>((resolve) => {
            release = () => resolve(jsonResponse(OTP_ISSUED_JSON));
          }) as unknown as Response,
      }),
    );
    renderApply();
    await fillValid(user);
    await submitUpload(user);
    await waitFor(() =>
      expect(byPath(calls, "POST", "/api/v1/applications/otp")).toHaveLength(1),
    );

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByLabelText(/họ và tên/i)).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Mở lại" }));

    await act(async () => {
      release();
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(screen.queryByLabelText(/mã xác thực/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/họ và tên/i)).toHaveValue("");
    expect(screen.getByLabelText(/^email/i)).toHaveValue("");
  });

  it("quay lại sửa email: phải tải lại, OTP gửi cho submission và email mới", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch(happyRoutes());
    renderApply(null);
    await fillValid(user);
    await submitUpload(user);
    await screen.findByRole("radio", { name: /kỹ sư dữ liệu/i });

    await user.click(screen.getByRole("button", { name: /quay lại|sửa thông tin/i }));
    const email = screen.getByLabelText(/^email/i);
    await user.clear(email);
    await user.type(email, "email.moi@example.test");
    // CAPTCHA dùng một lần: phải xác minh lại trước khi tải lên lần nữa.
    await user.click(screen.getByRole("button", { name: /xác minh captcha/i }));
    await submitUpload(user);
    await user.click(await screen.findByRole("radio", { name: /kỹ sư dữ liệu/i }));
    await user.click(screen.getByRole("button", { name: /gửi mã xác thực/i }));

    await screen.findByLabelText(/mã xác thực/i);
    const uploads = byPath(calls, "POST", "/api/v1/candidates/submissions");
    expect(uploads).toHaveLength(2);
    expect(uploads[1].form?.get("email")).toBe("email.moi@example.test");
    const otps = byPath(calls, "POST", "/api/v1/applications/otp");
    expect(otps).toHaveLength(1);
    expect((otps[0].json as { submission_id: number }).submission_id).toBe(
      SUBMISSION_JSON.submission_id + 1,
    );
    expect(screen.getAllByText(/email\.moi@example\.test/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/ung\.vien@example\.test/)).not.toBeInTheDocument();
  });
});
