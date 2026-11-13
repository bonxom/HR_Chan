import React, { useState, useEffect } from 'react';
import { UserPlus, Lock, Unlock, Edit } from 'lucide-react';
import { mockStore } from '../../shared/services/mockStore';
import { User, UserRole } from '../../shared/types/models';
import { Button } from '../../shared/components/ui/Button';
import { StatusBadge } from '../../shared/components/ui/Badge';
import { Modal } from '../../shared/components/ui/Modal';
import { Input } from '../../shared/components/ui/Input';
import { showToast } from '../../shared/components/ui/Toast';

export const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<User[]>(mockStore.getUsers());
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [isLockModalOpen, setIsLockModalOpen] = useState(false);

  // Form states
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [department, setDepartment] = useState('Engineering');
  const [accountType, setAccountType] = useState<'EMPLOYEE' | 'ADMIN'>('EMPLOYEE');
  const [selectedRoles, setSelectedRoles] = useState<UserRole[]>(['HR']);

  const [lockReason, setLockReason] = useState('');
  const [isUrgentLock, setIsUrgentLock] = useState(false);

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setUsers(mockStore.getUsers());
    });
    return unsubscribe;
  }, []);

  const handleCreateUser = () => {
    if (!fullName || !email) {
      showToast({ type: 'error', message: 'Vui lòng nhập họ tên và email công ty.' });
      return;
    }

    if (!email.endsWith('@hrchan.vn')) {
      showToast({ type: 'error', message: 'Email phải thuộc tên miền công ty (@hrchan.vn) theo BR39.' });
      return;
    }

    mockStore.addUser({
      fullName,
      email,
      department,
      accountType,
      roles: accountType === 'ADMIN' ? ['ADMIN'] : selectedRoles,
      status: 'ACTIVE',
    });

    showToast({
      type: 'success',
      title: 'Tạo tài khoản thành công (UC5.02 / UC5.03)',
      message: `Đã khởi tạo tài khoản cho ${fullName}. Email thiết lập mật khẩu lần đầu đã được gửi đi.`,
    });

    setIsCreateOpen(false);
    setFullName('');
    setEmail('');
  };

  const handleSaveRoles = () => {
    if (!selectedUser) return;
    if (selectedRoles.length === 0) {
      showToast({ type: 'error', message: 'Tài khoản nhân viên phải có ít nhất một vai trò nghiệp vụ (BR28).' });
      return;
    }

    mockStore.updateUserRoles(selectedUser.id, selectedRoles, 'Admin điều chỉnh phân quyền hệ thống');
    showToast({
      type: 'success',
      title: 'Cập nhật phân quyền thành công (UC5.08)',
      message: `Quyền hạn của ${selectedUser.fullName} đã được cập nhật thành: ${selectedRoles.join(', ')}.`,
    });
    setIsRoleModalOpen(false);
  };

  const handleLockAccount = () => {
    if (!selectedUser) return;
    if (!lockReason) {
      showToast({ type: 'error', message: 'Bắt buộc phải nhập lý do khi khóa tài khoản (BR38).' });
      return;
    }

    mockStore.updateUserStatus(selectedUser.id, 'LOCKED', `${isUrgentLock ? '[Khẩn cấp] ' : ''}${lockReason}`);
    showToast({
      type: 'info',
      title: isUrgentLock ? 'Khóa khẩn cấp tài khoản (BR34)' : 'Đã khóa tài khoản (UC5.05)',
      message: `Tài khoản ${selectedUser.fullName} đã bị khóa và chấm dứt mọi phiên đăng nhập. Công việc dở dang đã được chuyển sang hàng đợi bàn giao.`,
    });
    setIsLockModalOpen(false);
    setLockReason('');
  };

  const handleUnlockAccount = (u: User) => {
    mockStore.updateUserStatus(u.id, 'ACTIVE', 'Admin mở khóa tài khoản');
    showToast({
      type: 'success',
      title: 'Đã mở khóa tài khoản (UC5.05)',
      message: `Mật khẩu cũ của ${u.fullName} đã bị vô hiệu. Người dùng sẽ nhận email đặt lại mật khẩu mới qua Quên mật khẩu (BR36).`,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Quản lý Tài khoản &amp; Phân quyền (RBAC)</h2>
          <p className="text-xs text-slate-500 mt-1">
            Quản trị danh mục người dùng nội bộ, phân quyền vai trò nghiệp vụ và khóa tài khoản an toàn (UC5.01 &mdash; UC5.08).
          </p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)} leftIcon={<UserPlus className="w-4 h-4" />}>
          Thêm tài khoản mới
        </Button>
      </div>

      {/* Users Table */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-3.5 px-6">Họ và tên &amp; Email</th>
                <th className="py-3.5 px-4">Loại tài khoản</th>
                <th className="py-3.5 px-4">Phòng ban</th>
                <th className="py-3.5 px-4">Vai trò nghiệp vụ (Roles)</th>
                <th className="py-3.5 px-4">Trạng thái</th>
                <th className="py-3.5 px-6 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-4 px-6">
                    <div className="font-bold text-slate-900 text-sm">{u.fullName}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{u.email}</div>
                  </td>
                  <td className="py-4 px-4 font-semibold text-slate-700">
                    {u.accountType === 'ADMIN' ? (
                      <span className="text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">Admin</span>
                    ) : (
                      'Nhân viên'
                    )}
                  </td>
                  <td className="py-4 px-4">{u.department}</td>
                  <td className="py-4 px-4">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.map((r) => (
                        <StatusBadge key={r} status={r} />
                      ))}
                    </div>
                  </td>
                  <td className="py-4 px-4">
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded border ${
                        u.status === 'ACTIVE'
                          ? 'bg-teal-50 text-teal-700 border-teal-200'
                          : 'bg-rose-50 text-rose-700 border-rose-200'
                      }`}
                    >
                      {u.status === 'ACTIVE' ? 'Đang hoạt động' : 'Đã bị khóa'}
                    </span>
                  </td>
                  <td className="py-4 px-6 text-right space-x-2">
                    {u.accountType !== 'ADMIN' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedUser(u);
                          setSelectedRoles([...u.roles]);
                          setIsRoleModalOpen(true);
                        }}
                        leftIcon={<Edit className="w-3.5 h-3.5" />}
                      >
                        Phân quyền
                      </Button>
                    )}

                    {u.status === 'ACTIVE' ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelectedUser(u);
                          setIsLockModalOpen(true);
                        }}
                        className="text-rose-600 hover:bg-rose-50"
                        leftIcon={<Lock className="w-3.5 h-3.5" />}
                      >
                        Khóa
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleUnlockAccount(u)}
                        className="text-teal-600 hover:bg-teal-50"
                        leftIcon={<Unlock className="w-3.5 h-3.5" />}
                      >
                        Mở khóa
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal (UC5.02 & UC5.03) */}
      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Thêm tài khoản người dùng mới">
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">Loại tài khoản *</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setAccountType('EMPLOYEE')}
                className={`p-3 rounded-xl border text-xs font-bold cursor-pointer ${
                  accountType === 'EMPLOYEE' ? 'border-emerald-500 bg-emerald-50 text-emerald-800' : 'border-slate-200'
                }`}
              >
                Tài khoản Nhân viên (UC5.02)
              </button>
              <button
                type="button"
                onClick={() => setAccountType('ADMIN')}
                className={`p-3 rounded-xl border text-xs font-bold cursor-pointer ${
                  accountType === 'ADMIN' ? 'border-rose-500 bg-rose-50 text-rose-800' : 'border-slate-200'
                }`}
              >
                Tài khoản Quản trị Admin (UC5.03)
              </button>
            </div>
          </div>

          <Input label="Họ và tên *" placeholder="Nguyễn Văn A" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <Input label="Email công ty (@hrchan.vn - BR39) *" placeholder="a.nguyen@hrchan.vn" value={email} onChange={(e) => setEmail(e.target.value)} />

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">Phòng ban *</label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full bg-white border border-slate-300 rounded-lg p-2 text-xs"
            >
              <option value="Engineering">Engineering</option>
              <option value="People & Culture">People & Culture</option>
              <option value="Product Design">Product Design</option>
              <option value="IT Operations">IT Operations</option>
            </select>
          </div>

          {accountType === 'EMPLOYEE' && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1.5">
                Gán vai trò nghiệp vụ ban đầu (BR28):
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {(['HR', 'INTERVIEWER', 'DEPT_MANAGER'] as UserRole[]).map((r) => (
                  <label key={r} className="flex items-center gap-2 p-2 border rounded-lg bg-slate-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedRoles.includes(r)}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedRoles([...selectedRoles, r]);
                        else setSelectedRoles(selectedRoles.filter((item) => item !== r));
                      }}
                      className="rounded text-emerald-600"
                    />
                    <span>{r}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleCreateUser}>Khởi tạo tài khoản</Button>
          </div>
        </div>
      </Modal>

      {/* Role Assignment Modal (UC5.08) */}
      <Modal
        isOpen={isRoleModalOpen}
        onClose={() => setIsRoleModalOpen(false)}
        title={`Điều chỉnh phân quyền: ${selectedUser?.fullName || ''}`}
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Một tài khoản nhân viên có thể giữ nhiều vai trò (HR, INTERVIEWER, DEPT_MANAGER), trừ vai trò Nhân viên thử việc là độc lập (BR28).
          </p>

          <div className="space-y-2">
            {(['HR', 'INTERVIEWER', 'DEPT_MANAGER', 'PROBATION'] as UserRole[]).map((role) => (
              <label key={role} className="flex items-center gap-3 p-3 border rounded-xl bg-slate-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedRoles.includes(role)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      if (role === 'PROBATION') setSelectedRoles(['PROBATION']);
                      else setSelectedRoles([...selectedRoles.filter((r) => r !== 'PROBATION'), role]);
                    } else {
                      setSelectedRoles(selectedRoles.filter((r) => r !== role));
                    }
                  }}
                  className="rounded text-emerald-600"
                />
                <div>
                  <span className="font-bold text-xs text-slate-900">{role}</span>
                  <span className="text-[11px] text-slate-400 block">
                    {role === 'HR' && 'Quản lý tin tuyển dụng, tiêu chí, xét duyệt và báo cáo'}
                    {role === 'INTERVIEWER' && 'Tham gia đánh giá phỏng vấn theo phân công'}
                    {role === 'DEPT_MANAGER' && 'Giao task, chấm bài và kết luận thử việc'}
                    {role === 'PROBATION' && 'Nhân viên đang trong thời gian thử việc'}
                  </span>
                </div>
              </label>
            ))}
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsRoleModalOpen(false)}>
              Hủy
            </Button>
            <Button onClick={handleSaveRoles}>Lưu phân quyền mới</Button>
          </div>
        </div>
      </Modal>

      {/* Lock Account Modal (UC5.05 & BR34) */}
      <Modal
        isOpen={isLockModalOpen}
        onClose={() => setIsLockModalOpen(false)}
        title={`Khóa tài khoản: ${selectedUser?.fullName || ''}`}
      >
        <div className="space-y-4">
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 space-y-1">
            <p className="font-bold">Cảnh báo bảo mật (BR36):</p>
            <p>Khóa tài khoản sẽ chấm dứt ngay lập tức mọi phiên đăng nhập đang hoạt động trong vòng dưới 1 phút (NFR28).</p>
          </div>

          <label className="flex items-center gap-2 text-xs font-bold text-slate-800 cursor-pointer">
            <input
              type="checkbox"
              checked={isUrgentLock}
              onChange={(e) => setIsUrgentLock(e.target.checked)}
              className="rounded text-rose-600"
            />
            <span>Khóa khẩn cấp vì lý do bảo mật (BR34 - Chuyển ngay công việc dở dang sang Chờ bàn giao)</span>
          </label>

          <Input
            label="Lý do khóa tài khoản (Bắt buộc theo BR38) *"
            placeholder="Ví dụ: Tạm dừng công tác, điều tra vi phạm chính sách..."
            value={lockReason}
            onChange={(e) => setLockReason(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={() => setIsLockModalOpen(false)}>
              Hủy
            </Button>
            <Button variant="danger" onClick={handleLockAccount}>
              Xác nhận Khóa tài khoản
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
