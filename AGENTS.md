# Operis engineering

Read README.md, docs/DECISIONS.md, docs/architecture/PHASE_1.md and docs/roadmap/BUILD_SEQUENCE.md before changes. Inspect git status and preserve unrelated work.

The approved stack is Vite/React/TypeScript, Python/FastAPI, Supabase/Postgres with RLS, Netlify frontend and Docker backend. Prefer a modular monolith. Legacy Lovable module discovery/rebuild is Phase 2.

Keep authentication tokens out of browser-accessible storage and response JSON. Use HttpOnly secure cookies in production, same-origin API routing, and server-side authorization. Application data requests use the user's JWT so database RLS applies. No service-role key in the web runtime. Keep connector credentials, customer data, uploaded documents and secrets out of this public repository.

Never equate successful authentication with tenant access. Test cross-tenant access, viewer writes, membership escalation and audit tampering when touching authorization or schemas. Use composite tenant-scoped relationships. Audit mutations in the same database transaction.

Run npm run build, npm run test:web, npm run test:db and the API lint/tests for relevant changes. Preserve lockfiles. Keep docs/VERIFICATION.md honest about checks actually run and live integration gaps. Do not describe mocks or planned connectors as working integrations.

Do not apply migrations, provision infrastructure, modify production data or deploy without an approved target and authorization. Source implementation can proceed independently of live deployment. Public onboarding must not bypass server-verified activation/payment policy. Operational writes and agents require their own bounded execution and approval controls.
