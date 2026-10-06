# Unreleased

- 发布日期 / Release date：待定 / TBD
- 标签提交 / Tag commit：未打标签 / Not tagged
- 覆盖范围 / Commit range：`2a10fb8..`（`V0.2.1` 之后的变更 / changes after `V0.2.1`）

## 新增 / Added
- 无 / None.

## 修复 / Fixed
- 构建产物上传改用 `actions/upload-artifact@v7`：v6 不支持 `archive` 输入，只报 warning 就退回默认压缩，导致下载到的 zip 里还套着一层同名 zip。v7 的 direct upload（`archive: false`）让 artifact 名等于我们生成的归档名，解压一次即可用，并保留可执行权限。
  Artifact upload now uses `actions/upload-artifact@v7`: v6 does not support the `archive` input, warned and fell back to zipping again, so the downloaded zip contained a second zip of the same name. v7 direct upload (`archive: false`) makes the artifact name equal the archive we build, needs a single extraction, and keeps executable permissions.

## 变更 / Changed
- 无 / None.
