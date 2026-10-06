# 无线连接 ADB 服务状态

## 元信息
- 日期：2026-10-06
- 状态：完成

## 需求与范围
- 打开无线连接对话框后异步检查 ADB 服务，正常显示绿色圆点及服务端口，异常建议点击重启 ADB 服务。
- 保留已有重启确认和停止本应用投屏流程；不自动 kill-server，不修改设备设置。
- 保留工作区已有 .gitignore 和 .ignore 修改。

## 验收条件
- 服务协议响应有效才显示绿色，失败及超时显示重启建议。
- 显示实际配置的 ADB 服务端口，重启后刷新，关闭对话框清理检查。
- 五种语言齐全，回归测试通过。

## 设计与实现计划
- 通过异步 TCP 的 ADB host:version 请求检查服务，而非仅判断端口监听；不主动启动或重启服务。
- 默认 localhost:5037，遵循 ADB_SERVER_SOCKET / ANDROID_ADB_SERVER_ADDRESS / ANDROID_ADB_SERVER_PORT。
- 修改 wireless_ui.py，新增独立检查模块、翻译和测试。

## 验证记录
- `uv run --extra build python -m unittest discover -s tests -v`：80 项测试通过，含协议成功、分段响应、无效响应、超时、端口配置、对话框刷新与清理；五语言占位符测试通过。首次运行因 uv 缓存权限失败，授权后重跑成功。
- `git diff --check`：通过。
- 未打包、未提交、未推送；未验证真实手机、Windows / Linux 原生界面和打包应用。
- 后续用户要求本地打包：执行 `uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec` 成功，产物 `dist/EasyScrcpy.app`，macOS Apple Silicon arm64。首次因 uv 缓存权限失败，授权后重跑成功。未提交、未推送；打包应用实际无线功能待用户验证。
- 提交前复核（offscreen 脚本直连本机真实 ADB 服务）：`server_endpoint(tool_environment())` 返回 `('localhost', 5037)`，探测结果为 `True localhost:5037`；把 `ADB_SERVER_SOCKET` 指向未监听的 `tcp:127.0.0.1:5039` 时返回 `False 127.0.0.1:5039`，且 `active` 复位。全量测试重跑 80 项通过，`git diff --check` 无输出。

## 实际变更
- 新增 adb_status.py：独立只读异步 TCP 检查，3 秒超时，验证 host:version 响应。
- wireless_ui.py：顶部 10px 圆点、状态地址与端口，每 5 秒刷新，重启后立即刷新，关闭时释放检查。
- i18n.py：补齐五语言；test_adb_status.py：新增 3 项回归测试。
- 分支：codex/features-adb-server-status。

## 风险与后续事项
- 协议响应仅代表服务可访问，不保证手机或 mDNS 可访问；保留已有 mDNS 诊断。
- 非 TCP 的 ADB_SERVER_SOCKET 当前显示异常，不猜测端口。
