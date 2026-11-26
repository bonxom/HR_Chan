import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import {
  ArrowLeft,
  BarChart3,
  Briefcase,
  Building,
  Calendar,
  CheckSquare,
  ChevronUp,
  ChevronsLeft,
  ChevronsRight,
  FileText,
  LogOut,
  Menu,
  Search,
  Shield,
  UserCheck,
  UserCog,
  Users as UsersIcon,
  X,
} from "lucide-react";
import { Badge } from "@/shared/components/ui/Badge";
import { CommandPalette, type CommandItem } from "@/shared/components/ui/CommandPalette";
import { AmbientBackdrop, GLASS_BAR, GLASS_LAYER } from "@/shared/components/ui/Glass";
import { MockDataBadge } from "@/shared/components/ui/MockDataIndicator";
import { useAuth } from "@/features/auth/AuthProvider";
import type { AuthAccount, EmployeeRole } from "@/features/auth/types";

interface NavItem {
  label: string;
  path: string;
  icon: typeof Briefcase;
  isMock?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const ROLE_LABELS: Record<EmployeeRole, string> = {
  HR: "Tuyển dụng (HR)",
  INTERVIEWER: "Người phỏng vấn",
  DEPT_MANAGER: "Quản lý bộ phận",
  PROBATION: "Thử việc",
};

const ACCOUNT_ITEM: NavItem = { label: "Tài khoản của tôi", path: "/app/account", icon: UserCheck };

function navigationFor(account: AuthAccount): NavGroup[] {
  if (account.accountType === "ADMIN") {
    return [
      {
        label: "Quản trị",
        items: [
          { label: "Quản lý Người dùng & Quyền", path: "/app/admin/users", icon: UserCog },
          { label: "Nhật ký kiểm toán", path: "/app/admin/logs", icon: Shield },
        ],
      },
      { label: "Cá nhân", items: [ACCOUNT_ITEM] },
    ];
  }

  const groups: NavGroup[] = [];
  if (account.roles.includes("HR")) {
    groups.push({
      label: "Tuyển dụng",
      items: [
        { label: "Tổng quan Tuyển dụng", path: "/app/hr", icon: BarChart3, isMock: true },
        { label: "Tin tuyển dụng & Tiêu chí", path: "/app/hr/jobs", icon: Briefcase },
        { label: "Pipeline Hồ sơ ứng tuyển", path: "/app/hr/applications", icon: UsersIcon, isMock: true },
        { label: "Lịch phỏng vấn", path: "/app/hr/interviews", icon: Calendar, isMock: true },
        { label: "Báo cáo & Phễu tuyển dụng", path: "/app/hr/reports", icon: FileText, isMock: true },
      ],
    });
  }
  if (account.roles.includes("INTERVIEWER")) {
    groups.push({
      label: "Phỏng vấn",
      items: [
        { label: "Lịch phỏng vấn của tôi", path: "/app/interviewer", icon: Calendar, isMock: true },
        { label: "Chấm điểm phỏng vấn", path: "/app/interviewer/evaluations", icon: UserCheck, isMock: true },
      ],
    });
  }
  if (account.roles.includes("DEPT_MANAGER")) {
    groups.push({
      label: "Quản lý bộ phận",
      items: [
        { label: "Quản lý Đợt thử việc", path: "/app/manager", icon: Building, isMock: true },
        { label: "Giao task & Đánh giá bài", path: "/app/manager/tasks", icon: CheckSquare, isMock: true },
      ],
    });
  }
  if (account.roles.includes("PROBATION")) {
    groups.push({
      label: "Thử việc",
      items: [
        { label: "Nhiệm vụ thử việc của tôi", path: "/app/trainee", icon: CheckSquare, isMock: true },
        { label: "Kết quả đánh giá", path: "/app/trainee/results", icon: FileText, isMock: true },
      ],
    });
  }
  groups.push({ label: "Cá nhân", items: [ACCOUNT_ITEM] });
  return groups;
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

interface SidebarProps {
  account: AuthAccount;
  groups: NavGroup[];
  roleSummary: string;
  collapsed: boolean;
  onToggleCollapse?: () => void;
  onNavigate?: () => void;
  onLogout: () => void;
}

function Sidebar({ account, groups, roleSummary, collapsed, onToggleCollapse, onNavigate, onLogout }: SidebarProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex h-full flex-col">
      <div className={`flex h-14 shrink-0 items-center gap-2.5 ${collapsed ? "justify-center px-2" : "px-4"}`}>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]">
          <Briefcase className="h-4 w-4" />
        </span>
        {!collapsed && (
          <div className="min-w-0 leading-tight">
            <div className="text-[15px] font-semibold text-ink">HR_Chan</div>
            <div className="text-xs text-ink-subtle">Workspace nội bộ</div>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-2 py-3">
        {groups.map((group) => (
          <div key={group.label}>
            {!collapsed && <p className="mb-1 px-2.5 text-xs font-medium text-ink-subtle">{group.label}</p>}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end
                    onClick={onNavigate}
                    title={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      `flex h-9 items-center gap-2.5 rounded-control text-[13px] transition-colors ${
                        collapsed ? "justify-center px-0" : "px-2.5"
                      } ${
                        isActive
                          ? "bg-white/90 font-medium text-ink shadow-[inset_0_1px_0_rgba(255,255,255,1),0_1px_4px_rgba(15,60,50,0.14)]"
                          : "text-ink-muted hover:bg-white/50 hover:text-ink"
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-brand" : ""}`} />
                        <span className={collapsed ? "sr-only" : "flex-1 truncate"}>{item.label}</span>
                        {item.isMock && !collapsed && <MockDataBadge variant="sidebar" />}
                        {item.isMock && collapsed && <span className="sr-only">MOCK</span>}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-white/70 p-2">
        <div className="relative">
          {menuOpen && (
            <div className={`absolute bottom-full left-0 right-0 mb-2 rounded-xl p-3 text-[13px] ${GLASS_LAYER} ${collapsed ? "w-60" : ""}`}>
              <p className="truncate font-medium text-ink">{account.email}</p>
              <p className="mt-1 text-xs leading-relaxed text-ink-subtle">
                Phiên làm việc dùng cookie an toàn; quyền hạn do máy chủ quyết định.
              </p>
              <div className="mt-2 space-y-0.5 border-t border-line/80 pt-2">
                <Link
                  to="/"
                  className="flex items-center gap-2 rounded-control px-2 py-1.5 text-ink-muted hover:bg-ink/5 hover:text-ink"
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Về Cổng ứng viên
                </Link>
                <button
                  type="button"
                  onClick={onLogout}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-control px-2 py-1.5 text-left text-danger-ink hover:bg-danger-soft"
                >
                  <LogOut className="h-3.5 w-3.5" /> Đăng xuất
                </button>
              </div>
            </div>
          )}
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-label="Tài khoản hiện hành"
            className={`flex w-full cursor-pointer items-center gap-2.5 rounded-control p-2 text-left transition-colors hover:bg-white/50 ${
              collapsed ? "justify-center" : ""
            }`}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-brand-ink">
              {initials(account.fullName)}
            </span>
            {!collapsed && (
              <>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-ink">{account.fullName}</span>
                  <span className="block truncate text-xs text-ink-subtle">{roleSummary}</span>
                </span>
                <ChevronUp className={`h-4 w-4 shrink-0 text-ink-subtle transition-transform ${menuOpen ? "" : "rotate-180"}`} />
              </>
            )}
          </button>
        </div>
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            className="mt-1 flex h-8 w-full cursor-pointer items-center justify-center gap-2 rounded-control text-xs text-ink-subtle hover:bg-white/50 hover:text-ink"
          >
            {collapsed ? <ChevronsRight className="h-4 w-4" /> : <ChevronsLeft className="h-4 w-4" />}
            {!collapsed && "Thu gọn"}
          </button>
        )}
      </div>
    </div>
  );
}

export function DashboardLayout() {
  const { account, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!account) return null;

  const groups = navigationFor(account);
  const roleSummary =
    account.accountType === "ADMIN"
      ? "Quản trị hệ thống"
      : account.roles.map((role) => ROLE_LABELS[role] ?? role).join(", ");

  const commands: CommandItem[] = groups.flatMap((group) =>
    group.items.map((item) => ({ label: item.label, to: item.path, icon: item.icon, group: group.label })),
  );
  const current = commands
    .filter((item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`))
    .sort((a, b) => b.to.length - a.to.length)[0];

  const handleLogout = () => void logout();
  const sidebarProps = { account, groups, roleSummary, onLogout: handleLogout };

  return (
    <div className="relative isolate flex min-h-screen bg-canvas text-ink">
      <AmbientBackdrop />

      <aside
        className={`sticky top-3 my-3 ml-3 hidden h-[calc(100vh-1.5rem)] shrink-0 overflow-hidden rounded-2xl transition-[width] duration-200 lg:block ${GLASS_BAR} ${
          collapsed ? "w-16" : "w-64"
        }`}
      >
        <Sidebar {...sidebarProps} collapsed={collapsed} onToggleCollapse={() => setCollapsed((value) => !value)} />
      </aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Điều hướng">
          <button
            type="button"
            aria-label="Đóng menu"
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 bg-ink/25 backdrop-blur-[2px]"
          />
          <div className={`relative h-full w-72 rounded-r-2xl ${GLASS_LAYER}`}>
            <button
              type="button"
              aria-label="Đóng menu"
              onClick={() => setDrawerOpen(false)}
              className="absolute right-3 top-3.5 z-10 cursor-pointer rounded-control p-1.5 text-ink-muted hover:bg-ink/5"
            >
              <X className="h-4 w-4" />
            </button>
            <Sidebar {...sidebarProps} collapsed={false} onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className={`sticky top-3 z-30 mx-3 mt-3 flex h-14 items-center gap-3 rounded-2xl px-3 sm:px-4 ${GLASS_BAR}`}>
          <button
            type="button"
            aria-label="Mở menu"
            onClick={() => setDrawerOpen(true)}
            className="cursor-pointer rounded-control p-1.5 text-ink-muted hover:bg-white/60 lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0 truncate text-sm text-ink-muted">
            <span>{account.accountType === "ADMIN" ? "Quản trị" : "Workspace"}</span>
            {current && (
              <>
                <span className="mx-2 text-line-strong">/</span>
                <span className="font-medium text-ink">{current.label}</span>
              </>
            )}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="hidden h-9 w-64 cursor-pointer items-center gap-2 rounded-control border border-white/80 bg-white/55 px-3 text-left text-sm text-ink-subtle transition-colors hover:bg-white/85 md:flex"
            >
              <Search className="h-4 w-4" />
              <span className="flex-1">Đi tới trang…</span>
              <kbd className="rounded border border-line bg-surface/80 px-1.5 text-[11px] font-medium text-ink-muted">Ctrl K</kbd>
            </button>
            <button
              type="button"
              aria-label="Đi tới trang"
              onClick={() => setPaletteOpen(true)}
              className="cursor-pointer rounded-control p-2 text-ink-muted hover:bg-white/60 md:hidden"
            >
              <Search className="h-4 w-4" />
            </button>
            <Badge variant={account.accountType === "ADMIN" ? "danger" : "neutral"}>
              {account.accountType === "ADMIN" ? "Quản trị" : "Nhân viên"}
            </Badge>
            <button
              type="button"
              onClick={handleLogout}
              className="hidden h-9 cursor-pointer items-center gap-1.5 rounded-control px-3 text-[13px] font-medium text-ink-muted transition-colors hover:bg-white/60 hover:text-ink sm:inline-flex"
            >
              <LogOut className="h-4 w-4" /> Đăng xuất
            </button>
          </div>
        </header>

        <main className="flex-1 px-3 pb-10 pt-6 sm:px-6">
          <div className="mx-auto max-w-7xl space-y-6">
            <Outlet />
          </div>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={commands} />
    </div>
  );
}
