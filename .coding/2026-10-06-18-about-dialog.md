# 托盘关于窗口

## 元信息
- 日期：2026-10-06
- 状态：完成

## 需求与范围
- 托盘主菜单增加“关于”，显示当前版本、Git 仓库地址，底部提供“关闭”按钮。
- 版本取运行时 __version__；地址使用已核对的 origin 对应 HTTPS 地址；五语言一致。

## 验收与计划
- 新增非阻塞 AboutDialog，菜单连接控制器入口；关闭仅关闭窗口。
- 新增五语言与窗口内容回归，更新 V0.3.1 日志。不提交或打包。

## 实际变更与验证
- ui.py 新增 AboutDialog：版本来自 __version__，HTTPS 仓库链接可点击，关闭按钮关闭窗口并清理。
- app.py 托盘主菜单在退出前增加关于入口；i18n.py 补齐五语言；V0.3.1 日志记录新增功能。
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -p test_about.py -v`：2 项通过，覆盖五语言内容、版本、链接、关闭行为及翻译占位符一致性。
- `git diff --check`：通过。未重复完整测试，已知环境限制见迭代 15。
- 未打包、提交或发布；真实 macOS 托盘窗口交互及 Windows / Linux 未验证，现有 dist 尚不包含关于窗口。
- 用户随后要求本地重新打包：`UV_CACHE_DIR=/private/tmp/easy-scrcpy-uv-cache uv run --extra build --no-sync python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec` 成功。
- 产物为 dist/EasyScrcpy.app（macOS arm64）；校验 Info.plist 两个版本字段为 0.3.1，检查本次 PYZ 含 AboutDialog：通过。真实安装交互待用户验证，未提交或发布。
