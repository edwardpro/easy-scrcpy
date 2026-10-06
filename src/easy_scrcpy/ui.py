from dataclasses import replace

from PySide6.QtCore import Signal, Qt, QSize, QProcess, QTimer
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QAbstractItemView, QHeaderView, QComboBox, QToolButton, QStyle,
)

from .core import (Settings, resolve_executable, QUALITY_LABELS, device_quality, ORIENTATION_OPTIONS,
                   RESOLUTION_OPTIONS, FPS_OPTIONS, VIDEO_BIT_RATE_OPTIONS, AUDIO_BIT_RATE_OPTIONS, device_input)
from .i18n import LANGUAGES, tr, translate_widget
from .runtime import icon_path, tool_environment
from . import __version__

STATE_LABELS = {"device": "已就绪", "unauthorized": "请在手机上授权", "offline": "离线",
                 "no permissions": "缺少 USB 权限（检查 udev 规则）"}


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("关于"))
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Easy Scrcpy"))
        layout.addWidget(QLabel(tr("版本：{version}", version=__version__)))
        repository = QLabel('Git: <a href="https://github.com/edwardpro/easy-scrcpy">https://github.com/edwardpro/easy-scrcpy</a>')
        repository.setOpenExternalLinks(True)
        layout.addWidget(repository)
        close = QPushButton(tr("关闭"))
        close.setAccessibleName(tr("关闭"))
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)


def option_combo(options, current, suffix="", original=False):
    combo = QComboBox()
    combo.setEditable(False)
    # Preserve a valid saved value from older releases without silently replacing it.
    values = sorted(set(options) | {current})
    for value in values:
        combo.addItem(tr("原始分辨率") if original and value == 0 else f"{value}{suffix}", value)
    combo.setCurrentIndex(combo.findData(current))
    if original:
        combo.setProperty("i18n_original_resolution", True)
    return combo


def orientation_combo(current):
    combo = QComboBox()
    combo.setEditable(False)
    values = sorted(set(ORIENTATION_OPTIONS) | {current})
    for value in values:
        combo.addItem(tr("默认") if value == 0 else f"{value}°", value)
    combo.setCurrentIndex(combo.findData(current))
    combo.setToolTip(tr("锁定捕获方向，手机物理旋转不会带动投屏画面；修改会重启该设备投屏。"))
    combo.setAccessibleName(tr("方向"))
    return combo


class ControlWindow(QWidget):
    start_requested = Signal(str)
    stop_requested = Signal(str)
    stop_all_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    quality_requested = Signal(str, str)
    custom_quality_requested = Signal(str)
    wireless_requested = Signal()
    disconnect_wireless_requested = Signal(str)
    orientation_requested = Signal(str, int)
    input_requested = Signal(str)
    hidden_to_tray = Signal()

    def __init__(self, icon: QIcon):
        super().__init__()
        self.setWindowTitle("Easy Scrcpy")
        self.setWindowIcon(icon)
        self.resize(1120, 580)
        self.setMinimumSize(860, 460)
        self.device_view_key = None
        self.tray_available = True
        layout = QVBoxLayout(self)
        title = QLabel("Easy Scrcpy · Android 设备投屏")
        title.setStyleSheet("font-size: 22px; font-weight: 600; padding: 8px 0;")
        layout.addWidget(title)
        self.health = QLabel("正在检查运行环境…")
        self.health.setWordWrap(True)
        layout.addWidget(self.health)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        devices_tab = QWidget()
        devices_layout = QVBoxLayout(devices_tab)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["设备", "序列号", "状态", "画质", "方向", "操作"])
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(72)
        for column in (0, 1, 2):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        for column in (3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.verticalHeader().setMinimumSectionSize(56)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        devices_layout.addWidget(self.table)
        hint = QLabel("连接手机 → 开启开发者选项 / USB 调试 → 在手机上允许此电脑调试。\n"
                      "未开启 USB 调试的手机可能不会出现在列表中。拒绝投屏后可在这里手动启动。")
        hint.setWordWrap(True)
        devices_layout.addWidget(hint)
        quality_hint = QLabel("修改画质或方向会重启该设备投屏，不会关闭 USB 调试；只影响投屏画面，不修改手机屏幕。")
        quality_hint.setWordWrap(True)
        devices_layout.addWidget(quality_hint)
        tabs.addTab(devices_tab, "设备")
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.document().setMaximumBlockCount(1000)
        tabs.addTab(self.logs, "运行日志")
        buttons = QHBoxLayout()
        for label, signal in (("无线连接", self.wireless_requested), ("设置", self.settings_requested), ("停止全部投屏", self.stop_all_requested)):
            button = QPushButton(label)
            button.clicked.connect(signal.emit)
            buttons.addWidget(button)
        buttons.addStretch()
        quit_button = QPushButton("退出应用")
        quit_button.clicked.connect(self.quit_requested.emit)
        buttons.addWidget(quit_button)
        layout.addLayout(buttons)
        translate_widget(self)

    def update_devices(self, devices, manager):
        # ADB snapshots arrive every 2 seconds; don't destroy a user's open selector.
        key = repr((devices, sorted(manager.processes), sorted(manager.stopping), manager.settings))
        if key == self.device_view_key:
            return
        self.device_view_key = key
        self.table.setRowCount(len(devices))
        for row, device in enumerate(devices):
            running = device.serial in manager.processes
            state = tr("正在停止…" if device.serial in manager.stopping else "投屏中" if running else STATE_LABELS.get(device.state, device.state))
            connection = "USB" if device.usb else "Wi-Fi"
            for column, text in enumerate((f"{device.model.replace('_', ' ')} · {connection}", device.serial, state)):
                self.table.setItem(row, column, QTableWidgetItem(text))
            label = tr("停止投屏" if running else "开始投屏")
            button = QToolButton()
            button.setObjectName("mirrorActionButton")
            button.setFixedSize(40, 40)
            button.setIconSize(QSize(24, 24))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            icon = QIcon(str(icon_path("menu-stop-share.png" if running else "menu-start-share.png")))
            if icon.isNull():
                icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop if running else QStyle.StandardPixmap.SP_MediaPlay)
            button.setIcon(icon)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setEnabled(device.serial not in manager.stopping and (running or device.state == "device"))
            signal = self.stop_requested if running else self.start_requested
            button.clicked.connect(lambda checked=False, s=device.serial, target=signal: target.emit(s))
            quality = device_quality(device.serial, manager.settings)
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(6)
            combo = QComboBox()
            combo.setMinimumWidth(150)
            combo.setMinimumHeight(32)
            for profile, label in QUALITY_LABELS.items():
                combo.addItem(tr(label), profile)
            combo.setCurrentIndex(combo.findData(quality["profile"]))
            combo.setToolTip(tr("画质参数：最大边长 {size}，{fps} FPS，{bitrate} Mbps", size=quality["max_size"] or tr("原始分辨率"), fps=quality["max_fps"], bitrate=quality["video_bit_rate"]))
            combo.activated.connect(lambda index, s=device.serial, c=combo: self.quality_requested.emit(s, c.itemData(index)))
            layout.addWidget(combo)
            edit = QToolButton()
            edit.setObjectName("qualityConfigButton")
            edit.setFixedSize(40, 40)
            edit.setIconSize(QSize(24, 24))
            edit.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            config_icon = QIcon(str(icon_path("menu-config.png")))
            if config_icon.isNull():
                config_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
            edit.setIcon(config_icon)
            edit.setToolTip(tr("调整…"))
            edit.setAccessibleName(tr("自定义画质"))
            edit.clicked.connect(lambda checked=False, s=device.serial: self.custom_quality_requested.emit(s))
            layout.addWidget(edit)
            container.setEnabled(device.serial not in manager.stopping)
            self.table.setCellWidget(row, 3, container)
            orientation = orientation_combo(manager.settings.device_orientation.get(device.serial, 0))
            orientation.activated.connect(lambda index, s=device.serial, c=orientation: self.orientation_requested.emit(s, c.itemData(index)))
            orientation.setEnabled(device.serial not in manager.stopping)
            self.table.setCellWidget(row, 4, orientation)
            action_cell = QWidget()
            action_layout = QHBoxLayout(action_cell)
            action_layout.setContentsMargins(6, 6, 6, 6)
            if not device.usb:
                disconnect = QToolButton()
                disconnect.setObjectName("disconnectWirelessButton")
                disconnect.setFixedSize(40, 40)
                disconnect.setIconSize(QSize(24, 24))
                disconnect.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                disconnect_icon = QIcon(str(icon_path("menu-close-conn.png")))
                if disconnect_icon.isNull():
                    disconnect_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)
                disconnect.setIcon(disconnect_icon)
                disconnect.setToolTip(tr("断开无线连接"))
                disconnect.setAccessibleName(tr("断开无线连接"))
                disconnect.setEnabled(device.serial not in manager.stopping)
                disconnect.clicked.connect(lambda checked=False, s=device.serial: self.disconnect_wireless_requested.emit(s))
                action_layout.addWidget(disconnect, alignment=Qt.AlignmentFlag.AlignCenter)
            action_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
            input_button = QToolButton()
            input_button.setObjectName("keyboardSettingsButton")
            input_button.setFixedSize(40, 40)
            input_button.setIconSize(QSize(24, 24))
            input_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            input_icon = QIcon(str(icon_path("menu-kb-settings.png")))
            if input_icon.isNull():
                input_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
            input_button.setIcon(input_icon)
            input_button.setToolTip(tr("键盘输入…"))
            input_button.setAccessibleName(tr("键盘输入…"))
            input_button.setEnabled(device.state == "device" and device.serial not in manager.stopping)
            input_button.clicked.connect(lambda checked=False, s=device.serial: self.input_requested.emit(s))
            action_layout.addWidget(input_button, alignment=Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 5, action_cell)
        self.table.resizeColumnToContents(3)
        self.table.resizeColumnToContents(4)

    def retranslate(self):
        self.device_view_key = None
        translate_widget(self)

    def closeEvent(self, event: QCloseEvent):
        if self.tray_available:
            self.hide()
            self.hidden_to_tray.emit()
            event.ignore()
        else:
            event.ignore()
            self.quit_requested.emit()


class SettingsDialog(QDialog):
    def __init__(self, controller):
        super().__init__(controller.window)
        self.controller = controller
        self.setWindowTitle("设置")
        self.resize(580, 350)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.language = QComboBox()
        for code, label in LANGUAGES.items():
            self.language.addItem(tr("跟随系统") if code == "auto" else label, code)
        self.language.setCurrentIndex(self.language.findData(controller.settings.language))
        form.addRow("语言", self.language)
        self.adb = QLineEdit(controller.settings.adb_path)
        self.scrcpy = QLineEdit(controller.settings.scrcpy_path)
        for label, edit, name in (("ADB 路径", self.adb, "adb"), ("scrcpy 路径", self.scrcpy, "scrcpy")):
            edit.setPlaceholderText("留空使用内置版本；可指定外部可执行文件")
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(edit)
            browse = QPushButton("浏览…")
            browse.clicked.connect(lambda checked=False, e=edit, n=name: self.browse(e, n))
            row_layout.addWidget(browse)
            form.addRow(label, row)
        self.autostart = QCheckBox("用户登录后自动启动并常驻托盘")
        try:
            self.autostart.setChecked(controller.autostart.enabled())
        except OSError as error:
            self.autostart.setEnabled(False)
            self.autostart.setToolTip(str(error))
        form.addRow("登录自启动", self.autostart)
        self.prompt = QCheckBox("USB 设备就绪时询问是否投屏")
        self.prompt.setChecked(controller.settings.prompt_on_connect)
        form.addRow("设备连接", self.prompt)
        self.disable_debug = QCheckBox("停止投屏时尝试关闭 USB 调试")
        self.disable_debug.setChecked(controller.settings.disable_debug_on_stop)
        form.addRow("USB 调试", self.disable_debug)
        warning = QLabel("默认关闭。部分手机会拒绝；成功后影响该手机的所有 ADB 连接，下次需在手机上手动开启 USB 调试。")
        warning.setWordWrap(True)
        form.addRow(warning)
        self.size = option_combo(RESOLUTION_OPTIONS, controller.settings.max_size, " px", original=True)
        form.addRow("最大画面边长", self.size)
        self.fps = option_combo(FPS_OPTIONS, controller.settings.max_fps, " FPS")
        form.addRow("最大帧率", self.fps)
        self.bitrate = option_combo(VIDEO_BIT_RATE_OPTIONS, controller.settings.video_bit_rate, " Mbps")
        form.addRow("视频码率", self.bitrate)
        self.audio_bitrate = option_combo(AUDIO_BIT_RATE_OPTIONS, controller.settings.audio_bit_rate, " kbps")
        form.addRow("音频码率", self.audio_bitrate)
        self.audio = QCheckBox("转发音频（需要 Android 11 或更高）")
        self.audio.setChecked(controller.settings.audio)
        self.audio_bitrate.setEnabled(self.audio.isChecked())
        self.audio.toggled.connect(self.audio_bitrate.setEnabled)
        form.addRow("音频", self.audio)
        note = QLabel("关闭窗口仍会常驻托盘。投屏参数修改对下一次启动生效。\n"
                      "自启动使用当前安装位置；移动应用或虚拟环境后请重新设置。")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        translate_widget(self)

    def browse(self, edit, name):
        path, _ = QFileDialog.getOpenFileName(self, tr("选择 {name} 可执行文件", name=name), edit.text())
        if path:
            edit.setText(path)

    def save(self):
        for name, edit in (("adb", self.adb), ("scrcpy", self.scrcpy)):
            if edit.text().strip() and not resolve_executable(name, edit.text()):
                self.controller.show_error(tr("{name} 路径不是可执行文件。", name=name))
                return
        settings = replace(self.controller.settings, adb_path=self.adb.text().strip(),
                           scrcpy_path=self.scrcpy.text().strip(), prompt_on_connect=self.prompt.isChecked(),
                            max_size=self.size.currentData(), max_fps=self.fps.currentData(), audio=self.audio.isChecked(),
                           language=self.language.currentData(), disable_debug_on_stop=self.disable_debug.isChecked(),
                            video_bit_rate=self.bitrate.currentData(), audio_bit_rate=self.audio_bitrate.currentData())
        previous_autostart = None
        try:
            if self.autostart.isEnabled():
                previous_autostart = self.controller.autostart.enabled()
                self.controller.autostart.set_enabled(self.autostart.isChecked())
            settings.save(self.controller.config_path)
        except (OSError, ValueError) as error:
            rollback_error = ""
            if previous_autostart is not None:
                try:
                    self.controller.autostart.set_enabled(previous_autostart)
                except OSError as rollback:
                    rollback_error = tr("\n自启动恢复失败：{error}", error=rollback)
            self.controller.show_error(tr("无法保存设置") + "\n" + str(error) + rollback_error)
            return
        self.controller.apply_settings(settings)
        self.accept()


class QualityDialog(QDialog):
    def __init__(self, device, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("自定义画质")
        layout = QVBoxLayout(self)
        label = QLabel(device.label)
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label)
        form = QFormLayout()
        layout.addLayout(form)
        quality = device_quality(device.serial, settings)
        self.size = option_combo(RESOLUTION_OPTIONS, quality["max_size"], " px", original=True)
        form.addRow("最大画面边长", self.size)
        self.fps = option_combo(FPS_OPTIONS, quality["max_fps"], " FPS")
        form.addRow("最大帧率", self.fps)
        self.bitrate = option_combo(VIDEO_BIT_RATE_OPTIONS, quality["video_bit_rate"], " Mbps")
        form.addRow("视频码率", self.bitrate)
        self.audio_bitrate = option_combo(AUDIO_BIT_RATE_OPTIONS, quality["audio_bit_rate"], " kbps")
        self.audio_bitrate.setEnabled(settings.audio)
        form.addRow("音频码率", self.audio_bitrate)
        note = QLabel("修改画质会重启该设备投屏，不会关闭 USB 调试；只影响投屏画面，不修改手机屏幕分辨率。")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        translate_widget(self)

    def quality(self):
        return {"profile": "custom", "max_size": self.size.currentData(), "max_fps": self.fps.currentData(),
                "video_bit_rate": self.bitrate.currentData(), "audio_bit_rate": self.audio_bitrate.currentData()}


class InputDialog(QDialog):
    def __init__(self, device, settings, parent):
        super().__init__(parent)
        self.device = device
        self.settings = settings
        self.command = None
        self.setWindowTitle("键盘输入")
        self.resize(600, 420)
        layout = QVBoxLayout(self)
        label = QLabel(device.label)
        label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(label)
        form = QFormLayout()
        layout.addLayout(form)
        options = device_input(device.serial, settings)
        self.keyboard = QComboBox()
        self.keyboard.addItem("兼容键盘（SDK）", "sdk")
        self.keyboard.addItem("物理键盘（UHID，推荐）", "uhid")
        self.keyboard.setCurrentIndex(self.keyboard.findData(options["keyboard"]))
        form.addRow("键盘模式", self.keyboard)
        self.clipboard = QCheckBox("自动同步剪贴板")
        self.clipboard.setChecked(options["clipboard_autosync"])
        form.addRow(self.clipboard)
        for text in INPUT_GUIDANCE:
            note = QLabel(text)
            note.setWordWrap(True)
            layout.addWidget(note)
        self.physical = QPushButton("打开手机物理键盘设置")
        self.physical.clicked.connect(self.open_physical_settings)
        layout.addWidget(self.physical)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.timeout)
        self.finished.connect(self.cleanup)
        self.retranslate()

    def retranslate(self):
        translate_widget(self)
        for index, source in enumerate(("兼容键盘（SDK）", "物理键盘（UHID，推荐）")):
            self.keyboard.setItemText(index, tr(source))

    def options(self):
        return {"keyboard": self.keyboard.currentData(), "clipboard_autosync": self.clipboard.isChecked()}

    def open_physical_settings(self):
        if self.command is not None:
            return
        adb = resolve_executable("adb", self.settings.adb_path)
        if not adb:
            self.status.setText(tr("无法打开物理键盘设置"))
            return
        command = QProcess(self)
        self.command = command
        command.setProgram(adb)
        command.setArguments(["-s", self.device.serial, "shell", "am", "start", "-a",
                              "android.settings.HARD_KEYBOARD_SETTINGS"])
        command.setProcessEnvironment(tool_environment())
        command.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        command.finished.connect(self.command_finished)
        command.errorOccurred.connect(lambda error: self.command_finished(-1, QProcess.ExitStatus.CrashExit)
                                      if error == QProcess.ProcessError.FailedToStart else None)
        self.physical.setEnabled(False)
        self.status.clear()
        self.timer.start(5000)
        command.start()

    def command_finished(self, code, status):
        if self.command is None:
            return
        output = bytes(self.command.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        failed = code != 0 or status != QProcess.ExitStatus.NormalExit or "error" in output.lower() or "exception" in output.lower()
        self.status.setText(tr("无法打开物理键盘设置") if failed else tr("请在手机上选择物理键盘布局"))
        if failed and output:
            self.status.setText(self.status.text() + "\n" + output)
        self.cleanup()
        self.physical.setEnabled(True)

    def timeout(self):
        self.status.setText(tr("无法打开物理键盘设置"))
        self.cleanup()
        self.physical.setEnabled(True)

    def cleanup(self, *_):
        self.timer.stop()
        if self.command is not None:
            command, self.command = self.command, None
            command.finished.disconnect()
            command.errorOccurred.disconnect()
            if command.state() != QProcess.ProcessState.NotRunning:
                command.kill()
            command.deleteLater()


INPUT_GUIDANCE = (
    "先点击投屏窗口中的手机输入框，保持投屏窗口焦点，再用电脑键盘输入。保存会重启该设备投屏。",
    "UHID 使用手机输入法处理中文和日语；首次请配置手机物理键盘布局。若设备不支持 UHID，请切回 SDK（主要支持 ASCII）。",
    "电脑输入法直接提交中文可能无法输入。请先复制文字，点击手机输入框，再在投屏窗口按 MOD+V 粘贴文本：macOS 为左 Command+V，Windows / Linux 为左 Alt+V 或左 Super+V。部分安全输入框禁止粘贴。",
    "自动同步开启时也可用 Ctrl+V；关闭后请用 MOD+V 主动传输并粘贴电脑文本。仅支持文本，不支持图片或视频剪贴板；需 Android 7 或更高。注意敏感内容。",
)
