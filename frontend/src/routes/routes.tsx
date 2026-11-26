import { createBrowserRouter, Navigate } from 'react-router';
import type { ReactNode } from 'react';
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
import { AuditLogs } from '@/features/admin/AuditLogs';

// Authentication
import { useAuth } from '@/features/auth/AuthProvider';
import { RequireAccess, RequireAuth, landingPathFor } from '@/features/auth/RequireAuth';
import { accountRoutes, authEntryRoutes } from '@/features/auth/routes';
import { responseRoutes } from '@/features/responses/routes';
import type { EmployeeRole } from '@/features/auth/types';

function AppLanding() {
  const { account } = useAuth();
  return account ? <Navigate to={landingPathFor(account)} replace /> : null;
}

function section(
  element: ReactNode,
  options: { roles?: EmployeeRole[]; adminOnly?: boolean },
): ReactNode {
  if (options.adminOnly) {
    return <RequireAccess accountType="ADMIN">{element}</RequireAccess>;
  }
  return <RequireAccess roles={options.roles}>{element}</RequireAccess>;
}

const browserRouter = createBrowserRouter([
  ...responseRoutes,
  // Public Candidate Portal (demonstration data)
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

  ...authEntryRoutes,

  // Internal Corporate Workspace (server-enforced authorization)
  {
    path: '/app',
    element: (
      <RequireAuth>
        <DashboardLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <AppLanding /> },
      ...accountRoutes,

      // HR Workspace
      { path: 'hr', element: section(<HrDashboardOverview />, { roles: ['HR'] }) },
      { path: 'hr/jobs', element: section(<HrJobManagement />, { roles: ['HR'] }) },
      { path: 'hr/applications', element: section(<ApplicationPipeline />, { roles: ['HR'] }) },
      { path: 'hr/interviews', element: section(<InterviewCalendar />, { roles: ['HR'] }) },
      { path: 'hr/reports', element: section(<ReportsPage />, { roles: ['HR'] }) },

      // Interviewer Workspace
      { path: 'interviewer', element: section(<InterviewerDashboard />, { roles: ['INTERVIEWER'] }) },
      {
        path: 'interviewer/evaluations',
        element: section(<InterviewerDashboard />, { roles: ['INTERVIEWER'] }),
      },

      // Manager Workspace
      {
        path: 'manager',
        element: section(<ManagerProbationDashboard />, { roles: ['DEPT_MANAGER'] }),
      },
      {
        path: 'manager/tasks',
        element: section(<ManagerProbationDashboard />, { roles: ['DEPT_MANAGER'] }),
      },

      // Trainee Workspace
      { path: 'trainee', element: section(<TraineeDashboard />, { roles: ['PROBATION'] }) },
      { path: 'trainee/results', element: section(<TraineeDashboard />, { roles: ['PROBATION'] }) },

      // Admin Workspace
      { path: 'admin/users', element: section(<UserManagement />, { adminOnly: true }) },
      { path: 'admin/logs', element: section(<AuditLogs />, { adminOnly: true }) },
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
