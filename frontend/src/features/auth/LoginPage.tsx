import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { Briefcase, LogIn } from "lucide-react";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { ApiError } from "@/shared/services/client";
import { useAuth } from "./AuthProvider";
import { DEV_LOGINS, devLoginsEnabled, type DevLogin } from "./devLogins";
import { UnsupportedBrowserNotice, landingPathFor } from "./RequireAuth";
import { AmbientBackdrop } from "@/shared/components/ui/Glass";

export function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "authentication_unavailable") {
      return "Backend chưa cấu hình xác thực: thêm JWT_SECRET và LIMITER_SECRET vào backend/.env rồi khởi động lại API.";
    }
    if (error.status === 429) return "Quá nhiều lần thử. Vui lòng đợi rồi thử lại.";
    if (error.status === 403) return "Yêu cầu đăng nhập không đến từ nguồn được tin cậy.";
    if (error.status === 401) return "Email hoặc mật khẩu không đúng.";
  }
  return "Không thể đăng nhập lúc này. Vui lòng thử lại.";
}

export function LoginPage() {
  const { status, login, devLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [quickAccount, setQuickAccount] = useState<string | null>(null);

  const requested = (location.state as { from?: string } | null)?.from;
  // Only in-app workspace paths may be restored after login.
  const from = requested?.startsWith("/app") ? requested : undefined;

  if (status === "unsupported") return <UnsupportedBrowserNotice />;
  if (status === "authenticated") return <Navigate to={from ?? "/app"} replace />;

  async function handleDevLogin(dev: DevLogin) {
    setError(null);
    setQuickAccount(dev.id);
    try {
      const account = await devLogin(dev.id);
      navigate(from ?? landingPathFor(account), { replace: true });
    } catch (devError) {
      if (devError instanceof ApiError && devError.status === 404) {
        setError(
          "Backend chưa bật đăng nhập nhanh. Đặt DEV_LOGIN_ENABLED=true trong backend/.env rồi khởi động lại API.",
        );
      } else if (devError instanceof ApiError && devError.status === 409) {
        setError(devError.message);
      } else {
        setError(loginErrorMessage(devError));
      }
    } finally {
      setQuickAccount(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError("Vui lòng nhập email và mật khẩu.");
      return;
    }
    setSubmitting(true);
    try {
      const account = await login(email.trim(), password);
      navigate(from ?? landingPathFor(account), { replace: true });
    } catch (loginError) {
      setError(loginErrorMessage(loginError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative isolate min-h-screen flex items-center justify-center bg-canvas p-6">
      <AmbientBackdrop />
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2.5 justify-center mb-6">
          <div className="w-10 h-10 rounded-xl bg-brand flex items-center justify-center text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]">
            <Briefcase className="w-5 h-5" />
          </div>
          <div className="leading-tight">
            <div className="font-extrabold text-lg text-slate-900">HR_Chan</div>
            <div className="text-xs text-slate-500">Workspace nội bộ</div>
          </div>
        </div>

        <Card className="p-8">
          <h1 className="text-xl font-extrabold text-slate-900">Đăng nhập nội bộ</h1>
          <p className="mt-1 text-sm text-slate-500">
            Sử dụng email công ty được cấp trên tên miền sis.hust.edu.vn.
          </p>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
            <Input
              label="Email công việc"
              name="email"
              type="email"
              autoComplete="username"
              placeholder="ten.ban@sis.hust.edu.vn"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <Input
              label="Mật khẩu"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="Nhập mật khẩu"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {error && (
              <p role="alert" className="text-sm text-rose-600">
                {error}
              </p>
            )}
            <Button type="submit" isLoading={submitting} leftIcon={<LogIn className="w-4 h-4" />} className="w-full">
              Đăng nhập
            </Button>
          </form>

          <div className="mt-5 flex items-center justify-between text-xs">
            <Link to="/forgot-password" className="font-semibold text-emerald-700 hover:underline">
              Quên mật khẩu?
            </Link>
            <Link to="/" className="text-slate-500 hover:text-slate-800">
              Về cổng ứng viên
            </Link>
          </div>

          {devLoginsEnabled && (
            <div className="mt-6 border-t border-dashed border-slate-300 pt-4">
              <p className="text-xs font-semibold text-slate-500">
                Đăng nhập nhanh (chỉ môi trường dev)
              </p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {DEV_LOGINS.map((dev) => (
                  <Button
                    key={dev.id}
                    type="button"
                    size="sm"
                    variant="outline"
                    aria-label={`Đăng nhập nhanh ${dev.label}`}
                    isLoading={quickAccount === dev.id}
                    onClick={() => void handleDevLogin(dev)}
                  >
                    {dev.label}
                  </Button>
                ))}
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">
                Nút dùng endpoint dev <code className="text-slate-500">/auth/dev-login</code> (bật
                bằng <code className="text-slate-500">DEV_LOGIN_ENABLED=true</code>) nên vẫn vào được
                sau khi đổi mật khẩu. Tài khoản mẫu:{" "}
                <code className="text-slate-500">uv run python -m app.cli seed-dev-accounts</code>.
                Không xuất hiện trong bản build production.
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
