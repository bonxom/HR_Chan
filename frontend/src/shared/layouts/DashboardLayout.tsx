import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router";
import {
  BarChart3,
  Briefcase,
  Building,
  Calendar,
  CheckSquare,
  ChevronDown,
  FileText,
  LogOut,
  Shield,
  UserCheck,
  UserCog,
  Users as UsersIcon,
} from "lucide-react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { MockDataBadge } from "@/shared/components/ui/MockDataIndicator";
import { useAuth } from "@/features/auth/AuthProvider";
import type { AuthAccount, EmployeeRole } from "@/features/auth/types";

interface NavItem {
  label: string;
  path: string;
  icon: typeof Briefcase;
  isMock?: boolean;
}

const ROLE_LABELS: Record<EmployeeRole, string> = {
  HR: "Tuyển dụng (HR)",
  INTERVIEWER: "Người phỏng vấn",
  DEPT_MANAGER: "Quản lý bộ phận",
  PROBATION: "Thử việc",
};

function navigationFor(account: AuthAccount): NavItem[] {
  if (account.accountType === "ADMIN") {
    return [
      { label: "Quản lý Người dùng & Quyền", path: "/app/admin/users", icon: UserCog },
      { label: "Nhật ký kiểm toán", path: "/app/admin/logs", icon: Shield },
      { label: "Tài khoản của tôi", path: "/app/account", icon: UserCheck },
    ];
  }

  const items: NavItem[] = [];
  if (account.roles.includes("HR")) {
    items.push(
      { label: "Tổng quan Tuyển dụng", path: "/app/hr", icon: BarChart3, isMock: true },
      { label: "Tin tuyển dụng & Tiêu chí", path: "/app/hr/jobs", icon: Briefcase, isMock: true },
      { label: "Pipeline Hồ sơ ứng tuyển", path: "/app/hr/applications", icon: UsersIcon, isMock: true },
      { label: "Lịch phỏng vấn", path: "/app/hr/interviews", icon: Calendar, isMock: true },
      { label: "Báo cáo & Phễu tuyển dụng", path: "/app/hr/reports", icon: FileText, isMock: true },
    );
  }
  if (account.roles.includes("INTERVIEWER")) {
    items.push(
      { label: "Lịch phỏng vấn của tôi", path: "/app/interviewer", icon: Calendar, isMock: true },
      { label: "Chấm điểm phỏng vấn", path: "/app/interviewer/evaluations", icon: UserCheck, isMock: true },
    );
  }
  if (account.roles.includes("DEPT_MANAGER")) {
    items.push(
      { label: "Quản lý Đợt thử việc", path: "/app/manager", icon: Building, isMock: true },
      { label: "Giao task & Đánh giá bài", path: "/app/manager/tasks", icon: CheckSquare, isMock: true },
    );
  }
  if (account.roles.includes("PROBATION")) {
    items.push(
      { label: "Nhiệm vụ thử việc của tôi", path: "/app/trainee", icon: CheckSquare, isMock: true },
      { label: "Kết quả đánh giá", path: "/app/trainee/results", icon: FileText, isMock: true },
    );
  }
  items.push({ label: "Tài khoản của tôi", path: "/app/account", icon: UserCheck });
  return items;
}

export function DashboardLayout() {
  const { account, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  if (!account) return null;

  const navItems = navigationFor(account);
  const roleSummary =
    account.accountType === "ADMIN"
      ? "Quản trị hệ thống"
      : account.roles.map((role) => ROLE_LABELS[role] ?? role).join(", ");

  return (
    <div className="min-h-screen flex bg-slate-100 text-slate-900">
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 border-r border-slate-800">
        <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800/80">
          <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-white font-bold">
            <Briefcase className="w-4 h-4" />
          </div>
          <div>
            <div className="font-extrabold text-white tracking-tight flex items-center gap-1.5 text-base">
              HR_Chan{" "}
              <span className="text-[10px] bg-emerald-500/20 text-emerald-400 font-semibold px-1.5 py-0.5 rounded">
                Core
              </span>
            </div>
            <div className="text-[10px] text-slate-400">Enterprise AI Recruitment</div>
          </div>
        </div>

        <div className="p-4 border-b border-slate-800/80 bg-slate-950/40">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Tài khoản hiện hành
          </div>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            className="w-full text-left bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 rounded-xl p-2.5 flex items-center justify-between transition-colors"
          >
            <div className="min-w-0 pr-2">
              <div className="font-semibold text-white text-xs truncate">{account.fullName}</div>
              <div className="text-[11px] text-emerald-400 font-medium truncate mt-0.5">
                {roleSummary}
              </div>
            </div>
            <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
          </button>
          {menuOpen && (
            <div className="mt-2 rounded-xl border border-slate-700 bg-slate-800 p-3 text-xs text-slate-300">
              <p className="truncate">{account.email}</p>
              <p className="mt-1 text-[11px] text-slate-400">
                Phiên làm việc dùng cookie an toàn; quyền hạn do máy chủ quyết định.
              </p>
              <Button
                size="sm"
                variant="ghost"
                className="mt-2 w-full justify-start text-slate-200 hover:bg-slate-700"
                leftIcon={<LogOut className="w-3.5 h-3.5" />}
                onClick={() => void logout()}
              >
                Đăng xuất
              </Button>
            </div>
          )}
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Chức năng phân quyền
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-emerald-600 text-white shadow-xs font-semibold"
                      : "text-slate-300 hover:text-white hover:bg-slate-800"
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{item.label}</span>
                {item.isMock && <MockDataBadge variant="sidebar" />}
              </NavLink>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <Link
            to="/"
            className="flex items-center justify-between text-xs font-medium text-slate-400 hover:text-emerald-400 py-1.5 transition-colors"
          >
            <span>Về Cổng ứng viên</span>
            <LogOut className="w-3.5 h-3.5" />
          </Link>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-16 bg-white border-b border-slate-200/90 px-8 flex items-center justify-between shrink-0 shadow-xs">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-bold text-slate-900">
              <span className="text-emerald-700 font-semibold">{account.fullName}</span>
            </h1>
            <Badge variant={account.accountType === "ADMIN" ? "danger" : "neutral"}>
              {account.accountType === "ADMIN" ? "Quản trị" : "Nhân viên"}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="text-slate-500 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg">
              Phiên làm việc: <span className="font-semibold text-slate-700">Xác thực nội bộ</span>
            </div>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<LogOut className="w-3.5 h-3.5" />}
              onClick={() => void logout()}
            >
              Đăng xuất
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-7xl mx-auto space-y-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
