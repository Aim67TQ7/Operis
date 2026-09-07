# Discovery assessment release

The user authorized the five-step scanner recovery, integration, ingestion, hosting and live acceptance sequence on 2026-09-07. The target remains the existing operis-staging Netlify site, Pete Docker backend and Operis objects in ZODA. This is an assisted staging release, not approval for public onboarding or ERP writes.

## Source and scope

The original `epicor_discover.py` v0.1 attachment was recovered from “Operis Status Update.” That conversation references `OPERIS_Epicor_Discovery_MVP_v0.2.zip`, but the ZIP was not available through the connected tools and the browser was signed out of ChatGPT. The new reviewed **0.3.0** kit derives its probe inventory and metadata counting from v0.1; it does not claim to be the recovered v0.2 artifact.

The existing Lovable AP Entry Lab at commit `37f41104d67c7bbfc2bee16a88d9941880bb6546` supplied the Discovery workflow: company binding, download, upload, coverage, recommendations and assessment history. Its browser ZIP parsing/direct database mutations and browser-stored identity were not carried into Operis. The integrated Vite application retains the existing cookie sign-in and same-origin FastAPI gateway.

This kit deliberately provides a bounded metadata assessment: eleven count/schema probes, with an authorized company check. It does not do full-estate discovery, export definitions, infer GL coding correctness, estimate savings, or support SyteLine. No ERP writes or communications are triggered. See scanner/README.md for the exact collection disclosure and limits.

## Customer workflow

1. Open `/discovery`, sign in using the existing Operis account, and select a company whose code matches Epicor.
2. Download `/kits/operis-epicor-discovery-0.3.0.zip` and the authenticated company configuration. Extract the kit and place `operis-scan-config.json` alongside the Python script.
3. Run `Run-Discovery.cmd` on Windows or `python3 epicor_discover.py` on macOS/Linux with network access to the authorized Epicor environment. Credentials stay on that machine. Inspect the generated ZIP.
4. Upload the current results ZIP. The API validates the archive, every JSON field, all checksums, the signed company context and scan time. It recomputes the assessment and atomically saves the run, findings, recommendations and audit event.
5. Inspect the saved coverage and candidate modules, download assessment JSON, and optionally save a pilot request. A tenant administrator sees the request on the saved assessment and in Activity. No email is sent and no subscription/module is activated.

Configuration expires after seven days. It binds tenant/company/code and scan identity; it is not attestation that customer-supplied observations are true or that an altered scanner contacted the intended ERP. The customer confirms the target and results. Authentication still requires explicitly provisioned organization access; no public signup is added.

## Ingestion and retention

Uploads are `application/zip` with a 1 MiB compressed limit and 128 KiB total expanded limit. Exactly four root files are accepted; nested paths, extra files, duplicate entries/JSON keys, symlinks, encryption, nonfinite numbers, wrong types, unsupported compression, unreasonable compression ratios and checksum mismatches are rejected. There is no extraction or uploaded code execution. The JSON schema admits only fixed keys, enumerated statuses, bounded counts and signed context. The two report placeholders must match the kit; uploaded prose/scores are not trusted.

Only normalized aggregate JSON, an original-package hash, server-generated findings/recommendations, and audit data are retained. Raw ZIP uploads are discarded after processing. `storage_path` is NULL for these runs. The pre-existing private bucket is retained and its old direct upload policy is removed; no stored objects are deleted. Existing legacy discovery tables are reused and their browser write privileges are revoked. Existing reports remain readable under membership RLS. New writes and pilot requests require admin/operator access; viewers may read.

A backend-only random capability is passed on the internal PostgREST ingestion request in `x-operis-ingest-key`, together with the caller's JWT. Only its SHA-256 hash is stored in `operis_private.discovery_ingest_config`; it is not a Supabase service-role credential. The private SECURITY DEFINER mutation checks this capability, `auth.uid()`, a locked current membership, and locked company binding. This narrow function is needed because authenticated clients have no direct table write grants. Public RPC wrappers are SECURITY INVOKER. No arbitrary SQL, role selection or actor ID can be submitted. Cross-tenant foreign keys and an immutable scan key provide additional boundaries. Report reads always use caller JWT and RLS.

A retry of identical bytes returns the original run. Different bytes using an already committed scan configuration return a conflict. Run + findings + recommendations + audit commit in one transaction, so a failed commit leaves no partial assessment. Pilot requests similarly persist once per run with caller identity and an audit event.

## Deployment and rollback

- Rebuild the reviewed source download with `python3 scripts/build-discovery-kit.py`. Its ZIP has fixed member timestamps; API tests verify that every bundled byte matches source and that the advertised checksum is correct.
- Fresh local databases: apply `supabase/schema.sql`, then `supabase/discovery-foundation.sql`, then the new migration. The second file is the historical applied discovery migration without storage provisioning. **Do not apply either foundation file again to ZODA.**
- Existing ZODA: apply only `supabase/migrations/20260907111341_discovery_ingestion.sql` through the migration service. Record the actual hosted version separately; the service may assign its own timestamp.
- Generate a dedicated random `OPERIS_DISCOVERY_INGEST_KEY` in Pete's existing mode-600 env file, without printing it. Set its hash in the private configuration table via the operator connection. No shared Auth or unrelated database configuration is changed.
- Deploy the branch's API image to the existing `operis-staging` Compose project and the built frontend to the existing Netlify site. Keep the PR draft pending live acceptance.
- Revert the application image/frontend release if needed; retain additive schema and audit history. Do not reopen raw upload or browser report-write privileges to roll back. The earlier foundation does not use these discovery objects.

## Verification

Local build, offline API/scanner tests, browser component tests and real PostgreSQL/PGlite tests are required. Counts and live receipts are recorded below after execution. Offline transport fixtures do not prove Epicor access; PGlite role tests do not prove issued JWTs or browser sessions. A live acceptance needs an authorized Epicor target and the user's normal Operis sign-in. A macOS run does not establish Windows launcher behavior.

### Local receipt

- Locked npm installation succeeded with no lockfile reconciliation needed in `Aim67TQ7/Operis`.
- Frontend production build passed.
- API/scanner: 89 passed, including hostile archive/schema inputs, context binding, expired configuration, redaction, bounded endpoints, real kit packaging and HTTP authorization.
- Web: 15 passed, including reviewed file upload, unknown coverage, saved pilot state, viewer restrictions and expired-session handling.
- PostgreSQL/PGlite: 26 passed across foundation and discovery, including capability rejection, company/tenant ownership, viewer denial, atomic audit, immutable retries and pilot idempotency.
- Live deployment and authorized ERP/Windows receipts: pending.
