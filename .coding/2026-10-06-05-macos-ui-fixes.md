# macOS UI 修复：前台 Dock 图标与菜单、通知分线程不折叠

## 元信息
- 日期：2026-10-06
- 状态：完成（用户已在打包产物上实机验证通过）
- 关联需求或记录：2026-10-06-04-capture-orientation.md 之后的实机使用反馈（独立 UI 修复，另建记录）

## 需求与范围
- 用户目标：修复 macOS 实机使用中发现的四个界面问题。
- 本次包含：
  1. 主界面在前台时任务栏（Dock）没有图标 → 窗口显示时切换为 Regular 激活策略。
  2. 应用界面在前台时没有系统菜单（菜单栏）→ 同上，Regular 策略恢复 Qt 标准菜单栏。
  3. 通知"普通的不是置顶的" → 应用侧可增加声音与前台横幅呈现；横幅/提醒（Alerts）样式属系统设置项，应用无法强制，记录说明。
  4. 多设备时通知折叠 → 每个设备连接使用独立 `threadIdentifier`，通知中心不再合并为一组。
- 不包含：
  - Windows / Ubuntu 行为变化（激活策略与 UserNotifications 均为 macOS 专属代码路径）。
  - 自定义应用菜单项（依赖 Qt 自动生成的标准 macOS 菜单：应用菜单、编辑、窗口、帮助）。
  - `UNNotificationInterruptionLevelTimeSensitive`（需要签名 entitlement，ad-hoc 签名打包不可靠，不引入）。
  - 方向选项功能（PR #2 已合并进 main 为 c7f53ec；本分支开发中途快进集成，冲突仅 app.py / ui.py 信号声明与连接两处，均保留双方新增行）。
- 约束与兼容性：
  - 保留 `LSUIElement=True`：登录项后台启动仍不进 Dock；仅当主窗口显示时动态切换 Regular，窗口关闭回托盘时切回 Accessory。
  - 通知权限请求新增 Sound 选项；已授权用户不受影响（系统会补充询问声音权限或静默忽略）。
  - 非 macOS 平台与 offscreen 测试环境下激活策略辅助函数为无操作。

## 验收条件
- [x] 激活策略切换机制在本机真实 GUI 会话验证：`set_macos_foreground(True)` → Regular(0)，`False` → Accessory(1)。
- [x] 多设备通知设置互不相同的 `threadIdentifier`（每次连接唯一 token），通知中心按设备分列不折叠（代码与 API 实测验证）。
- [x] 通知带默认声音，权限请求包含 Sound 选项。
- [x] 全部测试通过；`git diff --check` 无空白错误。
- [x] 重新打包并冒烟启动，AppKit 确认打入包内。
- [ ] 打包应用实机交互：主窗口显示时 Dock 图标与菜单栏出现、关闭回托盘后消失；通知声音与分组表现（需用户安装 `dist/EasyScrcpy.app` 验证）。

## 设计与实现计划
- 方案及取舍：
  - 问题 1/2 根因：`packaging/EasyScrcpy.spec` 的 `LSUIElement=True` 使打包应用成为永久 agent 应用（无 Dock 图标、无菜单栏）。采用 macOS 托盘应用标准做法：运行时用 `NSApplication.setActivationPolicy_` 在 Regular（前台）与 Accessory（托盘）之间切换，保留 LSUIElement 以维持登录项静默启动。`activate()`（macOS 14+）优先，回退 `activateIgnoringOtherApps_`。
  - 问题 3 根因与边界：macOS 通知的"横幅（Banners，自动消失）/提醒（Alerts，停留至操作）"样式由用户在 系统设置 → 通知 → EasyScrcpy 中选择，应用侧无 API 强制。应用侧可做：默认声音（更醒目）、前台呈现选项（已有 `willPresentNotification` 返回 Banner|List）。如需停留式提醒，指引用户改系统设置为"提醒"样式。
  - 问题 4 根因：未设置 `threadIdentifier` 时所有通知落入同一默认线程，通知中心折叠显示。每次设备连接已有唯一 token（uuid4），直接作为 threadIdentifier，天然按设备连接分组，且旧通知不会控制重连设备（沿用 token 机制）。
- 设备 / 平台 / 权限影响：仅 macOS；通知新增声音权限请求；不修改手机设置。
- 预计改动文件：`src/easy_scrcpy/app.py`、`ui.py`、`notifications_macos.py`、`packaging/EasyScrcpy.spec`、`tests/test_macos_ui.py`。

## 实际变更
- 变更文件及内容：
  - `src/easy_scrcpy/app.py`：新增 `set_macos_foreground(active)` 辅助函数（非 darwin 或 offscreen 环境直接返回；AppKit 导入失败静默降级）；`show_window()` 先切 Regular 并激活；`Controller.__init__` 连接 `window.hidden_to_tray` → 切回 Accessory。
  - `src/easy_scrcpy/ui.py`：`ControlWindow` 新增 `hidden_to_tray = Signal()`；`closeEvent` 隐藏到托盘时发出该信号。
  - `src/easy_scrcpy/notifications_macos.py`：通知内容设置 `threadIdentifier=token`（每设备连接独立线程）与 `setSound_(UNNotificationSound.defaultSound())`；`request_permission` 权限选项增加 `UNAuthorizationOptionSound`。
  - `packaging/EasyScrcpy.spec`：darwin hiddenimports 增加 `AppKit`（随 pyobjc-framework-Cocoa 传递安装，无需改 pyproject）。
  - `tests/test_macos_ui.py`（新增）：offscreen / 非 darwin 平台辅助函数无操作；Controller 显示窗口触发 Regular、关闭到托盘触发 Accessory、重新打开再触发 Regular；（darwin 限定）通知内容按设备设置不同 threadIdentifier、声音与权限选项包含 Sound。
- 配置 / 翻译 / 资源 / 文档变更：无新增用户可见文案（未改 i18n）；无配置结构变化。

## 验证记录
- 执行命令：
  - `QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests`：71 个测试全部通过（含新增 3 个）。
  - `git diff --check`：无空白错误。
  - AppKit / UserNotifications API 实测：`NSApplicationActivationPolicyRegular=0`、`Accessory=1`；`UNMutableNotificationContent` 设置 `threadIdentifier` 与 `defaultSound()` 后属性回读正确（注意 `defaultSound` 是类方法，必须带括号调用）。
  - 本机真实 GUI 会话验证激活策略：初始 Regular(0) → `set_macos_foreground(True)` 保持 0 → `False` 切为 Accessory(1)，切换机制在本机 macOS 版本可用。
  - 集成 main（c7f53ec，含方向功能）后全量测试：75 个测试通过（72 + 本迭代 3 个），`git diff --check` 干净。
- 实际结果：71 个测试通过；激活策略切换、通知 threadIdentifier/声音均验证生效；打包冒烟正常。
- 打包平台、架构和产物（若执行）：
  - `uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec` 构建成功，产物 `dist/EasyScrcpy.app`（macOS Apple Silicon）与 `dist/EasyScrcpy` 目录。
  - 冒烟测试：`QT_QPA_PLATFORM=offscreen timeout 8 ./dist/EasyScrcpy.app/Contents/MacOS/EasyScrcpy --background` 运行 8 秒被超时终止（exit=124），无崩溃。
  - `AppKit` 确认打入包内：`Contents/Frameworks/AppKit/_AppKit.cpython-313-darwin.so` 与 `Contents/Resources/AppKit` 存在。
  - 未执行 Windows / Ubuntu 打包（无相关代码路径变化；构建不是跨平台交叉编译）。
- 用户实机验证（2026-10-06）：安装重新打包的 `dist/EasyScrcpy.app` 后确认全部功能正常，包含 Dock 图标 / 菜单栏随窗口前台与收起托盘切换、多设备通知不折叠且有声音。
- 未验证部分与原因：
  - 声音权限的系统弹窗表现（已授权设备升级安装后的行为）。
  - Windows / Ubuntu（无相关代码路径变化，未重新打包）。

## 风险与后续事项
- 已知限制：
  - "提醒（Alerts）"停留样式必须由用户在系统设置中开启，应用无法代设；如需更强制的置顶提醒，需引入 time-sensitive entitlement 与正式签名，超出本次范围。
  - Accessory ↔ Regular 切换时 Dock 图标出现/消失属预期行为；若未来增加"始终显示 Dock 图标"设置项，可在此辅助函数上扩展。
- 后续工作：用户实机验证四项表现；如通知样式仍不满足，评估 time-sensitive + 正式签名方案。
- 提交 / 发布信息：未提交；待用户要求后执行。
