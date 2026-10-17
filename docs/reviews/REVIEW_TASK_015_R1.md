# TASK-015-R1 验收记录

日期：2026-10-13；验收端：GPT。

结论：**B1 实现阻断已关闭；本卡尚未通过，返回 TASK-015-R2 仅修测试证据收尾。** 不要求再次修改宿主或事实底稿核心。TASK-015 原卡和 R1 保持待验收，暂不制定 TASK-016。

## 1. 交付身份与复验范围

实际源文件哈希与交接一致，GPT 定点运行前后保持不变：

- 宿主 `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`，版本 `TASK-015-workflow-host-1.1`。
- 本任务测试 `3f60cfff088d289358adcb24a4f85fa61787d8245399c921f46f48cc7991af26`。
- 宿主指南 `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8`，未改。
- R1 回执 `12822a413ffa613d26dc4644a1ac03f7bec2a764fec8e7e8fa086694823a31cc`。
- 六个关键冻结件、原 TASK-015 卡、R1 卡、原验收记录保持冻结哈希，详见本轮 `selected_hashes_before.json` 与 `selected_hashes_after.json`。

GPT 实际执行交付定点模式一次，新容器 `data/workflow_host_tests/task015_r1_gpt_20261013_004706`，退出 0、1/1 PASS。该结论仅表示定点模式自身执行的检查通过，不能包含被分支跳过的证据检查。GPT 未重跑 MAIN、完整八组、事实核心 21 组、TASK-002—014 历史入口或持久化故障组。

独立观察器绑定的是交付测试实际使用的模块级 `test.host`。实际 Python 代码帧观察到公开构建 4 次、真实底稿核心 4 次（3 次晚变更反例、1 次正常对照）；各次核心调用前后同一输入对象的规范指纹一致。交付记录中“进程内核心 1 次”仅捕获正常对照，不能据此称全部进程内核心只执行 1 次；子进程内部核心次数仍未观察。

## 2. B1 实现已实际复验关闭

收尾 Gate2 三份 JSON 和数据库改为实读磁盘，并与操作开始时绑定读数比较；后续再次同缓冲读取 Gate2 三份对象核验字节及规范对象。没有修改冻结核心、0005/0006 核验读数或 status 的链尾分流。

三个独立新 C06b 批次分别针对 `normalized.json`、`load_report.json`、`artifacts.json`：包装真实控制器检查，真实返回后在最后一次直接构建动作检查处追加一个 LF；原控制器仍严格返回 true，无哈希同步。三次本次公开构建均抛 `WorkflowHostBlocked`，准确指出目标文件，保存 `stage=fact_packet`、`target_exit_code=1` 和原因链。撤销 wrapper 后新进程 status 退出 1；只恢复输入原件后仍退出 1，失败事实未被删除。

独立代码帧快照证明：各反例在公开构建结束时，所有操作前已存在文件中只有故意注入的目标发生变化；恢复目标后，全部操作前文件哈希均不变。正常对照没有旧文件变化，0001—0006 在四次构建中均保持不变。

正常对照核心完整实际返回另存单份，packet 规范 JSON 严格相等、规范指纹一致、Markdown 精确等于返回字符串的 UTF-8 字节；0007 workflow 与 0006 相等，真实 Gate 批准 null、next_step_allowed=false，无 0008。五个下游守卫下 status 成功、命中全 0；外部观察到的同进程恢复前后批次文件哈希集合一致。

证据在 `data/reviews/task015_r1_gpt_20261013_004706/`：`actual_profile.json`、`core_returns/`、`normal_and_protection_checks.json`；注入、诊断及 CLI 原文在对应新定点容器。

## 3. E1（P2，验收阻断）：定点最终入口跳过必须的证据/保护收尾

R1 卡 §3.4 要求“文件引用实读核验并进入正式 failures；正确本轮保护比较、冻结哈希和开发态停止点进入正式判定”。当前入口没有满足：

1. `tests/test_fact_packet_demo_workflow.py:1140` 的 G7 仅在 all/evidence 模式执行，`:1308` 的 G8 仅在 all/protection 模式执行。late-controller 跳过两者，却在 `:1408` 打印初始化于 `:171` 的 missing=0/unregistered=0，并退出 0。这两个 0 不是已执行的审计结果。
2. 实读 `task015r1_run_01`，回执 §7 所列 `call_registry.json`、`evidence_ledger.json`、`scene_outcomes.json` 均不存在，保护扫描/比较结果也未落盘。内存确实收集了 call_registry，但未保存、未核验，不能补称为已登记且正式判定通过。
3. GPT 新容器复跑同样没有上述四项收尾产物，实际复现了成功退出却没有执行完整验收收尾。
4. 新增 G7 计数语句 `:1199` 使用 `scenes` 中不存在的 `item['batch']`。GPT只在已有四个现场上执行该条原始 AST 语句，得到 `KeyError: 'batch'`；没有因此重跑整组。简单把 late-controller 加入 G7 条件不足以修复。

这不是要求为旧辅助计数再建一轮链：阻断点是**本卡规定的最终入口未实际执行必要检查，却给出已审计为零的成功摘要，并且回执列出不存在的证据**。修复限于测试最终收尾和新回执，宿主 B1 不重开。

## 4. GPT 独立补证及其边界

GPT 独立实读原 R1 定点容器和本轮新定点容器的全部已登记 CLI/API 引用，核对存在性、哈希及原文双向对应；检查 receiver 与 checker 现场引用、workflow 停止点。详情见 `independent_evidence_audit.json`。这些补证用于确认宿主行为，不冒充执行端曾保存权威登记表或执行正式 failures 收尾。

保护结果见 `protection_result.json`：以 R1 卡指定的 121959 项基线作一次当前扫描，实扫 123102 文件，changed 恰为宿主与本任务测试、missing=0、unexpected=[]、读取错误0。该扫描是 GPT 本轮实际扫描，不追认回执所称未落盘的执行端扫描。新增 R2 的保护读数另存 `source_hashes_after.json`。

原 TASK-015 已通过的真实 writer 半写/完整后 sentinel 证据继续有效，本轮未重跑。原计数分类和旧隔离自测已独立补证的性质不重新设阻断；R2 只需让本轮定点入口的证据与判定真实、完整。

本轮 GPT 辅助审计脚本首次假设 smoke 也保存 cli_logs/api_records，实读发现 smoke 提前返回未保存，因而报 FileNotFoundError；已改为如实登记缺失，未改交付文件或重建业务批次。最初观察输出中的 `previous_0006_hash=null` 来自辅助脚本误取 `previous` 键；协议实际字段是 `previous_file_sha256`，补充核验使用正确字段，不把前者作为凭证缺陷。

## 5. 后续

交执行端 `docs/tasks/TASK-015-R2.md`。仅测试证据修正，宿主/指南/核心及既有现场冻结；一次新的定点最终入口即可，不运行完整入口、MAIN、smoke 或历史任务。验收通过后再按人类持续授权制定 TASK-016。DSH 卡片由人类操作，本次不关闭卡片。
