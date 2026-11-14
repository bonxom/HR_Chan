import React, { useState, useEffect } from 'react';
import { Search, Download } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { AuditLog } from '../../shared/types/models';
import { Button } from '../../shared/components/ui/Button';
import { showToast } from '../../shared/components/ui/Toast';

export const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>(mockStore.getAuditLogs());
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setLogs(mockStore.getAuditLogs());
    });
    return unsubscribe;
  }, []);

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.actorName.toLowerCase().includes(search.toLowerCase()) ||
      log.details.toLowerCase().includes(search.toLowerCase()) ||
      log.target.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === 'ALL' || log.actionType === typeFilter;
    return matchesSearch && matchesType;
  });

  const handleExport = () => {
    showToast({
      type: 'success',
      title: 'Đã xuất nhật ký kiểm toán (UC5.11)',
      message: 'File Excel chứa các bản ghi kiểm toán bất biến đã được tạo thành công.',
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Nhật Ký Kiểm Toán Bất Biến (Audit Logs)</h2>
          <p className="text-xs text-slate-500 mt-1">
            Ghi vết toàn bộ hành vi quản trị, phân quyền, xem hồ sơ và các quyết định xét duyệt (UC5.10 &mdash; UC5.11, BR38, NFR30).
          </p>
        </div>
        <Button size="sm" onClick={handleExport} leftIcon={<Download className="w-3.5 h-3.5" />}>
          Xuất Nhật ký (.xlsx)
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-2xl shadow-xs border border-slate-200 p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Tìm theo người thực hiện, thao tác, đối tượng..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto">
          {['ALL', 'DECISION', 'ROLE', 'ACCOUNT', 'CONFIG', 'VIEW_APPLICATION'].map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer whitespace-nowrap ${
                typeFilter === t
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {t === 'ALL'
                ? 'Tất cả'
                : t === 'DECISION'
                ? 'Quyết định'
                : t === 'ROLE'
                ? 'Phân quyền'
                : t === 'ACCOUNT'
                ? 'Tài khoản'
                : t === 'CONFIG'
                ? 'Cấu hình'
                : 'Xem hồ sơ'}
            </button>
          ))}
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3.5 px-6">Thời gian</th>
                <th className="py-3.5 px-4">Người thực hiện</th>
                <th className="py-3.5 px-4">Loại thao tác</th>
                <th className="py-3.5 px-6">Chi tiết hành động</th>
                <th className="py-3.5 px-6">Lý do ghi nhận</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredLogs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-4 px-6 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                    {new Date(log.timestamp).toLocaleString('vi-VN')}
                  </td>
                  <td className="py-4 px-4 whitespace-nowrap">
                    <div className="font-bold text-slate-900">{log.actorName}</div>
                    <div className="text-[10px] text-slate-400">{log.actorRole}</div>
                  </td>
                  <td className="py-4 px-4 whitespace-nowrap">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                      {log.actionType}
                    </span>
                  </td>
                  <td className="py-4 px-6 font-medium text-slate-800">
                    <div>{log.details}</div>
                  </td>
                  <td className="py-4 px-6 text-slate-500 italic">
                    {log.reason || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
