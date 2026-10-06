# Build on each target OS with: python -m PyInstaller packaging/EasyScrcpy.spec
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
sys.path.insert(0, str(root / "src"))
from easy_scrcpy.runtime import host_target
from easy_scrcpy import __version__

sys.path.insert(0, str(root / "packaging"))
from prepare_runtime import prepare
from prepare_icons import prepare_icons

runtime = prepare(host_target())
icons = prepare_icons(root) if (root / "assets/icon.png").is_file() else None
# Preserve the portable directory layout, including server, DLLs and notices.
# PyInstaller may reclassify / sign native executables during collection; the
# manifest records the original upstream files, not post-signing binary hashes.
data = [(str(p), str(Path("runtime") / p.relative_to(runtime).parent))
        for p in runtime.rglob("*") if p.is_file()]
data += [(str(p), "assets") for p in (root / "assets").glob("*.png")]
if icons:
    data.append((str(icons / "icon.png"), "assets/linux"))
native_imports = []
if sys.platform == "win32":
    native_imports = collect_submodules("windows_toasts") + collect_submodules("winrt")
elif sys.platform == "darwin":
    native_imports = ["UserNotifications", "Foundation", "objc", "AppKit"]
a = Analysis([str(root / "packaging/launcher.py")], pathex=[str(root / "src")],
             binaries=[], datas=data, hiddenimports=native_imports, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EasyScrcpy", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(icons / "icon.ico") if icons and sys.platform == "win32" else None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="EasyScrcpy")
if sys.platform == "darwin":
    app = BUNDLE(collection, name="EasyScrcpy.app", bundle_identifier="io.easy-scrcpy.app",
                 version=__version__,
                 icon=str(icons / "icon.icns") if icons else None,
                 info_plist={
                     "CFBundleVersion": __version__,
                     "LSUIElement": True, "NSHighResolutionCapable": True,
                     # macOS Local Network privacy: without these the bundled ADB
                     # server gets "No route to host" for wireless debugging.
                     "NSLocalNetworkUsageDescription":
                         "Easy Scrcpy connects to Android devices on your local network for wireless debugging and mirroring.",
                     "NSBonjourServices": ["_adb._tcp", "_adb-tls-connect._tcp", "_adb-tls-pairing._tcp"],
                 })
