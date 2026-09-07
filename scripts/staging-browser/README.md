# Temporary browser acceptance harness

These files are operator test assets, excluded from the normal Vite build. They
use the same-origin `/api` and the signed-in browser's existing HttpOnly cookie.
There is no new backend endpoint, authentication bypass, token export, credential
form, service-role credential, or change to shared Supabase Auth.

One approved verified account is sufficient for the FastAPI cases: it can be an
administrator in Operis, a viewer in an isolated `Operis PR1 QA Viewer` tenant,
and have no membership in a separate isolated private fixture tenant. Fixture
creation remains an explicit approved operator action. Use synthetic company
records in the QA tenants; preserve the real Operis membership. Fixture IDs and
account identifiers do not belong in the source or public evidence.

After a normal build, copy these HTML/JS/CSS files into `dist/__qa/`, deploy to
the existing approved staging site with its existing Netlify configuration, and
open `/__qa/pr1.html` in the same browser as the authenticated Operis session.
Enter the approved fixture identifiers and run the checks. The report contains
only check labels, status codes and request correlation IDs. It never displays
response bodies, JWTs or cookie/storage values.

The checks cover:

- Admin and viewer workspace access, and private-tenant invisibility.
- Viewer rename/company/site writes return 403; private-tenant reads/writes 404.
- An administrator cannot attach a private tenant's company to an own-tenant site.
- Denied requests leave the viewer's workspace and audit response unchanged.
- Response JSON has no access/refresh/id tokens; HttpOnly session/PKCE cookies
  are not JavaScript-visible; localStorage and sessionStorage are empty.
- After the operator removes only the temporary QA viewer membership, the
  separate removal check expects immediate 404 and absence from `/api/me`.

Inspect main-app tenant switching, viewer-only forms and lost-access behavior
separately. The page does not establish direct PostgREST HTTP denial, production
backup/restore, or expiry/replay of a delivered email link. Local DB role tests
and the credential-prompted `scripts/verify-staging.py` cover separate layers.

After collecting evidence, remove only `dist/__qa/` and redeploy the normal
staging build. Keep the audited fixture records; revoke temporary membership
as approved. Do not put this page into the ordinary build or leave it enabled
as a product feature. A passed report does not itself mark the PR ready.
