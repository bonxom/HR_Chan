import React, { useState, useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router';
import {
  Briefcase,
  Users,
  Calendar,
  BarChart3,
  CheckSquare,
  Shield,
  Sliders,
  FileText,
  UserCheck,
  Building,
  UserCog,
  RefreshCw,
  LogOut,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import { mockStore } from '../services/mockStore';
import { StatusBadge } from '../components/ui/Badge';
import { User } from '../types/models';

export const DashboardLayout: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User>(mockStore.getCurrentUser());
  const [allUsers, setAllUsers] = useState<User[]>(mockStore.getUsers());
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const unsubscribe = mockStore.subscribe(() => {
      setCurrentUser(mockStore.getCurrentUser());
      setAllUsers(mockStore.getUsers());
    });
    return unsubscribe;
  }, []);

  const hasRole = (role: string) => currentUser.roles.includes(role as any);

  // Define navigation sections based on active user roles
  const navItems = [
    // HR Role Items
    ...(hasRole('HR')
      ? [
          { label: 'Tổng quan Tuyển dụng', path: '/app/hr', icon: BarChart3 },
          { label: 'Tin tuyển dụng & Tiêu chí', path: '/app/hr/jobs', icon: Briefcase },
          { label: 'Pipeline Hồ sơ ứng tuyển', path: '/app/hr/applications', icon: Users },
          { label: 'Lịch phỏng vấn (Calendar)', path: '/app/hr/interviews', icon: Calendar },
          { label: 'Báo cáo & Phễu tuyển dụng', path: '/app/hr/reports', icon: FileText },
        ]
      : []),

    // Interviewer Role Items
    ...(hasRole('INTERVIEWER')
      ? [
          { label: 'Lịch phỏng vấn của tôi', path: '/app/interviewer', icon: Calendar },
          { label: 'Chấm điểm phỏng vấn', path: '/app/interviewer/evaluations', icon: UserCheck },
        ]
      : []),

    // Dept Manager Role Items
    ...(hasRole('DEPT_MANAGER')
      ? [
          { label: 'Quản lý Đợt thử việc', path: '/app/manager', icon: Building },
          { label: 'Giao task & Đánh giá bài', path: '/app/manager/tasks', icon: CheckSquare },
        ]
      : []),

    // Probation Trainee Role Items
    ...(hasRole('PROBATION')
      ? [
          { label: 'Nhiệm vụ thử việc của tôi', path: '/app/trainee', icon: CheckSquare },
          { label: 'Kết quả đánh giá', path: '/app/trainee/results', icon: FileText },
        ]
      : []),

    // Admin Role Items
    ...(hasRole('ADMIN')
      ? [
          { label: 'Quản lý Người dùng & Quyền', path: '/app/admin/users', icon: UserCog },
          { label: 'Bàn giao công việc dở dang', path: '/app/admin/handover', icon: RefreshCw },
          { label: 'Cấu hình tham số hệ thống', path: '/app/admin/settings', icon: Sliders },
          { label: 'Nhật ký kiểm toán (Audit Logs)', path: '/app/admin/logs', icon: Shield },
        ]
      : []),
  ];

  return (
    <div className="min-h-screen flex bg-slate-100 text-slate-900">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 border-r border-slate-800">
        {/* Brand */}
        <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800/80">
          <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-white font-bold">
            <Briefcase className="w-4 h-4" />
          </div>
          <div>
            <div className="font-extrabold text-white tracking-tight flex items-center gap-1.5 text-base">
              HR_Chan <span className="text-[10px] bg-emerald-500/20 text-emerald-400 font-semibold px-1.5 py-0.5 rounded">Core</span>
            </div>
            <div className="text-[10px] text-slate-400">Enterprise AI Recruitment</div>
          </div>
        </div>

        {/* User Info & Switcher Header */}
        <div className="p-4 border-b border-slate-800/80 bg-slate-950/40">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2 flex items-center justify-between">
            <span>Tài khoản hiện hành</span>
            <Sparkles className="w-3 h-3 text-emerald-400" />
          </div>

          <div className="relative">
            <button
              onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
              className="w-full text-left bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 rounded-xl p-2.5 flex items-center justify-between transition-colors cursor-pointer"
            >
              <div className="min-w-0 pr-2">
                <div className="font-semibold text-white text-xs truncate">{currentUser.fullName}</div>
                <div className="text-[11px] text-emerald-400 font-medium truncate mt-0.5">
                  {currentUser.roles.join(', ')}
                </div>
              </div>
              <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
            </button>

            {/* Role Switcher Menu */}
            {isRoleDropdownOpen && (
              <div className="absolute left-0 top-full mt-2 w-full bg-slate-800 border border-slate-700 rounded-xl shadow-2xl py-1.5 z-50">
                <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-700/60">
                  Chuyển góc nhìn diễn họa:
                </div>
                {allUsers.map((u) => (
                  <button
                    key={u.id}
                    onClick={() => {
                      mockStore.setCurrentUser(u.id);
                      setIsRoleDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs flex flex-col hover:bg-slate-700/70 transition-colors cursor-pointer ${
                      u.id === currentUser.id ? 'bg-emerald-950/40 text-emerald-300 font-semibold' : 'text-slate-300'
                    }`}
                  >
                    <span className="font-medium text-white">{u.fullName}</span>
                    <span className="text-[10px] text-slate-400">{u.roles.join(', ')} • {u.department}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Chức năng phân quyền
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path || (item.path !== '/app' && location.pathname.startsWith(item.path));
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-emerald-600 text-white shadow-xs font-semibold'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Footer / Quick Candidate Portal Link */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <Link
            to="/"
            className="flex items-center justify-between text-xs font-medium text-slate-400 hover:text-emerald-400 py-1.5 transition-colors"
          >
            <span>Về Cổng ứng viên</span>
            <LogOut className="w-3.5 h-3.5" />
          </Link>
        </div>
      </aside>

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200/90 px-8 flex items-center justify-between shrink-0 shadow-xs">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-bold text-slate-900">
              {currentUser.department} &mdash; <span className="text-emerald-700 font-semibold">{currentUser.fullName}</span>
            </h1>
            <StatusBadge status={currentUser.roles[0]} />
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="text-slate-500 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg">
              Phiên làm việc: <span className="font-semibold text-slate-700">Enterprise Secure SSO</span>
            </div>
          </div>
        </header>

        {/* Page Body */}
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

