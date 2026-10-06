# Wi-Fi 投屏调研与接入方案

## 元信息
- 日期：2026-10-06
- 状态：进行中，用户已授权在 features/add_wireless_connect 分支实现
- 范围：方案和流程，不修改应用行为、不执行真实手机命令。

## 资料与验证
- 已阅读 scrcpy v5.0 官方连接文档：https://github.com/Genymobile/scrcpy/blob/v5.0/doc/connection.md
- 已阅读 Android 官方 ADB 无线调试说明：https://developer.android.com/tools/adb#wireless
- 已检查 core.py 的 USB 过滤、monitor.py 的设备发现以及现有进程和通知架构。
- 未进行真实手机配对、TCP/IP 切换或性能测试。

## 推荐实现范围
第一阶段实现 Android 11+ 配对码无线调试、已配对设备地址直连、USB 引导传统 TCP/IP。二维码和自动重连作为后续迭代，不进行网段扫描、不自动开启无线调试、不重启全局 ADB 服务。

## 用户流程
### Android 11+ 配对（首选）
1. 手机和电脑位于可互通的同一局域网，手机手动开启无线调试。
2. 手机选择“使用配对码配对设备”。GUI 填写配对 IP、配对端口、配对码。
3. 异步执行 `adb pair <配对地址>`，通过进程 stdin 提交配对码，不保存配对码或写入日志。
4. 配对成功后重新枚举 ADB 设备 / mDNS 服务；若未自动连接，填写无线调试主页面的连接地址，执行 `adb connect <连接地址>`。
5. 配对端口与连接端口不同，不互相代用；端口可能随重新开启无线调试变化。
6. 连接状态验证为 device 后，用户点击开始投屏，scrcpy 明确指定枚举出的 transport serial。

### USB 引导 TCP/IP（兼容 Android 5–10 等设备）
1. USB 调试已开启并授权，手机和电脑在可互通局域网。
2. 用户选择“切换 Wi-Fi”，确认传统 TCP/IP 暴露调试端口且不具有 Android 11+ TLS 配对安全特性。
3. 在切换前获取并校验 Wi-Fi IP；多接口不猜测，允许用户确认地址。
4. 停止对应 USB 投屏（不关闭 USB 调试），执行 `adb -s <USB serial> tcpip 5555`。
5. 执行 `adb connect <IP>:5555`，验证网络 transport 为 device，再启动对应无线投屏。
6. 验证成功后提示可拔线；切换不承诺无缝播放，失败显示状态和恢复指引。

### 已配对 / 已监听设备直连
填写 IP 和连接端口，执行 adb connect 并验证连接。adb connect 不能绕过配对、授权或手机无线调试开关。

## 架构方案
- 增加无线连接窗口：配对、地址直连、USB 引导三个入口，进度、取消、错误信息。
- 新增异步无线连接服务：命令队列、超时、配对 stdin、严格主机 / 端口验证；不拼 shell，不泄漏密钥。
- 将 Device 的物理设备身份与 transport serial 分离，明确 USB / Wi-Fi transport；不能按型号合并设备。
- monitor / Presence 接受 USB 和真实网络设备，仍排除模拟器；mDNS 发现不是已授权连接，不发现后自动投屏。
- 首版可按 transport 分行展示，不自动合并身份未确认的同名手机；已验证物理身份后共享设备画质设置。
- 进程按具体 transport 管理；拔 USB 不终止 Wi-Fi 投屏，Wi-Fi 断线仅终止对应进程；不自动切换或无限重连。
- 保留 scrcpy --serial 方式，GUI 管理 adb pair / connect；不把 scrcpy --tcpip 的内部隐式切换作为主要架构，避免序列号变更与现有 USB 断线清理冲突。
- Wi-Fi Stop 仅停止投屏；单独“断开无线连接”执行目标 adb disconnect，提示会影响同一 ADB 服务上其他工具的该连接。不执行无目标 adb disconnect 或 adb kill-server。
- “断开”不等于关闭手机无线调试。手机设置关闭 / 忘记配对由用户操作；旧的关闭 USB 调试设置仅作用 USB 手动 Stop。
- 通知、翻译和配置同步支持网络 transport，通知连接级 token 防止旧通知控制重连设备。

## 验收条件与后续测试
- [ ] Android 11+ 配对成功 / 错码 / 超时 / 取消，配对端口与连接端口区别清晰。
- [ ] TCP/IP 切换失败不误停其他设备，不自动关闭调试或重启 ADB。
- [ ] USB 与 Wi-Fi 并存，多设备同型号不误合并，拔线不影响无线投屏。
- [ ] 参数保存、五种语言、通知操作和原设置向后兼容。
- [ ] Windows / macOS / Ubuntu 实机验证；访客网络、AP 隔离、防火墙及 mDNS 被阻断时允许手动地址连接并说明限制。

## 风险与建议
- 配对记录主要由 ADB / 手机保存，GUI 不保存临时配对码。
- 地址不能作为永久物理身份，DHCP 可能把同一个 IP 分配给另一台手机；新连接须验证身份。
- 无线性能受信号、网络干扰及带宽影响，推荐从 1280 / 30 FPS / 4 Mbps 开始，可由用户提高。
- mDNS 自动发现和新 ADB Wi-Fi 2.0 能力依手机系统与 ADB 服务配置，不能承诺所有 Android 11+ 都自动重连。

## 补充：本地网页二维码与 BLE 可行性

用户建议：GUI 增加无线连接按钮，启动本机网页服务并生成二维码；手机扫码访问网页，利用请求来源获取手机 IP，界面显示进行中，然后执行 ADB 连接，加入设备列表。

### 可行范围
- 本地 HTTP 服务可以获取 TCP 对端地址，适合辅助发现手机可达地址，无需手机安装应用，浏览器访问在新旧 Android 上均可使用。
- 此二维码是网页 URL，不是 Android 无线调试配对二维码；不能完成 ADB 授权、开启无线调试或获取连接 / 配对端口。
- Android 11+ 仍需用户开启无线调试并提供配对信息，或使用独立 ADB 配对二维码机制；旧版仍需已授权 USB 执行 tcpip。
- 对端地址可能受 VPN / 代理 / IPv6 影响，不能当作已验证物理设备身份，不能信任请求头 X-Forwarded-For 或页面自报 IP。
- 自动推进仅限用户确认的手机、已配对且端口已知 / 可发现的连接，不能对所有访问者自动尝试 ADB。

### 建议交互
1. 无线连接 → 选择电脑可达局域网网卡 → 临时启动服务 / 展示二维码。
2. 页面访问后显示候选地址和手机设置指引；GUI 显示“已发现手机，等待调试配置”，不是假装已进入 ADB 连接。
3. 分流至 Android 11+ 配对 / 已配对直连，或旧版已授权 USB 引导 tcpip。
4. 正确连接端口确定后显示“正在连接”，adb connect 成功且设备状态为 device 后显示“已连接”，用户开始投屏。
5. 确认候选设备后关闭临时网页服务，正常纳入设备监控和进程生命周期。

### 临时服务安全
- 使用高熵短期会话 token（URL 中），固定少量路由，只提供引导信息，不提供远程命令接口。
- 绑定用户选择的局域网地址、随机端口；处理防火墙拒绝、AP 隔离、多网卡及 IPv6。
- 会话超时 / 取消 / 成功后关闭监听；限制请求大小、频率和并发，不记录配对码或 token。
- 网页普通 GET 只产生候选地址，不能直接改变手机设置 / 发起 ADB 操作；避免二维码预览器和误访问触发。
- 首版只允许手机确认来源、GUI 确认后继续；页面不上传应用列表或敏感信息。

### BLE
- BLE 标准广播不提供 Wi-Fi IP / ADB 端口信息，不能直接从任意 Android 手机读取。
- 可开发配套 Android 应用通过 BLE GATT 自定义服务传输地址和设备身份，但需要安装、权限、前后台兼容、协议安全及三平台蓝牙适配。
- BLE 获取地址仍不能绕过 ADB 授权 / 无线调试开关。无配套应用时优先采用网页辅助发现与 ADB mDNS，不引入 BLE。

本补充为可行性分析，未实现服务、二维码或 BLE，未进行局域网 / 浏览器 / 实机测试。

## 实现启动
- 分支：features/add_wireless_connect。
- 首版实现临时网页二维码候选 IP、配对码 / 地址连接 / USB tcpip，以及网络设备列表。
- 不实现 BLE、ADB 专用配对二维码、自动扫描网段或全局 ADB 服务重启。

## 首版实现及验证
- 后续继续：新增 mDNS 服务发现（只填候选连接地址，不自动连接）、指定 transport 断开和取消 / 超时回归测试；开始前记录本计划。
- `wireless.py`：随机 URL 临时 HTTP 服务、来源地址发现、局域网 IPv4 绑定、会话到期、8 并发上限及请求超时；ADB 配对 / TCP/IP / connect / get-state 异步链路、取消及 15 秒阶段超时。配对码只经 stdin 传递。
- `wireless_ui.py`：无线连接窗口、网卡地址选择、网页二维码、配对码 / 地址 / USB 三个入口及状态提示。
- `core.py` / `monitor.py`：接受网络设备，继续排除模拟器。USB 与 Wi-Fi 按 transport 分行，未自动合并物理身份。
- `mirroring.py`：无线 Stop 不应用关闭 USB 调试设置。
- `app.py` / `ui.py`：面板及托盘入口、窗口取消 / 退出清理，Wi-Fi 标记。
- `i18n.py`：新增界面和网页引导五种语言；`pyproject.toml` / `uv.lock`：增加 qrcode 依赖。
- `README.md`：补充实际支持范围和安全限制。
- `uv sync --extra build`：通过。
- 首次测试发现无线窗口缺少 Qt 导入，修正后重测。
- `uv run --extra build python -m unittest discover -s tests -q`：58 项通过，包括 HTTP 随机路由、关闭服务、端口校验、stdin 配对、连接状态验证、非零 / 文本失败及 USB / Wi-Fi 隔离。
- 本轮未打包（用户尚未要求），未提交 / 推送。
- 未验证真实手机、真实局域网扫码、Windows / Ubuntu 运行及原生通知；需进一步验收。
- 与原调研方案的差异：首版没有 mDNS 发现、单独断开无线按钮或物理身份持久化；用户手动确认 IP 和端口。已有 transport 级画质保存机制保留，不宣称 IP 是稳定设备身份。

## 继续完善
- 增加 `adb mdns services` 候选发现，解析连接服务（排除配对服务与无效地址），不自动连接。
- 托盘无线设备子菜单增加指定 transport 断开操作，确认后执行定向 `adb disconnect`，不关闭手机无线调试或重启 ADB 服务。
- 新增阶段超时明确状态、配对取消不推进、发现服务解析及断开参数回归测试。
- 临时 HTTP 服务自行管理五分钟监听期限、并发候选锁；关闭窗口后忽略排队候选回调。
- 主界面标题和监控信息统一为 USB / Wi-Fi Android 设备。
- README 更新新增发现及断开操作。首版“无 mDNS 和断开”的范围记录已被本次实现补齐；仍无物理身份合并和自动重连。
- 最终 `uv run --extra build python -m unittest discover -s tests -q`：61 项通过；`git diff --check`：通过。
- 不进行打包、提交、推送；真实设备及三平台原生行为仍未验证。

## 本地打包验收
- 用户后续要求本地打包并重试。
- `uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec`：成功，包含 qrcode / Pillow 及原生通知依赖。
- 产物：`dist/EasyScrcpy.app`，macOS Apple Silicon / arm64。
- 未进行真实手机无线连接验证，等待用户本地试用；未提交或推送。
