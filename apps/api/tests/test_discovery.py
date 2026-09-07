import hashlib
import importlib.util
import io
import json
import time
import zipfile
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from operis.config import Settings
from operis.discovery import (
    COUNT_KEYS,
    SCHEMA_KEYS,
    Summary,
    assess,
    canonical,
    sign_context,
    validate_package,
)
from operis.gateway import Gateway
from operis.main import create_app

spec = importlib.util.spec_from_file_location(
    "scanner", Path(__file__).resolve().parents[3] / "scanner/epicor_discover.py"
)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)
TENANT, COMPANY, USER = str(uuid4()), str(uuid4()), str(uuid4())
KEY = "offline-ingestion-key-" + "x" * 48
COMPANY_ROW = {"id": COMPANY, "code": "TEST", "name": "Synthetic company"}


def context():
    now = int(time.time())
    value = {
        "tenant_id": TENANT,
        "company_id": COMPANY,
        "company_code": "TEST",
        "scan_id": str(uuid4()),
        "issued_at": now - 10,
        "expires_at": now + 3600,
    }
    return {"context": value, "signature": sign_context(value, KEY)}


def summary():
    return {
        "preflight": "ok",
        "measurements": [
            *[{"key": k, "status": "ok", "count": 17} for k in sorted(COUNT_KEYS)],
            *[
                {"key": k, "status": "ok", "counts": {"entities": 2, "fields": 8, "custom_fields": 1}}
                for k in sorted(SCHEMA_KEYS)
            ],
        ],
    }


def package(tmp_path, changes=None):
    file = scanner.package(context(), summary(), tmp_path)
    with zipfile.ZipFile(file) as z:
        docs = {n: z.read(n) for n in z.namelist()}
    if changes:
        changes(docs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in docs.items():
            z.writestr(name, data)
    return buffer.getvalue()


def update(docs, name, callback, checksums=True):
    value = json.loads(docs[name])
    callback(value)
    docs[name] = canonical(value)
    if checksums and name != "manifest.json":
        manifest = json.loads(docs["manifest.json"])
        manifest["checksums"][name] = hashlib.sha256(docs[name]).hexdigest()
        docs["manifest.json"] = canonical(manifest)


def test_real_scanner_package_roundtrips_and_server_ignores_untrusted_scores(tmp_path):
    data = package(tmp_path)
    manifest, normalized = validate_package(data, TENANT, COMPANY_ROW, KEY)
    report = assess(normalized)
    assert manifest.scanner_version == "0.3.0"
    assert report["coverage"] == {"measured": 11, "attempted": 11}
    assert report["overall_score"] is None
    assert len(report["recommendations"]) == 3


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update({"../passwords.txt": b"secret"}),
        lambda d: d.update({"credentials.json": b"{}"}),
        lambda d: d.pop("summary.json"),
        lambda d: d.update({"opportunities.md": b"injected instructions"}),
        lambda d: update(d, "manifest.json", lambda m: m.update(contains_credentials=True)),
        lambda d: update(d, "manifest.json", lambda m: m.update(scanner_version="0.2")),
        lambda d: update(d, "manifest.json", lambda m: m.update(checksums={})),
        lambda d: update(d, "manifest.json", lambda m: m.update(extra_secret="forbidden")),
        lambda d: update(
            d, "manifest.json", lambda m: m["scan_context"]["context"].update(tenant_id=str(uuid4()))
        ),
        lambda d: update(d, "manifest.json", lambda m: m.update(completed_at="1999-01-01T00:00:00Z")),
        lambda d: update(d, "summary.json", lambda s: s.update(credentials="secret")),
        lambda d: update(d, "summary.json", lambda s: s["measurements"][0].update(count=True)),
        lambda d: update(d, "summary.json", lambda s: s["measurements"][0].update(count=-1)),
        lambda d: update(d, "summary.json", lambda s: s["measurements"][0].update(count=1.5)),
        lambda d: update(d, "summary.json", lambda s: s["measurements"][0].update(count=10**30)),
        lambda d: update(d, "summary.json", lambda s: s["measurements"][0].update(status="forbidden")),
        lambda d: update(d, "summary.json", lambda s: s["measurements"].append(s["measurements"][0])),
        lambda d: update(d, "summary.json", lambda s: s["measurements"][0].update(key="unknown")),
        lambda d: update(d, "summary.json", lambda s: s["measurements"][0].update(count=42), checksums=False),
        lambda d: update(d, "self_evaluation.json", lambda s: s.update(overall_score=100)),
    ],
)
def test_hostile_packages_rejected(tmp_path, mutation):
    with pytest.raises(HTTPException) as exc:
        validate_package(package(tmp_path, mutation), TENANT, COMPANY_ROW, KEY)
    assert exc.value.status_code == 422
    assert "secret" not in exc.value.detail


@pytest.mark.parametrize(
    "tenant,company,key",
    [
        (str(uuid4()), COMPANY_ROW, KEY),
        (TENANT, {**COMPANY_ROW, "id": str(uuid4())}, KEY),
        (TENANT, {**COMPANY_ROW, "code": "OTHER"}, KEY),
        (TENANT, COMPANY_ROW, "wrong-key"),
    ],
)
def test_package_company_and_key_binding(tmp_path, tenant, company, key):
    with pytest.raises(HTTPException):
        validate_package(package(tmp_path), tenant, company, key)


def test_expired_configuration_rejected(tmp_path):
    with pytest.raises(HTTPException):
        validate_package(package(tmp_path), TENANT, COMPANY_ROW, KEY, now=int(time.time()) + 86400)


def test_duplicate_json_keys_rejected(tmp_path):
    def mutate(d):
        d["manifest.json"] = d["manifest.json"].replace(b"{", b'{"schema_version":"evil",', 1)

    with pytest.raises(HTTPException):
        validate_package(package(tmp_path, mutate), TENANT, COMPANY_ROW, KEY)


def test_archive_bomb_and_duplicate_entries_rejected(tmp_path):
    for bomb in (False, True):
        data = package(tmp_path)
        stream = io.BytesIO(data)
        with zipfile.ZipFile(stream, "a", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json" if not bomb else "large.txt", b"x" * (200000 if bomb else 10))
        with pytest.raises(HTTPException):
            validate_package(stream.getvalue(), TENANT, COMPANY_ROW, KEY)


def test_unknown_coverage_never_becomes_good_score():
    data = summary()
    for item in data["measurements"]:
        item["status"] = "forbidden"
        item["count"] = None
        item["counts"] = None
    report = assess(Summary.model_validate(data))
    assert report["coverage"]["measured"] == 0
    assert report["overall_score"] is None
    assert report["recommendations"] == []
    assert len(report["findings"]) == 11


@pytest.mark.parametrize(
    "url",
    [
        "http://erp.example",
        "https://user:pass@erp.example",
        "https://erp.example/?secret=x",
        "https://erp.example/#token",
        "https://erp.example/../x",
        "https://erp.example/%2fadmin",
        "https://erp.example\\@evil.test",
    ],
)
def test_scanner_rejects_unsafe_destination(url):
    with pytest.raises(scanner.ScanError):
        scanner.base_url(url)


def test_scanner_never_follows_redirects():
    assert scanner.NoRedirect().redirect_request(None, None, 302, None, None, "https://evil.example") is None


def test_scanner_preflight_fails_without_package():
    class Client:
        company = "TEST"

        def get(self, path):
            return "forbidden", b"secret upstream error"

    with pytest.raises(scanner.ScanError) as exc:
        scanner.scan(Client())
    assert "secret" not in str(exc.value)


def test_scanner_reduces_metadata_and_rejects_entities():
    xml = b'<Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"><EntityType Name="Invoice"><Property Name="Secret_c"/></EntityType></Schema>'
    assert scanner.metadata_counts(xml) == {"entities": 1, "fields": 1, "custom_fields": 1}
    with pytest.raises(ValueError):
        scanner.metadata_counts(b'<!DOCTYPE x [<!ENTITY x "secret">]><x/>')


def test_scanner_calls_only_bounded_explicit_read_endpoints():
    class Client:
        company = "TEST"
        paths = []

        def get(self, path):
            self.paths.append(path)
            if "Companies?" in path:
                return "ok", b'{"value":[{"Company1":"TEST","unexpected_secret":"never-exported"}]}'
            if "$count" in path:
                return "ok", b"42"
            return "not_exposed", None

    client = Client()
    result = scanner.scan(client)
    assert len(client.paths) == 12
    assert all("$count" in p or "$metadata" in p or "$select=Company1" in p for p in client.paths)
    assert "never-exported" not in json.dumps(result)


@pytest.fixture
def api_harness():
    state = {"member": True, "role": "admin", "company": True, "calls": []}
    settings = Settings(
        environment="production",
        app_origin="https://operis.example",
        supabase_url="https://identity.example",
        supabase_publishable_key="public-test-key",
        discovery_ingest_key=KEY,
    )

    def handler(req):
        state["calls"].append(req)
        path = req.url.path
        if path == "/auth/v1/user":
            result = {"id": USER, "email_confirmed_at": "2026-01-01T00:00:00Z"}
        elif path.endswith("operis_memberships"):
            result = [{"role": state["role"]}] if state["member"] else []
        elif path.endswith("operis_companies"):
            result = [COMPANY_ROW] if state["company"] else []
        elif path.endswith("operis_commit_discovery"):
            result = {"id": str(uuid4()), "duplicate": False}
        else:
            result = []
        return httpx.Response(200, json=result)

    app = create_app(settings)
    with TestClient(app, base_url="https://operis.example") as client:
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        app.state.gateway = Gateway(settings, upstream)
        client.cookies.set(settings.cookie_name, "test-user-jwt")
        yield client, state
        client.portal.call(upstream.aclose)


def test_authenticated_upload_uses_user_jwt_and_server_capability(tmp_path, api_harness):
    client, state = api_harness
    result = client.post(
        f"/api/tenants/{TENANT}/companies/{COMPANY}/discovery",
        content=package(tmp_path),
        headers={"Origin": "https://operis.example", "Content-Type": "application/zip"},
    )
    assert result.status_code == 200, result.text
    req = state["calls"][-1]
    assert req.headers["Authorization"] == "Bearer test-user-jwt"
    assert req.headers["x-operis-ingest-key"] == KEY
    assert all("x-operis-ingest-key" not in r.headers for r in state["calls"][:-1])
    assert KEY not in result.text
    assert result.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "change,status", [({"role": "viewer"}, 403), ({"member": False}, 404), ({"company": False}, 404)]
)
def test_upload_authorization_before_ingest(tmp_path, api_harness, change, status):
    client, state = api_harness
    state.update(change)
    r = client.post(
        f"/api/tenants/{TENANT}/companies/{COMPANY}/discovery",
        content=package(tmp_path),
        headers={"Origin": "https://operis.example", "Content-Type": "application/zip"},
    )
    assert r.status_code == status
    assert not any(c.url.path.endswith("operis_commit_discovery") for c in state["calls"])


def test_upload_origin_size_and_content_type_boundaries(api_harness):
    client, _ = api_harness
    path = f"/api/tenants/{TENANT}/companies/{COMPANY}/discovery"
    assert client.post(path, content=b"ZIP", headers={"Content-Type": "application/zip"}).status_code == 403
    assert client.post(path, json={}, headers={"Origin": "https://operis.example"}).status_code == 415
    assert (
        client.post(
            path,
            content=b"x" * 1048577,
            headers={"Origin": "https://operis.example", "Content-Type": "application/zip"},
        ).status_code
        == 413
    )
    client.cookies.clear()
    assert (
        client.post(
            path,
            content=b"ZIP",
            headers={"Origin": "https://operis.example", "Content-Type": "application/zip"},
        ).status_code
        == 401
    )


def test_hosted_kit_matches_reviewed_sources():
    root = Path(__file__).resolve().parents[3]
    path = root / "apps/web/public/kits/operis-epicor-discovery-0.3.0.zip"
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist()) == {"epicor_discover.py", "Run-Discovery.cmd", "README.md"}
        for name in z.namelist():
            assert z.read(name) == (root / "scanner" / name).read_bytes()
    assert (
        path.with_suffix(".zip.sha256").read_text().startswith(hashlib.sha256(path.read_bytes()).hexdigest())
    )
