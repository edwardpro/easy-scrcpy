from dataclasses import replace

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QAbstractItemView, QHeaderView, QComboBox,
)

from .core import Settings, resolve_executable, QUALITY_LABELS, device_quality
from .i18n import LANGUAGES, tr, translate_widget

STATE_LABELS = {"device": "已就绪", "unauthorized": "请在手机上授权", "offline": "离线",
                "no permissions": "缺少 USB 权限（检查 udev 规则）"}


class ControlWindow(QWidget):
    start_requested = Signal(str)
    stop_requested = Signal(str)
    stop_all_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    quality_requested = Signal(str, str)
    custom_quality_requested = Signal(str)

    def __init__(self, icon: QIcon):
        super().__init__()
        self.setWindowTitle("Easy Scrcpy")
        self.setWindowIcon(icon)
        self.resize(1000, 540)
        self.device_view_key = None
        self.tray_available = True
        layout = QVBoxLayout(self)
        title = QLabel("Easy Scrcpy · USB 设备投屏")
        title.setStyleSheet("font-size: 22px; font-weight: 600; padding: 8px 0;")
        layout.addWidget(title)
        self.health = QLabel("正在检查运行环境…")
        self.health.setWordWrap(True)
        layout.addWidget(self.health)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        devices_tab = QWidget()
        devices_layout = QVBoxLayout(devices_tab)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["设备", "序列号", "状态", "画质", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        devices_layout.addWidget(self.table)
        hint = QLabel("连接手机 → 开启开发者选项 / USB 调试 → 在手机上允许此电脑调试。\n"
                      "未开启 USB 调试的手机可能不会出现在列表中。拒绝投屏后可在这里手动启动。")
        hint.setWordWrap(True)
        devices_layout.addWidget(hint)
        quality_hint = QLabel("修改画质会重启该设备投屏，不会关闭 USB 调试；只影响投屏画面，不修改手机屏幕分辨率。")
        quality_hint.setWordWrap(True)
        devices_layout.addWidget(quality_hint)
        tabs.addTab(devices_tab, "USB 设备")
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.document().setMaximumBlockCount(1000)
        tabs.addTab(self.logs, "运行日志")
        buttons = QHBoxLayout()
        for label, signal in (("设置", self.settings_requested), ("停止全部投屏", self.stop_all_requested)):
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
            for column, text in enumerate((device.model.replace("_", " "), device.serial, state)):
                self.table.setItem(row, column, QTableWidgetItem(text))
            button = QPushButton(tr("停止投屏" if running else "开始投屏"))
            button.setEnabled(device.serial not in manager.stopping and (running or device.state == "device"))
            signal = self.stop_requested if running else self.start_requested
            button.clicked.connect(lambda checked=False, s=device.serial, target=signal: target.emit(s))
            quality = device_quality(device.serial, manager.settings)
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(2, 0, 2, 0)
            combo = QComboBox()
            for profile, label in QUALITY_LABELS.items():
                combo.addItem(tr(label), profile)
            combo.setCurrentIndex(combo.findData(quality["profile"]))
            combo.setToolTip(tr("画质参数：最大边长 {size}，{fps} FPS，{bitrate} Mbps", size=quality["max_size"] or tr("原始分辨率"), fps=quality["max_fps"], bitrate=quality["video_bit_rate"]))
            combo.activated.connect(lambda index, s=device.serial, c=combo: self.quality_requested.emit(s, c.itemData(index)))
            layout.addWidget(combo)
            edit = QPushButton(tr("调整…"))
            edit.clicked.connect(lambda checked=False, s=device.serial: self.custom_quality_requested.emit(s))
            layout.addWidget(edit)
            container.setEnabled(device.serial not in manager.stopping)
            self.table.setCellWidget(row, 3, container)
            self.table.setCellWidget(row, 4, button)

    def retranslate(self):
        self.device_view_key = None
        translate_widget(self)

    def closeEvent(self, event: QCloseEvent):
        if self.tray_available:
            self.hide()
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
        self.size = QSpinBox()
        self.size.setRange(0, 8192)
        self.size.setSpecialValueText("原始分辨率")
        self.size.setValue(controller.settings.max_size)
        form.addRow("最大画面边长", self.size)
        self.fps = QSpinBox()
        self.fps.setRange(1, 240)
        self.fps.setValue(controller.settings.max_fps)
        form.addRow("最大帧率", self.fps)
        self.bitrate = QSpinBox()
        self.bitrate.setRange(1, 100)
        self.bitrate.setSuffix(" Mbps")
        self.bitrate.setValue(controller.settings.video_bit_rate)
        form.addRow("视频码率", self.bitrate)
        self.audio = QCheckBox("转发音频（需要 Android 11 或更高）")
        self.audio.setChecked(controller.settings.audio)
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
                           max_size=self.size.value(), max_fps=self.fps.value(), audio=self.audio.isChecked(),
                           language=self.language.currentData(), disable_debug_on_stop=self.disable_debug.isChecked(),
                           video_bit_rate=self.bitrate.value())
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
        self.size = QSpinBox()
        self.size.setRange(0, 8192)
        self.size.setSpecialValueText("原始分辨率")
        self.size.setValue(quality["max_size"])
        form.addRow("最大画面边长", self.size)
        self.fps = QSpinBox()
        self.fps.setRange(1, 240)
        self.fps.setValue(quality["max_fps"])
        form.addRow("最大帧率", self.fps)
        self.bitrate = QSpinBox()
        self.bitrate.setRange(1, 100)
        self.bitrate.setSuffix(" Mbps")
        self.bitrate.setValue(quality["video_bit_rate"])
        form.addRow("视频码率", self.bitrate)
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
        return {"profile": "custom", "max_size": self.size.value(), "max_fps": self.fps.value(),
                "video_bit_rate": self.bitrate.value()}
