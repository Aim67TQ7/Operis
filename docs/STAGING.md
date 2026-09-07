# Operis staging receipt

Recorded 2026-09-05 after the user approved staging resources and selected the existing ZODA database.

## Deployed resources

| Resource | Recorded value | State |
| --- | --- | --- |
| Supabase project | ZODA, `ezlmmegowggujpcnzoda` | Existing shared project; no new project created |
| Supabase URL | `https://ezlmmegowggujpcnzoda.supabase.co` | Approved API configuration target |
| Migration | `operis_foundation`, version `20260905132610` | Applied through Supabase migration service |
| Netlify team | n0v8v, slug `aim67tq7` | Approved staging team |
| Netlify project | `operis-staging`, ID `5dc6fae8-a930-4483-b8a5-37d718aa0bc4` | Created |
| Frontend origin | [https://operis-staging.netlify.app](https://operis-staging.netlify.app) | HTTPS page and assets return 200 |
| Netlify deploy | `6a9c5d465bf2eddc00dfa917` | Ready, published 2026-09-05T18:20:07Z; API proxy enabled |
| Backend | Docker FastAPI on Hostinger Pete | Running; user verified HTTPS liveness and readiness HTTP 200 |

[Netlify deployment details](https://app.netlify.com/sites/5dc6fae8-a930-4483-b8a5-37d718aa0bc4/deploys/6a9c5d465bf2eddc00dfa917).

The frontend was deployed from a source upload of `build/phase-1-foundation` with the staging configuration changes. This does not establish automatic GitHub deployment. Netlify labels this the site's production context because it serves the site's primary URL; Operis remains a staging environment, not an accepted production application.

## Database changes and verification

Preflight found no Operis object collisions. The initial reviewed schema created five `public.operis_*` tables and the `operis_private` helpers, with explicit grants, RLS policies, relationships and audit triggers. Unrelated application objects and shared Auth configuration were not changed.

The migration service owned the transaction. The submitted source omitted the source file's outer BEGIN/COMMIT and used a five-second local lock timeout. Migration history records the version above; do not apply the initial schema again to ZODA. Use reviewed incremental migrations for subsequent changes.

All five tables have RLS enabled. Eight policies were inspected. Anonymous insert and authenticated delete grants are absent. Security advisor output contained no findings naming Operis objects; unrelated existing findings are outside this check, so this is not a security clearance for the whole shared project.

`supabase/tests/live-boundaries.sql` passed eight checks under actual authenticated/anonymous database roles: tenant visibility, atomic actor audit, cross-tenant insert denial, cross-company relationship denial, audit mutation denial, viewer write denial, self-escalation denial and anonymous visibility. The test used two existing verified user IDs only for local JWT claims, sent no email, and rolled back every temporary data change. All five Operis tables were empty afterward. This establishes database-role boundaries, not successful JWT issuance or HTTP integration.

## Remaining setup

1. Backend deployment completed on Pete at source commit `4db7de238ec797f09b6e29ac90912b6c0889e16a`. See [PETE.md](PETE.md) for the build and HTTPS readiness receipts.
2. Netlify published the `/api/*` proxy to `https://operis-api.gp3.app/api/:splat` in deploy `6a9c5d465bf2eddc00dfa917`. Live checks through the frontend origin passed readiness (200), unauthenticated access denial (401), input validation (422), Origin rejection (403) and no-store headers. Successful session cookie forwarding still needs a real sign-in.
3. Confirm existing ZODA Auth is compatible with code sign-in without changing global email, signup or session settings for other applications. No emails were sent during this setup.
4. The user superseded the earlier Magnet Applications name with **Operis** and explicitly confirmed the existing verified first-admin account. On 2026-09-05, one Operis tenant and its admin membership were provisioned atomically after checking that no tenant existed. Read-back verified the membership and one INSERT audit event each for the tenant and membership. Account identifiers are intentionally omitted from this public repository. Shared Auth settings and Auth user records were not changed. Do not rerun initial provisioning.
5. Complete deployed API readiness, real sign-in, persistence, cross-tenant HTTP tests and browser acceptance from SETUP.md.

The frontend now routes API requests to the HTTPS Pete backend. The initial placeholder deployment remains available as a historical rollback release. Frontend routes including `/workspace` return the SPA. No credentials, operational records or demonstration tenants are shipped in the frontend.

## Rollback boundary

Retain this additive schema during application rollback. Do not drop shared schemas, undo unrelated grants, or roll back shared Auth settings. Record an immutable backend image and verify backups before accepting operational writes. The deployed frontend permalink is [this release](https://6a9c195e0e442f20d55397e0--operis-staging.netlify.app).

The proxy deployment permalink is [this release](https://6a9c5d465bf2eddc00dfa917--operis-staging.netlify.app).


## Acceptance continuation, 2026-09-07

Read-only Netlify inspection identifies current ready frontend deploy `6a9c7086b96cca868f567eec`, which includes password/link sign-in. Direct SSH inspection confirms the healthy Operis backend runs `operis-api:258f96d724963bb8ae2a52d8e2a9396ac4ac902d` on Pete in `/opt/operis-staging`. Earlier statements about unavailable SSH and missing password UI are historical.

Browser creation, full-reload persistence and audit evidence passed for one labeled PR1 acceptance company/site. Retain these records and their history; no automatic cleanup or shared schema reset is authorized. At that point staging had one tenant and no viewer membership; the isolated fixture run below supersedes that pending statement. See the current VERIFICATION.md matrix.

Application commit `6fe21263b5b55333c5bf10e0a9a1973f4d799dc2` was then deployed to the same Pete service and Netlify site. Frontend deploy `6a9e868480b3933803d96053` is the new primary staging release; Pete reports Healthy and frontend-proxied readiness is 200. The saved backend release was updated, preserving other environment values. Authenticated browser logout now passes through the updated stack and remains signed out after reload. See VERIFICATION.md for request receipts and still-open draft gates.


### Isolated QA fixtures ready

On the user-authorized continuation, two synthetic QA organizations and one temporary viewer membership were added for the existing approved account. Its original Operis administrator membership is unchanged; the private QA organization has no memberships. This lets one real identity exercise admin, viewer and outsider paths without creating a new Auth user or granting an unrelated account access to existing business records. The signed-in FastAPI matrix, tenant switching, storage non-persistence and immediate membership-removal checks subsequently passed. The temporary viewer membership was removed; original administrator access and all fixture/audit records were retained. See VERIFICATION.md for request receipts and remaining direct PostgREST/email-link gates.

Normal frontend staging build restored in deploy `6a9e8eae62c1bc79311a8cae` after collecting browser evidence. `/__qa/pr1.html` now serves the ordinary SPA fallback, with no QA harness. Frontend HTTPS and proxied readiness return 200 (readiness request `40228f29-562e-4a51-8bce-d01c62c6f8df`). Application code remains `6fe2126`; the approved architecture and Pete backend are unchanged.
