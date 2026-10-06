# upload-artifact 升到 v7 以启用 archive: false

## 元信息
- 日期：2026-10-06
- 状态：完成（工作流已改，待再次触发验证）
- 关联需求或记录：2026-10-06-09-artifact-naming.md

## 需求与范围
- 用户目标：真实运行 build.yml 后产物文件名正确，但出现 warning：`Unexpected input(s) 'archive', valid inputs are ['name', 'path', 'if-no-files-found', 'retention-days', 'compression-level', 'overwrite', 'include-hidden-files']`。
- 本次包含：把 `actions/upload-artifact` 升到支持 `archive` 输入的版本；AGENTS.md 记录该输入的版本要求；变更日志。
- 不包含：不改归档命令、不改产物命名规则、不改构建矩阵、不创建 Release。
- 约束与兼容性：必须继续保留可执行权限，不能让 Actions 二次压缩。

## 验收条件
- [x] 定位 warning 根因并给出版本依据。
- [x] 工作流不再出现 `Unexpected input(s) 'archive'`（依据 v7 `action.yml` 的输入定义）。
- [x] `archive: false` 生效时产物名等于归档文件名，不再出现多层 zip。
- [x] YAML 可解析，`git diff --check` 通过。

## 设计与实现计划
- 方案及取舍：`archive: false`（direct upload）是 `actions/upload-artifact` **v7.0.0** 新增能力，v7.0.0 发布说明明确：仅支持单文件、glob 命中多个文件会失败、`name` 被忽略并以**上传文件名作为 artifact 名**。v6 没有该输入，GitHub Actions 对未知输入只报 warning 并继续执行，因此上一次运行实际退回到默认 `archive: true`：我们生成的归档又被 Actions 压了一层。升级到 v7 是唯一既保留权限又不产生嵌套的做法；替代方案（放弃自打包让 Actions 压缩）会丢可执行权限，违反 AGENTS.md。
- 设备 / 平台 / 权限影响：不涉及手机与 ADB；三平台归档命令不变。
- 预计改动文件：`.github/workflows/build.yml`、`AGENTS.md`、`changelogs/unreleased.md`、本文档。

## 实际变更
- `.github/workflows/build.yml`：`actions/upload-artifact@v6` → `@v7`，并在 `with` 上方注明 v7 direct upload 下 `name` 只是 `archive: true` 时的兜底。
- `AGENTS.md`：发布规约补充「必须用 `@v7`；`archive` 是 v7.0.0 新增输入，v6 会静默忽略并再压一层；升降级该 action 时要核对输入是否被支持」。
- `changelogs/unreleased.md`：新建并记录本次修复（双语）。

## 验证记录
- 执行命令：
  - `gh run list --workflow=build.yml`：最近一次成功运行 `37474870821`，在标签 `V0.2.1` 上触发，2m46s。
  - `gh api repos/edwardpro/easy-scrcpy/actions/runs/37474870821/artifacts`：三个 artifact 名为 `easyScrcpy-macos-arm64-0.2.1.zip`（53,551,465 B）、`easyScrcpy-windows-x64-0.2.1.zip`（80,196,668 B）、`easyScrcpy-linux-x64-0.2.1.tar.gz`（108,985,789 B），命名规则生效。
  - `gh api repos/actions/upload-artifact/releases`：v7.0.0（2026-02-26）新增 direct upload，v7.0.1（2026-04-10）为最新；v6.0.0 无 `archive`。
  - `gh api "repos/actions/upload-artifact/contents/action.yml?ref=v7"`：`archive` 输入存在，描述为「`archive` 为 false 时只能上传单文件，文件名即 artifact 名，忽略 `name`」。
  - 下载 macOS artifact 并 `unzip -l`：**外层 zip 内只有一个条目 `easyScrcpy-macos-arm64-0.2.1.zip`**，证实 v6 确实二次压缩（下载名为 `<artifact>.zip`，即嵌套两层）。
  - `uv run --with pyyaml python -c "import yaml; yaml.safe_load(...)"`：解析通过。
  - `git diff --check`：无输出。
- 实际结果：根因确认（v6 不支持 `archive`，静默退回二次压缩）；已改为 v7。
- 打包平台、架构和产物（若执行）：本次未执行 PyInstaller；上一次 Actions 运行的三平台产物见上，均为嵌套 zip，需在修复后重新触发一次以获得干净产物。
- 未验证部分与原因：改动后**尚未真实触发** workflow_dispatch，因此 v7 在 `archive: false` 下的实际 artifact 名、以及 Windows runner `tar.exe -a` 生成 zip 是否被 v7 正常上传，都还需一次真实运行确认；本机无法执行 GitHub runner 环境。

## 风险与后续事项
- 已知限制：
  - v7 的 direct upload 只允许单文件，`path` 命中多个文件会直接失败；当前每平台只生成一个归档，符合前提，但若以后加产物需拆成多个上传步骤。
  - v7 改为 ESM 实现，仅在 GitHub 托管 runner 上验证；自托管 runner 需具备对应 Node 运行时。
  - 上一次运行（`37474870821`）的三个 artifact 是嵌套 zip，仍可解压使用，但解压两次才能得到应用；如需要干净产物应重新触发构建。
- 后续工作：重新触发 workflow_dispatch，确认无 warning、artifact 名与归档文件名一致、解压一次即可用且可执行权限保留。
- 提交 / 发布信息：尚未提交。
