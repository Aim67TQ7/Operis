# OPERIS SEO Implementation

This public note describes the marketing-content foundation without publishing private deployment receipts, provider projects, hostnames, account identifiers, analytics accounts, or operator records.

## Scope

The source build includes static ERP planning resources at `/resources/`:

- Resource hub.
- Epicor planning guide.
- Infor SyteLine and CloudSuite Industrial planning guide.
- On-premises ERP planning guide.
- Discovery readiness checklist.
- Journal hub.
- Two draft articles.

The pages use unique titles, descriptions, canonical URLs, Open Graph metadata, semantic navigation, article microdata where applicable, and internal links. Draft articles stay out of production listings, sitemap, and RSS feed.

## Indexing Policy

Indexing is disabled by default. `operis-staging.netlify.app` is staging-only and must not be used as the production marketing canonical domain.

Production indexing requires:

- A confirmed public marketing domain.
- `SEO_INDEXABLE=true`.
- `SITE_URL` set to the confirmed HTTPS origin.
- A production deployment context.
- Representative HTTP/header and browser checks on the deployed site.

The build rejects staging, preview, non-HTTPS, path-bearing, credential-bearing, and mismatched origins when indexing is enabled.

## Conversion Policy

The first safe conversion path is the discovery readiness checklist CTA. This release does not include lead capture, CRM submission, payment activation, public customer signup, or a downloadable scanner.

## Claim Boundaries

The resource pages are educational planning content. They do not claim:

- Vendor affiliation or certification.
- Live connector availability.
- Scanner availability.
- Write-back support.
- Customer results, testimonials, rankings, or performance scores.
- Automatic blog publication.

## Release Checklist

Before enabling production indexing:

1. Confirm the public marketing domain.
2. Review article facts and publish dates.
3. Inspect desktop and mobile rendering in a real browser.
4. Verify canonical URLs, robots metadata, response headers, sitemap, RSS feed, and 404 behavior.
5. Configure Search Console and submit the sitemap.
6. Keep analytics privacy-safe and exclude ERP records, credentials, scan payloads, and form PII unless a reviewed policy explicitly allows it.

## References

- [Google: How Search works](https://developers.google.com/search/docs/fundamentals/how-search-works)
- [Google: AI-assisted content guidance](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content)
- [Google: AI features and websites](https://developers.google.com/search/docs/appearance/ai-features)
