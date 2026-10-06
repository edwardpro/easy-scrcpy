# Windows 键盘入口回归测试时序修复

## 元信息
- 日期：2026-10-06
- 状态：完成（Windows CI 待重跑）
- 关联记录：2026-10-06-11-keyboard-input.md

## 需求与范围
- 用户提供 Windows CI：83 项，1 error，2 skipped；test_keyboard 在读取 command.arguments 时 command 为 None。
- 原因：不存在的程序可同步发出 FailedToStart，正常清理后测试才读取进程；原测试假设异步失败。
- 本次仅修正回归测试时序，保留生产进程清理行为。

## 验收与计划
- 参数检查时 mock QProcess.start，随后单独覆盖即时失败与真实启动失败、超时清理。
- 运行键盘相关测试、diff 检查；Windows CI 需远程重新执行。

## 实际变更与验证
- tests/test_keyboard.py：参数断言在 mock start 下执行，通过 FailedToStart 信号显式验证同步清理；真实启动失败不再读取可能已经释放的 command。
- changelogs/V0.3.0.md：双语修复条目。
- `.venv/bin/python -m unittest discover -s tests -p test_keyboard.py -v`：3 项通过；模拟未启动进程产生 Qt device not open 诊断，不影响断言。
- `git diff --check`：通过。未运行 Windows CI、未打包；生产功能未变更。

## 补充验证
- 用户再次要求处理失败测试；额外模拟 start() 返回前同步发出 FailedToStart，验证命令清理、计时器停止及按钮恢复。
- mock 未启动进程的标准输出以消除模拟场景 Qt 诊断。
- 键盘相关 3 项重跑全部通过，git diff --check 通过；Windows CI 仍需重跑。
