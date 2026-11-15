import { useState, type FormEvent } from "react";
import { LogOut, ShieldCheck } from "lucide-react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { ApiError } from "@/shared/services/client";
import { useAuth } from "./AuthProvider";

const MIN_PASSWORD = 8;

const STATUS_LABELS: Record<string, string> = {
  PENDING_SETUP: "Chờ thiết lập mật khẩu",
  ACTIVE: "Đang hoạt động",
  LOCKED: "Đã khóa",
  PASSWORD_RESET_REQUIRED: "Cần đặt lại mật khẩu",
  DISABLED: "Đã vô hiệu hóa",
};

export function AccountPage() {
  const { account, changePassword, logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!account) return null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (newPassword.length < MIN_PASSWORD) {
      setError(`Mật khẩu mới phải có ít nhất ${MIN_PASSWORD} ký tự.`);
      return;
    }
    if (newPassword !== confirmation) {
      setError("Xác nhận mật khẩu không khớp.");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setSuccess("Đã đổi mật khẩu. Các phiên đăng nhập khác đã bị thu hồi.");
    } catch (changeError) {
      if (changeError instanceof ApiError && changeError.code === "invalid_current_password") {
        setError("Mật khẩu hiện tại không đúng.");
      } else if (changeError instanceof ApiError && changeError.code === "invalid_password") {
        setError(changeError.message);
      } else {
        setError("Không thể đổi mật khẩu lúc này. Vui lòng thử lại.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-slate-900">Tài khoản của tôi</h2>
        <p className="text-xs text-slate-500 mt-1">
          Thông tin định danh hiện hành và mật khẩu đăng nhập nội bộ.
        </p>
      </div>

      <Card>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Họ và tên</dt>
            <dd className="font-semibold text-slate-900 mt-1">{account.fullName}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Email</dt>
            <dd className="font-semibold text-slate-900 mt-1">{account.email}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Loại tài khoản</dt>
            <dd className="mt-1">
              <Badge variant={account.accountType === "ADMIN" ? "danger" : "neutral"}>
                {account.accountType === "ADMIN" ? "Quản trị hệ thống" : "Nhân viên"}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Trạng thái</dt>
            <dd className="mt-1">
              <Badge variant={account.status === "ACTIVE" ? "success" : "warning"}>
                {STATUS_LABELS[account.status] ?? account.status}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">Vai trò nghiệp vụ</dt>
            <dd className="font-semibold text-slate-900 mt-1">
              {account.roles.length ? account.roles.join(", ") : "Không có vai trò nghiệp vụ"}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">
              Đăng nhập gần nhất
            </dt>
            <dd className="font-semibold text-slate-900 mt-1">
              {account.lastLoginAt ? new Date(account.lastLoginAt).toLocaleString("vi-VN") : "—"}
            </dd>
          </div>
        </dl>
        <div className="mt-6 border-t border-slate-200 pt-4">
          <Button
            variant="outline"
            leftIcon={<LogOut className="w-4 h-4" />}
            onClick={() => void logout()}
          >
            Đăng xuất
          </Button>
        </div>
      </Card>

      <Card>
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-600" />
          <h3 className="text-base font-bold text-slate-900">Đổi mật khẩu</h3>
        </div>
        <form className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 items-end" onSubmit={handleSubmit} noValidate>
          <Input
            label="Mật khẩu hiện tại"
            name="current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
          <Input
            label="Mật khẩu mới"
            name="new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
          />
          <Input
            label="Xác nhận mật khẩu mới"
            name="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />
          <div className="sm:col-span-3 space-y-2">
            {error && (
              <p role="alert" className="text-sm text-rose-600">
                {error}
              </p>
            )}
            {success && (
              <p role="status" className="text-sm text-emerald-700">
                {success}
              </p>
            )}
            <Button type="submit" isLoading={submitting}>
              Cập nhật mật khẩu
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
