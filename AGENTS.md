# Easy Scrcpy 开发规约

本文件适用于整个仓库，供开发者和编码代理遵循。Easy Scrcpy 是独立的 scrcpy GUI / 托盘助手，不是 scrcpy 的 fork。开发时保留现有功能、用户文件和平台差异，不擅自修改手机安全设置或发布配置。

## 项目结构

- `src/easy_scrcpy/app.py`：应用入口、控制器、托盘菜单、设备交互和图标加载。
- `core.py`：设备解析、配置读写、画质预设、scrcpy 参数生成；尽量保持可独立测试。
- `monitor.py`：异步 ADB 查询及 USB 设备状态检测。
- `mirroring.py`：每台设备的 scrcpy 生命周期、重启和手动停止时可选关闭 USB 调试。
- `ui.py`：PySide6 设备面板、设置及画质窗口。
- `i18n.py`：英语、简体中文、法语、德语、日语翻译及即时切换。
- `runtime.py`：源码 / PyInstaller 应用的资源路径、内置工具定位及子进程环境。
- `notifications*.py`：通知协调层、Windows toast、macOS UserNotifications；Ubuntu 不启用可操作通知。
- `assets/`：应用和操作图标原图；`wiki/`：运行截图和文档。
- `packaging/`：依赖更新、下载校验、图标生成、PyInstaller spec 和第三方声明。
- `tests/`：unittest 单元测试及无界面 Qt 集成测试。
- `.github/workflows/`：三平台测试、手动触发打包。
- `.coding/`：必须保留的需求迭代记录，随源码提交。
- `changelogs/`：每个发布版本的双语变更日志，文件名与标签一致（`V0.2.0.md`），随源码提交。

## 工具链和常用命令

开发需要 Python 3.10+，推荐使用 **uv** 管理项目依赖和虚拟环境。GUI 使用 PySide6 / Qt，打包使用 PyInstaller，平台图标转换使用 Pillow。macOS 通知使用 PyObjC；Windows 通知使用 windows-toasts / WinRT，依赖通过平台 marker 自动安装。

在仓库根目录执行：

```bash
# 安装开发和构建依赖，更新 .venv
uv sync --extra build
# 获取本平台内置 scrcpy / ADB，首次需要联网
uv run --extra build python packaging/prepare_runtime.py
# 开发运行 / 托盘后台运行
uv run --extra build python -m easy_scrcpy
uv run --extra build python -m easy_scrcpy --background
# 全部测试；Qt 测试自行设置 offscreen
uv run --extra build python -m unittest discover -s tests -v
# 必要时显式指定无界面 Qt（macOS / Linux shell）
QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests -v
# 平台图标生成（通常打包自动执行）
uv run --extra build python packaging/prepare_icons.py
# 本机平台打包
uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec
# 检查补丁中的空白错误和工作区
git diff --check
git status --short --branch
```

不用 uv 时，创建并激活 `.venv`，运行 `python -m pip install -e '.[build]'`，再使用上述 `python` 命令。Windows PowerShell 使用 `.venv\Scripts\Activate.ps1`；设置环境变量时用 `$env:QT_QPA_PLATFORM = 'offscreen'`。

- 修改依赖后同步 `pyproject.toml` 和 `uv.lock`，不要提交虚拟环境。
- Windows CI 必须保留 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`，文件读写显式指定 UTF-8，避免 CP1252 崩溃。
- 原生通知必须在目标系统和打包应用中验证；offscreen / 模拟测试通过不代表原生交互已验证。
- 构建不是跨平台交叉编译：Windows、macOS、Ubuntu 各自运行 PyInstaller。本机 Apple Silicon 产物不能宣称支持 Intel。
- `dist/EasyScrcpy.app` 是 macOS 产物；Windows / Ubuntu 需分发完整目录或保留权限的归档，不单独发送可执行文件。

### 更新内置工具

```bash
# 默认只预览官方最新稳定版
uv run --extra build python packaging/update_scrcpy.py
# 用户确认后才执行更新
uv run --extra build python packaging/update_scrcpy.py --apply
# 指定上游版本并准备全部支持平台
uv run --extra build python packaging/update_scrcpy.py --version 5.0 --all-targets --apply
```

只使用官方 Genymobile GitHub / Google 下载源和锁定 SHA-256。更新保留备份、失败回滚、不覆盖修改过的依赖。不得跳过校验、执行下载的上游脚本或静默删除旧文件。Windows 上游许可证为 `LICENSE.txt`，保留原件并生成统一的 `LICENSE` 副本。更新后运行测试、复核第三方声明，并重新打包。

## 需求迭代文档（强制）

每次功能需求、行为调整、问题修复或开发流程改动，**必须在 `.coding/` 新建并保留迭代说明**。本规约发布后开始执行，不要求编造过去未记录的验证结果。

1. 开始实现前建立文档，记录用户目标、范围、约束、验收条件和计划。
2. 实现过程中补充设计选择、变更文件、兼容性和风险。
3. 完成后记录实际执行的命令、测试结果、打包情况及尚未验证的部分。
4. 未完成、取消或失败的迭代也保留，注明状态和原因，不删除记录。
5. 需求若持续补充，可更新当前迭代文档；独立需求或后续修复另建文件并引用关联记录。
6. 文档与实现一起提交；`.coding/` 不得加入 `.gitignore` / `.ignore`。不得写入密钥、令牌、设备真实序列号或用户敏感信息。

命名格式：`.coding/YYYY-MM-DD-NN-short-topic.md`，同日按序号递增；日期使用实际记录日期，不伪造。模板见 `.coding/TEMPLATE.md`，目录说明见 `.coding/README.md`。

## 实现规约

### 设备和进程安全

- 用参数数组启动 `QProcess`，不把设备序列号、路径或用户输入拼成 shell 命令。
- 所有投屏明确指定 `--serial`，一设备一进程；只终止本应用启动的进程，不用全局 `pkill` / `taskkill`。`adb kill-server` 只允许在用户明确确认后执行（例如无线连接中 ADB 服务缺少 macOS 本地网络权限时的“重启 ADB 服务”），并先停止本应用投屏。
- 无线连接只保留“IP 连接（已配对）”和“配对码连接（首次）”；配对端口与连接端口不同，ADB 的 pair / connect 退出码为 0 也可能失败，必须解析输出并用 `devices -l` 验证。macOS 包必须保留 `NSLocalNetworkUsageDescription` 和 `NSBonjourServices`。
- ADB 查询失败 / 超时保留之前设备状态，不当作所有设备拔出。
- 停止超时才强制结束，避免 Qt 主线程长时间阻塞；进程、计时器和回调必须清理。
- 画质修改只重启目标设备，不走关闭 USB 调试流程；拔线或退出取消待执行重启。
- 关闭 USB 调试仅限用户显式启用的可选设置及手动 Stop，默认关闭。拔线、退出、画质重启不得修改手机设置；不要承诺所有手机都支持或可以自动重新开启。
- 通知操作使用连接级标识，并经 Qt 信号切回主线程；断开后旧通知不可控制重新连接的设备。

### 界面和配置

- 新增用户可见文字必须补齐五种语言及占位符一致性测试；ADB / scrcpy 原始输出和历史日志无需翻译。
- 配置向后兼容，新增字段有默认值、类型和范围验证；原子保存，读取失败不覆盖原文件。
- 参数控件使用预设下拉选项，不恢复自由数值输入；旧有效值可保留为额外选项。
- Start、Stop、画质配置图标按钮为 40×40，图标 24×24，居中，设备行至少 56 px；保留多语言 tooltip 和 accessible name，不让图标溢出。
- 主界面关闭后常驻托盘；托盘不可用时保留窗口。平台通知失败不得导致应用启动失败。
- macOS 托盘使用单色 `tray-icon-mac.png` 模板，其他平台用彩色 `tray-icon.png`；应用大图标单独使用 `icon.png`。
- 新资源通过统一路径辅助函数定位，并确认包含在 PyInstaller 包内；勿依赖当前 shell 工作目录。

## 测试、提交和发布

- 功能改动同步新增回归测试；重点覆盖多设备隔离、失败 / 超时、断线、权限不足、语言切换、配置迁移及打包资源。
- 至少运行相关测试，交付前尽量运行完整测试及 `git diff --check`；明确说明没有验证的系统、设备和原生行为。
- 只有用户要求打包时才以最新代码重新打包；保留构建产物在忽略目录中。
- 源码、原始图标、截图、锁文件、迭代文档提交到 Git；`dist/`、`build/`、`vendor/`、`.cache/`、`.venv/` 不提交。
- 每个分支在合并 / 打标签前，必须把该分支的最终变更写入 `changelogs/`：文件名与标签一致（`V0.2.0.md`，大写 `V`），头部记录发布日期、标签提交与覆盖的提交范围，条目中英双语并按“新增 / Added”“修复 / Fixed”“变更 / Changed”分组。版本号未定时先写 `changelogs/unreleased.md`，打标签时重命名；已发布版本的文件只追加勘误，不改写既有结论。变更日志与源码一起提交，不得加入 `.gitignore`，不写入密钥、令牌或设备真实序列号。
- 不擅自提交、推送、移动标签或创建 Release；用户要求后执行，并检查远程当前状态。标签大小写敏感，项目使用 `V0.1.1` 这类大写 `V` 标签。
- 用户要求更新已有标签时，优先使用准确旧对象值的 `--force-with-lease`，避免覆盖他人的并发变更。
- 当前打包工作流是 `workflow_dispatch`，产物上传 Actions Artifacts，**不是自动上传 Release**。标签 / Release 更新不会自动替换运行包。
- 正式公开分发需复核签名 / 公证、第三方许可证、静态 LGPL 的源代码及可重链接材料，不将成功打包等同于完成发布合规。
