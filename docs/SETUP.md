# Development and Deployment Setup

This public setup guide describes the safe development and release boundaries for the Operis foundation. Private provider URLs, hostnames, project identifiers, credentials, and operator-specific receipts must stay outside the repository.

## Local Development

Requires Node 22.12+, Python 3.12, and uv.

```bash
npm ci --ignore-scripts
cd apps/api
uv sync --frozen
cp .env.example .env
```

Populate `.env` with approved local or staging values from the private deployment record. Do not commit provider URLs, publishable keys, service-role keys, database passwords, customer records, exported ERP data, or operator credentials.

Start the API from `apps/api`:

```bash
uv run uvicorn operis.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal, from the repository root:

```bash
npm run dev
```

Open `http://localhost:5173`. With no provider settings, the login interface renders and the readiness/sign-in endpoints return an explicit configuration error. There is no authentication bypass or simulated workspace.

## Identity Boundary

Operis supports already verified users. The application does not create public accounts, organizations, paid entitlements, or connector access from the frontend. Tenant membership remains required regardless of identity-provider signup policy.

Email links and codes must be verified against the approved identity provider. Shared provider settings, templates, redirect URLs, email delivery configuration, and token lifetime are deployment-owned controls. Do not change them from this repository.

Sessions use HttpOnly cookies. Tokens must not appear in JavaScript-accessible storage, response JSON, logs, docs, screenshots, or analytics. Refresh-token persistence and silent renewal are deferred.

## Database Boundary

Only `public.operis_*` objects and the `operis_private` helper schema belong to this foundation. Preserve unrelated schemas, data, grants, policies, provider settings, and legacy records.

Future schema changes require reviewed incremental migrations. Do not dump or commit shared database schemas, migration receipts, live project identifiers, customer data, or operator records.

Tenant provisioning is operator-only. Public onboarding, payment activation, invitations, connector registration, operational writes, and agents are later slices with separate controls.

## Deployment Boundary

The public repository defaults `/api/*` to an explicit unconfigured response so private backend origins are not committed. Configure live API routing in the approved deployment target.

The backend should run behind HTTPS with exact-origin CSRF checks, no cached authenticated API responses, and preserved Cookie, Set-Cookie, Content-Type, and Origin headers. Operational hostnames, network names, provider URLs, and deploy receipts belong in private runbooks.

## Acceptance Gate

Before release, verify:

- Production build and all local test suites pass.
- API liveness and readiness pass in the approved environment.
- Real email sign-in works end to end in the same browser.
- Tokens stay out of browser-accessible storage and response JSON.
- Tenant isolation, viewer restrictions, self-escalation denial, logout, provider outage, and proxy errors behave correctly.
- Desktop/mobile browser layout and keyboard navigation are inspected.
- Backup, rollback, incident ownership, and support ownership are documented privately.

The repository tests do not substitute for live acceptance. See [VERIFICATION.md](VERIFICATION.md) for public verification scope.
