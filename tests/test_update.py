import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGING = Path(__file__).resolve().parents[1] / "packaging"
sys.path.insert(0, str(PACKAGING))
spec = importlib.util.spec_from_file_location("update_scrcpy", PACKAGING / "update_scrcpy.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class UpdateTests(unittest.TestCase):
    def release(self):
        return {"tag_name": "v5.1", "draft": False, "prerelease": False,
                "assets": [{"name": pattern.format(version="5.1"), "digest": "sha256:" + "a" * 64}
                           for pattern, _ in update.ASSETS.values()]}

    def fetch(self, url):
        if "/releases/" in url:
            return json.dumps(self.release())
        if "/adb_" in url:
            return 'VERSION=37.0.2\nSHA256SUM=' + "b" * 64 + "\n"
        return "VERSION=1.2.3\n"

    def test_fetch_release_versions_and_checksums(self):
        with patch.object(update, "fetch_text", side_effect=self.fetch):
            lock = update.release_lock()
        self.assertEqual(lock["version"], "5.1")
        self.assertEqual(lock["platform_tools_version"], "37.0.2")
        self.assertEqual(set(lock["targets"]), set(update.ASSETS))
        self.assertTrue(all(x["sha256"] == "a" * 64 for x in lock["targets"].values()))

    def test_missing_platform_or_invalid_release_rejected(self):
        release = self.release()
        release["assets"].pop()
        with patch.object(update, "fetch_text", return_value=json.dumps(release)):
            with self.assertRaises(ValueError):
                update.release_lock()
        release = self.release()
        release["prerelease"] = True
        with patch.object(update, "fetch_text", return_value=json.dumps(release)):
            with self.assertRaises(ValueError):
                update.release_lock()
        with self.assertRaises(ValueError):
            update.release_lock("../../bad")

    def test_checksums_file_fallback(self):
        release = self.release()
        for asset in release["assets"]:
            asset["digest"] = None
        release["assets"].append({"name": "SHA256SUMS.txt"})
        def fetch(url):
            if url.endswith("SHA256SUMS.txt"):
                return "\n".join("c" * 64 + "  " + asset["name"] for asset in release["assets"][:-1])
            if "/releases/" in url:
                return json.dumps(release)
            return self.fetch(url)
        with patch.object(update, "fetch_text", side_effect=fetch):
            lock = update.release_lock("5.1")
        self.assertTrue(all(x["sha256"] == "c" * 64 for x in lock["targets"].values()))

    def setup_project(self, root):
        (root / "packaging").mkdir()
        old = json.loads((PACKAGING / "dependencies.json").read_text())
        (root / "packaging/dependencies.json").write_text(json.dumps(old))
        (root / "packaging/THIRD_PARTY_NOTICES.md").write_text((PACKAGING / "THIRD_PARTY_NOTICES.md").read_text())
        runtime = root / "vendor/macos-aarch64"
        runtime.mkdir(parents=True)
        (runtime / "original").write_text("user data retained")
        with patch.object(update, "fetch_text", side_effect=self.fetch):
            lock = update.release_lock()
        return lock

    def fake_prepare(self, target, cache):
        runtime = update.prepare_runtime.ROOT / "vendor" / target
        runtime.mkdir(parents=True)
        (runtime / "new").write_text("new verified bundle")
        return runtime

    def test_apply_preserves_backup_and_updates_notices(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = self.setup_project(root)
            with patch.object(update.prepare_runtime, "prepare", side_effect=self.fake_prepare):
                backup = update.apply_update(root, lock, ["macos-aarch64"])
            self.assertTrue((root / "vendor/macos-aarch64/new").exists())
            self.assertEqual((backup / "vendor/macos-aarch64/original").read_text(), "user data retained")
            self.assertEqual(json.loads((root / "packaging/dependencies.json").read_text()), lock)
            notices = (root / "packaging/THIRD_PARTY_NOTICES.md").read_text()
            self.assertIn("scrcpy 5.1:", notices)
            self.assertIn("platform-tools 37.0.2:", notices)
            self.assertIn("ffmpeg-1.2.3.tar.xz", notices)

    def test_download_failure_does_not_change_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = self.setup_project(root)
            original = (root / "packaging/dependencies.json").read_bytes()
            with patch.object(update.prepare_runtime, "prepare", side_effect=ValueError("hash mismatch")):
                with self.assertRaises(ValueError):
                    update.apply_update(root, lock, ["macos-aarch64"])
            self.assertEqual((root / "packaging/dependencies.json").read_bytes(), original)
            self.assertTrue((root / "vendor/macos-aarch64/original").exists())

    def test_install_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = self.setup_project(root)
            original = (root / "packaging/dependencies.json").read_bytes()
            rename = Path.rename
            def fail_once(path, destination):
                if "scrcpy-update-" in str(path) and path.name == "dependencies.json":
                    raise OSError("simulated installation failure")
                return rename(path, destination)
            with patch.object(update.prepare_runtime, "prepare", side_effect=self.fake_prepare), patch.object(Path, "rename", fail_once):
                with self.assertRaises(OSError):
                    update.apply_update(root, lock, ["macos-aarch64"])
            self.assertEqual((root / "packaging/dependencies.json").read_bytes(), original)
            self.assertTrue((root / "vendor/macos-aarch64/original").exists())
