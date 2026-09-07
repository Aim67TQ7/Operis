"""Explicit, credential-prompted acceptance against the approved staging target.

Run with apps/api/.venv/bin/python scripts/verify-staging.py --write-fixtures.
Creates one labeled company/site; retains their immutable audit evidence. Requires
an existing admin and viewer in the target, with the viewer a member of a second
tenant invisible to the admin. Never provisions accounts or modifies shared Auth.
"""

import argparse
import getpass
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx

ORIGIN = "https://operis-staging.netlify.app"
SUPABASE = "https://ezlmmegowggujpcnzoda.supabase.co"
COOKIE = "__Host-operis_session"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-fixtures",
        action="store_true",
        help="Create and retain one acceptance company/site in the selected staging tenant",
    )
    args = parser.parse_args()
    if not args.write_fixtures:
        parser.error(
            "This acceptance run writes labeled staging fixtures; explicitly pass --write-fixtures."
        )
    results = []

    def check(label, condition):
        if not condition:
            raise RuntimeError(label)
        results.append({"check": label, "result": "passed"})

    def request(client, method, path, expected=200, body=None):
        r = client.request(method, path, json=body)
        # Never include response bodies, identities, credentials or URLs in errors.
        check(f"{method} request status {expected}", r.status_code == expected)
        check(
            "API response is not cached", r.headers.get("cache-control") == "no-store"
        )
        check("API request correlation is present", bool(r.headers.get("x-request-id")))
        return r

    def signin(client, label):
        email = input(f"{label} email (existing approved account): ").strip()
        password = getpass.getpass(f"{label} password (hidden): ")
        r = request(
            client,
            "POST",
            "/api/auth/password",
            body={"email": email, "password": password},
        )
        del password
        check("Sign-in JSON contains no tokens", r.json() == {"authenticated": True})
        cookie = next(c for c in client.cookies.jar if c.name == COOKIE)
        check(
            "Session cookie flags",
            cookie.secure
            and cookie.path == "/"
            and not cookie.domain_specified
            and cookie.has_nonstandard_attr("HttpOnly")
            and cookie.get_nonstandard_attr("SameSite") == "strict",
        )
        return request(client, "GET", "/api/me").json()

    clients = [
        httpx.Client(
            base_url=ORIGIN,
            headers={"Origin": ORIGIN, "Content-Type": "application/json"},
            timeout=20,
            follow_redirects=False,
        )
        for _ in range(2)
    ]
    admin, viewer = clients
    failure = None
    try:
        a = signin(admin, "Administrator")
        v = signin(viewer, "Viewer")
        targets = [
            t
            for t in a["tenants"]
            if t["role"] == "admin"
            and any(u["id"] == t["id"] and u["role"] == "viewer" for u in v["tenants"])
        ]
        foreign = [
            t for t in v["tenants"] if t["id"] not in {u["id"] for u in a["tenants"]}
        ]
        check(
            "Approved two-tenant admin/viewer fixture exists",
            len(targets) == 1 and len(foreign) >= 1,
        )
        tenant, other = targets[0]["id"], foreign[0]["id"]
        prefix = f"/api/tenants/{tenant}"
        other_prefix = f"/api/tenants/{other}"
        request(viewer, "GET", prefix + "/workspace")
        request(viewer, "GET", other_prefix + "/workspace")
        request(admin, "GET", other_prefix + "/workspace", 404)
        code = "PR1-" + uuid4().hex[:12]
        company_r = request(
            admin,
            "POST",
            prefix + "/companies",
            201,
            {"code": code, "name": "PR1 acceptance company " + code},
        )
        company = company_r.json()
        site_r = request(
            admin,
            "POST",
            prefix + "/sites",
            201,
            {
                "company_id": company["id"],
                "code": code,
                "name": "PR1 acceptance site " + code,
            },
        )
        site = site_r.json()
        # Fresh client proves a new request reads committed server state.
        with httpx.Client(base_url=ORIGIN, cookies=admin.cookies, timeout=20) as fresh:
            state = request(fresh, "GET", prefix + "/workspace").json()
        check(
            "Company persists across clients",
            any(
                c["id"] == company["id"] and c["code"] == code
                for c in state["companies"]
            ),
        )
        check(
            "Site persists with its company",
            any(
                s["id"] == site["id"] and s["company_id"] == company["id"]
                for s in state["sites"]
            ),
        )
        for row, response, table in [
            (company, company_r, "operis_companies"),
            (site, site_r, "operis_sites"),
        ]:
            events = [
                e
                for e in state["audit_events"]
                if e["record_id"] == row["id"] and e["table_name"] == table
            ]
            check(table + " has one atomic INSERT event", len(events) == 1)
            event = events[0]
            check(
                table + " audit actor/before/after/request",
                event["actor_id"] == a["user"]["id"]
                and event["action"] == "INSERT"
                and event["before"] is None
                and event["after"] == row
                and event["request_id"] == response.headers["x-request-id"]
                and bool(event["created_at"]),
            )
        before = state
        for client, path, status in [(viewer, prefix, 403), (admin, other_prefix, 404)]:
            for method, suffix, payload in [
                ("PATCH", "", {"name": "Denied PR1 rename"}),
                ("POST", "/companies", {"code": code, "name": "Denied PR1 company"}),
                (
                    "POST",
                    "/sites",
                    {
                        "code": code,
                        "name": "Denied PR1 site",
                        "company_id": company["id"],
                    },
                ),
            ]:
                request(client, method, path + suffix, status, payload)
        check(
            "Denied writes leave target and audit unchanged",
            request(admin, "GET", prefix + "/workspace").json() == before,
        )
        # The publishable key is public, but do not echo any credential input.
        key = getpass.getpass(
            "ZODA publishable key (hidden; never a service-role key): "
        )
        check("Modern publishable key required", key.startswith("sb_publishable_"))
        for client, user, is_viewer in [(admin, a, False), (viewer, v, True)]:
            token = client.cookies.get(COOKIE)
            with httpx.Client(
                base_url=SUPABASE,
                headers={
                    "apikey": key,
                    "Authorization": "Bearer " + token,
                    "Prefer": "return=representation",
                },
                timeout=20,
            ) as db:
                if not is_viewer:
                    for table, field in [
                        ("operis_tenants", "id"),
                        ("operis_companies", "tenant_id"),
                        ("operis_sites", "tenant_id"),
                        ("operis_audit_events", "tenant_id"),
                    ]:
                        r = db.get(
                            "/rest/v1/" + table,
                            params={field: "eq." + other, "select": "*"},
                        )
                        check(
                            "Direct PostgREST cross-tenant " + table,
                            r.status_code == 200 and r.json() == [],
                        )
                denied_tenant = tenant if is_viewer else other
                for table, payload in [
                    (
                        "operis_companies",
                        {"tenant_id": denied_tenant, "code": code, "name": "Denied"},
                    ),
                    (
                        "operis_sites",
                        {
                            "tenant_id": denied_tenant,
                            "company_id": company["id"],
                            "code": code,
                            "name": "Denied",
                        },
                    ),
                    (
                        "operis_audit_events",
                        {
                            "tenant_id": denied_tenant,
                            "action": "INSERT",
                            "table_name": "forged",
                            "record_id": "forged",
                        },
                    ),
                ]:
                    check(
                        "Direct PostgREST denies " + table + " write",
                        db.post("/rest/v1/" + table, json=payload).status_code == 403,
                    )
                for method in ["PATCH", "DELETE"]:
                    r = db.request(
                        method,
                        "/rest/v1/operis_audit_events",
                        params={"record_id": "eq." + site["id"]},
                        json={"action": "DELETE"} if method == "PATCH" else None,
                    )
                    check("Direct audit immutability " + method, r.status_code == 403)
                if is_viewer:
                    r = db.patch(
                        "/rest/v1/operis_memberships",
                        params={
                            "tenant_id": "eq." + tenant,
                            "user_id": "eq." + user["user"]["id"],
                        },
                        json={"role": "admin"},
                    )
                    check(
                        "Direct membership self-escalation denied", r.status_code == 403
                    )
        # No email delivery is initiated. A missing verifier cannot exchange a link.
        with httpx.Client(base_url=ORIGIN, timeout=20) as signed_out:
            request(
                signed_out, "GET", "/api/auth/callback?code=expired-pr1-fixture", 400
            )
            request(signed_out, "GET", "/api/me", 401)
    except (RuntimeError, httpx.HTTPError, KeyError, StopIteration) as exc:
        failure = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
    finally:
        for client in clients:
            try:
                r = request(client, "POST", "/api/auth/logout", body={})
                check("Logout clears browser session", not client.cookies.get(COOKIE))
                check(
                    "Logout clears pending verifier",
                    not client.cookies.get("__Host-operis_pkce"),
                )
                request(client, "GET", "/api/me", 401)
                if r.json().get("provider_revoked") is False:
                    failure = failure or "Provider logout could not be confirmed"
            except (RuntimeError, httpx.HTTPError):
                failure = failure or "Logout verification failed"
            client.close()
    print(
        json.dumps(
            {
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "target": ORIGIN,
                "result": "failed" if failure else "passed",
                "failure": failure,
                "checks": results,
                "scope": "Live HTTP only; browser, delivered expired-link and membership-removal acceptance remain separate.",
            },
            indent=2,
        )
    )
    raise SystemExit(1 if failure else 0)


if __name__ == "__main__":
    main()
