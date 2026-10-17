# TASK-010-R4 验收：通过，TASK-010 结案

验收人：GPT；日期：2026-10-11；项目：D:\harness work\audit_sa_project。

**结论：ACCEPTED。R3 唯一剩余的 F05 测试证据缺口已关闭，TASK-010 开发态宿主通过验收。**这不是任何真实 Gate 的批准，也不为历史下游产物追认批准。

## 1. 实际复验

本轮没有修改交付的生产代码、测试或指南。新增 GPT QA 证据目录：

- data/reviews/task010_r4_20261011_125204
- 全新完整回归容器：data/workflow_host_tests/task010r4_gpt_20261011_125204
- 新回归批次：data/batches/task010r4_gpt_20261011_125204

使用项目 Python、禁写 bytecode，真实执行：

    .venv\Scripts\python.exe -B tests\test_run_demo_workflow.py --out-dir data\workflow_host_tests\task010r4_gpt_20261011_125204

源文本编译通过；回归退出 0，G1—G9 + R1 共 10 组全部 PASS，failures=[]。CLI start/status/record = 16/33/17，公开宿主 API 9、控制器造样 3；实际 receiver/checker 各 17，副本 17、模拟决定 3、真实批准 0、故障注入 26。当前可读清单确认 checker 16，H02 保留原清单另确认 1；独立按接收身份去重后的 17 份记录相符。summary/checks/cli_logs/count_audit 及最终读回一致。

QA 的真实命令、退出码和未执行项见 qa_commands.json；regression.stdout.txt/stderr.txt 保留完整输出。

## 2. F05 关闭依据

独立 AST 检查确认 old_0001_before 第 1085 行 < 目标调用第 1149 行 < old_0001_after 第 1163 行。以实际 AST 输出 artifact_audit.json 为最终行号证据，行号不是运行身份。

分别检查 DeepSeek 最终容器 task010r4_02 和 GPT 新回归容器：before/after 哈希均等于现场旧 0001 的字节哈希，阶段与顺序正确；生产 writer 真实传入的完整文本被捕获，部分文件为该文本的前 40 字节；opens/write/sentinel OSError 各 1，异常链保留，半文件保留，恢复拒绝。完整预期 checkpoint 的 workflow 由冻结控制器从旧 0001 和显式模拟决定重新计算，逐项精确相等，真实批准仍均为 null。

独立执行交付中的 guard_unchanged：同值成功、异值拒绝、缺 before 拒绝；新 QA 文件真实变化被拒绝。再执行交付的完整 real_fault_ok 表达式，证明 unchanged_guard=false 会令完整判据失败。自测没有向正式 failures 加入再移除假失败。

**换行口径说明：**DeepSeek 捕获的生产 writer 文本是 21,168 UTF-8 字节；其完整 JSON 副本通过 Path.write_text 保存，在 Windows 上转为 CRLF，因此落盘为 21,610 字节，共 442 处 CRLF。只还原这些换行后，字节数与捕获的 SHA-256 完全相等，JSON 与完整 workflow 内容一致。文件字节哈希另存于独立 QA，不能将副本文件的字节哈希误称为生产 writer 文本哈希。这是保存格式差异，不是本轮剩余阻断项。

本轮未重复 R3 已通过的 20 项生产宿主独立探针；宿主完整哈希未变。本轮独立检查针对 R4 的两个证据修复及最终统计，没有扩大到无边界 fuzz。

## 3. 范围与保护

- 宿主冻结：d42aeec3a4450d630507821e103e5b923c052e91e790644df143f5311e9475d0
- 测试：852bf336cd2d259e43b4da9eee539a52f48253767c52ff9327f62e12015f5f8c
- 指南冻结：2c164eff0c6e46c5d3de372c0105ccf6736a1c19db7664ff8e3e0bac89038cb3

相对 R3 的 24341 项基线，仅 tests/test_run_demo_workflow.py 一项变化、缺失 0。相对 R2/R1/TASK-010，仍为宿主/测试/指南三项累计变化；14691/13330/12546/10236/8547/6511/4902/874 旧基线全部 0 变化、0 缺失。GPT 本轮起始基线 0 变化、0 缺失；只新增 QA 和交接文档。逐项结果见 protected_files_comparison.json。

## 4. 下一步

主理人无需手工测试、提交模拟决定或签真实 Gate。转交本验收单与 docs/tasks/TASK-011_DRAFT.md 给 DeepSeek 即可。

TASK-011 才授权扩展宿主执行实际标准化/装载并建立 Gate2 待确认请求；这一授权不修改本轮验收结论，也不改变旧批次。正式契约、真实批准、人类判断、AI 建议仍未执行。

