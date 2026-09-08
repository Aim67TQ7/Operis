# Architecture decisions

Public decision record for the foundation source. Private operator names, host identifiers and provider project details are intentionally omitted.

| Date | Decision | Status | Public consequence |
| --- | --- | --- | --- |
| 2026-09-05 | Start new Operis foundation; move existing template discovery/rebuild to Phase 2 | Approved | Legacy access is no longer a prerequisite for this slice |
| 2026-09-05 | Retain Vite, React, TypeScript, Python/FastAPI, provider-backed Postgres, hosted frontend and Docker direction | Accepted | No alternate Worker backend or frontend framework in this foundation |
| 2026-09-05 | Modular monolith, same-origin API, row security enforced with caller JWT | Implemented; deployment-gated | No service-role credential in runtime; proxy must preserve cookies and Origin |
| 2026-09-05 | Email-code sign-in for already provisioned verified users; no public signup | Implemented; deployment-gated | Requires provider email configuration and explicit first-admin provisioning |
| 2026-09-05 | Short sessions with no refresh persistence | Implemented | Reauthentication at token expiry; stricter revocation checks required before operational actions |
| 2026-09-05 | Membership administration and initial tenant creation remain operator-only | Implemented | Users cannot grant themselves access; no payment verification implied |
| 2026-09-05 | No unapproved live infrastructure or legacy database changes in foundation source | Boundary | Schema, deployment files and setup are reviewable before live changes |
| 2026-09-05 | Use an approved shared provider project for staging | Applied | Additive Operis-only objects; preserve shared provider settings and legacy data |
| 2026-09-05 | Host the Docker FastAPI backend on an approved staging host | Prepared | Runtime acceptance, DNS and browser flow validation remain gates |
| 2026-09-05 | Keep private backend origins out of public source | Applied | Public Netlify config defaults to an explicit unconfigured API response |
| 2026-09-05 | Provision the first organization through an operator-controlled transaction | Applied | Account identifiers are excluded from public source |
| 2026-09-05 | Use PKCE magic links with server-side exchange and browser-bound verifier | Implemented; deployment-gated | Real email callback testing remains required before acceptance |
