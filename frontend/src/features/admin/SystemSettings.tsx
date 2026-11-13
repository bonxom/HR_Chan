import React, { useState } from 'react';
import { Save, Clock, Sparkles, Calendar } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { Input } from '../../shared/components/ui/Input';
import { showToast } from '../../shared/components/ui/Toast';

export const SystemSettings: React.FC = () => {
  const [settings] = useState(mockStore.getSettings());

  const [workingStart, setWorkingStart] = useState(settings.workingHours.start);
  const [workingEnd, setWorkingEnd] = useState(settings.workingHours.end);
  const [otpExpiry, setOtpExpiry] = useState(settings.otpExpiryMinutes);
  const [responseDays, setResponseDays] = useState(settings.candidateResponseDays);
  const [hrDays, setHrDays] = useState(settings.hrReviewDays);
  const [retentionMonths, setRetentionMonths] = useState(settings.retentionMonths);
  const [autoInviteThreshold, setAutoInviteThreshold] = useState(settings.defaultAutoInviteThreshold);
  const [suggestionThreshold, setSuggestionThreshold] = useState(settings.defaultSuggestionThreshold);

  const handleSave = () => {
    mockStore.updateSettings({
      workingHours: { start: workingStart, end: workingEnd },
      otpExpiryMinutes: Number(otpExpiry),
      candidateResponseDays: Number(responseDays),
      hrReviewDays: Number(hrDays),
      retentionMonths: Number(retentionMonths),
      defaultAutoInviteThreshold: Number(autoInviteThreshold),
      defaultSuggestionThreshold: Number(suggestionThreshold),
    });

    showToast({
      type: 'success',
      title: 'Đã lưu cấu hình hệ thống (UC5.12)',
      message: 'Các tham số mới có hiệu lực ngay lập tức cho các thao tác phát sinh sau thời điểm lưu (BR45).',
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Cấu hình Tham số Hệ thống (UC5.12 &mdash; UC5.16)</h2>
          <p className="text-xs text-slate-500 mt-1">
            Điều chỉnh lịch làm việc, thời hạn phản hồi, lưu trữ dữ liệu cá nhân và ngưỡng AI tự động.
          </p>
        </div>
        <Button onClick={handleSave} leftIcon={<Save className="w-4 h-4" />}>
          Lưu tất cả cấu hình
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Working Calendar (UC5.13) */}
        <Card className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Calendar className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Giờ làm việc &amp; Xếp lịch phỏng vấn (UC5.13)</h3>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Giờ bắt đầu làm việc *"
              type="time"
              value={workingStart}
              onChange={(e) => setWorkingStart(e.target.value)}
            />
            <Input
              label="Giờ kết thúc làm việc *"
              type="time"
              value={workingEnd}
              onChange={(e) => setWorkingEnd(e.target.value)}
            />
          </div>

          <div className="text-xs text-slate-500 space-y-1 bg-slate-50 p-3 rounded-xl">
            <p>&bull; Phỏng vấn chỉ được xếp trong khung giờ hành chính (BR09).</p>
            <p>&bull; Ngày làm việc: Thứ Hai &mdash; Thứ Sáu (không tính Thứ Bảy, Chủ Nhật và ngày lễ).</p>
          </div>
        </Card>

        {/* Expiries & Retention (UC5.15) */}
        <Card className="space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Clock className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Thời hạn &amp; Lưu trữ Dữ liệu (UC5.15)</h3>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Hiệu lực mã OTP (phút) *"
              type="number"
              min={1}
              max={15}
              value={otpExpiry}
              onChange={(e) => setOtpExpiry(Number(e.target.value))}
            />
            <Input
              label="Hạn phản hồi ứng viên (ngày làm việc) *"
              type="number"
              min={1}
              max={5}
              value={responseDays}
              onChange={(e) => setResponseDays(Number(e.target.value))}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Hạn HR xét duyệt hồ sơ (ngày) *"
              type="number"
              value={hrDays}
              onChange={(e) => setHrDays(Number(e.target.value))}
            />
            <Input
              label="Thời hạn lưu hồ sơ (tháng) *"
              type="number"
              value={retentionMonths}
              onChange={(e) => setRetentionMonths(Number(e.target.value))}
            />
          </div>
        </Card>

        {/* AI Thresholds (UC5.16) */}
        <Card className="space-y-4 md:col-span-2">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Ngưỡng chấm điểm &amp; Gợi ý AI (UC5.16)</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-slate-700">Ngưỡng AI tự động mời phỏng vấn mặc định:</span>
                <span className="text-emerald-700 font-extrabold">{autoInviteThreshold}/100</span>
              </div>
              <input
                type="range"
                min={60}
                max={95}
                value={autoInviteThreshold}
                onChange={(e) => setAutoInviteThreshold(Number(e.target.value))}
                className="w-full accent-emerald-600"
              />
              <p className="text-[11px] text-slate-400">
                Áp dụng cho các tin tuyển dụng mới tạo (BR47). Hồ sơ vượt ngưỡng và đạt đủ tiêu chí bắt buộc sẽ được mời tự động.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-slate-700">Ngưỡng tối thiểu để gợi ý việc làm cho CV:</span>
                <span className="text-emerald-700 font-extrabold">{suggestionThreshold}%</span>
              </div>
              <input
                type="range"
                min={40}
                max={80}
                value={suggestionThreshold}
                onChange={(e) => setSuggestionThreshold(Number(e.target.value))}
                className="w-full accent-emerald-600"
              />
              <p className="text-[11px] text-slate-400">
                Chỉ các vị trí có độ phù hợp từ ngưỡng này trở lên mới được hiển thị trong danh sách gợi ý (tối đa 5 vị trí - BR18).
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
