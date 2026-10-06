# 无线设备断开按钮

## 元信息
- 日期：2026-10-06
- 状态：完成（完整测试存在环境限制）
- 关联需求或记录：2026-10-06-02-wifi-mirroring-design.md

## 需求与范围
- 用户目标：在设备列表中提供无线断开按钮，放在开启共享按钮前，使用用户提供的 assets/menu-close-conn.png。
- 范围：仅无线设备显示，复用现有控制器断开流程与确认提示。
- 约束：不关闭手机无线调试或 USB 调试，不影响其他设备；不提交、推送或打包。

## 验收条件
- [x] 无线设备操作区先显示断开按钮，再显示开始 / 停止投屏按钮；USB 设备不显示。
- [x] 图标按钮 40×40、图标 24×24，tooltip 和 accessible name 支持五语言。
- [x] 点击传递目标设备序列号，复用异步断开流程；新增回归测试通过。
- [ ] 完整测试全部通过（详见环境限制）。

## 设计与实现计划
- 添加设备级断开信号并连接 Controller.disconnect_wireless，使用统一 icon_path；现有 PyInstaller PNG glob 自动包含资源。
- 预计变更：ui.py、app.py、test_icons.py、用户图标、changelogs/unreleased.md。

## 实际变更
- ui.py 添加无线设备专属图标按钮和设备级信号；app.py 连接现有 disconnect_wireless。
- test_icons.py 覆盖五语言、按钮顺序与尺寸、USB 隐藏、目标隔离、停止中禁用和离线无线设备断开入口。
- 使用用户提供的 PNG；复用已有翻译；PyInstaller 的 assets/*.png glob 包含该资源。新增 unreleased 双语变更日志。

## 验证记录
- `QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests -v`：uv 默认缓存目录受限；改用临时缓存后依赖构建因网络 DNS 不可用失败。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`：84 项，81 通过，2 失败、1 错误。ADB 状态与 discovery 测试无法监听本地端口；语言切换测试配置未成功保存。没有改动这些行为。
- 尝试放宽沙箱重跑完整测试：自动审批模型不受支持，审批未完成，命令未执行。
- 图标专项测试与 git diff --check：通过。
- 未打包；真实无线设备和 Windows / Linux 原生界面未验证。

## 风险与后续事项
- ADB 断开会影响其他工具对同一设备的连接，沿用现有确认提示。
