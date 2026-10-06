# 每设备显示旋转选项（--display-orientation）

## 元信息
- 日期：2026-10-06
- 状态：完成
- 关联需求或记录：2026-10-06-02-landscape-keyboard-research.md（建议首版范围第 1 项）

## 需求与范围
- 用户目标：启动投屏时可以按设备选择显示方向（默认、90°、180°、270°），并在实机确认 rotate 类命令能否触发手机真正横屏。
- 本次包含：
  - 每设备显示旋转下拉选项，标注“只旋转投屏画面，不改变手机应用方向”。
  - 启动 scrcpy 时按设备追加 `--display-orientation=<0|90|180|270>`（0 时不追加）。
  - 配置持久化与向后兼容（新字段有默认值、类型和范围验证）。
  - 与画质一致：运行中修改方向只重启目标设备投屏，不走关闭 USB 调试流程。
  - 实机验证：ADB 旋转命令（user-rotation 等）能否触发手机横屏，验证后恢复原状态。
- 不包含：
  - 全局方向设置、`--orientation` / `--capture-orientation`、虚拟显示横屏工作区。
  - 键盘模式、剪贴板同步等调研文档其他项。
  - 自动修改手机旋转设置的持久化功能（仅做一次保存/恢复式验证）。
- 约束与兼容性：
  - 旧配置文件无 `device_orientation` 字段时默认空字典，读取失败不覆盖原文件。
  - 只接受 0/90/180/270，其他值拒绝加载；序列号为字符串。
  - 不把显示旋转宣传成“手机应用横屏”。

## 验收条件
- [x] 设备行新增“方向”列：默认、90°、180°、270° 下拉，非可编辑，带多语言 tooltip。
- [x] 启动参数按设备追加 `--display-orientation`，其他设备互不影响。
- [x] 修改方向保存配置；运行中修改仅重启该设备且不触发 USB 调试关闭。
- [x] 五语言翻译齐全、占位符一致；旧配置可加载；非法值报错。
- [x] 实机验证 rotate/旋转命令对手机横屏的影响并恢复原状态，结论写入本记录。

## 设计与实现计划
- 方案及取舍：
  - 参照 `device_quality` 的按设备模式新增 `Settings.device_orientation: dict[str, int]`，与画质配置分离，互不干扰。
  - 只改窗口显示时官方推荐 `--display-orientation`（不影响录制与手机布局），故采用该参数而非 `--orientation`。
  - UI 在设备表新增“方向”列（画质列之后），复用画质的保存/重启流程。
- 设备 / 平台 / 权限影响：不修改手机设置；仅 scrcpy 启动参数变化。
- 预计改动文件：`src/easy_scrcpy/core.py`、`ui.py`、`app.py`、`i18n.py`、`tests/test_orientation.py`。

## 实际变更
- 变更文件及内容：
  - `src/easy_scrcpy/core.py`：`Settings` 新增 `device_orientation: dict`（按序列号存 0/90/180/270），加载时校验序列号为字符串、值必须在 `ORIENTATION_OPTIONS` 内；`scrcpy_arguments` 在值非 0 时追加 `--display-orientation=<value>`；新增常量 `ORIENTATION_OPTIONS = (0, 90, 180, 270)`。
  - `src/easy_scrcpy/ui.py`：设备表由 5 列改为 6 列（新增“方向”列于“画质”之后）；新增 `orientation_combo(current)` 帮助函数（不可编辑、0 显示“默认”、带多语言 tooltip 与 accessible name）；新增 `orientation_requested = Signal(str, int)`；底部提示改为“修改画质或方向会重启该设备投屏，不会关闭 USB 调试；只影响投屏画面，不修改手机屏幕。”
  - `src/easy_scrcpy/app.py`：接入 `orientation_requested`，新增 `select_orientation(serial, orientation)`，逻辑与画质一致：保存配置 → 应用 → 若该设备投屏中则仅重启该设备（`manager.restart`，不走关闭 USB 调试流程）；非法值不保存。
  - `src/easy_scrcpy/i18n.py`：新增 6 行五语言词条（方向、默认、方向参数超出范围、方向 tooltip、方向重启日志、更新后的底部提示）。
  - `tests/test_orientation.py`（新增）：参数按设备隔离与默认值省略、配置往返/旧文件兼容/非法值拒绝、下拉框选项与翻译、面板选择保存与运行中重启、语言切换重建标签。
  - `tests/test_icons.py`：操作按钮所在列由 4 调整为 5（因新增“方向”列）。
- 配置 / 翻译 / 资源 / 文档变更：无新资源文件；`device_orientation` 缺省为空字典，旧配置可直接加载。

## 验证记录
- 执行命令：
  - `QT_QPA_PLATFORM=offscreen uv run --extra build python -m unittest discover -s tests -v`：57 个测试全部通过（含新增 4 个方向测试）。
  - `QT_QPA_PLATFORM=offscreen timeout 8 uv run --extra build python -m easy_scrcpy --background`：应用正常启动，8 秒超时终止，无异常输出。
  - `git diff --check`：无空白错误。
  - 实机旋转验证（无线 ADB，两台已授权设备，Android 17 直板机与 Android 16 折叠屏）：
    - 只读确认初始状态：两台均 `accelerometer_rotation=0`、`user_rotation=0`（竖屏）。
    - `cmd window user-rotation lock 1`：两台均成功写入 `user_rotation=1`（系统接受锁请求），但激活显示的方向未变为横屏（`mCurrentOrientation` 与输入 viewport orientation 均为 0）。直板机测试时处于锁屏界面（无法远程解锁），锁屏方向固定竖屏；折叠屏主屏激活状态下同样未旋转，疑似厂商实现忽略用户旋转。
    - `settings put system user_rotation 1`（旧方法，折叠屏验证）：值被写入但显示同样不旋转，与 Android 12+ 由 WindowManager 掌管旋转的预期一致。
    - 副作用发现：`cmd window user-rotation free` 会把 `accelerometer_rotation` 置为 1（重新打开自动旋转），两台均复现。
    - 恢复：两台 `user_rotation` 均恢复为 0；直板机自动旋转恢复为 0、屏幕恢复熄屏。折叠屏在恢复后 `accelerometer_rotation` 变为 1，无法确认是系统行为还是用户手动开启，未再次覆盖。
- 实际结果：显示旋转功能按验收条件完成；手机真正横屏未在锁屏/折叠屏场景得到确认，详见风险。
- 打包平台、架构和产物（若执行）：
  - 执行 `uv run --extra build python -m PyInstaller --noconfirm packaging/EasyScrcpy.spec`，产物 `dist/EasyScrcpy.app`（macOS Apple Silicon）与 `dist/EasyScrcpy` 目录，构建成功。
  - 用户已将打包应用安装到本机并确认可运行。
  - 未执行 Windows / Ubuntu 打包（构建不是跨平台交叉编译）。
- 未验证部分与原因：
  - 解锁状态下的应用布局变化（远程无法解锁锁屏）。
  - scrcpy 运行时 MOD+r 旋转请求（需活动投屏会话与真实键盘焦点，未在实机模拟）。
  - Windows / Ubuntu 界面表现与打包（仅 macOS 开发环境验证，遵循“构建不是跨平台交叉编译”）。

## 风险与后续事项
- 已知限制：
  - `--display-orientation` 只旋转电脑上的投屏窗口，不改变手机应用布局（按调研结论明确标注）。
  - 实机验证表明 ADB 旋转命令虽被系统接受，但在锁屏界面与厂商折叠屏上显示方向不变化；`user-rotation free` 会顺带打开自动旋转。据此维持调研结论：不将固定旋转命令宣称通用，首版不提供“手机应用自动横屏”选项。
- 后续工作：若需手机应用自动横屏，需在解锁状态且各厂商设备上分别验证旋转命令、应用响应与状态恢复（含 accelerometer_rotation 副作用），再决定支持范围。
- 提交 / 发布信息：未提交、未打包；待用户要求后执行。
