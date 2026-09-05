# Development and deployment setup

## 1. Choose an isolated Operis environment

Use a dedicated development/staging Supabase project. Do not point these setup steps at legacy operational databases. Keep production separate from development. No project is assumed or automatically created by this repository.

Inspect CLI help for the installed version before using it. The current build environment could not complete CLI setup; `supabase/schema.sql` is the authoritative reviewed initial SQL, without a fabricated migration identifier.

With a functioning CLI and local Supabase environment, apply the source to the disposable local database, run advisors, then generate the clean migration with `supabase db pull <name> --local --yes` and inspect `supabase migration list --local`, following that version's help. Alternatively, create the initial migration with `supabase migration new operis_foundation` and populate the resulting file with the reviewed schema. Commit that generated migration before applying to the approved hosted project. Do not apply both source and migration to the same database.

After applying to staging, confirm RLS on all five `operis_*` tables, explicit grants and the private helper schema. Keep `operis_private` out of exposed Data API schemas. Run Supabase advisors and cross-tenant tests against the real API.

## 2. Configure identity

Use an existing verified Supabase Auth user as first administrator. The application requests OTP with `create_user=false`; it does not create users or paid entitlements. Disable public signup in the dedicated project's Auth configuration as well, because the provider's public Auth endpoint is independent of the application.

Set the Magic Link email template to show `{{ .Token }}` as the sign-in code, and use a short OTP expiry. Configure a production SMTP provider before sending to real users. New free-tier projects on Supabase's default mail service cannot customize email templates after the June 3, 2026 change; custom SMTP or an eligible plan is required for this code template. See [passwordless email sign-in](https://supabase.com/docs/guides/auth/auth-email-passwordless) and [email template change](https://supabase.com/changelog/46599-changes-to-email-template-customisation-on-free-tier).

Set JWT lifetime to no more than 3600 seconds; the app deliberately does not persist refresh tokens or silently renew sessions. A cookie's browser expiry is not a server-side revocation mechanism. Supabase logout revokes the provider session's refresh capability; an already issued access token can remain valid until expiry. Removing membership takes effect immediately via database policies. Before sensitive operational actions, add strict session-id/revocation verification and approved session lifetime requirements.

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
| `OPERIS_SUPABASE_URL` | Base URL of the dedicated Supabase project |
| `OPERIS_SUPABASE_PUBLISHABLE_KEY` | Project publishable key; never substitute a service-role/secret key |
| `OPERIS_SESSION_SECONDS` | Cookie lifetime, 60–3600 seconds; cannot extend JWT validity |

No Supabase credentials belong in frontend environment variables. Browser code calls only `/api` and never instantiates a Supabase client. All application data calls use the verified user's token so RLS applies. The privileged operator database connection is not a runtime dependency.

## 4. Deploy the runtime

Build the image from `apps/api`. Dependency hashes are committed in requirements.txt, exported from uv.lock. The Dockerfile uses a non-root user and one worker.

```bash
docker build -t operis-api:phase-1 apps/api
```

Place the API behind HTTPS. Configure Netlify's `/api/*` rewrite to the actual backend `/api/:splat` target **before** the SPA fallback and remove the explicit unconfigured 503 rewrite. Set `OPERIS_APP_ORIGIN` to the exact frontend origin. Preserve Cookie, Set-Cookie, Content-Type and Origin through the proxy. Never cache authenticated `/api` responses. The production session cookie is `__Host-operis_session`, HttpOnly, Secure, SameSite=Strict, Path=/, with no Domain attribute.

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
