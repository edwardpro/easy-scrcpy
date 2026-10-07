# 设备行控件视觉协调

## 元信息
- 日期：2026-10-07
- 状态：进行中

## 需求与范围
- 用户目标：按钮缩小、等比例、圆角无边框并带轻微阴影；下拉框与按钮高度协调，状态列收紧。
- 范围：主窗口设备表格，保留操作、翻译、图标资源和至少 56 px 行高。
- 约束：本次用户要求覆盖原 40×40 / 24×24 尺寸，采用 35×35 / 21×21，比例仍为 0.6；不修改设备安全设置，不打包或提交。

## 验收条件
- [ ] 所有设备行图标按钮使用统一圆角、无边框和阴影。
- [ ] 下拉框高度一致并垂直居中，状态列按内容占宽。
- [ ] 操作隔离、禁用状态和多语言回归测试通过。

## 设计与实现计划
- 使用 Qt 调色板颜色和 QGraphicsDropShadowEffect，保留浅色/深色适应及 hover/pressed/disabled 状态。
- 状态列 ResizeToContents，设备及序列号继续伸展；方向控件放入有边距的容器。
- 预计文件：ui.py、test_icons.py、AGENTS.md、changelogs/unreleased.md。

## 实际变更
待补充。

## 验证记录
待执行。未验证 Windows/Linux 原生外观及真实设备；本次不打包。

## 完成记录
- 状态：完成。
- 实际文件：ui.py 统一按钮样式、下拉框尺寸/容器和列宽；test_icons.py 更新尺寸并检查布局中心与阴影；test_orientation.py 适配容器；AGENTS.md 同步新的尺寸规约；changelogs/unreleased.md 双语记录。
- 无新增文字、配置字段或图像资源。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v`：90 项，87 项通过，2 项失败、1 项错误。ADB 状态/无线发现的两项不能在沙箱内绑定本地端口；语言配置保存断言失败。
- 单独执行 test_icons.py：7 项通过；test_orientation.py：4 项通过（新增布局测试在完整运行后添加）。
- 单独执行 test_i18n.py：4 项中 1 项失败。用 HEAD 版本 ui.py 的临时副本复测，同一语言保存断言也失败，确认并非此次样式变更引入。
- 沙箱外完整测试请求未执行：自动审批服务报当前模型不支持，未绕过审批。
- offscreen 模拟设备截图 `/tmp/easy-device-row-preview.png` 已查看：控件居中、按钮阴影及列布局正常。未使用真实设备信息。
- `git diff --check`：通过。
- 未打包、提交或发布；未验证 macOS 原生深色模式、Windows/Linux 原生外观和设备交互。
