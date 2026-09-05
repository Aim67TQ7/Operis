# Pete backend deployment

## Confirmed setup

The user selected their Hostinger VPS, Pete, for the FastAPI backend. Their Mac can now log in using its own SSH key. Direct SSH from the build workspace is unavailable, so server commands must currently run through the user's terminal. Do not copy the Mac's private SSH key into the repository or build workspace.

User-provided inspection established Docker Compose v5.3.1, a `hub-caddy` container running caddy-docker-proxy, and its attachment to the existing `hub-net` network. Caddy already owns public ports 80/443. An existing application is hosted at `hub.gp3.app`.

`deploy/pete/compose.yaml` defines only the Operis API, attached to that external network. It publishes no host ports and does not manage the existing Caddy or other application containers. Caddy discovers the new hostname and port 8000 through container labels. The runtime uses the existing non-root Dockerfile, a read-only filesystem with temporary space, bounded logs/resources, and a required ZODA publishable key. The Compose project name is `operis-staging`.

## DNS prerequisite

The user added `operis-api.gp3.app` in Netlify DNS pointing to Pete and verified HTTPS through Caddy. On 2026-09-05 at 18:16:30 UTC, the deployed readiness endpoint returned HTTP 200 with no-store headers after correcting the server's publishable key. This receipt comes from the user's terminal; the build workspace cannot independently resolve the hostname.

Check the hostname's A and AAAA records from the user's Mac. The A record should reach Pete; any AAAA record must also reach this server. Confirm that the hostname is unused before assigning it. DNS provider access and Caddy certificate issuance remain unverified. Do not alter the existing hub hostname or replace Caddy's configuration.

## Deploy after DNS and environment setup

Use a separate Operis checkout on Pete, on `build/phase-1-foundation` until PR #1 is merged. If that destination already contains a checkout, inspect its status before pulling. Do not overwrite another application directory.

From the Operis repository root on Pete, copy `deploy/pete/.env.example` to `deploy/pete/.env` only if the latter does not exist. Restrict it to the operator with mode 600. Populate:

- `OPERIS_RELEASE`: output of `git rev-parse HEAD` for this checkout.
- `OPERIS_API_HOSTNAME`: the confirmed DNS hostname, without scheme or path.
- `OPERIS_SUPABASE_PUBLISHABLE_KEY`: the existing ZODA publishable key, obtained from the project's API settings and entered on Pete. Keep it out of command history and shared terminal output.

The frontend origin, project URL and production cookie settings are already set by Compose. No database migration or tenant bootstrap runs during deployment.

Validate without printing interpolated environment values:

```bash
docker compose --env-file deploy/pete/.env -f deploy/pete/compose.yaml config --quiet
```

Build and start the Operis service only:

```bash
docker compose --env-file deploy/pete/.env -f deploy/pete/compose.yaml up -d --build --wait api
```

Check provider/schema readiness inside the running container:

```bash
docker compose --env-file deploy/pete/.env -f deploy/pete/compose.yaml exec -T api python -c 'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8000/api/health/ready", timeout=15); print(r.status, r.read().decode())'
```

Then verify both health endpoints through the actual HTTPS hostname. Successful container liveness alone does not establish Supabase readiness or Caddy routing. Record the source commit and image ID after success. The initial backend deployment has now been executed by the user on Pete; see the receipt below.

## Connect the frontend and finish acceptance

Only after HTTPS backend readiness succeeds, replace the placeholder Netlify `/api/*` rewrite with `https://CONFIRMED-HOSTNAME/api/:splat` using status 200, before the SPA fallback. Redeploy Netlify and verify Origin/cookie forwarding and no-store responses. Browser requests remain same-origin with Netlify.

Shared ZODA email-code compatibility, first organization/admin provisioning, authenticated HTTP isolation and browser acceptance remain separate gates in SETUP.md. The suggested administrator email is not yet a verified/provisioned membership. Do not modify shared Auth or seed a tenant as part of starting this container.

For an application rollback, retain the ZODA schema and point the Operis service at the previous retained image tag, then use `up -d --no-build --pull never api`. Do not rebuild the old tag from new source. To pause Operis, use this Compose file's `stop api`; do not stop the existing Caddy stack or prune shared Docker resources.

## Verification scope

The Compose YAML was parsed locally and reviewed against Docker/Caddy documentation. Docker is absent in the build workspace, so Compose interpolation, image build, resource limits, network discovery and HTTPS startup still require execution on Pete. Existing application source is unchanged by this deployment configuration.

References: [Caddy Docker Proxy](https://github.com/lucaslorentz/caddy-docker-proxy) and [Docker Compose services](https://docs.docker.com/reference/compose-file/services/).

## Initial backend receipt

The user built and started source commit `4db7de238ec797f09b6e29ac90912b6c0889e16a` on Pete. The built image is `operis-api:4db7de238ec797f09b6e29ac90912b6c0889e16a`, with reported image config digest `sha256:5410da337e81258138245d77534fb45598a81e5835eb716ca436a984bbc9c417`. Container `operis-staging-api-1` reports Healthy.

HTTPS liveness returned HTTP 200 via Caddy at 18:11:05 UTC. Initial readiness failed because the saved publishable key did not match ZODA and all three direct Supabase probes returned 401. The user entered the verified ZODA publishable key through a hidden prompt; the environment file was replaced atomically with mode 600 and only the Operis API container was recreated. HTTPS readiness then returned HTTP 200 at 18:16:30 UTC, with `Cache-Control: no-store` and request ID `4923919a-c625-47fd-9b98-c4f765e1b747`.

This verifies the backend's Auth-health and anonymous schema probe from Pete. It does not verify email delivery, user sessions or tenant membership. The original readiness failure was configuration-related; no shared Supabase keys or Auth settings were rotated or changed.
