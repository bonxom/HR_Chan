# General Conventions

Follow the [workflow](../workflow.md) and read existing code before changing it.
These rules apply across the repository.

## Scope and Naming

- Preserve existing user changes. Do not reset, overwrite, or delete unrelated work.
- Keep identifiers consistent with the surrounding project code and terminology.
- Do not infer recruitment, onboarding, or database requirements. Clarify missing
  information that affects API contracts or data structures.
- Empty placeholders are intentional. Add implementations only for concrete requirements.
- Do not add sample CRUD, data, models, fields, relationships, or generic frameworks
  just to demonstrate a structure.

## Dependencies and Configuration

- Keep `backend/uv.lock` and `frontend/pnpm-lock.yaml` synchronized with dependency
  changes and under version control. Use `uv sync --frozen` and `ppnpm install --frozen-lockfile` for locked installs.
- Add dependencies only for an identified need; do not add libraries to populate placeholders.
- Use safe placeholders in `.env.example` files.
- Never put secrets, tokens, personal data, or real `.env` contents in Git, logs,
  or documentation. Frontend `VITE_*` variables are public, not secret storage.

## Documentation and Handoff

- Write project documentation in English. Preserve tool-managed blocks when editing.
- Update the relevant guide, architectural description, and README links when structure
  or execution instructions change. Explain each directory's responsibility.
- Keep each rule in one authoritative convention document; link to it elsewhere.
- Do not commit, push, or deploy unless requested.
- Do not add `Co-authored-by` trailers or other co-author attribution to commit
  messages, including attribution to coding agents.
