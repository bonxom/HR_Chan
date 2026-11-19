// API tin công khai: đường dẫn/tham số đúng backend, DTO riêng (không dùng kiểu Job HR).
/**
 * Contract (src/features/jobs/publicApi.ts + publicTypes.ts):
 *  - listPublicJobs({ page?, pageSize?, q?, departmentId? }, signal?) -> PublicJobPage
 *    GET /api/v1/public/jobs?page=&page_size=[&q=][&department_id=]; empty/blank q omitted.
 *  - getPublicJob(id, signal?) -> PublicJobDetail; GET /api/v1/public/jobs/{id}.
 *  - PublicJobSummary { id, title, departmentId, departmentName, headcount, workMode,
 *    location, deadline }; PublicJobDetail adds description, requirements, benefits.
 *  - No Authorization header (public, no account).
 */
import { describe, expect, it } from "vitest";
import { ApiError } from "@/shared/services/client";
import {
  publicJobDetailJson,
  publicJobJson,
  publicPage,
  stubFlowFetch,
  appError,
} from "@/test/publicFlowStub";
import { jsonResponse } from "@/test/apiStub";
import { getPublicJob, listPublicJobs } from "./publicApi";

describe("listPublicJobs", () => {
  it("gọi endpoint công khai với phân trang và ánh xạ DTO camelCase", async () => {
    const { calls } = stubFlowFetch({
      "GET /api/v1/public/jobs": () =>
        jsonResponse(publicPage([publicJobJson()], { total: 25, page: 2, page_size: 12 })),
    });

    const page = await listPublicJobs({ page: 2, pageSize: 12 });

    const url = new URL(calls[0].path, "http://localhost");
    expect(url.pathname).toBe("/api/v1/public/jobs");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("page_size")).toBe("12");
    expect(url.searchParams.has("q")).toBe(false);
    expect(url.searchParams.has("department_id")).toBe(false);
    expect(calls[0].headers.authorization).toBeUndefined();
    expect(page).toEqual({
      items: [
        {
          id: 11,
          title: "Kỹ sư dữ liệu",
          departmentId: 3,
          departmentName: "Phòng Kỹ thuật",
          headcount: 2,
          workMode: "Toàn thời gian",
          location: "Hà Nội",
          deadline: "2026-12-30",
        },
      ],
      total: 25,
      page: 2,
      pageSize: 12,
    });
  });

  it("gửi q đã trim và department_id; bỏ q rỗng", async () => {
    const { calls } = stubFlowFetch({
      "GET /api/v1/public/jobs": () => jsonResponse(publicPage([])),
    });

    await listPublicJobs({ page: 1, pageSize: 12, q: "  dữ liệu  ", departmentId: 3 });
    await listPublicJobs({ page: 1, pageSize: 12, q: "   " });

    const first = new URL(calls[0].path, "http://localhost").searchParams;
    expect(first.get("q")).toBe("dữ liệu");
    expect(first.get("department_id")).toBe("3");
    expect(new URL(calls[1].path, "http://localhost").searchParams.has("q")).toBe(false);
  });
});

describe("getPublicJob", () => {
  it("trả chi tiết công khai, không có trường nội bộ", async () => {
    stubFlowFetch({
      "GET /api/v1/public/jobs/11": () => jsonResponse(publicJobDetailJson()),
    });

    const job = await getPublicJob(11);

    expect(job).toEqual({
      id: 11,
      title: "Kỹ sư dữ liệu",
      departmentId: 3,
      departmentName: "Phòng Kỹ thuật",
      headcount: 2,
      workMode: "Toàn thời gian",
      location: "Hà Nội",
      deadline: "2026-12-30",
      description: "Xây dựng pipeline dữ liệu.",
      requirements: "Python, SQL.",
      benefits: "Bảo hiểm đầy đủ.",
    });
    for (const internal of ["criteria", "interviewers", "createdBy", "version", "status"]) {
      expect(job).not.toHaveProperty(internal);
    }
  });

  it("404 job_not_found thành ApiError", async () => {
    stubFlowFetch({
      "GET /api/v1/public/jobs/99": () => appError(404, "job_not_found", "Không tìm thấy tin."),
    });
    const caught = await getPublicJob(99).catch((error: unknown) => error);
    expect(caught).toBeInstanceOf(ApiError);
    expect(caught).toMatchObject({ status: 404, code: "job_not_found" });
  });
});
