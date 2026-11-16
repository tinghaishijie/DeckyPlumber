"""Exercise the installer in a temporary sandbox with fake service/network tools."""

import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.geteuid() == 0, "Installer intentionally rejects root callers")
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "homebrew"
        self.plugin = self.home / "plugins/DeckyPlumber"
        self.plugin.mkdir(parents=True)
        (self.plugin / "old.txt").write_text("previous plugin")
        settings = self.home / "settings/DeckyPlumber"
        settings.mkdir(parents=True)
        (settings / "settings.json").write_text('{"mode":"xbox-elite"}')
        self.archive = self.root / "DeckyPlumber.tar.gz"
        with tarfile.open(self.archive, "w:gz") as tar:
            for name in ["main.py", "package.json", "plugin.json", "dist/index.js"]:
                data = b"fixture"
                info = tarfile.TarInfo("DeckyPlumber/" + name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.checksum = self.root / "DeckyPlumber.tar.gz.sha256"
        self.checksum.write_text(digest + "  DeckyPlumber.tar.gz\n")
        bindir = self.root / "bin"
        bindir.mkdir()
        scripts = {
            "sudo": '#!/bin/bash\nif [ "$1" = "-v" ]; then exit 0; fi\nexec "$@"\n',
            "systemctl": '''#!/bin/bash
printf '%s\n' "$*" >> "$FIXTURE_ROOT/services.log"
if [ "${FAIL_RESTART:-0}" = 1 ] && [ "$1" = restart ] && [ ! -f "$FIXTURE_ROOT/failed" ]; then
  touch "$FIXTURE_ROOT/failed"
  exit 1
fi
''',
            "curl": '''#!/bin/bash
if [ "${FAIL_DOWNLOAD:-0}" = 1 ]; then exit 22; fi
case "$2" in
  *.sha256) cp "$FIXTURE_ROOT/DeckyPlumber.tar.gz.sha256" "$4" ;;
  *.tar.gz) cp "$FIXTURE_ROOT/DeckyPlumber.tar.gz" "$4" ;;
  *) exit 23 ;;
esac
''',
        }
        for name, script in scripts.items():
            path = bindir / name
            path.write_text(script)
            path.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ["PATH"],
                        FIXTURE_ROOT=str(self.root), DECKY_HOME=str(self.home), VERSION="v0.1.9")

    def tearDown(self):
        self.temp.cleanup()

    def run_installer(self, **env):
        return subprocess.run(["bash", str(ROOT / "install.sh")],
                              env=dict(self.env, **env), text=True, capture_output=True)

    def test_success_preserves_settings(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.plugin / "dist/index.js").exists())
        self.assertFalse((self.plugin / "old.txt").exists())
        self.assertEqual((self.home / "settings/DeckyPlumber/settings.json").read_text(),
                         '{"mode":"xbox-elite"}')

    def test_download_failure_keeps_original_plugin_running(self):
        result = self.run_installer(FAIL_DOWNLOAD="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.plugin / "old.txt").exists())
        self.assertFalse((self.root / "services.log").exists())

    def test_checksum_failure_does_not_stop_decky(self):
        self.checksum.write_text("0" * 64 + "  DeckyPlumber.tar.gz\n")
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.plugin / "old.txt").exists())
        self.assertFalse((self.root / "services.log").exists())

    def test_restart_failure_rolls_back_previous_plugin(self):
        result = self.run_installer(FAIL_RESTART="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.plugin / "old.txt").exists())
        self.assertFalse((self.plugin / "dist/index.js").exists())
        self.assertEqual((self.root / "services.log").read_text().count("restart"), 2)
