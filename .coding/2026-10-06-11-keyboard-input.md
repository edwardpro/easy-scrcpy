# 每设备键盘输入支持

## 元信息
- 日期：2026-10-06
- 状态：完成（沙箱内验证完成，实机待验证）
- 分支：`codex/feature-keyboard-input`
- 关联记录：2026-10-06-02-landscape-keyboard-research.md

## 需求与范围
- 用户目标：新 feature 分支，依据调研支持电脑键盘与手机输入交互。
- 包含：每设备 SDK / UHID 选择、剪贴板自动同步开关、输入引导、物理键盘设置入口。
- 兼容性：默认 SDK、同步开启，保持旧配置行为；参数变化仅重启目标设备；不修改安全设置。
- 不包含：GUI 任意 Unicode 发送、模拟外部窗口快捷键、AOA、打包发布。

## 验收条件
- [x] 配置校验、迁移与设备隔离。
- [x] 五语言界面与输入操作提示。
- [x] 新增相关回归通过；完整测试已执行，环境限制见下。

## 设计与实现计划
- 每设备输入对话框；物理键盘设置通过明确点击后的异步 ADB intent 打开，带超时和关闭清理。
- 使用既有 manager.restart，不触发关闭 USB 调试。

## 实际变更
- core.py：device_input 配置验证、兼容默认值、每设备 scrcpy 参数。
- ui.py / app.py：设备行输入入口、模式与同步设置、五语言引导；异步指定设备 ADB intent，失败/超时/断线/退出清理；目标设备重启复用现有安全生命周期。
- i18n.py：五语言文字；README.md：操作说明；tests/test_keyboard.py：配置、隔离、保存失败、语言切换、断线与命令清理回归；changelogs/unreleased.md：双语变更日志。

## 验证记录
- `uv run --extra build python -m unittest discover -s tests -v`：默认缓存权限不足，未启动测试。
- `.venv/bin/python -m unittest discover -s tests -v`：83 项，80 通过；ADB 回环监听、无线网页监听、语言切换测试中的登录自启动保存因沙箱权限失败。
- 请求沙箱外同命令重跑：自动审批服务返回 codex-auto-review 模型不支持，未执行；没有绕过审批。
- `.venv/bin/python -m unittest discover -s tests -p test_keyboard.py -v`：3 项全部通过（最终布局修改后重跑通过）。
- `git diff --check`：通过。
- 未打包、未提交、未推送；未验证真实 Android、Windows/macOS/Linux 输入法与原生窗口交互。

## 风险与后续事项
- UHID 依赖设备内核与权限，失败需切回 SDK；SDK 不是任意 Unicode 输入接口。手机 intent 成功只表示命令接受，实际布局需在手机确认。
- 需要在允许监听及测试登录自启动写入的环境重跑完整测试，并以真实设备确认输入与粘贴。

## 用户追加：本地打包测试
- 用户授权本地打包，以测试键盘输入。
- `.venv/bin/python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec`：成功，生成 `dist/EasyScrcpy.app`，macOS Apple Silicon（arm64）。
- 使用当前分支工作区代码和已有锁定内置工具；未发布，真实输入交互由用户测试。

## 用户验收（2026-10-06）
- 用户测试最新本地 macOS arm64 包，反馈没有问题，功能整体通过。当前纳入 V0.3.0 开发版本，日志移至 changelogs/V0.3.0.md。不据此声明 Windows / Linux 已实机验证。
