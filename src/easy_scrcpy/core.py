from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import shutil

from .runtime import bundled_executable
from .i18n import LANGUAGES, tr


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    model: str = "Android"
    usb: bool = False

    @property
    def label(self) -> str:
        return f"{self.model.replace('_', ' ')} ({self.serial})"


def parse_devices(output: str) -> list[Device]:
    devices = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] == "List" or line.startswith("*"):
            continue
        if fields[1] not in {"device", "offline", "unauthorized", "no"}:
            continue
        metadata = dict(item.split(":", 1) for item in fields[2:] if ":" in item)
        devices.append(Device(
            fields[0], "no permissions" if fields[1] == "no" else fields[1],
            metadata.get("model", "Android"), "usb" in metadata,
        ))
    return devices


def is_network_or_emulator(serial: str) -> bool:
    return serial.startswith("emulator-") or ":" in serial or serial.endswith("._tcp")


class Presence:
    """One prompt per ready connection; failed scans must not be applied."""

    def __init__(self):
        self.devices: dict[str, Device] = {}
        self.prompted: set[str] = set()

    def update(self, devices: list[Device]) -> tuple[list[Device], set[str]]:
        current = {d.serial: d for d in devices if d.usb}
        lost = {s for s, d in self.devices.items()
                if d.state == "device" and (s not in current or current[s].state != "device")}
        self.prompted.intersection_update(current)
        ready = [d for d in current.values() if d.state == "device" and d.serial not in self.prompted]
        self.prompted.update(d.serial for d in ready)
        self.devices = current
        return ready, lost


@dataclass
class Settings:
    language: str = "auto"
    adb_path: str = ""
    scrcpy_path: str = ""
    prompt_on_connect: bool = True
    max_size: int = 1920
    max_fps: int = 60
    audio: bool = True
    disable_debug_on_stop: bool = False
    video_bit_rate: int = 8
    device_quality: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Settings":
        if not path.exists():
            return cls()
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError(tr("设置文件必须为 JSON 对象"))
        result = cls()
        for key in asdict(result):
            if key in values:
                value = values[key]
                if type(value) is not type(getattr(result, key)):
                    raise ValueError(tr("设置类型错误：{key}", key=key))
                setattr(result, key, value)
        if not 0 <= result.max_size <= 8192 or not 1 <= result.max_fps <= 240:
            raise ValueError(tr("投屏分辨率或帧率设置超出范围"))
        if result.language not in LANGUAGES:
            raise ValueError(tr("不支持的语言：{language}", language=result.language))
        if not 1 <= result.video_bit_rate <= 100:
            raise ValueError(tr("画质参数超出范围"))
        for serial, quality in result.device_quality.items():
            if not isinstance(serial, str):
                raise ValueError(tr("画质参数超出范围"))
            validate_quality(quality)
        return result

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)


def resolve_executable(name: str, configured: str = "") -> str | None:
    if configured.strip():
        path = Path(configured.strip()).expanduser()
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    bundled = bundled_executable(name)
    if bundled:
        return bundled
    found = shutil.which(name)
    if found:
        return found
    # Finder/login sessions do not inherit the interactive shell PATH.
    for folder in ("/opt/homebrew/bin", "/usr/local/bin", "~/Applications/platform-tools",
                   "~/Library/Android/sdk/platform-tools", "~/Android/Sdk/platform-tools",
                   "~/AppData/Local/Android/Sdk/platform-tools"):
        path = Path(folder).expanduser() / (name + ".exe" if os.name == "nt" else name)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def scrcpy_arguments(device: Device, settings: Settings) -> list[str]:
    quality = device_quality(device.serial, settings)
    args = [f"--serial={device.serial}", f"--window-title=Easy Scrcpy — {device.label}",
            f"--max-fps={quality['max_fps']}", f"--video-bit-rate={quality['video_bit_rate']}M"]
    if quality["max_size"]:
        args.append(f"--max-size={quality['max_size']}")
    if not settings.audio:
        args.append("--no-audio")
    return args


QUALITY_PRESETS = {
    "smooth": {"max_size": 1024, "max_fps": 30, "video_bit_rate": 2},
    "standard": {"max_size": 1920, "max_fps": 60, "video_bit_rate": 8},
    "high": {"max_size": 0, "max_fps": 60, "video_bit_rate": 16},
}
QUALITY_LABELS = {"default": "跟随全局设置", "smooth": "流畅", "standard": "标准", "high": "高清", "custom": "自定义"}


def validate_quality(quality):
    if not isinstance(quality, dict) or quality.get("profile") not in QUALITY_LABELS:
        raise ValueError(tr("画质参数超出范围"))
    if quality["profile"] == "custom":
        for key, low, high in (("max_size", 0, 8192), ("max_fps", 1, 240), ("video_bit_rate", 1, 100)):
            value = quality.get(key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(tr("画质参数超出范围"))


def device_quality(serial: str, settings: Settings) -> dict:
    selection = settings.device_quality.get(serial, {"profile": "default"})
    validate_quality(selection)
    profile = selection["profile"]
    if profile == "custom":
        return dict(selection)
    if profile in QUALITY_PRESETS:
        return {"profile": profile, **QUALITY_PRESETS[profile]}
    return {"profile": "default", "max_size": settings.max_size, "max_fps": settings.max_fps,
            "video_bit_rate": settings.video_bit_rate}
