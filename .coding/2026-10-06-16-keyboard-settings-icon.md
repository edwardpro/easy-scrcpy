# 键盘设置图标按钮

## 元信息
- 日期：2026-10-06
- 状态：完成
- 关联记录：2026-10-06-15-wireless-disconnect-button.md

## 需求与范围
- 将设备操作区键盘输入文字按钮改为用户提供的 assets/menu-kb-settings.png 图标按钮。
- 保留原操作、启用条件、五语言提示及无障碍名称；按钮 40×40，图标 24×24。

## 验收条件与计划
- 使用统一 icon_path 和缺图回退；PyInstaller PNG glob 自动包含资源。
- 更新 ui.py、图标回归测试和 unreleased 变更日志；验证五语言、目标隔离与禁用状态。

## 实际变更与验证
- ui.py 改为 QToolButton，统一尺寸、图标路径与回退，保留 input_requested 信号和原启用条件。
- test_icons.py 新增五语言、尺寸、操作区位置、USB / 无线目标隔离、离线与停止中禁用回归；更新双语 unreleased。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p test_icons.py -v`：6 项全部通过。
- `git diff --check`：通过。完整测试此前的环境限制见关联记录，本次未重复运行。
- 未提交、未打包。真实设备和 Windows / Linux 原生界面未验证。
- 用户随后要求本机打包验证：`UV_CACHE_DIR=/private/tmp/easy-scrcpy-uv-cache uv run --extra build --no-sync python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec` 成功；产物 `dist/EasyScrcpy.app`，macOS arm64。默认 uv 缓存受限，改用临时缓存。
- 已检查应用包包含 menu-close-conn.png 和 menu-kb-settings.png；真实界面效果待用户安装验证。未提交或发布。
