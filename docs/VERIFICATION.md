# Foundation verification

Latest acceptance work: 2026-09-07. The current matrix below supersedes older pending statements; dated receipts later in this file are historical evidence. This is not full production acceptance.

## Review-readiness acceptance, 2026-09-07

PR #1 remains **draft**. The approved Vite/React → same-origin Netlify proxy → Docker FastAPI on Pete → caller-JWT PostgREST/RLS architecture is unchanged. No schema migration, shared Auth setting, account credential or membership was changed.

| Acceptance | Result | Evidence / limitation |
| --- | --- | --- |
| Local API authorization and auth | 43 passed | Every company/site/rename route denies nonmembers (404), viewers/operators (403) before data writes; viewer workspace reads are scoped; lost membership is rechecked. Provider responses are mocked. |
| Local PostgreSQL boundaries | 17 passed | Real PGlite schema/policies/triggers: committed company/site rows survive a separate transaction with exact actor/before/after/request audit evidence; viewer site denial, escalation and audit tamper checks pass. |
| Local UI | 12 passed | Site save/read-back after remount, audit details, tenant switching, logout, expiry, expired-code recovery and successful-write/failed-refresh handling. JSDOM and isolated responses; not live browser evidence. |
| Build and static checks | Passed | Production TypeScript/Vite build; Ruff lint/format; frontend format; whitespace checks. Locked dependencies unchanged. |
| Live company/site persistence | Passed | Chrome administrator created `PR1-20260907` company and `PR1-SITE` child site; both visible with their relationship after a full page reload. These labeled staging acceptance records and their audit history are intentionally retained. |
| Live company/site audit | Passed | Expanded both events in Activity. Database read-back independently confirms INSERT, administrator actor, null before, exact `after = to_jsonb(row)`, and request correlation. Receipts below. |
| Expired browser session write | Passed on previously deployed source | A stale session returned sign-in-required and removed the workspace UI; read-back confirmed zero acceptance rows before the successful fresh-session retry. This is session expiry, not a delivered expired magic-link test. |
| Authenticated viewer/cross-tenant HTTP | Pending | Staging has one tenant, one admin membership and zero viewer memberships. No unrelated Auth account was assigned access. Local policy/API tests do not substitute for live JWT/HTTP acceptance. |
| Live responsive UI and keyboard | Passed for exercised paths | Desktop 1440×900 and mobile 390×844: Organization fields fit; page width remains 390; Activity table scrolls within its container (707 content / 356 visible pixels). Both audit evidence panels opened, including Tab/Enter keyboard activation. Connections correctly shows not enabled. Viewport override reset afterward. Multi-tenant browser switching is still pending its fixture. |
| Browser security inspection | Pending | Successful refresh establishes browser session forwarding. Detailed HttpOnly/Storage/Set-Cookie inspection has not been performed in the live browser. Cookie flags and token-free JSON are covered locally. |
| Live delivered expired-link and replay | Pending | Local callback tests cover expired/provider-error/missing-verifier/replay recovery. A newly delivered expired link has not been exercised. |
| Live logout after fix | Pending deployment | Fix always clears session and pending PKCE cookies, including provider outages, and reports unconfirmed remote revocation. The UI clears private state and displays that limitation. Local tests cover provider success/401/403/500 and next-request 401. |

Audit receipts (UTC; account and tenant identifiers omitted):

- Company INSERT: `2026-09-07 09:13:15.855625+00`, request `39ec4e8e-9366-492c-8a70-480079c9f25f`.
- Site INSERT: `2026-09-07 09:13:45.100004+00`, request `0cca8c85-09c4-45e0-9376-0368703f092a`.
- The first rejected write had request `e7ba0307-3465-4816-b930-e9f3f6900883`; no acceptance company was committed.

`python scripts/verify-staging.py --help` and static checks validate the new credential-prompted live HTTP runner. It has **not** run authenticated against staging. It requires an explicitly approved existing admin/viewer arrangement across two tenants; it creates one labeled company/site, preserves audit evidence, tests FastAPI and direct PostgREST denials, and signs out its own sessions. See SETUP.md. A successful runner result covers only its stated HTTP scope.

## Historical foundation baseline (2026-09-05)

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


## Password authentication addition

24 API tests pass, including password grant cookie isolation, exact password preservation, authenticated self-only updates, Origin rejection, generic failure messages and rate limits. Frontend password confirmation/clearing is tested alongside the existing UI suite. Frontend build and API lint pass. Provider responses are mocked; no real account password was set during these checks.
