# Open questions

These do not block source implementation. Do not reopen Lovable discovery as a Phase 1 prerequisite.

| Question | Why it matters | Default until answered | Decision deadline |
| --- | --- | --- | --- |
| Which dedicated Supabase development/staging project should host Operis? | Determines the authorized schema and identity target | No live project selected or changed | Before first migration/provisioning |
| What frontend origin and Docker backend host should be used? | Cookie, Origin and same-origin proxy configuration | Local development only | Before staging deployment |
| Who is the first organization administrator and what is the initial organization name? | Explicit bootstrap ownership | No seeded customer or admin | Before tenant provisioning |
| Which SMTP service and session/SSO policy should the initial release use? | Enables real code delivery and identity rollout | Existing-user email OTP; reauthentication at expiry; no SSO claims | Before staging sign-in acceptance |
| What payment and activation implementation is approved? | Required before external customer signup | Operator-only tenant creation, no payment entitlement implied | Before commercial onboarding |
| Which Lovable projects are authoritative and actively used? | Sets module extraction and requirements | Screenshots establish project names only | Phase 2 discovery |
