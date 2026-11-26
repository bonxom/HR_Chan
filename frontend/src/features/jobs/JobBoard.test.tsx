// Trang việc làm công khai dùng API thật: loading/lỗi/thử lại/rỗng/tìm kiếm/phân trang, chỉ
// hiển thị dữ liệu API cung cấp (không mockStore, không lương/AI bịa), không gọi API HR.
/**
 * Contract (src/features/jobs/JobBoard.tsx):
 *  - Fetches listPublicJobs via TanStack Query: GET /api/v1/public/jobs?page=1&page_size=N.
 *  - Loading: role="status" /đang tải/i. Error: role="alert" + button /thử lại/i (refetch).
 *    Empty: /chưa có vị trí|không tìm thấy vị trí/i.
 *  - Search: textbox /tìm kiếm/i submitted with Enter or button /tìm/i -> q=... and page=1.
 *  - Pagination: buttons /trang sau/i and /trang trước/i driven by total/page/page_size.
 *  - Cards show title, department_name, location, deadline; link to /jobs/{id};
 *    button /ứng tuyển/i opens <ApplyModal preselectedJob={{ id, title, ... }} />.
 *  - Never calls /api/v1/departments or /api/v1/jobs (HR API).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "@/test/apiStub";
import {
  appError,
  publicJobJson,
  publicPage,
  stubFlowFetch,
  type FlowRequest,
} from "@/test/publicFlowStub";
import { JobBoard } from "./JobBoard";

vi.mock("@/features/candidates/ApplyModal", () => ({
  ApplyModal: ({
    isOpen,
    preselectedJob,
  }: {
    isOpen: boolean;
    preselectedJob?: { id: number; title: string } | null;
  }) =>
    isOpen ? (
      <div data-testid="apply-modal">{preselectedJob ? preselectedJob.title : "chưa chọn tin"}</div>
    ) : null,
}));

vi.mock("@/shared/services/mockStore", () => {
  throw new Error("JobBoard must not use mockStore");
});

function renderBoard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<JobBoard />} />
          <Route path="/jobs/:id" element={<div>Trang chi tiết</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const params = (call: FlowRequest) => new URL(call.path, "http://localhost").searchParams;
const listCalls = (calls: FlowRequest[]) =>
  calls.filter((call) => call.path.startsWith("/api/v1/public/jobs"));

describe("JobBoard", () => {
  it("hiển thị trạng thái tải rồi các tin từ API công khai", async () => {
    let release: () => void = () => {};
    const { calls } = stubFlowFetch({
      "GET /api/v1/public/jobs": () =>
        new Promise<Response>((resolve) => {
          release = () =>
            resolve(
              jsonResponse(
                publicPage([
                  publicJobJson(),
                  publicJobJson({
                    id: 12,
                    title: "Nhân viên kinh doanh",
                    department_name: "Phòng Kinh doanh",
                    location: "TP. Hồ Chí Minh",
                  }),
                ]),
              ),
            );
        }),
    });
    renderBoard();

    expect(await screen.findByRole("status")).toHaveTextContent(/đang tải/i);
    release();

    expect(await screen.findByText("Kỹ sư dữ liệu")).toBeInTheDocument();
    expect(screen.getByText("Nhân viên kinh doanh")).toBeInTheDocument();
    expect(screen.getAllByText("Phòng Kỹ thuật").length).toBeGreaterThan(0);
    expect(screen.getByText(/TP\. Hồ Chí Minh/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /chi tiết/i })[0]).toHaveAttribute(
      "href",
      "/jobs/11",
    );
    // Danh sách tin chỉ hiện dữ liệu API trả về: không lương, không gợi ý AI, không
    // tiêu chí/phỏng vấn. Phần "Quy trình ứng tuyển" tĩnh nằm ngoài khu danh sách.
    expect(document.getElementById("jobs-list")?.textContent).not.toMatch(
      /💰|Mức lương|AI|tiêu chí|phỏng vấn/i,
    );
    expect(document.body.textContent).not.toMatch(/💰|Mức lương/i);
    expect(params(listCalls(calls)[0]).get("page")).toBe("1");
    for (const call of calls) {
      expect(call.path).not.toMatch(/^\/api\/v1\/(departments|jobs)(\/|\?|$)/);
    }
  });

  it("lỗi tải có nút thử lại gọi lại API", async () => {
    const user = userEvent.setup();
    let attempt = 0;
    const { calls } = stubFlowFetch({
      "GET /api/v1/public/jobs": () =>
        attempt++ === 0
          ? appError(503, "unavailable", "Máy chủ bận")
          : jsonResponse(publicPage([publicJobJson()])),
    });
    renderBoard();

    const alert = await screen.findByRole("alert");
    await user.click(within(alert).getByRole("button", { name: /thử lại/i }));

    expect(await screen.findByText("Kỹ sư dữ liệu")).toBeInTheDocument();
    expect(listCalls(calls)).toHaveLength(2);
  });

  it("danh sách rỗng hiển thị thông báo, không bịa tin", async () => {
    stubFlowFetch({ "GET /api/v1/public/jobs": () => jsonResponse(publicPage([])) });
    renderBoard();
    expect(await screen.findByText(/chưa có vị trí|không tìm thấy vị trí/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ứng tuyển/i })).not.toBeInTheDocument();
  });

  it("tìm kiếm gửi q lên server và quay về trang 1", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch({
      "GET /api/v1/public/jobs": (request) =>
        params(request).get("q")
          ? jsonResponse(publicPage([publicJobJson({ id: 12, title: "Kỹ sư dữ liệu cấp cao" })]))
          : jsonResponse(publicPage([publicJobJson()])),
    });
    renderBoard();
    await screen.findByText("Kỹ sư dữ liệu");

    await user.type(screen.getByRole("textbox", { name: /tìm kiếm/i }), "cấp cao{Enter}");

    expect(await screen.findByText("Kỹ sư dữ liệu cấp cao")).toBeInTheDocument();
    const last = listCalls(calls).at(-1)!;
    expect(params(last).get("q")).toBe("cấp cao");
    expect(params(last).get("page")).toBe("1");
  });

  it("phân trang theo total/page_size của server", async () => {
    const user = userEvent.setup();
    const { calls } = stubFlowFetch({
      "GET /api/v1/public/jobs": (request) => {
        const page = Number(params(request).get("page"));
        const size = Number(params(request).get("page_size"));
        return jsonResponse(
          publicPage([publicJobJson({ id: page * 100, title: `Tin trang ${page}` })], {
            total: size * 2,
            page,
            page_size: size,
          }),
        );
      },
    });
    renderBoard();
    await screen.findByText("Tin trang 1");
    expect(screen.getByRole("button", { name: /trang trước/i })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /trang sau/i }));

    expect(await screen.findByText("Tin trang 2")).toBeInTheDocument();
    expect(params(listCalls(calls).at(-1)!).get("page")).toBe("2");
    expect(screen.getByRole("button", { name: /trang sau/i })).toBeDisabled();
  });

  it("nút ứng tuyển mở ApplyModal với đúng tin công khai", async () => {
    const user = userEvent.setup();
    stubFlowFetch({ "GET /api/v1/public/jobs": () => jsonResponse(publicPage([publicJobJson()])) });
    renderBoard();

    const card = (await screen.findByText("Kỹ sư dữ liệu")).closest("article, li, div")!;
    await user.click(within(card as HTMLElement).getByRole("button", { name: /ứng tuyển/i }));

    expect(screen.getByTestId("apply-modal")).toHaveTextContent("Kỹ sư dữ liệu");
  });

  it("nút tải CV chung mở ApplyModal chưa chọn tin", async () => {
    const user = userEvent.setup();
    stubFlowFetch({ "GET /api/v1/public/jobs": () => jsonResponse(publicPage([publicJobJson()])) });
    renderBoard();
    await screen.findByText("Kỹ sư dữ liệu");

    await user.click(screen.getByRole("button", { name: /tải cv/i }));

    await waitFor(() =>
      expect(screen.getByTestId("apply-modal")).toHaveTextContent("chưa chọn tin"),
    );
  });
});
