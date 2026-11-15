import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { CheckCircle2, KeyRound } from "lucide-react";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { ApiError } from "@/shared/services/client";
import { completePassword } from "./api";

const MIN_PASSWORD = 8;
const MAX_PASSWORD = 128;

/** Read the fragment token into memory and immediately remove it from the URL. */
export function consumeFragmentToken(): string {
  if (typeof window === "undefined") return "";
  const hash = window.location.hash;
  if (!hash.startsWith("#token=")) return "";
  const token = decodeURIComponent(hash.slice("#token=".length));
  window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  return token;
}

export function CompletePasswordPage() {
  const [token] = useState(consumeFragmentToken);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD || password.length > MAX_PASSWORD) {
      setError(`Mật khẩu phải có từ ${MIN_PASSWORD} đến ${MAX_PASSWORD} ký tự.`);
      return;
    }
    if (password !== confirmation) {
      setError("Xác nhận mật khẩu không khớp.");
      return;
    }
    setSubmitting(true);
    try {
      await completePassword(token, password);
      setDone(true);
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.code === "invalid_password_link") {
        setExpired(true);
      } else if (submitError instanceof ApiError && submitError.code === "invalid_password") {
        setError(submitError.message);
      } else {
        setError("Không thể đặt mật khẩu lúc này. Vui lòng thử lại.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 p-6">
      <Card className="w-full max-w-md p-8">
        <div className="flex items-center gap-2 text-emerald-700">
          <KeyRound className="w-5 h-5" />
          <h1 className="text-xl font-extrabold text-slate-900">Đặt mật khẩu</h1>
        </div>

        {!token ? (
          <div className="mt-5 space-y-3">
            <p className="text-sm text-slate-600" role="alert">
              Liên kết không hợp lệ hoặc đã hết hạn. Hãy yêu cầu một email mới.
            </p>
            <Link to="/forgot-password" className="text-sm font-semibold text-emerald-700 hover:underline">
              Yêu cầu liên kết mới
            </Link>
          </div>
        ) : done ? (
          <div className="mt-5 space-y-3">
            <div className="flex items-start gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <p className="text-sm text-emerald-900" role="status">
                Mật khẩu đã được cập nhật. Hãy đăng nhập bằng mật khẩu mới.
              </p>
            </div>
            <Link to="/login" className="text-sm font-semibold text-emerald-700 hover:underline">
              Đi tới đăng nhập
            </Link>
          </div>
        ) : expired ? (
          <div className="mt-5 space-y-3">
            <p className="text-sm text-slate-600" role="alert">
              Liên kết không hợp lệ hoặc đã hết hạn. Hãy yêu cầu một email mới.
            </p>
            <Link to="/forgot-password" className="text-sm font-semibold text-emerald-700 hover:underline">
              Yêu cầu liên kết mới
            </Link>
          </div>
        ) : (
          <form className="mt-5 space-y-4" onSubmit={handleSubmit} noValidate>
            <p className="text-sm text-slate-500">
              Mật khẩu từ {MIN_PASSWORD} đến {MAX_PASSWORD} ký tự. Không phân biệt quy tắc ký tự đặc
              biệt.
            </p>
            <Input
              label="Mật khẩu mới"
              name="new-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <Input
              label="Xác nhận mật khẩu"
              name="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
            {error && (
              <p role="alert" className="text-sm text-rose-600">
                {error}
              </p>
            )}
            <Button type="submit" isLoading={submitting} className="w-full">
              Lưu mật khẩu
            </Button>
            <Link to="/login" className="block text-center text-xs font-semibold text-slate-600 hover:text-slate-900">
              &larr; Quay lại đăng nhập
            </Link>
          </form>
        )}
      </Card>
    </div>
  );
}
