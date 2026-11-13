# Enterprise Frontend Application Design

## Goal and Context

HR_Chan is an automated hiring and onboarding platform designed for enterprise human resource workflows, combining AI-driven candidate screening, candidate-job matching, automated interview coordination (Google Meet / Calendar), and probation management. 
The current repository contains a basic frontend scaffold using React 19, React Router 7, TanStack Query 5, and Vite with plain CSS.

The goal is to design and build a comprehensive, production-grade, enterprise-level frontend application implementing the full suite of user journeys specified across the 66 Use Cases and 62 Business Rules documented in `PRJ3_Report_Final.docx.pdf`.

## Scope

### Included
- Complete Enterprise Design System & Component Library (Button, Input, Select, Badge, Card, Modal, Drawer, DataTable, Tabs, Toast, Dropdown, Skeleton, EmptyState).
- Single Tailwind CSS entry stylesheet in `src/styles/index.css` replacing legacy styles (complying with `docs/engineering/conventions/frontend.md`).
- Enterprise Navigation Shells:
  - Public Portal layout (Navbar, Hero, Footer) for candidates.
  - Internal Workspace layout (Collapsible Sidebar, Breadcrumbs, Notifications, User profile, Global Role Switcher for seamless demonstration of all 5 internal roles).
- Candidate Public Portal:
  - Job Board with search, department filtering, and pagination.
  - Job Detail view with requirements, benefits, and instant application trigger.
  - AI-Powered CV Submission & Job Matching modal (file upload, simulated LLM structured extraction, % compatibility ranking, consent checkbox per Decree 13/2023/ND-CP).
  - 6-digit OTP Email verification modal with 60s cooldown, 5-attempt lockout, and application generation.
  - Tokenized Public Actions (via secure email links): Interview Confirmation / Reschedule Request, Probation Offer Decision, and 12-month Consent Renewal.
- Internal Role Portals:
  - **HR / Recruitment Portal:** Job Posting management (Draft/Open/Closed), Criteria Set Editor (sum=100%, auto-invite threshold, mandatory flags, interviewer assignment), 14-state Application Pipeline (Kanban & Data Grid), Review Dossier with AI Scoring explanation (scores, comments, CV evidence quote), Interview Management & Calendar timeline, Recruitment Funnel & AI Analytics reports with export capabilities.
  - **Interviewer Portal:** Assigned interview schedule, candidate dossier review, Structured Evaluation Sheet (1–5 scale criteria rating, overall comments, Pass/Fail/Absent outcome).
  - **Department Manager Portal:** Active probation batches, task assignment with attachments and deadlines, submission assessment (Pass/Fail + mandatory feedback), progress overview, and final Probation Conclusion.
  - **Probation Trainee Portal:** "My Tasks" board, submission form (HTTP link or file upload), submission revision, manager feedback and final result view.
  - **Admin Portal:** User & Admin account directory, RBAC role assignment, Work Handover management for locked/transferred users, System Settings (Working calendar, Email templates, Token expiry, AI thresholds), Immutable Audit Log viewer.
- Mock API & State Engine: realistic in-memory state engine simulating the 25 physical tables and 14 application states to enable end-to-end functionality without backend dependency.

### Excluded
- Backend Python API implementations (handled in separate backend spec/tasks).
- Direct external third-party OAuth2 handshake (simulated via mock service boundaries).

## Requirements and Expected Behavior

1. **Role-Based Workspaces & Dynamic Role Switcher**:
   - Internal users can easily switch roles (HR, Interviewer, Dept Manager, Probation Trainee, Admin) to audit role-specific boundaries as defined in BR27–BR30 and NFR26.
   - Admin is isolated from candidate CVs, AI scores, and interview results (BR29).
2. **AI Transparency & Explainability**:
   - The HR candidate review screen must clearly present the AI's breakdown per criterion and the verified evidence snippet from the CV (BR06, UC1.08, NFR09).
   - System calculation of weighted scores in code rather than unverified LLM math.
3. **Responsive & Professional UI**:
   - Modern clean enterprise theme with emerald/slate corporate palette, crisp typography, accessible contrasts, responsive from 360px mobile to 1920px+ ultrawide displays (NFR11, NFR12, NFR24, NFR37).
4. **Resilience & Feedback**:
   - Granular validation for forms (OTP cooldown, criterion weights summing strictly to 100%, probation duration 1–180 days, file types PDF/DOCX $\le$ 5MB).
   - Toast notifications for async actions and immediate feedback.

## Design and Architecture

### Directory Layout (under `frontend/src/`)
```
src/
├── configs/
│   └── env.ts
├── features/
│   ├── admin/
│   ├── applications/
│   ├── auth/
│   ├── candidates/
│   ├── home/
│   ├── interviews/
│   ├── jobs/
│   ├── probation/
│   └── reports/
├── routes/
│   ├── routes.tsx
│   └── guard.tsx
├── shared/
│   ├── components/
│   │   ├── forms/
│   │   ├── navigation/
│   │   └── ui/
│   ├── hooks/
│   ├── layouts/
│   │   ├── CandidateLayout.tsx
│   │   └── DashboardLayout.tsx
│   ├── services/
│   │   ├── client.ts
│   │   └── mockStore.ts
│   └── types/
│       ├── api.ts
│       ├── enterprise.ts
│       └── models.ts
└── styles/
    └── index.css
```

## Acceptance Criteria and Verification

1. **Build & Typecheck**: `pnpm run build` succeeds with zero TypeScript errors.
2. **Tailwind Styling**: All screens use Tailwind CSS utility classes; no ad-hoc CSS modules or inline CSS hacks.
3. **Public Experience**: Candidate can browse jobs, upload CV, receive simulated AI recommendations, complete OTP, and view confirmation.
4. **Internal Workspaces**:
   - HR can create jobs with criteria, inspect applications, review AI scorecards, and reschedule interviews.
   - Interviewer can submit 1–5 scoring and review CVs assigned to them.
   - Manager can assign probation tasks, grade submissions, and issue final conclusions.
   - Trainee can submit task deliverables and view grading.
   - Admin can manage accounts, transfer handover jobs, and view immutable audit logs.

