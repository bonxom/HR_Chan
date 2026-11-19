import React, { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Mail, AlertCircle, RefreshCw } from 'lucide-react';
import { Modal } from '../../shared/components/ui/Modal';
import { Button } from '../../shared/components/ui/Button';
import { ApiError } from '../../shared/services/client';
import { requestApplicationOtp, submitApplication } from './api';
import type { ApplicationCreated } from './types';
import { formatWait, withRetry } from './validation';

interface OtpModalProps {
  isOpen: boolean;
  email: string;
  submissionId: number;
  submissionToken: string;
  jobId: number;
  /** Thời điểm hết hạn/được gửi lại do server trả về; không tự tính ở trình duyệt. */
  expiresAt: string;
  resendAvailableAt: string;
  onClose: () => void;
  onSubmitted: (result: ApplicationCreated) => void;
}

const CODE_LENGTH = 6;
const toMs = (iso: string) => {
  const value = Date.parse(iso);
  return Number.isNaN(value) ? 0 : value;
};
const clock = (seconds: number) =>
  `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;

export const OtpModal: React.FC<OtpModalProps> = ({
  isOpen,
  email,
  submissionId,
  submissionToken,
  jobId,
  expiresAt,
  resendAvailableAt,
  onClose,
  onSubmitted,
}) => {
  const [code, setCode] = useState('');
  const [fieldError, setFieldError] = useState('');
  const [alertMessage, setAlertMessage] = useState('');
  const [notice, setNotice] = useState('');
  const [times, setTimes] = useState({ expires: toMs(expiresAt), resend: toMs(resendAvailableAt) });
  const [lockedUntil, setLockedUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setTimes({ expires: toMs(expiresAt), resend: toMs(resendAvailableAt) });
  }, [expiresAt, resendAvailableAt]);

  useEffect(() => {
    if (!isOpen) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [isOpen]);

  const capability = { submissionId, submissionToken, jobId };

  const submit = useMutation({
    mutationFn: (otpCode: string) => submitApplication({ ...capability, otpCode }),
    onSuccess: (result) => onSubmitted(result),
    onError: (error) => {
      if (error instanceof ApiError) {
        const issue = error.validationIssues?.find((item) => item.loc[item.loc.length - 1] === 'otp_code');
        if (error.status === 422 && issue) {
          setFieldError(issue.msg);
          return;
        }
        if (error.status === 429 && error.code === 'otp_locked') {
          const current = Date.now();
          setNow(current);
          setLockedUntil(current + (error.retryAfter ?? 900) * 1000);
          setAlertMessage(error.message);
          return;
        }
        setAlertMessage(withRetry(error.message, error.retryAfter, error.status === 429));
        return;
      }
      setAlertMessage('Không kết nối được máy chủ. Vui lòng thử lại.');
    },
  });

  const resend = useMutation({
    mutationFn: () => requestApplicationOtp(capability),
    onSuccess: (issued) => {
      setTimes({ expires: toMs(issued.expiresAt), resend: toMs(issued.resendAvailableAt) });
      setCode('');
      setFieldError('');
      setAlertMessage('');
      setNotice('Đã gửi mã mới tới email của bạn.');
    },
    onError: (error) => {
      setNotice('');
      if (error instanceof ApiError) {
        if (error.status === 429 && error.retryAfter) setTimes((t) => ({ ...t, resend: Date.now() + error.retryAfter! * 1000 }));
        setAlertMessage(withRetry(error.message, error.retryAfter, error.status === 429));
      } else {
        setAlertMessage('Không kết nối được máy chủ. Vui lòng thử lại.');
      }
    },
  });

  const lockedSeconds = Math.max(0, (lockedUntil - now) / 1000);
  const isLocked = lockedSeconds > 0;
  const resendSeconds = Math.max(0, (times.resend - now) / 1000);
  const expiresSeconds = (times.expires - now) / 1000;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (submit.isPending || isLocked) return;
    if (code.length !== CODE_LENGTH) {
      setFieldError('Vui lòng nhập đủ 6 chữ số của mã xác thực.');
      return;
    }
    setFieldError('');
    setAlertMessage('');
    setNotice('');
    submit.mutate(code);
  };

  const handleResend = () => {
    if (resendSeconds > 0 || resend.isPending || isLocked) return;
    setAlertMessage('');
    setNotice('');
    resend.mutate();
  };

  const resendLabel =
    resendSeconds > 0 && resendSeconds <= 3600 ? `Gửi lại mã (${clock(Math.ceil(resendSeconds))})` : 'Gửi lại mã';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Xác thực email" maxWidth="md">
      <form onSubmit={handleSubmit} noValidate className="text-center py-2 space-y-4">
        <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto">
          <Mail className="w-6 h-6" />
        </div>

        <div>
          <h4 className="text-sm font-bold text-slate-900">Kiểm tra hộp thư điện tử</h4>
          <p className="text-xs text-slate-600 mt-1 break-words">
            Mã gồm 6 chữ số đã được gửi tới <strong className="text-slate-800">{email}</strong>.
          </p>
          {expiresSeconds > 0 && expiresSeconds <= 600 && (
            <p className="text-[11px] text-slate-500 mt-1">Mã còn hiệu lực {clock(Math.ceil(expiresSeconds))}.</p>
          )}
          {expiresSeconds <= 0 && times.expires > 0 && (
            <p className="text-[11px] text-amber-700 mt-1">Mã đã hết hạn. Hãy gửi lại mã.</p>
          )}
        </div>

        <div className="text-left">
          <label htmlFor="otp-code" className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
            Mã xác thực
          </label>
          <input
            id="otp-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={CODE_LENGTH}
            value={code}
            disabled={isLocked}
            aria-invalid={fieldError ? true : undefined}
            aria-describedby={fieldError ? 'otp-code-error' : undefined}
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, '').slice(0, CODE_LENGTH));
              setFieldError('');
            }}
            className={`w-full text-center tracking-[0.5em] text-xl font-bold bg-white border rounded-xl py-3 outline-none focus:ring-2 transition-all ${
              fieldError
                ? 'border-rose-400 focus:border-rose-400 focus:ring-rose-400'
                : 'border-slate-300 focus:border-emerald-500 focus:ring-emerald-200'
            }`}
          />
          {fieldError && (
            <p id="otp-code-error" className="mt-1 text-xs text-rose-600">
              {fieldError}
            </p>
          )}
        </div>

        {alertMessage && (
          <div role="alert" className="flex items-start justify-center gap-1.5 text-xs text-rose-600 font-medium">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{isLocked ? `${alertMessage} Vui lòng thử lại sau ${formatWait(lockedSeconds)}.` : alertMessage}</span>
          </div>
        )}
        {notice && (
          <p role="status" className="text-xs text-emerald-700 font-medium">
            {notice}
          </p>
        )}

        <div className="pt-2 flex flex-col gap-3">
          <Button type="submit" size="md" className="w-full" isLoading={submit.isPending} disabled={isLocked}>
            Xác nhận và nộp hồ sơ
          </Button>
          <button
            type="button"
            onClick={handleResend}
            disabled={resendSeconds > 0 || resend.isPending || isLocked}
            className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 disabled:text-slate-400 cursor-pointer disabled:cursor-not-allowed flex items-center justify-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>{resendLabel}</span>
          </button>
        </div>
      </form>
    </Modal>
  );
};
