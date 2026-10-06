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
    """USB/Wi-Fi transport presence; failed scans must not be applied."""

    def __init__(self):
        self.devices: dict[str, Device] = {}
        self.prompted: set[str] = set()

    def update(self, devices: list[Device]) -> tuple[list[Device], set[str]]:
        current = {d.serial: d for d in devices if not d.serial.startswith("emulator-")}
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
    audio_bit_rate: int = 128
    device_quality: dict = field(default_factory=dict)
    paired_devices: list = field(default_factory=list)
    device_orientation: dict = field(default_factory=dict)
    device_input: dict = field(default_factory=dict)

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
        if not 16 <= result.audio_bit_rate <= 512:
            raise ValueError(tr("画质参数超出范围"))
        for serial, quality in result.device_quality.items():
            if not isinstance(serial, str):
                raise ValueError(tr("画质参数超出范围"))
            validate_quality(quality)
        for record in result.paired_devices:
            if (not isinstance(record, dict) or not isinstance(record.get("guid"), str) or not record["guid"]
                    or any(not isinstance(record.get(k, ""), str) for k in ("name", "address", "paired_at"))):
                raise ValueError(tr("设置类型错误：{key}", key="paired_devices"))
        for serial, orientation in result.device_orientation.items():
            if not isinstance(serial, str) or orientation not in ORIENTATION_OPTIONS:
                raise ValueError(tr("方向参数超出范围"))
        for serial, options in result.device_input.items():
            if not isinstance(serial, str):
                raise ValueError(tr("设置类型错误：{key}", key="device_input"))
            validate_input(options)
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
    orientation = settings.device_orientation.get(device.serial, 0)
    if orientation:
        args.append(f"--capture-orientation=@{orientation}")
    if not settings.audio:
        args.append("--no-audio")
    else:
        args.append(f"--audio-bit-rate={quality['audio_bit_rate']}K")
    options = device_input(device.serial, settings)
    args.append(f"--keyboard={options['keyboard']}")
    if not options["clipboard_autosync"]:
        args.append("--no-clipboard-autosync")
    return args


QUALITY_PRESETS = {
    "smooth": {"max_size": 1024, "max_fps": 30, "video_bit_rate": 2},
    "standard": {"max_size": 1920, "max_fps": 60, "video_bit_rate": 8},
    "high": {"max_size": 0, "max_fps": 60, "video_bit_rate": 16},
}
QUALITY_LABELS = {"default": "跟随全局设置", "smooth": "流畅", "standard": "标准", "high": "高清", "custom": "自定义"}
ORIENTATION_OPTIONS = (0, 90, 180, 270)
RESOLUTION_OPTIONS = (0, 640, 800, 1024, 1280, 1440, 1920, 2560, 3840)
FPS_OPTIONS = (15, 24, 30, 45, 60, 90, 120)
VIDEO_BIT_RATE_OPTIONS = (1, 2, 4, 5, 8, 10, 12, 16, 24, 32)
AUDIO_BIT_RATE_OPTIONS = (64, 96, 128, 192, 256, 320)


def validate_quality(quality):
    if not isinstance(quality, dict) or quality.get("profile") not in QUALITY_LABELS:
        raise ValueError(tr("画质参数超出范围"))
    if quality["profile"] == "custom":
        for key, low, high in (("max_size", 0, 8192), ("max_fps", 1, 240), ("video_bit_rate", 1, 100)):
            value = quality.get(key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(tr("画质参数超出范围"))
        if "audio_bit_rate" in quality:
            value = quality["audio_bit_rate"]
            if type(value) is not int or not 16 <= value <= 512:
                raise ValueError(tr("画质参数超出范围"))


def device_quality(serial: str, settings: Settings) -> dict:
    selection = settings.device_quality.get(serial, {"profile": "default"})
    validate_quality(selection)
    profile = selection["profile"]
    if profile == "custom":
        return {"audio_bit_rate": settings.audio_bit_rate, **selection}
    if profile in QUALITY_PRESETS:
        return {"profile": profile, "audio_bit_rate": settings.audio_bit_rate, **QUALITY_PRESETS[profile]}
    return {"profile": "default", "max_size": settings.max_size, "max_fps": settings.max_fps,
            "video_bit_rate": settings.video_bit_rate, "audio_bit_rate": settings.audio_bit_rate}


INPUT_DEFAULTS = {"keyboard": "sdk", "clipboard_autosync": True}


def validate_input(options):
    if (not isinstance(options, dict) or options.get("keyboard") not in ("sdk", "uhid")
            or type(options.get("clipboard_autosync")) is not bool):
        raise ValueError(tr("设置类型错误：{key}", key="device_input"))


def device_input(serial, settings):
    options = settings.device_input.get(serial, INPUT_DEFAULTS)
    validate_input(options)
    return dict(options)
