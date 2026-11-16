"""Build the Decky archive from an explicit set of runtime files."""

import hashlib
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "out"
OUTPUT.mkdir(exist_ok=True)
archive = OUTPUT / "DeckyPlumber.tar.gz"
required = ["dist/index.js", "main.py", "package.json", "plugin.json"]
for name in required:
    if not (ROOT / name).is_file():
        raise SystemExit(f"Missing build input: {name}")

with tarfile.open(archive, "w:gz") as tar:
    for name in ["dist", "py_modules", "assets", "main.py", "package.json", "plugin.json", "README.md", "LICENSE"]:
        path = ROOT / name
        paths = sorted(path.rglob("*")) if path.is_dir() else [path]
        for item in paths:
            if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc":
                tar.add(item, arcname="DeckyPlumber/" + str(item.relative_to(ROOT)), recursive=False)

with tarfile.open(archive) as tar:
    names = set(tar.getnames())
    assert all("DeckyPlumber/" + name in names for name in required)
    assert "DeckyPlumber/py_modules/controller_recovery.py" in names
    assert not any("node_modules" in name or "__pycache__" in name for name in names)

digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(OUTPUT / "DeckyPlumber.tar.gz.sha256").write_text(f"{digest}  {archive.name}\n")
print(f"Packaged {archive} ({archive.stat().st_size} bytes)")
