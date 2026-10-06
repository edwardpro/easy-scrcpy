# 启动横屏与电脑键盘输入可行性调研

## 元信息
- 日期：2026-10-06
- 状态：调研完成，待确认实现范围
- 分支：`features/research_landscape_input`，基于 `main`。
- 原无线分支保留，本轮不合并、不删除、不修改其代码。
- 范围：查阅 scrcpy v5.0 官方文档与源码，不修改应用行为、不在手机上执行旋转或输入命令。

## 资料
- https://github.com/Genymobile/scrcpy/blob/v5.0/doc/video.md#orientation
- https://github.com/Genymobile/scrcpy/blob/v5.0/doc/keyboard.md
- https://github.com/Genymobile/scrcpy/blob/v5.0/doc/control.md#copy-paste
- https://github.com/Genymobile/scrcpy/blob/v5.0/doc/shortcuts.md
- https://github.com/Genymobile/scrcpy/blob/v5.0/doc/virtual-display.md
- https://github.com/Genymobile/scrcpy/blob/v5.0/server/src/main/java/com/genymobile/scrcpy/control/Controller.java
- https://github.com/Genymobile/scrcpy/blob/v5.0/server/src/main/java/com/genymobile/scrcpy/wrappers/WindowManager.java

## 一、启动时横屏

必须分离两个需求：旋转电脑投屏画面，与改变手机应用实际布局。

### 仅旋转画面（直接支持）
- 启动参数 `--display-orientation=90` / `270`，只改变电脑显示，不让手机应用重新排版；竖屏内容只是被旋转，文字也会侧向显示。
- `--orientation` 同时影响显示和录制；若只改窗口，优先 `--display-orientation`。
- `--capture-orientation=@90` 锁定采集方向，影响采集 / 录制，不等于强制手机应用横屏。
- 运行时 MOD+左右箭头改变显示方向；MOD 默认左 Alt 或左 Super（macOS Command）。
- 方向相对于原始画面，不应把 90°称为对所有手机 / 平板都有效的“横屏”。

### 手机应用真正横屏（有条件可行）
- scrcpy 提供 MOD+r 请求切换手机横竖屏；官方注明应用可以拒绝不支持的方向。
- v5.0 文档未提供“启动时强制手机横屏”的对应 CLI 参数。
- GUI 可另用已授权 ADB 在启动前读取旋转状态，调用目标系统支持的 WindowManager 旋转命令或改变自动旋转 / 用户旋转设置；具体命令和权限需要按 Android 版本 / 厂商验证，不能将一个固定命令宣称通用。
- 旋转值是相对设备自然方向，手机、横屏平板及折叠屏不同，需查询当前显示信息。
- 设置可能持久化影响手机：必须显式选择、保存原状态、正常结束恢复、失败提示；拔线无法立即恢复时保留待恢复记录。不可盲目覆盖用户后来手动修改的旋转状态。
- 不建议向外部 scrcpy 窗口模拟快捷键实现自动旋转：依赖焦点和平台自动化权限，可能误操作其他窗口。

### 横向独立工作区（另一种场景）
- `--new-display=1920x1080 --start-app=<包名>` 创建独立虚拟显示并启动应用。
- 不等于把当前手机主屏原样切成横屏；应用 / 系统需支持独立显示，输入法和内容迁移行为须验证。
- 适合作为后续高级功能，不纳入普通“启动横屏”默认行为。

## 二、电脑向手机输入框输入

### 已有功能
- 默认 `--keyboard=sdk` 已支持键盘；点击 scrcpy 窗口中的手机输入框，保持 scrcpy 窗口焦点，键入内容即发到手机当前焦点。
- 目标输入框由 Android 焦点决定，不需在 GUI 中识别文本框。不能自动保证正确字段，用户先点击目标框。
- 若无法输入，检查 `--no-control` / disabled keyboard、手机输入注入权限与应用限制。
- SDK 模式主要支持 ASCII 和部分字符；源码 injectText 经 KeyCharacterMap 转为按键，不能将其当任意 Unicode 文本接口。

### 推荐：UHID 物理键盘
- `--keyboard=uhid` / `-K`，手机把电脑键盘视为物理键盘，官方推荐常用此模式。
- USB 与 TCP/IP 均可使用；旧 Android 可能因权限或内核支持失败。
- 首次在手机物理键盘设置匹配布局：scrcpy 窗口 MOD+k，或已授权 `adb -s <serial> shell am start -a android.settings.HARD_KEYBOARD_SETTINGS`。
- 中文 / 日语输入通常由手机输入法处理电脑发送的按键，候选和组合过程发生在手机。不等于把电脑输入法的任意组合文本原样实时同步。
- 英语、法语、德语等键盘布局同样需要手机侧配置正确。
- AOA 是 USB 专用且 Windows 投屏有兼容限制，不作为第一版推荐。

### 使用电脑输入法：复制 / 粘贴
- 在电脑上输入中文 / 日语，复制，然后点击手机输入框，在 scrcpy 窗口用 Ctrl+v 或 MOD+v 同步剪贴板并粘贴。
- MOD 默认左 Alt / 左 Super（macOS Command），具体行为取决于手机应用，文档对剪贴板快捷操作标注 Android 7+。
- MOD+Shift+v 是按键注入替代粘贴，对非 ASCII 可能失败，不作为 Unicode 解决方案。
- 密码框 / 安全输入框 / 某些应用可能禁止粘贴，不能绕过。
- 剪贴板有隐私风险，避免敏感内容，提供关闭自动同步 `--no-clipboard-autosync` 的可选设置。

### 在本 GUI 的输入框输入并发送（额外工作）
- 当前 GUI 只启动外部 scrcpy 子进程，没有控制协议连接；scrcpy stdin 不是发送文本或粘贴命令的公开接口。
- 不建议使用 `adb shell input text` 作为通用方案：Unicode、转义、焦点和权限受限，不可保证中文输入。
- 不建议通过操作系统模拟 Ctrl+v：依赖焦点、权限和系统差异。
- 真正实现需接入 scrcpy 版本绑定的控制协议 / 修改客户端，或安装手机端输入法 / 辅助应用（额外权限、分发、维护）；仍需正确输入焦点。
- 首版先支持键盘模式配置和输入操作引导，不增加误导性的“发送任意文本”按钮。

## 建议首版范围
1. 每设备显示旋转选择：默认、90°、180°、270°；明确标注“只旋转投屏画面”。启动时追加 --display-orientation。
2. 键盘模式选择：兼容 SDK / 物理键盘 UHID；提供物理键盘设置入口和输入引导。
3. 剪贴板自动同步选项（默认行为兼容现有），提示复制粘贴敏感信息风险。
4. 若实际目标是“手机应用自动横屏”，应先单独实机验证旋转命令、应用响应与状态恢复，再决定支持范围。

## 验证结果
- 已读取上述官方 v5.0 文档和控制器 / WindowManager 源码。
- 未执行手机旋转、粘贴、键盘注入或新增打包；未进行 Windows / macOS / Ubuntu 真实输入法验证。
- 本轮仅产生此调研文档；后续实现需用户确认。
