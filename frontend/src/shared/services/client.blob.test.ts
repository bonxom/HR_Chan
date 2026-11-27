// Tải tệp nhị phân (CV) qua client dùng chung: token, cookie, tên tệp và lỗi.
import { describe, expect, it } from "vitest";
import { errorResponse, stubFetch } from "@/test/apiStub";
import { ApiError, apiBlob } from "./client";

function fileResponse(disposition?: string, type = "application/pdf"): Response {
  const headers: Record<string, string> = { "Content-Type": type };
  if (disposition !== undefined) headers["Content-Disposition"] = disposition;
  // Chuỗi thay vì Blob: Blob của jsdom bị Response của Node chuyển thành "[object Blob]".
  return new Response("%PDF-1.4", { status: 200, headers });
}

describe("apiBlob", () => {
  it("gửi bearer, credentials và trả blob kèm tên tệp tiếng Việt đã giải mã", async () => {
    const { calls, fetchMock } = stubFetch({
      "GET /api/v1/applications/7/cv": () =>
        fileResponse("attachment; filename*=UTF-8''CV%20Nguy%E1%BB%85n%20V%C4%83n%20A.pdf"),
    });

    const result = await apiBlob("/api/v1/applications/7/cv", { accessToken: "hr-token" });

    expect(calls[0].headers.authorization).toBe("Bearer hr-token");
    expect(fetchMock.mock.calls[0][1]?.credentials).toBe("include");
    expect(result.filename).toBe("CV Nguyễn Văn A.pdf");
    expect(result.blob.type).toBe("application/pdf");
    expect(await result.blob.text()).toBe("%PDF-1.4");
  });

  it.each([
    ["thiếu header", undefined],
    ["header không có filename", "attachment"],
    ["mã hóa hỏng", "attachment; filename*=UTF-8''%E0%A4%A"],
    ["tên rỗng", "attachment; filename*=UTF-8''"],
  ])("trả filename null khi %s", async (_label, disposition) => {
    stubFetch({ "GET /api/v1/applications/7/cv": () => fileResponse(disposition) });

    const result = await apiBlob("/api/v1/applications/7/cv", { accessToken: "hr-token" });

    expect(result.filename).toBeNull();
  });

  it("bỏ phần đường dẫn trong tên tệp", async () => {
    stubFetch({
      "GET /api/v1/applications/7/cv": () => fileResponse("attachment; filename*=UTF-8''..%2F..%2Fcv.pdf"),
    });

    const result = await apiBlob("/api/v1/applications/7/cv", { accessToken: "hr-token" });

    expect(result.filename).toBe("cv.pdf");
  });

  it("đổi phản hồi lỗi JSON thành ApiError giống apiRequest", async () => {
    stubFetch({
      "GET /api/v1/applications/7/cv": () => errorResponse(503, "cv_unavailable", "Không đọc được CV"),
    });

    const caught = await apiBlob("/api/v1/applications/7/cv", { accessToken: "hr-token" }).catch(
      (error: unknown) => error,
    );

    expect(caught).toBeInstanceOf(ApiError);
    expect(caught).toMatchObject({ status: 503, code: "cv_unavailable", message: "Không đọc được CV" });
  });
});
