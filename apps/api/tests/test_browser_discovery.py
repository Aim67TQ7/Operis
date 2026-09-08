import asyncio
import copy
import json
import socket
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from test_discovery import COMPANY, KEY, TENANT, api_harness, scanner  # noqa: F401

from operis import browser_discovery as browser
from operis.config import Settings

BASE = "https://erp.example/Test"
PATH = f"/api/tenants/{TENANT}/companies/{COMPANY}/discovery/browser"
CREDS = {"username": "synthetic-user", "password": "synthetic-password", "api_key": "synthetic-api-key"}
HEADERS = {"Origin": "https://operis.example"}
XML = b'<Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"><EntityType Name="PrivateName"><Property Name="Private_c"/></EntityType></Schema>'


@pytest.fixture
def harness(api_harness, monkeypatch):  # noqa: F811 — reuse the shared gateway fixture
    client, state = api_harness
    client.app.state.settings.discovery_browser_targets = {TENANT: {"base_url": BASE, "companies": ["TEST"]}}
    state["epicor"] = []

    def handler(req):
        state["epicor"].append(req)
        if state.get("revoke"):
            state["member"] = False
        if "Companies" in req.url.path:
            return httpx.Response(
                state.get("preflight", 200),
                json={"value": [{"Company1": "TEST", "private": "never-retained"}]},
            )
        if req.url.path.endswith("$count"):
            return httpx.Response(200, text="17")
        return httpx.Response(200, content=XML)

    client.app.state.epicor_transport = httpx.MockTransport(handler)
    monkeypatch.setattr(browser, "public_target", AsyncMock())
    return client, state


def run(client):
    return client.post(PATH + "/run", json=CREDS, headers=HEADERS)


def commits(state):
    return [r for r in state["calls"] if r.url.path.endswith("operis_commit_discovery")]


def test_reads_then_explicit_save_are_bound_and_credentials_are_discarded(harness):
    client, state = harness
    assert client.get(PATH).json()["endpoint"] == BASE
    result = run(client)
    assert result.status_code == 200, result.text
    assert result.headers["Cache-Control"] == "no-store"
    value = result.json()
    assert value["report"]["coverage"] == {"measured": 11, "attempted": 11}
    assert len(state["epicor"]) == 12
    assert not commits(state)
    for req in state["epicor"]:
        assert req.method == "GET"
        assert str(req.url).startswith(BASE + "/api/v2/odata/TEST/")
        assert "$count" in str(req.url) or "$metadata" in str(req.url) or "$select=Company1" in str(req.url)
        assert req.headers["x-api-key"] == CREDS["api_key"]
        assert req.headers["accept-encoding"] == "identity"
        assert req.headers["Authorization"].startswith("Basic ")
    saved = client.post(PATH + "/save", json=value["receipt"], headers=HEADERS)
    assert saved.status_code == 200, saved.text
    req = commits(state)[0]
    assert req.headers["Authorization"] == "Bearer test-user-jwt"
    assert req.headers["x-operis-ingest-key"] == KEY
    persisted = json.loads(req.content)["p_payload"]
    assert persisted["report"]["limitations"][0].startswith("Read by Operis")
    assert "site-specific coverage is not established" in persisted["report"]["limitations"][-1]
    for secret in [*CREDS.values(), "PrivateName", "Private_c", "never-retained", KEY]:
        assert secret not in result.text + saved.text + req.content.decode()
    assert BASE not in req.content.decode()
    # The same receipt produces the same immutable scan identity/hash for a retry.
    assert client.post(PATH + "/save", json=value["receipt"], headers=HEADERS).status_code == 200
    assert commits(state)[1].content == req.content


@pytest.mark.parametrize(
    "change,status", [({"role": "viewer"}, 403), ({"member": False}, 404), ({"company": False}, 404)]
)
def test_access_denial_precedes_credentials_and_network(harness, change, status):
    client, state = harness
    state.update(change)
    assert client.get(PATH).status_code == status
    for action in ("run", "save"):
        assert client.post(PATH + "/" + action, json=CREDS, headers=HEADERS).status_code == status
    assert not state["epicor"] and not commits(state)


def test_auth_origin_configuration_and_json_boundaries(harness):
    client, state = harness
    assert client.post(PATH + "/run", json=CREDS).status_code == 403
    assert client.post(PATH + "/run", content="{}", headers=HEADERS).status_code == 415
    assert (
        client.post(
            PATH + "/save", content="x" * 32769, headers={**HEADERS, "Content-Type": "application/json"}
        ).status_code
        == 413
    )
    client.app.state.settings.discovery_browser_targets = {}
    assert run(client).status_code == 409
    client.cookies.clear()
    assert client.get(PATH).status_code == 401
    assert run(client).status_code == 401
    assert not state["epicor"] and not commits(state)


@pytest.mark.parametrize(
    "patch",
    [
        {"password": []},
        {"api_key": "private\r\nheader"},
        {"api_key": "nonascii-🔑"},
        {"endpoint": "https://evil.example"},
        {"username": "bad:user"},
    ],
)
def test_bad_credentials_never_echo_inputs(harness, patch):
    client, state = harness
    response = client.post(PATH + "/run", json={**CREDS, **patch}, headers=HEADERS)
    assert response.status_code == 422
    assert "synthetic-" not in response.text and "private" not in response.text
    assert not state["epicor"]


@pytest.mark.parametrize(
    "patch",
    [
        {"tenant_id": "other"},
        {"company_code": "OTHER"},
        {"actor_id": "other"},
        {"endpoint": "https://evil.example"},
        {"expires_at": 0},
    ],
)
def test_signed_receipt_binding_and_expiry(harness, patch):
    client, state = harness
    receipt = run(client).json()["receipt"]
    receipt["payload"].update(patch)
    receipt["signature"] = browser.signature(receipt["payload"], KEY)
    result = client.post(PATH + "/save", json=receipt, headers=HEADERS)
    assert result.status_code == 422 and not commits(state)


def test_tamper_then_role_revocation_prevents_save(harness):
    client, state = harness
    receipt = run(client).json()["receipt"]
    bad = copy.deepcopy(receipt)
    bad["payload"]["summary"]["measurements"][0]["count"] = 900
    assert client.post(PATH + "/save", json=bad, headers=HEADERS).status_code == 422
    state["role"] = "viewer"
    assert client.post(PATH + "/save", json=receipt, headers=HEADERS).status_code == 403
    assert not commits(state)


def test_revocation_during_scan_withholds_results(harness):
    client, state = harness
    state["revoke"] = True
    assert run(client).status_code == 404
    assert not commits(state)


def test_preflight_denial_and_rate_limit_leave_no_assessment(harness):
    client, state = harness
    state["preflight"] = 401
    for _ in range(3):
        result = run(client)
        assert result.status_code == 422 and "unauthorized" in result.text
    assert run(client).status_code == 429
    assert len(state["epicor"]) == 3 and not commits(state)


def test_deadline_is_safe_and_releases_scan_slot(harness, monkeypatch):
    client, state = harness
    monkeypatch.setattr(browser, "scan", AsyncMock(side_effect=TimeoutError))
    for _ in range(2):
        assert run(client).status_code == 504
    assert not commits(state)


async def test_probe_parity_partial_results_and_no_redirects():
    assert browser.COUNTS == scanner.COUNTS
    assert browser.METADATA == scanner.METADATA
    requests = []
    responses = [
        httpx.Response(302, headers={"Location": "https://evil.example"}),
        httpx.Response(403, text="secret"),
        httpx.Response(200, text="not-count"),
        httpx.Response(200, content=b"x" * (browser.MAX_RESPONSE + 1)),
    ]

    def handler(req):
        requests.append(req)
        if "Companies" in req.url.path:
            return httpx.Response(200, json={"value": [{"Company1": "TEST"}]})
        if responses:
            return responses.pop(0)
        return httpx.Response(404, text="secret upstream body")

    result = await browser.scan(BASE, "TEST", browser.Credentials(**CREDS), httpx.MockTransport(handler))
    assert len(requests) == 12 and all(r.url.host == "erp.example" for r in requests)
    assert [m.status for m in result.measurements][:4] == [
        "http_error",
        "forbidden",
        "invalid_response",
        "too_large",
    ]
    assert browser.browser_report(result)["coverage"]["measured"] == 0
    assert "secret" not in result.model_dump_json()


@pytest.mark.parametrize(
    "url",
    [
        "http://erp.example",
        "https://user:pass@erp.example",
        "https://erp.example/?key=private",
        "https://erp.example/#token",
        "https://erp.example/%2fadmin",
        "https://erp.example:8443",
        "https://erp.example/../admin",
    ],
)
def test_bad_operator_destinations_rejected(url):
    with pytest.raises(ValueError):
        Settings(discovery_browser_targets={TENANT: {"base_url": url, "companies": ["TEST"]}})


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"])
async def test_private_network_resolution_rejected(monkeypatch, address):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop,
        "getaddrinfo",
        AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]),
    )
    with pytest.raises(HTTPException) as exc:
        await browser.public_target(BASE)
    assert exc.value.status_code == 503


@pytest.mark.parametrize(
    "data", [b'<!DOCTYPE x [<!ENTITY x "secret">]><x/>', b"<x/>", b"\xff", b"<x>\x00</x>"]
)
def test_metadata_rejects_unsafe_or_unrecognized_data(data):
    with pytest.raises(ValueError):
        browser.reduce_metadata(data)


async def test_compressed_responses_are_rejected_before_reading():
    class MustNotRead(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("Compressed response must not be read or decompressed")
            yield b""

    def handler(req):
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=MustNotRead())

    with pytest.raises(HTTPException) as exc:
        await browser.scan(BASE, "TEST", browser.Credentials(**CREDS), httpx.MockTransport(handler))
    assert exc.value.status_code == 422
    assert "invalid_response" in exc.value.detail
