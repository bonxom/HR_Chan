import React, { useState } from 'react';
import { useParams } from 'react-router';
import { CheckCircle2, XCircle, Mail, Key } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { showToast } from '../../shared/components/ui/Toast';

export const OfferActionPage: React.FC = () => {
  const { id } = useParams();
  const [decision, setDecision] = useState<'PENDING' | 'ACCEPTED' | 'DECLINED'>('PENDING');
  const [declineReason, setDeclineReason] = useState('');
  const [isDeclining, setIsDeclining] = useState(false);

  const handleAccept = () => {
    setDecision('ACCEPTED');
    showToast({
      type: 'success',
      title: 'Chúc mừng bạn gia nhập đội ngũ!',
      message: 'Hệ thống đã tự động khởi tạo hộp thư công ty và tài khoản thử việc nội bộ.',
    });
  };

  const handleDecline = () => {
    setDecision('DECLINED');
    setIsDeclining(false);
    showToast({
      type: 'info',
      title: 'Đã từ chối lời mời thử việc',
      message: 'Hệ thống đã cập nhật trạng thái Từ chối thử việc theo quy định BR24.',
    });
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-16">
      <div className="text-center mb-8">
        <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
          Thư Mời Thử Việc &amp; Onboarding (UC2.11)
        </span>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-3">
          Chúc mừng bạn đã trúng tuyển vị trí Senior Backend Engineer!
        </h1>
        <p className="text-xs text-slate-500 mt-1">Mã lời mời: #OFFER-{id || '502'}</p>
      </div>

      <Card className="space-y-6">
        {/* Offer Details */}
        <div className="space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">Thông tin thỏa thuận thử việc:</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-5 bg-slate-50 rounded-2xl border border-slate-200 text-xs">
            <div>
              <span className="text-slate-400 block mb-0.5">Vị trí tiếp nhận</span>
              <span className="font-bold text-slate-900 text-sm">Senior Python / FastAPI Engineer</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Phòng ban công tác</span>
              <span className="font-bold text-slate-900 text-sm">Engineering / Platform Core</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Ngày bắt đầu dự kiến</span>
              <span className="font-bold text-slate-900 text-sm">01/12/2026 (Thứ Ba)</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Thời gian thử việc (BR53)</span>
              <span className="font-bold text-slate-900 text-sm">60 ngày (Theo Điều 25 BLLĐ 2019)</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Quản lý trực tiếp phụ trách</span>
              <span className="font-bold text-slate-900 text-sm">Nguyễn Thị Hương (Engineering Manager)</span>
            </div>
            <div>
              <span className="text-slate-400 block mb-0.5">Địa điểm làm việc</span>
              <span className="font-bold text-slate-900 text-sm">Tòa nhà Keangnam Landmark 72, Hà Nội</span>
            </div>
          </div>
        </div>

        {decision === 'ACCEPTED' && (
          <div className="p-6 bg-teal-50 border border-teal-200 rounded-2xl text-left space-y-4">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-8 h-8 text-teal-600 shrink-0" />
              <div>
                <h4 className="text-base font-bold text-teal-900">Bạn đã chấp nhận lời mời thử việc!</h4>
                <p className="text-xs text-teal-700">Tài khoản nội bộ đã được cấp tự động (UC2.12).</p>
              </div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-teal-100 text-xs space-y-2">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-teal-600" />
                <span className="text-slate-600">Email công ty được tạo:</span>
                <span className="font-mono font-bold text-slate-900">nam.hoang@hrchan.vn</span>
              </div>
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-teal-600" />
                <span className="text-slate-600">Kích hoạt tài khoản:</span>
                <span className="text-slate-800">
                  Sử dụng tính năng <strong>Quên mật khẩu (UC5.18)</strong> với OTP gửi về hộp thư công ty để đặt mật khẩu lần đầu.
                </span>
              </div>
            </div>
          </div>
        )}

        {decision === 'DECLINED' && (
          <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-center space-y-2">
            <XCircle className="w-10 h-10 text-rose-600 mx-auto" />
            <h4 className="text-base font-bold text-rose-900">Bạn đã từ chối lời mời thử việc</h4>
            <p className="text-xs text-rose-700">Hệ thống đã ghi nhận phản hồi và thông báo tới ban tuyển dụng.</p>
          </div>
        )}

        {decision === 'PENDING' && !isDeclining && (
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4 border-t border-slate-100">
            <Button size="lg" onClick={handleAccept} leftIcon={<CheckCircle2 className="w-5 h-5" />}>
              Đồng ý thử việc &amp; Nhận tài khoản
            </Button>
            <Button variant="danger" size="lg" onClick={() => setIsDeclining(true)}>
              Từ chối lời mời
            </Button>
          </div>
        )}

        {isDeclining && (
          <div className="p-5 border border-rose-200 rounded-2xl bg-rose-50/40 space-y-4">
            <h4 className="text-sm font-bold text-rose-900">Xác nhận từ chối thử việc:</h4>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Lý do từ chối (tùy chọn, tối đa 500 ký tự)</label>
              <textarea
                rows={2}
                value={declineReason}
                onChange={(e) => setDeclineReason(e.target.value)}
                placeholder="Nhập lý do của bạn..."
                className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setIsDeclining(false)}>
                Quay lại
              </Button>
              <Button variant="danger" size="sm" onClick={handleDecline}>
                Xác nhận từ chối
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
