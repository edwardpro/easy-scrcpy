# 无线二维码配对“无反应”：ADB 服务 mDNS 发现失效

## 元信息
- 日期：2026-10-06
- 状态：完成（根因已消除，用户已在打包产物上实机验证通过）
- 关联：`.coding/2026-10-06-04-wireless-qr-pairing.md`、`.coding/2026-10-06-03-wireless-pairing-fix.md`

## 用户反馈
- 使用打包后的 macOS 应用，在“开发者选项 → 无线调试 → 使用二维码配对设备”扫描应用生成的二维码，随后填写配对信息，界面“无反应”。

## 诊断过程
- 应用日志（`~/Library/Preferences/EasyScrcpy/EasyScrcpy/easy-scrcpy.log`）中没有任何无线相关记录：无线流程此前完全不打日志，属于可诊断性缺口。
- `settings.json` 未被本次会话写入（mtime 早于当前应用启动时间），说明本次没有走到 `remember_paired`，即配对确实没有成功。
- 打包产物检查：`qrcode`、`easy_scrcpy.wireless`、`easy_scrcpy.wireless_ui` 均在 `PYZ-00.toc` 中，`PIL` 已随包分发，排除“二维码模块缺失导致静默异常”。
- 运行中的 ADB 服务进程 PID 10359，启动时间 15:41，可执行文件为 `/Applications/EasyScrcpy.app/Contents/Frameworks/runtime/adb`；而 `/Applications/EasyScrcpy.app` 是 17:45 才安装、17:46 才启动的当前版本。即应用连接的是一个**更早的构建（或其他父进程）留下的陈旧 ADB 服务**（PPID=1，已脱离父进程）。
- 对照实验（不影响 5037 上的现有服务）：
  - 用 `dns-sd -R` 在本机注册假的 `_adb-tls-pairing._tcp` 服务，`dns-sd -B` 能立即发现，说明本机 Bonjour 正常。
  - `adb -L tcp:5037 mdns services`（应用使用的陈旧服务）：**始终为空**。
  - `adb -L tcp:localhost:5038 mdns services`（同一 adb 二进制新启的服务）：立即列出上述假服务，**并且列出了用户手机正在广播的 `_adb-tls-connect._tcp` 实例**。
- 结论：二维码配对的第一步依赖 `adb mdns services` 找到手机扫描后广播的 `_adb-tls-pairing._tcp`。陈旧 ADB 服务的 mDNS 发现失效（macOS 本地网络权限按“责任进程”归属，该服务由更早的构建/其他父进程启动，签名与归属已变化），因此永远看不到手机广播；应用按设计每秒轮询、最多约 3 分钟后才报超时，期间只显示“等待手机扫描配对二维码…”，用户感知为“无反应”。

## 需求与范围
- 本次包含：
  1. 二维码配对等待期间，若 mDNS 长时间返回**完全空**的服务列表，提前给出可操作提示（不再静默等满 3 分钟）。
  2. “重启 ADB 服务”按钮改为**常驻可见**并补充 tooltip（用户要求：出问题时能立刻自救）。仍保留原有确认对话框，不自动执行。
  3. 无线流程写入应用日志（阶段、退出码、脱敏后的 ADB 输出），便于后续排查。
  4. 消除其余静默路径：`connect_phone()` 在流程进行中时给出可见状态；`qr_pixmap()` 的延迟导入纳入异常处理；ADB 服务重启后在“首次配对”模式自动重新开始二维码配对。
- 不包含：
  - **不在打开无线窗口时自动重启 ADB 服务**：会每次掐断所有 ADB 客户端（含正在投屏的设备、Android Studio 等），且 `adb kill-server` 按规约必须用户显式确认；改为常驻按钮 + 停滞提示，由用户决定时机。
  - 不改动配对协议、二维码格式、mDNS 解析逻辑。
  - 不承诺在屏蔽组播的网络下可用（保留配对码与手动端口作为备用路径）。

## 验收条件
- [x] mDNS 持续为空时，二维码等待界面在约 10 秒内出现提示（详情行）。
- [x] “重启 ADB 服务”按钮常驻可见，点击后仍有确认对话框；确认后在扫码模式自动重新生成二维码并重新开始等待扫描。
- [x] 应用日志中出现无线各阶段记录，且不包含配对码明文。
- [x] 流程进行中重复点击“确认并连接”时界面给出可见提示，而不是毫无反应。
- [x] 全部单元测试通过，`git diff --check` 无空白错误。
- [x] 用户在重启 ADB 服务后完成实机验证：全部功能正常。

## 设计与实现
- `wireless.py`
  - 新增 `POLL_DELAY_MS`、`MDNS_STALL_POLLS` 常量（轮询间隔与判定阈值分离出来，便于测试缩短）。
  - 新增 `discovery_stalled` 信号；`_reset()` 增加 `stalled` 标志，一次流程内只提示一次。
  - 判定依据：手机只要开着无线调试就会广播 `_adb-tls-connect._tcp`，用户此时必然停留在无线调试页面，因此“连续多次完全没有服务”指向 ADB 服务侧的发现能力失效，而不是手机没广播。空列表本身不能区分“后端失效”和“网络里确实没有任何 ADB 设备”，所以**不判失败**，只提示并保留继续轮询。
  - 增加 `logging` 输出，复用 `_sanitize()` 做配对码脱敏与长度截断。
- `wireless_ui.py`
  - `discovery_stalled` 写入灰色详情行（状态行仍显示“等待手机扫描配对二维码…”，避免被每秒的阶段状态覆盖），同时显示“重启 ADB 服务”按钮。
  - `update_status()` 收到 `restarted` 且处于扫码配对模式时自动调用 `start_qr_pairing()`，重新生成凭据并恢复等待。
- 翻译：新增两条用户可见文案，补齐 en / fr / de / ja。
- 预计改动文件：`src/easy_scrcpy/wireless.py`、`src/easy_scrcpy/wireless_ui.py`、`src/easy_scrcpy/i18n.py`、`tests/test_wireless.py`。

## 实际变更
- `src/easy_scrcpy/wireless.py`
  - 新增 `POLL_DELAY_MS = 1000`、`MDNS_STALL_POLLS = 10`、模块 `logger`。
  - `WirelessConnection` 新增 `discovery_stalled` 信号；`_reset()` 新增 `stalled`、`logged_phase`。
  - `_run()` 在阶段变化时记录一行（adb 路径 + 参数，配对码经 `_sanitize()` 脱敏）；`_fail()`、`_located()` 成功分支、`_timeout()`、ADB 服务重启成功各记录一行；`find_pairing` 首次轮询记录发现到的服务列表。
  - `find_pairing` 分支：连续 `MDNS_STALL_POLLS` 次拿到**完全空**的服务列表时，置 `stalled` 并发出一次 `discovery_stalled`，之后继续按原逻辑轮询到 `QR_WAIT_ATTEMPTS`。
- `src/easy_scrcpy/wireless_ui.py`
  - “重启 ADB 服务”按钮改为常驻可见并设置 tooltip；移除原先按条件 `show()` / `hide()` 的 5 处调用（`start_qr_pairing`、`connect_phone`、`discovery_stalled`、`probe_reachability`、`restart_adb`）。确认对话框与“先停止本应用投屏”的顺序保持不变。
  - 连接 `discovery_stalled` → 新增 `discovery_stalled()` 槽：把提示写入灰色详情行（避免被每秒刷新的阶段状态覆盖）。
  - `update_status()`：状态为 `restarted` 且处于扫码配对模式时自动 `start_qr_pairing()`，重新生成凭据并恢复等待扫描。
  - `connect_phone()`：流程进行中时给出可见状态，不再静默返回。
  - `start_qr_pairing()`：`qr_pixmap()` 移入 `try`，并捕获 `ImportError`，二维码生成失败会显示在状态行而不是只打印到不可见的 stderr。
- 配置 / 翻译 / 资源 / 文档变更：`src/easy_scrcpy/i18n.py` 新增 4 条文案（mDNS 停滞提示、无线操作进行中提示、重启按钮 tooltip，以及此前漏译的“连接失败，请检查地址、端口、授权及防火墙。”），各补齐 en / fr / de / ja。
- `tests/test_wireless.py`：新增停滞检测（连接层）与对话框行为（提示、常驻按钮、重启后自动恢复、忙碌点击）两项测试；原有“重启按钮默认隐藏”的断言改为“常驻可见”。

## 验证记录
- 执行命令：
  - `QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests -p "test_wireless.py" -v`
  - `QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests`
  - `git diff --check`
  - 临时脚本：配置 `logging` 后驱动一次配对码失败流程，检查日志内容与脱敏。
  - 临时脚本：用 `ast` 扫描 `src/easy_scrcpy/*.py` 中所有 `tr("字面量")`，逐条核对是否存在于 `CATALOG["zh"]`。
- 实际结果：
  - 无线测试 17 项全部通过（新增 `test_qr_pairing_reports_stalled_mdns_discovery`、`test_dialog_explains_stalled_discovery_busy_clicks_and_restart`）。
  - 全量 77 项测试通过（改为常驻按钮后再次运行，仍为 77 项通过）；`git diff --check` 无输出。
  - `tr()` 字面量覆盖检查：补译后 `missing: []`（此前 `app.py` 有 1 条漏译）。
  - 日志验证：输出 `wireless pair: <adb> <script> pair 192.168.1.20:41000 ******` 与 `wireless failed: Failed: Wrong password`，配对码未出现在日志中。
  - 诊断用对照实验（`dns-sd -R/-B`、`adb -L tcp:5037 / tcp:localhost:5038 mdns services`）已在上文记录；临时 5038 ADB 服务已按其 PID 停止，5037 上应用正在使用的服务未被本次改动触碰。
- 环境修复（经用户确认后执行）：先核对 `cleanup()` 不会关闭 ADB 服务、且监视器每 2 秒的 `adb devices -l` 会在无服务时自动拉起新服务（不会出现下次启动不了的情况），再 `kill 10359`；约 6 秒后出现新服务（PID 46495），`adb mdns services` 立即列出两台测试机的 `_adb-tls-connect._tcp` 广播，其中一台作为 known host 自动连接。根因确认消除。
- 打包平台、架构和产物（若执行）：`uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec` 构建成功，产物 `dist/EasyScrcpy.app`（macOS Apple Silicon / arm64，ad-hoc 签名，约 132 MB）；`build/EasyScrcpy/PYZ-00.pyz` 的重建时间晚于最后一次源码修改，确认包含本次改动。未执行 Windows / Ubuntu 打包（无相关代码路径变化，构建不是跨平台交叉编译）。
- 用户实机验证（2026-10-06）：安装新产物后确认全部功能正常（含无线连接与同批打包的 macOS 界面改动）。
- 未验证部分与原因：mDNS 停滞提示在真实图形界面中的触发未复现——环境修复后 mDNS 恢复正常，无法自然触发该分支，改由单元测试覆盖。

## 风险与后续事项
- 已知限制：陈旧 ADB 服务是当前环境状态，重启后即可恢复；若用户机器上还有终端或其他工具持有 ADB 服务，仍可能再次出现同类问题，因此提示文案保留了“改用配对码”的备用路径。空列表无法区分“发现后端失效”与“网络中确实没有任何 ADB 设备”，所以只提示、不判失败。
- 后续工作：可考虑在应用启动时检测 ADB 服务的启动时间与归属，主动提示一次；需先确认不会干扰其他 ADB 客户端。
- 提交 / 发布信息：尚未提交。
