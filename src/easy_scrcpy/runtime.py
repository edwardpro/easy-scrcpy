"""Locate the private, platform-specific tool bundle in source and frozen builds."""

import os
from pathlib import Path
import platform
import sys


def icon_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        root = Path(__file__).resolve().parents[2]
    return root / "assets" / name


def host_target() -> str:
    arch = platform.machine().lower()
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(arch, arch)
    system = {"darwin": "macos", "win32": "windows", "linux": "linux"}.get(sys.platform)
    target = f"{system}-{arch}"
    if target not in {"macos-aarch64", "macos-x86_64", "windows-x86_64", "windows-aarch64", "linux-x86_64"}:
        raise ValueError(f"暂不支持此平台的内置依赖：{target}")
    return target


def bundle_directory() -> Path | None:
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "runtime"
    else:
        try:
            root = Path(__file__).resolve().parents[2] / "vendor" / host_target()
        except ValueError:
            return None
    return root if root.is_dir() else None


def bundled_executable(name: str) -> str | None:
    root = bundle_directory()
    if root is None:
        return None
    path = root / (name + ".exe" if sys.platform == "win32" else name)
    return str(path) if path.is_file() and os.access(path, os.X_OK) else None


def tool_environment():
    from PySide6.QtCore import QProcessEnvironment

    environment = QProcessEnvironment.systemEnvironment()
    if getattr(sys, "frozen", False):
        # PyInstaller's library search path is for Python/Qt, not external programs.
        # In particular it must not make scrcpy load Qt's bundled multimedia libs.
        for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            original = environment.value(key + "_ORIG")
            if original:
                environment.insert(key, original)
            else:
                environment.remove(key)
    return environment
