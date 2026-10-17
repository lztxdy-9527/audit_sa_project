# TASK-012-R1 执行回执（补齐决定收尾检查，纠正测试计数）

任务：关闭 TASK-012 复验的 F01（0004 未进入提交最终复测）、F02（两个 Gate2 入口的静态绑定复测早于最后一次控制器调用）、F03（测试计数重复／漏计、决定数混入副本与半文件、writer 证据未完整落盘）。
日期：2026-10-12。执行端：DeepSeek。
依据：`docs/tasks/TASK-012-R1.md`、`docs/reviews/REVIEW_TASK_012.md`。状态：完成并自检通过，**停在 Gate2 决定后的开发状态**，等独立验收；未推进 TASK-013。

---

## 1. 结论摘要

| 缺口 | 最小修复 |
| --- | --- |
| **F01 0004 未进入最终复测** | 写入 `0004` 后立即把收尾预期集合补成**四份**：`0001`—`0003` 用本次**初始同缓冲读取**得到的字节哈希，`0004` 用**本次真实 writer 返回的文件字节哈希**（不在收尾重读 0004 后取新值当预期）。因此“真实 SCREEN 动作检查返回后有人改磁盘 `0004`”会在**本次调用**内被发现并返回 `WorkflowHostBlocked`（指向 `workflow/checkpoints/0004.json`，含预期与实际），而不是等到下一次 `status` |
| **F02 静态绑定复测时点** | 新增 `_recheck_static_bindings()`：在**最后一次必要控制器动作检查之后**，从磁盘**重新读取实际字节**实测静态绑定，与本次操作开始的读数逐项比较（差异列出字段名与 `source/input.xlsx` 预期／实际），并同时要求与 workflow 创建绑定一致。接入 `record_simulated_gate2_decision` 与 `inspect_dev_batch`（含 Gate2 恢复分支，往前阶段入口也一并覆盖）；既有产物／数据库／清单／checkpoint／failure 最终核验**未移动、未省掉** |
| **F03 计数与留痕** | 建立**统一真实入口观察层**：公开宿主 API（含经 helper 进入的 `inspect_dev_batch`、直接调用、抛错前已进入）只计一次，删除 `run_api` 与 G6/G7/G8 的手动重复累加；宿主内部控制器重放与测试造样**分列**；故障 wrapper 一律调用观察包装器（不再绕过计数）。`0004` 改为**分类**：原始文件／可解析原始记录／副本记录／半文件（副本用 `Path` 层级识别，不拼字符串前缀），且“合法决定已保存”以**逐份真实恢复核验**为准（完整 JSON 不是充分条件）。接收启动与调用记录**双向**核对并报告 missing／unregistered；保留“删一条记录必失败”自测，新增“内存中未登记记录必须被识别”对照。G6 完整待写文本以**原 UTF-8 字节**另存并核对文件字节数与 SHA-256，旧 `0001`—`0003` 调用前后**两组真实哈希**、阶段顺序与 sentinel 异常链写入 `writer_evidence.json` |
| **版本** | 实现版本升 `TASK-012-workflow-host-1.1`；**持久化协议版本保持** `TASK-012-host-manifest-1.0`／`TASK-012-checkpoint-1.0`／`TASK-012-gate2-artifacts-1.0`／`TASK-012-gate2-failure-1.0`（字段结构未变）；材料中随 `HOST_VERSION` 生成的 `prepare_version` 与最终代码一致（用最终固定代码新建批次，未迁移旧批次） |

## 2. 交付文件完整 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `scripts\run_demo_workflow.py`（改，实现版本 1.1） | `dc6e53db794322082c14c37ff3da09118f90f01361c0d517aa78e3562bd360a6` |
| `tests\test_record_demo_gate2_decision.py`（改） | `d5a18bbb211716ae60f4d4da605df4108743bbeb5d8551b602a7e064efc7211b` |
| `docs\WORKFLOW_HOST_GUIDE.md`（改） | `513e6eda28fa2dc993982d92ae640deabf11451407a7058074fc90657f9d3c4b` |
| `docs\EXEC_REPORT_012_R1.md`（新增，本文件） | 见交付回报 |

## 3. 真实命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"          # 0
& $py -B -c "src = open(r'...\tests\test_record_demo_gate2_decision.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_record_demo_gate2_decision.py' --out-dir '...\data\workflow_host_tests\task012r1_final_01'   # 0
```

**结果：退出 0，10 组全 PASS，`failures=[]`**（`G1_MAIN_FULL_FLOW`、`G2_STOP_STATES_AND_MISSING_LINK`、`G3_REJECTION_SURFACE`、`G4_DECISION_LOCK_AND_LEGACY`、`G5_CHECKPOINT_TAMPERING`、`G6_WRITER_AND_POST_WRITE_ERROR`、`G7_BOUNDED_TAIL_CHANGES`、`G8_GUARDS_AND_COUNTS`、**`G9_R1_FINAL_TAIL_PROBES`（本卡新增）**、**`G10_COUNT_AUDIT`（本卡新增，在全部探针之后运行）**）。原 8 组断言与失败案例全部保留，未放宽原因匹配。

## 4. 三条完整产物路径

| 类型 | 路径 | 规模 |
| --- | --- | --- |
| 测试容器 | `data\workflow_host_tests\task012r1_final_01` | 257 文件（含 `writer_evidence.json`、`writer_full_expected_0004.json`、`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`cli_logs/`） |
| 批次父目录 | `data\batches\task012r1_final_01` | 318 文件 / 142 目录；**12 份 `0004`、0 份 `0005`**、2 份 `gate2/failure.json` |
| 外置数据库目录 | `data\sqlite_tests\workflow_gate2\task012r1_final_01` | 13 文件 / 14 目录 |

## 5. F01／F02 定向探针（本轮真实证据）

| 探针 | 命中 | 类别 | 本次结果（截断展示，完整消息在容器 `checks.json`） | 真正 before → after | 撤销 wrapper 后新进程 status |
| --- | --- | --- | --- | --- | --- |
| **F01** `G9_F01_TAIL_0004_EXPECTED_SET`（record 最后一次 SCREEN 动作检查返回后改 `0004.operation.phase_after`） | 1 | `WorkflowHostBlocked` | `字段 workflow/checkpoints/0004.json 不可用：收尾复测发现 checkpoint 字节变化：期望 'c5dc4f56…'，实际 '198c86f6…'` | `c5dc4f56…` → `198c86f6…` | **exit 1**，`0004.json.operation.phase_after 不可用：操作摘要的 phase 必须与实际状态一致` |
| **F02 record** `G9_F02_RECORD_STATIC_BINDING_TAIL`（record 最后一次 SCREEN 返回后改 `source/input.xlsx`） | 1 | `WorkflowHostBlocked` | `Gate2 决定提交收尾（最后一次控制器动作检查之后）重新从磁盘实测的静态绑定与本次操作开始时不一致（差异字段 ['input_sha256','receive_materials']）：source/input.xlsx 预期（操作开始）'0908d28a…'，实际 'e6bd017b…'` | `0908d28a…` → `e6bd017b…` | **exit 1**，`host_manifest.json.receive.materials.snapshot.sha256 不可用：必须与本批次实际字节一致` |
| **F02 status** `G9_F02_STATUS_STATIC_BINDING_TAIL`（已决定 Gate2 状态的 status 在**最后一次**动作检查返回后改快照） | 1 | `WorkflowHostBlocked` | `Gate2 恢复收尾（最后一次动作检查之后）重新从磁盘实测的静态绑定与本次操作开始时不一致（差异字段 ['input_sha256','receive_materials']）…` | `0908d28a…` → `e6bd017b…` | **exit 1**，同一 snapshot 语义原因 |

正向对照（未变化不得误拒）：`DEV_GATE2_APPROVED`、`DEV_GATE2_APPROVED`(MAIN)、`DEV_GATE2_HELD`、`DEV_GATE2_REJECTED` 四个批次 `status` 全部 **exit 0**；两个 F02 探针在**恢复快照原位**后 `status` 重新 **exit 0**。两处探针均记录注入时点（第几次 SCREEN 返回）、命中 1、真实 before／after 与后续 CLI 日志，**不以内部调用总数当业务协议**。

## 6. F03 计数与留痕（本轮真实留痕导出，未照抄任何旧值）

| 项目 | 数值 | 来源 |
| --- | --- | --- |
| CLI 子进程 | `start 17`／`status 42`／`record 17`／`prepare-gate2 12`／`record-simulated-gate2-decision 14` | `run_cli` 逐次记录（参数、退出码、stdout／stderr 落盘） |
| **公开宿主 API（进程内）** | **31** | 统一入口观察层的 `api_events`（含 helper 进入的 `inspect_dev_batch`、直接调用、抛错前已进入）；与 `counts.host_api_calls` **一致** |
| 宿主内部控制器重放（进程内） | **245** | `controller_events`（底层真实入口观察）；**CLI 内未观测 = `null`** |
| 测试造样调用 | 0（本入口不再直接调用测试侧控制器模块） | `controller_sample_events` |
| 真实接收／checker | **17 / 17** | 每条 `receive_invocation.json`（副本排除）／各接收身份 `checker_invocation.started`（运行失败样本也计）；`missing_records=[]`、`unregistered_records=[]` |
| 进程内标准化／装载 | 3 / 2（CLI 内未观测 `null`，按成功 CLI 推导 11 / 11 单列） | 测试侧包装真实上游（故障前真实进入也计） |
| 副本／故障注入／负向拒绝 | 1 / 18 / 26 | 副本登记来源后排除，故障注入与拒绝来自实际探针 |
| **0004 分类** | 原始文件 **12**＝可解析原始记录 **10** ＋ 副本记录 **1** ＋ 半文件 **1**；另有 **1** 份探针故意保留的非法现场单列 | `decision_files_audit`（副本用 `Path` 层级识别） |
| **经恢复核验的合法决定** | **9** | 逐份真实恢复核验（`APPROVE`／`HOLD`／`REJECT` 均计入；完整 JSON 不作为充分条件） |
| **真实批准** | **0** | 全部检查点 `gate1_approval`／`gate2_approval` 恒 `null` |

隔离自测（均通过且不污染 `failures`）：匹配器自测（类别正确但原因不符必须判失败）；计数自测（内存中去掉一条记录必须判不一致；**新增**内存中加入未登记记录必须被识别）。

**G6 writer 证据**（`writer_evidence.json` + `writer_full_expected_0004.json`）：完整待写文本以原 UTF-8 字节另存，文件字节数与 SHA-256 与捕获值一致且可解析为完整 checkpoint；`opens/writes/raises` 各 1、部分字节 < 完整字节、`__cause__` 为 sentinel `OSError`、旧 `0001`—`0003` 调用前后两组哈希**逐份落盘**且相同（不再只留布尔值）。

## 7. 保护结果

- 主基线 `data/reviews/task012_20261011_162219/source_hashes_after.json`（46623 项）：**恰为宿主／测试／指南 3 项授权变化，缺失 0**。
- 更早基线按起点累计授权：`task011_r2`（39831）**仅宿主＋指南 2 项**（该基线时 TASK-012 测试尚不存在）；`task011_r1`（34813）／`task011`（28489）／`task010`（16340）各为宿主＋指南＋当时测试入口 3 项累计。
- `task009_r2`（14691）与 13330／12546／10236／8547／6511／4902／874 全部 **0 变化、0 缺失**；测试内建受保护文件（13 个）前后哈希一致。
- 冻结上游与旧入口逐项未变：控制器 `a6b7b8e1`、接收器 `52195620`、checker `a7e5eb67`、标准化 `a2bae49e`、装载器 `1abfad89`、schema `7e0c6463`、筛查 `1b123766`、复算 `8fe75bfe`、底稿 `f4998d92`、SPEC `5df632ed`、契约 `af405cb6`、`tests/test_run_demo_workflow.py` `852bf336`、`tests/test_prepare_demo_gate2.py` `11d4fe57`。
- 无临时脚本与 `__pycache__` 残留，四个文件均 UTF-8 无 BOM；未安装依赖、未初始化 Git、未新增生产模块／接口／命令（CLI 仍恰 5 个子命令）。

## 8. 失败尝试

1. **审计块位置**：首版审计放在 G8（G9 之前），导致 G9 新增的 3 次真实启动漏计（`receiver_starts_host` 17 vs 记录 14）→ 把计数审计整体移到**全部探针之后**单列 `G10_COUNT_AUDIT`，本轮由此得到一一对应的 17/17。
2. **故意保留的篡改现场**：F01 探针按要求保留被改的 `0004`，首版审计把它当成“无法恢复的非法记录”判失败 → 增加 `deliberate_tamper_batches` 登记，单列“探针故意保留的非法现场”，不计作审计问题。
3. **G7 故障 wrapper 绕过计数**：原先调用测试侧保存的原始 `record_dev_decision`，经包装器替换后宿主内部调用未被计入 → 改为调用**观察包装器**（`observed_record_decision`）并在探针结束后恢复观察包装器。
4. **重复累加**：`run_api` 自行 +1 与 G7 手动 +1 造成同一调用计两次 → 计数统一由观察层按真实入口事件导出，删除全部手动累加。
5. **锚点冲突**：`"bindings_sha256": canonical_sha256(measured)` 在宿主中出现两处 → 改用含上下文的三行精确锚点（补丁脚本在断言失败时不写盘，文件未被中途改坏）。

## 9. 未执行（不写通过）

未实现或提交 Gate2 决定之外的任何动作：未执行筛查／R01—R04、独立复算、事实底稿、AI 建议；未建立正式契约、未签真实 Gate、未保存或预填人类判断；未新增 UI／真实 ERP／压测／并发锁／断电试验；未重跑 TASK-002—011 整套历史入口（本卡要求的最小回归由新入口覆盖）；未推进 TASK-013。

停止状态：**停在 Gate2 决定后的开发状态**（`DEV_GATE2_PENDING`／`APPROVED`／`HELD`／`REJECTED` 依批次），模拟 `APPROVE` **不是**真实 Gate2 放行——宿主只声明控制器允许筛查，**没有执行筛查的命令**。
