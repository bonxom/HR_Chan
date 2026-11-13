import React, { useState } from 'react';
import { RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Card } from '../../shared/components/ui/Card';
import { showToast } from '../../shared/components/ui/Toast';

export const WorkHandover: React.FC = () => {
  const [pendingHandovers, setPendingHandovers] = useState([
    {
      id: 1,
      type: 'INTERVIEW',
      title: 'Phỏng vấn ứng viên Đặng Mai Linh (Vị trí Python Engineer)',
      currentOwner: 'Trần Văn Lead (Đang xin nghỉ phép)',
      department: 'Engineering',
      due: '16/11/2026 - 14:00',
    },
    {
      id: 2,
      type: 'PROBATION',
      title: 'Đợt thử việc nhân viên Phạm Quốc Bảo (2 task đang thực hiện)',
      currentOwner: 'Nguyễn Thị Hương (Đã khóa tài khoản tạm thời)',
      department: 'Engineering',
      due: '31/12/2026',
    },
  ]);

  const handleReassign = (id: number) => {
    setPendingHandovers((prev) => prev.filter((item) => item.id !== id));
    showToast({
      type: 'success',
      title: 'Bàn giao công việc thành công (UC5.09)',
      message: 'Công việc dở dang đã được chuyển giao cho nhân sự thay thế hợp lệ cùng phòng ban (BR33). Sự kiện lịch đã được cập nhật.',
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-slate-900">Bàn Giao Công Việc Dở Dang (UC5.09)</h2>
        <p className="text-xs text-slate-500 mt-1">
          Điều phối các buổi phỏng vấn chưa diễn ra hoặc đợt thử việc chưa kết luận của người dùng bị khóa/đổi vai trò (BR32 &mdash; BR35).
        </p>
      </div>

      <div className="p-3.5 bg-sky-50 border border-sky-200 rounded-xl text-xs text-sky-800 flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 text-sky-600 shrink-0 mt-0.5" />
        <span>
          Người nhận bàn giao phải là tài khoản đang hoạt động, có cùng vai trò nghiệp vụ; đối với công việc của Quản lý bộ phận phải cùng phòng ban (BR33).
        </span>
      </div>

      <div className="space-y-4">
        {pendingHandovers.map((item) => (
          <Card key={item.id} className="p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                  {item.type === 'INTERVIEW' ? 'Phỏng vấn dở dang' : 'Đợt thử việc dở dang'}
                </span>
                <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                  {item.department}
                </span>
              </div>

              <h4 className="text-sm font-bold text-slate-900">{item.title}</h4>

              <div className="text-xs text-slate-500 space-y-0.5">
                <p>Người phụ trách cũ: <strong className="text-rose-700">{item.currentOwner}</strong></p>
                <p>Thời hạn xử lý: <strong className="text-slate-700">{item.due}</strong></p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <Button
                size="sm"
                onClick={() => handleReassign(item.id)}
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Chuyển giao cho đồng nghiệp
              </Button>
            </div>
          </Card>
        ))}

        {pendingHandovers.length === 0 && (
          <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-slate-300">
            <CheckCircle2 className="w-10 h-10 text-teal-600 mx-auto mb-2" />
            <h4 className="text-sm font-bold text-slate-700">Tất cả công việc đã được xử lý hoàn tất</h4>
            <p className="text-xs text-slate-400 mt-1">Hiện không còn mục công việc nào ở trạng thái Chờ chuyển giao.</p>
          </div>
        )}
      </div>
    </div>
  );
};
