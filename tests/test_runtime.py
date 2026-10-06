import importlib.util
import io
import hashlib
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from easy_scrcpy.core import resolve_executable
from easy_scrcpy.runtime import bundled_executable, host_target, tool_environment

spec = importlib.util.spec_from_file_location("prepare_runtime", Path(__file__).resolve().parents[1] / "packaging/prepare_runtime.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class RuntimeTests(unittest.TestCase):
    def test_download_timeout_retries_from_scratch(self):
        payload = b"verified archive"
        class Interrupted(io.BytesIO):
            def read(self, size=-1):
                if self.tell():
                    raise TimeoutError("read timed out")
                return super().read(3)
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "archive.zip"
            destination.write_bytes(b"old cache")
            with patch.object(prepare.urllib.request, "urlopen", side_effect=[Interrupted(payload), io.BytesIO(payload)]) as request, patch.object(prepare.time, "sleep") as sleep:
                prepare.download("https://example.test/archive", destination, hashlib.sha256(payload).hexdigest())
            self.assertEqual(destination.read_bytes(), payload)
            self.assertFalse(destination.with_suffix(".zip.part").exists())
            self.assertEqual(request.call_count, 2)
            sleep.assert_called_once_with(2)

    def test_download_exhaustion_preserves_cache_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "archive.zip"
            destination.write_bytes(b"old cache")
            with patch.object(prepare.urllib.request, "urlopen", side_effect=TimeoutError("timeout")) as request, patch.object(prepare.time, "sleep") as sleep:
                with self.assertRaises(TimeoutError):
                    prepare.download("https://example.test/archive", destination, "0" * 64)
            self.assertEqual(request.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4])
            self.assertEqual(destination.read_bytes(), b"old cache")
            self.assertFalse(destination.with_suffix(".zip.part").exists())

    def test_download_hash_failure_is_not_retried_and_verified_cache_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "archive.zip"
            with patch.object(prepare.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")) as request, patch.object(prepare.time, "sleep") as sleep:
                with self.assertRaises(ValueError):
                    prepare.download("https://example.test/archive", destination, "0" * 64)
                request.assert_called_once()
                sleep.assert_not_called()
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_suffix(".zip.part").exists())
            destination.write_bytes(b"verified")
            with patch.object(prepare.urllib.request, "urlopen") as request:
                prepare.download("https://example.test/archive", destination, hashlib.sha256(b"verified").hexdigest())
                request.assert_not_called()

    def test_windows_license_normalized_without_removing_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            license_text = b"Original upstream license\r\n"
            (root / "LICENSE.txt").write_bytes(license_text)
            prepare.normalize_license(root)
            self.assertEqual((root / "LICENSE").read_bytes(), license_text)
            self.assertEqual((root / "LICENSE.txt").read_bytes(), license_text)
            (root / "LICENSE").write_bytes(b"existing license")
            prepare.normalize_license(root)
            self.assertEqual((root / "LICENSE").read_bytes(), b"existing license")

    def test_windows_cp1252_console_handles_unicode(self):
        output = io.BytesIO()
        stream = io.TextIOWrapper(output, encoding="cp1252")
        with patch.object(prepare.sys, "stdout", stream), patch.object(prepare.sys, "stderr", None):
            prepare.configure_console()
            print("下载 → 内置依赖", flush=True)
        self.assertEqual(output.getvalue().decode("utf-8").strip(), "下载 → 内置依赖")
        stream.close()

    def test_frozen_bundle_resolution_precedes_path(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            runtime.mkdir()
            binary = runtime / ("adb.exe" if sys.platform == "win32" else "adb")
            binary.write_text("test")
            binary.chmod(0o755)
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", temp, create=True):
                self.assertEqual(bundled_executable("adb"), str(binary))
                with patch("easy_scrcpy.core.shutil.which") as which:
                    self.assertEqual(resolve_executable("adb"), str(binary))
                    which.assert_not_called()
                self.assertIsNone(resolve_executable("adb", str(runtime / "missing")))

    def test_host_targets(self):
        for system, machine, expected in (("darwin", "arm64", "macos-aarch64"),
                                          ("win32", "AMD64", "windows-x86_64"),
                                          ("linux", "x86_64", "linux-x86_64")):
            with patch.object(sys, "platform", system), patch("easy_scrcpy.runtime.platform.machine", return_value=machine):
                self.assertEqual(host_target(), expected)
        with patch.object(sys, "platform", "linux"), patch("easy_scrcpy.runtime.platform.machine", return_value="aarch64"):
            with self.assertRaises(ValueError):
                host_target()

    def test_frozen_library_environment_restored(self):
        with patch.object(sys, "frozen", True, create=True), patch.dict(os.environ, {
                "LD_LIBRARY_PATH": "/pyinstaller", "LD_LIBRARY_PATH_ORIG": "/original",
                "DYLD_LIBRARY_PATH": "/pyinstaller"}, clear=True):
            env = tool_environment()
            self.assertEqual(env.value("LD_LIBRARY_PATH"), "/original")
            self.assertFalse(env.contains("DYLD_LIBRARY_PATH"))

    def test_download_hash_failure_and_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "download.zip"
            with patch.object(prepare.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")):
                with self.assertRaises(ValueError):
                    prepare.download("https://example.com/test", path, "0" * 64)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix(".zip.part").exists())
            path.write_bytes(b"cached")
            with patch.object(prepare.urllib.request, "urlopen") as fetch:
                prepare.download("https://example.com/test", path, prepare.sha256(path))
                fetch.assert_not_called()

    def test_archive_executable_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "valid.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                member = tarfile.TarInfo("bundle/adb")
                member.mode = 0o755
                member.size = 4
                output.addfile(member, io.BytesIO(b"test"))
            prepare.extract(archive, Path(temp) / "output")
            binary = Path(temp) / "output/bundle/adb"
            self.assertEqual(binary.read_bytes(), b"test")
            if os.name != "nt":
                self.assertTrue(os.access(binary, os.X_OK))

    def test_archive_traversal_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unsafe.zip"
            for name in ("../escape", "/absolute", "C:/escape", "..\\escape"):
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr(name, "bad")
                with self.assertRaises(ValueError):
                    prepare.extract(archive, Path(temp) / "out")
            archive = Path(temp) / "link.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                member = tarfile.TarInfo("link")
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
                output.addfile(member)
            with self.assertRaises(ValueError):
                prepare.extract(archive, Path(temp) / "out")
