# 中文输入与文本粘贴引导修正

## 元信息
- 日期：2026-10-06
- 状态：完成（操作引导修正，待用户实机验证）
- 关联记录：2026-10-06-11-keyboard-input.md、2026-10-06-02-landscape-keyboard-research.md

## 需求与范围
- 用户实测英文可输入，电脑输入法直接提交中文失败；希望支持文本，最好多媒体粘贴。
- 本次：核实已有 scrcpy 文本粘贴能力，明确中文输入路径及关闭自动同步后 MOD+V 的行为，修正五语言引导。
- 不包含：模拟系统快捷键、手机端应用安装、scrcpy 控制协议接入、多媒体剪贴板传输。

## 验收条件
- [x] 五语言提示明确 UHID 使用手机输入法，电脑提交中文改用文本粘贴。
- [x] 自动同步关闭时明确 MOD+V 仍主动传输并粘贴文本；Ctrl+V 无此保证。
- [x] 回归检查及记录。

## 设计依据
- 本地 `vendor/macos-aarch64/scrcpy --help`：MOD+v 复制电脑剪贴板并注入 Android PASTE；Android 7+。`--no-clipboard-autosync` 关闭 Ctrl+v 前自动同步；MOD+Shift+v / legacy-paste 使用字符按键注入，不能解决任意中文。
- 之前调研：SDK Unicode 限制；UHID 发送物理按键、手机输入法处理组合。scrcpy 控制接口剪贴板只支持文本，不能用相同机制粘贴图片/视频。
- 尝试 curl 获取官方 v5.0 文档：环境 DNS 解析失败；采用已保存调研与本地 v5.0 help。

## 验证记录
- 尚未实机验证；本次不自动向手机粘贴用户剪贴板内容。

## 实际变更与验证
- ui.py / i18n.py：五语言中文输入与显式文本粘贴说明；README.md 与 unreleased 变更日志同步。
- 键盘回归 3 项通过；翻译目录与占位符检查通过；i18n 4 项中 3 通过，既有登录自启动保存测试仍因沙箱权限失败。
- git diff --check 通过。未打包、提交或推送；此前生成的测试包已具备 MOD+V 文本粘贴能力，当前仅更新引导。

## 用户追加：最新代码本地打包
- 用户要求本地打包。
- `.venv/bin/python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec`：成功。
- 产物：`dist/EasyScrcpy.app`，macOS arm64，包含最新中文文本粘贴引导。未发布；实机交互待用户测试。
- 初次成功日志后 dist 根目录中的 app 在检查时已不在，未据此交付。改用 `--distpath dist/keyboard-test` 重新打包成功，实际交付 `dist/keyboard-test/EasyScrcpy.app`；file 确认 Mach-O arm64。

## 用户验收（2026-10-06）
- 用户测试最新本地 macOS arm64 包，反馈没有问题，功能整体通过。当前纳入 V0.3.0 开发版本，日志移至 changelogs/V0.3.0.md。不据此声明 Windows / Linux 已实机验证。
