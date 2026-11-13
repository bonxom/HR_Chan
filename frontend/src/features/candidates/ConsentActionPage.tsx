import React, { useState } from 'react';
import { ShieldCheck, CheckCircle2 } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { showToast } from '../../shared/components/ui/Toast';

export const ConsentActionPage: React.FC = () => {
  const [hasConsented, setHasConsented] = useState(false);

  const handleConsent = () => {
    setHasConsented(true);
    showToast({
      type: 'success',
      title: 'Đã lưu hồ sơ thành công',
      message: 'Hồ sơ của bạn được lưu trữ an toàn trong 12 tháng để ưu tiên liên hệ cho các đợt tuyển dụng sau (BR21).',
    });
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-16">
      <div className="text-center mb-8">
        <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto mb-3">
          <ShieldCheck className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-extrabold text-slate-900">Đồng ý Lưu trữ Hồ sơ Ứng tuyển (UC2.13)</h1>
        <p className="text-xs text-slate-500 mt-1">Căn cứ theo Nghị định 13/2023/NĐ-CP và Quy tắc BR21</p>
      </div>

      <Card className="space-y-6">
        <div className="text-xs text-slate-600 space-y-3 leading-relaxed">
          <p>
            Dù chưa có cơ hội đồng hành trong vị trí hiện tại, chúng tôi đánh giá rất cao năng lực và tiềm năng của bạn.
            Chúng tôi mong muốn được phép lưu trữ thông tin hồ sơ của bạn trong hệ thống với các cam kết:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-slate-700 font-medium">
            <li>Thời hạn lưu trữ tối đa: <strong>12 tháng</strong> kể từ ngày xác nhận.</li>
            <li>Chỉ sử dụng để tự động gửi thông báo khi công ty mở các vị trí tương thích mới.</li>
            <li>Bạn có toàn quyền yêu cầu rút lại sự đồng ý hoặc xóa thông tin bất kỳ lúc nào.</li>
            <li>Dữ liệu được mã hóa an toàn và không chia sẻ cho bên thứ ba.</li>
          </ul>
        </div>

        {hasConsented ? (
          <div className="p-5 bg-teal-50 border border-teal-200 rounded-xl text-center space-y-2">
            <CheckCircle2 className="w-8 h-8 text-teal-600 mx-auto" />
            <h4 className="text-sm font-bold text-teal-900">Cảm ơn bạn đã xác nhận!</h4>
            <p className="text-xs text-teal-700">
              Hệ thống đã gia hạn thời gian lưu trữ hồ sơ đến ngày <strong>13/11/2027</strong>.
            </p>
          </div>
        ) : (
          <div className="pt-4 border-t border-slate-100 flex justify-center">
            <Button size="lg" onClick={handleConsent} leftIcon={<CheckCircle2 className="w-4 h-4" />}>
              Tôi đồng ý lưu hồ sơ 12 tháng
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
};

