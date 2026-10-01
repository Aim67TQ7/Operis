#!/usr/bin/env python3
"""Create a separate customer plugin copy without storing credentials."""

import argparse
import ipaddress
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def validate_endpoint(endpoint):
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.path or parsed.path == "/":
        raise ValueError("Use the customer's full HTTPS MCP endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Keep credentials, query strings and fragments out of the endpoint")
    if any(character.isspace() for character in endpoint) or "\\" in endpoint:
        raise ValueError("Endpoint contains invalid characters")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Endpoint has an invalid port") from None
    if port not in {None, 443}:
        raise ValueError("Use a public HTTPS endpoint on port 443")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".example", ".test", ".invalid")):
        raise ValueError("Use a customer-owned public hostname")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host):
            raise ValueError("Use a valid public hostname") from None
        if host in {"example.com", "example.org", "example.net"} or host.endswith((".example.com", ".example.org", ".example.net")):
            raise ValueError("Example domains are not customer connections")
        if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in host.split(".")):
            raise ValueError("Use a valid public hostname")
    else:
        if not address.is_global:
            raise ValueError("Use a customer-owned public endpoint")
    return endpoint


def configure(output, endpoint, registered_app_id=None):
    if (PLUGIN_ROOT / "mcp.json").exists() or (PLUGIN_ROOT / ".app.json").exists():
        raise ValueError("Configure each customer from the unconfigured base package")
    endpoint = validate_endpoint(endpoint)
    if registered_app_id and not re.fullmatch(r"(?:plugin_asdk_app_|connector_)[A-Za-z0-9_-]+", registered_app_id):
        raise ValueError("Provide the real registered MCP app ID from ChatGPT")
    output = Path(output).resolve()
    if output == PLUGIN_ROOT or PLUGIN_ROOT in output.parents:
        raise ValueError("Write the customer copy outside the distributable source folder")
    if output.exists():
        raise ValueError("Output already exists; choose a new customer folder")
    shutil.copytree(PLUGIN_ROOT, output, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "tests"))
    mcp = {"$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
           "mcpServers": {"operis_customer_finance": {"type": "streamable-http", "url": endpoint}}}
    (output / "mcp.json").write_text(json.dumps(mcp, indent=2) + "\n")
    if registered_app_id:
        apps = {"apps": {"operis_customer_finance": {"id": registered_app_id, "required": True}}}
        (output / ".app.json").write_text(json.dumps(apps, indent=2) + "\n")
        manifest_path = output / "plugin.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["extensions"]["com.openai"]["apps"] = "./.app.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "CUSTOMER_CONNECTION.md").write_text(
        "# Customer connection status\n\n"
        "This copy has a configured endpoint, not a verified integration.\n"
        "Authenticate through the MCP client. No credentials are stored here.\n"
        "Before use, verify the authenticated customer/company scope, permitted read tools,\n"
        "revocation behavior, cross-company denials and a reconciled financial query.\n"
        "The server must enforce permissions; plugin instructions do not enforce isolation.\n"
        "Do not upload this customer-specific copy to the public source repository.\n"
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--registered-app-id")
    args = parser.parse_args()
    try:
        output = configure(args.output, args.endpoint, args.registered_app_id)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"Created customer copy: {output}. Authentication and live verification remain required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
