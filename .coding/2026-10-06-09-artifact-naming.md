# 构建产物统一命名 easyScrcpy-{platform}-{arch}-{version}

## 元信息
- 日期：2026-10-06
- 状态：完成（工作流本身未在 GitHub Actions 上实际运行）
- 关联需求或记录：AGENTS.md「测试、提交和发布」

## 需求与范围
- 用户目标：GitHub Actions 构建出来的产物文件名统一为 `easyScrcpy-{platform}-{version}.zip`。
- 本次包含：`.github/workflows/build.yml` 的产物命名、三平台归档命令与上传方式；版本号一致性；AGENTS.md 发布规约；变更日志。
- 不包含：不改成自动上传 Release，不改 PyInstaller spec，不改构建矩阵平台，不做签名 / 公证。
- 约束与兼容性：AGENTS.md 要求 macOS / Ubuntu 使用保留可执行权限的归档；`actions/upload-artifact` 官方文档明确「File permissions are not maintained during zipped artifact upload」，因此不能让 Actions 代为压缩。
- 用户确认的三个决策：`{version}` 只读 `pyproject.toml`；`{platform}` 带 CPU 架构；Ubuntu 保留 `.tar.gz`（不强制改成 zip）。

## 验收条件
- [x] 三平台产物名为 `easyScrcpy-{platform}-{arch}-{version}.{ext}`，`ext` 在 Linux 为 `tar.gz`、其余为 `zip`。
- [x] 从 Actions 下载到的文件名与产物名一致，不出现多层 zip。
- [x] macOS / Linux / Windows 归档均保留可执行权限与顶层 `EasyScrcpy` 目录。
- [x] `pyproject.toml` 与 `src/easy_scrcpy/__init__.py` 版本号一致（0.2.1）。
- [x] YAML 可解析、命名逻辑本地模拟通过、全量回归测试通过。

## 设计与实现计划
- 方案及取舍：
  - 新增 `Resolve artifact name` 步骤（`shell: bash`，三平台统一），用 `tomllib` 读 `pyproject.toml` 的 `project.version`，`runner.os` / `runner.arch` 转小写得到 `platform` / `arch`，输出 `artifact`（文件名）与 `archive`（`dist/` 路径）。
  - 上传使用 `actions/upload-artifact@v6` 的 `archive: false`：该模式只允许单文件，且**上传文件名会覆盖 `name`**，正好让下载名等于我们自己生成的归档名，同时避免 Actions 二次压缩丢权限。配 `if-no-files-found: error`，缺产物直接失败而不是静默上传空件。
  - Windows 用 `tar -a -cf`（bsdtar 按扩展名生成 zip）而不是 `Compress-Archive`：避免 PowerShell 与 bash 的引号差异，也避免旧版 `Compress-Archive` 写入反斜杠条目导致跨平台解压异常；zip 内保留 `EasyScrcpy/` 顶层目录，与 Linux 一致。
  - 设备 / 平台 / 权限影响：不涉及手机、ADB 或系统权限；只改 CI 产物形态。
  - 预计改动文件：`.github/workflows/build.yml`、`pyproject.toml`、`src/easy_scrcpy/__init__.py`、`AGENTS.md`、`changelogs/unreleased.md`。

## 实际变更
- `.github/workflows/build.yml`：新增 `Resolve artifact name`（id `names`）与 `List archives` 步骤；macOS `ditto`、Linux `tar -czf` 的输出改为 `${{ steps.names.outputs.archive }}`；新增 Windows `tar -a -cf` 归档步骤（原工作流在 Windows 上不打包，直接上传散文件）；上传步骤由 `dist/*.zip`、`dist/*.tar.gz`、`dist/EasyScrcpy/**` 通配改为单文件 + `archive: false`，`name` 由 `EasyScrcpy-${{ matrix.os }}` 改为产物文件名。
- `pyproject.toml`：`version` 0.1.0 → 0.2.1（本次沿用工作区已有修改）。
- `src/easy_scrcpy/__init__.py`：`__version__` 0.1.0 → 0.2.1，与 pyproject 保持一致。
- `AGENTS.md`：新增两条发布规约（产物命名与版本号同步要求、各平台自行归档 + `archive: false` 的原因）。
- `changelogs/unreleased.md`：新建，记录本次变更（双语）。

## 验证记录
- 执行命令：
  - `uv run --with pyyaml --extra build python`：解析 `build.yml`，确认 YAML 合法、`archive` 解析为布尔 `false`、上传步骤字段正确。
  - 同一脚本按矩阵推导产物名：`macOS/ARM64 → easyScrcpy-macos-arm64-0.2.1.zip`、`Windows/X64 → easyScrcpy-windows-x64-0.2.1.zip`、`Linux/X64 → easyScrcpy-linux-x64-0.2.1.tar.gz`。
  - 临时目录中以 `bash` 原样执行 `Resolve artifact name` 脚本体（注入 `RUNNER_OS` / `RUNNER_ARCH` / `GITHUB_OUTPUT`），并对三平台分别执行 `tar -a -cf`：产物名与预期一致；用 `zipfile` 检查 Windows zip 条目为 `EasyScrcpy/`（0o40755）与 `EasyScrcpy/EasyScrcpy`（0o100755），可执行位保留；`tar -tzvf` 检查 Linux 归档为 `-rwxr-xr-x`。
  - `QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests`：80 项全部通过。
  - `uv run --extra build python -c "import easy_scrcpy; print(easy_scrcpy.__version__)"`：输出 `0.2.1`。
  - `git diff --check`：无输出。
- 实际结果：命名逻辑与归档命令在本机（macOS arm64）验证通过；测试全绿。
- 打包平台、架构和产物（若执行）：本次未执行 PyInstaller，也未触发 workflow_dispatch。
- 未验证部分与原因：
  - 未在 GitHub Actions 上真实运行（需要先推送并由用户触发），因此 `runner.os` / `runner.arch` 的实际取值、Windows runner 上 `tar.exe`（bsdtar）对 `-a` 生成 zip 的支持、`upload-artifact@v6` 的 `archive: false` 行为均只依据官方文档与本机 bsdtar 结果，未实测。
  - 首次验证脚本因在 zsh 下未做单词分割得到错误产物名，改用 `bash` 重跑后正确；这是测试脚本问题，不是工作流问题（工作流步骤显式声明 `shell: bash`）。

## 风险与后续事项
- 已知限制：
  - 若 `windows-latest` 的 `tar.exe` 不支持写 zip，Windows 步骤会失败；备选方案是 `Compress-Archive -Path dist/EasyScrcpy -DestinationPath <archive>` 或 `python -m zipfile -c`。
  - Windows 产物结构由「散文件」变为「单个 zip，内含 `EasyScrcpy/` 目录」，解压后需进入该目录运行 `EasyScrcpy.exe`；`RELEASE_NOTES.md` 是 v0.1.0 的历史文件，按规约只追加勘误、不改写，如需澄清另建新版本说明。
  - 版本号唯一来源是 `pyproject.toml`，忘记同步会导致产物名带旧版本号；已在 AGENTS.md 写明。
  - 标签 `V0.2.1` 指向的提交里 `pyproject.toml` 仍是 0.1.0，因此**在标签上触发构建会得到 `easyScrcpy-*-0.1.0.*`**；只有在包含本次版本号修改的提交上触发才会得到 0.2.1。若要产物名与 `V0.2.1` 标签一致，需要把版本号修改并入该标签指向的内容（重新打标签）或把下一个版本定为 0.2.2 后再打标签。此项需用户决定，本次未擅自移动标签。
- 后续工作：真实触发一次 workflow_dispatch 核对三个 Artifact 名与解压后可执行权限；如需要正式发布再评估切换到 Release 资产上传。
- 提交 / 发布信息：尚未提交。
