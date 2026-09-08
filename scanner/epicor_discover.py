#!/usr/bin/env python3
"""Operis Epicor Discovery Kit 0.3.0. GET-only, aggregate metadata export.
Derived from the supplied v0.1 probe inventory; the unavailable v0.2 artifact
is not claimed as recovered. Standard library only. Python 3.10+.
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.3.0"
SCHEMA = "1"
EDM = "{http://docs.oasis-open.org/odata/ns/edm}"
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


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ScanError(Exception):
    pass


def base_url(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or re.search(r"[\s\\]", value)
            or re.search(r"%|\.\.", parsed.path)):
        raise ScanError("Use the HTTPS Epicor application URL, without credentials, query, or fragment.")
    return value.rstrip("/")


class Client:
    def __init__(self, base, company, api_key, user="", password="", bearer="", ca_file=None):
        self.base = base_url(base)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", company):
            raise ScanError("The company code is invalid.")
        self.company = company
        self.headers = {"Accept": "application/json", "User-Agent": "operis-discovery/" + VERSION,
                        "x-api-key": api_key}
        if bearer:
            self.headers["Authorization"] = "Bearer " + bearer
        elif user and password:
            self.headers["Authorization"] = "Basic " + base64.b64encode((user + ":" + password).encode()).decode()
        else:
            raise ScanError("Supply an existing Epicor user/password or bearer credential.")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)), NoRedirect())
        self.calls = 0

    def get(self, path):
        self.calls += 1
        if self.calls > 16:
            raise ScanError("Request budget exceeded.")
        url = self.base + "/api/v2/odata/" + self.company + "/" + path
        request = urllib.request.Request(url, headers=self.headers, method="GET")
        time.sleep(0.15)
        try:
            with self.opener.open(request, timeout=20) as response:
                data = response.read(MAX_RESPONSE + 1)
                if len(data) > MAX_RESPONSE:
                    return "too_large", None
                return "ok", data
        except urllib.error.HTTPError as error:
            # Never read, print, or export error bodies or request URLs.
            status = {401: "unauthorized", 403: "forbidden", 404: "not_exposed", 429: "rate_limited"}.get(error.code, "http_error")
            error.close()
            return status, None
        except (urllib.error.URLError, TimeoutError, OSError):
            return "network_error", None


def metadata_counts(body):
    body = body.decode("utf-8", errors="strict")
    if "\x00" in body or "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper():
        raise ValueError("DTD is not allowed")
    root = ET.fromstring(body)
    entities = list(root.iter(EDM + "EntityType"))
    if not entities:
        raise ValueError("No OData entities")
    fields = [p for e in entities for p in e.findall(EDM + "Property")]
    return {"entities": len(entities), "fields": len(fields),
            "custom_fields": sum(p.get("Name", "").endswith("_c") for p in fields)}


def scan(client):
    # Company value is checked locally and never exported from the response.
    path = "Erp.BO.CompanySvc/Companies?$top=1&$select=Company1&$filter=Company1%20eq%20%27" + client.company + "%27"
    status, body = client.get(path)
    try:
        company_ok = status == "ok" and json.loads(body)["value"][0]["Company1"] == client.company
    except (ValueError, TypeError, KeyError, IndexError):
        company_ok = False
    if not company_ok:
        raise ScanError("Company preflight failed (" + status + "). Check access, endpoint and company. No package created.")
    measurements = []
    for key, path in COUNTS.items():
        status, body = client.get(path)
        value = None
        if status == "ok":
            try:
                text = body.decode("ascii").strip()
                if not re.fullmatch(r"\d{1,12}", text):
                    raise ValueError("Invalid count")
                value = int(text)
            except (ValueError, UnicodeError):
                status = "invalid_response"
        measurements.append({"key": key, "status": status, "count": value})
        print(key + ": " + status)
    for key, path in METADATA.items():
        status, body = client.get(path)
        counts = None
        if status == "ok":
            try:
                counts = metadata_counts(body)
            except (ValueError, ET.ParseError):
                status = "invalid_response"
        measurements.append({"key": key, "status": status, "counts": counts})
        print(key + ": " + status)
    return {"measurements": measurements, "preflight": "ok"}


def package(config, summary, output_dir):
    stamp = datetime.now(timezone.utc).isoformat()
    docs = {
        "summary.json": canonical(summary),
        "self_evaluation.json": canonical({"assessment": "server_computed", "overall_score": None}),
        "opportunities.md": b"# Assessment pending\nUpload this package to Operis for a server-computed assessment.\n",
    }
    docs["manifest.json"] = canonical({
        "package_type": "operis.epicor.discovery", "schema_version": SCHEMA,
        "scanner_version": VERSION, "scan_mode": "metadata_only", "contains_credentials": False,
        "scan_context": config, "completed_at": stamp,
        "checksums": {name: hashlib.sha256(data).hexdigest() for name, data in docs.items()},
    })
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / ("operis-discovery-" + str(uuid.uuid4()) + ".zip")
    # Exclusive creation prevents stale output or overwriting a prior scan.
    with output.open("xb") as handle, zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in docs.items():
            archive.writestr(name, data)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="operis-scan-config.json")
    parser.add_argument("--out", default="results")
    parser.add_argument("--ca-file", help="Optional trusted organization CA bundle; TLS verification stays enabled")
    parser.add_argument("--base-url", help="HTTPS Epicor application URL (no credentials)")
    args = parser.parse_args()
    try:
        if Path(args.config).stat().st_size > 4096:
            raise ScanError("Configuration is too large.")
        config = json.loads(Path(args.config).read_text())
        context = config["context"]
        for key in ("tenant_id", "company_id", "scan_id"):
            uuid.UUID(context[key])
        if context["expires_at"] <= int(time.time()):
            raise ScanError("Download a fresh scan configuration from Operis.")
        base = args.base_url or os.environ.get("EPICOR_BASE_URL") or input("Epicor HTTPS application URL: ").strip()
        base_url(base)  # Validate destination before prompting for credentials.
        key = os.environ.get("EPICOR_API_KEY") or getpass.getpass("Epicor API key (hidden): ")
        bearer = os.environ.get("EPICOR_BEARER", "")
        user = "" if bearer else os.environ.get("EPICOR_USER") or input("Epicor username: ").strip()
        password = "" if bearer else os.environ.get("EPICOR_PASS") or getpass.getpass("Epicor password (hidden): ")
        client = Client(base, context["company_code"], key, user, password, bearer, args.ca_file)
        result = scan(client)
        output = package(config, result, args.out)
        print("Package created: " + str(output))
        print("Exports company binding, aggregate counts and coverage statuses only. Review the ZIP before upload.")
        return 0
    except ScanError as error:
        print(str(error), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError):
        print("Unable to read configuration or create output. Download a fresh configuration and check the output folder.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
