import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { BarChart3, Calendar, UserCheck } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette, type CommandItem } from "./CommandPalette";

const ITEMS: CommandItem[] = [
  { label: "Tổng quan Tuyển dụng", to: "/app/hr", icon: BarChart3, group: "Tuyển dụng" },
  { label: "Lịch phỏng vấn", to: "/app/hr/interviews", icon: Calendar, group: "Tuyển dụng" },
  { label: "Tài khoản của tôi", to: "/app/account", icon: UserCheck, group: "Cá nhân" },
];

function renderPalette(onClose = vi.fn()) {
  render(
    <MemoryRouter initialEntries={["/app/hr"]}>
      <Routes>
        <Route path="*" element={<CommandPalette open onClose={onClose} items={ITEMS} />} />
      </Routes>
      <Routes>
        <Route path="/app/account" element={<p>account page</p>} />
        <Route path="/app/hr/interviews" element={<p>interviews page</p>} />
        <Route path="*" element={null} />
      </Routes>
    </MemoryRouter>,
  );
  return onClose;
}

describe("CommandPalette", () => {
  it("matches pages without requiring Vietnamese diacritics", async () => {
    renderPalette();
    await userEvent.type(screen.getByPlaceholderText("Đi tới trang…"), "lich phong van");

    expect(screen.getByRole("button", { name: /Lịch phỏng vấn/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tài khoản của tôi/ })).not.toBeInTheDocument();
  });

  it("navigates to the highlighted page with the keyboard and closes", async () => {
    const onClose = renderPalette();
    const input = screen.getByPlaceholderText("Đi tới trang…");
    await userEvent.type(input, "tai khoan{Enter}");

    expect(await screen.findByText("account page")).toBeInTheDocument();
    expect(onClose).toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const onClose = renderPalette();
    await userEvent.type(screen.getByPlaceholderText("Đi tới trang…"), "{Escape}");

    expect(onClose).toHaveBeenCalled();
  });
});
