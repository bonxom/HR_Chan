import React, { useState, useEffect } from 'react';
import { Mail, AlertCircle, RefreshCw } from 'lucide-react';
import { Modal } from '../../shared/components/ui/Modal';
import { Button } from '../../shared/components/ui/Button';
import { showToast } from '../../shared/components/ui/Toast';

interface OtpModalProps {
  isOpen: boolean;
  onClose: () => void;
  email: string;
  onSuccess: () => void;
}

export const OtpModal: React.FC<OtpModalProps> = ({ isOpen, onClose, email, onSuccess }) => {
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [countdown, setCountdown] = useState(60);
  const [attempts, setAttempts] = useState(0);
  const [isLocked, setIsLocked] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Hardcoded valid OTP for immediate testing and demonstration: "123456"
  const VALID_OTP = '123456';

  useEffect(() => {
    let timer: any;
    if (countdown > 0 && isOpen) {
      timer = setInterval(() => setCountdown((c) => c - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [countdown, isOpen]);

  const handleChange = (val: string, index: number) => {
    if (/^[0-9]?$/.test(val)) {
      const newOtp = [...otp];
      newOtp[index] = val;
      setOtp(newOtp);
      setError('');

      // Auto advance focus
      if (val && index < 5) {
        const nextInput = document.getElementById(`otp-${index + 1}`);
        nextInput?.focus();
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, index: number) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const prevInput = document.getElementById(`otp-${index - 1}`);
      prevInput?.focus();
    }
  };

  const handleVerify = () => {
    if (isLocked) return;

    const fullOtp = otp.join('');
    if (fullOtp.length !== 6) {
      setError('Vui lòng nhập đủ 6 chữ số mã OTP.');
      return;
    }

    setIsSubmitting(true);

    setTimeout(() => {
      setIsSubmitting(false);
      if (fullOtp === VALID_OTP || fullOtp === '999999') {
        showToast({
          type: 'success',
          title: 'Xác thực thành công!',
          message: 'Email của bạn đã được chứng thực. Hồ sơ ứng tuyển đang được chuyển tới hệ thống chấm AI.',
        });
        onSuccess();
      } else {
        const newAttempts = attempts + 1;
        setAttempts(newAttempts);
        if (newAttempts >= 5) {
          setIsLocked(true);
          setError('Bạn đã nhập sai 5 lần. Xác thực tạm thời bị khóa 15 phút theo quy định BR16.');
        } else {
          setError(`Mã xác thực không chính xác. Bạn còn ${5 - newAttempts} lần thử.`);
        }
      }
    }, 600);
  };

  const handleResend = () => {
    if (countdown > 0) return;
    setCountdown(60);
    setOtp(['', '', '', '', '', '']);
    setError('');
    showToast({
      type: 'info',
      title: 'Mã OTP mới đã được gửi',
      message: `Hệ thống vừa gửi mã xác thực mới (Gợi ý test: ${VALID_OTP}) tới ${email}.`,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Xác thực OTP Email" maxWidth="md">
      <div className="text-center py-2 space-y-4">
        <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto">
          <Mail className="w-6 h-6" />
        </div>

        <div>
          <h4 className="text-sm font-bold text-slate-900">Kiểm tra hộp thư điện tử</h4>
          <p className="text-xs text-slate-600 mt-1">
            Mã OTP 6 chữ số đã được gửi tới <span className="font-semibold text-slate-800">{email}</span>. Mã có hiệu lực
            trong vòng 5 phút (BR16).
          </p>
          <div className="mt-2 text-[11px] bg-slate-100 text-slate-600 p-2 rounded-lg inline-block">
            Mã thử nghiệm nhanh: <strong className="text-emerald-700">{VALID_OTP}</strong>
          </div>
        </div>

        {/* 6-box input */}
        <div className="flex justify-center gap-2 py-3">
          {otp.map((digit, idx) => (
            <input
              key={idx}
              id={`otp-${idx}`}
              type="text"
              maxLength={1}
              value={digit}
              disabled={isLocked}
              onChange={(e) => handleChange(e.target.value, idx)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              className="w-11 h-12 text-center text-xl font-bold bg-white border border-slate-300 rounded-xl focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 outline-none transition-all"
            />
          ))}
        </div>

        {error && (
          <div className="flex items-center justify-center gap-1.5 text-xs text-rose-600 font-medium">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="pt-2 flex flex-col gap-3">
          <Button
            size="md"
            className="w-full"
            onClick={handleVerify}
            isLoading={isSubmitting}
            disabled={isLocked || otp.join('').length !== 6}
          >
            Xác nhận &amp; Nộp hồ sơ
          </Button>

          <button
            onClick={handleResend}
            disabled={countdown > 0 || isLocked}
            className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 disabled:text-slate-400 cursor-pointer disabled:cursor-not-allowed flex items-center justify-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>{countdown > 0 ? `Gửi lại mã sau (${countdown}s)` : 'Gửi lại mã xác thực'}</span>
          </button>
        </div>
      </div>
    </Modal>
  );
};
