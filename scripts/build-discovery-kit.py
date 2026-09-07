"""Deterministic public download, containing reviewed source only."""
from pathlib import Path
import hashlib
import zipfile
root = Path(__file__).resolve().parents[1]
dest = root / 'apps/web/public/kits'
dest.mkdir(parents=True, exist_ok=True)
path = dest / 'operis-epicor-discovery-0.3.0.zip'
with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for name in ('epicor_discover.py', 'Run-Discovery.cmd', 'README.md'):
        item = zipfile.ZipInfo(name, (2026, 9, 7, 0, 0, 0))
        item.compress_type = zipfile.ZIP_DEFLATED
        item.external_attr = 0o100644 << 16
        archive.writestr(item, (root / 'scanner' / name).read_bytes())
sha = hashlib.sha256(path.read_bytes()).hexdigest()
(dest / (path.name + '.sha256')).write_text(sha + '  ' + path.name + '\n')
print(sha)
