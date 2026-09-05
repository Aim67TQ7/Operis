# Operis build sequence

## Phase 1 — platform foundation

This PR starts Phase 1, not all seed Gate 1 capabilities.

1. Repository, quality gates, application shell and backend health.
2. Verified-user email code login, cookie session, tenant membership and RLS.
3. Company/site creation and tenant naming with atomic audit evidence.
4. Select dedicated development/staging Supabase project, SMTP, frontend origin and backend host.
5. Generate/review migration from schema.sql using a functioning Supabase CLI; apply only to the approved environment. Run live advisors and the full Supabase integration test gate.
6. Verify sign-in delivery, cookies behind the proxy, tenant isolation, unauthorized paths and organization creation in staging. Exercise actual browser flows at desktop/mobile sizes.
7. Complete controlled activation/payment, invitation/admin lifecycle, secret storage and connector registration as further Phase 1 slices before external customer onboarding.

Exit gate for this foundation: test suites and build pass, staging flow accepted, deployment health verified, configuration and rollback ownership documented. Gate 1 from the original seed remains incomplete until connector registration and remaining foundation controls exist.

## Phase 2 — existing builds and operational modules

Inspect the Lovable projects and their linked code/data sources. Determine which are active and reusable; screenshots establish names only. Discover legacy Supabase and operational integrations with read-only access.

Define the module manifest and bounded company/site/domain permissions using verified module requirements. Choose one module, implement real connector ingestion and canonical mappings, then deliver its exception/evidence workflow in shadow mode. Do not manufacture connector success or sample operational records for production UI.

Complete the seed's twelve discovery/architecture/roadmap deliverables as evidence becomes available. Proposed first domain remains PO/AP lifecycle pending source inspection and operational priority.

## Later production gates

Write-enabled actions need separate authorization, strict session revocation checks, action-specific policy, idempotency, approvals, before/after evidence and reconciliation. Model execution and schedules stay absent until deterministic execution controls and observability are proven. Extract reusable module templates only after a first tenant proves the contracts.

## Rollback

Before production release, record immutable frontend/backend version identifiers and a verified database backup. Revert to the preceding application image and frontend release for code failures. Keep additive schema and audit history in place; do not drop tenant tables to roll back an app. Stop writes during investigation; repair schema forward through a reviewed migration. Destructive teardown is for an explicitly disposable development project only and is not automated here.
