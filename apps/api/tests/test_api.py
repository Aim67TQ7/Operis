import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from operis.config import Settings
from operis.gateway import Gateway
from operis.main import create_app

TENANT = "10000000-0000-0000-0000-000000000001"
USER = "20000000-0000-0000-0000-000000000001"
HEADERS = {"Origin": "https://operis.example"}


@pytest.fixture
def harness():
    settings = Settings(
        environment="production",
        app_origin="https://operis.example",
        supabase_url="https://identity.example",
        supabase_publishable_key="public-test-key",
    )
    calls = []
    behavior = {"role": "admin", "member": True, "failure": None}

    def handler(request):
        calls.append(request)
        if behavior["failure"]:
            return httpx.Response(behavior["failure"], json={"error": "sensitive-upstream-detail"})
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(
                200,
                json={"id": USER, "email": "admin@example.com", "email_confirmed_at": "2026-01-01T00:00:00Z"},
            )
        if path in {"/auth/v1/verify", "/auth/v1/token"}:
            return httpx.Response(
                200,
                json={
                    "access_token": "private-test-access-token",
                    "refresh_token": "private-test-refresh-token",
                    "expires_in": 3600,
                },
            )
        if path.startswith("/auth/"):
            return httpx.Response(200, json={})
        if path.endswith("operis_memberships"):
            return httpx.Response(
                200,
                json=[{"tenant_id": TENANT, "user_id": USER, "role": behavior["role"]}]
                if behavior["member"]
                else [],
            )
        if request.method in ("POST", "PATCH"):
            return httpx.Response(201, json=[{"id": str(uuid4()), **json.loads(request.content)}])
        if path.endswith("operis_tenants"):
            return httpx.Response(200, json=[{"id": TENANT, "name": "Test organization"}])
        return httpx.Response(200, json=[])

    app = create_app(settings)
    with TestClient(app, base_url="https://operis.example") as client:
        transport_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        app.state.gateway = Gateway(settings, transport_client)
        client.cookies.set(settings.cookie_name, "user-access-token")
        yield client, calls, behavior
        client.portal.call(transport_client.aclose)


def test_live_and_unconfigured_readiness():
    with TestClient(create_app(Settings(environment="test"))) as client:
        assert client.get("/api/health/live").status_code == 200
        assert client.get("/api/health/ready").status_code == 503


def test_missing_cookie_denies_access(harness):
    client, calls, _ = harness
    client.cookies.clear()
    assert client.get("/api/me").status_code == 401
    assert calls == []


def test_cross_origin_and_missing_origin_rejected_before_auth(harness):
    client, calls, _ = harness
    for origin in [{}, {"Origin": "https://hostile.example"}]:
        assert (
            client.post("/api/auth/code", json={"email": "admin@example.com"}, headers=origin).status_code
            == 403
        )
    assert calls == []


def test_tokens_never_returned_to_javascript_and_cookie_is_secure(harness):
    client, _, _ = harness
    response = client.post(
        "/api/auth/verify", json={"email": "admin@example.com", "code": "123456"}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "__Host-operis_session=" in cookie
    assert "refresh" not in cookie and "token" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_signin_cannot_create_users(harness):
    client, calls, _ = harness
    assert (
        client.post("/api/auth/code", json={"email": "admin@example.com"}, headers=HEADERS).status_code == 202
    )
    assert json.loads(calls[-1].content)["create_user"] is False


def test_invalid_input_does_not_echo_code_or_email(harness):
    client, calls, _ = harness
    response = client.post(
        "/api/auth/verify", json={"email": "private@example.com", "code": "private-secret"}, headers=HEADERS
    )
    assert response.status_code == 422
    assert "private" not in response.text
    assert calls == []


def test_nonmember_blocked_before_data_request(harness):
    client, calls, behavior = harness
    behavior["member"] = False
    response = client.get(f"/api/tenants/{TENANT}/workspace")
    assert response.status_code == 404
    assert len(calls) == 2


def test_viewer_cannot_create_company(harness):
    client, calls, behavior = harness
    behavior["role"] = "viewer"
    response = client.post(
        f"/api/tenants/{TENANT}/companies", json={"code": "ACME", "name": "Company"}, headers=HEADERS
    )
    assert response.status_code == 403
    assert all(r.method == "GET" for r in calls)


def test_company_write_is_scoped_correlated_and_user_authenticated(harness):
    client, calls, _ = harness
    response = client.post(
        f"/api/tenants/{TENANT}/companies", json={"code": "ACME", "name": "Company"}, headers=HEADERS
    )
    assert response.status_code == 201
    request = calls[-1]
    assert json.loads(request.content)["tenant_id"] == TENANT
    assert request.headers["authorization"] == "Bearer user-access-token"
    assert request.headers["x-request-id"] == response.headers["x-request-id"]


def test_client_cannot_override_tenant(harness):
    client, calls, _ = harness
    response = client.post(
        f"/api/tenants/{TENANT}/companies",
        json={"code": "ACME", "name": "Company", "tenant_id": str(uuid4())},
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert all(r.method == "GET" for r in calls)


def test_site_must_belong_to_visible_company(harness):
    client, calls, _ = harness
    response = client.post(
        f"/api/tenants/{TENANT}/sites",
        json={"code": "SITE", "name": "Facility", "company_id": str(uuid4())},
        headers=HEADERS,
    )
    assert response.status_code == 404
    assert all(r.method == "GET" for r in calls)


def test_upstream_error_redacted(harness):
    client, _, behavior = harness
    behavior["failure"] = 500
    response = client.get("/api/me")
    assert response.status_code == 503
    assert "sensitive" not in response.text


def test_invalid_session_is_not_accepted(harness):
    client, _, behavior = harness
    behavior["failure"] = 401
    assert client.get("/api/me").status_code == 401


def test_logout_revokes_provider_session_and_clears_cookie(harness):
    client, calls, _ = harness
    response = client.post("/api/auth/logout", json={}, headers=HEADERS)
    assert response.status_code == 200
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert calls[-1].url.path == "/auth/v1/logout"
    assert calls[-1].url.params["scope"] == "local"


def test_verification_attempts_are_bounded(harness):
    client, _, _ = harness
    for _ in range(10):
        client.post(
            "/api/auth/verify", json={"email": "admin@example.com", "code": "123456"}, headers=HEADERS
        )
    assert (
        client.post(
            "/api/auth/verify", json={"email": "admin@example.com", "code": "123456"}, headers=HEADERS
        ).status_code
        == 429
    )


def test_production_fails_closed_without_configuration():
    with pytest.raises(ValueError):
        Settings(environment="production")


def test_html_form_post_is_rejected(harness):
    client, calls, _ = harness
    assert (
        client.post("/api/auth/code", data={"email": "admin@example.com"}, headers=HEADERS).status_code == 415
    )
    assert calls == []


def test_magic_link_is_browser_bound_and_server_exchanged(harness):
    import base64
    import hashlib

    client, calls, _ = harness
    client.cookies.clear()
    sent = client.post("/api/auth/code", json={"email": "admin@example.com"}, headers=HEADERS)
    verifier = client.cookies.get("__Host-operis_pkce")
    payload = json.loads(calls[-1].content)
    assert payload["code_challenge"] == base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    assert payload["code_challenge_method"] == "s256"
    assert calls[-1].url.params["redirect_to"] == "https://operis.example/api/auth/callback"
    assert "HttpOnly" in sent.headers["set-cookie"] and "SameSite=lax" in sent.headers["set-cookie"]
    result = client.get(
        "/api/auth/callback?code=one-time-code&next=https://evil.example", follow_redirects=False
    )
    assert result.status_code == 303 and result.headers["location"] == "/"
    exchange = calls[-2]
    assert exchange.url.params["grant_type"] == "pkce"
    assert json.loads(exchange.content) == {"auth_code": "one-time-code", "code_verifier": verifier}
    assert client.cookies.get("__Host-operis_pkce") is None
    assert client.cookies.get("__Host-operis_session") == "private-test-access-token"
    assert "private-test" not in result.text
    assert result.headers["cache-control"] == "no-store"
    assert client.get("/api/auth/callback?code=one-time-code", follow_redirects=False).status_code == 400


def test_callback_without_browser_verifier_never_calls_provider(harness):
    client, calls, _ = harness
    client.cookies.clear()
    response = client.get("/api/auth/callback?code=private-code&error_description=private-error")
    assert response.status_code == 400
    assert "private" not in response.text
    assert calls == []


def test_callback_provider_failure_clears_verifier_without_session(harness):
    client, calls, behavior = harness
    client.cookies.clear()
    client.post("/api/auth/code", json={"email": "admin@example.com"}, headers=HEADERS)
    behavior["failure"] = 400
    response = client.get("/api/auth/callback?code=expired", follow_redirects=False)
    assert response.status_code == 400
    assert client.cookies.get("__Host-operis_pkce") is None
    assert client.cookies.get("__Host-operis_session") is None
    assert "sensitive" not in response.text


def test_password_login_keeps_tokens_private_and_preserves_spaces(harness):
    client, calls, _ = harness
    client.cookies.clear()
    response = client.post(
        "/api/auth/password",
        headers=HEADERS,
        json={"email": "admin@example.com", "password": "  example password  "},
    )
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    assert json.loads(calls[0].content)["password"] == "  example password  "
    assert calls[0].url.params["grant_type"] == "password"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert "private-test" not in response.text


def test_password_update_requires_session_and_origin(harness):
    client, calls, _ = harness
    assert client.put("/api/auth/password", json={"password": "long-test-password"}).status_code == 403
    client.cookies.clear()
    assert (
        client.put("/api/auth/password", headers=HEADERS, json={"password": "long-test-password"}).status_code
        == 401
    )
    assert calls == []


def test_password_update_targets_only_current_user(harness):
    client, calls, _ = harness
    response = client.put("/api/auth/password", headers=HEADERS, json={"password": "  long-test-password  "})
    assert response.json() == {"updated": True}
    assert calls[-1].method == "PUT"
    assert calls[-1].url.path == "/auth/v1/user"
    assert calls[-1].headers["authorization"] == "Bearer user-access-token"
    assert json.loads(calls[-1].content) == {"password": "  long-test-password  "}
    assert "password" not in response.text
    assert (
        client.put(
            "/api/auth/password", headers=HEADERS, json={"password": "long-test-password", "user_id": USER}
        ).status_code
        == 422
    )


def test_password_rejections_are_redacted_and_rate_limited(harness):
    client, calls, behavior = harness
    client.cookies.clear()
    behavior["failure"] = 400
    for _ in range(10):
        r = client.post(
            "/api/auth/password",
            headers=HEADERS,
            json={"email": "admin@example.com", "password": "private-password"},
        )
        assert r.status_code == 401
        assert "private-password" not in r.text and "sensitive" not in r.text
    assert (
        client.post(
            "/api/auth/password",
            headers=HEADERS,
            json={"email": "admin@example.com", "password": "private-password"},
        ).status_code
        == 429
    )
    assert client.cookies.get("__Host-operis_session") is None


@pytest.mark.parametrize(
    "member,role,status", [(False, "admin", 404), (True, "viewer", 403), (True, "operator", 403)]
)
@pytest.mark.parametrize(
    "method,suffix,payload",
    [
        ("PATCH", "", {"name": "Denied rename"}),
        ("POST", "/companies", {"code": "DENIED", "name": "Denied company"}),
        ("POST", "/sites", {"code": "DENIED", "name": "Denied site", "company_id": TENANT}),
    ],
)
def test_all_structural_writes_enforce_membership_before_data(
    harness, member, role, status, method, suffix, payload
):
    client, calls, behavior = harness
    behavior.update(member=member, role=role)
    response = client.request(method, f"/api/tenants/{TENANT}{suffix}", json=payload, headers=HEADERS)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert [r.url.path for r in calls] == ["/auth/v1/user", "/rest/v1/operis_memberships"]
    assert all(r.headers["authorization"] == "Bearer user-access-token" for r in calls)


def test_viewer_can_read_workspace_with_scoped_queries(harness):
    client, calls, behavior = harness
    behavior["role"] = "viewer"
    response = client.get(f"/api/tenants/{TENANT}/workspace")
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"
    for request in calls[1:]:
        assert request.url.params["tenant_id"] == f"eq.{TENANT}"
        assert request.headers["authorization"] == "Bearer user-access-token"


def test_membership_removal_takes_effect_on_next_request(harness):
    client, calls, behavior = harness
    assert client.get(f"/api/tenants/{TENANT}/workspace").status_code == 200
    behavior["member"] = False
    calls.clear()
    assert client.get(f"/api/tenants/{TENANT}/workspace").status_code == 404
    assert len(calls) == 2


@pytest.mark.parametrize("failure", [None, 401, 403, 500])
def test_logout_clears_session_and_pending_link_even_when_provider_fails(harness, failure):
    client, calls, behavior = harness
    client.cookies.clear()
    client.post("/api/auth/verify", json={"email": "admin@example.com", "code": "123456"}, headers=HEADERS)
    client.post("/api/auth/code", json={"email": "admin@example.com"}, headers=HEADERS)
    behavior["failure"] = failure
    response = client.post("/api/auth/logout", json={}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "provider_revoked": failure != 500}
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert all(
        "HttpOnly" in c and "Secure" in c and "Path=/" in c and "Max-Age=0" in c and "Domain=" not in c
        for c in cookies
    )
    assert not client.cookies.get("__Host-operis_session")
    assert not client.cookies.get("__Host-operis_pkce")
    calls.clear()
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/auth/callback?code=old-link", follow_redirects=False).status_code == 400
    assert calls == []
    assert client.post("/api/auth/logout", json={}, headers=HEADERS).status_code == 200


@pytest.mark.parametrize(
    "query",
    ["error=access_denied&error_code=otp_expired&error_description=private", "code=expired", "code=replayed"],
)
def test_failed_link_has_safe_recovery_and_no_session(harness, query):
    client, calls, behavior = harness
    client.cookies.clear()
    client.post("/api/auth/code", json={"email": "admin@example.com"}, headers=HEADERS)
    behavior["failure"] = 400
    result = client.get(f"/api/auth/callback?{query}", follow_redirects=False)
    assert result.status_code == 400
    assert '<a href="/">Operis</a>' in result.text
    assert "private" not in result.text
    assert result.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in result.headers["content-security-policy"]
    assert result.headers["cache-control"] == "no-store"
    assert not client.cookies.get("__Host-operis_pkce")
    assert not client.cookies.get("__Host-operis_session")


def test_site_success_scopes_parent_and_correlates_audit_request(harness):
    client, calls, _ = harness
    original = client.app.state.gateway

    class VisibleCompanyGateway:
        async def request(self, method, path, **kwargs):
            if method == "GET" and path == "/rest/v1/operis_companies":
                assert kwargs["params"] == {"select": "id", "id": f"eq.{USER}", "tenant_id": f"eq.{TENANT}"}
                assert kwargs["token"] == "user-access-token"
                return [{"id": USER}]
            return await original.request(method, path, **kwargs)

    client.app.state.gateway = VisibleCompanyGateway()
    response = client.post(
        f"/api/tenants/{TENANT}/sites",
        json={"company_id": USER, "code": "SITE", "name": "Facility"},
        headers=HEADERS,
    )
    assert response.status_code == 201
    assert json.loads(calls[-1].content) == {
        "tenant_id": TENANT,
        "company_id": USER,
        "code": "SITE",
        "name": "Facility",
    }
    assert calls[-1].headers["x-request-id"] == response.headers["x-request-id"]
    assert calls[-1].headers["authorization"] == "Bearer user-access-token"
