# Unreleased

- 发布日期 / Release date：待定 / TBD
- 标签提交 / Tag commit：未打标签 / Not tagged
- 覆盖范围 / Commit range：`0290d4b..`（`V0.2.1` 之后的变更 / changes after `V0.2.1`）

## 新增 / Added
- 无 / None.

## 修复 / Fixed
- 无 / None.

## 变更 / Changed
- GitHub Actions 构建产物统一命名为 `easyScrcpy-{platform}-{arch}-{version}.{ext}`（如 `easyScrcpy-macos-arm64-0.2.1.zip`、`easyScrcpy-windows-x64-0.2.1.zip`、`easyScrcpy-linux-x64-0.2.1.tar.gz`）；`version` 读 `pyproject.toml`，`platform` / `arch` 来自 `runner.os` / `runner.arch`，Ubuntu 仍为 `.tar.gz`。
  Build artifacts from GitHub Actions are now named `easyScrcpy-{platform}-{arch}-{version}.{ext}` (for example `easyScrcpy-macos-arm64-0.2.1.zip`, `easyScrcpy-windows-x64-0.2.1.zip`, `easyScrcpy-linux-x64-0.2.1.tar.gz`); the version comes from `pyproject.toml`, platform and arch from `runner.os` / `runner.arch`, and Ubuntu stays a `.tar.gz`.
- 每个平台自行生成归档（macOS `ditto`、Linux `tar -czf`、Windows `tar -a -cf`），并以 `actions/upload-artifact` 的 `archive: false` 单文件模式上传：下载到的文件名与产物名一致，不再多套一层 zip，也不会丢失可执行权限。
  Each platform creates its own archive (macOS `ditto`, Linux `tar -czf`, Windows `tar -a -cf`) and uploads it as a single file with `actions/upload-artifact` `archive: false`, so the downloaded filename matches the artifact and executable permissions survive instead of being re-zipped by Actions.
- Windows 产物由散文件改为单个 zip，内含完整 `EasyScrcpy/` 目录，与 Ubuntu 归档结构一致。
  The Windows artifact is a single zip containing the complete `EasyScrcpy/` folder instead of loose files, matching the Ubuntu layout.
- `pyproject.toml` 与 `src/easy_scrcpy/__init__.py` 的版本号统一为 0.2.1（此前 `__init__.py` 仍停留在 0.1.0），`AGENTS.md` 增加发版前同步两处版本号的要求。
  The version in `pyproject.toml` and `src/easy_scrcpy/__init__.py` is now consistently 0.2.1 (`__init__.py` was still 0.1.0), and `AGENTS.md` requires keeping both in sync before a release.
