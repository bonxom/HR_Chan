import React from 'react';
import { Link, Outlet } from 'react-router';
import { Briefcase, ArrowRight, ShieldCheck, Sparkles } from 'lucide-react';

export const CandidateLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Banner / Announcement */}
      <div className="bg-emerald-900 text-emerald-100 text-xs py-2 px-4 text-center font-medium flex items-center justify-center gap-2">
        <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
        <span>Hệ thống tuyển dụng thông minh tích hợp AI &mdash; Sàng lọc tự động &amp; phản hồi minh bạch</span>
      </div>

      {/* Main Navbar */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 text-emerald-800 font-extrabold text-xl tracking-tight">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center text-white shadow-xs">
              <Briefcase className="w-5 h-5" />
            </div>
            <span>HR<span className="text-slate-900">_Chan</span></span>
            <span className="text-[10px] font-bold uppercase tracking-widest bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full ml-1">
              Careers
            </span>
          </Link>

          <nav className="flex items-center gap-6 text-sm font-medium">
            <Link to="/" className="text-slate-700 hover:text-emerald-700 transition-colors">
              Cơ hội việc làm
            </Link>
            <Link to="/about" className="text-slate-600 hover:text-emerald-700 transition-colors">
              Văn hóa doanh nghiệp
            </Link>
            <div className="h-4 w-px bg-slate-200" />
            <Link
              to="/app"
              className="inline-flex items-center gap-1.5 text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white px-3.5 py-2 rounded-lg shadow-xs transition-all"
            >
              <span>Cổng nội bộ (Workspace)</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </nav>
        </div>
      </header>

      {/* Content Area */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 text-xs py-10 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Tuân thủ quy định bảo vệ dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP</span>
          </div>
          <div className="flex items-center gap-6">
            <span>&copy; 2026 HR_Chan Enterprise Platform. All rights reserved.</span>
            <Link to="/app" className="text-emerald-400 hover:underline">
              Truy cập Hệ thống Quản trị
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

