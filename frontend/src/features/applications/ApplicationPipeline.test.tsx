// Danh sách hồ sơ HR trên API giả: hàng, điểm null, đánh dấu, tìm kiếm, lọc, phân trang và thẻ đếm.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CSRF_ROUTE, errorResponse, jsonResponse, stubFetch, type RecordedRequest, type RouteHandler } from "@/test/apiStub";
import { accountJson, applicationSummaryJson } from "@/test/fixtures";
import { COUNTS_ROUTE, applicationsRoute, countsRoute, params, renderPipeline } from "./testUtils";

const authRoutes: Record<string, RouteHandler> = {
  ...CSRF_ROUTE,
  "POST /api/v1/auth/refresh": () =>
    jsonResponse({ access_token: "hr-token", token_type: "bearer", expires_in: 300, account: accountJson() }),
  "GET /api/v1/auth/me": () => jsonResponse(accountJson()),
};

const listCalls = (calls: RecordedRequest[]) => calls.filter((call) => call.path.startsWith("/api/v1/applications?"));
const countCalls = (calls: RecordedRequest[]) => calls.filter((call) => call.path === "/api/v1/applications/counts");

const page = (items: unknown[], total = items.length, pageNo = 1) =>
  jsonResponse({ items, total, page: pageNo, page_size: 20 });

function routes(extra: Record<string, RouteHandler> = {}) {
  return {
    ...authRoutes,
    "GET /api/v1/applications": applicationsRoute(() => page([applicationSummaryJson()])),
    [COUNTS_ROUTE]: countsRoute(),
    ...extra,
  };
}

describe("ApplicationPipeline — danh sách", () => {
  it("hiển thị hồ sơ thật từ API và không còn banner dữ liệu giả", async () => {
    stubFetch(routes());
    renderPipeline();

    const row = (await screen.findByText("Trần Thị Ứng Viên")).closest("tr") as HTMLElement;
    expect(within(row).getByText("ung.vien@example.com")).toBeInTheDocument();
    expect(within(row).getByText("Lập trình viên Backend Python")).toBeInTheDocument();
    expect(within(row).getByText("43.4/100")).toBeInTheDocument();
    expect(within(row).getByText("Chờ HR duyệt")).toBeInTheDocument();
    // 00:25 UTC là 07:25 giờ công ty cùng ngày.
    expect(within(row).getByText("27/11/2026")).toBeInTheDocument();
    expect(screen.queryByText(/dữ liệu giả lập/i)).not.toBeInTheDocument();
  });

  it("điểm null hiển thị nhãn trạng thái chấm, không hiển thị 0", async () => {
    stubFetch(
      routes({
        "GET /api/v1/applications": applicationsRoute(() =>
          page([
            applicationSummaryJson({ id: 1, full_name: "A Đang Chấm", status: "SCORING", ai_status: "PENDING", ai_total_score: null }),
            applicationSummaryJson({ id: 2, full_name: "B Cần Xem", ai_status: "NEEDS_REVIEW", ai_total_score: null }),
            applicationSummaryJson({ id: 3, full_name: "C Lỗi", ai_status: "FAILED", ai_total_score: null }),
          ]),
        ),
      }),
    );
    renderPipeline();

    const rowOf = async (name: string) => (await screen.findByText(name)).closest("tr") as HTMLElement;
    expect(within(await rowOf("A Đang Chấm")).getByText("Đang chấm điểm")).toBeInTheDocument();
    expect(within(await rowOf("B Cần Xem")).getByText("AI không chấm được")).toBeInTheDocument();
    expect(within(await rowOf("C Lỗi")).getByText("Lỗi chấm điểm")).toBeInTheDocument();
    expect(screen.queryByText("0/100")).not.toBeInTheDocument();
  });

  it("đánh dấu quá hạn chỉ khi chờ duyệt đã quá hạn, và đánh dấu lỗi email khi có", async () => {
    stubFetch(
      routes({
        "GET /api/v1/applications": applicationsRoute(() =>
          page([
            applicationSummaryJson({ id: 1, full_name: "Quá Hạn", review_due_at: "2020-01-01T10:30:00+00:00" }),
            applicationSummaryJson({ id: 2, full_name: "Còn Hạn", review_due_at: "2099-01-01T10:30:00+00:00" }),
            applicationSummaryJson({
              id: 3,
              full_name: "Đã Mời",
              status: "INTERVIEW_INVITED",
              review_due_at: "2020-01-01T10:30:00+00:00",
              email_issue: "BOUNCED",
            }),
          ]),
        ),
      }),
    );
    renderPipeline();

    const rowOf = async (name: string) => (await screen.findByText(name)).closest("tr") as HTMLElement;
    expect(within(await rowOf("Quá Hạn")).getByText("Quá hạn")).toBeInTheDocument();
    expect(within(await rowOf("Còn Hạn")).queryByText("Quá hạn")).not.toBeInTheDocument();
    expect(within(await rowOf("Đã Mời")).queryByText("Quá hạn")).not.toBeInTheDocument();
    expect(within(await rowOf("Đã Mời")).getByText("Lỗi gửi email")).toBeInTheDocument();
    expect(within(await rowOf("Còn Hạn")).queryByText("Lỗi gửi email")).not.toBeInTheDocument();
  });

  it("trạng thái rỗng và lỗi tải có nút thử lại", async () => {
    let fail = true;
    stubFetch(
      routes({
        "GET /api/v1/applications": applicationsRoute(() =>
          fail ? errorResponse(500, "internal", "boom") : page([]),
        ),
      }),
    );
    renderPipeline();

    expect(await screen.findByText("Không tải được danh sách hồ sơ.")).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText("Chưa có hồ sơ nào phù hợp.")).toBeInTheDocument();
  });

  it("tìm kiếm có debounce, trim, về trang 1 và chỉ hiện kết quả mới nhất", async () => {
    const { calls } = stubFetch(
      routes({
        "GET /api/v1/applications": applicationsRoute(async (request) => {
          const q = params(request).get("q");
          const pageNo = Number(params(request).get("page"));
          if (q === "Tr") {
            // Phản hồi cũ đến muộn không được ghi đè kết quả mới hơn.
            await new Promise((resolve) => setTimeout(resolve, 600));
            return page([applicationSummaryJson({ id: 8, full_name: "Kết Quả Cũ" })]);
          }
          if (q === "Trần") return page([applicationSummaryJson({ id: 9, full_name: "Kết Quả Mới" })]);
          return page([applicationSummaryJson({ full_name: `Trang ${pageNo}` })], 45, pageNo);
        }),
      }),
    );
    renderPipeline();

    await screen.findByText("Trang 1");
    await userEvent.click(screen.getByRole("button", { name: "Trang sau" }));
    await screen.findByText("Trang 2");

    const search = screen.getByRole("searchbox", { name: "Tìm hồ sơ" });
    expect(search).toHaveAttribute("placeholder", "Tìm theo tên hoặc email ứng viên");
    await userEvent.type(search, " Tr");
    await new Promise((resolve) => setTimeout(resolve, 450));
    await userEvent.type(search, "ần ");

    expect(await screen.findByText("Kết Quả Mới")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(screen.queryByText("Kết Quả Cũ")).not.toBeInTheDocument();

    const searched = listCalls(calls).filter((call) => params(call).has("q"));
    // Không gửi một request cho mỗi ký tự.
    expect(searched.length).toBeLessThanOrEqual(2);
    expect(params(searched[searched.length - 1]).get("q")).toBe("Trần");
    expect(params(searched[searched.length - 1]).get("page")).toBe("1");
  });

  it("lọc trạng thái gửi status, 'Tất cả' bỏ status và về trang 1", async () => {
    const { calls } = stubFetch(routes());
    renderPipeline();
    await screen.findByText("Trần Thị Ứng Viên");

    const select = screen.getByRole("combobox", { name: "Lọc trạng thái" });
    await userEvent.selectOptions(select, "REJECTED");
    await waitFor(() => expect(params(listCalls(calls).at(-1)!).get("status")).toBe("REJECTED"));
    expect(params(listCalls(calls).at(-1)!).get("page")).toBe("1");

    await userEvent.selectOptions(select, "");
    await waitFor(() => expect(params(listCalls(calls).at(-1)!).has("status")).toBe(false));
  });

  it("phân trang theo total", async () => {
    stubFetch(
      routes({
        "GET /api/v1/applications": applicationsRoute((request) => {
          const pageNo = Number(params(request).get("page"));
          return page([applicationSummaryJson({ full_name: `Người ${pageNo}` })], 41, pageNo);
        }),
      }),
    );
    renderPipeline();

    await screen.findByText("Người 1");
    expect(screen.getByText("Trang 1 / 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Trang trước" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Trang sau" }));
    await userEvent.click(await screen.findByRole("button", { name: "Trang sau" }));
    await screen.findByText("Người 3");
    expect(screen.getByRole("button", { name: "Trang sau" })).toBeDisabled();
  });
});

describe("ApplicationPipeline — thẻ đếm", () => {
  it("Tổng, Chờ HR duyệt và Đang phỏng vấn (tổng ba trạng thái)", async () => {
    stubFetch(routes());
    renderPipeline();

    await waitFor(() => expect(screen.getByTestId("count-total")).toHaveTextContent("12"));
    await waitFor(() => expect(screen.getByTestId("count-pending")).toHaveTextContent("4"));
    await waitFor(() => expect(screen.getByTestId("count-interviewing")).toHaveTextContent("6"));
    // Chỉ ba thẻ; không có thẻ thử việc (bộ lọc trạng thái vẫn liệt kê trạng thái thử việc).
    expect(screen.getAllByTestId(/^count-/).map((card) => card.dataset.testid)).toEqual([
      "count-total",
      "count-pending",
      "count-interviewing",
    ]);
  });

  it("API đếm lỗi thì cả ba thẻ báo lỗi, danh sách vẫn hiện", async () => {
    stubFetch(routes({ [COUNTS_ROUTE]: () => errorResponse(500, "internal", "boom") }));
    renderPipeline();

    expect(await screen.findByText("Trần Thị Ứng Viên")).toBeInTheDocument();
    for (const id of ["count-total", "count-pending", "count-interviewing"]) {
      await waitFor(() => expect(screen.getByTestId(id)).toHaveTextContent("Lỗi tải"));
    }
  });

  it("chỉ một request đếm; gõ tìm kiếm không tải lại; nút Làm mới tải lại cả danh sách và thẻ đếm", async () => {
    const { calls } = stubFetch(routes());
    renderPipeline();
    await screen.findByText("Trần Thị Ứng Viên");
    await waitFor(() => expect(countCalls(calls)).toHaveLength(1));
    // Không còn lời gọi danh sách page_size=1 để đếm.
    expect(listCalls(calls).some((call) => params(call).get("page_size") === "1")).toBe(false);

    await userEvent.type(screen.getByRole("searchbox", { name: "Tìm hồ sơ" }), "abc");
    await waitFor(() => expect(listCalls(calls).some((call) => params(call).get("q") === "abc")).toBe(true));
    expect(countCalls(calls)).toHaveLength(1);

    const listBefore = listCalls(calls).length;
    await userEvent.click(screen.getByRole("button", { name: "Làm mới" }));
    await waitFor(() => expect(countCalls(calls)).toHaveLength(2));
    await waitFor(() => expect(listCalls(calls).length).toBeGreaterThan(listBefore));
  });
});
