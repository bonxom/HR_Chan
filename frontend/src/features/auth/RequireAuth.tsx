import type { PropsWithChildren } from "react";
import { Link, Navigate, useLocation } from "react-router";
import { Loader2, ShieldAlert } from "lucide-react";
import { useAuth } from "./AuthProvider";
import type { AuthAccount, EmployeeRole } from "./types";
import { AmbientBackdrop } from "@/shared/components/ui/Glass";

export function landingPathFor(account: AuthAccount): string {
  if (account.accountType === "ADMIN") return "/app/admin/users";
  if (account.roles.includes("HR")) return "/app/hr";
  if (account.roles.includes("INTERVIEWER")) return "/app/interviewer";
  if (account.roles.includes("DEPT_MANAGER")) return "/app/manager";
  if (account.roles.includes("PROBATION")) return "/app/trainee";
  return "/app/account";
}

export function canAccess(
  account: AuthAccount,
  options: { accountType?: "ADMIN" | "EMPLOYEE"; roles?: EmployeeRole[] },
): boolean {
  if (options.accountType && account.accountType !== options.accountType) return false;
  if (options.roles && !options.roles.some((role) => account.roles.includes(role))) return false;
  return true;
}

function LoadingPanel() {
  return (
    <div className="relative isolate min-h-screen flex flex-col items-center justify-center gap-3 bg-canvas text-slate-600">
      <AmbientBackdrop />
      <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
      <p className="text-sm font-medium">Đang xác thực phiên làm việc…</p>
    </div>
  );
}

export function UnsupportedBrowserNotice() {
  return (
    <div className="relative isolate min-h-screen flex items-center justify-center bg-canvas p-6">
      <AmbientBackdrop />
      <div className="max-w-md bg-white border border-slate-200 rounded-2xl p-8 text-center shadow-sm">
        <ShieldAlert className="w-8 h-8 text-rose-500 mx-auto" />
        <h1 className="mt-4 text-lg font-bold text-slate-900">Trình duyệt không được hỗ trợ</h1>
        <p className="mt-2 text-sm text-slate-600">
          Hệ thống cần Web Locks API để đồng bộ phiên đăng nhập giữa các tab. Vui lòng dùng bản
          Chrome, Edge, Firefox hoặc Safari gần đây.
        </p>
        <Link to="/" className="mt-5 inline-block text-sm font-semibold text-emerald-700 hover:underline">
          &larr; Về cổng ứng viên
        </Link>
      </div>
    </div>
  );
}

export function RequireAuth({ children }: PropsWithChildren) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <LoadingPanel />;
  if (status === "unsupported") return <UnsupportedBrowserNotice />;
  if (status === "anonymous") {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }
  return <>{children}</>;
}

export function RequireAccess({
  accountType,
  roles,
  children,
}: PropsWithChildren<{ accountType?: "ADMIN" | "EMPLOYEE"; roles?: EmployeeRole[] }>) {
  const { account } = useAuth();
  if (!account) return null;
  if (canAccess(account, { accountType, roles })) return <>{children}</>;

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center">
      <ShieldAlert className="w-8 h-8 text-amber-500 mx-auto" />
      <h2 className="mt-3 text-base font-bold text-slate-900">Không có quyền truy cập</h2>
      <p className="mt-1 text-sm text-slate-600">
        Tài khoản hiện tại không được cấp quyền cho khu vực này.
      </p>
      <Link to="/app" className="mt-4 inline-block text-sm font-semibold text-emerald-700 hover:underline">
        Về trang làm việc mặc định
      </Link>
    </div>
  );
}
