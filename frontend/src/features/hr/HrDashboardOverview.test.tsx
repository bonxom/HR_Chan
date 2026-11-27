// Tổng quan HR trên API giả: thẻ số liệu, bảng hồ sơ, biểu đồ giai đoạn, lỗi từng khối.
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { CSRF_ROUTE, errorResponse, jsonResponse, stubFetch, type RecordedRequest, type RouteHandler } from "@/test/apiStub";
import { accountJson, applicationSummaryJson, jobSummaryJson } from "@/test/fixtures";
import { COUNTS_ROUTE, countsJson, countsRoute, params } from "@/features/applications/testUtils";
import { HrDashboardOverview } from "./HrDashboardOverview";

let queryClient: QueryClient;

function renderOverview() {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/app/hr"]}>
          <HrDashboardOverview />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const page = (items: unknown[], total = items.length) => jsonResponse({ items, total, page: 1, page_size: 8 });

function routes(extra: Record<string, RouteHandler> = {}): Record<string, RouteHandler> {
  return {
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({ access_token: "hr-token", token_type: "bearer", expires_in: 300, account: accountJson() }),
    "GET /api/v1/auth/me": () => jsonResponse(accountJson()),
    // BY_STATUS mặc định: SCORING 1, PENDING 4, INVITED 2, CONFIRMED 1, AWAITING 3, REJECTED 1 → tổng 12.
    [COUNTS_ROUTE]: countsRoute(countsJson(undefined, 1)),
    "GET /api/v1/jobs": () => jsonResponse({ items: [jobSummaryJson()], total: 2, page: 1, page_size: 1 }),
    "GET /api/v1/applications": () => page([applicationSummaryJson()]),
    ...extra,
  };
}

const listCalls = (calls: RecordedRequest[]) => calls.filter((call) => call.path.startsWith("/api/v1/applications?"));
const tile = (id: string) => screen.getByTestId(id);

describe("HrDashboardOverview — thẻ số liệu", () => {
  it("lấy số từ API đếm và API tin tuyển dụng", async () => {
    const { calls } = stubFetch(routes());
    renderOverview();

    await waitFor(() => expect(tile("tile-open-jobs")).toHaveTextContent("2"));
    expect(tile("tile-pending")).toHaveTextContent("4");
    expect(tile("tile-pending")).toHaveTextContent("1 hồ sơ quá hạn xét duyệt");
    expect(tile("tile-interviewing")).toHaveTextContent("6");
    expect(tile("tile-total")).toHaveTextContent("12");
    expect(screen.getByText("Hôm nay có 4 hồ sơ chờ duyệt và 6 hồ sơ đang phỏng vấn.")).toBeInTheDocument();
    const jobsCall = calls.find((call) => call.path.startsWith("/api/v1/jobs?"))!;
    expect(params(jobsCall).get("status")).toBe("OPEN");
    expect(params(jobsCall).get("page_size")).toBe("1");
    // Một request đếm cho cả trang.
    expect(calls.filter((call) => call.path === "/api/v1/applications/counts")).toHaveLength(1);
  });

  it("API đếm lỗi: thẻ, câu đầu trang và số trên tab không hiện 0; bảng và tin đang mở vẫn hiện", async () => {
    stubFetch(routes({ [COUNTS_ROUTE]: () => errorResponse(500, "internal", "boom") }));
    renderOverview();

    expect(await screen.findByText("Trần Thị Ứng Viên")).toBeInTheDocument();
    await waitFor(() => expect(tile("tile-pending")).toHaveTextContent("Lỗi tải"));
    expect(tile("tile-interviewing")).toHaveTextContent("Lỗi tải");
    expect(tile("tile-total")).toHaveTextContent("Lỗi tải");
    expect(tile("tile-open-jobs")).toHaveTextContent("2");
    expect(screen.queryByText(/Hôm nay có/)).not.toBeInTheDocument();
    expect(screen.getByText("Tổng quan hồ sơ và tin tuyển dụng.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Chờ duyệt" })).toHaveTextContent(/^Chờ duyệt$/);
  });

  it("API tin tuyển dụng lỗi chỉ ảnh hưởng thẻ Tin đang mở, và thẻ có nút thử lại", async () => {
    let fail = true;
    stubFetch(
      routes({
        "GET /api/v1/jobs": () =>
          fail
            ? errorResponse(500, "internal", "boom")
            : jsonResponse({ items: [jobSummaryJson()], total: 2, page: 1, page_size: 1 }),
      }),
    );
    renderOverview();

    await waitFor(() => expect(tile("tile-open-jobs")).toHaveTextContent("Lỗi tải"));
    await waitFor(() => expect(tile("tile-total")).toHaveTextContent("12"));
    fail = false;
    await userEvent.click(within(tile("tile-open-jobs")).getByRole("button", { name: "Thử lại" }));
    await waitFor(() => expect(tile("tile-open-jobs")).toHaveTextContent("2"));
  });

  it("tải lại API đếm bị lỗi sau lần thành công: không giữ số cũ ở câu đầu trang và tab", async () => {
    let fail = false;
    stubFetch(
      routes({
        [COUNTS_ROUTE]: () => (fail ? errorResponse(500, "internal", "boom") : jsonResponse(countsJson(undefined, 1))),
      }),
    );
    renderOverview();
    await screen.findByText("Hôm nay có 4 hồ sơ chờ duyệt và 6 hồ sơ đang phỏng vấn.");

    fail = true;
    await act(() => queryClient.invalidateQueries({ queryKey: ["applications"] }));

    await waitFor(() => expect(tile("tile-pending")).toHaveTextContent("Lỗi tải"));
    expect(screen.queryByText(/Hôm nay có/)).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Chờ duyệt/ })).toHaveTextContent(/^Chờ duyệt$/);
    expect(screen.getByRole("tab", { name: /Tất cả/ })).toHaveTextContent(/^Tất cả$/);
    expect(screen.getByTestId("stage-chart")).not.toHaveTextContent("12 hồ sơ");
  });

  it("đang tải API đếm: không hiện số 0 ở dòng gợi ý", async () => {
    stubFetch(routes({ [COUNTS_ROUTE]: () => new Promise<Response>(() => {}) }));
    renderOverview();

    await screen.findByText("Trần Thị Ứng Viên");
    expect(tile("tile-pending")).not.toHaveTextContent(/\d/);
  });
});

describe("HrDashboardOverview — bảng hồ sơ", () => {
  it("tab Chờ duyệt lọc theo trạng thái, sắp theo điểm; đổi tab và đổi chiều sắp xếp", async () => {
    const { calls } = stubFetch(routes());
    renderOverview();

    await screen.findByText("Trần Thị Ứng Viên");
    const first = params(listCalls(calls)[0]);
    expect(first.get("status")).toBe("PENDING_HR_REVIEW");
    expect(first.get("page_size")).toBe("8");
    expect(first.get("sort")).toBe("ai_total_score");
    expect(first.get("order")).toBe("desc");
    await waitFor(() => expect(screen.getByRole("tab", { name: /Chờ duyệt/ })).toHaveTextContent("4"));
    expect(screen.getByRole("tab", { name: /Tất cả/ })).toHaveTextContent("12");

    await userEvent.click(screen.getByRole("tab", { name: /Tất cả/ }));
    await waitFor(() => expect(params(listCalls(calls).at(-1)!).has("status")).toBe(false));

    await userEvent.click(screen.getByRole("button", { name: /Điểm AI/ }));
    await waitFor(() => expect(params(listCalls(calls).at(-1)!).get("order")).toBe("asc"));
  });

  it("hàng: điểm null hiện nhãn, hạn theo giờ công ty, nút Xét duyệt dẫn sang Pipeline", async () => {
    stubFetch(
      routes({
        "GET /api/v1/applications": () =>
          page([applicationSummaryJson({ ai_total_score: null, ai_status: "NEEDS_REVIEW" })]),
      }),
    );
    renderOverview();

    const row = (await screen.findByText("Trần Thị Ứng Viên")).closest("tr") as HTMLElement;
    expect(within(row).getByText("AI không chấm được")).toBeInTheDocument();
    expect(within(row).queryByText("0")).not.toBeInTheDocument();
    // 10:30 UTC là 17:30 giờ công ty.
    expect(within(row).getByText("17:30 04/12/2026")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: "Xét duyệt" })).toHaveAttribute("href", "/app/hr/applications");
  });

  it("trạng thái rỗng khác nhau cho từng tab", async () => {
    stubFetch(routes({ "GET /api/v1/applications": () => page([]) }));
    renderOverview();

    expect(await screen.findByText("Không có hồ sơ chờ duyệt.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Tất cả/ }));
    expect(await screen.findByText("Chưa có hồ sơ nào.")).toBeInTheDocument();
  });

  it("bảng lỗi có nút thử lại, thẻ số liệu vẫn hiện", async () => {
    let fail = true;
    stubFetch(
      routes({
        "GET /api/v1/applications": () =>
          fail ? errorResponse(500, "internal", "boom") : page([applicationSummaryJson()]),
      }),
    );
    renderOverview();

    expect(await screen.findByText("Không tải được danh sách hồ sơ.")).toBeInTheDocument();
    await waitFor(() => expect(tile("tile-total")).toHaveTextContent("12"));
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText("Trần Thị Ứng Viên")).toBeInTheDocument();
  });
});

describe("HrDashboardOverview — biểu đồ và nội dung giả đã bỏ", () => {
  it("biểu đồ giai đoạn tính từ by_status", async () => {
    stubFetch(routes());
    renderOverview();

    const chart = await screen.findByTestId("stage-chart");
    await waitFor(() => expect(within(chart).getByTestId("stage-Sàng lọc")).toHaveTextContent("5"));
    expect(within(chart).getByTestId("stage-Phỏng vấn")).toHaveTextContent("6");
    expect(within(chart).getByTestId("stage-Thử việc")).toHaveTextContent("0");
    expect(within(chart).getByTestId("stage-Đã kết thúc")).toHaveTextContent("1");
  });

  it("không còn banner MOCK, không còn dữ liệu phỏng vấn giả; có link Lịch phỏng vấn", async () => {
    stubFetch(routes());
    renderOverview();

    await screen.findByText("Trần Thị Ứng Viên");
    expect(screen.queryByTestId("mock-data-banner")).not.toBeInTheDocument();
    expect(screen.queryByText("Phỏng vấn sắp tới")).not.toBeInTheDocument();
    expect(screen.queryByText(/Vào phòng Meet/)).not.toBeInTheDocument();
    expect(screen.queryByText(/5 ngày làm việc/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Lịch phỏng vấn/ })).toHaveAttribute("href", "/app/hr/interviews");
  });
});
