# Operis

**One interface. Full context. Your systems, working as one.**

Operis is an operating intelligence layer above existing business systems. This repository starts its platform foundation. Existing Lovable builds and operational integrations are Phase 2.

## Implemented in this foundation

- Vite + React + TypeScript organization workspace, with responsive navigation and explicit loading/error/empty states.
- FastAPI email-code sign-in for existing users. Provider access tokens remain in HttpOnly cookies; no tokens in localStorage, sessionStorage or response JSON.
- Organization selection, admin-only tenant naming, company and facility creation, and member role visibility.
- Postgres membership-based row security, composite tenant/company foreign keys, and atomic, client-immutable audit records with before/after evidence.
- API liveness/readiness, request correlation, sanitized structured request logs, bounded OTP attempts, tests and CI.

**Staging frontend deployed:** [operis-staging.netlify.app](https://operis-staging.netlify.app). The approved staging database contains the isolated Operis foundation. The containerized API passed its HTTPS readiness check. The public source defaults `/api/*` to an explicit unconfigured response; live proxy targets are deployment-specific and must not be committed. Real sign-in and workspace acceptance still require live browser validation. See [the staging receipt](docs/STAGING.md). The Connections screen accurately states that integrations are not enabled. This is the first foundation slice, not completion of all seed platform gates.

## Layout

| Path | Responsibility |
| --- | --- |
| `apps/web` | User interface; all requests use same-origin `/api` |
| `apps/api/operis` | Identity gateway, policy checks, organization API |
| `supabase/schema.sql` | Reviewed initial SQL; applied to the approved staging database |
| `supabase/tests` | PGlite tests and rollback-only hosted database checks |
| `scripts/provision-tenant.sql` | Explicit operator bootstrap; no public tenant creation |
| `docs/architecture/PHASE_1.md` | Scope, interface hierarchy and architecture |
| `docs/SETUP.md` | Environment setup, sign-in configuration and deployment gates |
| `docs/BACKEND_DEPLOYMENT.md` | Prepared Docker deployment using the approved staging host |
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

Open `http://localhost:5173`. With no provider settings, the login interface renders and the readiness/sign-in endpoints return an explicit configuration error. There is no authentication bypass or simulated workspace.

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

API tests use isolated provider responses. Database tests execute the real schema/policies/triggers in a PostgreSQL WebAssembly engine with a minimal test auth schema. These local suites do not establish hosted integration. Separately, rollback-only checks passed under actual staging database roles; see `docs/VERIFICATION.md`. Test records never seed the product.

## Deployment direction

Netlify serves the frontend. The public source defaults `/api/*` to an explicit unconfigured response so private backend origins are not committed. Configure the same-origin API proxy in the approved deployment target. The backend uses the approved staging provider project and runs as a non-root container with one worker. Read `docs/SETUP.md` before deploying; infrastructure changes, migrations and live provisioning require an approved target.

## SEO and public resources

The source build now includes static ERP planning resources at `/resources/`, plus draft blog articles. Run `npm run build` to generate them and `npm run test:seo` to check indexing boundaries. Indexing is disabled by default. `operis-staging.netlify.app` is staging-only; production indexing still requires a confirmed public marketing domain. The first safe conversion path is the discovery readiness checklist CTA, with no lead capture or scanner download in this release. See [SEO implementation and release requirements](docs/marketing/SEO_IMPLEMENTATION.md) before enabling production indexing or publishing articles. This source change is not a receipt for a live website deployment.
