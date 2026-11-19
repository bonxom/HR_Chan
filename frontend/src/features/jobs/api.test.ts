// Kiểm hợp đồng HTTP và mapping snake_case/camelCase bằng response giả.
// Request phải giữ đúng method, payload và version, không chỉ đúng dữ liệu hiển thị.
import { describe, expect, it } from "vitest";
import { ApiError } from "@/shared/services/client";
import { errorResponse, jsonResponse, stubFetch } from "@/test/apiStub";
import { jobDetailJson, jobSummaryJson } from "@/test/fixtures";
import {
  closeJob,
  createJob,
  deleteDraftJob,
  describeJobError,
  getJob,
  listCriteriaVersions,
  listDepartments,
  listInterviewers,
  listJobs,
  publishJob,
  saveCriteria,
  updateJob,
} from "./api";
import type { JobFieldsInput } from "./types";

const fields: JobFieldsInput = {
  title: "Lập trình viên",
  departmentId: 1,
  description: "Mô tả",
  requirements: "Yêu cầu",
  benefits: "",
  headcount: 2,
  workMode: "Toàn thời gian – Hybrid",
  location: "",
  deadline: "2026-12-31",
};

describe("jobs api", () => {
  it("lists jobs with only the filters that are set and maps the page", async () => {
    const { calls } = stubFetch({
      "GET /api/v1/jobs": () =>
        jsonResponse({ items: [jobSummaryJson()], total: 21, page: 2, page_size: 20 }),
    });

    const page = await listJobs("token", { page: 2, pageSize: 20, q: "python", status: "OPEN", departmentId: 3 });

    expect(calls[0].path).toBe("/api/v1/jobs?page=2&page_size=20&q=python&status=OPEN&department_id=3");
    expect(calls[0].headers.authorization).toBe("Bearer token");
    expect(page.total).toBe(21);
    expect(page.pageSize).toBe(20);
    expect(page.items[0]).toMatchObject({
      id: 1,
      departmentName: "Phòng Kỹ thuật",
      status: "DRAFT",
      workMode: "Hybrid",
      location: "Hà Nội",
    });
  });

  it("omits empty filters", async () => {
    const { calls } = stubFetch({
      "GET /api/v1/jobs": () => jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
    });
    await listJobs("token", { q: "", page: 1 });
    expect(calls[0].path).toBe("/api/v1/jobs?page=1");
  });

  it("maps job detail and converts decimal strings to numbers", async () => {
    stubFetch({ "GET /api/v1/jobs/7": () => jsonResponse(jobDetailJson({ id: 7 })) });

    const job = await getJob("token", 7);

    expect(job.workMode).toBe("Hybrid");
    expect(job.currentCriteria?.autoInviteThreshold).toBe(75);
    expect(job.currentCriteria?.criteria[0].weight).toBe(60);
    expect(job.interviewers[0]).toEqual({ id: "iv-1", fullName: "Người Phỏng Vấn" });
  });

  it("creates a job with snake_case fields, blanks as null and the criteria set", async () => {
    const { calls } = stubFetch({ "POST /api/v1/jobs": () => jsonResponse(jobDetailJson(), 201) });

    await createJob("token", {
      ...fields,
      publish: true,
      criteria: {
        autoInviteThreshold: null,
        interviewerIds: ["iv-1"],
        criteria: [{ name: "Python", description: "Kinh nghiệm", isMandatory: true, weight: 100 }],
      },
    });

    expect(calls[0].method).toBe("POST");
    expect(calls[0].body).toEqual({
      title: "Lập trình viên",
      department_id: 1,
      description: "Mô tả",
      requirements: "Yêu cầu",
      benefits: null,
      headcount: 2,
      work_mode: "Toàn thời gian – Hybrid",
      location: null,
      deadline: "2026-12-31",
      publish: true,
      criteria: {
        auto_invite_threshold: null,
        interviewer_ids: ["iv-1"],
        criteria: [{ name: "Python", description: "Kinh nghiệm", is_mandatory: true, weight: 100 }],
      },
    });
  });

  it("sends the row version on every write", async () => {
    const { calls } = stubFetch({
      "PUT /api/v1/jobs/7": () => jsonResponse(jobDetailJson({ id: 7 })),
      "POST /api/v1/jobs/7/publish": () => jsonResponse(jobDetailJson({ id: 7 })),
      "POST /api/v1/jobs/7/close": () => jsonResponse(jobDetailJson({ id: 7 })),
      "PUT /api/v1/jobs/7/criteria": () => jsonResponse(jobDetailJson({ id: 7 })),
    });

    await updateJob("token", 7, fields, 3);
    await publishJob("token", 7, 4);
    await closeJob("token", 7, 5);
    await saveCriteria("token", 7, { autoInviteThreshold: 80, criteria: [], interviewerIds: ["iv-1"] }, 6);

    expect(calls.map((call) => [call.method, call.path])).toEqual([
      ["PUT", "/api/v1/jobs/7"],
      ["POST", "/api/v1/jobs/7/publish"],
      ["POST", "/api/v1/jobs/7/close"],
      ["PUT", "/api/v1/jobs/7/criteria"],
    ]);
    expect((calls[0].body as { version: number }).version).toBe(3);
    expect(calls[1].body).toEqual({ version: 4 });
    expect(calls[2].body).toEqual({ version: 5 });
    expect(calls[3].body).toEqual({
      version: 6,
      auto_invite_threshold: 80,
      criteria: [],
      interviewer_ids: ["iv-1"],
    });
  });

  it("reads departments, interviewers and criteria versions", async () => {
    stubFetch({
      "GET /api/v1/departments": () => jsonResponse([{ id: 1, name: "Phòng Kỹ thuật", is_active: true }]),
      "GET /api/v1/interviewers": () => jsonResponse([{ id: "iv-1", full_name: "Người Phỏng Vấn" }]),
      "GET /api/v1/jobs/7/criteria/versions": () =>
        jsonResponse([jobDetailJson().current_criteria]),
    });

    expect(await listDepartments("token")).toEqual([{ id: 1, name: "Phòng Kỹ thuật", isActive: true }]);
    expect(await listInterviewers("token")).toEqual([{ id: "iv-1", fullName: "Người Phỏng Vấn" }]);
    const versions = await listCriteriaVersions("token", 7);
    expect(versions[0]).toMatchObject({ versionNo: 1, autoInviteThreshold: 75 });
  });

  it("describes errors with the backend message for business failures", async () => {
    stubFetch({
      "POST /api/v1/jobs/7/publish": () =>
        errorResponse(422, "job_rule_violation", "Bộ tiêu chí phải có ít nhất 1 người phỏng vấn"),
    });
    const error = await publishJob("token", 7, 1).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(describeJobError(error)).toBe("Bộ tiêu chí phải có ít nhất 1 người phỏng vấn");
    expect(describeJobError(new ApiError(409, "version_conflict", "Tin đã thay đổi"))).toBe("Tin đã thay đổi");
    expect(describeJobError(new ApiError(403, "forbidden", "x"))).toBe(
      "Bạn không có quyền thực hiện thao tác này.",
    );
    expect(describeJobError(new Error("network"))).toBe("Không thể hoàn tất thao tác. Vui lòng thử lại.");
    // FastAPI's default validation 422 has no `error.message`; show a readable message instead.
    expect(describeJobError(new ApiError(422, "request_failed", "Request failed (422)"))).toBe(
      "Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại các trường đã nhập.",
    );
  });
});

describe("jobs api — xóa bản nháp và ngày đủ hạn xóa", () => {
  it("xóa bản nháp gửi DELETE kèm version đang hiển thị và nhận 204 không có nội dung", async () => {
    const { calls } = stubFetch({ "DELETE /api/v1/jobs/7": () => jsonResponse(null, 204) });

    await expect(deleteDraftJob("token", 7, 3)).resolves.toBeUndefined();

    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].path).toBe("/api/v1/jobs/7");
    expect(calls[0].body).toEqual({ version: 3 });
    expect(calls[0].headers.authorization).toBe("Bearer token");
  });

  it("lỗi xóa giữ nguyên mã lỗi của backend (409 xung đột, 404 không còn tin)", async () => {
    stubFetch({
      "DELETE /api/v1/jobs/7": () =>
        errorResponse(409, "version_conflict", "Tin tuyển dụng đã được người khác thay đổi."),
      "DELETE /api/v1/jobs/8": () => errorResponse(404, "job_not_found", "Không tìm thấy tin tuyển dụng"),
    });

    const conflict = await deleteDraftJob("token", 7, 1).catch((caught: unknown) => caught);
    expect(conflict).toBeInstanceOf(ApiError);
    expect((conflict as ApiError).status).toBe(409);
    expect(describeJobError(conflict)).toBe("Tin tuyển dụng đã được người khác thay đổi.");

    const missing = await deleteDraftJob("token", 8, 1).catch((caught: unknown) => caught);
    expect((missing as ApiError).status).toBe(404);
    expect(describeJobError(missing)).toBe("Không tìm thấy tin tuyển dụng.");
  });

  it("ánh xạ deletion_due_date của backend cho danh sách và chi tiết, null khi không có", async () => {
    stubFetch({
      "GET /api/v1/jobs": () =>
        jsonResponse({
          items: [
            jobSummaryJson({ id: 1, status: "DRAFT", deletion_due_date: null }),
            jobSummaryJson({
              id: 2,
              status: "CLOSED",
              closed_at: "2026-11-17T03:00:00Z",
              deletion_due_date: "2028-11-17",
            }),
          ],
          total: 2,
          page: 1,
          page_size: 20,
        }),
      "GET /api/v1/jobs/2": () =>
        jsonResponse(
          jobDetailJson({
            id: 2,
            status: "CLOSED",
            closed_at: "2026-11-17T03:00:00Z",
            deletion_due_date: "2028-11-17",
          }),
        ),
    });

    const page = await listJobs("token");
    const [draft, closed] = page.items;
    expect(closed.deletionDueDate).toBe("2028-11-17");
    // Taken from the backend as is, never computed on the client.
    expect(draft.deletionDueDate).toBeNull();

    const detail = await getJob("token", 2);
    expect(detail.deletionDueDate).toBe("2028-11-17");
  });
});
