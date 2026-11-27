// Chi tiết hồ sơ và quyết định của HR trên API giả: điểm, tải CV, từ chối, mời phỏng vấn và lỗi.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CSRF_ROUTE, errorResponse, jsonResponse, stubFetch, type RecordedRequest, type RouteHandler } from "@/test/apiStub";
import { accountJson, applicationDetailJson, applicationSummaryJson, jobDetailJson } from "@/test/fixtures";
import { BY_STATUS, COUNTS_ROUTE, applicationsRoute, countsJson, countsRoute, renderPipeline } from "./testUtils";

const SLOTS = [
  { start_at: "2026-12-02T08:00:00+07:00", end_at: "2026-12-02T09:00:00+07:00" },
  { start_at: "2026-12-02T09:30:00+07:00", end_at: "2026-12-02T10:30:00+07:00" },
];

interface State {
  detail: ReturnType<typeof applicationDetailJson>;
  listStatus: string;
}

function routes(state: State, extra: Record<string, RouteHandler> = {}): Record<string, RouteHandler> {
  return {
    ...CSRF_ROUTE,
    "POST /api/v1/auth/refresh": () =>
      jsonResponse({ access_token: "hr-token", token_type: "bearer", expires_in: 300, account: accountJson() }),
    "GET /api/v1/auth/me": () => jsonResponse(accountJson()),
    "GET /api/v1/applications": applicationsRoute(() =>
      jsonResponse({
        items: [applicationSummaryJson({ status: state.listStatus as never })],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    ),
    [COUNTS_ROUTE]: countsRoute(),
    "GET /api/v1/applications/1": () => jsonResponse(state.detail),
    "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson()),
    "GET /api/v1/applications/1/interview-slots": () => jsonResponse(SLOTS),
    ...extra,
  };
}

function freshState(overrides: Parameters<typeof applicationDetailJson>[0] = {}): State {
  return { detail: applicationDetailJson(overrides), listStatus: "PENDING_HR_REVIEW" };
}

async function openDetail(options: { gcTime?: number } = {}) {
  renderPipeline(options);
  await userEvent.click(await screen.findByRole("button", { name: "Xem chi tiết hồ sơ Trần Thị Ứng Viên" }));
  return screen.findByRole("dialog");
}

const callsTo = (calls: RecordedRequest[], method: string, path: string) =>
  calls.filter((call) => call.method === method && call.path.split("?")[0] === path);

afterEach(() => vi.restoreAllMocks());

describe("Chi tiết hồ sơ", () => {
  it("hiển thị ứng viên, điểm từng tiêu chí, đóng góp, điểm sàn và lịch sử", async () => {
    stubFetch(routes(freshState({ hr_note: "Đạt ngưỡng – cần mời thủ công" })));
    const dialog = await openDetail();

    expect(await within(dialog).findByText("0900000000")).toBeInTheDocument();
    expect(within(dialog).getByText("ung.vien@example.com")).toBeInTheDocument();
    expect(within(dialog).getByText("Đạt ngưỡng – cần mời thủ công")).toBeInTheDocument();

    const mandatory = within(dialog).getByTestId("criterion-1");
    expect(within(mandatory).getByText("Kinh nghiệm Python")).toBeInTheDocument();
    expect(within(mandatory).getByText("Trọng số 40%")).toBeInTheDocument();
    expect(within(mandatory).getByText("5/100")).toBeInTheDocument();
    expect(within(mandatory).getByText("Đóng góp 2.0 điểm")).toBeInTheDocument();
    expect(within(mandatory).getByText("Điểm sàn 50")).toBeInTheDocument();
    expect(within(mandatory).getByText("Chưa đạt tiêu chí bắt buộc")).toBeInTheDocument();
    expect(within(mandatory).getByText("Chưa thấy dự án Python thực tế.")).toBeInTheDocument();

    const optional = within(dialog).getByTestId("criterion-2");
    expect(within(optional).getByText("Đóng góp 34.7 điểm")).toBeInTheDocument();
    expect(within(optional).queryByText(/tiêu chí bắt buộc/)).not.toBeInTheDocument();
    expect(within(optional).queryByText(/Điểm sàn/)).not.toBeInTheDocument();

    const history = within(dialog).getByTestId("status-history");
    expect(within(history).getByText("Chờ HR duyệt")).toBeInTheDocument();
  });

  it("hiển thị lý do AI không chấm được và không có điểm 0 giả", async () => {
    stubFetch(
      routes(
        freshState({ ai_status: "NEEDS_REVIEW", ai_total_score: null, ai_failure_reason: "INVALID_AI_RESPONSE", scores: [] }),
      ),
    );
    const dialog = await openDetail();

    expect(await within(dialog).findByText(/INVALID_AI_RESPONSE/)).toBeInTheDocument();
    expect(within(dialog).getAllByText("AI không chấm được").length).toBeGreaterThan(0);
    expect(within(dialog).queryByText("0/100")).not.toBeInTheDocument();
  });

  it("mở lại chi tiết (còn cache) luôn gọi lại API và khóa quyết định đến khi tải xong", async () => {
    let release: (() => void) | null = null;
    let detailCalls = 0;
    const state = freshState();
    const { calls } = stubFetch(
      routes(state, {
        "GET /api/v1/applications/1": () => {
          detailCalls += 1;
          if (detailCalls === 1) return jsonResponse(state.detail);
          // Lần mở lại: bản mới có version khác, đến chậm.
          return new Promise<Response>((resolve) => {
            release = () => resolve(jsonResponse(applicationDetailJson({ version: 5 })));
          });
        },
        "POST /api/v1/applications/1/reject": () => jsonResponse({}),
      }),
    );
    // Cache giữ chi tiết sau khi đóng, giống ứng dụng thật.
    const dialog = await openDetail({ gcTime: 300_000 });
    await within(dialog).findByText("0900000000");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Xem chi tiết hồ sơ Trần Thị Ứng Viên" }));
    const reopened = await screen.findByRole("dialog");
    // Đang hiện bản cache cũ: không được cho quyết định.
    expect(await within(reopened).findByRole("button", { name: "Từ chối hồ sơ" })).toBeDisabled();
    expect(within(reopened).getByRole("button", { name: "Mời phỏng vấn" })).toBeDisabled();

    await waitFor(() => expect(release).not.toBeNull());
    release!();
    await waitFor(() => expect(within(reopened).getByRole("button", { name: "Từ chối hồ sơ" })).toBeEnabled());
    await userEvent.click(within(reopened).getByRole("button", { name: "Từ chối hồ sơ" }));
    await userEvent.click(within(reopened).getByRole("button", { name: "Xác nhận từ chối" }));

    await screen.findByText(/Đã từ chối hồ sơ/);
    expect(callsTo(calls, "GET", "/api/v1/applications/1")).toHaveLength(2);
    // Quyết định dùng version của bản vừa tải, không phải bản cache.
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")[0].body).toMatchObject({ version: 5 });
  });

  it("ẩn nút quyết định khi hồ sơ không còn chờ HR duyệt", async () => {
    stubFetch(routes(freshState({ status: "INTERVIEW_INVITED" })));
    const dialog = await openDetail();

    await within(dialog).findByText("0900000000");
    expect(within(dialog).queryByRole("button", { name: "Từ chối hồ sơ" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Mời phỏng vấn" })).not.toBeInTheDocument();
  });

  it("tải CV với tên tệp từ server và thu hồi object URL", async () => {
    const createObjectURL = vi.fn(() => "blob:cv-1");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL, revokeObjectURL }));
    const downloads: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download);
    });
    const { calls } = stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications/1/cv": () =>
          new Response("pdf", {
            status: 200,
            headers: {
              "Content-Type": "application/pdf",
              "Content-Disposition": "attachment; filename*=UTF-8''CV%20Tr%E1%BA%A7n.pdf",
            },
          }),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Tải CV" }));

    await waitFor(() => expect(downloads).toEqual(["CV Trần.pdf"]));
    expect(callsTo(calls, "GET", "/api/v1/applications/1/cv")[0].headers.authorization).toBe("Bearer hr-token");
    await waitFor(() => expect(revokeObjectURL).toHaveBeenCalledWith("blob:cv-1"));
  });

  it("nút Tải CV dùng tên dự phòng khi không đọc được tên, và làm mới phiên một lần khi gặp 401", async () => {
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:cv"), revokeObjectURL: vi.fn() }));
    const downloads: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download);
    });
    let cvCalls = 0;
    const { calls } = stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications/1/cv": () => {
          cvCalls += 1;
          if (cvCalls === 1) return errorResponse(401, "invalid_token", "Token expired");
          // Khác origin: trình duyệt ẩn Content-Disposition.
          return new Response("docx", {
            status: 200,
            headers: { "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
          });
        },
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Tải CV" }));

    await waitFor(() => expect(downloads).toEqual(["CV-hoso-1.docx"]));
    expect(callsTo(calls, "GET", "/api/v1/applications/1/cv")).toHaveLength(2);
    expect(callsTo(calls, "POST", "/api/v1/auth/refresh").length).toBeGreaterThanOrEqual(2);
  });

  it("nút Tải CV dùng tên dự phòng .pdf cho CV PDF khi không đọc được tên", async () => {
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:cv"), revokeObjectURL: vi.fn() }));
    const downloads: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      downloads.push(this.download);
    });
    stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications/1/cv": () =>
          new Response("pdf", { status: 200, headers: { "Content-Type": "application/pdf" } }),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Tải CV" }));

    await waitFor(() => expect(downloads).toEqual(["CV-hoso-1.pdf"]));
  });

  it("báo lỗi khi không tải được CV", async () => {
    stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications/1/cv": () => errorResponse(503, "cv_unavailable", "Không đọc được CV"),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Tải CV" }));

    expect(await within(dialog).findByText("Không đọc được CV")).toBeInTheDocument();
  });
});

describe("Từ chối hồ sơ", () => {
  it("gửi mã lý do và version; thành công thì báo email đã xếp hàng, đóng và làm mới", async () => {
    const state = freshState();
    const { calls } = stubFetch(
      routes(state, {
        "POST /api/v1/applications/1/reject": () => {
          state.listStatus = "REJECTED";
          return jsonResponse({ status: "REJECTED" });
        },
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Từ chối hồ sơ" }));
    await userEvent.selectOptions(within(dialog).getByRole("combobox", { name: "Lý do từ chối" }), "SKILL_MISMATCH");
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận từ chối" }));

    expect(
      await screen.findByText("Đã từ chối hồ sơ. Thư cảm ơn đã được xếp hàng gửi tới ứng viên."),
    ).toBeInTheDocument();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")[0].body).toEqual({
      reason_code: "SKILL_MISMATCH",
      version: 2,
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // Danh sách tải lại và hiện trạng thái mới.
    const row = (await screen.findByText("Trần Thị Ứng Viên")).closest("tr") as HTMLElement;
    expect(await within(row).findByText("Đã từ chối")).toBeInTheDocument();
  });

  it("Lý do khác bắt buộc nội dung không chỉ khoảng trắng; tối đa 500 ký tự", async () => {
    const { calls } = stubFetch(routes(freshState(), { "POST /api/v1/applications/1/reject": () => jsonResponse({}) }));
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Từ chối hồ sơ" }));
    await userEvent.selectOptions(within(dialog).getByRole("combobox", { name: "Lý do từ chối" }), "OTHER");
    const text = within(dialog).getByRole("textbox", { name: "Ghi chú lý do" });
    await userEvent.type(text, "   ");
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận từ chối" }));
    expect(await within(dialog).findByText("Vui lòng nhập lý do khác.")).toBeInTheDocument();

    await userEvent.clear(text);
    await userEvent.click(text);
    await userEvent.paste("x".repeat(501));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận từ chối" }));
    expect(await within(dialog).findByText("Lý do tối đa 500 ký tự.")).toBeInTheDocument();

    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(0);
  });

  it("409 hiển thị thông điệp backend, tải lại chi tiết, danh sách và thẻ đếm; không tự gửi lại", async () => {
    const state = freshState();
    let pendingTotal = 4;
    const { calls } = stubFetch(
      routes(state, {
        [COUNTS_ROUTE]: () => jsonResponse(countsJson({ ...BY_STATUS, PENDING_HR_REVIEW: pendingTotal })),
        "POST /api/v1/applications/1/reject": () => {
          // Người khác vừa mời phỏng vấn hồ sơ này.
          state.detail = applicationDetailJson({ status: "INTERVIEW_INVITED", version: 3 });
          state.listStatus = "INTERVIEW_INVITED";
          pendingTotal = 3;
          return errorResponse(409, "invalid_application_state", "Hồ sơ không còn chờ xét duyệt");
        },
      }),
    );
    const dialog = await openDetail();
    await waitFor(() => expect(screen.getByTestId("count-pending")).toHaveTextContent("4"));

    await userEvent.click(await within(dialog).findByRole("button", { name: "Từ chối hồ sơ" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận từ chối" }));

    expect(await within(dialog).findByText("Hồ sơ không còn chờ xét duyệt")).toBeInTheDocument();
    // Chi tiết mới: không còn nút quyết định.
    await waitFor(() =>
      expect(within(dialog).queryByRole("button", { name: "Từ chối hồ sơ" })).not.toBeInTheDocument(),
    );
    const row = screen.getAllByText("Trần Thị Ứng Viên").map((node) => node.closest("tr")).find(Boolean) as HTMLElement;
    expect(await within(row).findByText("Đã mời phỏng vấn")).toBeInTheDocument();
    // Thẻ đếm hiện số liệu mới sau khi tải lại.
    await waitFor(() => expect(screen.getByTestId("count-pending")).toHaveTextContent("3"));
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(1);
  });

  it("lỗi mạng, 422 và 503 không tự gửi lại; 401 được gửi lại đúng một lần sau khi làm mới phiên", async () => {
    let attempt = 0;
    const { calls } = stubFetch(
      routes(freshState(), {
        "POST /api/v1/applications/1/reject": () => {
          attempt += 1;
          if (attempt === 1) throw new TypeError("Failed to fetch");
          if (attempt === 2) return errorResponse(422, "invalid_reason", "Lý do không hợp lệ");
          if (attempt === 3) return errorResponse(503, "configuration_error", "Thiếu cấu hình hạn phản hồi");
          if (attempt === 4) return errorResponse(401, "invalid_token", "Token expired");
          return jsonResponse({});
        },
      }),
    );
    const dialog = await openDetail();
    const confirm = async () => {
      await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận từ chối" }));
    };

    await userEvent.click(await within(dialog).findByRole("button", { name: "Từ chối hồ sơ" }));
    await confirm();
    expect(await within(dialog).findByText("Không thể hoàn tất thao tác. Vui lòng thử lại.")).toBeInTheDocument();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(1);

    await confirm();
    expect(await within(dialog).findByText("Lý do không hợp lệ")).toBeInTheDocument();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(2);

    await confirm();
    expect(await within(dialog).findByText("Thiếu cấu hình hạn phản hồi")).toBeInTheDocument();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(3);

    await confirm();
    expect(await screen.findByText(/Đã từ chối hồ sơ/)).toBeInTheDocument();
    // Lần 4 gặp 401, AuthProvider làm mới phiên và gửi lại đúng một lần (lần 5).
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(5);
  });

  it("không đóng được cửa sổ khi đang gửi quyết định", async () => {
    let release!: () => void;
    const { calls } = stubFetch(
      routes(freshState(), {
        "POST /api/v1/applications/1/reject": () =>
          new Promise<Response>((resolve) => {
            release = () => resolve(jsonResponse({}));
          }),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Từ chối hồ sơ" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận từ chối" }));
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Xác nhận từ chối" })).toBeDisabled());
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    release();
    await screen.findByText(/Đã từ chối hồ sơ/);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(1);
  });

  it("quyết định làm trống trang cuối thì lùi về trang trước", async () => {
    let total = 21;
    stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications": applicationsRoute((request) => {
          const pageNo = Number(new URL(request.path, "http://localhost").searchParams.get("page"));
          const items =
            pageNo === 2 && total === 21
              ? [applicationSummaryJson()]
              : pageNo === 1
                ? [applicationSummaryJson({ id: 2, full_name: "Người Trang Một" })]
                : [];
          return jsonResponse({ items, total, page: pageNo, page_size: 20 });
        }),
        "POST /api/v1/applications/1/reject": () => {
          total = 20;
          return jsonResponse({});
        },
      }),
    );
    renderPipeline();
    await screen.findByText("Người Trang Một");
    await userEvent.click(screen.getByRole("button", { name: "Trang sau" }));
    await userEvent.click(await screen.findByRole("button", { name: "Xem chi tiết hồ sơ Trần Thị Ứng Viên" }));
    const dialog = await screen.findByRole("dialog");

    await userEvent.click(await within(dialog).findByRole("button", { name: "Từ chối hồ sơ" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận từ chối" }));

    expect(await screen.findByText("Người Trang Một")).toBeInTheDocument();
    expect(screen.getByText("Trang 1 / 1")).toBeInTheDocument();
  });

  it("khóa nút trong lúc đang gửi để không gửi hai lần", async () => {
    let release!: () => void;
    const { calls } = stubFetch(
      routes(freshState(), {
        "POST /api/v1/applications/1/reject": () =>
          new Promise<Response>((resolve) => {
            release = () => resolve(jsonResponse({}));
          }),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Từ chối hồ sơ" }));
    const confirm = within(dialog).getByRole("button", { name: "Xác nhận từ chối" });
    await userEvent.click(confirm);
    await waitFor(() => expect(confirm).toBeDisabled());
    await userEvent.click(confirm);
    release();

    await screen.findByText(/Đã từ chối hồ sơ/);
    expect(callsTo(calls, "POST", "/api/v1/applications/1/reject")).toHaveLength(1);
  });
});

describe("Mời phỏng vấn", () => {
  it("một người phỏng vấn: không gửi interviewer_id, chọn khung giờ và gửi nguyên start_at", async () => {
    const { calls } = stubFetch(
      routes(freshState(), { "POST /api/v1/applications/1/invite": () => jsonResponse({}) }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    expect(await within(dialog).findByText("Người Phỏng Vấn")).toBeInTheDocument();
    expect(within(dialog).queryByRole("combobox", { name: "Người phỏng vấn" })).not.toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận mời" }));

    expect(
      await screen.findByText("Đã mời phỏng vấn. Thư mời đã được xếp hàng gửi tới ứng viên."),
    ).toBeInTheDocument();
    const slotCall = callsTo(calls, "GET", "/api/v1/applications/1/interview-slots")[0];
    expect(slotCall.path).not.toContain("interviewer_id");
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")[0].body).toEqual({
      start_at: "2026-12-02T08:00:00+07:00",
      version: 2,
    });
  });

  it("nhiều người phỏng vấn: bắt buộc chọn, đổi người hoặc ngày thì bỏ khung giờ đã chọn", async () => {
    const { calls } = stubFetch(
      routes(freshState(), {
        "GET /api/v1/jobs/1": () =>
          jsonResponse(
            jobDetailJson({
              interviewers: [
                { id: "iv-1", full_name: "Người Phỏng Vấn" },
                { id: "iv-2", full_name: "Trưởng Nhóm" },
              ],
            }),
          ),
        "POST /api/v1/applications/1/invite": () => jsonResponse({}),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    const interviewer = await within(dialog).findByRole("combobox", { name: "Người phỏng vấn" });
    expect(within(dialog).getByRole("button", { name: "Tìm khung giờ" })).toBeDisabled();

    await userEvent.selectOptions(interviewer, "iv-2");
    await userEvent.click(within(dialog).getByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" }));
    expect(within(dialog).getByRole("button", { name: "Xác nhận mời" })).toBeEnabled();

    await userEvent.selectOptions(interviewer, "iv-1");
    expect(within(dialog).queryByRole("radio", { name: "08:00 – 09:00, 02/12/2026" })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Xác nhận mời" })).toBeDisabled();

    await userEvent.click(within(dialog).getByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "09:30 – 10:30, 02/12/2026" }));
    const from = within(dialog).getByLabelText("Từ ngày");
    await userEvent.clear(from);
    await userEvent.type(from, "2026-12-03");
    expect(within(dialog).getByRole("button", { name: "Xác nhận mời" })).toBeDisabled();

    await userEvent.click(within(dialog).getByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "09:30 – 10:30, 02/12/2026" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận mời" }));

    await screen.findByText("Đã mời phỏng vấn. Thư mời đã được xếp hàng gửi tới ứng viên.");
    const slotPaths = callsTo(calls, "GET", "/api/v1/applications/1/interview-slots").map((call) => call.path);
    expect(slotPaths[0]).toContain("interviewer_id=iv-2");
    expect(slotPaths.at(-1)).toContain("date_from=2026-12-03");
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")[0].body).toEqual({
      start_at: "2026-12-02T09:30:00+07:00",
      version: 2,
      interviewer_id: "iv-1",
    });
  });

  it("tin không có người phỏng vấn thì không cho mời", async () => {
    stubFetch(routes(freshState(), { "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ interviewers: [] })) }));
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));

    expect(await within(dialog).findByText(/chưa có người phỏng vấn/i)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Tìm khung giờ" })).toBeDisabled();
  });

  it("không có khung giờ trống thì báo rõ", async () => {
    stubFetch(routes(freshState(), { "GET /api/v1/applications/1/interview-slots": () => jsonResponse([]) }));
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.click(await within(dialog).findByRole("button", { name: "Tìm khung giờ" }));

    expect(await within(dialog).findByText("Không có khung giờ trống")).toBeInTheDocument();
  });

  it("slot_conflict: báo lỗi, bỏ khung giờ đã chọn và tải lại khung giờ; không tự gửi lại", async () => {
    const { calls } = stubFetch(
      routes(freshState(), {
        "POST /api/v1/applications/1/invite": () => errorResponse(409, "slot_conflict", "Khung giờ vừa có người đặt"),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.click(await within(dialog).findByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận mời" }));

    expect(await within(dialog).findByText("Khung giờ vừa có người đặt")).toBeInTheDocument();
    await waitFor(() => expect(callsTo(calls, "GET", "/api/v1/applications/1/interview-slots")).toHaveLength(2));
    expect(within(dialog).getByRole("radio", { name: "08:00 – 09:00, 02/12/2026" })).not.toBeChecked();
    expect(within(dialog).getByRole("button", { name: "Xác nhận mời" })).toBeDisabled();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")).toHaveLength(1);
  });

  it("lỗi người phỏng vấn (422) tải lại danh sách người phỏng vấn của tin", async () => {
    const { calls } = stubFetch(
      routes(freshState(), {
        "POST /api/v1/applications/1/invite": () =>
          errorResponse(422, "invalid_interviewer", "Người phỏng vấn không thuộc tin"),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.click(await within(dialog).findByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" }));
    const jobCallsBefore = callsTo(calls, "GET", "/api/v1/jobs/1").length;
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận mời" }));

    expect(await within(dialog).findByText("Người phỏng vấn không thuộc tin")).toBeInTheDocument();
    await waitFor(() => expect(callsTo(calls, "GET", "/api/v1/jobs/1").length).toBeGreaterThan(jobCallsBefore));
  });

  it("lỗi lịch (503) khi tìm khung giờ hiển thị thông điệp backend", async () => {
    stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications/1/interview-slots": () =>
          errorResponse(503, "calendar_unavailable", "Không truy cập được lịch phỏng vấn"),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.click(await within(dialog).findByRole("button", { name: "Tìm khung giờ" }));

    expect(await within(dialog).findByText("Không truy cập được lịch phỏng vấn")).toBeInTheDocument();
  });

  it("bấm lại Tìm khung giờ với cùng đầu vào vẫn gọi lại API (thử lại sau lỗi)", async () => {
    let slotCalls = 0;
    const { calls } = stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications/1/interview-slots": () => {
          slotCalls += 1;
          return slotCalls === 1
            ? errorResponse(503, "calendar_unavailable", "Không truy cập được lịch phỏng vấn")
            : jsonResponse(SLOTS);
        },
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.click(await within(dialog).findByRole("button", { name: "Tìm khung giờ" }));
    expect(await within(dialog).findByText("Không truy cập được lịch phỏng vấn")).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Tìm khung giờ" }));

    expect(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" })).toBeInTheDocument();
    expect(callsTo(calls, "GET", "/api/v1/applications/1/interview-slots")).toHaveLength(2);
  });

  it("tìm lại khung giờ: khóa chọn khi đang tải, không xác nhận giờ không còn trong kết quả mới", async () => {
    let slotCalls = 0;
    let release: (() => void) | null = null;
    const { calls } = stubFetch(
      routes(freshState(), {
        "GET /api/v1/applications/1/interview-slots": () => {
          slotCalls += 1;
          if (slotCalls === 1) return jsonResponse(SLOTS);
          // Lần tìm lại đến chậm và khung 08:00 đã bị đặt.
          return new Promise<Response>((resolve) => {
            release = () => resolve(jsonResponse([SLOTS[1]]));
          });
        },
        "POST /api/v1/applications/1/invite": () => jsonResponse({}),
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.click(await within(dialog).findByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Tìm khung giờ" }));

    await waitFor(() => expect(release).not.toBeNull());
    // Đang tải lại: không chọn được giờ cũ, không xác nhận được.
    for (const radio of within(dialog).queryAllByRole("radio")) expect(radio).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Xác nhận mời" })).toBeDisabled();

    release!();
    // 09:30 đã có trong kết quả cũ, nên chờ đến khi 08:00 biến mất (kết quả mới đã về).
    await waitFor(() =>
      expect(within(dialog).queryByRole("radio", { name: "08:00 – 09:00, 02/12/2026" })).not.toBeInTheDocument(),
    );
    expect(within(dialog).getByRole("radio", { name: "09:30 – 10:30, 02/12/2026" })).toBeEnabled();
    expect(within(dialog).getByRole("button", { name: "Xác nhận mời" })).toBeDisabled();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")).toHaveLength(0);
  });

  it("mời: lỗi mạng và 503 không tự gửi lại; 401 được gửi lại đúng một lần", async () => {
    let attempt = 0;
    const { calls } = stubFetch(
      routes(freshState(), {
        "POST /api/v1/applications/1/invite": () => {
          attempt += 1;
          if (attempt === 1) throw new TypeError("Failed to fetch");
          if (attempt === 2) return errorResponse(503, "calendar_unavailable", "Không truy cập được lịch phỏng vấn");
          if (attempt === 3) return errorResponse(401, "invalid_token", "Token expired");
          return jsonResponse({});
        },
      }),
    );
    const dialog = await openDetail();
    const confirm = () => userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận mời" }));

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.click(await within(dialog).findByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" }));

    await confirm();
    expect(await within(dialog).findByText("Không thể hoàn tất thao tác. Vui lòng thử lại.")).toBeInTheDocument();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")).toHaveLength(1);

    await confirm();
    expect(await within(dialog).findByText("Không truy cập được lịch phỏng vấn")).toBeInTheDocument();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")).toHaveLength(2);

    await confirm();
    expect(await screen.findByText("Đã mời phỏng vấn. Thư mời đã được xếp hàng gửi tới ứng viên.")).toBeInTheDocument();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")).toHaveLength(4);
  });

  it("danh sách người phỏng vấn đổi sau 422 thì bỏ người và khung giờ đã chọn, không gửi lại", async () => {
    let interviewers = [
      { id: "iv-1", full_name: "Người Phỏng Vấn" },
      { id: "iv-2", full_name: "Trưởng Nhóm" },
    ];
    const { calls } = stubFetch(
      routes(freshState(), {
        "GET /api/v1/jobs/1": () => jsonResponse(jobDetailJson({ interviewers })),
        "POST /api/v1/applications/1/invite": () => {
          // HR khác vừa đổi người phỏng vấn của tin.
          interviewers = [{ id: "iv-3", full_name: "Người Mới" }];
          return errorResponse(422, "invalid_interviewer", "Người phỏng vấn không thuộc tin");
        },
      }),
    );
    const dialog = await openDetail();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Mời phỏng vấn" }));
    await userEvent.selectOptions(await within(dialog).findByRole("combobox", { name: "Người phỏng vấn" }), "iv-1");
    await userEvent.click(within(dialog).getByRole("button", { name: "Tìm khung giờ" }));
    await userEvent.click(await within(dialog).findByRole("radio", { name: "08:00 – 09:00, 02/12/2026" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Xác nhận mời" }));

    expect(await within(dialog).findByText("Người phỏng vấn không thuộc tin")).toBeInTheDocument();
    expect(await within(dialog).findByText("Người Mới")).toBeInTheDocument();
    // Khung giờ tìm cho người cũ không còn được dùng.
    expect(within(dialog).queryByRole("radio")).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Xác nhận mời" })).toBeDisabled();
    expect(callsTo(calls, "POST", "/api/v1/applications/1/invite")).toHaveLength(1);
  });
});
