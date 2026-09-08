"""Strict aggregate-only scanner ingestion; uploaded prose/scores are never trusted."""

import asyncio
import hashlib
import hmac
import io
import json
import re
import stat
import time
import zipfile
import zlib
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from starlette.concurrency import run_in_threadpool

MAX_UPLOAD = 1024 * 1024
MAX_EXPANDED = 128 * 1024
FILES = {"manifest.json", "summary.json", "self_evaluation.json", "opportunities.md"}
COUNT_KEYS = {"baqs", "bpms", "functions", "reports", "dashboards", "scheduled_tasks", "ap_invoices"}
SCHEMA_KEYS = {"ap_schema", "vendor_schema", "purchase_schema", "receipt_schema"}
STATUS = Literal[
    "ok",
    "too_large",
    "unauthorized",
    "forbidden",
    "not_exposed",
    "rate_limited",
    "http_error",
    "network_error",
    "invalid_response",
]
LABELS = {
    "baqs": "Business activity queries",
    "bpms": "BPM methods",
    "functions": "Functions",
    "reports": "Reports",
    "dashboards": "Dashboards",
    "scheduled_tasks": "Scheduled tasks",
    "ap_invoices": "Visible AP invoice records",
    "ap_schema": "AP invoice schema",
    "vendor_schema": "Vendor schema",
    "purchase_schema": "Purchasing schema",
    "receipt_schema": "Receipt schema",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Context(StrictModel):
    tenant_id: str
    company_id: str
    company_code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,24}$")
    scan_id: str
    issued_at: int
    expires_at: int

    @model_validator(mode="after")
    def valid_ids(self):
        for value in (self.tenant_id, self.company_id, self.scan_id):
            if str(UUID(value)) != value:
                raise ValueError("Noncanonical identity")
        return self


class ScanContext(StrictModel):
    context: Context
    signature: str = Field(pattern=r"^[a-f0-9]{64}$")


class Manifest(StrictModel):
    package_type: Literal["operis.epicor.discovery"]
    schema_version: Literal["1"]
    scanner_version: Literal["0.3.0"]
    scan_mode: Literal["metadata_only"]
    contains_credentials: Literal[False]
    scan_context: ScanContext
    completed_at: str = Field(max_length=40)
    checksums: dict[str, str]


class SchemaCounts(StrictModel):
    entities: int = Field(ge=1, le=100000)
    fields: int = Field(ge=0, le=1000000)
    custom_fields: int = Field(ge=0, le=1000000)

    @model_validator(mode="after")
    def custom_subset(self):
        if self.custom_fields > self.fields:
            raise ValueError("Custom fields exceed fields")
        return self


class Measurement(StrictModel):
    key: str
    status: STATUS
    count: int | None = Field(default=None, ge=0, le=999999999999)
    counts: SchemaCounts | None = None

    @model_validator(mode="after")
    def valid_measure(self):
        if self.key not in COUNT_KEYS | SCHEMA_KEYS:
            raise ValueError("Unknown measurement")
        if self.status != "ok":
            if self.count is not None or self.counts is not None:
                raise ValueError("Unavailable measurement has data")
        elif self.key in COUNT_KEYS:
            if self.count is None or self.counts is not None:
                raise ValueError("Invalid count")
        elif self.counts is None or self.count is not None:
            raise ValueError("Invalid metadata counts")
        return self


class Summary(StrictModel):
    preflight: Literal["ok"]
    measurements: list[Measurement] = Field(min_length=11, max_length=11)

    @model_validator(mode="after")
    def exact_measurements(self):
        if {item.key for item in self.measurements} != COUNT_KEYS | SCHEMA_KEYS:
            raise ValueError("Missing or duplicate measurement")
        return self


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sign_context(context, key):
    return hmac.new(key.encode(), b"operis-scan-v1:" + canonical(context), hashlib.sha256).hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("Nonfinite JSON")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def validate_package(data, tenant_id, company, key, now=None):
    """No extraction to disk. Exact allowlist + actual read bounds + strict types."""
    now = now or int(time.time())
    try:
        if len(data) > MAX_UPLOAD or not data.startswith(b"PK\x03\x04"):
            raise ValueError("Not an allowed ZIP")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) != 4 or {e.filename for e in entries} != FILES:
                raise ValueError("Unexpected archive entries")
            docs = {}
            total = 0
            for entry in entries:
                if (
                    entry.flag_bits & 1
                    or entry.is_dir()
                    or stat.S_ISLNK(entry.external_attr >> 16)
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or entry.file_size > MAX_EXPANDED
                    or entry.file_size > max(entry.compress_size, 1) * 100
                ):
                    raise ValueError("Unsafe archive member")
                with archive.open(entry) as handle:
                    body = handle.read(MAX_EXPANDED + 1)
                total += len(body)
                if total > MAX_EXPANDED or len(body) != entry.file_size:
                    raise ValueError("Expanded data too large")
                docs[entry.filename] = body
        manifest = Manifest.model_validate(strict_json(docs["manifest.json"]))
        if manifest.contains_credentials is not False:
            raise ValueError("Credential declaration")
        if set(manifest.checksums) != FILES - {"manifest.json"}:
            raise ValueError("Incomplete checksums")
        for name, expected in manifest.checksums.items():
            if not re.fullmatch(r"[a-f0-9]{64}", expected) or not hmac.compare_digest(
                hashlib.sha256(docs[name]).hexdigest(), expected
            ):
                raise ValueError("Checksum mismatch")
        context = manifest.scan_context.context
        if not hmac.compare_digest(sign_context(context.model_dump(), key), manifest.scan_context.signature):
            raise ValueError("Invalid company binding")
        if (
            context.tenant_id != str(tenant_id)
            or context.company_id != company["id"]
            or context.company_code != company["code"]
            or not context.issued_at <= now + 60
            or not now < context.expires_at <= context.issued_at + 7 * 86400
        ):
            raise ValueError("Expired or mismatched company binding")
        completed = datetime.fromisoformat(manifest.completed_at)
        if completed.tzinfo is None or not context.issued_at - 60 <= completed.timestamp() <= now + 300:
            raise ValueError("Invalid scan time")
        # No uploaded prose or claims are retained. These must be the exact kit placeholders.
        if strict_json(docs["self_evaluation.json"]) != {
            "assessment": "server_computed",
            "overall_score": None,
        }:
            raise ValueError("Unexpected assessment claims")
        if (
            docs["opportunities.md"]
            != b"# Assessment pending\nUpload this package to Operis for a server-computed assessment.\n"
        ):
            raise ValueError("Unexpected report content")
        summary = Summary.model_validate(strict_json(docs["summary.json"]))
        return manifest, summary
    except (
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
        RecursionError,
        zipfile.BadZipFile,
        zlib.error,
        RuntimeError,
        NotImplementedError,
        ValidationError,
    ):
        raise HTTPException(
            422,
            "Package rejected. Use the current kit and a fresh configuration for this company. Check the ZIP contents and checksums; only aggregate schema 1 packages are accepted.",
        ) from None


def assess(summary):
    measurements = [m.model_dump() for m in summary.measurements]
    measured = sum(m["status"] == "ok" for m in measurements)
    findings = []
    recommendations = []
    for m in measurements:
        if m["status"] != "ok":
            findings.append(
                {
                    "category": "gap",
                    "subject": LABELS[m["key"]] + " could not be measured",
                    "evidence": m["key"] + ": " + m["status"],
                    "score": 0,
                    "rationale": "Unknown coverage. Confirm API availability and account permissions; this is not a healthy result.",
                }
            )
    by_key = {m["key"]: m for m in measurements}
    for module, name, keys, rationale in [
        (
            "OPERIS-PAYABLES",
            "Operis Payables",
            ["ap_invoices"],
            "Review one invoice from intake through matching, GL suggestion and human approval. Invoice counts alone do not prove manual effort or savings.",
        ),
        (
            "OPERIS-INSIGHT",
            "Operis Insight",
            ["baqs", "reports", "dashboards"],
            "Review reporting ownership and overlap with the customer. Metadata counts do not establish which reports can be retired.",
        ),
        (
            "OPERIS-NERVE",
            "Operis Nerve",
            ["scheduled_tasks", "functions"],
            "Discuss communication and automation handoffs. These counts do not prove email, Slack or Teams usage.",
        ),
    ]:
        evidence = [
            {"measurement": key, "count": by_key[key]["count"]}
            for key in keys
            if by_key[key]["status"] == "ok" and by_key[key]["count"] > 0
        ]
        if evidence:
            recommendations.append(
                {
                    "module_code": module,
                    "module_name": name,
                    "rank": len(recommendations) + 1,
                    "evidence": evidence,
                    "rationale": rationale,
                }
            )
    custom = sum(m["counts"]["custom_fields"] for m in measurements if m["counts"])
    if custom:
        findings.append(
            {
                "category": "coverage",
                "subject": "Custom fields observed in sampled schemas",
                "evidence": f"{custom} custom-field appearances across sampled service schemas (may overlap).",
                "score": 0,
                "rationale": "Review ownership and dependencies. This does not establish upgrade risk.",
            }
        )
    return {
        "version": "1",
        "coverage": {"measured": measured, "attempted": len(measurements)},
        "overall_score": None,
        "findings": findings,
        "recommendations": recommendations,
        "limitations": [
            "Customer-supplied aggregate observations; the server validates the package, not the truth of its contents.",
            "Coverage is limited to eleven probes and the scanning account's visible data. Unknown is not healthy.",
            "No invoice lines, GL allocations, definitions, business values or credential material are collected.",
            "Recommendations are discussion candidates, not measured savings, ERP health scores or module activation.",
            "The signed company configuration binds the upload to Operis; it cannot attest which ERP an altered scanner contacted.",
        ],
    }


def install_routes(app, user_dependency, gateway_dependency, member):
    # The concrete Depends annotations are supplied by main to keep identity centralized.
    from typing import Annotated

    from fastapi import Depends

    User = Annotated[dict, Depends(user_dependency)]
    GW = Annotated[object, Depends(gateway_dependency)]
    semaphore = asyncio.Semaphore(2)

    async def company_access(tenant_id, company_id, user, gw, write=False):
        membership = await member(gw, user, tenant_id)
        if write and membership["role"] == "viewer":
            raise HTTPException(403, "An administrator or operator must upload scans and request pilots.")
        rows = await gw.request(
            "GET",
            "/rest/v1/operis_companies",
            token=user["token"],
            params={"select": "id,code,name", "id": f"eq.{company_id}", "tenant_id": f"eq.{tenant_id}"},
        )
        if not rows:
            raise HTTPException(404, "Company not found in this organization.")
        return rows[0]

    def signing_key():
        key = app.state.settings.discovery_ingest_key.get_secret_value()
        if len(key) < 32:
            raise HTTPException(503, "Discovery is not configured. Contact your administrator.")
        return key

    @app.get("/api/tenants/{tenant_id}/companies/{company_id}/discovery/config")
    async def config(tenant_id: UUID, company_id: UUID, user: User, gw: GW):
        company = await company_access(tenant_id, company_id, user, gw, write=True)
        now = int(time.time())
        context = {
            "tenant_id": str(tenant_id),
            "company_id": str(company_id),
            "company_code": company["code"],
            "scan_id": str(uuid4()),
            "issued_at": now,
            "expires_at": now + 7 * 86400,
        }
        return JSONResponse(
            {"context": context, "signature": sign_context(context, signing_key())},
            headers={"Content-Disposition": 'attachment; filename="operis-scan-config.json"'},
        )

    @app.post("/api/tenants/{tenant_id}/companies/{company_id}/discovery")
    async def upload(tenant_id: UUID, company_id: UUID, request: Request, user: User, gw: GW):
        company = await company_access(tenant_id, company_id, user, gw, write=True)
        key = signing_key()
        app.state.limiter.check("discovery:" + user["id"], 12)
        if semaphore.locked():
            raise HTTPException(429, "Other assessments are processing. Please retry shortly.")
        async with semaphore:
            data = bytearray()
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_UPLOAD:
                    raise HTTPException(413, "This aggregate-only kit must be no larger than 1 MiB.")
                data.extend(chunk)
            manifest, summary = await run_in_threadpool(
                validate_package, bytes(data), tenant_id, company, key
            )
            report = assess(summary)
            payload = {
                "tenant_id": str(tenant_id),
                "company_id": str(company_id),
                "company_code": company["code"],
                "scan_id": manifest.scan_context.context.scan_id,
                "package_sha256": hashlib.sha256(data).hexdigest(),
                "scanner_version": manifest.scanner_version,
                "completed_at": manifest.completed_at,
                "summary": summary.model_dump(),
                "report": report,
            }
            result = await gw.request(
                "POST",
                "/rest/v1/rpc/operis_commit_discovery",
                token=user["token"],
                payload={"p_payload": payload},
                request_id=request.state.request_id,
                ingest_key=key,
            )
            return result

    @app.get("/api/tenants/{tenant_id}/discovery")
    async def runs(tenant_id: UUID, user: User, gw: GW):
        await member(gw, user, tenant_id)
        return await gw.request(
            "GET",
            "/rest/v1/operis_discovery_runs",
            token=user["token"],
            params={
                "tenant_id": f"eq.{tenant_id}",
                "select": "id,company_id,status,scanner_version,created_at,package_sha256",
                "order": "created_at.desc",
                "limit": "100",
            },
        )

    async def get_run(tenant_id, run_id, user, gw):
        await member(gw, user, tenant_id)
        rows = await gw.request(
            "GET",
            "/rest/v1/operis_discovery_runs",
            token=user["token"],
            params={
                "tenant_id": f"eq.{tenant_id}",
                "id": f"eq.{run_id}",
                "select": "id,company_id,status,scanner_version,created_at,package_sha256,summary,self_evaluation,limitations",
            },
        )
        if not rows:
            raise HTTPException(404, "Assessment not found.")
        return rows[0]

    @app.get("/api/tenants/{tenant_id}/discovery/{run_id}")
    async def report(tenant_id: UUID, run_id: UUID, user: User, gw: GW):
        result = await get_run(tenant_id, run_id, user, gw)
        pilots = await gw.request(
            "GET",
            "/rest/v1/operis_discovery_pilots",
            token=user["token"],
            params={
                "tenant_id": f"eq.{tenant_id}",
                "run_id": f"eq.{run_id}",
                "select": "id,status,created_at",
            },
        )
        return {**result, "pilot_request": pilots[0] if pilots else None}

    @app.get("/api/tenants/{tenant_id}/discovery/{run_id}/export")
    async def export(tenant_id: UUID, run_id: UUID, user: User, gw: GW):
        result = await get_run(tenant_id, run_id, user, gw)
        return Response(
            canonical(result),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="operis-assessment.json"'},
        )

    @app.post("/api/tenants/{tenant_id}/discovery/{run_id}/pilot")
    async def pilot(tenant_id: UUID, run_id: UUID, request: Request, user: User, gw: GW):
        run = await get_run(tenant_id, run_id, user, gw)
        await company_access(tenant_id, run["company_id"], user, gw, write=True)
        return await gw.request(
            "POST",
            "/rest/v1/rpc/operis_request_discovery_pilot",
            token=user["token"],
            payload={"p_tenant": str(tenant_id), "p_run": str(run_id)},
            request_id=request.state.request_id,
        )

    from .browser_discovery import install_browser_routes

    install_browser_routes(app, User, GW, company_access, signing_key)
