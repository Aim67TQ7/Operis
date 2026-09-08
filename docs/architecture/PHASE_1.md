# Phase 1: Operis foundation

Status: first foundation slice implemented and tested; staging schema applied and staging frontend deployed. Backend hosting and end-to-end acceptance remain pending.

Operis foundation work is authorized, and discovery/rebuild of existing templates is deferred to Phase 2. This supersedes the seed's requirement to finish legacy-system discovery before construction. The destination is Aim67TQ7/Operis, initially one README on main.

## First slice

Existing, administrator-provisioned users sign in with an email code, select a tenant they belong to, maintain its company/site structure if authorized, and inspect the resulting audit history. No public signup, automatic entitlement, fabricated operational records, external connector execution, or scheduler is included.

## Interface wireframe

| Region | Contents / behavior |
| --- | --- |
| Left rail | Operis mark; Workspace, Organization, Connections, Activity; user and sign out |
| Top bar | Tenant selector; current role; refresh |
| Workspace | Real organization counts; setup checklist; recent changes |
| Organization | Tenant name; company table; site table; admin-only creation forms; member role list |
| Connections | Honest unconnected state and Phase 2 explanation; no simulated health |
| Activity | UTC time, actor, operation, record identity; expandable before/after evidence |
| Signed out | Email → code form; configuration / network failure visible |

Visual thesis: a quiet industrial workspace, dark navy rail, white working surface, precise dividers, restrained cobalt actions, compact tables. No decorative metrics or chat-first workflow.

## Boundaries

React + TypeScript on Vite uses same-origin `/api` requests. FastAPI holds the provider access token in an HttpOnly cookie and never returns tokens in JSON. It uses the user JWT for provider HTTP data calls, so row security remains active; no service-role key is needed by the web runtime. The identity provider verifies identity remotely on authenticated requests. Sessions deliberately require reauthentication after at most one hour; refresh-token persistence is deferred.

Postgres owns tenancy, organization structure, membership, and append-only audit events. Membership is read from the database, never user-editable JWT metadata. Tenant administrators may change organization structure. Operators/viewers have structural read access. Company/site restrictions for operational records are a Phase 2 contract, not a claim of implemented record-level permissions.

Tenant provisioning is an explicit operator SQL transaction, separate from customer authentication. Payment activation and entitlement verification must precede opening public onboarding. The first slice does not implement the commercial payment flow.

Deployment follows the seed: hosted frontend with a same-origin API proxy and Docker FastAPI service. Sites' default Worker/Vinext runtime is not adopted because it conflicts with the requested Vite/Python stack. The staging frontend and additive schema are provisioned; see ../STAGING.md.
