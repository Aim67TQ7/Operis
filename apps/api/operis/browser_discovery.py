"""Bounded server-side Epicor reads. No credentials, raw responses or jobs persist."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import re
import socket
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, Request
from pydantic import Field, SecretStr, ValidationError

from .discovery import StrictModel, Summary, assess, canonical, strict_json

# Same eleven probes as the reviewed 0.3.0 local kit; parity is tested.
COUNTS = {
    "baqs": "Ice.BO.BAQDesignerSvc/BAQDesigners/$count",
    "bpms": "Ice.BO.BpMethodSvc/BpMethods/$count",
    "functions": "Ice.BO.EFxLibrarySvc/EFxLibraries/$count",
    "reports": "Ice.BO.ReportSvc/Reports/$count",
    "dashboards": "Ice.BO.DashBoardSvc/DashBoards/$count",
    "scheduled_tasks": "Ice.BO.SysTaskSvc/SysTasks/$count",
    "ap_invoices": "Erp.BO.APInvoiceSvc/APInvoices/$count",
}
METADATA = {
    "ap_schema": "Erp.BO.APInvoiceSvc/$metadata",
    "vendor_schema": "Erp.BO.VendorSvc/$metadata",
    "purchase_schema": "Erp.BO.POSvc/$metadata",
    "receipt_schema": "Erp.BO.ReceiptSvc/$metadata",
}
MAX_RESPONSE = 4 * 1024 * 1024


class Credentials(StrictModel):
    username: str = Field(min_length=1, max_length=256, pattern=r"^[^:\r\n]+$", repr=False)
    password: SecretStr = Field(min_length=1, max_length=512, repr=False)
    api_key: SecretStr = Field(min_length=1, max_length=2048, repr=False)


def valid_target(value):
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.query
        or p.fragment
        or p.port not in (None, 443)
        or re.search(r"[\s\\%]|\.\.", value)
    ):
        raise ValueError("Browser discovery targets must be fixed HTTPS application URLs")
    return value.rstrip("/")


async def public_target(base):
    # Targets come only from operator configuration, never request input.
    host = urlsplit(valid_target(base)).hostname
    try:
        addresses = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Nonpublic destination")
    except (OSError, ValueError):
        raise HTTPException(503, "The configured Epicor endpoint is not publicly reachable.") from None


def reduce_metadata(data):
    text = data.decode("utf-8", errors="strict")
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("Unsafe XML")
    edm = "{http://docs.oasis-open.org/odata/ns/edm}"
    entities = list(ET.fromstring(text).iter(edm + "EntityType"))
    if not entities:
        raise ValueError("Missing entities")
    fields = [p for e in entities for p in e.findall(edm + "Property")]
    return {
        "entities": len(entities),
        "fields": len(fields),
        "custom_fields": sum(p.get("Name", "").endswith("_c") for p in fields),
    }


async def scan(base, company, credentials, transport=None):
    async with httpx.AsyncClient(
        auth=httpx.BasicAuth(credentials.username, credentials.password.get_secret_value()),
        headers={
            "x-api-key": credentials.api_key.get_secret_value(),
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "operis-browser-discovery/0.3.0",
        },
        timeout=4,
        follow_redirects=False,
        trust_env=False,
        transport=transport,
    ) as client:
        prefix = base + "/api/v2/odata/" + company + "/"

        async def get(path):
            try:
                async with client.stream("GET", prefix + path) as response:
                    if response.status_code != 200:
                        return {
                            401: "unauthorized",
                            403: "forbidden",
                            404: "not_exposed",
                            429: "rate_limited",
                        }.get(response.status_code, "http_error"), None
                    # Do not let automatic HTTP decompression allocate an unbounded body.
                    if response.headers.get("content-encoding", "identity").lower() not in ("", "identity"):
                        return "invalid_response", None
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > MAX_RESPONSE:
                            return "too_large", None
                        body.extend(chunk)
                    return "ok", bytes(body)
            except (httpx.HTTPError, ValueError):
                return "network_error", None

        status, body = await get(
            "Erp.BO.CompanySvc/Companies?$top=1&$select=Company1"
            + "&$filter=Company1%20eq%20%27"
            + company
            + "%27"
        )
        try:
            found = status == "ok" and json.loads(body)["value"][0]["Company1"] == company
        except (ValueError, TypeError, KeyError, IndexError):
            found = False
        if not found:
            raise HTTPException(
                422,
                "Epicor company check failed ("
                + status
                + "). Check the company, API key and account permissions. Nothing was saved.",
            )
        gate = asyncio.Semaphore(3)

        async def measure(key, path):
            async with gate:
                status, body = await get(path)
            result = {"key": key, "status": status}
            if status == "ok":
                try:
                    if key in COUNTS:
                        count = body.decode("ascii").strip()
                        if not re.fullmatch(r"\d{1,12}", count):
                            raise ValueError("Invalid count")
                        result["count"] = int(count)
                    else:
                        result["counts"] = reduce_metadata(body)
                except (ValueError, ET.ParseError):
                    result = {"key": key, "status": "invalid_response"}
            return result

        measurements = await asyncio.gather(*(measure(k, v) for k, v in (COUNTS | METADATA).items()))
        try:
            return Summary.model_validate({"preflight": "ok", "measurements": measurements})
        except ValidationError:
            raise HTTPException(422, "Epicor returned measurements outside the supported limits.") from None


def signature(payload, key):
    return hmac.new(key.encode(), b"operis-browser-scan-v1:" + canonical(payload), hashlib.sha256).hexdigest()


def browser_report(summary):
    report = assess(summary)
    report["limitations"][0] = (
        "Read by Operis from the operator-configured Epicor endpoint using the supplied account."
    )
    report["limitations"][-1] = "Company-wide metadata scan; site-specific coverage is not established."
    return report


async def bounded_json(request, limit):
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "Use a JSON request.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, "Request is too large.")
        data.extend(chunk)
    try:
        return strict_json(bytes(data))
    except (ValueError, RecursionError):
        raise HTTPException(422, "Check the form fields and try again.") from None


def install_browser_routes(app, User, GW, company_access, signing_key):
    gate = asyncio.Semaphore(1)

    def target(tenant_id, company):
        config = app.state.settings.discovery_browser_targets.get(str(tenant_id), {})
        if company["code"] not in config.get("companies", []):
            raise HTTPException(
                409, "Browser discovery is not configured for this company. Contact your administrator."
            )
        return valid_target(config["base_url"])

    @app.get("/api/tenants/{tenant_id}/companies/{company_id}/discovery/browser")
    async def options(tenant_id: UUID, company_id: UUID, user: User, gw: GW):
        company = await company_access(tenant_id, company_id, user, gw, write=True)
        return {"endpoint": target(tenant_id, company), "company_code": company["code"], "probes": 11}

    @app.post("/api/tenants/{tenant_id}/companies/{company_id}/discovery/browser/run")
    async def run(tenant_id: UUID, company_id: UUID, request: Request, user: User, gw: GW):
        company = await company_access(tenant_id, company_id, user, gw, write=True)
        base = target(tenant_id, company)
        key = signing_key()
        app.state.limiter.check("browser-scan:" + user["id"], 3)
        if gate.locked():
            raise HTTPException(429, "A browser scan is running. Retry shortly.")
        try:
            credentials = Credentials.model_validate(await bounded_json(request, 8192))
            if not re.fullmatch(r"[!-~]+", credentials.api_key.get_secret_value()):
                raise ValueError("Invalid header")
        except (ValidationError, ValueError):
            raise HTTPException(422, "Check the Epicor credential fields and try again.") from None
        if gate.locked():
            raise HTTPException(429, "A browser scan is running. Retry shortly.")
        async with gate:
            try:
                async with asyncio.timeout(22):
                    await public_target(base)
                    summary = await scan(
                        base, company["code"], credentials, getattr(app.state, "epicor_transport", None)
                    )
            except TimeoutError:
                raise HTTPException(
                    504, "The Epicor scan timed out. Nothing was saved. Retry later."
                ) from None
            finally:
                del credentials
        # Membership and company are checked again before returning any measurements.
        current = await company_access(tenant_id, company_id, user, gw, write=True)
        if current["code"] != company["code"] or target(tenant_id, current) != base:
            raise HTTPException(409, "Company configuration changed. Run a new scan.")
        completed = datetime.now(timezone.utc).isoformat()
        payload = {
            "tenant_id": str(tenant_id),
            "company_id": str(company_id),
            "company_code": company["code"],
            "actor_id": user["id"],
            "endpoint": base,
            "scan_id": str(uuid4()),
            "expires_at": int(time.time()) + 1800,
            "completed_at": completed,
            "summary": summary.model_dump(),
        }
        return {
            "receipt": {"payload": payload, "signature": signature(payload, key)},
            "report": browser_report(summary),
        }

    @app.post("/api/tenants/{tenant_id}/companies/{company_id}/discovery/browser/save")
    async def save(tenant_id: UUID, company_id: UUID, request: Request, user: User, gw: GW):
        company = await company_access(tenant_id, company_id, user, gw, write=True)
        base, key = target(tenant_id, company), signing_key()
        value = await bounded_json(request, 32768)
        try:
            payload = value["payload"]
            if not hmac.compare_digest(signature(payload, key), value["signature"]):
                raise ValueError("Changed receipt")
            if (
                payload["tenant_id"] != str(tenant_id)
                or payload["company_id"] != str(company_id)
                or payload["company_code"] != company["code"]
                or payload["actor_id"] != user["id"]
                or payload["endpoint"] != base
                or payload["expires_at"] <= int(time.time())
            ):
                raise ValueError("Invalid binding")
            summary = Summary.model_validate(payload["summary"])
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, "This scan receipt changed or expired. Run discovery again.") from None
        normalized = {
            k: payload[k] for k in ("tenant_id", "company_id", "company_code", "scan_id", "completed_at")
        }
        normalized.update(
            scanner_version="0.3.0",
            package_sha256=hashlib.sha256(canonical(payload)).hexdigest(),
            summary=summary.model_dump(),
            report=browser_report(summary),
        )
        return await gw.request(
            "POST",
            "/rest/v1/rpc/operis_commit_discovery",
            token=user["token"],
            payload={"p_payload": normalized},
            request_id=request.state.request_id,
            ingest_key=key,
        )
