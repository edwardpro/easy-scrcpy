"""Maintainer update tool. Preview by default; apply only with --apply."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request

import prepare_runtime

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com/repos/Genymobile/scrcpy"
ASSETS = {
    "macos-aarch64": ("scrcpy-macos-aarch64-v{version}.tar.gz", "darwin"),
    "macos-x86_64": ("scrcpy-macos-x86_64-v{version}.tar.gz", "darwin"),
    "windows-x86_64": ("scrcpy-win64-v{version}.zip", "win"),
    "windows-aarch64": ("scrcpy-winarm64-v{version}.zip", "win"),
    "linux-x86_64": ("scrcpy-linux-x86_64-v{version}.tar.gz", "linux"),
}


def fetch_text(url):
    headers = {"User-Agent": "EasyScrcpy-update/0.1"}
    if url.startswith(API) and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return response.read().decode("utf-8")


def script_value(text, name):
    match = re.search(rf"^{name}=[\"']?([a-zA-Z0-9.]+)", text, re.MULTILINE)
    if not match:
        raise ValueError(f"上游构建脚本无法识别 {name}，请人工检查，未更新文件")
    return match.group(1)


def release_lock(version=None):
    if version and not re.fullmatch(r"v?\d+\.\d+(?:\.\d+)?", version):
        raise ValueError("版本格式应为 5.0 或 v5.0（只接受稳定版）")
    endpoint = "/releases/tags/v" + version.removeprefix("v") if version else "/releases/latest"
    release = json.loads(fetch_text(API + endpoint))
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v\d+\.\d+(?:\.\d+)?", tag):
        raise ValueError("拒绝草稿或预发布版本")
    version = tag[1:]
    assets = {item["name"]: item for item in release["assets"]}
    checksums = None
    targets = {}
    for target, (pattern, adb_os) in ASSETS.items():
        name = pattern.format(version=version)
        if name not in assets:
            raise ValueError(f"官方发布缺少 {name}，请人工检查支持平台")
        digest = assets[name].get("digest") or ""
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            if checksums is None:
                checksum_asset = assets.get("SHA256SUMS.txt")
                if not checksum_asset:
                    raise ValueError("官方发布没有 SHA-256 校验信息")
                checksums = {}
                checksum_url = f"https://github.com/Genymobile/scrcpy/releases/download/{tag}/SHA256SUMS.txt"
                for line in fetch_text(checksum_url).splitlines():
                    parts = line.split()
                    if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
                        checksums[parts[1].lstrip("*")] = parts[0]
            digest = "sha256:" + checksums.get(name, "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError(f"缺少有效校验值：{name}")
        targets[target] = {"asset": name, "sha256": digest[7:], "adb_os": adb_os}
    base = f"https://raw.githubusercontent.com/Genymobile/scrcpy/{tag}/app/deps/"
    adb_versions, adb_hashes = set(), {}
    for system, script in (("darwin", "adb_macos.sh"), ("linux", "adb_linux.sh"), ("win", "adb_windows.sh")):
        text = fetch_text(base + script)
        adb_versions.add(script_value(text, "VERSION"))
        digest = script_value(text, "SHA256SUM")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"上游 ADB 校验值无效：{system}")
        adb_hashes[system] = digest
    if len(adb_versions) != 1:
        raise ValueError("上游三平台 ADB 版本不一致，需人工检查")
    components = {name: script_value(fetch_text(base + name + ".sh"), "VERSION")
                  for name in ("ffmpeg", "sdl", "dav1d")}
    return {"version": version, "platform_tools_version": adb_versions.pop(), "targets": targets,
            "platform_tools_sha256": adb_hashes, "component_versions": components}


def updated_notices(text, old, new):
    text = text.replace(f"scrcpy {old['version']}:", f"scrcpy {new['version']}:")
    text = text.replace(f"/v{old['version']}", f"/v{new['version']}")
    text = text.replace(f"platform-tools {old['platform_tools_version']}:",
                        f"platform-tools {new['platform_tools_version']}:")
    patterns = {"ffmpeg": (r"FFmpeg ([\d.]+):", "ffmpeg-"),
                "sdl": (r"SDL ([\d.]+):", "release-"),
                "dav1d": (r"dav1d ([\d.]+):", "/tree/")}
    for name, (pattern, url_prefix) in patterns.items():
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"第三方声明中未找到 {name}，请人工检查")
        previous = match.group(1)
        current = new["component_versions"][name]
        text = text.replace(match.group(0), match.group(0).replace(previous, current))
        text = text.replace(url_prefix + previous, url_prefix + current)
    return text


def apply_update(root, lock, targets, cache=None):
    """Prepare everything before changing live files; preserve originals and rollback."""
    old = json.loads((root / "packaging/dependencies.json").read_text(encoding="utf-8"))
    notices = updated_notices((root / "packaging/THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"), old, lock)
    cache = cache or root / ".cache/downloads"
    staging_parent = root / ".cache"
    staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scrcpy-update-", dir=staging_parent) as temp:
        staging = Path(temp)
        (staging / "packaging").mkdir()
        (staging / "packaging/dependencies.json").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        (staging / "packaging/THIRD_PARTY_NOTICES.md").write_text(notices, encoding="utf-8")
        original_root = prepare_runtime.ROOT
        try:
            prepare_runtime.ROOT = staging
            for target in targets:
                prepare_runtime.prepare(target, cache)
        finally:
            prepare_runtime.ROOT = original_root
        backup = root / ".cache/backups" / datetime.now(timezone.utc).strftime("scrcpy-%Y%m%dT%H%M%S%fZ")
        backup.mkdir(parents=True)
        changed = []
        try:
            for relative in [*[Path("vendor") / target for target in targets],
                             Path("packaging/THIRD_PARTY_NOTICES.md"), Path("packaging/dependencies.json")]:
                live, saved, ready = root / relative, backup / relative, staging / relative
                live.parent.mkdir(parents=True, exist_ok=True)
                saved.parent.mkdir(parents=True, exist_ok=True)
                existed = live.exists()
                if existed:
                    live.rename(saved)
                changed.append((live, saved, existed))
                ready.rename(live)
        except Exception:
            for live, saved, existed in reversed(changed):
                if live.exists():
                    failed = backup / "failed-new" / live.relative_to(root)
                    failed.parent.mkdir(parents=True, exist_ok=True)
                    live.rename(failed)
                if existed:
                    saved.rename(live)
            raise
    return backup


def main():
    prepare_runtime.configure_console()
    parser = argparse.ArgumentParser(description="预览或更新官方内置 scrcpy / ADB")
    parser.add_argument("--version", help="指定稳定版，例如 5.0；默认官方最新稳定版")
    parser.add_argument("--apply", action="store_true", help="确认应用更新；不指定时只预览")
    parser.add_argument("--target", action="append", choices=ASSETS, help="额外准备的平台（可重复）")
    parser.add_argument("--all-targets", action="store_true", help="准备全部平台")
    parser.add_argument("--cache", type=Path, help="下载缓存路径")
    args = parser.parse_args()
    try:
        old = json.loads((ROOT / "packaging/dependencies.json").read_text(encoding="utf-8"))
        lock = release_lock(args.version)
        # Refresh every existing managed platform to avoid leaving stale bundles.
        existing = [target for target in ASSETS if (ROOT / "vendor" / target).exists()]
        targets = list(ASSETS) if args.all_targets else sorted(set(existing + (args.target or [prepare_runtime.host_target()])))
        print(f"scrcpy: {old['version']} → {lock['version']}")
        print(f"ADB: {old['platform_tools_version']} → {lock['platform_tools_version']}")
        print("准备平台：" + ", ".join(targets))
        print(json.dumps(lock, ensure_ascii=False, indent=2))
        if not args.apply:
            print("仅预览，未修改文件。使用 --apply 确认更新。")
            return
        backup = apply_update(ROOT, lock, targets, args.cache)
        print(f"更新完成，旧文件保留在：{backup}")
        print("请运行测试并重新打包：python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec")
        print("已有 dist 安装包不会被此脚本修改。公开发布前请复核许可证与源代码材料。")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"更新失败：{error}\n")


if __name__ == "__main__":
    main()
