# ADB 状态区域位置与边框

## 元信息
- 日期：2026-10-06
- 状态：完成
- 关联记录：2026-10-06-07-adb-server-status.md

## 需求与范围
- 用户要求将 ADB 服务状态移至底部 Restart 按钮上方，添加外围边框突出独立功能。
- 仅调整布局，保留检查和重启行为；沿用本地打包验证流程。

## 验收条件与计划
- 状态区域位于按钮行正上方，边框包围圆点和说明，保留自动换行。
- 运行相关回归测试及 git diff --check，重新构建 macOS arm64 应用。

## 实际变更与验证
- wireless_ui.py：将圆点与状态文字包裹于独立 QWidget，1px 边框、6px 圆角及内边距；移到按钮行正上方。
- changelogs/unreleased.md：补充双语布局变更。
- `uv run --extra build python -m unittest discover -s tests -p test_adb_status.py -v`：3 项通过。
- `uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec`：成功，产物 dist/EasyScrcpy.app，macOS arm64。
- `git diff --check`：通过。
- 原生界面视觉及真实设备待用户验证；未提交、推送。
- 用户再次要求重新打包：再次执行上述 PyInstaller 命令成功，重新生成 dist/EasyScrcpy.app（macOS arm64），供本地验证。
- 用户确认本地验证无问题，并要求完成 changelogs 后提交和 push。
