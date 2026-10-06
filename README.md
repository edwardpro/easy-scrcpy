# Easy Scrcpy

基于 [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) 的独立 GUI / 托盘助手，不修改 scrcpy 的投屏核心。支持 Windows、macOS、Ubuntu。

## 功能

- 菜单栏 / 系统托盘常驻，关闭面板不退出；通过“退出”停止所有由本应用启动的投屏。
- 每 2 秒通过 ADB 异步检测 USB Android 设备，不把 Wi-Fi 设备和模拟器作为 USB 设备。
- 设备完成授权后询问是否投屏，同一次连接只询问一次；拒绝后可手动启动。
- 多台设备各自启动一个 scrcpy 进程与投屏窗口，支持独立停止或全部停止。
- USB 拔出 / 设备离线后停止对应进程；正常停止超时后强制结束，不杀其他应用的进程或全局 ADB 服务。
- 设置 ADB / scrcpy 路径、连接提示、分辨率、帧率和音频转发。
- 当前用户登录自启动：macOS LaunchAgent、Windows HKCU Run、Ubuntu XDG autostart。
- 单实例锁、运行日志、依赖缺失和投屏错误提示。托盘不可用时保留主窗口。
- 英语、简体中文、法语、德语、日语；默认跟随系统（其他系统语言回退英语）。在“设置 → 语言”选择，保存后立即更新界面 / 托盘 / 待确认投屏弹窗，无需重启。历史日志和 scrcpy / ADB 原始输出不翻译。

## 前置条件

安装打包应用不需要 Python、ADB 或 scrcpy。开发 / 构建需要 Python 3.10+。手机 Android 5.0+，开启开发者选项与 **USB 调试**，首次连接在手机上确认电脑 RSA 授权。音频转发需要 Android 11+。

**仅开启开发者模式不够，ADB 无法通过尚未建立的调试连接开启 USB 调试或绕过授权。** 未开启 USB 调试的手机可能不出现在设备列表中。Linux 的 USB 权限和 Windows 的 OEM USB 驱动也需要正确配置。

安装包内置官方便携版 **scrcpy 5.0 + ADB 37.0.1**，包括 Android 服务端和配套动态库。启动 / 投屏时不下载依赖。优先级：设置中的显式路径 → 内置版本 → 系统 PATH / 常见 SDK 路径（开发环境兜底）。通常无需填写路径。

内置依赖不等于内置驱动：Windows 个别手机仍需 OEM USB 驱动；Ubuntu 仍需 USB 访问权限 / udev 规则。桌面图形库和 GPU 驱动属于操作系统依赖。

## 开发运行

在项目目录运行：

```bash
python3 -m venv .venv
# macOS / Ubuntu
source .venv/bin/activate
# Windows PowerShell 使用：.venv\Scripts\Activate.ps1
python -m pip install -e .
python packaging/prepare_runtime.py
python -m easy_scrcpy
```

或使用 uv：

```bash
uv sync
uv run python packaging/prepare_runtime.py
uv run python -m easy_scrcpy
```

隐藏主窗口启动：`python -m easy_scrcpy --background`。

登录自启动需保持安装位置 / 虚拟环境路径不变。macOS 开关对下次登录生效，不启动第二个实例。Ubuntu GNOME 某些环境需安装 AppIndicator 扩展才能显示托盘，Wayland 下弹窗是否获得焦点由桌面环境决定。

## 测试

```bash
python -m unittest discover -s tests -v
```

无显示器环境可用 `QT_QPA_PLATFORM=offscreen` 运行 Qt 集成测试。测试使用模拟子进程，不需要手机，也不改变真实自启动配置。

## 更新内置 scrcpy / ADB（维护者）

```bash
# 查询官方最新稳定版，仅预览，不修改文件
uv run python packaging/update_scrcpy.py
# 确认更新：同步锁定版本、SHA-256、第三方版本声明和本机依赖
uv run python packaging/update_scrcpy.py --apply
# 指定版本 / 一次准备所有平台
uv run python packaging/update_scrcpy.py --version 5.0 --all-targets --apply
# 验证后重新打包
uv run --extra build python -m unittest discover -s tests -v
uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec
```

也可用 `python` 代替 `uv run python`。脚本仅访问官方 GitHub / Google 下载源；版本与校验信息来自官方发布 API 和对应 tag 的构建脚本，不执行上游脚本。GitHub API 限流时可设置 `GITHUB_TOKEN`。

`--target <平台-架构>` 可重复指定；已有的受支持 `vendor/` 平台会一并更新，避免残留旧版本。先在临时目录完整下载、校验、准备，再替换项目文件。原依赖及配置保留在 `.cache/backups/`；失败时恢复已替换文件，不删除原文件。脚本不更新已安装应用或 `dist/`，需要重新打包；构建期间请勿同时运行更新脚本。上游缺少资产 / 校验值或构建脚本格式改变时会报错，要求人工检查。

## 打包

分别在目标操作系统构建（PyInstaller 不能直接跨系统打包）：

```bash
python -m pip install -e '.[build]'
python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec
```

构建脚本自动下载官方便携版并按 `packaging/dependencies.json` 中锁定的 SHA-256 校验；保留全部发布文件及 ADB 原始 NOTICE。依赖准备在 `vendor/<平台-架构>/`，缓存位于 `.cache/downloads/`，均不提交到 Git。重复构建会校验已准备文件，不覆盖不同版本或被修改的依赖。

输出在 `dist/`，必须分发完整目录 / macOS `.app`，不是单独一个可执行文件。macOS 应用为菜单栏应用，不常驻 Dock。支持 macOS Apple Silicon / Intel、Windows x64 / ARM64、Ubuntu x64；Ubuntu ARM64 暂无上游官方便携包，构建会明确报错。需使用相应架构的 Python 构建。

`.github/workflows/build.yml` 可手动触发三平台构建，并上传内置依赖的构建产物供测试（不自动发布）。正式公开发布前需处理 macOS 签名 / 公证、Windows 签名，补齐静态 LGPL 依赖的对应源代码 / 可重链接材料与完整许可证；详见 `packaging/THIRD_PARTY_NOTICES.md`。

设置及轮转日志存放在 Qt 的用户配置目录：
- macOS：`~/Library/Preferences/EasyScrcpy/EasyScrcpy/`
- Windows：`%LOCALAPPDATA%/EasyScrcpy/EasyScrcpy/`
- Ubuntu：`~/.config/EasyScrcpy/EasyScrcpy/`

设备断开响应通常在 2 秒左右，ADB 正常查询需少量额外时间；查询失败时保留之前状态，避免误杀仍在投屏的设备。设备数量较多时 USB 带宽和电脑编码 / 解码负载会影响性能。

本项目是非官方 GUI，scrcpy 及相关组件版权和许可证属于各自作者。安装包的 `runtime/` 内保留原始 LICENSE、`licenses/platform-tools-NOTICE.txt`、第三方声明及依赖校验清单。
