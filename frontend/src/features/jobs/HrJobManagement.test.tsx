// Kiểm thao tác người dùng trên trang HR với API giả: đọc, lưu, lỗi từng ô và xóa.
// Các ca tải lại nền phải giữ nội dung đang sửa và version lúc mở form.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/features/auth/AuthProvider";
import {
  CSRF_ROUTE,
  errorResponse,
  jsonResponse,
  stubFetch,
  type RecordedRequest,
  type RouteHandler,
} from "@/test/apiStub";
import { accountJson, jobDetailJson, jobSummaryJson } from "@/test/fixtures";
import { ToastContainer } from "@/shared/components/ui/Toast";
import { HrJobManagement } from "./HrJobManagement";

const DEPARTMENTS = [
  { id: 1, name: "Phòng Kỹ thuật", is_active: true },
  { id: 2, name: "Phòng Nhân sự", is_active: true },
  { id: 3, name: "Phòng Cũ", is_active: false },
];
let lastQueryClient: QueryClient;

/** Simulates a background refetch (e.g. window refocus) of every job query. */
async function refetchJobsInBackground() {
  await act(() => lastQueryClient.invalidateQueries({ queryKey: ["job"] }));
}

const INTERVIEWERS = [
  { id: "iv-1", full_name: "Người Phỏng Vấn" },
  { id: "iv-2", full_name: "Trưởng Nhóm" },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  lastQueryClient = queryClient;
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/app/hr/jobs"]}>
          <HrJobManagement />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

function hrRoutes(extra: Record<string, RouteHandler> = {}): Record<string, RouteHandler> {
  return {
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({ access_token: "hr-token", token_type: "bearer", expires_in: 300, account: accountJson() }),
    "GET /api/v1/auth/me": () => jsonResponse(accountJson()),
    "GET /api/v1/departments": () => jsonResponse(DEPARTMENTS),
    "GET /api/v1/interviewers": () => jsonResponse(INTERVIEWERS),
    "GET /api/v1/jobs": () =>
      jsonResponse({ items: [jobSummaryJson()], total: 1, page: 1, page_size: 20 }),
    ...extra,
  };
}

/** A button inside the open job form (the table may hold a same-named row action). */
function formButton(name: string) {
  const form = screen.getByLabelText("Tên vị trí *").closest(".overflow-y-auto") as HTMLElement;
  return within(form).getByRole("button", { name });
}

const page = (items: ReturnType<typeof jobSummaryJson>[], total = items.length) =>
  jsonResponse({ items, total, page: 1, page_size: 20 });

// jsdom has no scrollIntoView; the form may scroll the first error into view.
beforeAll(() => {
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
});

/** A deadline that stays in the future whenever the suite runs (local yyyy-mm-dd). */
const FUTURE_DEADLINE = (() => {
  const date = new Date();
  date.setDate(date.getDate() + 30);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
})();

async function openCreate() {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Lập trình viên Backend Python");
  await user.click(screen.getByRole("button", { name: "Tạo tin tuyển dụng" }));
  await waitFor(() =>
    expect(within(screen.getByLabelText("Phòng ban *")).getByText("Phòng Nhân sự")).toBeInTheDocument(),
  );
  return user;
}

/** Fills every create-form field with input the backend accepts for publishing. */
async function fillValidPublishForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Tên vị trí *"), "Kỹ sư dữ liệu");
  await user.selectOptions(screen.getByLabelText("Phòng ban *"), "1");
  await user.type(screen.getByLabelText("Hình thức làm việc"), "Toàn thời gian – Hybrid");
  await user.type(screen.getByLabelText("Địa điểm làm việc"), "Hà Nội");
  fireEvent.change(screen.getByLabelText("Hạn nộp hồ sơ"), { target: { value: FUTURE_DEADLINE } });
  await user.type(screen.getByLabelText("Mô tả công việc"), "Xây dựng pipeline");
  await user.type(screen.getByLabelText("Yêu cầu ứng viên"), "SQL");
  await user.type(screen.getByLabelText("Tên tiêu chí 1"), "SQL");
  await user.type(screen.getByLabelText("Mô tả tiêu chí 1"), "Thành thạo SQL");
  await user.click(screen.getByLabelText("Người phỏng vấn: Trưởng Nhóm"));
}

/** Text of the elements referenced by aria-describedby. */
function describedText(field: HTMLElement): string {
  return (field.getAttribute("aria-describedby") ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" ");
}

function expectFieldError(field: HTMLElement, message: string | RegExp) {
  expect(field).toHaveAttribute("aria-invalid", "true");
  expect(field.className).toMatch(/(^|\s)border-rose-\d+/);
  if (typeof message === "string") expect(describedText(field)).toContain(message);
  else expect(describedText(field)).toMatch(message);
}

function expectFieldValid(field: HTMLElement) {
  expect(field).not.toHaveAttribute("aria-invalid", "true");
  expect(describedText(field)).not.toMatch(/Chưa nhập|Chưa chọn/);
}

/** The alert at the top of the form that lists every given message. */
function errorSummaryWith(...messages: string[]): HTMLElement {
  const summary = screen
    .queryAllByRole("alert")
    .find((element) => messages.every((message) => element.textContent?.includes(message)));
  if (!summary) throw new Error(`Không có thông báo tổng hợp chứa: ${messages.join(" | ")}`);
  return summary;
}

const jobPosts = (calls: RecordedRequest[]) =>
  calls.filter((call) => call.method === "POST" && call.path === "/api/v1/jobs");

const fastApi422 = (detail: unknown[]) => jsonResponse({ detail }, 422);

describe("HrJobManagement — danh sách", () => {
  it("hiển thị tin từ API, không có cột ngưỡng và không còn dữ liệu giả", async () => {
    stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () =>
          page([
            jobSummaryJson(),
            jobSummaryJson({ id: 2, title: "Chuyên viên Tuyển dụng", status: "OPEN", department_name: "Phòng Nhân sự" }),
          ]),
      }),
    );
    renderPage();

    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    expect(within(row).getByText("Phòng Kỹ thuật")).toBeInTheDocument();
    expect(within(row).getByText("Bản nháp")).toBeInTheDocument();
    expect(within(row).getByText("17/12/2026")).toBeInTheDocument();
    expect(within(row).getByText("Hybrid • Hà Nội")).toBeInTheDocument();
    expect(screen.getByText("Chuyên viên Tuyển dụng")).toBeInTheDocument();
    expect(screen.queryByText(/Ngưỡng mời/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Senior Python/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/BR0\d|UC1\.\d/)).not.toBeInTheDocument();
  });

  it("gửi đúng tham số tìm kiếm, lọc và phân trang; phòng ban lấy từ API", async () => {
    const { calls } = stubFetch(
      hrRoutes({ "GET /api/v1/jobs": () => page([jobSummaryJson()], 45) }),
    );
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Lập trình viên Backend Python");

    const departmentFilter = screen.getByLabelText("Lọc phòng ban");
    await waitFor(() => expect(within(departmentFilter).getByText("Phòng Nhân sự")).toBeInTheDocument());

    await user.type(screen.getByLabelText("Tìm theo tên vị trí"), "python");
    await user.click(screen.getByRole("button", { name: "Tìm" }));
    await user.selectOptions(screen.getByLabelText("Lọc trạng thái"), "OPEN");
    await user.selectOptions(departmentFilter, "2");
    await user.click(screen.getByRole("button", { name: "Trang sau" }));

    await waitFor(() =>
      expect(calls.map((call) => call.path)).toContain(
        "/api/v1/jobs?page=2&page_size=20&q=python&status=OPEN&department_id=2",
      ),
    );
    expect(screen.getByText("Trang 2 / 3")).toBeInTheDocument();
  });

  it("hiện một phần hoặc không hiện gì khi thiếu hình thức làm việc, địa điểm", async () => {
    stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () =>
          page([
            jobSummaryJson({ id: 1, title: "Chỉ địa điểm", work_mode: null, location: "Đà Nẵng" }),
            jobSummaryJson({ id: 2, title: "Không có gì", work_mode: null, location: null }),
          ]),
      }),
    );
    renderPage();

    const partial = (await screen.findByText("Chỉ địa điểm")).closest("tr")!;
    expect(within(partial).getByText("Đà Nẵng")).toBeInTheDocument();
    const empty = screen.getByText("Không có gì").closest("td")!;
    expect(empty.textContent).toBe("Không có gì");
  });

  it("báo khi chưa có tin và khi tải lỗi", async () => {
    stubFetch(hrRoutes({ "GET /api/v1/jobs": () => page([]) }));
    const first = renderPage();
    expect(await screen.findByText("Chưa có tin tuyển dụng nào.")).toBeInTheDocument();
    first.unmount();

    stubFetch(hrRoutes({ "GET /api/v1/jobs": () => errorResponse(500, "internal", "boom") }));
    renderPage();
    expect(await screen.findByText("Không tải được danh sách tin tuyển dụng.")).toBeInTheDocument();
  });
});

describe("HrJobManagement — tạo và sửa tin", () => {
  it("form đúng trường của database: có Hình thức làm việc, không có lương và loại hợp đồng", async () => {
    stubFetch(hrRoutes());
    await openCreate();

    const workMode = screen.getByLabelText("Hình thức làm việc");
    expect(workMode).toHaveAttribute("maxlength", "50");
    expect(workMode).toHaveAttribute("placeholder", "Toàn thời gian – Hybrid");
    expect(screen.queryByLabelText(/Mức lương/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Loại hợp đồng|Full-time/i)).not.toBeInTheDocument();
    // Inactive departments are not offered for a new posting.
    expect(within(screen.getByLabelText("Phòng ban *")).queryByText("Phòng Cũ")).not.toBeInTheDocument();
  });

  it("Lưu nháp gửi publish=false; bộ tiêu chí chưa nhập gửi null", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.type(screen.getByLabelText("Tên vị trí *"), "Kỹ sư dữ liệu");
    await user.selectOptions(screen.getByLabelText("Phòng ban *"), "2");
    await user.type(screen.getByLabelText("Hình thức làm việc"), "Toàn thời gian – Hybrid");
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));

    await waitFor(() => expect(calls.some((call) => call.method === "POST" && call.path === "/api/v1/jobs")).toBe(true));
    const body = calls.find((call) => call.method === "POST" && call.path === "/api/v1/jobs")!.body as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({
      title: "Kỹ sư dữ liệu",
      department_id: 2,
      work_mode: "Toàn thời gian – Hybrid",
      publish: false,
    });
    // An untouched criteria editor used to send a set with an empty criterion name, which the
    // backend rejects (string_too_short); criteria are optional for a draft, so none is sent.
    expect(body.criteria).toBeNull();
    await waitFor(() => expect(screen.queryByLabelText("Tên vị trí *")).not.toBeInTheDocument());
  });

  it("Đăng tin gửi publish=true kèm tiêu chí, ngưỡng kéo và người phỏng vấn đã chọn", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.type(screen.getByLabelText("Tên vị trí *"), "Kỹ sư dữ liệu");
    await user.selectOptions(screen.getByLabelText("Phòng ban *"), "1");
    // Publishing needs a future deadline on the backend; keep the fixture truly valid.
    fireEvent.change(screen.getByLabelText("Hạn nộp hồ sơ"), { target: { value: FUTURE_DEADLINE } });
    await user.type(screen.getByLabelText("Mô tả công việc"), "Xây dựng pipeline");
    await user.type(screen.getByLabelText("Yêu cầu ứng viên"), "SQL");
    await user.type(screen.getByLabelText("Tên tiêu chí 1"), "SQL");
    await user.type(screen.getByLabelText("Mô tả tiêu chí 1"), "Thành thạo SQL");
    await user.click(screen.getByLabelText("Tiêu chí bắt buộc 1"));
    await user.type(screen.getByLabelText("Điểm sàn tiêu chí 1"), "60");
    await user.click(screen.getByLabelText("Dùng ngưỡng mặc định của hệ thống"));
    const slider = screen.getByLabelText("Ngưỡng tự động mời phỏng vấn");
    expect(slider).toHaveAttribute("min", "0");
    expect(slider).toHaveAttribute("max", "100");
    fireEvent.change(slider, { target: { value: "85" } });
    await user.click(screen.getByLabelText("Người phỏng vấn: Trưởng Nhóm"));
    await user.click(formButton("Đăng tin"));

    await waitFor(() => expect(calls.some((call) => call.method === "POST" && call.path === "/api/v1/jobs")).toBe(true));
    const body = calls.find((call) => call.method === "POST" && call.path === "/api/v1/jobs")!.body;
    expect(body).toMatchObject({
      publish: true,
      deadline: FUTURE_DEADLINE,
      description: "Xây dựng pipeline",
      requirements: "SQL",
      criteria: {
        auto_invite_threshold: 85,
        interviewer_ids: ["iv-2"],
        criteria: [{ name: "SQL", description: "Thành thạo SQL", is_mandatory: true, min_score: 60, weight: 100 }],
      },
    });
  });

  it("lỗi 422 của backend hiện đúng thông điệp và giữ dữ liệu form", async () => {
    stubFetch(
      hrRoutes({
        "POST /api/v1/jobs": () =>
          errorResponse(422, "job_rule_violation", "Chưa đủ thông tin để đăng tin, còn thiếu: mô tả công việc"),
      }),
    );
    const user = await openCreate();

    // Client-valid input so the request reaches the (stubbed) backend rule check.
    await fillValidPublishForm(user);
    await user.click(formButton("Đăng tin"));

    expect(await screen.findByText("Chưa đủ thông tin để đăng tin, còn thiếu: mô tả công việc")).toBeInTheDocument();
    expect(screen.getByLabelText("Tên vị trí *")).toHaveValue("Kỹ sư dữ liệu");
  });

  it("sửa tin gửi PUT kèm version; 409 hiện thông điệp và tải lại danh sách", async () => {
    let jobListCalls = 0;
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () => {
          jobListCalls += 1;
          return page([jobSummaryJson({ version: 3 })]);
        },
        "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ version: 3 })),
        "PUT /api/v1/jobs/1": () =>
          errorResponse(409, "version_conflict", "Tin tuyển dụng đã được người khác thay đổi. Hãy tải lại tin rồi thực hiện lại."),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Sửa" }));

    const title = await screen.findByLabelText("Tên vị trí *");
    await waitFor(() => expect(title).toHaveValue("Lập trình viên Backend Python"));
    expect(screen.getByLabelText("Hình thức làm việc")).toHaveValue("Hybrid");
    await user.clear(title);
    await user.type(title, "Lập trình viên Python");
    await user.click(screen.getByRole("button", { name: "Lưu thay đổi" }));

    expect(
      await screen.findByText("Tin tuyển dụng đã được người khác thay đổi. Hãy tải lại tin rồi thực hiện lại."),
    ).toBeInTheDocument();
    const put = calls.find((call) => call.method === "PUT")!;
    expect(put.body).toMatchObject({ title: "Lập trình viên Python", version: 3 });
    await waitFor(() => expect(jobListCalls).toBeGreaterThan(1));
  });
});

describe("HrJobManagement — tải lại ngầm và tin vừa bị đóng", () => {
  it("tải lại ngầm không ghi đè form đang sửa và vẫn gửi version lúc mở form", async () => {
    let detailCalls = 0;
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () => page([jobSummaryJson({ version: 3 })]),
        "GET /api/v1/jobs/1": () => {
          detailCalls += 1;
          return detailCalls === 1
            ? jsonResponse(jobDetailJson({ version: 3 }))
            : jsonResponse(jobDetailJson({ version: 4, title: "Người khác vừa sửa" }));
        },
        "PUT /api/v1/jobs/1": () =>
          errorResponse(409, "version_conflict", "Tin tuyển dụng đã được người khác thay đổi."),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Sửa" }));
    const title = await screen.findByLabelText("Tên vị trí *");
    await waitFor(() => expect(title).toHaveValue("Lập trình viên Backend Python"));
    await user.clear(title);
    await user.type(title, "Bản sửa của tôi");

    await refetchJobsInBackground();
    await waitFor(() => expect(detailCalls).toBe(2));

    expect(screen.getByLabelText("Tên vị trí *")).toHaveValue("Bản sửa của tôi");
    await user.click(screen.getByRole("button", { name: "Lưu thay đổi" }));
    await waitFor(() => expect(calls.some((call) => call.method === "PUT")).toBe(true));
    expect(calls.find((call) => call.method === "PUT")!.body).toMatchObject({
      title: "Bản sửa của tôi",
      version: 3,
    });
  });

  it("tải lại ngầm không ghi đè bộ tiêu chí đang sửa và vẫn gửi version lúc mở", async () => {
    let detailCalls = 0;
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs/1": () => {
          detailCalls += 1;
          return jsonResponse(jobDetailJson({ version: detailCalls === 1 ? 4 : 5 }));
        },
        "PUT /api/v1/jobs/1/criteria": () => jsonResponse(jobDetailJson({ version: 6 })),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Bộ tiêu chí" }));
    const name1 = await screen.findByLabelText("Tên tiêu chí 1");
    await waitFor(() => expect(name1).toHaveValue("Python"));
    await user.clear(name1);
    await user.type(name1, "Python nâng cao");

    await refetchJobsInBackground();
    await waitFor(() => expect(detailCalls).toBe(2));

    expect(screen.getByLabelText("Tên tiêu chí 1")).toHaveValue("Python nâng cao");
    await user.click(screen.getByRole("button", { name: "Lưu phiên bản mới" }));
    await waitFor(() => expect(calls.some((call) => call.method === "PUT")).toBe(true));
    expect(calls.find((call) => call.method === "PUT")!.body).toMatchObject({ version: 4 });
  });

  it("danh sách còn Đang mở nhưng chi tiết đã đóng: form sửa chỉ đọc, không có nút lưu", async () => {
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () => page([jobSummaryJson({ status: "OPEN" })]),
        "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ status: "CLOSED" })),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Sửa" }));

    expect(await screen.findByText("Tin đã đóng nên không thể sửa.")).toBeInTheDocument();
    expect(screen.getByLabelText("Tên vị trí *")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Lưu thay đổi" })).not.toBeInTheDocument();
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
  });
});

describe("HrJobManagement — đăng và đóng tin", () => {
  it("đăng tin nháp và đóng tin đang mở gửi đúng version; tin đã đóng không có nút ghi", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () =>
          page([
            jobSummaryJson({ id: 1, title: "Tin nháp", status: "DRAFT", version: 2 }),
            jobSummaryJson({ id: 2, title: "Tin đang mở", status: "OPEN", version: 5 }),
            jobSummaryJson({ id: 3, title: "Tin đã đóng", status: "CLOSED", version: 9 }),
          ]),
        "POST /api/v1/jobs/1/publish": () => jsonResponse(jobDetailJson({ status: "OPEN" })),
        "POST /api/v1/jobs/2/close": () => jsonResponse(jobDetailJson({ id: 2, status: "CLOSED" })),
      }),
    );
    const user = userEvent.setup();
    renderPage();

    const draftRow = (await screen.findByText("Tin nháp")).closest("tr")!;
    const openRow = screen.getByText("Tin đang mở").closest("tr")!;
    const closedRow = screen.getByText("Tin đã đóng").closest("tr")!;

    expect(within(draftRow).queryByRole("button", { name: "Đóng tin" })).not.toBeInTheDocument();
    expect(within(openRow).queryByRole("button", { name: "Đăng tin" })).not.toBeInTheDocument();
    for (const name of ["Sửa", "Đăng tin", "Đóng tin", "Bộ tiêu chí"]) {
      expect(within(closedRow).queryByRole("button", { name })).not.toBeInTheDocument();
    }
    expect(within(closedRow).getByRole("button", { name: "Xem tiêu chí" })).toBeInTheDocument();

    await user.click(within(draftRow).getByRole("button", { name: "Đăng tin" }));
    await user.click(within(openRow).getByRole("button", { name: "Đóng tin" }));

    await waitFor(() => expect(calls.some((call) => call.path === "/api/v1/jobs/2/close")).toBe(true));
    expect(calls.find((call) => call.path === "/api/v1/jobs/1/publish")!.body).toEqual({ version: 2 });
    expect(calls.find((call) => call.path === "/api/v1/jobs/2/close")!.body).toEqual({ version: 5 });
    expect(window.confirm).toHaveBeenCalled();
  });

  it("đăng tin bị từ chối hiện thông điệp của backend", async () => {
    stubFetch(
      hrRoutes({
        "POST /api/v1/jobs/1/publish": () =>
          errorResponse(422, "job_rule_violation", "Bộ tiêu chí phải có ít nhất 1 người phỏng vấn"),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Đăng tin" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Bộ tiêu chí phải có ít nhất 1 người phỏng vấn");
  });
});

describe("HrJobManagement — bộ tiêu chí", () => {
  it("nạp bộ tiêu chí hiện tại, lưu phiên bản mới kèm version và xem lịch sử", async () => {
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ version: 4 })),
        "PUT /api/v1/jobs/1/criteria": () => jsonResponse(jobDetailJson({ version: 5 })),
        "GET /api/v1/jobs/1/criteria/versions": () =>
          jsonResponse([
            { ...jobDetailJson().current_criteria!, id: 2, version_no: 2, auto_invite_threshold: "80.00" },
            jobDetailJson().current_criteria,
          ]),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Bộ tiêu chí" }));

    const name1 = await screen.findByLabelText("Tên tiêu chí 1");
    await waitFor(() => expect(name1).toHaveValue("Python"));
    expect(screen.getByLabelText("Trọng số tiêu chí 2")).toHaveValue(40);
    expect(screen.getByLabelText("Dùng ngưỡng mặc định của hệ thống")).not.toBeChecked();
    expect(screen.getByLabelText("Ngưỡng tự động mời phỏng vấn")).toHaveValue("75");
    expect(screen.getByLabelText("Người phỏng vấn: Người Phỏng Vấn")).toBeChecked();
    expect(screen.getByText("Tổng trọng số: 100/100")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Thêm tiêu chí" }));
    expect(screen.getByLabelText("Tên tiêu chí 3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Xóa tiêu chí 3" }));
    await user.click(screen.getByLabelText("Dùng ngưỡng mặc định của hệ thống"));
    expect(screen.getByLabelText("Ngưỡng tự động mời phỏng vấn")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Lưu phiên bản mới" }));

    await waitFor(() => expect(calls.some((call) => call.method === "PUT")).toBe(true));
    expect(calls.find((call) => call.method === "PUT")!.body).toEqual({
      version: 4,
      auto_invite_threshold: null,
      interviewer_ids: ["iv-1"],
      criteria: [
        { name: "Python", description: "Kinh nghiệm Python", is_mandatory: true, min_score: 50, weight: 60 },
        { name: "SQL", description: "Thiết kế CSDL", is_mandatory: false, weight: 40 },
      ],
    });

    await user.click(within(row).getByRole("button", { name: "Bộ tiêu chí" }));
    await user.click(await screen.findByRole("button", { name: "Lịch sử phiên bản" }));
    expect(await screen.findByText("Phiên bản 2")).toBeInTheDocument();
    expect(screen.getByText("Phiên bản 1")).toBeInTheDocument();
    expect(screen.getByText("Ngưỡng tự động mời: 80/100")).toBeInTheDocument();
  });

  it("tin đã đóng chỉ xem được tiêu chí, không có nút lưu", async () => {
    stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () => page([jobSummaryJson({ status: "CLOSED" })]),
        "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ status: "CLOSED" })),
        "GET /api/v1/jobs/1/criteria/versions": () => jsonResponse([jobDetailJson().current_criteria]),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Xem tiêu chí" }));

    expect(await screen.findByText("Tin đã đóng nên không thể thay đổi bộ tiêu chí.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Lưu phiên bản mới" })).not.toBeInTheDocument();
  });
});

describe("HrJobManagement — lỗi tại từng trường khi tạo tin", () => {
  it("Đăng tin khi để trống: báo mọi trường thiếu tại ô, tổng hợp đầu form, focus ô đầu, không gửi request", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.click(formButton("Đăng tin"));

    const title = screen.getByLabelText("Tên vị trí *");
    await waitFor(() => expect(title).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(title, "Chưa nhập tên vị trí");
    expectFieldError(screen.getByLabelText("Phòng ban *"), "Chưa chọn phòng ban");
    expectFieldError(screen.getByLabelText("Tên tiêu chí 1"), "Chưa nhập tên tiêu chí 1");
    expectFieldError(screen.getByLabelText("Mô tả tiêu chí 1"), "Chưa nhập mô tả tiêu chí 1");
    // Each field is described by its own message, not by the whole list.
    expect(describedText(title)).not.toContain("Chưa chọn phòng ban");
    expect(describedText(screen.getByLabelText("Tên tiêu chí 1"))).not.toContain("Chưa nhập mô tả tiêu chí 1");
    // Optional fields stay valid.
    expectFieldValid(screen.getByLabelText("Hình thức làm việc"));
    expectFieldValid(screen.getByLabelText("Quyền lợi"));

    errorSummaryWith(
      "Chưa nhập tên vị trí",
      "Chưa chọn phòng ban",
      "Chưa nhập tên tiêu chí 1",
      "Chưa nhập mô tả tiêu chí 1",
    );
    await waitFor(() => expect(title).toHaveFocus());
    expect(jobPosts(calls)).toHaveLength(0);
  });

  it("sửa một ô chỉ gỡ lỗi của ô đó, giữ lỗi và dữ liệu các ô khác", async () => {
    stubFetch(hrRoutes());
    const user = await openCreate();
    await user.click(formButton("Đăng tin"));
    const title = screen.getByLabelText("Tên vị trí *");
    const department = screen.getByLabelText("Phòng ban *");
    await waitFor(() => expect(title).toHaveAttribute("aria-invalid", "true"));

    await user.type(title, "Kỹ sư dữ liệu");

    expectFieldValid(title);
    expect(screen.queryAllByText("Chưa nhập tên vị trí")).toHaveLength(0);
    expectFieldError(department, "Chưa chọn phòng ban");
    expectFieldError(screen.getByLabelText("Tên tiêu chí 1"), "Chưa nhập tên tiêu chí 1");
    expectFieldError(screen.getByLabelText("Mô tả tiêu chí 1"), "Chưa nhập mô tả tiêu chí 1");

    await user.selectOptions(department, "2");

    expectFieldValid(department);
    expect(title).toHaveValue("Kỹ sư dữ liệu");
    expect(department).toHaveValue("2");
    expectFieldError(screen.getByLabelText("Tên tiêu chí 1"), "Chưa nhập tên tiêu chí 1");
    expectFieldError(screen.getByLabelText("Mô tả tiêu chí 1"), "Chưa nhập mô tả tiêu chí 1");
  });

  it("thêm/xóa tiêu chí không làm lỗi lệch sang hàng khác", async () => {
    stubFetch(hrRoutes());
    const user = await openCreate();
    await user.click(formButton("Đăng tin"));
    await waitFor(() => expect(screen.getByLabelText("Tên tiêu chí 1")).toHaveAttribute("aria-invalid", "true"));

    await user.click(screen.getByRole("button", { name: "Thêm tiêu chí" }));

    // Row 1 keeps its own error; row 2 never shows row 1's message.
    expectFieldError(screen.getByLabelText("Tên tiêu chí 1"), "Chưa nhập tên tiêu chí 1");
    expect(describedText(screen.getByLabelText("Tên tiêu chí 2"))).not.toContain("tiêu chí 1");
    expect(describedText(screen.getByLabelText("Mô tả tiêu chí 2"))).not.toContain("tiêu chí 1");

    await user.type(screen.getByLabelText("Tên tiêu chí 2"), "Giao tiếp");
    await user.type(screen.getByLabelText("Mô tả tiêu chí 2"), "Trao đổi rõ ràng");
    expectFieldValid(screen.getByLabelText("Tên tiêu chí 2"));
    expectFieldValid(screen.getByLabelText("Mô tả tiêu chí 2"));

    await user.click(screen.getByRole("button", { name: "Xóa tiêu chí 1" }));

    // The remaining (valid) row is now row 1: the deleted row's errors must not move onto it.
    const name1 = screen.getByLabelText("Tên tiêu chí 1");
    expect(name1).toHaveValue("Giao tiếp");
    expect(screen.getByLabelText("Mô tả tiêu chí 1")).toHaveValue("Trao đổi rõ ràng");
    expectFieldValid(name1);
    expectFieldValid(screen.getByLabelText("Mô tả tiêu chí 1"));
    expect(screen.queryAllByText("Chưa nhập tên tiêu chí 1")).toHaveLength(0);
    expect(screen.queryAllByText("Chưa nhập mô tả tiêu chí 1")).toHaveLength(0);
    // Unrelated errors stay.
    expectFieldError(screen.getByLabelText("Tên vị trí *"), "Chưa nhập tên vị trí");
  });

  it("Lưu nháp trống chỉ báo tên vị trí và phòng ban; đóng rồi mở lại không còn lỗi cũ", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));

    const title = screen.getByLabelText("Tên vị trí *");
    await waitFor(() => expect(title).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(title, "Chưa nhập tên vị trí");
    expectFieldError(screen.getByLabelText("Phòng ban *"), "Chưa chọn phòng ban");
    // Untouched criteria are optional for a draft.
    expectFieldValid(screen.getByLabelText("Tên tiêu chí 1"));
    expectFieldValid(screen.getByLabelText("Mô tả tiêu chí 1"));
    expect(screen.queryAllByText("Chưa nhập tên tiêu chí 1")).toHaveLength(0);
    expect(jobPosts(calls)).toHaveLength(0);

    await user.click(formButton("Hủy"));
    await waitFor(() => expect(screen.queryByLabelText("Tên vị trí *")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Tạo tin tuyển dụng" }));

    expectFieldValid(await screen.findByLabelText("Tên vị trí *"));
    expectFieldValid(screen.getByLabelText("Phòng ban *"));
    expect(screen.queryAllByText("Chưa nhập tên vị trí")).toHaveLength(0);
    expect(screen.queryAllByText("Chưa chọn phòng ban")).toHaveLength(0);
  });

  it("Lưu nháp với bộ tiêu chí hoàn toàn chưa nhập gửi criteria: null", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.type(screen.getByLabelText("Tên vị trí *"), "Kỹ sư dữ liệu");
    await user.selectOptions(screen.getByLabelText("Phòng ban *"), "2");
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));

    await waitFor(() => expect(jobPosts(calls)).toHaveLength(1));
    expect(jobPosts(calls)[0].body).toMatchObject({
      title: "Kỹ sư dữ liệu",
      department_id: 2,
      publish: false,
      deadline: null,
      description: null,
      criteria: null,
    });
  });

  it("Lưu nháp với tiêu chí nhập dở báo phần thiếu; nhập đủ thì gửi", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.type(screen.getByLabelText("Tên vị trí *"), "Kỹ sư dữ liệu");
    await user.selectOptions(screen.getByLabelText("Phòng ban *"), "2");
    await user.type(screen.getByLabelText("Tên tiêu chí 1"), "SQL");
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));

    const description1 = screen.getByLabelText("Mô tả tiêu chí 1");
    await waitFor(() => expect(description1).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(description1, "Chưa nhập mô tả tiêu chí 1");
    // The backend checks any criteria set it receives (check_criteria), draft included.
    expectFieldError(screen.getByRole("group", { name: "Người phỏng vấn" }), "Chọn ít nhất một người phỏng vấn");
    expectFieldValid(screen.getByLabelText("Tên tiêu chí 1"));
    expect(screen.getByLabelText("Tên tiêu chí 1")).toHaveValue("SQL");
    expect(jobPosts(calls)).toHaveLength(0);

    await user.type(description1, "Thành thạo SQL");
    await user.click(screen.getByLabelText("Người phỏng vấn: Trưởng Nhóm"));
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));

    await waitFor(() => expect(jobPosts(calls)).toHaveLength(1));
    expect(jobPosts(calls)[0].body).toMatchObject({
      publish: false,
      criteria: {
        interviewer_ids: ["iv-2"],
        criteria: [{ name: "SQL", description: "Thành thạo SQL", weight: 100 }],
      },
    });
  });

  it("Lưu nháp: tổng trọng số sai và thiếu người phỏng vấn được đánh dấu tại nhóm, không gửi request", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.type(screen.getByLabelText("Tên vị trí *"), "Kỹ sư dữ liệu");
    await user.selectOptions(screen.getByLabelText("Phòng ban *"), "2");
    await user.type(screen.getByLabelText("Tên tiêu chí 1"), "SQL");
    await user.type(screen.getByLabelText("Mô tả tiêu chí 1"), "Thành thạo SQL");
    fireEvent.change(screen.getByLabelText("Trọng số tiêu chí 1"), { target: { value: "90" } });
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));

    const interviewers = screen.getByRole("group", { name: "Người phỏng vấn" });
    const criteriaGroup = screen.getByRole("group", { name: "Tiêu chí chấm điểm" });
    await waitFor(() => expect(interviewers).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(interviewers, "Chọn ít nhất một người phỏng vấn");
    expectFieldError(criteriaGroup, "Tổng trọng số phải bằng 100 (hiện tại 90)");
    errorSummaryWith("Chọn ít nhất một người phỏng vấn", "Tổng trọng số phải bằng 100 (hiện tại 90)");
    // The weight itself is within range: only the group is marked.
    expectFieldValid(screen.getByLabelText("Trọng số tiêu chí 1"));
    await waitFor(() => expect(screen.getByLabelText("Người phỏng vấn: Người Phỏng Vấn")).toHaveFocus());
    expect(jobPosts(calls)).toHaveLength(0);

    // Fixing the weight re-checks the total; the interviewer error stays until it is fixed.
    fireEvent.change(screen.getByLabelText("Trọng số tiêu chí 1"), { target: { value: "100" } });
    expect(criteriaGroup).not.toHaveAttribute("aria-invalid", "true");
    expectFieldError(interviewers, "Chọn ít nhất một người phỏng vấn");
    expect(screen.getByLabelText("Mô tả tiêu chí 1")).toHaveValue("Thành thạo SQL");
  });

  it("Lưu nháp sau khi đã đổi ngưỡng rồi chọn lại mặc định không âm thầm bỏ bộ tiêu chí", async () => {
    const { calls } = stubFetch(hrRoutes({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) }));
    const user = await openCreate();

    await user.type(screen.getByLabelText("Tên vị trí *"), "Kỹ sư dữ liệu");
    await user.selectOptions(screen.getByLabelText("Phòng ban *"), "2");
    await user.click(screen.getByLabelText("Dùng ngưỡng mặc định của hệ thống"));
    fireEvent.change(screen.getByLabelText("Ngưỡng tự động mời phỏng vấn"), { target: { value: "70" } });
    await user.click(screen.getByLabelText("Dùng ngưỡng mặc định của hệ thống"));
    await user.click(screen.getByRole("button", { name: "Lưu nháp" }));

    await waitFor(() => expect(screen.getByLabelText("Tên tiêu chí 1")).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(screen.getByLabelText("Tên tiêu chí 1"), "Chưa nhập tên tiêu chí 1");
    expect(screen.getByLabelText("Ngưỡng tự động mời phỏng vấn")).toHaveValue("70");
    expect(jobPosts(calls)).toHaveLength(0);
  });

  it("422 FastAPI tại criteria.criteria[0].name: đỏ đúng Tên tiêu chí 1, thông báo tiếng Việt, giữ dữ liệu", async () => {
    const { calls } = stubFetch(
      hrRoutes({
        "POST /api/v1/jobs": () =>
          fastApi422([
            {
              type: "string_too_short",
              loc: ["body", "criteria", "criteria", 0, "name"],
              msg: "String should have at least 1 character",
              input: "",
            },
          ]),
      }),
    );
    const user = await openCreate();
    await fillValidPublishForm(user);

    await user.click(formButton("Đăng tin"));

    const name1 = screen.getByLabelText("Tên tiêu chí 1");
    await waitFor(() => expect(name1).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(name1, "Chưa nhập tên tiêu chí 1");
    errorSummaryWith("Chưa nhập tên tiêu chí 1");
    expectFieldValid(screen.getByLabelText("Mô tả tiêu chí 1"));
    expectFieldValid(screen.getByLabelText("Tên vị trí *"));
    await waitFor(() => expect(name1).toHaveFocus());

    expect(jobPosts(calls)).toHaveLength(1);
    expect(screen.getByLabelText("Tên vị trí *")).toHaveValue("Kỹ sư dữ liệu");
    expect(screen.getByLabelText("Phòng ban *")).toHaveValue("1");
    expect(screen.getByLabelText("Hạn nộp hồ sơ")).toHaveValue(FUTURE_DEADLINE);
    expect(screen.getByLabelText("Mô tả công việc")).toHaveValue("Xây dựng pipeline");
    expect(name1).toHaveValue("SQL");
    expect(screen.getByLabelText("Mô tả tiêu chí 1")).toHaveValue("Thành thạo SQL");
    expect(screen.getByLabelText("Người phỏng vấn: Trưởng Nhóm")).toBeChecked();
  });

  it("422 FastAPI quá độ dài / vượt khoảng số có lý do cụ thể; đường dẫn lạ không gán nhầm ô", async () => {
    stubFetch(
      hrRoutes({
        "POST /api/v1/jobs": () =>
          fastApi422([
            {
              type: "string_too_long",
              loc: ["body", "title"],
              msg: "String should have at most 200 characters",
              input: "x",
              ctx: { max_length: 200 },
            },
            {
              type: "greater_than",
              loc: ["body", "headcount"],
              msg: "Input should be greater than 0",
              input: 0,
              ctx: { gt: 0 },
            },
            { type: "extra_forbidden", loc: ["body", "unexpected_field"], msg: "Extra inputs are not permitted", input: 1 },
          ]),
      }),
    );
    const user = await openCreate();
    await fillValidPublishForm(user);

    await user.click(formButton("Đăng tin"));

    const title = screen.getByLabelText("Tên vị trí *");
    const headcount = screen.getByLabelText("Số lượng cần tuyển");
    await waitFor(() => expect(title).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(title, /200/);
    expect(describedText(title)).not.toMatch(/Chưa nhập/);
    expectFieldError(headcount, /0/);
    expect(describedText(headcount)).not.toMatch(/Chưa nhập/);
    // The unknown path is reported at the top, never pinned on an unrelated field.
    for (const label of ["Mô tả công việc", "Hạn nộp hồ sơ", "Phòng ban *", "Tên tiêu chí 1", "Mô tả tiêu chí 1"]) {
      expectFieldValid(screen.getByLabelText(label));
    }
    expect(screen.getAllByRole("alert").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Extra inputs are not permitted/)).not.toBeInTheDocument();
    expect(title).toHaveValue("Kỹ sư dữ liệu");
  });
});

describe("HrJobManagement — lỗi tại từng trường khi sửa tin và bộ tiêu chí", () => {
  it("sửa tin: xóa tên vị trí bị chặn tại ô; nhập lại thì PUT thành công", async () => {
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ version: 3 })),
        "PUT /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ version: 4 })),
      }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Sửa" }));
    const title = await screen.findByLabelText("Tên vị trí *");
    await waitFor(() => expect(title).toHaveValue("Lập trình viên Backend Python"));

    await user.clear(title);
    await user.click(screen.getByRole("button", { name: "Lưu thay đổi" }));

    await waitFor(() => expect(title).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(title, "Chưa nhập tên vị trí");
    expect(screen.getByLabelText("Hình thức làm việc")).toHaveValue("Hybrid");
    expect(calls.some((call) => call.method === "PUT")).toBe(false);

    await user.type(title, "Lập trình viên Python");
    await user.click(screen.getByRole("button", { name: "Lưu thay đổi" }));

    await waitFor(() => expect(calls.some((call) => call.method === "PUT")).toBe(true));
    expect(calls.find((call) => call.method === "PUT")!.body).toMatchObject({
      title: "Lập trình viên Python",
      version: 3,
    });
    await waitFor(() => expect(screen.queryByLabelText("Tên vị trí *")).not.toBeInTheDocument());
  });

  async function openCriteria(extra: Record<string, RouteHandler>) {
    const result = stubFetch(
      hrRoutes({ "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ version: 4 })), ...extra }),
    );
    const user = userEvent.setup();
    renderPage();
    const row = (await screen.findByText("Lập trình viên Backend Python")).closest("tr")!;
    await user.click(within(row).getByRole("button", { name: "Bộ tiêu chí" }));
    await waitFor(() => expect(screen.getByLabelText("Tên tiêu chí 1")).toHaveValue("Python"));
    return { user, calls: result.calls };
  }

  it("bộ tiêu chí riêng: thiếu tên tiêu chí 2 bị chặn đúng hàng, không gửi request", async () => {
    const { user, calls } = await openCriteria({
      "PUT /api/v1/jobs/1/criteria": () => jsonResponse(jobDetailJson({ version: 5 })),
    });

    await user.clear(screen.getByLabelText("Tên tiêu chí 2"));
    await user.click(screen.getByRole("button", { name: "Lưu phiên bản mới" }));

    const name2 = screen.getByLabelText("Tên tiêu chí 2");
    await waitFor(() => expect(name2).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(name2, "Chưa nhập tên tiêu chí 2");
    expectFieldValid(screen.getByLabelText("Tên tiêu chí 1"));
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
  });

  it("bộ tiêu chí riêng: 422 FastAPI tại criteria[0].description và criteria[1].weight đánh dấu đúng hàng", async () => {
    const { user, calls } = await openCriteria({
      "PUT /api/v1/jobs/1/criteria": () =>
        fastApi422([
          {
            type: "string_too_short",
            loc: ["body", "criteria", 0, "description"],
            msg: "String should have at least 1 character",
            input: "",
            ctx: { min_length: 1 },
          },
          {
            type: "less_than_equal",
            loc: ["body", "criteria", 1, "weight"],
            msg: "Input should be less than or equal to 100",
            input: "150",
            ctx: { le: 100 },
          },
        ]),
    });

    await user.click(screen.getByRole("button", { name: "Lưu phiên bản mới" }));

    const description1 = screen.getByLabelText("Mô tả tiêu chí 1");
    await waitFor(() => expect(description1).toHaveAttribute("aria-invalid", "true"));
    expectFieldError(description1, "Chưa nhập mô tả tiêu chí 1");
    const weight2 = screen.getByLabelText("Trọng số tiêu chí 2");
    expectFieldError(weight2, /100/);
    expect(describedText(weight2)).not.toMatch(/Chưa nhập/);
    errorSummaryWith("Chưa nhập mô tả tiêu chí 1");
    // Other rows/fields are untouched, and the draft is kept as entered.
    expectFieldValid(screen.getByLabelText("Tên tiêu chí 1"));
    expectFieldValid(screen.getByLabelText("Mô tả tiêu chí 2"));
    expectFieldValid(screen.getByLabelText("Trọng số tiêu chí 1"));
    expect(screen.getByLabelText("Tên tiêu chí 1")).toHaveValue("Python");
    expect(weight2).toHaveValue(40);
    expect(screen.getByRole("button", { name: "Lưu phiên bản mới" })).toBeInTheDocument();
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(1);
  });
});

describe("HrJobManagement — xóa bản nháp và tin đã đóng chờ dọn dẹp", () => {
  function renderPageWithToasts() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    lastQueryClient = queryClient;
    return render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/app/hr/jobs"]}>
            <HrJobManagement />
            <ToastContainer />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );
  }

  function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((done) => {
      resolve = done;
    });
    return { promise, resolve };
  }

  const deletes = (calls: RecordedRequest[]) => calls.filter((call) => call.method === "DELETE");
  const draft = jobSummaryJson({ id: 1, title: "Tin nháp", status: "DRAFT", version: 4 });
  const other = jobSummaryJson({ id: 2, title: "Tin đang mở", status: "OPEN", version: 5 });
  const rowOf = async (title: string) => (await screen.findByText(title)).closest("tr")!;

  it("chỉ tin nháp có nút Xóa bản nháp; xác nhận nêu tên tin, hủy thì không gửi request", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () =>
          page([
            draft,
            other,
            jobSummaryJson({
              id: 3,
              title: "Tin đã đóng",
              status: "CLOSED",
              closed_at: "2026-11-17T03:00:00Z",
              deletion_due_date: "2099-12-31",
            }),
          ]),
      }),
    );
    const user = userEvent.setup();
    renderPage();

    const draftRow = await rowOf("Tin nháp");
    for (const title of ["Tin đang mở", "Tin đã đóng"]) {
      expect(within(screen.getByText(title).closest("tr")!).queryByRole("button", { name: /xóa/i })).toBeNull();
    }

    await user.click(within(draftRow).getByRole("button", { name: "Xóa bản nháp" }));

    expect(confirm).toHaveBeenCalledTimes(1);
    const question = String(confirm.mock.calls[0][0]);
    expect(question).toContain("Tin nháp");
    expect(question).toMatch(/không thể khôi phục/i);
    expect(deletes(calls)).toHaveLength(0);
    expect(screen.getByText("Tin nháp")).toBeInTheDocument();
  });

  it("xác nhận gửi DELETE kèm version; đang gửi khóa nút, chưa bỏ hàng; thành công báo và tải lại", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const answer = deferred<Response>();
    let deleted = false;
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () => (deleted ? page([other]) : page([draft, other])),
        "DELETE /api/v1/jobs/1": async () => {
          const response = await answer.promise;
          deleted = true;
          return response;
        },
      }),
    );
    const user = userEvent.setup();
    renderPageWithToasts();

    const button = within(await rowOf("Tin nháp")).getByRole("button", { name: "Xóa bản nháp" });
    await user.click(button);

    await waitFor(() => expect(button).toBeDisabled());
    await user.click(button);
    expect(deletes(calls)).toHaveLength(1);
    expect(deletes(calls)[0]).toMatchObject({ path: "/api/v1/jobs/1", body: { version: 4 } });
    expect(confirm).toHaveBeenCalledTimes(1);
    // The row stays until the API confirms the deletion.
    expect(screen.getByText("Tin nháp")).toBeInTheDocument();

    answer.resolve(jsonResponse(null, 204));

    await waitFor(() => expect(screen.queryByText("Tin nháp")).not.toBeInTheDocument());
    expect(screen.getByText("Tin đang mở")).toBeInTheDocument();
    expect(await screen.findByText(/đã xóa/i)).toBeInTheDocument();
    expect(deletes(calls)).toHaveLength(1);
  });

  it("lỗi mạng giữ nguyên hàng, báo lỗi và cho thử lại", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () => page([draft, other]),
        "DELETE /api/v1/jobs/1": () => {
          throw new TypeError("Failed to fetch");
        },
      }),
    );
    const user = userEvent.setup();
    renderPage();

    const row = await rowOf("Tin nháp");
    await user.click(within(row).getByRole("button", { name: "Xóa bản nháp" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Không thể hoàn tất thao tác. Vui lòng thử lại.");
    expect(screen.getByText("Tin nháp")).toBeInTheDocument();
    const button = within(screen.getByText("Tin nháp").closest("tr")!).getByRole("button", { name: "Xóa bản nháp" });
    await waitFor(() => expect(button).toBeEnabled());
    expect(deletes(calls)).toHaveLength(1);
  });

  it.each([
    [409, "version_conflict", "Tin tuyển dụng đã được người khác thay đổi. Hãy tải lại tin rồi thực hiện lại."],
    [404, "job_not_found", "Không tìm thấy tin tuyển dụng."],
  ])("%i khi xóa: báo lỗi và tải lại danh sách", async (status, code, shown) => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let listCalls = 0;
    stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () => {
          listCalls += 1;
          return page([draft, other]);
        },
        "DELETE /api/v1/jobs/1": () => errorResponse(status, code, shown),
      }),
    );
    const user = userEvent.setup();
    renderPage();

    const row = await rowOf("Tin nháp");
    const before = listCalls;
    await user.click(within(row).getByRole("button", { name: "Xóa bản nháp" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(shown);
    await waitFor(() => expect(listCalls).toBeGreaterThan(before));
  });

  it("xóa hàng cuối cùng của trang cuối thì lùi về trang trước còn dữ liệu", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let deleted = false;
    const firstPage = jobSummaryJson({ id: 30, title: "Tin trang 1", status: "OPEN" });
    const lastDraft = jobSummaryJson({ id: 21, title: "Nháp cuối cùng", status: "DRAFT", version: 2 });
    const { calls } = stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": (request) => {
          const pageNo = Number(new URL(request.path, "http://localhost").searchParams.get("page") ?? "1");
          const total = deleted ? 20 : 21;
          if (pageNo === 2) {
            return jsonResponse({ items: deleted ? [] : [lastDraft], total, page: 2, page_size: 20 });
          }
          return jsonResponse({ items: [firstPage], total, page: pageNo, page_size: 20 });
        },
        "DELETE /api/v1/jobs/21": () => {
          deleted = true;
          return jsonResponse(null, 204);
        },
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Tin trang 1");
    expect(screen.getByText("Trang 1 / 2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Trang sau" }));
    const row = await rowOf("Nháp cuối cùng");
    await user.click(within(row).getByRole("button", { name: "Xóa bản nháp" }));

    expect(await screen.findByText("Tin trang 1")).toBeInTheDocument();
    expect(screen.getByText("Trang 1 / 1")).toBeInTheDocument();
    expect(screen.queryByText("Chưa có tin tuyển dụng nào.")).not.toBeInTheDocument();
    const deleteIndex = calls.findIndex((call) => call.method === "DELETE");
    expect(deleteIndex).toBeGreaterThan(-1);
    expect(
      calls.slice(deleteIndex + 1).some((call) => call.method === "GET" && /[?&]page=1(&|$)/.test(call.path)),
    ).toBe(true);
  });

  it("tin đã đóng hiện ngày đủ hạn xóa hoặc đang chờ dọn dẹp, không có nút xóa tay", async () => {
    stubFetch(
      hrRoutes({
        "GET /api/v1/jobs": () =>
          page([
            jobSummaryJson({
              id: 3,
              title: "Đóng gần đây",
              status: "CLOSED",
              closed_at: "2026-11-17T03:00:00Z",
              deletion_due_date: "2099-12-31",
            }),
            jobSummaryJson({
              id: 4,
              title: "Đóng từ lâu",
              status: "CLOSED",
              closed_at: "2018-01-01T03:00:00Z",
              deletion_due_date: "2020-01-01",
            }),
          ]),
      }),
    );
    renderPage();

    const upcoming = await rowOf("Đóng gần đây");
    expect(upcoming).toHaveTextContent("31/12/2099");
    expect(upcoming.textContent).toMatch(/tự động/i);
    expect(upcoming.textContent).not.toMatch(/chờ dọn dẹp/i);

    // Due but not yet swept by the worker: never claim the posting is already deleted.
    const overdue = await rowOf("Đóng từ lâu");
    expect(overdue.textContent).toMatch(/đang chờ (hệ thống )?dọn dẹp/i);
    expect(overdue.textContent).not.toMatch(/đã (bị )?xóa/i);

    for (const row of [upcoming, overdue]) {
      expect(within(row).queryByRole("button", { name: /xóa/i })).toBeNull();
      expect(within(row).getByRole("button", { name: "Xem tiêu chí" })).toBeInTheDocument();
    }
  });
});
