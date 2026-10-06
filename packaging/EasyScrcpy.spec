# Build on each target OS with: python -m PyInstaller packaging/EasyScrcpy.spec
from pathlib import Path
import sys

root = Path(SPECPATH).parent
sys.path.insert(0, str(root / "src"))
from easy_scrcpy.runtime import host_target

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
a = Analysis([str(root / "packaging/launcher.py")], pathex=[str(root / "src")],
             binaries=[], datas=data, hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EasyScrcpy", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(icons / "icon.ico") if icons and sys.platform == "win32" else None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="EasyScrcpy")
if sys.platform == "darwin":
    app = BUNDLE(collection, name="EasyScrcpy.app", bundle_identifier="io.easy-scrcpy.app",
                 icon=str(icons / "icon.icns") if icons else None,
                 info_plist={"LSUIElement": True, "NSHighResolutionCapable": True})
