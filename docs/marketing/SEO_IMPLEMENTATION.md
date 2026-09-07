# OPERIS SEO implementation — September 6, 2026

## Scope and verified starting point

Source branch: `build/phase-1-foundation`, starting commit `258f96d724963bb8ae2a52d8e2a9396ac4ac902d` in Aim67TQ7/Operis. Main remains a README shell. Existing source has a JavaScript-rendered organization workspace with generic workspace metadata, no resource pages, and no sitemap or robots file. Those are source findings, not a completed audit of Google's index.

Netlify reports staging deploy `6a9c7086b96cca868f567eec`, uploaded September 5, 2026, with no commit ref or repository binding. Source-to-deploy parity is unverified. The public web fetch did not return usable site HTML. No Search Console, Analytics, Ads, or keyword-volume account was inspected. No production domain is established in the inspected configuration.

## Implemented

- Eight static HTML resource routes: resource hub, Epicor guide, SyteLine guide, on-premises guide, discovery readiness checklist, journal hub, and two draft articles.
- Unique titles, descriptions, canonical URLs, Open Graph and summary-card metadata.
- Semantic navigation, one H1 per resource page, mobile CSS, keyboard focus styles, and meaningful internal links.
- BlogPosting/Organization microdata for articles. Uses visible byline content and no invented expert or customer evidence. Published dates appear only for released articles.
- Generated XML sitemap and RSS feed. Draft and future-dated articles are excluded; production hub listings exclude drafts.
- Indexing disabled by default in HTML and response-header output. Crawl access remains available so crawlers can read noindex.
- Workspace remains at its existing routes and has explicit noindex metadata. A sign-in page link exposes the resource hub.
- Resource paths that have no static file return a 404 through Netlify before the existing SPA fallback. Existing API proxy preserved.
- No paid capture form, tracking pixel, public scanner download, fabricated testimonials, or invented connector status.

## Configuration and publishing

`npm run build` generates the app and resource pages. To inspect all draft pages, serve `dist` locally. The ordinary Vite development server does not generate the resource routes.

Production indexing requires both `SEO_INDEXABLE=true` and `SITE_URL=https://<confirmed-public-origin>`. The build rejects staging/preview origins, non-production Netlify contexts, URLs containing credentials, and mismatches with Netlify's `URL`. SITE_URL is an origin, not a path. On a staging or preview environment keep SEO_INDEXABLE unset or false. Canonicals on preview builds may point to the chosen public origin while noindex remains enabled.

Edit authored content in `content/pages.json`. Articles start with `status: draft`. After factual and editorial review, set `status: published` and an actual release date. The deployment build controls when content changes go live. A daily draft automation is not a CMS or automatic website publisher. Its output must be reviewed and incorporated into content before a build.

The existing CSP continues to prohibit inline executable scripts; the resource HTML contains no JavaScript and structured data is microdata. Real image assets and social preview imagery can be added after a brand asset is selected. No fake rich-result reviews or FAQs are added.

## Remaining launch work

1. Confirm the authoritative public marketing domain and reconcile this branch with the uploaded website. Preserve any newer discovery/marketing work before merging. Do not replace a separately maintained marketing site with the older workspace source.
2. Decide the public homepage routing while preserving workspace and callback routes. This change deliberately adds `/resources/`; it is not a homepage replacement.
3. Review the two articles, validate product claims against the latest build, and confirm SyteLine is the intended product.
4. Add a real lead conversion destination tied to the selected commercial offer. The current CTA reaches an actual readiness checklist; it does not collect a lead.
5. Deploy the reviewed code to the verified target. Inspect real HTTP status, headers, canonical host, mobile layout, redirects, and sitemap entries.
6. Verify domain ownership in Search Console, submit the sitemap, and inspect representative URLs. Record index coverage and query baselines. Metadata does not guarantee indexing or ranking.
7. Implement privacy-appropriate analytics and verified server/CRM qualification events before buying traffic. Do not send ERP records, scan payloads, credential data, or form PII into analytics.
8. Measure page speed and accessibility on the actual deployment. Avoid inventing performance scores from a successful build.

## References

- [Google: How Search works](https://developers.google.com/search/docs/fundamentals/how-search-works)
- [Google: AI-assisted content guidance](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content)
- [Google: AI features and websites](https://developers.google.com/search/docs/appearance/ai-features)
