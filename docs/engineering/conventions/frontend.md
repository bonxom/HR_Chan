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
- The current scaffold still uses plain CSS and has no Tailwind dependency.
  Integrate Tailwind and migrate affected styles before implementing the next UI
  styling change; do not extend the legacy stylesheet with new component rules.

## Routing and Data

- Keep alias `@/` pointing to `src/` consistently in TypeScript and Vite.
- Keep the shared HTTP client in `shared/services`; read the backend URL from
  environment configuration, not hardcoded feature URLs.
- Use TanStack Query for server data and distinguish it from shared client state.
- TypeScript response types describe contracts; they do not validate runtime JSON.
- `src/features/jobs/api.ts` is intentionally empty. Do not add sample Job requests or types.

Typecheck/build do not establish UI behavior. Follow the
[testing conventions](testing.md) and identify behavioral test tooling in the
feature spec/plan before adding it.
