# 无线连接可用性修复

## 元信息
- 日期：2026-10-06
- 状态：代码修复完成，待用户用真实配对码验收
- 关联：`.coding/2026-10-06-02-wifi-mirroring-design.md`

## 用户反馈
- 连接模式只保留“IP 获取 / IP 连接”和“配对码”两种，其余移除。
- 开启无线调试后，扫码或手工填写配对端口、配对码均无法连接。
- 网页只能获取 IP，无法获取端口；需在网页上说明如何打开开发者选项、无线调试并读取端口。
- 直接按无线调试页面的 IP 和端口填写也无法连接，要求重新核对文档和实现。

## 文档 / 源码核对
- Android 无线调试：配对端口在“使用配对码配对设备”弹窗中，连接端口在无线调试主页面，两者不同；首次必须配对。
- ADB 37 `adb help` 与 AOSP `commandline.cpp`：支持 `pair HOST:PORT [PAIRING CODE]`；pair / connect 结果以文本返回且退出码为 0，不能只看退出码。
- AOSP `adb_wifi.cpp`：配对成功后写入 known hosts，并尝试 mDNS 自动连接。
- AOSP `socket_spec.cpp` / `services.cpp`：connect 由 ADB 服务器进程发起网络连接。

## 实测诊断（测试设备 192.168.66.104:40747）
- 终端 `nc -z 192.168.66.104 40747`：成功，说明网络和端口可达。
- 当前 ADB 服务器（14:05 由 vendor/adb 启动，开发调试遗留）执行 `adb connect`：`No route to host`；日志中对此前地址也全部为 `No route to host`。
- 在隔离端口 5038 启动新的 ADB 服务器后连接：网络可达，TLS 握手返回 `SSLV3_ALERT_CERTIFICATE_UNKNOWN`，即该电脑尚未与手机配对。测试后立即仅停止该隔离服务器。
- 结论：
  1. 已运行的 ADB 服务器缺少 macOS 本地网络权限（由其他进程启动的长驻服务器继承其权限），所有无线请求都被系统拒绝，GUI 却只显示笼统失败。
  2. 未配对时只填 IP + 连接端口必然失败，必须先配对。
  3. 原实现：配对码经 stdin 交互输入不可靠；输出判断过严且吞掉 ADB 错误；连接端口默认 5555 误导用户；网页无端口说明；`.app` 缺少 `NSLocalNetworkUsageDescription` / `NSBonjourServices`。

## 实际变更
- `wireless.py`：只保留 IP 连接与配对码连接；配对码按 ADB 文档作为参数传递（不写日志，失败详情中脱敏）；接受 `connected to` / `already connected to`；用 `devices -l` 轮询验证精确 transport（最多 8 次）；合并 stdout/stderr 并分类失败原因（网络不可达、端口拒绝、配对码错误、未授权、未知）；新增用户确认后的 ADB 服务重启（kill-server → start-server）。网页显示 IP 和获取端口的分步说明。
- `wireless_ui.py`：两种模式、分步指引、连接端口不再默认 5555、显示 ADB 原始返回；网络不可达时由应用自行 TCP 探测，若手机可达则判定为 ADB 服务权限问题，显示“重启 ADB 服务”（需确认，先停止本应用投屏，不触发关闭 USB 调试）。移除 mDNS 发现与 USB 转无线 UI。
- `packaging/EasyScrcpy.spec`：Info.plist 增加本地网络用途说明和 ADB Bonjour 服务类型。
- `i18n.py`：新增 / 移除相应五语言文案。
- `tests/test_wireless.py`：按 ADB 真实输出格式重写，覆盖配对参数、错码脱敏、already connected、零退出码失败、输入校验、重启流程、超时取消、网页说明及两种模式。
- `AGENTS.md`：明确仅允许用户确认后的 ADB 服务重启。

## 验证记录
- `uv run --extra build python -m unittest discover -s tests -q`：65 项通过。
- `uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec`：成功，产物 `dist/EasyScrcpy.app`（macOS arm64）；`plutil` 确认 Info.plist 含 `NSLocalNetworkUsageDescription` 与 `NSBonjourServices`。
- `git diff --check`：通过。
- 未验证：真实配对码完整流程（需用户在手机上生成配对码）、Windows / Ubuntu 无线连接。

## 风险与后续事项
- 配对码短暂出现在 ADB 子进程参数中（本机可见，数秒内结束），换取 GUI 下可靠配对。
- 配对后 ADB 可能同时出现 mDNS 序列号与 IP:端口两个 transport，列表可能出现同一手机两行。
- 重启 ADB 服务会影响所有 ADB 客户端，必须由用户确认。
