# Frontend Conventions

Use React, TypeScript, Vite, React Router, TanStack Query, Tailwind CSS, and pnpm.

## Directory Responsibilities

All `src/` paths below are relative to `frontend/`.

| Path | Responsibility |
| --- | --- |
| `src/App.tsx` | Compose application providers and router |
| `src/routes/` | Assemble routes; each implemented feature owns its `routes.tsx` |
| `src/features/` | Business features and their pages, components, hooks, services, and types |
| `src/shared/` | Shared components, UI, layouts, providers, hooks, services, types, utilities, and constants |
| `src/configs/` | Application configuration and environment variables |
| `src/styles/` | Single Tailwind entry stylesheet and shared theme tokens |
| `src/assets/` | Assets imported by source code |
| `public/` | Static assets served directly |
| `src/stores/` | Shared client state when needed; no library just to fill the directory |
| `src/helper/` | Helpers; avoid duplicating `shared/utils` |

Do not revert to root-level `src/app`, `src/pages`, `src/components`, `src/hooks`,
`src/lib`, or `src/types` directories.


## Styling

- Tailwind CSS is required for new or changed UI styling. Use utility classes
  directly in React components for layout, typography, colors, and responsive states.
- Do not create standalone component/feature CSS, SCSS, or CSS Module files.
  Do not move custom component selectors into a global stylesheet instead.
- Keep a single entry stylesheet in `src/styles/` for loading Tailwind and defining
  shared theme tokens or necessary global base styles. Component styling belongs
  in utility classes; reuse React components for repeated UI patterns.
- Tailwind is installed and configured through the Vite plugin; `src/styles/index.css`
  is the single entry stylesheet. Do not add component stylesheets.

## Routing and Data

- Keep alias `@/` pointing to `src/` consistently in TypeScript and Vite.
- Keep the shared HTTP client in `shared/services`; read the backend URL from
  environment configuration, not hardcoded feature URLs.
- Use TanStack Query for server data and distinguish it from shared client state.
- TypeScript response types describe contracts; they do not validate runtime JSON.
- `src/features/jobs/api.ts` calls the real HR job posting API (`/api/v1/jobs`,
  `/departments`, `/interviewers`); the HR job page (`/app/hr/jobs`) uses it.
  The public job board and detail use `features/jobs/publicApi.ts` (separate public DTOs,
  no HR fields), and the apply/OTP modals use `features/candidates/api.ts` (multipart
  `FormData` upload; the shared client must not JSON-encode it or set its `Content-Type`).
  Upload, OTP and submit mutations are never retried automatically; capability tokens and
  OTP state stay in memory only. The HR overview still uses `mockStore`. Do not add
  sample Job requests or mock data to the API modules.

Typecheck/build do not establish UI behavior. Follow the
[testing conventions](testing.md); Vitest and Playwright are configured for
behavioral and browser tests.

## Authentication and Session State

- Keep access tokens in memory. Never write credentials to local storage, session
  storage, IndexedDB, or the URL.
- Run every credential-changing call (login, refresh, logout, password change)
  inside the shared Web Locks lock from `features/auth/refreshCoordinator.ts`, and
  deduplicate per-tab refreshes.
- Treat route guards as navigation aids only; the backend enforces authorization.
  Never invent an Admin bypass or derive permissions from bundled mock data.
- Use `authorized(...)` from `features/auth/AuthProvider` for protected requests so
  expired access tokens refresh once instead of replaying mutations blindly.
- Build API calls through `shared/services/client.ts` so `ApiError`, `204` handling,
  and credentialed requests stay consistent.
- Development-only affordances (for example the quick-login buttons in
  `features/auth/devLogins.ts`) must be gated by `import.meta.env.DEV`, must call
  the real API instead of bypassing authentication, and must not appear in the
  production bundle.
