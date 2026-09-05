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

## Pete live backend receipt

The user successfully built the Docker image from commit `4db7de238ec797f09b6e29ac90912b6c0889e16a` and started `operis-staging-api-1` with Healthy status. User-provided HTTPS responses establish liveness HTTP 200 and, after correcting a mismatched publishable key, readiness HTTP 200 at 2026-09-05 18:16:30 UTC through Caddy, with no-store headers. See PETE.md for the image and request identifiers. The Netlify proxy target is now configured in source; deployment and verification of this new routing are recorded separately.

Netlify deploy `6a9c5d465bf2eddc00dfa917` completed its hosted build and published the new API proxy at 2026-09-05 18:20:07 UTC. The local build command was interrupted by a cancelled network approval; the successful hosted build is the deployment validation for this change.

## Frontend proxy live checks

After deploy `6a9c5d465bf2eddc00dfa917`, direct HTTPS requests to `operis-staging.netlify.app` verified:

| Request | Result | Evidence |
| --- | --- | --- |
| GET /api/health/live | 200 | status ok, version 0.1.0 |
| GET /api/health/ready | 200 | status ready |
| GET /api/me without a cookie | 401 | Sign in to continue |
| POST /api/auth/verify, allowed Origin, invalid input | 422 | Validated by the API; provider not called |
| POST /api/auth/verify, foreign Origin | 403 | Request origin is not allowed |

All five returned JSON with Cache-Control: no-store. These checks establish routing, readiness, unauthenticated access denial and preservation of Origin through Netlify/Caddy. They do not establish successful code delivery, Set-Cookie forwarding, a real session or tenant administration. No sign-in emails were sent by these checks.


## PKCE magic-link compatibility change

Implemented server-side email-link request and callback, preserving shared Auth defaults. Local API suite: 20 tests passed, including browser-verifier challenge binding, missing verifier rejection, provider failure cleanup, replay rejection after cookie removal, fixed redirect destination and session token non-disclosure. Provider calls in these tests are mocked; this is not live email acceptance. Backend deployment on Pete and the exact additional Supabase redirect URL remain required before real callback testing.
