"""Transport/launcher integration using an explicitly synthetic local HTTPS ERP.
Run: python -m unittest discover -s scanner -p 'test_*.py'
The Windows CI job exercises the actual batch file, including a path with spaces.
"""
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
import zipfile

HERE = Path(__file__).resolve().parent


class LauncherTests(unittest.TestCase):
    def test_https_launcher_exports_only_aggregates(self):
        openssl = shutil.which("openssl")
        if not openssl and os.name == "nt":
            candidate = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")
            if candidate.exists():
                openssl = str(candidate)
        self.assertTrue(openssl, "OpenSSL is required to generate an ephemeral local test certificate")
        with tempfile.TemporaryDirectory(prefix="operis scanner test ") as directory:
            root = Path(directory)
            for name in ("epicor_discover.py", "Run-Discovery.cmd"):
                shutil.copyfile(HERE / name, root / name)
            cert, key = root / "cert.pem", root / "key.pem"
            subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
                            "-out", str(cert), "-days", "1", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            requests = []
            class ERP(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    requests.append((self.command, self.path))
                    if self.headers.get("x-api-key") != "fixture-api-key":
                        self.send_error(401)
                        return
                    if "Companies?" in self.path:
                        body = b'{"value":[{"Company1":"TEST","private_fixture":"must-not-export"}]}'
                    elif self.path.endswith("/$count"):
                        body = b"12"
                    elif self.path.endswith("/$metadata"):
                        body = b'<Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"><EntityType Name="Synthetic"><Property Name="Example_c"/></EntityType></Schema>'
                    else:
                        self.send_error(404)
                        return
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                def log_message(self, *_):
                    pass
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ERP)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(cert, key)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            context = {"tenant_id": str(uuid.uuid4()), "company_id": str(uuid.uuid4()), "company_code":"TEST",
                       "scan_id":str(uuid.uuid4()),"issued_at":int(time.time()),"expires_at":int(time.time())+3600}
            (root / "operis-scan-config.json").write_text(json.dumps({"context":context,"signature":"0"*64}))
            env = {**os.environ, "EPICOR_BASE_URL": f"https://127.0.0.1:{server.server_port}/EpicorTest",
                   "EPICOR_API_KEY":"fixture-api-key","EPICOR_USER":"fixture-user","EPICOR_PASS":"fixture-password",
                   "SSL_CERT_FILE":str(cert), "NO_PROXY":"127.0.0.1,localhost", "no_proxy":"127.0.0.1,localhost"}
            env.pop("EPICOR_BEARER", None)
            command = ["cmd", "/c", "Run-Discovery.cmd"] if os.name == "nt" else [sys.executable, "epicor_discover.py"]
            try:
                completed = subprocess.run(command, cwd=root, env=env, input="\n", text=True, capture_output=True, timeout=60)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertEqual(len(requests), 12)
                self.assertTrue(all(method == "GET" for method, _ in requests))
                packages = list((root / "results").glob("*.zip"))
                self.assertEqual(len(packages), 1)
                with zipfile.ZipFile(packages[0]) as archive:
                    self.assertEqual(set(archive.namelist()), {"manifest.json","summary.json","self_evaluation.json","opportunities.md"})
                    data = b"".join(archive.read(n) for n in archive.namelist())
                    for forbidden in (b"fixture-password",b"fixture-api-key",b"must-not-export",b"127.0.0.1"):
                        self.assertNotIn(forbidden, data)
                    manifest=json.loads(archive.read("manifest.json"))
                    for name, checksum in manifest["checksums"].items():
                        self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),checksum)
                    measurements=json.loads(archive.read("summary.json"))["measurements"]
                    self.assertEqual(len(measurements),11)
                    self.assertTrue(all(m["status"]=="ok" for m in measurements))
                # Invalid credentials fail preflight and must not create a new ZIP.
                env["EPICOR_API_KEY"]="invalid-fixture-key"
                failed=subprocess.run(command,cwd=root,env=env,input="\n",text=True,capture_output=True,timeout=60)
                self.assertNotEqual(failed.returncode,0)
                self.assertEqual(list((root/"results").glob("*.zip")),packages)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
