# Backend Deployment

This public repository contains a deployment template only. Private hostnames, provider URLs, network names, credentials, deployment receipts, and operator-specific commands belong in a private runbook.

## Template

`deploy/staging/compose.yaml` defines the Operis API service and expects deployment-owned values from `deploy/staging/.env`.

Required values:

- `OPERIS_RELEASE`: exact reviewed source commit for the image tag.
- `OPERIS_API_HOSTNAME`: approved API hostname, stored outside source.
- `OPERIS_SUPABASE_URL`: approved provider project URL, stored outside source.
- `OPERIS_SUPABASE_PUBLISHABLE_KEY`: publishable key only; never a service-role key.
- `OPERIS_INGRESS_NETWORK`: approved reverse-proxy network name, stored outside source.

## Safety Rules

- Do not commit `.env` files, hostnames, provider URLs, keys, database passwords, SSH keys, or customer data.
- Do not run migrations, tenant provisioning, connector registration, or operational writes as part of starting the container.
- Keep the API behind HTTPS and preserve Cookie, Set-Cookie, Content-Type, and Origin headers through the proxy.
- Keep authenticated API responses uncached.
- Record deployment receipts, image IDs, request IDs, DNS checks, and rollback targets privately.

Successful container health does not prove real email delivery, browser sign-in, tenant membership, or operational readiness.
