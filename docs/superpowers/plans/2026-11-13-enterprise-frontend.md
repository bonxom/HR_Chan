# Enterprise Frontend Implementation Plan

Link to spec: [Enterprise Frontend Application Design](../specs/2026-11-13-enterprise-frontend-design.md)

## Tasks

### Phase 1: Shared Models, Mock Store & Design System Components
- [x] Create core TypeScript models matching the 25 tables and 14 states (`src/shared/types/models.ts`).
- [x] Create persistent reactive Mock Store (`src/shared/services/mockStore.ts`) pre-seeded with rich enterprise sample data (jobs, criteria, applications, candidates, interviews, probation tasks, internal users).
- [x] Build reusable enterprise UI components (`src/shared/components/ui/`):
  - Button, Input, Select, Textarea, Badge, Modal, Card, Toast Notification container.

### Phase 2: Navigation & Shell Layouts
- [x] Create `CandidateLayout` (`src/shared/layouts/CandidateLayout.tsx`): modern public navigation bar, hero branding, footer, candidate status check.
- [x] Create `DashboardLayout` (`src/shared/layouts/DashboardLayout.tsx`): enterprise sidebar with active link states, breadcrumbs, search, notification popover, profile card, and global **Role Switcher** (HR, Interviewer, Dept Manager, Trainee, Admin).

### Phase 3: Candidate Public Portal
- [x] Job Board & Filtering (`src/features/jobs/JobBoard.tsx`): search, department filter, salary/location badge, job cards with pagination.
- [x] Job Detail view (`JobDetail.tsx`).
- [x] AI-Powered CV Submission & Matching Modal (`ApplyModal.tsx`): file upload dropzone, AI structured profile preview, % compatibility list, statutory consent checkbox.
- [x] OTP Verification Modal (`OtpModal.tsx`): 6-digit input, countdown timer, lockout handling.
- [x] Public Token Response Pages (`src/features/candidates/`):
  - Interview Confirmation / Reschedule page (`InterviewActionPage.tsx`).
  - Probation Offer Acceptance page (`OfferActionPage.tsx`).
  - 12-month Consent Renewal page (`ConsentActionPage.tsx`).

### Phase 4: HR & Interviewer Workspaces
- [x] Job Posting Management (`src/features/jobs/HrJobManagement.tsx`): Draft/Open/Closed status, create new job form, criteria builder.
- [x] Criteria Set Editor: weights sum=100%, auto-invite threshold slider, mandatory checkboxes, interviewer selector.
- [x] Application Pipeline (`src/features/applications/ApplicationPipeline.tsx`): 14-state Kanban & Table view, candidate search.
- [x] Candidate Review Dossier (`ApplicationReviewModal.tsx`): split-screen view of CV vs. AI score breakdown per criterion, evidence quote, Approve / Reject with internal notes.
- [x] Interview Management & Schedule (`src/features/interviews/InterviewCalendar.tsx`): timeline, Google Meet link generation, slot rescheduling, interviewer reassignment.
- [x] Interviewer Evaluation Form (`src/features/interviews/InterviewerEvaluationModal.tsx`): 1–5 scoring per criterion, notes, Pass/Fail/Absent outcome.
- [x] HR Analytics & Reports (`src/features/reports/ReportsPage.tsx`): Funnel chart, AI screening vs. human alignment, probation pass rates, CSV/Excel export.

### Phase 5: Probation & Trainee Workspaces
- [x] Dept Manager Probation Dashboard (`src/features/probation/ManagerProbationDashboard.tsx`): active trainees list, task assignment modal with deadline & attachments, task grading modal with pass/fail & feedback, conclusion dialog.
- [x] Trainee Dashboard (`src/features/probation/TraineeDashboard.tsx`): task list, deadline badges, deliverable submission modal (link/file), feedback inspection.

### Phase 6: Admin Workspace
- [x] User & Role Management (`src/features/admin/UserManagement.tsx`): active/locked accounts, role checkboxes (HR, Interviewer, Dept Manager, Trainee, Admin), create user, lock/unlock with audit reason.
- [x] Work Handover Dashboard (`WorkHandover.tsx`): reassign pending interviews and active probation tasks from locked users.
- [x] System Configuration (`SystemSettings.tsx`): office working hours, holiday calendar, email templates with variable interpolation, OTP/link validity, AI thresholds.
- [x] Immutable Audit Log Viewer (`AuditLogs.tsx`): chronological log of all administrative and status change events.

### Phase 7: Routes Assembly & Verification
- [x] Wire all routes in `src/routes/routes.tsx`.
- [x] Verify complete build with `pnpm run build` and interactive flow checks.
