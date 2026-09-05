# Foundation verification

Verified locally on 2026-09-05. No production deployment claim.

| Check | Result | What it establishes |
| --- | --- | --- |
| `npm run build` | Passed | Strict TypeScript compilation and Vite production bundle |
| `npm run test:web` | 5 passed | Email/code interaction, cookie request mode, no browser token persistence, company creation, tenant switching, errors and no-membership state |
| `npm run test:db` | 15 passed | Executed PostgreSQL RLS, tenant-scoped writes/reads, composite foreign key, no self-elevation, atomic audit and audit immutability |
| `pytest -q` in apps/api | 17 passed | API authorization, CSRF Origin check, secure cookie flags, signup disabled, validation redaction, provider errors, rate limits, logout and health behavior |
| Ruff lint and formatting | Passed | Python static checks and formatting |
| Frontend formatting | Passed | Reviewable formatted TypeScript/CSS/test source |
| `git diff --check` | Passed | No whitespace errors |

API tests use `httpx.MockTransport` and a real FastAPI application lifecycle. UI tests use React Testing Library and JSDOM against isolated responses. PGlite runs the authored SQL in a PostgreSQL engine with test-only auth functions and users. Synthetic records are confined to test files.

Two non-failing upstream test-client deprecation warnings occur for Starlette's httpx and AnyIO portal integrations. They do not affect passing assertions. The source and lockfiles preserve the tested versions; migration to the successor interfaces should be reviewed independently.

## Not verified in this environment

- Full Supabase Auth/PostgREST integration, SMTP delivery and hosted RLS advisors.
- Real browser layout, mobile sizing, keyboard navigation and live end-to-end sign-in.
- Docker image execution, Netlify routing and deployed health.
- Production backup/restore, proxy limits and scaling policy.
- Legacy Lovable implementations and their operational source systems (Phase 2).

Supabase CLI setup encountered a cancelled network approval. Docker and psql were absent. No live database was modified. The reviewed `supabase/schema.sql` still needs a CLI-generated migration and staging acceptance before production use.
