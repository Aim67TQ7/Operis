# Development and deployment setup

## 1. Approved staging environment

The user selected the existing **ZODA** Supabase instance for Operis staging on 2026-09-05. Its database is shared with existing applications. The additive `operis_foundation` migration has already been applied; **do not reapply `supabase/schema.sql` to ZODA**. See [STAGING.md](STAGING.md) for the deployment receipt and remaining setup.

Only `public.operis_*` objects and the `operis_private` helper schema belong to this foundation. Preserve unrelated schemas, data, grants, policies and shared Auth settings. Keep `operis_private` out of exposed Data API schemas. Future schema changes require reviewed incremental migrations; do not dump or commit the shared database's legacy schema or records.

For a new disposable local environment, apply the reviewed initial source once. Inspect the installed CLI's help before generating migrations. This environment's CLI setup was blocked by a cancelled network approval, so the hosted migration was applied through the Supabase migration service. The actual recorded migration version is `20260905132610`, not an invented local migration identifier.

## 2. Configure identity without changing shared Auth

Use an existing verified Supabase Auth user as first administrator. The application requests OTP with `create_user=false`; it does not create users or paid entitlements. The approved Operis organization and verified first-admin membership have been provisioned. Provider signup settings are independent of the application; tenant membership remains required regardless of provider signup policy.

ZODA's email template, SMTP configuration and token lifetime are shared with existing applications. **Do not change them for Operis during this setup.** The application now requests PKCE magic links with an explicit `/api/auth/callback` redirect. Add exactly `https://operis-staging.netlify.app/api/auth/callback` to the project's additional Redirect URLs, preserving every existing entry and the Site URL. The shared template must use `{{ .ConfirmationURL }}` (a hard-coded neoneo link or SiteURL-only link will not honor the requested redirect). Do not change that shared template in this rollout; inspect it if a newly requested link still goes to neoneo.

A random verifier is stored for ten minutes in an HttpOnly, Secure, SameSite=Lax cookie so it accompanies the cross-site callback navigation. The callback exchanges the one-use code server-side, checks verified identity, clears the verifier and sets the existing Strict session cookie. Open the latest email link in the same browser/device that requested it. Existing six-to-ten-digit email-code verification remains supported. No session tokens appear in response JSON or JavaScript storage. New requests supersede earlier links in the same browser. The callback is deployed; expired-link recovery passed by user verification, while consumed-link replay acceptance remains pending. See [passwordless email sign-in](https://supabase.com/docs/guides/auth/auth-email-passwordless).

The app deliberately does not persist refresh tokens or silently renew sessions, and caps cookie lifetime at 3600 seconds. A cookie's browser expiry is not server-side token revocation. Supabase logout revokes refresh capability; an already issued access token can remain valid until its provider expiry, which has not been verified on ZODA. Removing membership takes effect via database policies. Before sensitive operational actions, add strict session-id/revocation verification and approved session lifetime requirements without unilaterally altering shared Auth.

Use an operator's secure database connection to run the provisioning script after replacing the non-secret inputs below. Supply database credentials through your approved environment or password prompt, never the command text, chat or repository.

```bash
psql -v tenant_name='Your organization' -v admin_user_id='VERIFIED-USER-UUID' -f scripts/provision-tenant.sql
```

This creates one tenant and one admin membership in a single transaction, with audit entries. The script is intentionally operator-only and not retry-idempotent: inspect the prior result before repeating. Payment activation, invoices, subscriptions and invitation lifecycle are subsequent slices.

## 3. API configuration

Copy `apps/api/.env.example` to `.env` in that directory for development. Production uses host-managed environment values.

| Variable | Meaning |
| --- | --- |
| `OPERIS_ENVIRONMENT` | `development`, `test`, or `production`; production fails startup without secure configuration |
| `OPERIS_APP_ORIGIN` | Exact browser origin, such as the chosen HTTPS frontend origin; no path |
| `OPERIS_SUPABASE_URL` | Base URL of the approved ZODA project (see STAGING.md) |
| `OPERIS_SUPABASE_PUBLISHABLE_KEY` | Project publishable key; never substitute a service-role/secret key |
| `OPERIS_SESSION_SECONDS` | Cookie lifetime, 60–3600 seconds; cannot extend JWT validity |

No Supabase credentials belong in frontend environment variables. Browser code calls only `/api` and never instantiates a Supabase client. All application data calls use the verified user's token so RLS applies. The privileged operator database connection is not a runtime dependency.

## 4. Deploy the runtime

Build the image from `apps/api`. Dependency hashes are committed in requirements.txt, exported from uv.lock. The Dockerfile uses a non-root user and one worker.

```bash
docker build -t operis-api:phase-1 apps/api
```

Place the API behind HTTPS. The repository now places Netlify's `/api/*` rewrite to `https://operis-api.gp3.app/api/:splat` **before** the SPA fallback. Verify the active frontend deployment includes that configuration. Set `OPERIS_APP_ORIGIN` to the exact frontend origin. Preserve Cookie, Set-Cookie, Content-Type and Origin through the proxy. Never cache authenticated `/api` responses. The production session cookie is `__Host-operis_session`, HttpOnly, Secure, SameSite=Strict, Path=/, with no Domain attribute.

Origin validation is the CSRF boundary; state changes require exact allowed Origin and JSON. No permissive CORS configuration is used. Do not strip Origin at the proxy. Netlify custom headers protect the static frontend; ensure your backend proxy also preserves the API's no-store headers.

Apply a small request-body limit (16 KB is sufficient for these forms) and abuse limits at the trusted edge. The application limiter is an in-memory, single-process OTP backstop. Multiple replicas need a shared limiter or a verified edge policy. The Docker command does not trust forwarded IP headers, so proxy traffic may share a conservative IP limit. Configure trusted proxy handling explicitly before scaling; never trust arbitrary X-Forwarded-For input.

## 5. Acceptance before production

- Verify `/api/health/live` and `/api/health/ready`; readiness checks Auth and the tenant schema, not SMTP delivery or every RLS rule.
- Sign in through actual email delivery; confirm tokens are absent from JavaScript-accessible storage and responses.
- Create a company/site and rename the organization; verify persistence after reload and actor/before/after/request evidence.
- Exercise a second tenant and viewer; reject cross-tenant reads/writes and self-escalation through both FastAPI and direct PostgREST.
- Check expired codes, lost membership, logout, provider outage and proxy errors.
- Verify desktop/mobile UI, keyboard navigation and tenant switching in a real browser.
- Verify a database backup restore and document host, incident and support ownership.

The repository's tests do not substitute for this live acceptance gate. See `VERIFICATION.md` for what ran here.

## Operational limits of this slice

Organization lists are capped at 200 records and activity at the latest 200 events. There are no operational records, document uploads, connector secrets, agents, external writes, financial actions or schedules. Structured application request logs record correlation, route template, method, status and duration without request bodies or token values. Supabase owns authentication event logs; unified tenant authentication audit presentation is deferred.


## Password sign-in

Password login is available alongside email links. After signing in, expand **Account password**, enter and confirm a password of at least 12 characters, and save. This updates the same ZODA Auth identity used by other connected applications. Supabase's existing password and reauthentication policies still apply; no project settings are changed. For a forgotten password, use an email link to sign in and return to Account password. If the provider requires a fresh session, sign out and use a fresh email link first.

The backend uses the password grant and the current caller's authenticated update-user endpoint. Passwords are not normalized, logged, returned in JSON, or persisted by Operis. Login attempts are rate-limited; password updates require the verified session, allowed Origin and JSON. The existing tenant membership checks remain unchanged. Live password entry is performed by the user; deployment and an actual password sign-in remain acceptance gates.


## Repeatable staging HTTP acceptance

After the operator designates an existing administrator and viewer in one Operis tenant, and the viewer has access to a second tenant invisible to the administrator, run from the repository root:

```bash
apps/api/.venv/bin/python scripts/verify-staging.py --write-fixtures
```

The script is fixed to the approved Netlify origin and ZODA URL. It prompts locally for existing account credentials and a modern publishable key; do not place secrets in shell arguments, chat, evidence or source. It does not set passwords, create accounts, change memberships or modify shared Auth. It creates and retains one labeled company and site per invocation, verifies persisted actor/before/after/request evidence, checks API 403/404 and direct PostgREST isolation/tampering, and clears its own sessions. Its final JSON is sanitized; a nonzero exit means acceptance failed. Review the target and use only designated test accounts.

Live browser layout, storage non-persistence, tenant switching and membership removal have separate passing receipts in VERIFICATION.md. Expired-link recovery passed by user verification; consumed-link replay remains pending. Do not mark the draft PR ready solely because this runner or local tests pass.
