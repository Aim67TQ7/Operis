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
| Netlify deploy | `6a9c195e0e442f20d55397e0` | Ready, published 2026-09-05T13:30:20Z |
| Backend | Docker FastAPI | Host/access not selected; not deployed |

[Netlify deployment details](https://app.netlify.com/sites/5dc6fae8-a930-4483-b8a5-37d718aa0bc4/deploys/6a9c195e0e442f20d55397e0).

The frontend was deployed from a source upload of `build/phase-1-foundation` with the staging configuration changes. This does not establish automatic GitHub deployment. Netlify labels this the site's production context because it serves the site's primary URL; Operis remains a staging environment, not an accepted production application.

## Database changes and verification

Preflight found no Operis object collisions. The initial reviewed schema created five `public.operis_*` tables and the `operis_private` helpers, with explicit grants, RLS policies, relationships and audit triggers. Unrelated application objects and shared Auth configuration were not changed.

The migration service owned the transaction. The submitted source omitted the source file's outer BEGIN/COMMIT and used a five-second local lock timeout. Migration history records the version above; do not apply the initial schema again to ZODA. Use reviewed incremental migrations for subsequent changes.

All five tables have RLS enabled. Eight policies were inspected. Anonymous insert and authenticated delete grants are absent. Security advisor output contained no findings naming Operis objects; unrelated existing findings are outside this check, so this is not a security clearance for the whole shared project.

`supabase/tests/live-boundaries.sql` passed eight checks under actual authenticated/anonymous database roles: tenant visibility, atomic actor audit, cross-tenant insert denial, cross-company relationship denial, audit mutation denial, viewer write denial, self-escalation denial and anonymous visibility. The test used two existing verified user IDs only for local JWT claims, sent no email, and rolled back every temporary data change. All five Operis tables were empty afterward. This establishes database-role boundaries, not successful JWT issuance or HTTP integration.

## Remaining setup

1. Select the Docker backend host and provide its approved deployment access. Configure production environment values from SETUP.md, with the ZODA publishable key supplied securely to that host. No runtime service-role key is needed.
2. Replace the Netlify `/api/*` placeholder with the actual HTTPS backend proxy and redeploy. Set `OPERIS_APP_ORIGIN=https://operis-staging.netlify.app` on the backend and preserve Origin/cookie headers.
3. Confirm existing ZODA Auth is compatible with code sign-in without changing global email, signup or session settings for other applications. No emails were sent during this setup.
4. Confirm the initial organization name and verified first-admin account; run the explicit provisioning transaction once. No initial tenant/admin has been created yet.
5. Complete deployed API readiness, real sign-in, persistence, cross-tenant HTTP tests and browser acceptance from SETUP.md.

Until the backend is configured, `/api/health/ready` returns HTTP 404 with the explicit API-unconfigured JSON response. Frontend routes including `/workspace` return the SPA. No credentials, operational records or demonstration tenants are shipped in the frontend.

## Rollback boundary

Retain this additive schema during application rollback. Do not drop shared schemas, undo unrelated grants, or roll back shared Auth settings. Record an immutable backend image and verify backups before accepting operational writes. The deployed frontend permalink is [this release](https://6a9c195e0e442f20d55397e0--operis-staging.netlify.app).
