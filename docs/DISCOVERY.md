# Discovery assessment release

The user authorized the five-step scanner recovery, integration, ingestion, hosting and live acceptance sequence on 2026-09-07. The target remains the existing operis-staging Netlify site, Pete Docker backend and Operis objects in ZODA. This is an assisted staging release, not approval for public onboarding or ERP writes.

## Source and scope

The original `epicor_discover.py` v0.1 attachment was recovered from “Operis Status Update.” That conversation references `OPERIS_Epicor_Discovery_MVP_v0.2.zip`, but the ZIP was not available through the connected tools and the browser was signed out of ChatGPT. The new reviewed **0.3.0** kit derives its probe inventory and metadata counting from v0.1; it does not claim to be the recovered v0.2 artifact.

The existing Lovable AP Entry Lab at commit `37f41104d67c7bbfc2bee16a88d9941880bb6546` supplied the Discovery workflow: company binding, download, upload, coverage, recommendations and assessment history. Its browser ZIP parsing/direct database mutations and browser-stored identity were not carried into Operis. The integrated Vite application retains the existing cookie sign-in and same-origin FastAPI gateway.

This kit deliberately provides a bounded metadata assessment: eleven count/schema probes, with an authorized company check. It does not do full-estate discovery, export definitions, infer GL coding correctness, estimate savings, or support SyteLine. No ERP writes or communications are triggered. See scanner/README.md for the exact collection disclosure and limits.

## Local scanner workflow

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

### Staging receipt, 2026-09-07

- Draft PR: https://github.com/Aim67TQ7/Operis/pull/3.
- Application source: `f8a85516d19a2eed77127bada15b79316b783595`; subsequent verification-only commit `5a445cc4d0181a1568adacec1c0ab647a883e5e2`.
- Hosted migration `discovery_ingestion`: actual version `20260907112520`. All four discovery tables expose only SELECT to authenticated users, with membership read policies. The backend-only capability hash is configured; its plaintext remains in Pete's mode-600 env file and is never part of this repository.
- `supabase/tests/discovery-live.sql` passed against ZODA. Validated persistence, audit actor/request, identical retry, changed-content conflict, cross-company rejection, direct-write rejection, pilot idempotency, missing-capability rejection, viewer denial, membership removal and anonymous denial were checked with actual database roles. All fixtures and temporary capability settings rolled back. This is not an issued-JWT/browser test.
- Pete container is Healthy, running `operis-api:f8a85516d19a2eed77127bada15b79316b783595`. Docker image ID reported by inspect: `sha256:d4a6f7aeb9f48f4a15f850b5ca2ce19f07c8e3188bfe883cd5c06eeba8d5dcf1`.
- Preview `6a9e9f9b5356e8ff51ade8c7` passed HTTP route, scanner-byte/hash and upload Origin/auth/content-type checks. Frontend staging deploy `6a9ea03d57f6a9043aba7d1e` then published to the existing site. HTTPS readiness returns 200 and OpenAPI exposes six discovery paths.
- The normal signed-in Chrome session loads `/discovery`, company selection, scanner/configuration links, upload controls and assessment history. Source kit bytes served publicly match SHA-256 `6ecb65af5a3eb91771bad0f9cc739ca931db7090cfaeb13bfff1966a2c8c87b9`.
- A downloaded copy of the published kit ran on macOS against a **synthetic local HTTPS fixture**, produced a valid package with 12 GET requests, and reported one intentionally unavailable probe. The fixture is associated with the pre-existing labeled acceptance company; its signed configuration was issued using the deployed signing helper on Pete. Browser download actions were separately initiated. This is not a real Epicor scan.
- [GitHub Actions run 34116851899](https://github.com/Aim67TQ7/Operis/actions/runs/34116851899) passed API, frontend/database, and **Windows scanner** jobs. The Windows job executes the actual batch launcher in a path containing spaces against a synthetic HTTPS server, verifies credentials/extra fields are not exported, checks output checksums, and verifies failed preflight does not create another package.
- Security advisors report one Operis informational notice: the private capability-hash table has RLS and intentionally no client policies. Clients have no grants; opening access would weaken the intended boundary. See the [RLS policy advisory](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy). Unrelated shared-project findings were not modified.

### Open acceptance gates

The Chrome extension rejected file selection with `fileChooser.setFiles: Not allowed`; its documented requirement is "Allow access to file URLs." A package was prepared, but no browser upload, saved assessment or pilot click is claimed. The user was asked to enable the extension setting. The real Epicor company/environment selection is also still awaiting the user's answer. Existing Epicor settings were identified on the Mac, but were not used without confirming the intended test target. No customer ERP scan or customer invitation has occurred.

Keep PR #3 draft until the remaining acceptance receipts are recorded. Earlier source/compile/database successes do not close these gates.


## Browser discovery continuation — 2026-09-08

The user authorized browser-initiated discovery after organizational policy blocked scanner downloads. The existing Netlify → same-origin FastAPI on Pete → caller-JWT PostgREST architecture remains. No new database migration, worker, credential store, public signup or ERP write capability is introduced.

### Browser workflow

1. Sign in to the provisioned Operis organization. Select an existing company with the exact Epicor company code.
2. Choose **Set up browser scan**. The API returns the operator-configured HTTPS application endpoint for this tenant/company. A company without configuration receives an explicit setup error before credential entry.
3. Enter an authorized Epicor username, password and API key in the form, confirm the read-only collection, and select **Run read-only discovery**. The browser sends these credentials over the existing same-origin HTTPS API; they are used only in request memory and are not saved, returned, or logged. Password/API-key inputs clear when the request starts. Existing Kinetic browser sign-in is not reused or extracted.
4. Inspect the aggregate preview. Missing, denied, malformed or oversized measurements remain explicit unknowns. The company preflight must succeed; failure or timeout creates no assessment. The preview remains in component memory, expires after 30 minutes and is discarded on company/organization change or reload.
5. Select **Save assessment** to persist the aggregate observations, computed assessment and atomic audit through the existing RPC. A signed receipt binds tenant, company, code, actor, endpoint, measurements and expiry. Identical retries use the same scan identity/hash. The endpoint and credentials are omitted from persisted assessment data. View the saved assessment and existing history without downloading anything.

The collection remains the reviewed kit's seven count and four schema probes plus a selected-company preflight: twelve GET requests, no paging of business records, and no retained definitions or raw responses. Coverage is company-wide; choosing a site in Kinetic does not make this a site-filtered assessment. Browser scans have a different provenance statement from customer-supplied ZIP observations. The existing database's legacy original-filename field remains `aggregate-discovery.zip`; browser runs are identified by the report's server-observation statement, and their evidence hash covers the signed payload rather than an uploaded ZIP.

### Operator configuration and bounds

Set `OPERIS_DISCOVERY_BROWSER_TARGETS` to a JSON map of tenant UUID to `{"base_url":"https://erp.example/Test","companies":["TEST"]}`. Use `{}` to disable browser scans. Company codes must be explicitly listed; requests cannot select an arbitrary URL. Keep actual customer mappings in Pete's existing mode-600 env file, outside Git. Compose requires this setting; set it before upgrading. Preserve the existing ingestion capability and all other environment settings.

Destinations require HTTPS/443 without embedded credentials, query, fragment or ambiguous path escapes. Runtime DNS rejects nonpublic addresses; redirects are not followed, TLS is verified, and environment HTTP proxies are disabled. This is an operator-controlled destination allowlist, not a public URL-fetch service. The scanner requests identity encoding and rejects compressed responses before reading, so decompression cannot bypass the 4 MiB response limit. Requests use a four-second network timeout and the complete Epicor read phase has a 22-second deadline, with at most three probes in flight. The single-worker staging API allows one scan at a time and three attempts per user per ten minutes. No automatic retries or background jobs are created. Cancel discards the browser result; any already-started reads can continue only within the deadline, and no automatic save occurs.

Authenticated current admin/operator membership and company ownership are checked before network access, again before returning results, and on save. The database independently locks/rechecks membership and company on commit. Viewers receive 403, absent membership/company receives 404, and unconfigured companies receive 409. JSON bodies are size-bounded; malformed credential input and upstream failures produce redacted errors. The same-origin Origin check and no-store response policy apply to all new routes.

### Executed local checks

Production build and formatting passed. API/scanner: **125 passed**; web: **20 passed**; PostgreSQL/PGlite: **26 passed**. New tests cover endpoint/probe parity, GET-only transport, redaction, strict input bounds, redirects/private-network denial, unavailable probes, timeout, rate limiting, tenant/viewer rejection, membership removal during scan, receipt tampering/actor binding/expiry, stable save retries, explicit save, credential clearing, cancellation and company-switch isolation. PostgreSQL tests continue to verify atomic persistence/audit, direct-write rejection and immutable retries on the reused RPC.

These tests use synthetic upstream responses. They do not establish real Epicor API authentication or successful customer discovery. Live browser execution with the customer's credentials, saved assessment/audit read-back and pilot review remain acceptance gates; keep PR #3 draft until those receipts pass. The authorized test environment/company scope has now been supplied by the user, superseding the earlier “target pending” note. Organizational download restrictions remain in place; the browser flow requires neither a downloaded scanner nor file-picker access.
