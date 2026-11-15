import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { MailCheck } from "lucide-react";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { ApiError } from "@/shared/services/client";
import { requestPasswordRecovery } from "./api";

export function RecoveryPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [throttled, setThrottled] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) return;
    setSubmitting(true);
    setThrottled(false);
    try {
      await requestPasswordRecovery(email.trim());
    } catch (error) {
      // The response stays generic; only an IP-level throttle is exposed.
      setThrottled(error instanceof ApiError && error.status === 429);
    } finally {
      setSubmitting(false);
      setSubmitted(true);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 p-6">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-xl font-extrabold text-slate-900">Khôi phục mật khẩu</h1>
        <p className="mt-1 text-sm text-slate-500">
          Nhập email công ty. Nếu tài khoản tồn tại và đang hoạt động, chúng tôi sẽ gửi liên kết đặt
          lại mật khẩu trong vòng 30 phút.
        </p>

        {submitted ? (
          <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="flex items-start gap-2.5">
              <MailCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <p className="text-sm text-emerald-900" role="status">
                Nếu email hợp lệ và thuộc tài khoản đang hoạt động, liên kết đặt lại mật khẩu đã được
                gửi. Hãy kiểm tra hộp thư nội bộ của bạn.
              </p>
            </div>
            {throttled && (
              <p className="mt-2 text-xs text-amber-700">
                Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau ít phút.
              </p>
            )}
            <div className="mt-4 flex items-center gap-4 text-xs">
              <Link to="/login" className="font-semibold text-emerald-700 hover:underline">
                Quay lại đăng nhập
              </Link>
              <button
                type="button"
                className="text-slate-600 hover:text-slate-900"
                onClick={() => setSubmitted(false)}
              >
                Gửi lại yêu cầu khác
              </button>
            </div>
          </div>
        ) : (
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
            <Button type="submit" isLoading={submitting} className="w-full">
              Gửi liên kết đặt lại
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
