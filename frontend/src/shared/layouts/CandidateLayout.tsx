import React from 'react';
import { Link, NavLink, Outlet } from 'react-router';
import { ArrowRight, Briefcase, ShieldCheck } from 'lucide-react';
import { AmbientBackdrop, GLASS_BAR } from '@/shared/components/ui/Glass';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `hidden rounded-control px-3 py-2 text-sm transition-colors sm:block ${
    isActive ? 'font-medium text-ink' : 'text-ink-muted hover:text-ink'
  }`;

export const CandidateLayout: React.FC = () => {
  return (
    <div className="relative isolate flex min-h-screen flex-col bg-canvas text-ink">
      <AmbientBackdrop />

      <header className="sticky top-3 z-40 px-3">
        <div className={`mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 rounded-2xl px-4 sm:px-6 ${GLASS_BAR}`}>
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]">
              <Briefcase className="h-4 w-4" />
            </span>
            <span className="text-lg font-semibold tracking-tight">HR_Chan</span>
            <span className="hidden text-sm text-ink-subtle sm:inline">Tuyển dụng</span>
          </Link>

          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={navLinkClass}>
              Cơ hội việc làm
            </NavLink>
            <NavLink to="/about" className={navLinkClass}>
              Văn hóa doanh nghiệp
            </NavLink>
            <Link
              to="/app"
              className="ml-2 inline-flex h-9 items-center gap-1.5 rounded-control bg-ink px-3.5 text-[13px] font-medium text-white transition-colors hover:bg-ink/85"
            >
              Cổng nội bộ <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-white/70 py-10 text-sm text-ink-muted">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 shrink-0 text-brand" />
            Dữ liệu cá nhân được xử lý theo Nghị định 13/2023/NĐ-CP.
          </p>
          <div className="flex items-center gap-6">
            <span>&copy; 2026 HR_Chan</span>
            <Link to="/app" className="font-medium text-brand hover:underline">
              Truy cập hệ thống quản trị
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
};
