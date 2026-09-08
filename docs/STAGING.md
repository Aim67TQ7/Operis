# Operis Staging Receipt

This public receipt records only release-relevant status. Exact provider projects, deployment IDs, hostnames, account identifiers, request IDs, credentials, and operator records are intentionally omitted.

## Staging Status

| Area | Public status |
| --- | --- |
| Frontend | Staging origin exists at [operis-staging.netlify.app](https://operis-staging.netlify.app) |
| Database | Additive Operis foundation schema applied to the approved staging provider |
| Backend | Containerized API reached HTTPS liveness and readiness in staging |
| API routing | Live routing is deployment-specific; private backend origins are not committed |
| Sign-in | Real browser sign-in and session acceptance remain release gates |

## Boundaries

The foundation schema is additive and limited to Operis-owned objects. Shared provider settings, unrelated schemas, legacy records, and identity-provider configuration must be preserved.

The public source defaults `/api/*` to an explicit unconfigured response. The staging deployment may override that privately with the approved API origin.

Do not rerun initial provisioning without inspecting the private deployment record. Do not publish account identifiers, provider project identifiers, customer records, or operational receipts in this repository.

## Remaining Setup

1. Verify live sign-in, session cookies, persistence, tenant isolation, and browser acceptance.
2. Keep production indexing disabled until the public marketing domain is confirmed.
3. Keep the first marketing conversion path as the readiness checklist CTA until a real lead-capture destination is approved.
4. Record backup, rollback, incident, and support ownership privately before accepting operational writes.
