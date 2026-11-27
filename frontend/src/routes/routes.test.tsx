// Các trang /action/* cũ (dữ liệu giả) đã gỡ; link thật của ứng viên là /r/{token}.
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import browserRouter from "./routes";

describe("routes", () => {
  it.each(["/action/interview/1", "/action/consent/1", "/action/offer/1"])("%s trả về trang 404", async (path) => {
    await browserRouter.navigate(path);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={browserRouter} />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Trang không tồn tại hoặc đã được di chuyển.")).toBeInTheDocument();
  });
});
