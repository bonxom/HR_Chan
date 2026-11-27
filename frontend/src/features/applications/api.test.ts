// Kiểm lớp gọi API xét duyệt hồ sơ: tham số, đổi tên trường, null, tên CV dự phòng và lỗi.
import { describe, expect, it } from "vitest";
import { ApiError } from "@/shared/services/client";
import { errorResponse, jsonResponse, stubFetch } from "@/test/apiStub";
import { applicationDetailJson, applicationSummaryJson } from "@/test/fixtures";
import {
  describeApplicationError,
  getApplicationCounts,
  downloadApplicationCv,
  getApplication,
  getInterviewSlots,
  inviteApplication,
  listApplications,
  rejectApplication,
} from "./api";

const TOKEN = "hr-token";
const page = (items: unknown[], total = items.length) => jsonResponse({ items, total, page: 1, page_size: 20 });

describe("listApplications", () => {
  it("gửi page, page_size, q đã trim, status và đổi sang camelCase", async () => {
    const { calls } = stubFetch({ "GET /api/v1/applications": () => page([applicationSummaryJson()], 41) });

    const result = await listApplications(TOKEN, {
      page: 3,
      pageSize: 20,
      q: "  Trần  ",
      status: "PENDING_HR_REVIEW",
    });

    expect(calls[0].path).toBe("/api/v1/applications?page=3&page_size=20&q=Tr%E1%BA%A7n&status=PENDING_HR_REVIEW");
    expect(calls[0].headers.authorization).toBe(`Bearer ${TOKEN}`);
    expect(result.total).toBe(41);
    expect(result.items[0]).toEqual({
      id: 1,
      jobId: 1,
      jobTitle: "Lập trình viên Backend Python",
      fullName: "Trần Thị Ứng Viên",
      email: "ung.vien@example.com",
      submittedAt: "2026-11-27T00:25:19.606934+00:00",
      status: "PENDING_HR_REVIEW",
      aiStatus: "SCORED",
      aiTotalScore: 43.4,
      reviewDueAt: "2026-12-04T10:30:00+00:00",
      emailIssue: null,
      version: 2,
    });
  });

  it("bỏ q rỗng và status khi lọc tất cả", async () => {
    const { calls } = stubFetch({ "GET /api/v1/applications": () => page([]) });

    await listApplications(TOKEN, { page: 1, pageSize: 20, q: "   " });

    expect(calls[0].path).toBe("/api/v1/applications?page=1&page_size=20");
  });

  it("giữ điểm null (đang chấm) là null và nhận decimal dạng chuỗi", async () => {
    stubFetch({
      "GET /api/v1/applications": () =>
        page([
          applicationSummaryJson({ id: 1, ai_total_score: null, ai_status: "PENDING", status: "SCORING" }),
          applicationSummaryJson({ id: 2, ai_total_score: "70.50" }),
        ]),
    });

    const result = await listApplications(TOKEN, { page: 1, pageSize: 20 });

    expect(result.items[0].aiTotalScore).toBeNull();
    expect(result.items[1].aiTotalScore).toBe(70.5);
  });
});

describe("listApplications — sắp xếp", () => {
  it("gửi sort và order khi có", async () => {
    const { calls } = stubFetch({ "GET /api/v1/applications": () => page([]) });

    await listApplications(TOKEN, { page: 1, pageSize: 8, sort: "ai_total_score", order: "asc" });

    expect(calls[0].path).toBe("/api/v1/applications?page=1&page_size=8&sort=ai_total_score&order=asc");
  });
});

describe("getApplicationCounts", () => {
  it("gọi /counts và đổi by_status sang byStatus", async () => {
    const { calls } = stubFetch({
      "GET /api/v1/applications/counts": () =>
        jsonResponse({ total: 5, overdue: 1, by_status: { PENDING_HR_REVIEW: 3, SCORING: 2 } }),
    });

    const counts = await getApplicationCounts(TOKEN);

    expect(calls[0].headers.authorization).toBe(`Bearer ${TOKEN}`);
    expect(counts).toEqual({ total: 5, overdue: 1, byStatus: { PENDING_HR_REVIEW: 3, SCORING: 2 } });
  });
});

describe("getApplication", () => {
  it("đổi chi tiết; chỉ tiêu chí bắt buộc có điểm sàn và kết quả", async () => {
    stubFetch({
      "GET /api/v1/applications/1": () =>
        jsonResponse(applicationDetailJson({ hr_note: "Đạt ngưỡng – cần mời thủ công", email_issue: "BOUNCED" })),
    });

    const detail = await getApplication(TOKEN, 1);

    expect(detail.candidate).toEqual({
      id: 1,
      fullName: "Trần Thị Ứng Viên",
      email: "ung.vien@example.com",
      phone: "0900000000",
    });
    expect(detail.hrNote).toBe("Đạt ngưỡng – cần mời thủ công");
    expect(detail.emailIssue).toBe("BOUNCED");
    expect(detail.scores[0]).toEqual({
      criterionId: 1,
      name: "Kinh nghiệm Python",
      isMandatory: true,
      score: 5,
      weight: 40,
      aiComment: "Chưa thấy dự án Python thực tế.",
      minScore: 50,
      meetsMandatory: false,
    });
    expect(detail.scores[1].minScore).toBeUndefined();
    expect(detail.scores[1].meetsMandatory).toBeUndefined();
    expect(detail.statusHistory[1]).toEqual({
      at: "2026-11-27T00:25:48.323301+00:00",
      actorId: null,
      before: "SCORING",
      after: "PENDING_HR_REVIEW",
    });
    expect(detail.interview).toBeNull();
  });
});

describe("quyết định và khung giờ", () => {
  it("rejectApplication gửi mã lý do, nội dung đã trim và version", async () => {
    const { calls } = stubFetch({ "POST /api/v1/applications/1/reject": () => jsonResponse({ status: "REJECTED" }) });

    await rejectApplication(TOKEN, 1, { reasonCode: "OTHER", reasonText: "  Không phù hợp văn hóa  ", version: 2 });

    expect(calls[0].body).toEqual({ reason_code: "OTHER", reason_text: "Không phù hợp văn hóa", version: 2 });
  });

  it("rejectApplication bỏ reason_text rỗng", async () => {
    const { calls } = stubFetch({ "POST /api/v1/applications/1/reject": () => jsonResponse({}) });

    await rejectApplication(TOKEN, 1, { reasonCode: "SKILL_MISMATCH", reasonText: "  ", version: 2 });

    expect(calls[0].body).toEqual({ reason_code: "SKILL_MISMATCH", version: 2 });
  });

  it("getInterviewSlots gửi khoảng ngày, người phỏng vấn tùy chọn và đổi kết quả", async () => {
    const { calls } = stubFetch({
      "GET /api/v1/applications/1/interview-slots": () =>
        jsonResponse([{ start_at: "2026-12-02T08:00:00+07:00", end_at: "2026-12-02T09:00:00+07:00" }]),
    });

    const slots = await getInterviewSlots(TOKEN, 1, { dateFrom: "2026-12-01", dateTo: "2026-12-05" });
    await getInterviewSlots(TOKEN, 1, { dateFrom: "2026-12-01", dateTo: "2026-12-05", interviewerId: "iv-2" });

    expect(slots).toEqual([{ startAt: "2026-12-02T08:00:00+07:00", endAt: "2026-12-02T09:00:00+07:00" }]);
    expect(calls[0].path).toBe("/api/v1/applications/1/interview-slots?date_from=2026-12-01&date_to=2026-12-05");
    expect(calls[1].path).toBe(
      "/api/v1/applications/1/interview-slots?date_from=2026-12-01&date_to=2026-12-05&interviewer_id=iv-2",
    );
  });

  it("inviteApplication gửi nguyên start_at, version và bỏ interviewer_id khi không chọn", async () => {
    const { calls } = stubFetch({ "POST /api/v1/applications/1/invite": () => jsonResponse({}) });

    await inviteApplication(TOKEN, 1, { startAt: "2026-12-02T08:00:00+07:00", version: 2 });
    await inviteApplication(TOKEN, 1, { startAt: "2026-12-02T08:00:00+07:00", version: 2, interviewerId: "iv-2" });

    expect(calls[0].body).toEqual({ start_at: "2026-12-02T08:00:00+07:00", version: 2 });
    expect(calls[1].body).toEqual({ start_at: "2026-12-02T08:00:00+07:00", version: 2, interviewer_id: "iv-2" });
  });
});

describe("downloadApplicationCv", () => {
  function cvResponse(type: string, disposition?: string): Response {
    const headers: Record<string, string> = { "Content-Type": type };
    if (disposition) headers["Content-Disposition"] = disposition;
    return new Response("cv-bytes", { status: 200, headers });
  }

  it("dùng tên tệp của server khi có", async () => {
    stubFetch({
      "GET /api/v1/applications/9/cv": () => cvResponse("application/pdf", "attachment; filename*=UTF-8''cv%20goc.pdf"),
    });

    expect((await downloadApplicationCv(TOKEN, 9)).filename).toBe("cv goc.pdf");
  });

  it.each([
    ["application/pdf", "CV-hoso-9.pdf"],
    ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "CV-hoso-9.docx"],
    ["application/octet-stream", "CV-hoso-9"],
  ])("đặt tên dự phòng theo loại %s", async (type, expected) => {
    stubFetch({ "GET /api/v1/applications/9/cv": () => cvResponse(type) });

    expect((await downloadApplicationCv(TOKEN, 9)).filename).toBe(expected);
  });
});

describe("describeApplicationError", () => {
  it.each([
    [errorResponse(409, "version_conflict", "Hồ sơ đã thay đổi, vui lòng tải lại"), "Hồ sơ đã thay đổi, vui lòng tải lại"],
    [errorResponse(409, "slot_conflict", "Khung giờ vừa có người đặt"), "Khung giờ vừa có người đặt"],
    [errorResponse(422, "interviewer_required", "Cần chọn người phỏng vấn"), "Cần chọn người phỏng vấn"],
    [errorResponse(503, "calendar_unavailable", "Không truy cập được lịch phỏng vấn"), "Không truy cập được lịch phỏng vấn"],
    [errorResponse(503, "configuration_error", "Thiếu cấu hình hạn phản hồi"), "Thiếu cấu hình hạn phản hồi"],
    [jsonResponse({ detail: [{ type: "missing", loc: ["body", "version"], msg: "Field required" }] }, 422),
      "Dữ liệu chưa hợp lệ. Vui lòng kiểm tra lại."],
    [errorResponse(403, "forbidden", "Forbidden"), "Bạn không có quyền thực hiện thao tác này."],
    [errorResponse(404, "application_not_found", "Không tìm thấy hồ sơ"), "Không tìm thấy hồ sơ ứng tuyển."],
    [errorResponse(500, "internal", "boom"), "Không thể hoàn tất thao tác. Vui lòng thử lại."],
  ])("thông điệp phù hợp cho phản hồi lỗi %#", async (response, expected) => {
    stubFetch({ "POST /api/v1/applications/1/reject": () => response });

    const caught = await rejectApplication(TOKEN, 1, { reasonCode: "NOT_QUALIFIED", version: 2 }).catch(
      (error: unknown) => error,
    );

    expect(caught).toBeInstanceOf(ApiError);
    expect(describeApplicationError(caught)).toBe(expected);
  });

  it("lỗi không phải ApiError dùng thông điệp chung", () => {
    expect(describeApplicationError(new TypeError("Failed to fetch"))).toBe(
      "Không thể hoàn tất thao tác. Vui lòng thử lại.",
    );
  });
});
