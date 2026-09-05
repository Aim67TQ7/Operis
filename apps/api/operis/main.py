import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings, get_settings
from .gateway import Gateway

log = logging.getLogger("operis")
log.setLevel(logging.INFO)
log.propagate = False
if not log.handlers:
    log.addHandler(logging.StreamHandler())


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EmailInput(Input):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class VerifyInput(EmailInput):
    code: str = Field(pattern=r"^\d{6,10}$")


class TenantInput(Input):
    name: str = Field(min_length=2, max_length=100)


class CompanyInput(TenantInput):
    code: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")


class SiteInput(CompanyInput):
    company_id: UUID


class RateLimiter:
    """Single-process backstop. Supabase also enforces provider-side OTP limits."""

    def __init__(self):
        self.buckets = defaultdict(deque)

    def check(self, key: str, limit: int, window: int = 600):
        now = time.monotonic()
        # Bound memory even if hostile clients rotate addresses / email values.
        if len(self.buckets) >= 10000:
            self.buckets = defaultdict(
                deque, {k: v for k, v in self.buckets.items() if v and v[-1] > now - window}
            )
            if len(self.buckets) >= 10000 and key not in self.buckets:
                raise HTTPException(429, "Too many attempts. Please wait and try again.")
        bucket = self.buckets[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, "Too many attempts. Please wait and try again.")
        bucket.append(now)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        app.state.gateway = Gateway(app.state.settings, client)
        yield


def gateway(request: Request) -> Gateway:
    return request.app.state.gateway


GW = Annotated[Gateway, Depends(gateway)]


async def identity(request: Request, gw: GW):
    token = request.cookies.get(request.app.state.settings.cookie_name)
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    user = await gw.request("GET", "/auth/v1/user", token=token)
    if not user.get("id") or user.get("is_anonymous") or not user.get("email_confirmed_at"):
        raise HTTPException(401, "A verified email identity is required.")
    return {"id": user["id"], "email": user.get("email", ""), "token": token}


User = Annotated[dict, Depends(identity)]


async def member(gw, user, tenant_id, admin=False):
    rows = await gw.request(
        "GET",
        "/rest/v1/operis_memberships",
        token=user["token"],
        params={"select": "tenant_id,role", "tenant_id": f"eq.{tenant_id}", "user_id": f"eq.{user['id']}"},
    )
    if not rows:
        raise HTTPException(404, "Organization not found.")
    if admin and rows[0]["role"] != "admin":
        raise HTTPException(403, "An organization administrator must make this change.")
    return rows[0]


def create_app(settings: Settings | None = None):
    settings = settings or get_settings()
    app = FastAPI(
        title="Operis API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.limiter = RateLimiter()

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        request.state.request_id = str(uuid4())
        start = time.monotonic()
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(
            "origin"
        ) != settings.app_origin.rstrip("/"):
            response = JSONResponse({"detail": "Request origin is not allowed."}, status_code=403)
        elif (
            request.method in {"POST", "PATCH", "PUT"}
            and request.headers.get("content-type", "").split(";")[0] != "application/json"
        ):
            response = JSONResponse({"detail": "JSON content is required."}, status_code=415)
        else:
            response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request.state.request_id,
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            }
        )
        log.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "unmatched"),
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - start) * 1000),
                }
            )
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        # FastAPI's default errors include rejected input; never echo OTPs or identity data.
        return JSONResponse({"detail": "Check the form fields and try again."}, status_code=422)

    @app.get("/api/health/live")
    async def live():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/health/ready")
    async def ready(gw: GW):
        if not settings.configured:
            raise HTTPException(503, "Identity and data services are not configured.")
        await gw.request("GET", "/auth/v1/health")
        # Probe the schema without a user: should expose no tenant rows.
        await gw.request("GET", "/rest/v1/operis_tenants", params={"select": "id", "limit": "0"})
        return {"status": "ready"}

    def limit(request, email, purpose):
        ip = request.client.host if request.client else "unknown"
        app.state.limiter.check(f"ip:{ip}:{purpose}", 30)
        digest = hashlib.sha256(email.lower().encode()).hexdigest()
        app.state.limiter.check(f"email:{digest}:{purpose}", 5 if purpose == "request" else 10)

    @app.post("/api/auth/code", status_code=202)
    async def send_code(data: EmailInput, request: Request, gw: GW):
        limit(request, data.email, "request")
        try:
            await gw.request(
                "POST", "/auth/v1/otp", payload={"email": data.email.lower(), "create_user": False}
            )
        except HTTPException as e:
            if e.status_code not in {401, 403}:
                raise
        return {"message": "If this email has access, a sign-in code will arrive shortly."}

    @app.post("/api/auth/verify")
    async def verify(data: VerifyInput, request: Request, response: Response, gw: GW):
        limit(request, data.email, "verify")
        result = await gw.request(
            "POST",
            "/auth/v1/verify",
            payload={"email": data.email.lower(), "token": data.code, "type": "email"},
        )
        token = result.get("access_token")
        if not token:
            raise HTTPException(401, "Your code is invalid or expired.")
        response.set_cookie(
            settings.cookie_name,
            token,
            httponly=True,
            secure=settings.environment == "production",
            samesite="strict",
            path="/",
            max_age=min(settings.session_seconds, int(result.get("expires_in", 3600))),
        )
        return {"authenticated": True}

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response, gw: GW):
        token = request.cookies.get(settings.cookie_name)
        if token:
            try:
                await gw.request("POST", "/auth/v1/logout", token=token, params={"scope": "local"})
            except HTTPException as e:
                if e.status_code not in {401, 403}:
                    raise
        response.delete_cookie(
            settings.cookie_name,
            path="/",
            secure=settings.environment == "production",
            httponly=True,
            samesite="strict",
        )
        return {"authenticated": False}

    @app.get("/api/me")
    async def me(user: User, gw: GW):
        tenants = await gw.request(
            "GET",
            "/rest/v1/operis_tenants",
            token=user["token"],
            params={"select": "id,name", "order": "name"},
        )
        roles = await gw.request(
            "GET",
            "/rest/v1/operis_memberships",
            token=user["token"],
            params={"select": "tenant_id,role", "user_id": f"eq.{user['id']}"},
        )
        by_id = {r["tenant_id"]: r["role"] for r in roles}
        return {
            "user": {"id": user["id"], "email": user["email"]},
            "tenants": [{**t, "role": by_id[t["id"]]} for t in tenants if t["id"] in by_id],
        }

    @app.get("/api/tenants/{tenant_id}/workspace")
    async def workspace(tenant_id: UUID, user: User, gw: GW):
        role = await member(gw, user, tenant_id)
        result = {"role": role["role"]}
        for name, selection in [
            ("companies", "id,code,name"),
            ("sites", "id,company_id,code,name"),
            ("memberships", "user_id,role"),
            ("audit_events", "id,actor_id,action,table_name,record_id,before,after,created_at,request_id"),
        ]:
            params = {"select": selection, "tenant_id": f"eq.{tenant_id}", "limit": "200"}
            params["order"] = (
                "created_at.desc"
                if name == "audit_events"
                else ("user_id" if name == "memberships" else "name")
            )
            result[name] = await gw.request(
                "GET", f"/rest/v1/operis_{name}", token=user["token"], params=params
            )
        return result

    @app.patch("/api/tenants/{tenant_id}")
    async def rename(tenant_id: UUID, data: TenantInput, request: Request, user: User, gw: GW):
        await member(gw, user, tenant_id, admin=True)
        result = await gw.request(
            "PATCH",
            "/rest/v1/operis_tenants",
            token=user["token"],
            payload=data.model_dump(),
            params={"id": f"eq.{tenant_id}"},
            request_id=request.state.request_id,
        )
        if not result:
            raise HTTPException(403, "The organization could not be updated.")
        return result[0]

    @app.post("/api/tenants/{tenant_id}/companies", status_code=201)
    async def company(tenant_id: UUID, data: CompanyInput, request: Request, user: User, gw: GW):
        await member(gw, user, tenant_id, admin=True)
        result = await gw.request(
            "POST",
            "/rest/v1/operis_companies",
            token=user["token"],
            payload={**data.model_dump(), "tenant_id": str(tenant_id)},
            request_id=request.state.request_id,
        )
        return result[0]

    @app.post("/api/tenants/{tenant_id}/sites", status_code=201)
    async def site(tenant_id: UUID, data: SiteInput, request: Request, user: User, gw: GW):
        await member(gw, user, tenant_id, admin=True)
        rows = await gw.request(
            "GET",
            "/rest/v1/operis_companies",
            token=user["token"],
            params={"select": "id", "id": f"eq.{data.company_id}", "tenant_id": f"eq.{tenant_id}"},
        )
        if not rows:
            raise HTTPException(404, "Company not found in this organization.")
        result = await gw.request(
            "POST",
            "/rest/v1/operis_sites",
            token=user["token"],
            payload={**data.model_dump(mode="json"), "tenant_id": str(tenant_id)},
            request_id=request.state.request_id,
        )
        return result[0]

    return app


app = create_app()
