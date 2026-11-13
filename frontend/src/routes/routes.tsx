import { createBrowserRouter, Navigate } from 'react-router';
import { CandidateLayout } from '@/shared/layouts/CandidateLayout';
import { DashboardLayout } from '@/shared/layouts/DashboardLayout';

// Candidate Portal Features
import { JobBoard } from '@/features/jobs/JobBoard';
import { JobDetail } from '@/features/jobs/JobDetail';
import { InterviewActionPage } from '@/features/candidates/InterviewActionPage';
import { OfferActionPage } from '@/features/candidates/OfferActionPage';
import { ConsentActionPage } from '@/features/candidates/ConsentActionPage';

// HR & Interviewer Features
import { HrDashboardOverview } from '@/features/hr/HrDashboardOverview';
import { HrJobManagement } from '@/features/jobs/HrJobManagement';
import { ApplicationPipeline } from '@/features/applications/ApplicationPipeline';
import { InterviewCalendar } from '@/features/interviews/InterviewCalendar';
import { InterviewerDashboard } from '@/features/interviews/InterviewerDashboard';
import { ReportsPage } from '@/features/reports/ReportsPage';

// Manager & Trainee Features
import { ManagerProbationDashboard } from '@/features/probation/ManagerProbationDashboard';
import { TraineeDashboard } from '@/features/probation/TraineeDashboard';

// Admin Features
import { UserManagement } from '@/features/admin/UserManagement';
import { WorkHandover } from '@/features/admin/WorkHandover';
import { SystemSettings } from '@/features/admin/SystemSettings';
import { AuditLogs } from '@/features/admin/AuditLogs';

const browserRouter = createBrowserRouter([
  // Public Candidate Portal
  {
    element: <CandidateLayout />,
    children: [
      { path: '/', element: <JobBoard /> },
      { path: '/jobs/:id', element: <JobDetail /> },
      { path: '/action/interview/:id', element: <InterviewActionPage /> },
      { path: '/action/offer/:id', element: <OfferActionPage /> },
      { path: '/action/consent/:id', element: <ConsentActionPage /> },
    ],
  },

  // Internal Corporate Workspace (RBAC)
  {
    path: '/app',
    element: <DashboardLayout />,
    children: [
      { index: true, element: <Navigate to="/app/hr" replace /> },

      // HR Workspace
      { path: 'hr', element: <HrDashboardOverview /> },
      { path: 'hr/jobs', element: <HrJobManagement /> },
      { path: 'hr/applications', element: <ApplicationPipeline /> },
      { path: 'hr/interviews', element: <InterviewCalendar /> },
      { path: 'hr/reports', element: <ReportsPage /> },

      // Interviewer Workspace
      { path: 'interviewer', element: <InterviewerDashboard /> },
      { path: 'interviewer/evaluations', element: <InterviewerDashboard /> },

      // Manager Workspace
      { path: 'manager', element: <ManagerProbationDashboard /> },
      { path: 'manager/tasks', element: <ManagerProbationDashboard /> },

      // Trainee Workspace
      { path: 'trainee', element: <TraineeDashboard /> },
      { path: 'trainee/results', element: <TraineeDashboard /> },

      // Admin Workspace
      { path: 'admin/users', element: <UserManagement /> },
      { path: 'admin/handover', element: <WorkHandover /> },
      { path: 'admin/settings', element: <SystemSettings /> },
      { path: 'admin/logs', element: <AuditLogs /> },
    ],
  },

  // Fallback 404
  {
    path: '*',
    element: (
      <div className="min-h-screen flex flex-col items-center justify-center p-6 text-center bg-slate-50">
        <h1 className="text-4xl font-extrabold text-slate-800">404</h1>
        <p className="text-sm text-slate-500 mt-2">Trang không tồn tại hoặc đã được di chuyển.</p>
        <a href="/" className="mt-4 text-xs font-bold text-emerald-600 hover:underline">
          &larr; Quay lại Trang chủ
        </a>
      </div>
    ),
  },
]);

export default browserRouter;
