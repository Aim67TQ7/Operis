# Foundation verification

Latest acceptance work: 2026-09-07. The current matrix below supersedes older pending statements; dated receipts later in this file are historical evidence. This is not full production acceptance.

## Review-readiness acceptance, 2026-09-07

PR #1 remains **draft**. The approved Vite/React → same-origin Netlify proxy → Docker FastAPI on Pete → caller-JWT PostgREST/RLS architecture is unchanged. No schema migration, shared Auth setting or account credential was changed. On continuation, two isolated QA tenants and one temporary viewer membership for the existing approved account were provisioned; the original Operis administrator membership is unchanged.

| Acceptance | Result | Evidence / limitation |
| --- | --- | --- |
| Local API authorization and auth | 43 passed | Every company/site/rename route denies nonmembers (404), viewers/operators (403) before data writes; viewer workspace reads are scoped; lost membership is rechecked. Provider responses are mocked. |
| Local PostgreSQL boundaries | 17 passed | Real PGlite schema/policies/triggers: committed company/site rows survive a separate transaction with exact actor/before/after/request audit evidence; viewer site denial, escalation and audit tamper checks pass. |
| Local UI | 12 passed | Site save/read-back after remount, audit details, tenant switching, logout, expiry, expired-code recovery and successful-write/failed-refresh handling. JSDOM and isolated responses; not live browser evidence. |
| Build and static checks | Passed | Production TypeScript/Vite build; Ruff lint/format; frontend format; whitespace checks. Locked dependencies unchanged. |
| Live company/site persistence | Passed | Chrome administrator created `PR1-20260907` company and `PR1-SITE` child site; both visible with their relationship after a full page reload. These labeled staging acceptance records and their audit history are intentionally retained. |
| Live company/site audit | Passed | Expanded both events in Activity. Database read-back independently confirms INSERT, administrator actor, null before, exact `after = to_jsonb(row)`, and request correlation. Receipts below. |
| Expired browser session write | Passed on previously deployed source | A stale session returned sign-in-required and removed the workspace UI; read-back confirmed zero acceptance rows before the successful fresh-session retry. This is session expiry, not a delivered expired magic-link test. |
| Authenticated viewer/cross-tenant HTTP | FastAPI passed; PostgREST user reported passed | Real Supabase-issued browser session: viewer reads 200; viewer rename/company/site writes 403; existing private tenant reads and writes 404; admin site creation with a private company 404. Every response was no-store, correlated and token-free. Rejected writes left viewer data/audit unchanged. Receipts below. The user subsequently reported PostgREST passes. No per-request direct PostgREST receipt or runner output was supplied; this is user acceptance, not an independently captured bypass-matrix run. |
| Live responsive UI and keyboard | Passed for exercised paths | Desktop 1440×900 and mobile 390×844: Organization fields fit; page width remains 390; Activity table scrolls within its container (707 content / 356 visible pixels). Both audit evidence panels opened, including Tab/Enter keyboard activation. Connections correctly shows not enabled. Viewport override reset afterward. Live admin → viewer → admin switching clears old records during loading, scopes loaded records and hides/restores write controls. |
| Browser security inspection | Passed for exercised scope | While authenticated, the same-origin harness found no JavaScript-visible session/PKCE cookie, empty localStorage and sessionStorage, and no token fields in all checked API responses. Live logout header probes independently verified Secure/HttpOnly cookie deletions. Browser cookie-store metadata for the original sign-in Set-Cookie was not exported. |
| Live membership removal | Passed | Removed only the temporary QA viewer membership. The next workspace request returned 404; /me omitted the revoked tenant. App Refresh cleared its private records; full reload selected the original admin organization and removed QA Viewer from the selector. Fixture rows and audit history retained. |
| Live callback recovery; delivered expired-link and replay | Expired-link recovery passed (user verified); replay pending | The user confirmed normal sign-in works and that an expired email link required obtaining a new one. This is manual user acceptance of the expired-link recovery flow. Separately, the synthetic callback returned HTTP 400/no-store and a safe recovery link. A previously consumed link replay remains unverified live. |
| Live logout after fix | Passed | Updated signed-in Chrome session displayed the real workspace after deployment; Sign out removed private UI and a full reload stayed signed out. Proxied HTTP logout separately returned 200 and both Secure/HttpOnly/Path=/ cookie deletions (session Strict, PKCE Lax), no Domain, Max-Age=0 and no-store. Provider outage cleanup is locally tested, not a live outage injection. |

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


## Deployed acceptance fix, 2026-09-07

- Application source: `6fe21263b5b55333c5bf10e0a9a1973f4d799dc2`. [GitHub Actions run 34106990331](https://github.com/Aim67TQ7/Operis/actions/runs/34106990331) passed.
- Frontend: ready deploy `6a9e868480b3933803d96053`, built locally with the locked dependencies and uploaded to the existing staging site. Netlify redirects/headers retained.
- Backend: `operis-api:6fe21263b5b55333c5bf10e0a9a1973f4d799dc2`, image digest `sha256:e894ce2299876b319d449d180167a92bef895fc17f3500d285d558a11485d2e8`; Compose reports Healthy. Only Operis api was recreated. The saved release identifier was updated atomically; other runtime values preserved.
- Browser session receipts from sanitized backend logs: `/api/me` 200 (`e700a103-d8da-4cf6-9ca6-aa4617559bff`), workspace 200 (`e4ac0019-ee12-441b-b202-074ebd8d8990`), authenticated logout 200 (`f326c41d-4765-4856-bc6a-89b5aa04a621`).
- Post-deploy checks at 2026-09-07T09:41:07.693179+00:00: all below passed with no-store headers. No emails were sent by these probes.

| Request | HTTP | Request ID |
| --- | --- | --- |
| GET /api/health/live | 200 | `2d0c3f30-9ed5-4c3e-970b-3f8fe6606709` |
| GET /api/health/ready | 200 | `a2f9e192-ea2b-49e7-8e11-3574e76a0b5e` |
| GET /api/me | 401 | `8c9b5dd3-56eb-49ea-88a9-9518f5f3c1f6` |
| POST /api/auth/verify | 422 | `067ca269-ca02-4b33-84fb-070bdf20874c` |
| POST /api/auth/verify | 403 | `e1a4657c-8e23-43c8-b7bd-aff75611737e` |
| GET /api/auth/callback | 400 | `1e98d5d2-10d9-4ca9-a1c4-7cd3ccd2b75d` |
| POST /api/auth/logout | 200 | `70ab512f-1b7d-4754-817b-fbbc44703c1e` |

Keep PR #1 draft: replay of an already consumed email link remains unconfirmed. Expired-link recovery and PostgREST are recorded as passed by user confirmation. The live FastAPI viewer/cross-tenant, tenant-switching, membership-removal and browser non-persistence checks now pass. Production backup/restore and operational release controls remain broader production gates.


## Single-account QA continuation

The user authorized continuation. Two synthetic fixture organizations, **Operis PR1 QA Viewer** and **Operis PR1 QA Private**, were provisioned atomically with one company each. Only the existing approved identity received a temporary viewer membership, scoped to QA Viewer. QA Private has no membership. The original Operis administrator membership and all Auth users/settings were preserved. Fixture identifiers and account details are omitted from public evidence.

`scripts/staging-browser/` contains a temporary same-origin browser harness for the authenticated API matrix, storage non-persistence and immediate membership-removal check. It is excluded from the ordinary Vite build. Staging deploy `6a9e8af94b31821a386414d1` temporarily includes `/__qa/pr1.html` alongside the unchanged application from `6fe2126`; restore the normal build after collecting the evidence. No backend test endpoints, credential forms, token export or authorization bypass were added.

The first attempt at `2026-09-07T10:02:21.382Z` stopped at `/api/me` **401**, request `bb8500bb-b5d5-4427-92ae-50b69082ddd3`, because the browser remained signed out. No mutation requests ran in that attempt. The user subsequently completed password sign-in; this does not establish email-link delivery acceptance.

### Authenticated browser receipt, 2026-09-07 10:11–10:15 UTC

The same-origin harness completed all boundary assertions at `2026-09-07T10:11:27.035Z`, then membership-removal assertions at `2026-09-07T10:13:25.987Z`. It used the normal HttpOnly session and deployed FastAPI gateway. Credentials, tokens, account IDs and tenant IDs are omitted from this evidence. Sanitized backend request logs independently confirm the statuses and request IDs.

| Live request | HTTP | Request ID |
| --- | --- | --- |
| Authenticated identity | 200 | `32a66787-2938-403a-9747-19577d35a5d2` |
| Admin workspace | 200 | `49aa0d2a-d143-4b8c-ac9c-5f007ddfe92a` |
| Viewer workspace | 200 | `5c3ae7d5-5fce-4be5-af7d-879d5332c256` |
| Existing private workspace | 404 | `7c3f0433-c21c-4519-b82d-831168462172` |
| Viewer rename | 403 | `bb9c3472-0878-49cf-b39f-c4c411998c79` |
| Viewer company creation | 403 | `c4ee58bc-3308-460e-92b4-d4000b5a90a6` |
| Viewer site creation | 403 | `e625933f-840a-4c30-a1cf-66559c71af35` |
| Private tenant rename | 404 | `e71ad321-29c4-4d5c-a862-470429c39d38` |
| Private company creation | 404 | `f43a2954-44c3-4a4b-abd1-e32b149583b3` |
| Private site creation | 404 | `b4f94c35-0d36-40b5-846a-b544481cf28b` |
| Admin site with private company parent | 404 | `bf1e8156-cf31-41f0-974e-ac8e9d05ff10` |
| Viewer workspace after denied writes | 200 | `739ec1ff-1da1-47f2-a108-5c5aa996a534` |
| Workspace immediately after membership removal | 404 | `fbcd9554-e1d8-43e7-9da3-e697d3084357` |
| Identity after membership removal | 200 | `c9db7890-a20b-4e7a-894d-561578b7f331` |
| App Refresh after membership removal | 404 | `f1af97ff-f8da-4e2f-b6b1-9e4bd82081ef` |
| Authenticated logout | 200 | `fb02d894-c199-4f5f-b08e-95c1521208d6` |
| Identity after logout and full reload | 401 | `e0a370ae-cf63-4efd-bc35-c3484b57c82a` |

All harness requests also passed no-store, nonempty correlation ID and absence of access_token/refresh_token/id_token response fields. Browser document.cookie exposed neither Operis session nor PKCE cookie; localStorage and sessionStorage were empty. Viewer workspace JSON, including audit, matched before and after rejected writes. Independent database read-back found one fixture company and zero sites in each QA organization, with the original three/two audit events respectively, and zero `PR1-DENIED` companies or sites. Exactly one temporary viewer membership was subsequently removed; the original administrator membership remains intact.

In the app, switching to QA Viewer showed only its fixture company, no sites and no organization/company/site write forms. Switching back restored the original administrator records and controls. After viewer membership removal, Refresh showed a load error with no private records; full reload removed QA Viewer from the selector and opened the original administrator workspace. Logout then removed private UI and reload stayed signed out.

Application code remains `6fe2126`. Harness/documentation commit `10206b2` passed [GitHub Actions run 34109505166](https://github.com/Aim67TQ7/Operis/actions/runs/34109505166). Normal frontend deploy `6a9e8eae62c1bc79311a8cae` removed the temporary harness after evidence collection; its old route now serves the ordinary SPA fallback. HTTPS frontend and proxied readiness passed, readiness request `40228f29-562e-4a51-8bce-d01c62c6f8df`. Harness source remains available for a future explicitly scoped run. PR remains draft for the unconfirmed consumed-link replay check.

### User acceptance: expired email link

On 2026-09-07 the user confirmed that normal Operis sign-in works, then reported: “the expired links passed - it made me get a new one”. Record expired-link recovery as passed by manual user verification. No new link, code or credentials were collected. This receipt does not assert a captured HTTP status or identify whether provider expiry or the browser verifier caused rejection. Rejection of a previously consumed link remains a separate live check.

### User acceptance: PostgREST

On 2026-09-07, after the remaining direct PostgREST checks were identified, the user reported: “postgREST is perfect”. Record PostgREST as passed by user verification. No request-by-request statuses, test identities or runner output were provided. The credential-prompted runner was not executed by the agent, and no independent direct HTTP denial/tampering receipt is claimed. Existing automated SQL and live FastAPI evidence remains separately identified above.
