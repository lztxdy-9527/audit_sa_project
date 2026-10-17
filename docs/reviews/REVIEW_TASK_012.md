# TASK-012 独立验收：暂不通过，按 TASK-012-R1 修复

验收人：GPT；日期：2026-10-12（Asia/Shanghai）。项目：`D:\harness work\audit_sa_project`。

结论：**CHANGES_REQUIRED**。原入口的 8 组测试在 GPT 全新容器中通过，但独立定向检查发现两项收尾实现缺口；另有本轮测试计数与实际入口不符，需要随修复更正。暂不发 TASK-013，不执行筛查。

## 1. 已执行的独立验证

GPT 没有修改宿主、测试入口、指南或冻结上游。新增证据目录：

`D:\harness work\audit_sa_project\data\reviews\task012_20261011_162219`

实际完成：

- 编译宿主与新测试的源文本；执行现行 `tests/test_record_demo_gate2_decision.py`，全新容器 `data/workflow_host_tests/task012_gpt_20261011_162219`，退出 0，8 组 PASS、failures 为空。
- 为核对计数，测试通过 QA `observe_regression.py` 的 runpy 启动，并在 QA 内存中观察实际宿主/控制器/标准化/装载函数入口。生产源码与测试源码未改；CLI 子进程另计，不冒称被进程内观察器覆盖。
- 逐项读取执行端 final、verify 和 GPT 三个容器；组名及登记计数一致，summary/checks/counts/cli_logs/self_tests 的落盘内容相符。
- 全新真实 C02 基线实际 start、Gate1 模拟 APPROVE、prepare-gate2；另登记 9 份 QA 副本，复制数据库并显式同步路径及派生引用，用冻结纯控制器重新构造副本 0003。副本没有被记成新的接收、标准化或装载。
- 9 项独立检查：6 项符合预期，3 项违反要求。实际公开 API 调用 23 次；基线真实 receiver/checker 各 1，normalize/load 各 1，副本纯控制器构造 9 次。详见 `independent_results.json` 和逐项 `.call.json`／`.proof.json`。
- 撤销故障 wrapper 后，另起 5 个独立 CLI status 进程核对恢复；完整结果见 `recovery_cli_checks_verified.json`。

第一次 CLI 恢复核对的 GPT 断言把源快照诊断路径写成了 `source_workbook_sha256`，实际优先在 `host_manifest.json.receive.materials.snapshot.sha256` 阻断。退出码本已正确，随后修正 QA 目标路径，5 项全部匹配。首次失败记录保存在 `recovery_cli_checks.json`，未覆盖。

本次不是重跑 TASK-002—011 的全部历史测试，也不证明防断电、并发锁或同权限安全隔离。

## 2. F01：新写入的 0004 未进入决定提交的最后一次字节复测

优先级 P1；需修复宿主与新增回归。

位置：`scripts/run_demo_workflow.py:2416`、`:2443`、`:2457`。提交入口在写入 0004 之前，从原链建立 `gate2_expected["checkpoints"]`，集合只有 0001—0003。写后恢复确实核验过 0004，但最后一次 `check_dev_action` 之后调用 `_verify_gate2_tail()` 时，仍使用这份只有前三项的集合。末尾旧 checkpoint 循环也只检查前三项。

独立复现 `F01_record_checkpoint4_tail`：冻结动作检查真实返回后，仅把新场景磁盘 0004 的 `operation.phase_after` 从 APPROVED 改成 HELD；命中 1 次，发生在链重放之后、本次 API 返回之前。

- 本次 `record_simulated_gate2_decision` **返回 0／READY／DEV_GATE2_APPROVED**。
- 0004 实际字节已变；返回的 current_checkpoint_file_sha256 仍是旧值。
- 撤销 wrapper 后，正常 API 与新进程 CLI status 均退出 1，指向 `0004.json.operation.phase_after`。
- before：`51788633e54167cd84d1361a597b63ede4900e5af609c4f4741db97277342df3`。
- after：`5a9d426e16a25487cf6c99f06656d4893190f8403aa1906b6004578f4cfd76b7`。

证据：`F01_record_checkpoint4_tail.proof.json`。应在本次提交拒绝，不能等下一次 status。最终预期集合必须含旧三份的初始实读哈希和 writer 返回的本次 0004 哈希，不能在变化后重新取值当作预期。

对照：status 对同一位置的 0004 晚变更可以当次拒绝，见 `P_status_checkpoint4_tail.proof.json`；说明不是所有恢复路径都失效，缺口位于提交收尾集合。

## 3. F02：静态绑定的最终读数取在最后一次控制器调用之前

优先级 P1；两个入口均需修复。

位置：`scripts/run_demo_workflow.py:2447`、`:2452`、`:2458`，以及 status 的 `:1909`、`:1916`、`:1926`。

Gate2 record 的 `measured_after` 是 `_load_host_context()` 先前取得的值；最后一次 `check_dev_action` 后，只比较两个旧内存对象。status 虽另行调用 `_measure_bindings()`，但随后还会执行 `other_actions` 的两次控制器检查。最终 `_verify_gate2_tail()` 检查产物/数据库/checkpoint/manifest/failure，没有复测源快照及代码等静态绑定。

两项独立复现均只改新场景 `source/input.xlsx`，每项真实修改 1 次：

- `F02_record_static_binding_tail`：在 record 最后一次 SCREEN 动作检查真实返回后改变快照；本次 record **0／READY**，撤销 wrapper 后 status 1。
- `F02_status_static_binding_tail`：在已批准状态的 status 最后一次 SCREEN 动作检查真实返回后改变快照；本次 status **0／READY**，撤销 wrapper 后 status 1。

两项快照 before 均为 `0908d28af5a57e96ca113c4546394a6fe8ee9247861dc5691b516bb5c1e53e0d`，after 均为 `fbebd31da7b0051f986ae06489e70de201a58b8dd9e03fdf8dd691d3daf38945`。后续新进程 CLI 均准确指向 `host_manifest.json.receive.materials.snapshot.sha256`。

证据为对应两份 `.proof.json`。应把真实静态绑定复测放到最后一次必要控制器调用之后，以初始绑定为基准比较，变化当次给 WorkflowHostBlocked。不要用此前 `context_after` 保存的读数代替这次真实读盘。

以上三项均是 TASK-012 原卡 §3 步骤 5 的既定收尾要求，不是新增恶意篡改、无界竞态或安全认证要求。

## 4. F03：测试计数与观察值不一致，决定数混入副本和半文件

测试/留痕问题，不扩大生产接口。

`entry_count_audit.json` 与 `artifact_audit.json` 记录实际入口：

- 公开宿主 API **19**，登记 **21**。G7 两处调用前手动加 1，随后 `run_api()` 又加 1（测试约 946/995 行与 255 行），同一调用重复计算。
- 进程内控制器实际 **117**，登记 **113**。G7 的故障 wrapper 调用了先前保存的真实 `record_dev_decision`，绕过外层计数 wrapper，漏掉 4 次。具体调用方及行号完整保存在审计文件。
- `simulated_decisions=9` 实际是原始 0004 文件数。逐份解析后：**7 份原始完整记录 + 1 份副本完整记录 + 1 份故意半文件**。不能把三者合并称为 9 条已保存模拟决定。Windows 相对路径含反斜杠，使用 `copy + "/"` 前缀排除副本也不可靠。
- receiver/checker 各 **14** 与独立身份核对一致；normalize/load 进程内 **3/2** 与入口观察相同。CLI 内实际次数仍未观测，保留 null，推导值单列。

修复时用测试侧真实入口记录导出次数，包含抛错前已进入的调用；统一计数与故障 wrapper 的层次，避免手动重复/绕过。0004 原始文件数、完整原始记录、副本、半文件分别列示；完整 JSON 还不等于通过恢复协议。接收启动登记与记录做双向核对，保留少一条记录必失败的隔离自测，并补未登记记录对照。所有本轮数值来自新留痕，不硬编码成上述数值。

留痕还需补一处原卡已要求的保存：G6 的 `fault_state["full_text"]` 捕获了真实完整待写文本，但仅留在内存，未保存完整 checkpoint；旧三份的 before/after 哈希也只以 `old_checkpoints_unchanged` 布尔值落盘。代码中的取值时点与比较正确，本轮不判它为 writer 功能失效；随 F03 把完整捕获文本、两组真实哈希及异常链保存，保证回执可以离线核验。

## 5. 已确认正常的边界

- APPROVE／HOLD／REJECT 三个独立对照正常，决定总数恰为 2；旧 0001—0003 和数据库字节未变，真实批准仍 null，next_step_allowed=false。
- 原入口 C07b 合法未匹配关联非零仍可模拟 APPROVE；没有改成质量阻断。
- 真 writer 部分写入与完整写后抛错两种场景原回归均通过。GPT 另独立验证完整合法 0004 写后抛错：本次错误 2，撤销 wrapper 后新进程 status 0／APPROVED。该恢复行为符合原卡，不要求增加决定失败标记。
- 准备阶段有效 failure 与完整 0003 共存时，提交决定仍拒绝；不追加 0004。
- 三个全量容器的 8 份完整 0004（含 1 份故意路径不一致的副本）均保留前序哈希、revision=4、两条模拟决定、真实批准 null、next_step_allowed=false；另有 1 份半文件。0005 为 0。完整副本不据此宣称可合法恢复。
- 宿主 AST 没有调用 screen_sqlite／verify_rule_facts／build_fact_packet。未执行筛查、独立复算、事实底稿或 AI。

## 6. 哈希与保护

交付物实际完整 SHA-256 与本次声明相符：

- 宿主：`0e1a95dfe7c65dad9c5c54cb043fbe3dc7756632f2f3962bfab6df55f29b0e76`。
- 新测试：`84dfac91c66c8ad33b9a2441a4c72ba6b1ab022f02744f0ac1d6b816e0877c7b`。
- 指南：`2396be82cae2e19378367c16fe21faacaf9ac8c84e05b179e2fb7ecd3c992fdb`。
- 回执：`1f9229f99bd11c91ff3046fbbf4b0b0dee6d804a596cd82f6dbf08be08f45203`。

保护比对详见同一 GPT 证据目录的 `protected_files_comparison.json`：主基线 task011_r2（39831 项）仅宿主/指南 2 项授权变化；本次复验前既有文件 0 变化、0 缺失；更早基线按各自累计授权范围核对。冻结上游及两个旧测试入口保持原字节。

## 7. 后续

转交 `docs/tasks/TASK-012-R1.md` 全文，完成最小修复后用最终固定代码建立全新测试场景，提交新回执再复验。主理人此时无需手动跑测试、签 Gate 或填写判断。停在当前决定后开发状态；TASK-013 尚未开始。
