# TASK-009-R2 复验：通过

日期：2026-10-11；验收：GPT。结论：**任务九开发态控制协议验收通过，F01—F04 全部关闭，可以领取 TASK-010。**这不是任何真实 Gate 的批准。

## 1. 本次实际复验

复验对象是当前磁盘文件，不仅依据执行回执：

- `scripts/control_demo_workflow.py`：`a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`，版本 `TASK-009-workflow-control-1.2`。
- `tests/test_control_demo_workflow.py`：`09ac1328f52bad00d7e0c7711562f69dfdff1bfb3cf59c9dd5d444fb32347559`。
- `docs/WORKFLOW_CONTROL_GUIDE.md`：`a806a0a1e1b3b6306a949a06bd099e0fb8b7404309765c264e1bde596ca6ab50`。

使用项目 Python 3.11.1，在全新容器 `data/workflow_tests/task009_r2_gpt_20261011_101113` 真实执行验证入口，退出 0、测试失败 0。入口调用 272 次（create 51、prepare 92、record 59、check 70），入口保存文件重放 6 次，总计 278 次。原探针 63、R1 新增 15、R2 新增 8、流程检查 14；helper 自测 1 单列，混入主 checks 为 0。模拟决定 2，真实批准 0。

另由 GPT 的独立 QA 调用公共 API 34 次，单列而不混进上述 278 次：旧十项负向及五个阶段正向控制共 20 次；事件引用 Q01—Q08 共 8 次；保存文件重放 6 次。全部达到预期，输入对象保持不变。

## 2. 缺口关闭依据

**F01：历史协议、事件引用与集合。**旧 P01—P10 仍全部按目标字段阻断。独立重现 Q01—Q08，错误 event_id、gate、request_id、materials_sha256、创建 batch_id、请求绑定、无 history 的额外请求、决定列表重排，均得到指向目标字段或集合的 `WorkflowBlocked`。实际代码逐种事件核验必需字段，并将 state 真正保存的请求与重放结果比较；决定按 history 次序比较。通过。

**F02、F03：错误分类与严格类型。**旧独立探针确认：请求缺键、决定条目类型错误不会退化成意外程序错误；布尔序号、等值浮点行数等仍按协议阻断。合法阶段正向控制可用。通过。

**F04：完整调用留痕、实际重放与 helper 隔离。**独立解析全部 104 份内容对象，内容指纹正确；核对 317 次对象引用读取，规范内容哈希与落盘字节哈希均正确。全部 86 条 probe 还原 args 和 kwargs，公共函数签名 `bind()` 均成功，keyword-only 的 `current_bindings` 没有遗漏。五个关键 workflow 完整且 state 指纹正确。

独立从保存文件恢复五条绑定变化负向调用，均再次得到相同的绑定变化阻断；另一个成功调用的完整返回与首次精确相等。六次重放均未修改实参。helper 自测在主 checks 中为 0，并保留“异常类别正确但原因不符时 helper 判失败”的独立证据。通过。

## 3. 文件保护与计数说明

本轮验收开始前 14498 项快照：0 变化、0 缺失。GPT 没有修改实现、项目测试、指南或旧产物。

- TASK-009-R1 的 13943 项基线：变化 3、缺失 0，恰为授权的控制核心、测试入口、指南。
- TASK-009 原版的 13395 项基线：同样变化 3、缺失 0。这份基线保存的是原版三个文件；它们已在后续修复中获准修改，因此不能写成“0 变化”。这是回执的非阻断记账更正，不要求重写旧回执或再次修复代码。
- 13330 / 12546 / 10236 / 8547 / 6511 / 4902 / 874 项更早基线：均 0 变化、0 缺失。

本次 QA 有一次编排失误：保存文件核对先于原回归写出 `checks.json` 启动，因文件尚未生成退出 1；原回归完成后仅重跑该核对，退出 0。首次失败日志及重试命令均保留，没有将其隐藏或算作实现失败。其余已通过检查未重复运行。

收尾汇总脚本另有一次计数类型错误：把事件探针的整数调用次数当成对象读取，退出 1；修正的仅是 GPT 汇总脚本，不涉及实现或核心测试重跑，失败与修正记入 `qa_commands.json`。

## 4. 证据与下一步

GPT 证据目录：`data/reviews/task009_r2_20261011_101113`。重点文件：`regression_execution.json`、`independent_results.json`、`event_reference_results.json`、`saved_call_review.json`、`saved_retry_execution.json`、`protected_files_comparison.json`、`acceptance_summary.json`。新冻结基线为该目录的 `source_hashes_after.json`。

本次没有执行任务二至八整套回归、无边界 fuzz、真实审批、正式契约、文件持久化或真实业务管道。通过只表示这个开发态内存控制协议满足当前任务卡；它不证明来源真实，不认证人类身份，不抵御同权限重写全部内容与哈希。

下一张卡为 `docs/tasks/TASK-010_DRAFT.md`：只接通实际接收、磁盘绑定和 Gate1 开发态暂停/恢复。主理人转交本验收单及任务卡即可，无需手工检测、签 Gate 或替测试填写决定。
