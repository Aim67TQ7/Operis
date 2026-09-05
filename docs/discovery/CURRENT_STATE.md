# Current state — scoped foundation baseline

## Verified

- GitHub destination is Aim67TQ7/Operis, public, default branch main. Initial inspected commit: c0b7cf6bf3db4b1fe0605c36cc4a331525fbbded; README.md was the sole tracked file, containing `# Operis`. GitHub contents, branches and commits APIs plus a local clone establish this baseline.
- The local clone began clean. No pre-existing AGENTS.md, application, architecture documents, dependency manifests, migrations, tests or deployment configuration existed.
- This PR adds apps/web (React interface), apps/api (FastAPI identity and organization service), supabase/schema.sql (RLS/audit schema), executable tests, CI, deployment configuration and setup documentation. Exact dependency versions and transitive hashes live in package-lock.json and apps/api/uv.lock.
- The user moved Lovable discovery and template rebuilds to Phase 2 and authorized starting this foundation.

## Inferred

The screenshots show multiple recently edited builds that may map to future operational modules. Activity timestamps and names do not establish operational use, favorites, data lineage or implementation status.

## Proposed

Architecture and first release policies are in ../architecture/PHASE_1.md and ../DECISIONS.md. The first implemented user journey is a provisioned user's organization workspace, not the seed's later real-connector vertical slice.

## Blocked / deferred

- Update 2026-09-05: user selected shared ZODA for staging; additive schema applied and Netlify frontend deployed. Docker host, shared Auth compatibility and first-admin identity remain unresolved. See ../STAGING.md.
- Existing Lovable source, legacy schemas, ERP integrations and deployed behavior remain uninspected and are intentionally Phase 2 work.
- Docker and psql were unavailable in this build environment. Supabase CLI setup encountered a cancelled network approval; no live schema mutation or migration history operation was attempted. The schema is a reviewed SQL source, not a fabricated CLI migration.
- Full Supabase-stack integration, container execution, live sign-in and browser/deployment acceptance remain release gates. Local PGlite tests verify SQL behavior but do not replace these gates.

This is not the complete legacy discovery package required by the original seed. It records the evidence relevant to the user-approved foundation scope.
