// Chi tiết tin công khai từ API thật: chỉ trường công khai, 404 rõ ràng, lỗi khác có thử lại,
// nút nộp hồ sơ mở ApplyModal với đúng tin; không lương/AI/tiêu chí bịa.
/**
 * Contract (src/features/jobs/JobDetail.tsx), route /jobs/:id:
 *  - getPublicJob(id) via TanStack Query: GET /api/v1/public/jobs/{id}.
 *  - Loading role="status"; 404 job_not_found -> /không tìm thấy/i with link back to "/";
 *    other errors -> role="alert" + /thử lại/i.
 *  - Shows title, department, location, deadline, headcount, description, requirements,
 *    benefits as returned. Button /nộp hồ sơ|ứng tuyển/i opens ApplyModal preselected.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { jsonResponse } from "@/test/apiStub";
import { appError, publicJobDetailJson, stubFlowFetch } from "@/test/publicFlowStub";
import { JobDetail } from "./JobDetail";

vi.mock("@/features/candidates/ApplyModal", () => ({
  ApplyModal: ({
    isOpen,
    preselectedJob,
  }: {
    isOpen: boolean;
    preselectedJob?: { id: number; title: string } | null;
  }) =>
    isOpen ? (
      <div data-testid="apply-modal">
        {preselectedJob?.id}:{preselectedJob?.title}
      </div>
    ) : null,
}));

vi.mock("@/shared/services/mockStore", () => {
  throw new Error("JobDetail must not use mockStore");
});

function renderDetail(id = "11") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/jobs/${id}`]}>
        <Routes>
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/" element={<div>Danh sách việc làm</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JobDetail", () => {
  it("hiển thị đúng dữ liệu công khai từ API", async () => {
    const { calls } = stubFlowFetch({
      "GET /api/v1/public/jobs/11": () => jsonResponse(publicJobDetailJson()),
    });
    renderDetail();

    expect(await screen.findByRole("heading", { name: "Kỹ sư dữ liệu" })).toBeInTheDocument();
    for (const text of [
      "Phòng Kỹ thuật",
      "Hà Nội",
      "Xây dựng pipeline dữ liệu.",
      "Python, SQL.",
      "Bảo hiểm đầy đủ.",
    ]) {
      expect(screen.getByText(text, { exact: false })).toBeInTheDocument();
    }
    expect(document.body.textContent).not.toMatch(/Mức lương|Thỏa thuận|AI|tiêu chí|phỏng vấn/i);
    expect(calls.map((call) => call.path)).toEqual(["/api/v1/public/jobs/11"]);
  });

  it("tin không công khai (404) báo không tìm thấy và có đường quay lại", async () => {
    stubFlowFetch({
      "GET /api/v1/public/jobs/99": () => appError(404, "job_not_found", "Không tìm thấy tin."),
    });
    renderDetail("99");

    expect(await screen.findByText(/không tìm thấy/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /quay lại/i })).toHaveAttribute("href", "/");
  });

  it("lỗi khác có nút thử lại", async () => {
    const user = userEvent.setup();
    let attempt = 0;
    stubFlowFetch({
      "GET /api/v1/public/jobs/11": () =>
        attempt++ === 0 ? appError(503, "unavailable", "bận") : jsonResponse(publicJobDetailJson()),
    });
    renderDetail();

    await user.click(await screen.findByRole("button", { name: /thử lại/i }));
    expect(await screen.findByRole("heading", { name: "Kỹ sư dữ liệu" })).toBeInTheDocument();
  });

  it("nộp hồ sơ mở ApplyModal với đúng tin", async () => {
    const user = userEvent.setup();
    stubFlowFetch({ "GET /api/v1/public/jobs/11": () => jsonResponse(publicJobDetailJson()) });
    renderDetail();

    await user.click(await screen.findByRole("button", { name: /nộp hồ sơ|ứng tuyển/i }));
    expect(screen.getByTestId("apply-modal")).toHaveTextContent("11:Kỹ sư dữ liệu");
  });
});
