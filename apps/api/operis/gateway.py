import httpx
from fastapi import HTTPException

from .config import Settings


class Gateway:
    """Request-scoped Supabase gateway. Authorization always uses the user's JWT."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    async def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload=None,
        params=None,
        request_id: str | None = None,
        ingest_key: str | None = None,
    ):
        if not self.settings.configured:
            raise HTTPException(503, "Sign-in is not configured. Contact your administrator.")
        headers = {"apikey": self.settings.supabase_publishable_key.get_secret_value()}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if request_id:
            headers["x-request-id"] = request_id
        if ingest_key:
            if path != "/rest/v1/rpc/operis_commit_discovery":
                raise ValueError("Ingestion key may only be sent to the ingestion RPC")
            headers["x-operis-ingest-key"] = ingest_key
        if path.startswith("/rest/"):
            headers["Prefer"] = "return=representation"
        try:
            response = await self.client.request(
                method,
                self.settings.supabase_url.rstrip("/") + path,
                headers=headers,
                json=payload,
                params=params,
            )
        except httpx.RequestError:
            raise HTTPException(503, "The identity or data service is temporarily unavailable.") from None
        if response.status_code >= 400:
            # Never forward provider payloads, SQL, request bodies, or credentials.
            code = response.status_code
            if code == 429:
                raise HTTPException(429, "Too many attempts. Please wait and try again.")
            if code in (400, 401) and path.startswith("/auth/"):
                raise HTTPException(401, "Your code or session is invalid or expired.")
            if code == 403:
                raise HTTPException(403, "You do not have permission for this action.")
            if code == 409:
                if path == "/rest/v1/rpc/operis_commit_discovery":
                    raise HTTPException(
                        409,
                        "This scan configuration already has a saved assessment. Retry the original ZIP or download a new configuration and run a new scan.",
                    )
                raise HTTPException(409, "This code already exists in the organization.")
            raise HTTPException(503, "The service could not complete this request.")
        return response.json() if response.content else None
