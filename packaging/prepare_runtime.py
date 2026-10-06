"""Download verified official portable releases; preserve their complete contents."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from easy_scrcpy.runtime import host_target


def configure_console():
    """Windows redirected stdout can default to CP1252 even in CI."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _digest(stream)


def _digest(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path, expected: str):
    if destination.is_file() and sha256(destination) == expected:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    configure_console()
    print(f"下载 {url}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "EasyScrcpy-build/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        if sha256(partial) != expected:
            raise ValueError(f"SHA-256 校验失败：{destination.name}")
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def safe_path(root: Path, member: str) -> Path:
    path = PurePosixPath(member)
    if path.is_absolute() or ".." in path.parts or "\\" in member or ":" in member:
        raise ValueError(f"不安全的归档路径：{member}")
    return root.joinpath(*path.parts)


def extract(archive: Path, root: Path):
    """Reject links and traversal rather than trusting archive extractall."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                path = safe_path(root, member.filename)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError("归档中不允许符号链接")
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(member) as input_file, path.open("wb") as output:
                        shutil.copyfileobj(input_file, output)
                    path.chmod(0o755 if mode & 0o111 else 0o644)
    else:
        with tarfile.open(archive) as source:
            for member in source:
                path = safe_path(root, member.name)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as input_file, path.open("wb") as output:
                        shutil.copyfileobj(input_file, output)
                    path.chmod(0o755 if member.mode & 0o111 else 0o644)
                else:
                    raise ValueError("归档中只允许普通文件与目录")


def validate(root: Path, target: str):
    extension = ".exe" if target.startswith("windows-") else ""
    for name in ("adb" + extension, "scrcpy" + extension, "scrcpy-server", "LICENSE",
                 "licenses/platform-tools-NOTICE.txt", "THIRD_PARTY_NOTICES.md"):
        if not (root / name).is_file():
            raise ValueError(f"内置依赖不完整：缺少 {name}")
    if extension:
        for name in ("AdbWinApi.dll", "AdbWinUsbApi.dll"):
            if not (root / name).is_file():
                raise ValueError(f"缺少 ADB 配套文件：{name}")


def normalize_license(bundle: Path):
    """Windows releases use LICENSE.txt; preserve it and add a common alias."""
    if not (bundle / "LICENSE").is_file() and (bundle / "LICENSE.txt").is_file():
        shutil.copy2(bundle / "LICENSE.txt", bundle / "LICENSE")


def prepare(target: str, cache: Path | None = None) -> Path:
    configure_console()
    lock = json.loads((ROOT / "packaging/dependencies.json").read_text(encoding="utf-8"))
    asset = lock["targets"][target]
    destination = ROOT / "vendor" / target
    manifest = {"target": target, "scrcpy_version": lock["version"],
                "scrcpy_sha256": asset["sha256"], "platform_tools_version": lock["platform_tools_version"],
                "platform_tools_sha256": lock["platform_tools_sha256"][asset["adb_os"]]}
    if destination.exists():
        validate(destination, target)
        existing = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
        if any(existing.get(k) != v for k, v in manifest.items()):
            raise ValueError(f"已有不同版本的依赖，请先移动 {destination} 再重新构建")
        for name, digest in existing["files"].items():
            if sha256(safe_path(destination, name)) != digest:
                raise ValueError(f"内置文件已改变：{name}；请移动依赖目录后重新准备")
        return destination
    cache = cache or ROOT / ".cache/downloads"
    archive = cache / asset["asset"]
    download(f"https://github.com/Genymobile/scrcpy/releases/download/v{lock['version']}/{asset['asset']}",
             archive, asset["sha256"])
    tools_name = f"platform-tools_r{lock['platform_tools_version']}-{asset['adb_os']}.zip"
    tools_archive = cache / tools_name
    download(f"https://dl.google.com/android/repository/{tools_name}", tools_archive,
             manifest["platform_tools_sha256"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=destination.parent) as temp:
        staging = Path(temp)
        extract(archive, staging / "scrcpy")
        extract(tools_archive, staging / "platform")
        extracted = staging / "scrcpy" / asset["asset"].removesuffix(".tar.gz").removesuffix(".zip")
        bundle = staging / "runtime"
        shutil.copytree(extracted, bundle)
        normalize_license(bundle)
        # The official scrcpy release already includes the matching ADB binary and
        # Windows DLLs. Google's complete NOTICE is not included there: retain it.
        notices = bundle / "licenses"
        notices.mkdir(exist_ok=True)
        shutil.copy2(staging / "platform/platform-tools/NOTICE.txt", notices / "platform-tools-NOTICE.txt")
        shutil.copy2(ROOT / "packaging/THIRD_PARTY_NOTICES.md", bundle / "THIRD_PARTY_NOTICES.md")
        if not target.startswith("windows-"):
            for name in ("adb", "scrcpy"):
                (bundle / name).chmod(0o755)
        validate(bundle, target)
        manifest["files"] = {str(p.relative_to(bundle).as_posix()): sha256(p)
                             for p in sorted(bundle.rglob("*")) if p.is_file()}
        (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        bundle.rename(destination)
    print(f"内置依赖已准备：{destination}", flush=True)
    return destination


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="准备内置 scrcpy / ADB，仅构建时联网")
    parser.add_argument("--target", choices=json.loads((ROOT / "packaging/dependencies.json").read_text(encoding="utf-8"))["targets"])
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    prepare(args.target or host_target(), args.cache)


if __name__ == "__main__":
    main()
