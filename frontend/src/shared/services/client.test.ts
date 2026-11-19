// Kiểm lỗi HTTP/422 dùng chung và bảo đảm không giữ input nhạy cảm trong ApiError.
import { describe, expect, it } from "vitest";
import { errorResponse, jsonResponse, stubFetch } from "@/test/apiStub";
import { ApiError, apiRequest, type ApiValidationIssue } from "./client";

// Value the user typed; it must never be kept on the error object.
const SECRET_INPUT = "giá-trị-người-dùng-SECRET";

async function failureOf(path: string, method: "GET" | "POST" | "PUT" = "POST"): Promise<ApiError> {
  const caught = await apiRequest(path, { method, body: method === "GET" ? undefined : {} }).catch(
    (error: unknown) => error,
  );
  expect(caught).toBeInstanceOf(ApiError);
  return caught as ApiError;
}

describe("apiRequest — lỗi validation 422 mặc định của FastAPI", () => {
  it("giữ type/loc/msg và giới hạn số trong ctx, không giữ input hoặc url", async () => {
    stubFetch({
      "POST /api/v1/jobs": () =>
        jsonResponse(
          {
            detail: [
              {
                type: "string_too_short",
                loc: ["body", "criteria", "criteria", 0, "name"],
                msg: "String should have at least 1 character",
                input: SECRET_INPUT,
                ctx: { min_length: 1 },
                url: "https://errors.pydantic.dev/2/v/string_too_short",
              },
              {
                type: "less_than_equal",
                loc: ["body", "headcount"],
                msg: "Input should be less than or equal to 2147483647",
                input: 98765432109,
                ctx: { le: 2147483647 },
              },
              { type: "missing", loc: ["body", "title"], msg: "Field required", input: { note: SECRET_INPUT } },
            ],
          },
          422,
        ),
    });

    const error = await failureOf("/api/v1/jobs");

    expect(error.status).toBe(422);
    expect(error.code).toBe("request_failed");
    expect(error.message).toBe("Request failed (422)");
    const expected: ApiValidationIssue[] = [
      {
        type: "string_too_short",
        loc: ["body", "criteria", "criteria", 0, "name"],
        msg: "String should have at least 1 character",
        ctx: { min_length: 1 },
      },
      {
        type: "less_than_equal",
        loc: ["body", "headcount"],
        msg: "Input should be less than or equal to 2147483647",
        ctx: { le: 2147483647 },
      },
      { type: "missing", loc: ["body", "title"], msg: "Field required" },
    ];
    expect(error.validationIssues).toEqual(expected);
    for (const issue of error.validationIssues ?? []) expect(issue).not.toHaveProperty("input");
    const serialized = JSON.stringify(error) + JSON.stringify(error.validationIssues);
    expect(serialized).not.toContain(SECRET_INPUT);
    expect(serialized).not.toContain("98765432109");
  });

  it("chỉ giữ các phần tử detail đúng cấu trúc khi danh sách lẫn phần tử hỏng", async () => {
    stubFetch({
      "PUT /api/v1/jobs/1/criteria": () =>
        jsonResponse(
          {
            detail: [
              null,
              5,
              "loi",
              { loc: "body.title", type: "missing", msg: "Field required" },
              { loc: ["body", { bad: true }], type: "missing", msg: "Field required" },
              { loc: ["body", "title"], type: 1, msg: "Field required" },
              { loc: ["body", "criteria", 0, "description"], type: "missing", msg: "Field required", input: SECRET_INPUT },
            ],
          },
          422,
        ),
    });

    const error = await failureOf("/api/v1/jobs/1/criteria", "PUT");

    expect(error.status).toBe(422);
    expect(error.validationIssues).toEqual([
      { type: "missing", loc: ["body", "criteria", 0, "description"], msg: "Field required" },
    ]);
  });

  it.each([
    ["detail là chuỗi", () => jsonResponse({ detail: "Not authenticated" }, 422)],
    ["detail là object", () => jsonResponse({ detail: { loc: ["body", "title"] } }, 422)],
    ["detail rỗng", () => jsonResponse({ detail: [] }, 422)],
    ["body không phải JSON", () => new Response("<html>Unprocessable</html>", { status: 422 })],
    ["body rỗng", () => new Response(null, { status: 422 })],
  ])("không crash khi %s", async (_label, respond) => {
    stubFetch({ "POST /api/v1/jobs": respond });

    const error = await failureOf("/api/v1/jobs");

    expect(error.status).toBe(422);
    expect(error.code).toBe("request_failed");
    expect(error.message).toBe("Request failed (422)");
    expect(error.validationIssues ?? []).toEqual([]);
  });
});

describe("apiRequest — các lỗi hiện có không đổi", () => {
  it("giữ code/message cho lỗi nghiệp vụ, 401, 403, 409 và Retry-After", async () => {
    stubFetch({
      "POST /api/v1/jobs/1/publish": () =>
        errorResponse(422, "job_rule_violation", "Bộ tiêu chí phải có ít nhất 1 người phỏng vấn"),
      "GET /api/v1/auth/me": () => errorResponse(401, "invalid_session", "Session expired"),
      "POST /api/v1/accounts": () => errorResponse(403, "forbidden", "Không có quyền"),
      "PUT /api/v1/jobs/1": () => errorResponse(409, "version_conflict", "Tin đã thay đổi"),
      "POST /api/v1/auth/login": () =>
        jsonResponse({ error: { code: "rate_limited", message: "Thử lại sau" } }, 429, { "Retry-After": "30" }),
    });

    const business = await failureOf("/api/v1/jobs/1/publish");
    expect(business).toMatchObject({
      status: 422,
      code: "job_rule_violation",
      message: "Bộ tiêu chí phải có ít nhất 1 người phỏng vấn",
    });
    expect(business.validationIssues ?? []).toEqual([]);

    expect(await failureOf("/api/v1/auth/me", "GET")).toMatchObject({
      status: 401,
      code: "invalid_session",
      message: "Session expired",
    });
    expect(await failureOf("/api/v1/accounts")).toMatchObject({ status: 403, code: "forbidden" });
    expect(await failureOf("/api/v1/jobs/1", "PUT")).toMatchObject({
      status: 409,
      code: "version_conflict",
      message: "Tin đã thay đổi",
    });
    const throttled = await failureOf("/api/v1/auth/login");
    expect(throttled).toMatchObject({ status: 429, code: "rate_limited", retryAfter: 30 });
  });

  it("204 vẫn trả undefined và 200 trả payload", async () => {
    stubFetch({
      "POST /api/v1/auth/logout": () => jsonResponse(null, 204),
      "GET /api/v1/departments": () => jsonResponse([{ id: 1 }]),
    });

    await expect(apiRequest("/api/v1/auth/logout", { method: "POST" })).resolves.toBeUndefined();
    await expect(apiRequest("/api/v1/departments")).resolves.toEqual([{ id: 1 }]);
  });
});

describe("apiRequest — multipart FormData (tải CV)", () => {
  it("gửi nguyên FormData, không JSON.stringify và không tự đặt Content-Type", async () => {
    const { stubFlowFetch } = await import("@/test/publicFlowStub");
    const { calls } = stubFlowFetch({
      "POST /api/v1/candidates/submissions": () => jsonResponse({ submission_id: 1 }, 201),
    });
    const form = new FormData();
    form.append("full_name", "Nguyễn Văn A");
    form.append("file", new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" }));

    await expect(
      apiRequest("/api/v1/candidates/submissions", { method: "POST", body: form }),
    ).resolves.toEqual({ submission_id: 1 });

    const [call] = calls;
    expect(call.rawBody).toBe(form);
    expect(call.form?.get("full_name")).toBe("Nguyễn Văn A");
    // Trình duyệt tự đặt multipart boundary; client không được ghi đè.
    expect(Object.keys(call.headers).map((key) => key.toLowerCase())).not.toContain(
      "content-type",
    );
  });

  it("body JSON vẫn được stringify với Content-Type application/json", async () => {
    const { stubFlowFetch } = await import("@/test/publicFlowStub");
    const { calls } = stubFlowFetch({
      "POST /api/v1/applications/otp": () => jsonResponse({ ok: true }),
    });

    await apiRequest("/api/v1/applications/otp", { method: "POST", body: { job_id: 1 } });

    expect(calls[0].json).toEqual({ job_id: 1 });
    expect(calls[0].headers["content-type"]).toBe("application/json");
  });

  it("lỗi multipart vẫn là ApiError với Retry-After và lỗi trường 422", async () => {
    const { stubFlowFetch, validationResponse } = await import("@/test/publicFlowStub");
    stubFlowFetch({
      "POST /api/v1/candidates/submissions": () =>
        validationResponse("phone", "Số điện thoại phải gồm đúng 10 chữ số."),
    });
    const caught = await apiRequest("/api/v1/candidates/submissions", {
      method: "POST",
      body: new FormData(),
    }).catch((error: unknown) => error);
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).validationIssues).toEqual([
      { type: "value_error", loc: ["body", "phone"], msg: "Số điện thoại phải gồm đúng 10 chữ số." },
    ]);
  });
});

describe("ApiError constructor", () => {
  it("giữ 4 tham số cũ; tham số thứ 5 tùy chọn là validationIssues", () => {
    const legacy = new ApiError(409, "version_conflict", "Tin đã thay đổi", 12);
    expect(legacy).toBeInstanceOf(Error);
    expect(legacy.name).toBe("ApiError");
    expect(legacy).toMatchObject({ status: 409, code: "version_conflict", message: "Tin đã thay đổi", retryAfter: 12 });
    expect(legacy.validationIssues).toBeUndefined();

    const issues: ApiValidationIssue[] = [
      { type: "string_too_long", loc: ["body", "title"], msg: "String should have at most 200 characters", ctx: { max_length: 200 } },
    ];
    const withIssues = new ApiError(422, "request_failed", "Request failed (422)", undefined, issues);
    expect(withIssues.validationIssues).toEqual(issues);
    expect(withIssues.retryAfter).toBeUndefined();
  });
});
