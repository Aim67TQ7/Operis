# Foundation Verification

This public file records verification scope without publishing private provider projects, hostnames, deployment IDs, account identifiers, request IDs, credentials, or operator receipts.

## Local Checks

| Check | Result | Scope |
| --- | --- | --- |
| `npm run build` | Passed in prior CI/hosted validation | TypeScript compilation, Vite production bundle, static resource generation |
| `npm run test:web` | Passed in prior validation | Sign-in UI, cookie request mode, organization workflow states |
| `npm run test:db` | Passed in prior validation | Row security, tenant-scoped writes/reads, audit immutability |
| API tests | Passed in prior validation | Authorization, CSRF Origin checks, cookie flags, provider errors, rate limits, logout and health behavior |
| `npm run test:seo` | Passed locally on 2026-09-08 | Indexing guardrails, static HTML, draft exclusion, sitemap/feed behavior |
| `git diff --check` | Passed locally on 2026-09-08 | No whitespace errors |

Local tests use isolated provider responses and synthetic records. They do not establish hosted integration, email delivery, live identity-provider compatibility, or production readiness.

## Hosted Staging Scope

Staging checks previously established:

- Additive foundation schema applied to the approved staging database.
- Rollback-only row-security checks passed under staging database roles.
- API liveness and readiness returned HTTP 200 in the approved staging environment.
- Unauthenticated API access denial, input validation, Origin rejection, and no-store behavior were observed.

Private deployment receipts are intentionally excluded from public source.

## Not Verified Publicly

- Real browser sign-in, session persistence, and Set-Cookie forwarding.
- Full provider Auth/API integration through the deployed proxy.
- Desktop/mobile browser layout and keyboard acceptance.
- Production domain ownership, Search Console, sitemap submission, indexing, ranking, analytics, or paid-traffic tracking.
- Backup/restore, rollback ownership, incident ownership, and support ownership.

## SEO and Content Foundation

The branch adds eight static resource pages, metadata, sitemap/RSS generation, and draft article handling. Indexing is disabled by default. Draft articles remain out of production listings, sitemap, and feed.

The 2026-09-08 follow-up records these release decisions:

- `operis-staging.netlify.app` is staging-only.
- First conversion path is checklist CTA only, with no lead capture or public scanner download.
- Public SyteLine pages should target both Infor SyteLine and CloudSuite Industrial.

Browser/mobile QA remains a release gate in a browser-capable deployment environment.
