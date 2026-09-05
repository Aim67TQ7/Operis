# Foundation verification

Verified on 2026-09-05. Local foundation checks and hosted staging checks are separated below; this is not full production acceptance.

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

## Hosted staging verification

The user approved shared ZODA and the Netlify staging site. See [STAGING.md](STAGING.md) for identifiers and migration receipt.

| Check | Result | Scope |
| --- | --- | --- |
| Initial migration | Applied, version `20260905132610` | Five Operis tables and private helpers only |
| Live RLS/grants/policies | Passed | RLS on all five tables, eight policies, restricted grants |
| `supabase/tests/live-boundaries.sql` | Eight checks passed | Actual DB roles, isolation and audit; transaction rolled back |
| Test cleanup | Passed | All five Operis tables empty afterward |
| Hosted security advisors | No Operis findings | Does not clear unrelated pre-existing project findings |
| Netlify build/deploy | Ready | Deploy `6a9c195e0e442f20d55397e0`; no secret matches reported by deploy scan |
| HTTPS frontend and assets | HTTP 200 | Page title, JS and CSS retrieved successfully |
| `/workspace` | HTTP 200 | SPA fallback serves frontend |
| `/api/health/ready` | Expected HTTP 404 JSON | Explicit unconfigured-API boundary; not backend readiness |

`npm run build` and all 15 PGlite database tests were rerun successfully during this staging setup. The earlier 5 web and 17 API tests remain the latest local results for unchanged application source. These live database checks use local JWT claims under database roles; they do not verify Supabase-issued tokens through PostgREST or the FastAPI proxy.

## Not verified in this environment

- Full Supabase Auth/PostgREST HTTP integration, SMTP delivery and compatibility of shared ZODA email templates.
- Real browser layout, mobile sizing, keyboard navigation and live end-to-end sign-in.
- Docker image execution, deployed FastAPI health and authenticated Netlify proxy behavior.
- Production backup/restore, proxy limits and scaling policy.
- Legacy Lovable implementations and their operational source systems (Phase 2).

Supabase CLI setup encountered a cancelled network approval. Docker and psql were absent. The hosted migration was instead applied successfully through Supabase's migration service. No first tenant/admin was provisioned and no shared Auth configuration was changed.

## Pete deployment preparation

User-provided terminal output confirms Mac SSH access, Compose v5.3.1, and the existing Caddy container on hub-net. The added Compose YAML parses locally; required settings, image build context and inherited healthcheck were reviewed. Docker remains unavailable in the build workspace, so this is not a Compose runtime or backend deployment claim. DNS lookup failed locally for both the existing hub hostname and the proposed Operis hostname. See PETE.md for the executable deployment sequence and remaining checks.
