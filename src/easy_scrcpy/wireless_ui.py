from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtNetwork import QNetworkInterface, QAbstractSocket, QTcpSocket
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QLabel,
                               QPushButton, QHBoxLayout, QWidget, QMessageBox, QCheckBox)

from .i18n import tr, translate_message_buttons
from .wireless import (Discovery, WirelessConnection, endpoint, FAILURE_HINTS,
                       new_pairing_credentials, pairing_qr_payload)

STATUS_LABELS = {
    "find_pairing": "等待手机扫描配对二维码…", "pair": "正在配对…", "locate": "正在检查设备状态…",
    "find_connect": "正在局域网中查找设备…", "connect": "正在连接…",
    "connected": "无线设备已连接，请在设备列表开始投屏。", "failed": "连接失败",
    "cancelled": "取消", "timeout": "无线操作超时，请检查手机和网络。",
    "kill": "正在重启 ADB 服务…", "start": "正在重启 ADB 服务…",
    "restarted": "ADB 服务已重启，请重新连接。",
}
IDLE = {"failed", "cancelled", "connected", "timeout", "restarted"}


def qr_pixmap(text, size):
    import qrcode
    image = qrcode.make(text).convert("RGB")
    data = image.tobytes()
    qt_image = QImage(data, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qt_image).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation)


def section(*widgets):
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget) if isinstance(widget, QWidget) else layout.addLayout(widget)
    return box


def wrapped(text):
    label = QLabel(text)
    label.setWordWrap(True)
    return label


class WirelessDialog(QDialog):
    def __init__(self, controller):
        super().__init__(controller.window)
        self.controller = controller
        self.closed = False
        self.candidate_ip = None
        self.probe = None
        self.last_detail = ""
        self.setWindowTitle(tr("无线连接"))
        self.resize(560, 760)
        self.discovery = Discovery(self)
        self.connection = WirelessConnection(controller.settings, self)
        layout = QVBoxLayout(self)

        self.mode = QComboBox()
        self.mode.addItem(tr("首次配对"), "pair")
        self.mode.addItem(tr("连接已配对设备"), "paired")
        top = QFormLayout()
        top.addRow(tr("连接方式"), self.mode)
        layout.addLayout(top)

        # --- First-time pairing: Android-compatible ADB pairing QR code ---
        self.pair_qr = QLabel()
        self.pair_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pair_qr_button = QPushButton(tr("重新生成配对二维码"))
        self.pair_qr_button.clicked.connect(self.start_qr_pairing)
        self.use_code = QCheckBox(tr("无法扫码时改用配对码"))
        self.code_host = QLineEdit()
        self.code_host.setPlaceholderText("192.168.1.20")
        self.pair_port = QLineEdit()
        self.pair_port.setPlaceholderText(tr("配对弹窗中的端口"))
        self.code = QLineEdit()
        self.code.setEchoMode(QLineEdit.EchoMode.Password)
        self.code.setMaxLength(6)
        self.code.setPlaceholderText("123456")
        self.code_port = QLineEdit()
        self.code_port.setPlaceholderText(tr("可选：无线调试页面冒号后的端口"))
        code_form = QFormLayout()
        for label, widget in (("手机 IP", self.code_host), ("配对端口", self.pair_port),
                              ("配对码", self.code), ("连接端口", self.code_port)):
            code_form.addRow(tr(label), widget)
        self.code_group = section(wrapped(tr("手机点“使用配对码配对设备”，填写弹窗中的 IP、端口和六位配对码。")), code_form)
        self.pair_group = section(
            wrapped(tr("在手机打开“设置 → 开发者选项 → 无线调试 → 使用二维码配对设备”，扫描下方二维码。电脑与手机需在同一 Wi-Fi。")),
            self.pair_qr, self.pair_qr_button, self.use_code, self.code_group)

        # --- Paired devices: mDNS finds the current port; web QR / manual as fallback ---
        self.paired = QComboBox()
        self.forget_button = QPushButton(tr("删除记录"))
        self.forget_button.clicked.connect(self.forget_selected)
        paired_row = QHBoxLayout()
        paired_row.addWidget(self.paired, 1)
        paired_row.addWidget(self.forget_button)
        self.interface = QComboBox()
        for address in QNetworkInterface.allAddresses():
            if address.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol and not address.isLoopback():
                self.interface.addItem(address.toString())
        self.ip_qr_button = QPushButton(tr("生成网页二维码"))
        self.ip_qr_button.clicked.connect(self.make_ip_qr)
        ip_row = QHBoxLayout()
        ip_row.addWidget(self.interface, 1)
        ip_row.addWidget(self.ip_qr_button)
        self.ip_qr = QLabel()
        self.ip_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url = QLabel()
        self.url.setWordWrap(True)
        self.url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.host = QLineEdit()
        self.host.setPlaceholderText("192.168.1.20")
        self.port = QLineEdit()
        self.port.setPlaceholderText(tr("无线调试页面冒号后的端口"))
        manual_form = QFormLayout()
        manual_form.addRow(tr("手机 IP"), self.host)
        manual_form.addRow(tr("连接端口"), self.port)
        self.manual_group = section(
            wrapped(tr("未自动发现时：扫码获取手机 IP，并填写无线调试主页面“IP 地址和端口”中的连接端口。")),
            QLabel(tr("电脑局域网 IP")), ip_row, self.ip_qr, self.url, manual_form)
        self.paired_group = section(
            wrapped(tr("手机开启无线调试并与电脑在同一 Wi-Fi 后，选择设备即可自动查找当前端口并连接。")),
            paired_row, self.manual_group)

        layout.addWidget(self.pair_group)
        layout.addWidget(self.paired_group)

        self.status = wrapped("")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.detail = wrapped("")
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail.setStyleSheet("color: #888;")
        layout.addWidget(self.detail)
        layout.addStretch()

        buttons = QHBoxLayout()
        self.connect_button = QPushButton(tr("确认并连接"))
        self.connect_button.clicked.connect(self.connect_phone)
        buttons.addWidget(self.connect_button)
        self.restart_button = QPushButton(tr("重启 ADB 服务"))
        self.restart_button.clicked.connect(self.restart_adb)
        self.restart_button.hide()
        buttons.addWidget(self.restart_button)
        cancel = QPushButton(tr("取消"))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        self.controls = [self.mode, self.pair_qr_button, self.use_code, self.code_host, self.pair_port,
                         self.code, self.code_port, self.paired, self.forget_button, self.interface,
                         self.ip_qr_button, self.host, self.port]
        self.discovery.candidate.connect(self.candidate)
        self.connection.status.connect(self.update_status)
        self.connection.failure.connect(self.show_failure)
        self.connection.connected.connect(self.connected)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.use_code.toggled.connect(self.mode_changed)
        self.paired.currentIndexChanged.connect(self.mode_changed)
        self.finished.connect(self.cleanup)
        self.probe_target = None
        self.load_paired()
        # Remembered devices make "connect paired" the default; first use starts with QR pairing.
        self.mode.blockSignals(True)
        self.mode.setCurrentIndex(self.mode.findData("paired" if controller.settings.paired_devices else "pair"))
        self.mode.blockSignals(False)
        self.mode_changed()

    # ----- state -----
    def load_paired(self, select=""):
        self.paired.blockSignals(True)
        self.paired.clear()
        for record in self.controller.settings.paired_devices:
            label = record.get("name") or record["guid"]
            if record.get("address"):
                label += f" · {record['address']}"
            self.paired.addItem(label, record["guid"])
        self.paired.addItem(tr("手动输入 IP 和端口"), None)
        index = self.paired.findData(select) if select else 0
        self.paired.setCurrentIndex(max(index, 0))
        self.paired.blockSignals(False)

    def mode_changed(self):
        pairing = self.mode.currentData() == "pair"
        self.pair_group.setVisible(pairing)
        self.paired_group.setVisible(not pairing)
        self.code_group.setVisible(pairing and self.use_code.isChecked())
        self.manual_group.setVisible(not pairing and self.paired.currentData() is None)
        self.forget_button.setEnabled(self.paired.currentData() is not None and not self.connection.busy())
        manual_code = pairing and self.use_code.isChecked()
        self.connect_button.setVisible(not pairing or manual_code)
        if pairing and not manual_code:
            if not self.connection.busy() and not self.closed:
                self.start_qr_pairing()
        elif self.connection.phase == "find_pairing" or self.connection.next_phase == "find_pairing":
            self.connection.cancel()
            self.pair_qr.clear()

    # ----- first-time pairing -----
    def start_qr_pairing(self):
        if self.connection.busy():
            self.connection.cancel()
        name, password = new_pairing_credentials()
        self.pair_qr.setPixmap(qr_pixmap(pairing_qr_payload(name, password), 240))
        self.detail.clear()
        self.restart_button.hide()
        try:
            self.connection.pair_qr(name, password)
        except (ValueError, OSError) as error:
            self.status.setText(tr("连接失败") + f": {error}")

    # ----- paired devices / manual -----
    def forget_selected(self):
        guid = self.paired.currentData()
        if guid:
            self.controller.forget_paired(guid)
            self.load_paired()
            self.mode_changed()

    def make_ip_qr(self):
        try:
            url = self.discovery.start(self.interface.currentText())
            self.ip_qr.setPixmap(qr_pixmap(url, 180))
            self.url.setText(url)
            self.candidate_ip = None
            self.status.setText(tr("等待手机扫码"))
        except Exception as error:
            self.discovery.stop()
            self.ip_qr.clear()
            self.url.clear()
            self.status.setText(tr("无法启动网页服务：{error}", error=error))

    def candidate(self, host):
        if not self.closed and self.discovery.server is not None and self.candidate_ip is None and not self.connection.busy():
            self.candidate_ip = host
            self.host.setText(host)
            self.status.setText(tr("已获取手机 IP；网页无法读取端口，请按手机无线调试页面填写端口。"))
            self.port.setFocus()

    def connect_phone(self):
        if self.connection.busy():
            return
        self.detail.clear()
        self.restart_button.hide()
        try:
            if self.mode.currentData() == "pair":
                endpoint(self.code_host.text(), self.pair_port.text())
                port = self.code_port.text().strip() or None
                if port:
                    endpoint(self.code_host.text(), port)
                self.probe_target = (self.code_host.text(), self.pair_port.text())
                self.connection.connect_device(self.code_host.text(), port, pair_port=self.pair_port.text(),
                                               code=self.code.text().strip())
            elif self.paired.currentData():
                self.probe_target = None
                self.connection.connect_paired(self.paired.currentData())
            else:
                endpoint(self.host.text(), self.port.text())
                self.probe_target = (self.host.text(), self.port.text())
                self.connection.connect_device(self.host.text(), self.port.text())
        except ValueError as error:
            self.status.setText(tr("请填写有效的手机 IP 和端口。") + f" ({error})")
        except OSError as error:
            self.status.setText(tr("连接失败") + f": {error}")
        finally:
            self.code.clear()

    # ----- results -----
    def update_status(self, status):
        self.status.setText(tr(STATUS_LABELS.get(status, status)))
        idle = status in IDLE or status == "find_pairing"
        for widget in self.controls:
            widget.setEnabled(idle)
        self.connect_button.setEnabled(status in IDLE)
        if status in IDLE:
            self.forget_button.setEnabled(self.paired.currentData() is not None)

    def show_failure(self, kind, detail):
        self.last_detail = detail
        self.status.setText(tr(FAILURE_HINTS.get(kind, FAILURE_HINTS["unknown"])))
        self.detail.setText(tr("ADB 返回：{detail}", detail=detail) if detail else "")
        if kind == "network":
            self.probe_reachability()

    def connected(self, serial, guid, model, address):
        self.discovery.stop()
        self.ip_qr.clear()
        self.url.clear()
        self.pair_qr.clear()
        if guid:
            self.controller.remember_paired(guid, model.replace("_", " "), address)
            self.load_paired(select=guid)
        self.controller.monitor.scan()
        self.controller.show_window()

    # ----- diagnostics -----
    def probe_reachability(self):
        """Distinguish an unreachable phone from an ADB server lacking LAN access."""
        target = getattr(self, "probe_target", None)
        if not target:
            return
        try:
            host, port = target[0].strip(), int(target[1])
        except ValueError:
            return
        if self.probe is not None:
            self.probe.abort()
            self.probe.deleteLater()
        socket = QTcpSocket(self)
        self.probe = socket
        timer = QTimer(socket)
        timer.setSingleShot(True)

        def reachable():
            timer.stop()
            socket.abort()
            if not self.closed and self.probe is socket:
                self.show_failure("adb_network", self.last_detail)
                self.restart_button.show()

        socket.connected.connect(reachable)
        timer.timeout.connect(socket.abort)
        socket.connectToHost(host, port)
        timer.start(3000)

    def restart_adb(self):
        dialog = QMessageBox(QMessageBox.Icon.Warning, tr("重启 ADB 服务"),
                             tr("重启 ADB 服务会短暂断开所有 ADB 设备（包括正在进行的投屏）及其他工具的连接。是否继续？"),
                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, self)
        dialog.setDefaultButton(QMessageBox.StandardButton.No)
        translate_message_buttons(dialog)
        if dialog.exec() != QMessageBox.StandardButton.Yes:
            return
        if self.connection.busy():
            self.connection.cancel()
        self.restart_button.hide()
        # Stop our mirrors first; never apply the optional USB-debugging shutdown here.
        self.controller.manager.stop_all()
        try:
            self.connection.restart_server()
        except (ValueError, OSError) as error:
            self.status.setText(tr("连接失败") + f": {error}")

    def cleanup(self, result):
        self.closed = True
        if self.probe is not None:
            self.probe.abort()
        self.discovery.stop()
        self.connection.shutdown()
