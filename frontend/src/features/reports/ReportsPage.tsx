import React from 'react';
import { Download, TrendingUp, Sparkles, CheckCircle2 } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { showToast } from '../../shared/components/ui/Toast';

export const ReportsPage: React.FC = () => {
  const handleExport = (format: 'Excel' | 'PDF') => {
    showToast({
      type: 'success',
      title: 'Đang xuất báo cáo tổng hợp',
      message: `Báo cáo dạng ${format} đã được tạo và ghi nhận vào nhật ký kiểm toán (BR12, UC1.15).`,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Báo cáo &amp; Phân tích Tuyển dụng</h2>
          <p className="text-xs text-slate-500 mt-1">
            Số liệu thống kê phễu tuyển dụng, mức độ chuẩn hóa của mô hình AI và hiệu quả thử việc (UC1.11 &mdash; UC1.15).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => handleExport('Excel')} leftIcon={<Download className="w-3.5 h-3.5" />}>
            Xuất Excel (.xlsx)
          </Button>
          <Button size="sm" onClick={() => handleExport('PDF')} leftIcon={<Download className="w-3.5 h-3.5" />}>
            Xuất PDF
          </Button>
        </div>
      </div>

      {/* Recruitment Funnel (UC1.12) */}
      <Card className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Phễu Tuyển dụng Toàn diện (Recruitment Funnel)</h3>
          </div>
          <span className="text-[11px] text-slate-400 font-medium">Khoảng thời gian: 30 ngày gần nhất (BR13)</span>
        </div>

        <div className="space-y-3 pt-2">
          {[
            { stage: '1. Gửi hồ sơ ban đầu (CV Submission)', count: 42, pct: '100%', color: 'bg-slate-700' },
            { stage: '2. Nộp hồ sơ chính thức (Xác thực OTP)', count: 35, pct: '83.3%', color: 'bg-emerald-800' },
            { stage: '3. Được mời phỏng vấn (AI & HR duyệt)', count: 18, pct: '51.4%', color: 'bg-emerald-600' },
            { stage: '4. Đã tham gia phỏng vấn', count: 15, pct: '83.3%', color: 'bg-teal-600' },
            { stage: '5. Đạt kết quả phỏng vấn', count: 8, pct: '53.3%', color: 'bg-teal-500' },
            { stage: '6. Đồng ý lời mời thử việc & Cấp tài khoản', count: 6, pct: '75.0%', color: 'bg-sky-500' },
            { stage: '7. Đạt thử việc chính thức', count: 5, pct: '83.3%', color: 'bg-indigo-600' },
          ].map((item, idx) => (
            <div key={idx} className="space-y-1">
              <div className="flex justify-between text-xs font-semibold text-slate-700">
                <span>{item.stage}</span>
                <span className="font-mono">
                  {item.count} ứng viên <span className="text-slate-400 font-normal">({item.pct})</span>
                </span>
              </div>
              <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden">
                <div className={`h-full ${item.color} rounded-full transition-all`} style={{ width: item.pct }} />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Two Column Analytics (AI Accuracy & Probation metrics) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* AI Screening Accuracy (UC1.13) */}
        <Card className="space-y-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Thống kê Sàng lọc AI (UC1.13)</h3>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Tỷ lệ tự động mời phỏng vấn (&ge; 80đ):</span>
              <span className="font-extrabold text-emerald-700 text-sm">48.6%</span>
            </div>
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Tỷ lệ chuyển HR xem xét thủ công:</span>
              <span className="font-extrabold text-amber-700 text-sm">51.4%</span>
            </div>
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Mức độ tương thích giữa AI và HR:</span>
              <span className="font-extrabold text-teal-700 text-sm">88.5%</span>
            </div>
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Thời gian trung bình từ nộp đến mời PV:</span>
              <span className="font-extrabold text-slate-900 text-sm">1.8 giờ</span>
            </div>
          </div>
        </Card>

        {/* Probation Success Metrics (UC1.14) */}
        <Card className="space-y-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-teal-600" />
            <h3 className="text-sm font-bold text-slate-900">Hiệu quả Thử việc (UC1.14)</h3>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Tỷ lệ Đạt thử việc chính thức:</span>
              <span className="font-extrabold text-teal-700 text-sm">83.3%</span>
            </div>
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Tỷ lệ nộp task đúng hạn:</span>
              <span className="font-extrabold text-emerald-700 text-sm">92.0%</span>
            </div>
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Số task trung bình mỗi đợt thử việc:</span>
              <span className="font-extrabold text-slate-900 text-sm">8 task</span>
            </div>
            <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-slate-600">Thời gian thử việc trung bình:</span>
              <span className="font-extrabold text-slate-900 text-sm">60 ngày</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};
