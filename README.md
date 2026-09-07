# Operis

**One interface. Full context. Your systems, working as one.**

Operis is an operating intelligence layer above existing business systems. This repository starts its platform foundation. Existing Lovable builds and operational integrations are Phase 2.

## Implemented in this foundation

- Vite + React + TypeScript organization workspace, with responsive navigation and explicit loading/error/empty states.
- FastAPI email-code sign-in for existing users. Supabase access tokens remain in HttpOnly cookies; no tokens in localStorage, sessionStorage or response JSON.
- Organization selection, admin-only tenant naming, company and facility creation, and member role visibility.
- Postgres membership-based RLS, composite tenant/company foreign keys, and atomic, client-immutable audit records with before/after evidence.
- API liveness/readiness, request correlation, sanitized structured request logs, bounded OTP attempts, tests and CI.

**Staging frontend deployed:** [operis-staging.netlify.app](https://operis-staging.netlify.app). The approved ZODA database now contains the isolated Operis foundation. The Docker backend now runs on Pete and passed its HTTPS readiness check. The frontend API proxy is deployed. The first administrator is provisioned; real browser company/site persistence and audit read-back passed on 2026-09-07. Authenticated viewer/cross-tenant checks and the remaining session/browser gates still keep PR #1 in draft. See [the staging receipt](docs/STAGING.md). The Connections screen accurately states that integrations are not enabled. This is the first foundation slice, not completion of all seed platform gates.

## Layout

| Path | Responsibility |
| --- | --- |
| `apps/web` | User interface; all requests use same-origin `/api` |
| `apps/api/operis` | Identity gateway, policy checks, organization API |
| `supabase/schema.sql` | Reviewed initial SQL; applied to approved ZODA staging |
| `supabase/tests` | PGlite tests and rollback-only hosted database checks |
| `scripts/provision-tenant.sql` | Explicit operator bootstrap; no public tenant creation |
| `docs/architecture/PHASE_1.md` | Scope, interface hierarchy and architecture |
| `docs/SETUP.md` | Environment setup, sign-in configuration and deployment gates |
| `docs/PETE.md` | Prepared Docker deployment using Pete’s existing Caddy network |
| `docs/VERIFICATION.md` | Executed checks and limitations |
| `docs/roadmap/BUILD_SEQUENCE.md` | Foundation rollout and Phase 2 sequence |

## Local development

Requires Node 22.12+ (22 LTS recommended), Python 3.12 and uv.

```bash
npm ci --ignore-scripts
cd apps/api
uv sync --frozen
cp .env.example .env
```

Populate `.env` only with the approved environment's settings described in `docs/SETUP.md`. Start the API from `apps/api`:

```bash
uv run uvicorn operis.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal, from the repository root:

```bash
npm run dev
```

Open `http://localhost:5173`. With no Supabase settings, the login interface renders and the readiness/sign-in endpoints return an explicit configuration error. There is no authentication bypass or simulated workspace.

## Verification

From the repository root:

```bash
npm run build
npm run test:web
npm run test:db
```

From `apps/api`:

```bash
uv run ruff check operis tests
uv run ruff format --check operis tests
uv run pytest -q
```

API tests use isolated provider responses. Database tests execute the real schema/policies/triggers in a PostgreSQL WebAssembly engine with a minimal test auth schema. These local suites do not establish hosted integration. Separately, eight rollback-only checks passed on ZODA under actual database roles; see `docs/VERIFICATION.md`. Test records never seed the product.

## Deployment direction

Netlify serves the frontend and proxies `/api/*` to the Docker FastAPI backend under the same browser origin. The Netlify configuration proxies API requests to `https://operis-api.gp3.app`; the backend uses the approved ZODA project. The backend image runs as a non-root user with one worker. Read `docs/SETUP.md` before deploying; infrastructure changes, migrations and live provisioning require an approved target.
