# 无线二维码配对、端口自动发现与已配对设备记录

## 元信息
- 日期：2026-10-06
- 状态：进行中
- 关联：`.coding/2026-10-06-03-wireless-pairing-fix.md`

## 需求
1. 首次使用时生成 Android 系统可识别的配对二维码，手机在“无线调试 → 使用二维码配对设备”扫描即可配对。
2. 记录配对过的设备；下次默认进入“连接已配对设备”（网页 IP 二维码 / 自动发现）。
3. 调研能否自动获得连接端口：网页 / JS、远端执行、打开开发者选项页面等。

## 调研结论
- AOSP Settings `wifi/dpp/AdbQrCode.java`：ADB 配对二维码格式为 ZXing Wi-Fi 格式 `WIFI:T:ADB;S:<服务名>;P:<密码>;;`，要求 T=ADB、S 与 P 非空，特殊字符需反斜杠转义。手机扫描后用该密码开启配对，并以服务名 S 广播 mDNS `_adb-tls-pairing._tcp`。电脑需通过 mDNS 找到该服务的 IP:端口，再执行 `adb pair IP:端口 密码`（Android Studio 同一流程）。
- AOSP `adb_wifi.cpp`：配对成功输出 `Successfully paired to ... [guid=<设备 guid>]`，写入 known hosts，并对 `_adb-tls-connect._tcp` 中同名实例自动连接；`transport_mdns.cpp`：只对 known hosts 自动连接，序列号为 `<guid>._adb-tls-connect._tcp`。
- **端口获取的正规方式是 mDNS**：手机开启无线调试后广播 `_adb-tls-connect._tcp`，包含当前 IP 与连接端口。实测（隔离 ADB 服务，具备本地网络权限）`adb mdns services` 返回 `adb-ZY22L2VL3P-H70Q3s  _adb-tls-connect._tcp  192.168.66.104:40747`，与用户提供的测试设备一致。
- 网页 / JS：浏览器没有读取 Android 设置、adbd 端口或执行系统命令的 API；不存在“用户同意一下即可远程执行”的标准机制（需安装配套 App 或已有 ADB 授权）。
- 网页打开开发者选项：Chrome 的 `intent:` 只能启动带 BROWSABLE category 的 Activity，系统设置的开发者选项 / 无线调试页面不是 BROWSABLE，无法可靠跳转；只能文字指引。
- 局限：mDNS 依赖电脑与手机同一可互通网络且未屏蔽组播；访客网络、AP 隔离、部分企业网络会失败，此时保留配对码 + 手动端口作为备用。

## 计划
- 首次配对（默认，无配对记录时）：生成随机服务名 / 密码的 ADB 二维码，轮询 mDNS 配对服务，配对成功后按 guid 等待自动连接，必要时通过 mDNS 找连接端口并 connect；备用配对码方式中连接端口改为可选。
- 已配对设备（有记录时默认）：列出记录，选择后通过 mDNS 查找当前 IP:端口自动连接；保留网页 IP 二维码 + 手动端口兜底。
- 设置中保存 `paired_devices`（guid、型号、最近地址、时间），可删除记录（不撤销手机授权）。
- 测试、五语言、README、打包。

## 实际变更
- `wireless.py`：`new_pairing_credentials()` 生成仅字母数字的服务名 / 密码；`pairing_qr_payload()` 输出 `WIFI:T:ADB;S:...;P:...;;`；`parse_mdns()` 解析配对 / 连接服务。连接状态机：二维码配对（轮询 mDNS 配对服务约 3 分钟 → pair → 按 guid 等待自动连接 / mDNS 查端口后 connect）、配对码（连接端口可选）、已配对设备（guid → 自动连接或 mDNS 查当前端口）、手动 IP。新增“未扫码”“mDNS 未发现”失败提示。网页说明改为引导首次扫码配对。
- `wireless_ui.py`：两种方式“首次配对”（显示系统可扫描的配对二维码，可改用配对码）与“连接已配对设备”（记录列表 + 自动发现，手动 IP / 网页二维码兜底）；有记录时默认后者；可删除记录。
- `core.py`：`Settings.paired_devices`（guid、名称、地址、配对时间）及校验；`app.py`：保存 / 删除记录（不撤销手机授权）。
- `i18n.py`、测试同步更新。

## 验证记录
- `uv run --extra build python -m unittest discover -s tests -q`：68 项通过（含二维码格式、mDNS 解析、二维码配对状态机、已配对设备经 mDNS 查端口、记录校验与默认模式）。
- 打包：`dist/EasyScrcpy.app`（macOS arm64）成功，Info.plist 含本地网络与 Bonjour 声明；`git diff --check` 通过。
- 未验证：真实手机扫码配对（需用户操作）；Windows / Ubuntu。README 尚未同步本次界面变化。
