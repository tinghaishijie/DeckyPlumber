#!/usr/bin/env bash
set -euo pipefail

VERSION=${VERSION:-LATEST}
REPO=tinghaishijie/DeckyPlumber
DECKY_HOME=${DECKY_HOME:-"$HOME/homebrew"}

if [ "$EUID" -eq 0 ]; then
  echo "Run as your normal desktop user, not root." >&2
  exit 1
fi
if [ ! -d "$DECKY_HOME/plugins" ]; then
  echo "Decky Loader was not found at $DECKY_HOME. Install Decky first." >&2
  exit 1
fi

workdir=$(mktemp -d)
backup_moved=0
new_installed=0
service_stopped=0
installed=0
cleanup() {
  status=$?
  if [ "$installed" -eq 0 ]; then
    if [ "$new_installed" -eq 1 ]; then
      sudo rm -rf -- "$DECKY_HOME/plugins/DeckyPlumber"
    fi
    if [ "$backup_moved" -eq 1 ]; then
      sudo mv -- "$workdir/previous" "$DECKY_HOME/plugins/DeckyPlumber" || {
        echo "Restore the previous plugin from $workdir/previous." >&2
        return 1
      }
    fi
  fi
  if [ "$service_stopped" -eq 1 ]; then
    sudo systemctl restart plugin_loader.service || true
  fi
  sudo rm -rf -- "$workdir"
  return "$status"
}
trap cleanup EXIT

if [ "$VERSION" = LATEST ]; then
  curl -fLsS "https://api.github.com/repos/$REPO/releases/latest" -o "$workdir/release.json"
  VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tag_name"])' "$workdir/release.json")
fi
base="https://github.com/$REPO/releases/download/$VERSION"
curl -fLsS "$base/DeckyPlumber.tar.gz" -o "$workdir/DeckyPlumber.tar.gz"
curl -fLsS "$base/DeckyPlumber.tar.gz.sha256" -o "$workdir/DeckyPlumber.tar.gz.sha256"
python3 - "$workdir" <<'PY'
import hashlib
from pathlib import Path
import sys
import tarfile

root = Path(sys.argv[1])
archive = root / "DeckyPlumber.tar.gz"
expected = (root / "DeckyPlumber.tar.gz.sha256").read_text().split()[0]
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit("Archive checksum mismatch")
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        parts = Path(member.name).parts
        if not parts or parts[0] != "DeckyPlumber" or ".." in parts or not member.isfile():
            raise SystemExit("Unexpected archive member: " + member.name)
    for name in ["main.py", "package.json", "plugin.json", "dist/index.js"]:
        tar.getmember("DeckyPlumber/" + name)
    tar.extractall(root / "staged")
PY

sudo -v
sudo systemctl stop plugin_loader.service
service_stopped=1
if [ -d "$DECKY_HOME/plugins/DeckyPlumber" ]; then
  sudo mv -- "$DECKY_HOME/plugins/DeckyPlumber" "$workdir/previous"
  backup_moved=1
fi
sudo mv -- "$workdir/staged/DeckyPlumber" "$DECKY_HOME/plugins/DeckyPlumber"
new_installed=1
sudo systemctl restart plugin_loader.service
service_stopped=0
installed=1
echo "Installed DeckyPlumber $VERSION. Saved settings were preserved. Reboot once before testing."
