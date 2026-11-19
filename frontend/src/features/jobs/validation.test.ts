// Kiểm ranh giới nghiệp vụ: số thập phân, tổng trọng số, ngày UTC+7 và độ dài Unicode.
import { describe, expect, it } from "vitest";
import {
  criteriaInputFrom,
  emptyCriteriaDraft,
  isCriteriaDraftPristine,
  type CriteriaDraft,
  type CriteriaDraftRow,
} from "./CriteriaEditor";
import type { Criterion } from "./types";
import { companyToday, rowErrorKey, validateCriteria, validateJobFields, type JobFormValues } from "./validation";

function row(patch: Partial<Criterion>): CriteriaDraftRow {
  return { ...emptyCriteriaDraft().criteria[0], description: "Mô tả", ...patch };
}

/** A criteria set the backend accepts, apart from what each test changes. */
function validSet(rows: CriteriaDraftRow[], patch: Partial<CriteriaDraft> = {}): CriteriaDraft {
  return { ...emptyCriteriaDraft(), interviewerIds: ["iv-1"], criteria: rows, ...patch };
}

const JOB: JobFormValues = {
  title: "Kỹ sư dữ liệu",
  departmentId: "1",
  description: "Xây dựng pipeline",
  requirements: "SQL",
  benefits: "",
  headcount: "2",
  workMode: "",
  location: "",
  deadline: "2026-12-31",
};

describe("validateCriteria — trọng số", () => {
  it("trọng số phải lớn hơn 0, không quá 100 và có tối đa 2 chữ số thập phân", () => {
    const rows = [
      row({ name: "A", weight: 0 }),
      row({ name: "B", weight: 100.01 }),
      row({ name: "C", weight: 12.345 }),
      row({ name: "D", weight: 0.01 }),
      row({ name: "E", weight: 12.5 }),
    ];
    const errors = validateCriteria(validSet(rows));

    expect(errors[rowErrorKey(rows[0].key, "weight")]).toEqual({ reason: "gt", limit: 0 });
    expect(errors[rowErrorKey(rows[1].key, "weight")]).toEqual({ reason: "le", limit: 100 });
    expect(errors[rowErrorKey(rows[2].key, "weight")]).toEqual({ reason: "decimals", limit: 2 });
    expect(errors[rowErrorKey(rows[3].key, "weight")]).toBeUndefined();
    expect(errors[rowErrorKey(rows[4].key, "weight")]).toBeUndefined();
  });

  it("tổng thập phân 33.33 + 33.33 + 33.34 hợp lệ; 33.33 × 3 báo tổng 99.99", () => {
    const exact = [row({ name: "A", weight: 33.33 }), row({ name: "B", weight: 33.33 }), row({ name: "C", weight: 33.34 })];
    expect(validateCriteria(validSet(exact))).toEqual({});

    const short = [row({ name: "A", weight: 33.33 }), row({ name: "B", weight: 33.33 }), row({ name: "C", weight: 33.33 })];
    expect(validateCriteria(validSet(short))).toEqual({ criteria: { reason: "totalWeight", limit: 99.99 } });
  });
});

describe("ngưỡng tự động mời", () => {
  it("dùng mặc định thì không kiểm tra và không gửi giá trị thanh trượt, nhưng giá trị đã chỉnh vẫn được giữ", () => {
    const set = validSet([row({ name: "A", weight: 100 })], { useDefaultThreshold: true, threshold: 70 });

    expect(validateCriteria(set)).toEqual({});
    expect(criteriaInputFrom(set).autoInviteThreshold).toBeNull();
    expect(set.threshold).toBe(70);
    // An adjusted slider is an edit: a draft must not silently drop the criteria set.
    expect(isCriteriaDraftPristine({ ...emptyCriteriaDraft(), threshold: 70 })).toBe(false);
    expect(isCriteriaDraftPristine(emptyCriteriaDraft())).toBe(true);
  });

  it("ngưỡng tùy chỉnh nằm trong 0..100 với tối đa 2 chữ số thập phân", () => {
    const at = (threshold: number) =>
      validateCriteria(validSet([row({ name: "A", weight: 100 })], { useDefaultThreshold: false, threshold })).threshold;

    expect(at(0)).toBeUndefined();
    expect(at(100)).toBeUndefined();
    expect(at(72.5)).toBeUndefined();
    expect(at(-1)).toEqual({ reason: "ge", limit: 0 });
    expect(at(100.5)).toEqual({ reason: "le", limit: 100 });
    expect(at(72.555)).toEqual({ reason: "decimals", limit: 2 });
    expect(criteriaInputFrom(validSet([row({ name: "A", weight: 100 })], { useDefaultThreshold: false, threshold: 72.5 })).autoInviteThreshold).toBe(72.5);
  });
});

describe("validateJobFields", () => {
  it("số lượng cần tuyển là số nguyên dương trong giới hạn INTEGER của PostgreSQL", () => {
    const headcount = (value: string, rule: "draft" | "publish" = "draft") =>
      validateJobFields({ ...JOB, headcount: value }, rule, "2026-11-17").headcount;

    expect(headcount("2147483647")).toBeUndefined();
    expect(headcount("2147483648")).toEqual({ reason: "le", limit: 2_147_483_647 });
    expect(headcount("1.5")).toEqual({ reason: "integer" });
    expect(headcount("0")).toEqual({ reason: "gt", limit: 0 });
    expect(headcount("-3")).toEqual({ reason: "gt", limit: 0 });
    // Optional for a draft, required to publish.
    expect(headcount("")).toBeUndefined();
    expect(headcount("", "publish")).toEqual({ reason: "required" });
  });

  it("ngày công ty (UTC+7) sang ngày mới lúc 17:00 UTC; đăng tin không nhận hạn nộp đã qua", () => {
    const beforeMidnight = companyToday(new Date("2026-11-17T16:59:59.999Z"));
    const afterMidnight = companyToday(new Date("2026-11-17T17:00:00.000Z"));
    expect(beforeMidnight).toBe("2026-11-17");
    expect(afterMidnight).toBe("2026-11-18");

    const deadline = { ...JOB, deadline: "2026-11-17" };
    expect(validateJobFields(deadline, "publish", beforeMidnight).deadline).toBeUndefined();
    expect(validateJobFields(deadline, "publish", afterMidnight).deadline).toEqual({ reason: "pastDate" });
    // The backend only checks the deadline when a posting opens.
    expect(validateJobFields(deadline, "draft", afterMidnight).deadline).toBeUndefined();
  });

  it("độ dài đếm theo ký tự Unicode như backend, không theo UTF-16", () => {
    const title = (value: string) => validateJobFields({ ...JOB, title: value }, "draft", "2026-11-17").title;

    expect(title("😀".repeat(200))).toBeUndefined();
    expect(title("😀".repeat(201))).toEqual({ reason: "tooLong", limit: 200 });
    expect(title("a".repeat(201))).toEqual({ reason: "tooLong", limit: 200 });
  });
});
