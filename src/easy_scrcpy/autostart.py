"""Register login startup for the current user only; never needs admin rights."""

import os
from pathlib import Path
import plistlib
import subprocess
import sys

LABEL = "io.easy-scrcpy.app"
REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--background"]
    return [sys.executable, "-m", "easy_scrcpy", "--background"]


def desktop_exec(command: list[str]) -> str:
    def quote(arg):
        # Desktop Entry Exec quoting is not shell quoting. Escape literal field codes.
        arg = arg.replace("%", "%%")
        for char in ("\\", '"', "`", "$"):
            arg = arg.replace(char, "\\" + char)
        return '"' + arg + '"'
    return " ".join(quote(arg) for arg in command)


class Autostart:
    def __init__(self, platform: str | None = None, home: Path | None = None):
        self.platform = platform or sys.platform
        self.home = home or Path.home()

    @property
    def path(self) -> Path:
        if self.platform == "darwin":
            return self.home / "Library/LaunchAgents" / f"{LABEL}.plist"
        config = Path(os.environ.get("XDG_CONFIG_HOME", str(self.home / ".config")))
        return config / "autostart/easy-scrcpy.desktop"

    def enabled(self) -> bool:
        if self.platform == "win32":
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
                    winreg.QueryValueEx(key, "EasyScrcpy")
                return True
            except FileNotFoundError:
                return False
        return self.path.is_file()

    def set_enabled(self, enabled: bool):
        command = launch_command()
        if self.platform == "win32":
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
                if enabled:
                    winreg.SetValueEx(key, "EasyScrcpy", 0, winreg.REG_SZ, subprocess.list2cmdline(command))
                else:
                    try:
                        winreg.DeleteValue(key, "EasyScrcpy")
                    except FileNotFoundError:
                        pass
            return
        path = self.path
        if not enabled:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.platform == "darwin":
            data = plistlib.dumps({"Label": LABEL, "ProgramArguments": command,
                                  "RunAtLoad": True, "ProcessType": "Interactive"})
        else:
            data = ("[Desktop Entry]\nType=Application\nName=Easy Scrcpy\n"
                    f"Exec={desktop_exec(command)}\nTerminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n").encode("utf-8")
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
