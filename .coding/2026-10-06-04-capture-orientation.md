# 方向参数切换为锁定捕获方向（--capture-orientation=@值）

## 元信息
- 日期：2026-10-06
- 状态：完成
- 关联需求或记录：2026-10-06-03-display-orientation.md（本次为其后续修复）、2026-10-06-02-landscape-keyboard-research.md

## 需求与范围
- 用户目标：实测 03 号记录的“方向”选项后发现两个问题——`--display-orientation` 只把窗体转横、内部画面仍是竖直内容；且手机物理旋转时窗体跟着转，投屏反而变竖。期望找到“ADB 触发手机横屏并锁定”的方案；验证后改为不随手机旋转的锁定捕获方向。
- 本次包含：
  - 实机第二轮验证：`user-rotation lock` 是否真正生效、旋转是否由传感器驱动、能否通过 ADB 注入传感器参数置横屏。
  - 方向参数由 `--display-orientation=<value>` 切换为 `--capture-orientation=@<value>`（锁定捕获方向，0 仍不追加参数）。
  - 更新方向下拉 tooltip 文案（五语言），说明锁定捕获、手机物理旋转不带动画面。
  - 同步更新回归测试。
- 不包含：
  - `--orientation`（同时改捕获与显示）、flip 变体、虚拟显示。
  - 自动修改手机旋转设置或传感器注入的任何持久化功能（验证结论为不可行，见下）。
  - 键盘模式等调研文档其他项。
- 约束与兼容性：
  - 配置结构不变：仍为 `device_orientation: dict[str, int]`，值域 0/90/180/270，旧配置直接兼容（仅启动参数变化）。
  - 内置 scrcpy 5.0 已确认支持 `--capture-orientation=@value`（`scrcpy --help` 实测）。
  - 手机屏幕与应用布局不受影响；锁定仅作用于捕获流。

## 验收条件
- [x] 启动参数按设备追加 `--capture-orientation=@<value>`，默认（0）不追加，其他设备互不影响。
- [x] tooltip 文案更新为锁定捕获语义，五语言齐全、占位符一致。
- [x] 全部测试通过；`git diff --check` 无空白错误。
- [x] 实机验证结论（传感器驱动、锁定被厂商忽略、无 ADB 注入途径）写入本记录并恢复设备原状态。
- [x] 重新打包本机产物并启动验证。

## 实机第二轮验证结论（2026-10-06）
- 设备：无线 ADB 两台已授权设备（Android 17 直板机、Android 16 折叠屏）。
- 旋转由传感器驱动：`cmd window user-rotation lock 1` 后 `settings` 中 `user_rotation=1` 写入成功，但 WMS 状态始终为 `mUserRotationMode=USER_ROTATION_FREE`，厂商实现忽略锁定；上一轮“横屏成功”实为用户物理旋转手机触发的传感器事件。
- 无法通过 ADB 伪造传感器：加速度传感器（Bosch bmi2xy）仅经 sensors HAL 暴露，无 `/dev/input/eventX` 节点（sendevent 不可行）；`cmd sensorservice` 无注入命令；该版本 `wm set-user-rotation` 已移除。
- 副作用复现：`cmd window user-rotation free` 会把 `accelerometer_rotation` 置 1。
- 结论：“ADB 锁定手机横屏、免用 scrcpy 旋转参数”的思路在这两台设备上不可行；手机横屏只能靠物理旋转（传感器）或应用自身请求方向。
- 恢复：两台设备 `user_rotation=0`、直板机 `accelerometer_rotation=0`，与测试前一致。
- 替代方案：scrcpy 5.0 `--capture-orientation=@<value>` 官方语义为锁定捕获方向，“a physical device rotation does not change the captured video orientation”，即窗体不再跟随手机物理旋转；捕获侧旋转使画面内容保持正立，同时解决 03 号记录“窗体横、内容竖”的问题。

## 设计与实现计划
- 方案及取舍：仅替换 `scrcpy_arguments` 中的参数形态，配置字段、UI 结构、保存/重启流程全部复用；不新增设置项。
- 设备 / 平台 / 权限影响：无；仅 scrcpy 启动参数变化，不修改手机设置。
- 预计改动文件：`src/easy_scrcpy/core.py`、`ui.py`、`i18n.py`、`tests/test_orientation.py`、本文档。

## 实际变更
- 变更文件及内容：
  - `src/easy_scrcpy/core.py`：`scrcpy_arguments` 中方向参数由 `--display-orientation=<value>` 改为 `--capture-orientation=@<value>`（0 仍省略）。
  - `src/easy_scrcpy/i18n.py`：方向 tooltip 词条替换为“锁定捕获方向，手机物理旋转不会带动投屏画面；修改会重启该设备投屏。”及对应四语翻译。
  - `src/easy_scrcpy/ui.py`：`orientation_combo` tooltip 引用新词条。
  - `tests/test_orientation.py`：参数断言改为 `--capture-orientation=@90` / 前缀 `--capture-orientation`；tooltip 断言同步。
- 配置 / 翻译 / 资源 / 文档变更：无新增资源；配置格式不变。

## 验证记录
- 执行命令：
  - `QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests -v`：57 个测试全部通过。
  - `git diff --check`：无空白错误。
  - 内置工具确认：`vendor/macos-aarch64/scrcpy --help` 显示 `--capture-orientation` 支持 `@` 前缀锁定（scrcpy 5.0，manifest 确认）。
- 实际结果：参数切换完成，57 个测试通过；打包产物启动正常。
- 打包平台、架构和产物（若执行）：
  - `uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec` 构建成功，产物 `dist/EasyScrcpy.app`（macOS Apple Silicon）与 `dist/EasyScrcpy` 目录。
  - 冒烟测试：`QT_QPA_PLATFORM=offscreen timeout 8 ./dist/EasyScrcpy.app/Contents/MacOS/EasyScrcpy --background` 运行 8 秒被超时终止（exit=124），无崩溃、无异常输出。
  - 未执行 Windows / Ubuntu 打包（构建不是跨平台交叉编译）。
- 未验证部分与原因：
  - 实机投屏画面效果（需活动会话人工确认锁定后物理旋转不带动窗体）。
  - Windows / Ubuntu 打包与界面表现（构建不是跨平台交叉编译，仅 macOS 验证）。

## 风险与后续事项
- 已知限制：
  - `--capture-orientation=@值` 在捕获端旋转，部分应用（如相机、DRM 内容）可能表现不同；手机自身屏幕不变。
  - 锁定后手机物理旋转不再同步到窗体，属预期行为（用户诉求），但与“跟随手机”直觉相反，tooltip 已说明。
- 后续工作：如实机确认锁定捕获满足横屏诉求，可在 README / wiki 截图更新方向选项说明。
- 提交 / 发布信息：未提交；待用户要求后执行。
