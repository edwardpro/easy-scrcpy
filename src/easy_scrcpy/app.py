import argparse
from dataclasses import replace
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .autostart import Autostart
from .core import Presence, Settings, resolve_executable, validate_quality, ORIENTATION_OPTIONS, validate_input, device_input
from .mirroring import MirroringManager
from .monitor import DeviceMonitor
from .ui import ControlWindow, SettingsDialog, QualityDialog, InputDialog, AboutDialog, STATE_LABELS
from .i18n import tr, set_language, translate_widget, translate_message_buttons
from .runtime import icon_path
from .notifications import DeviceNotifications
from .wireless_ui import WirelessDialog
from .wireless import WirelessConnection


def app_icon() -> QIcon:
    path = icon_path("icon.png")
    if path.is_file():
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#167dcb"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("white"), 4))
    painter.drawRoundedRect(20, 10, 24, 44, 4, 4)
    painter.drawLine(29, 47, 35, 47)
    painter.end()
    return QIcon(pixmap)


def tray_icon() -> QIcon:
    if sys.platform == "darwin":
        path = icon_path("tray-icon-mac.png")
        image = QImage(str(path))
        if not image.isNull():
            # macOS templates use alpha, not black/white pixel colors. Convert
            # white artwork/background to transparent while retaining black ink.
            image = image.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_ARGB32)
            for y in range(image.height()):
                for x in range(image.width()):
                    color = image.pixelColor(x, y)
                    alpha = round((255 - color.lightness()) * color.alpha() / 255)
                    image.setPixelColor(x, y, QColor(0, 0, 0, alpha))
            icon = QIcon(QPixmap.fromImage(image))
            icon.setIsMask(True)
            return icon
    path = icon_path("tray-icon.png")
    if path.is_file():
        icon = QIcon(str(path))
        if not icon.isNull():
            # User-supplied colored artwork is not a macOS monochrome template.
            return icon
    return app_icon()


def set_macos_foreground(active: bool):
    """LSUIElement bundles need a Regular policy for the Dock icon and menu bar."""
    if sys.platform != "darwin" or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return
    try:
        from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory,
                            NSApplicationActivationPolicyRegular)
    except ImportError:
        return
    application = NSApplication.sharedApplication()
    application.setActivationPolicy_(
        NSApplicationActivationPolicyRegular if active else NSApplicationActivationPolicyAccessory)
    if active:
        if hasattr(application, "activate"):
            application.activate()
        else:
            application.activateIgnoringOtherApps_(True)


class Controller(QObject):
    def __init__(self, app, config_path, settings, background=False, startup_error=""):
        super().__init__(app)
        self.app = app
        self.config_path = config_path
        self.settings = settings
        set_language(settings.language)
        self.health_source = "正在检查运行环境…"
        self.autostart = Autostart()
        self.presence = Presence()
        self.quitting = False
        self.dialogs = set()
        self.prompts = {}
        self.settings_dialog = None
        self.quality_dialogs = {}
        self.input_dialogs = {}
        self.wireless_dialog = None
        self.disconnect_jobs = {}
        icon = app_icon()
        app.setWindowIcon(icon)
        self.window = ControlWindow(icon)
        self.manager = MirroringManager(settings, self)
        self.monitor = DeviceMonitor(settings, self)
        self.notifications = DeviceNotifications(self)
        self.notifications.action.connect(self.notification_action)
        self.notifications.log.connect(self.log)
        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("Easy Scrcpy")
        self.tray.activated.connect(self._activated)
        self.window.start_requested.connect(self.start_device)
        self.window.stop_requested.connect(self.manager.request_stop)
        self.window.stop_all_requested.connect(self.manager.request_stop_all)
        self.window.settings_requested.connect(self.open_settings)
        self.window.quit_requested.connect(self.quit)
        self.window.quality_requested.connect(self.select_quality)
        self.window.custom_quality_requested.connect(self.open_quality)
        self.window.wireless_requested.connect(self.open_wireless)
        self.window.disconnect_wireless_requested.connect(self.disconnect_wireless)
        self.window.orientation_requested.connect(self.select_orientation)
        self.window.input_requested.connect(self.open_input)
        self.window.hidden_to_tray.connect(lambda: set_macos_foreground(False))
        self.manager.restart_ready.connect(self.restart_device)
        self.manager.changed.connect(self.refresh)
        self.manager.error.connect(self.show_error)
        self.manager.log.connect(self.log)
        self.monitor.snapshot.connect(self.on_snapshot)
        self.monitor.health.connect(self.on_health)
        app.aboutToQuit.connect(self.cleanup)
        self.refresh()
        self.window.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        if self.window.tray_available:
            self.tray.show()
        else:
            self.log(tr("系统托盘不可用：保留主窗口；Ubuntu GNOME 可能需要 AppIndicator 扩展。"))
        if not background or not self.window.tray_available:
            self.show_window()
        self.monitor.start()
        if startup_error:
            QTimer.singleShot(0, lambda: self.show_error(startup_error))
        if not resolve_executable("scrcpy", settings.scrcpy_path):
            self.log(tr("尚未找到 scrcpy：请检查内置依赖是否完整，开发环境先运行依赖准备脚本。"))

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self):
        set_macos_foreground(True)
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def log(self, message):
        logging.info(message)
        self.window.logs.appendPlainText(message)

    def on_health(self, message):
        self.health_source = message
        message = tr(message)
        if self.window.health.text() != message:
            self.log(message)
        self.window.health.setText(message)

    def refresh(self):
        if self.quitting:
            return
        devices = list(self.presence.devices.values())
        self.window.update_devices(devices, self.manager)
        self.tray.setToolTip(tr("Easy Scrcpy · {devices} 台设备 · {mirrors} 路投屏", devices=len(devices), mirrors=len(self.manager.processes)))
        self.menu.clear()
        self.menu.addAction(tr("打开设备面板"), self.show_window)
        self.menu.addAction(tr("无线连接"), self.open_wireless)
        self.menu.addSeparator()
        if not devices:
            self.menu.addAction(tr("未发现 Android 设备")).setEnabled(False)
        for device in devices:
            running = device.serial in self.manager.processes
            state = tr("正在停止" if device.serial in self.manager.stopping else "投屏中" if running else STATE_LABELS.get(device.state, device.state))
            submenu = self.menu.addMenu(f"{device.label} · {state}")
            if running:
                action = submenu.addAction(tr("停止投屏"), lambda s=device.serial: self.manager.request_stop(s))
                action.setEnabled(device.serial not in self.manager.stopping)
            else:
                action = submenu.addAction(tr("开始投屏"), lambda s=device.serial: self.start_device(s))
                action.setEnabled(device.state == "device" and device.serial not in self.manager.stopping)
            if not device.usb:
                submenu.addAction(tr("断开无线连接"), lambda s=device.serial: self.disconnect_wireless(s))
        self.menu.addSeparator()
        self.menu.addAction(tr("停止全部投屏"), self.manager.request_stop_all).setEnabled(bool(self.manager.processes))
        self.menu.addAction(tr("设置…"), self.open_settings)
        if sys.platform in {"darwin", "win32"}:
            self.menu.addAction(tr("通知权限…"), self.notifications.request_permission)
        self.menu.addAction(tr("关于"), self.open_about)
        self.menu.addAction(tr("退出"), self.quit)

    def open_about(self):
        dialog = AboutDialog(self.window)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def on_snapshot(self, devices):
        previous = self.presence.devices
        ready, lost = self.presence.update(devices)
        for serial, dialog in list(self.prompts.items()):
            device = self.presence.devices.get(serial)
            if device is None or device.state != "device":
                dialog.reject()
        for serial, dialog in list(self.input_dialogs.items()):
            device = self.presence.devices.get(serial)
            if device is None or device.state != "device":
                dialog.reject()
        for serial in lost:
            self.log(tr("设备断开或失去就绪状态：{serial}，停止对应投屏。", serial=serial))
            self.manager.stop(serial)
        for device in devices:
            old = previous.get(device.serial)
            if old is None or old.state != device.state:
                self.log(f"{device.label}: {tr(STATE_LABELS.get(device.state, device.state))}")
                if device.state == "unauthorized":
                    self.tray.showMessage(tr("请在手机上授权 USB 调试"), device.label,
                                          QSystemTrayIcon.MessageIcon.Information)
        self.refresh()
        self.notifications.sync(devices)
        if self.settings.prompt_on_connect:
            for device in ready:
                if device.serial not in self.manager.processes:
                    self.ask_mirror(device)

    def ask_mirror(self, device):
        dialog = QMessageBox(self.window)
        dialog.setWindowTitle(tr("发现 Android 设备"))
        dialog.setText(tr("{device}\n\n是否开始投屏？", device=device.label))
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        translate_message_buttons(dialog)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.prompts[device.serial] = dialog

        def finished(result):
            self.prompts.pop(device.serial, None)
            if result == QMessageBox.StandardButton.Yes and not self.quitting:
                self.start_device(device.serial)
            dialog.finished.disconnect()
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def start_device(self, serial):
        device = self.presence.devices.get(serial)
        if device is not None:
            self.manager.start(device)

    def open_wireless(self):
        if self.wireless_dialog:
            self.wireless_dialog.raise_()
            self.wireless_dialog.activateWindow()
            return
        dialog = WirelessDialog(self)
        self.wireless_dialog = dialog
        def finished(result):
            self.wireless_dialog = None
            dialog.finished.disconnect()
            dialog.deleteLater()
        dialog.finished.connect(finished)
        dialog.show()

    def notification_action(self, serial, action):
        if self.quitting:
            return
        device = self.presence.devices.get(serial)
        if device is None or device.state != "device":
            return
        if action == "restart":
            if serial in self.manager.processes:
                self.manager.restart(device)
            else:
                self.manager.start(device)
        elif action == "stop":
            self.manager.request_stop(serial)
        elif action == "settings":
            self.open_quality(serial)

    def remember_paired(self, guid, name, address):
        from datetime import datetime
        records = [r for r in self.settings.paired_devices if r.get("guid") != guid]
        records.insert(0, {"guid": guid, "name": name, "address": address,
                           "paired_at": datetime.now().isoformat(timespec="seconds")})
        self._save_paired(records)

    def forget_paired(self, guid):
        # Only forgets the local record; the phone keeps its authorization until revoked there.
        self._save_paired([r for r in self.settings.paired_devices if r.get("guid") != guid])

    def _save_paired(self, records):
        settings = replace(self.settings, paired_devices=records)
        try:
            settings.save(self.config_path)
        except (OSError, ValueError) as error:
            self.show_error(tr("无法保存设置") + "\n" + str(error))
            return
        self.settings = settings
        self.monitor.settings = settings
        self.manager.settings = settings

    def disconnect_wireless(self, serial):
        device = self.presence.devices.get(serial)
        if device is None or device.usb or serial in self.disconnect_jobs:
            return
        dialog = QMessageBox(QMessageBox.Icon.Warning, tr("断开无线连接"),
            tr("断开会影响其他工具对该设备的 ADB 连接，但不会关闭手机无线调试。是否继续？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self.window)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        translate_message_buttons(dialog)
        self.disconnect_jobs[serial] = dialog
        def confirmed(result):
            self.disconnect_jobs.pop(serial, None)
            dialog.finished.disconnect()
            dialog.deleteLater()
            current = self.presence.devices.get(serial)
            if result != QMessageBox.StandardButton.Yes or self.quitting or current is None or current.usb:
                return
            job = WirelessConnection(self.settings, self)
            self.disconnect_jobs[serial] = job
            def status_changed(status):
                if status not in {"failed", "disconnected", "timeout", "cancelled"}:
                    return
                self.disconnect_jobs.pop(serial, None)
                job.status.disconnect()
                if status == "disconnected":
                    self.manager.stop(serial)
                    self.monitor.scan()
                elif not self.quitting:
                    self.show_error(tr("连接失败，请检查地址、端口、授权及防火墙。"))
                # Give a killed process time to finish before deleting its owner.
                job.shutdown()
                job.deleteLater()
            job.status.connect(status_changed)
            try:
                job.disconnect_device(serial)
            except (ValueError, OSError):
                status_changed("failed")
        dialog.finished.connect(confirmed)
        dialog.show()

    def restart_device(self, device):
        current = self.presence.devices.get(device.serial)
        if current is not None and current.state == "device" and not self.quitting:
            self.manager.start(current)

    def select_quality(self, serial, profile):
        if profile == "custom":
            self.open_quality(serial)
        else:
            self.save_quality(serial, {"profile": profile})

    def open_quality(self, serial):
        device = self.presence.devices.get(serial)
        if device is None or serial in self.manager.stopping:
            return
        if serial in self.quality_dialogs:
            self.quality_dialogs[serial].raise_()
            self.quality_dialogs[serial].activateWindow()
            return
        dialog = QualityDialog(device, self.settings, self.window)
        self.quality_dialogs[serial] = dialog

        def finished(result):
            self.quality_dialogs.pop(serial, None)
            if result == QualityDialog.DialogCode.Accepted and not self.quitting:
                self.save_quality(serial, dialog.quality())
            else:
                self.window.device_view_key = None
                self.refresh()
            dialog.finished.disconnect()
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def save_quality(self, serial, quality):
        if serial in self.manager.stopping:
            self.window.device_view_key = None
            self.refresh()
            return
        try:
            validate_quality(quality)
            selections = {**self.settings.device_quality, serial: dict(quality)}
            settings = replace(self.settings, device_quality=selections)
            settings.save(self.config_path)
        except (OSError, ValueError) as error:
            self.window.device_view_key = None
            self.refresh()
            self.show_error(tr("无法保存设置") + "\n" + str(error))
            return
        self.apply_settings(settings)
        device = self.presence.devices.get(serial)
        if device and device.state == "device" and serial in self.manager.processes:
            self.log(tr("正在重启设备投屏以应用画质：{serial}", serial=serial))
            self.manager.restart(device)

    def select_orientation(self, serial, orientation):
        if orientation not in ORIENTATION_OPTIONS or serial in self.manager.stopping:
            self.window.device_view_key = None
            self.refresh()
            return
        try:
            selections = {**self.settings.device_orientation, serial: orientation}
            settings = replace(self.settings, device_orientation=selections)
            settings.save(self.config_path)
        except (OSError, ValueError) as error:
            self.window.device_view_key = None
            self.refresh()
            self.show_error(tr("无法保存设置") + "\n" + str(error))
            return
        self.apply_settings(settings)
        device = self.presence.devices.get(serial)
        if device and device.state == "device" and serial in self.manager.processes:
            self.log(tr("正在重启设备投屏以应用方向：{serial}", serial=serial))
            self.manager.restart(device)

    def open_input(self, serial):
        device = self.presence.devices.get(serial)
        if device is None or device.state != "device" or serial in self.manager.stopping:
            return
        if serial in self.input_dialogs:
            self.input_dialogs[serial].raise_()
            self.input_dialogs[serial].activateWindow()
            return
        dialog = InputDialog(device, self.settings, self.window)
        self.input_dialogs[serial] = dialog

        def finished(result):
            self.input_dialogs.pop(serial, None)
            if result == InputDialog.DialogCode.Accepted and not self.quitting:
                self.save_input(serial, dialog.options())
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.show()

    def save_input(self, serial, options):
        if serial in self.manager.stopping:
            return
        try:
            validate_input(options)
            if options == device_input(serial, self.settings):
                return
            settings = replace(self.settings, device_input={**self.settings.device_input, serial: dict(options)})
            settings.save(self.config_path)
        except (OSError, ValueError) as error:
            self.show_error(tr("无法保存设置") + "\n" + str(error))
            return
        self.apply_settings(settings)
        device = self.presence.devices.get(serial)
        if device and device.state == "device" and serial in self.manager.processes:
            self.manager.restart(device)

    def open_settings(self):
        if self.settings_dialog is not None:
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self)
        self.settings_dialog = dialog

        def finished(_):
            self.settings_dialog = None
            dialog.finished.disconnect()
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def apply_settings(self, settings):
        language_changed = settings.language != self.settings.language
        self.settings = settings
        self.monitor.settings = settings
        self.manager.settings = settings
        set_language(settings.language)
        self.window.retranslate()
        for dialog in self.quality_dialogs.values():
            translate_widget(dialog)
        for dialog in self.input_dialogs.values():
            dialog.retranslate()
        self.window.health.setText(tr(self.health_source))
        for serial, dialog in self.prompts.items():
            device = self.presence.devices.get(serial)
            if device:
                dialog.setWindowTitle(tr("发现 Android 设备"))
                dialog.setText(tr("{device}\n\n是否开始投屏？", device=device.label))
                translate_message_buttons(dialog)
        for dialog in self.dialogs:
            translate_message_buttons(dialog)
        self.refresh()
        if language_changed:
            self.notifications.refresh_language(list(self.presence.devices.values()))
        self.monitor.scan()
        self.log(tr("设置已保存；新的投屏参数在下一次启动时生效。"))

    def show_error(self, message):
        if self.quitting:
            return
        self.log(message)
        dialog = QMessageBox(QMessageBox.Icon.Warning, "Easy Scrcpy", message,
                             QMessageBox.StandardButton.Ok, self.window)
        dialog.setTextFormat(Qt.TextFormat.PlainText)
        translate_message_buttons(dialog)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.dialogs.add(dialog)

        def finished(_):
            self.dialogs.discard(dialog)
            dialog.finished.disconnect()
            dialog.deleteLater()

        dialog.finished.connect(finished)
        dialog.show()

    def quit(self):
        self.app.quit()

    def cleanup(self):
        if self.quitting:
            return
        self.quitting = True
        for job in list(self.disconnect_jobs.values()):
            if isinstance(job, WirelessConnection):
                job.status.disconnect()
                job.shutdown()
            else:
                job.reject()
        self.disconnect_jobs.clear()
        if self.wireless_dialog:
            self.wireless_dialog.cleanup(0)
        for dialog in list(self.input_dialogs.values()):
            dialog.reject()
        self.notifications.shutdown()
        self.monitor.stop()
        self.manager.shutdown()
        self.tray.hide()


def main():
    parser = argparse.ArgumentParser(description="Easy Scrcpy USB tray companion")
    parser.add_argument("--background", action="store_true", help="Start with the main window hidden")
    args = parser.parse_args()
    # Must be set before creating QApplication. Keep macOS login launches out of Dock.
    if sys.platform == "darwin" and args.background:
        os.environ.setdefault("QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM", "1")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("EasyScrcpy")
    app.setOrganizationName("EasyScrcpy")
    app.setQuitOnLastWindowClosed(False)
    set_language("auto")
    directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[
        RotatingFileHandler(directory / "easy-scrcpy.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")])
    config_path = directory / "settings.json"
    startup_error = ""
    try:
        settings = Settings.load(config_path)
    except (OSError, ValueError) as error:
        settings = Settings()
        startup_error = tr("读取设置失败，暂用默认值（原文件未修改）：{error}", error=error)
    set_language(settings.language)
    lock = QLockFile(str(directory / "app.lock"))
    if not lock.tryLock(100):
        dialog = QMessageBox(QMessageBox.Icon.Information, "Easy Scrcpy",
                             tr("应用已经运行，请通过系统托盘打开。"), QMessageBox.StandardButton.Ok)
        translate_message_buttons(dialog)
        dialog.exec()
        return
    controller = Controller(app, config_path, settings, args.background, startup_error)
    try:
        app.exec()
    finally:
        controller.cleanup()
        lock.unlock()
