import { beforeEach, expect, it, vi } from "vitest";

beforeEach(() => {
  vi.resetModules();
  history.replaceState(null, "", "/");
});

it("captures before routing and clears only the URL, preserving memory across imports", async () => {
  history.replaceState(null, "", "/r/private-token?source=email#fragment");
  const first = await import("./tokenBootstrap");
  expect(first.getResponseToken()).toBe("private-token");
  expect(location.pathname + location.search + location.hash).toBe("/r");
  expect((await import("./tokenBootstrap")).getResponseToken()).toBe("private-token");
});

it("reloading the cleared URL cannot recover the token", async () => {
  history.replaceState(null, "", "/r");
  expect((await import("./tokenBootstrap")).getResponseToken()).toBeNull();
});
