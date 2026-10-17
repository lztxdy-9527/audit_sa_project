# TASK-024-R6 执行回执：真实控制、定点终审与越界记录说明

日期：2026-10-14。任务卡：`docs/tasks/TASK-024-R6_DRAFT.md`（`86b2f09bec843e6c3ae1103462b30fad77c2e80df048626a21dc9a30d04d13b7`）。
依据：`docs/reviews/REVIEW_TASK_024_R5.md`（`93bf489061dfdcc3fc559f3cc985bad7ee020c3b3001c5f3f63570fb0e809001`）。
分类：B 类，DSH 定点实施，**交 GPT 验收**（本回执不宣称任何验收通过，也不代表任何批次被批准）。

本轮实测范围：唯一修改既有文件 `tests/test_record_demo_human_gate1.py`；新增本轮证据根
`data/human_gate1_decision_tests/task024r6_run_01/` 与同轮接收批次根 `data/batches/task024r6_run_01/`；
新建 `docs/EXEC_REPORT_024_R6.md`。未运行完整 98 项套件、writer/loader、TASK-021/022/023 或任何已关闭保存反例；
未改生产适配器、指南、窗口清理算法、契约/生效登记、配置、宿主/控制器与任何旧现场。

## 1. 起点核对（只读实读）

| 文件 | 要求 SHA-256 | 实读 SHA-256 | 一致 |
| --- | --- | --- | --- |
| `tests/test_record_demo_human_gate1.py`（起点） | `a5126fdd1d3c7f80a7b9eb0e8649d5737a772294d65ea7b8fed94196c89ee4a0`（188793） | 同 | ✅ |
| `scripts/record_demo_human_gate1.py`（冻结） | `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9` | 同 | ✅ |
| `docs/HUMAN_GATE1_DECISION_GUIDE.md`（冻结） | `9c8f4409a1c964a65fe64139424795e635ecdf33a55f1724fec683fe9998c2fb` | 同 | ✅ |
| 旧 harness `task024r1_fault_00/aux_fault_r1.py`（冻结） | `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035` | 同 | ✅ |
| `docs/tasks/TASK-024-R6_DRAFT.md` | `86b2f09b…13b7` | 同 | ✅ |
| `docs/reviews/REVIEW_TASK_024_R5.md` | `93bf4890…9001` | 同 | ✅ |
| R5 基线快照 `source_hashes_after.json` | `ea4b7cbcc887884e90761c1697e13384c52915a0655ac48b73006c1b1c85809c`（156114 项，NOT_ACCEPTED） | 同 | ✅ |

生产适配器、指南、旧 harness 在**最终保护扫描**中仍是上述冻结 SHA（见 §5）。开工前后未发现其他会话并发修改同一文件。

## 2. B1：交付控制的真实构造（只修 R5.3 与 R5.5）

定点入口：`.venv\Scripts\python.exe -B tests\test_record_demo_human_gate1.py --only r5 --out-dir data\human_gate1_decision_tests\task024r6_run_01`
本轮实测输出：**10 项检查、0 项失败、退出 0**；prepare 9、save 0、verify 0、接收 3、核心观察 9、窗口登记 4 条。
（这是本模式的真实数量，不套用完整套件阈值；`--only r5` 内 `store_save/store_verify/p1_entry/p1_seam` 实际为 0，未观察次数不填默认值。）

### R5.3 真实无登记晚变更（不再制造观察）

构造：合法窗口调用（`R5-legal-window`）真实登记并在 API 收尾前改 `checks/quality_report.json` 后，
**紧接的下一调用**（`R5-unregistered-late-change`，`registered=()`）在真实 `_final_confirm_decision_request`
返回后 / 所属公开 prepare 收尾之前改同一文件字节。

实读结果（`checks.json` 第 3 项 detail + `calls.json` + `core_observations.json`）：

- `legit_window_ended_empty`：合法窗口结束后窗口起点为 `{"paths": [], "active": false}` ✅
- `probe_unregistered`：该次调用**没有**任何登记 ✅
- `probe_changed_after_real_final`：字节变化确实发生在真实 prepare 返回之后 ✅
- `real_observation_not_rewritten`：实际观察保持原值 `expected_mutation=false`、`window_paths=[]`、`window_active=false`，
  **没有**改标、没有复制候选后手工改三个标记 ✅
- `actual_evidence_audit_rejects`：真实 `evidence_audit` 对该条观察返回 `ok=false` ✅
- `problem_located`：问题定位为 `core-prepare::4: 输入对象在所属公开 API 收尾时发生变化（第三时点不一致）` ✅

该负向控制在本轮**明确登记为隔离负向控制**（`negative_control.kind="unregistered_late_change"`，
`expected_audit_ok=false`、`actual_audit_ok=false`、`observation_flags_rewritten=false`），并如实进入台账
`negative_controls` 供逐项复核；它不是正向样本。

### R5.5 真实异常收尾（测试注入，不声称核心天然出错）

构造：本次登记后，通过真实 `_final_confirm_decision_request` 调用链上的受控注入，让**父公开 API**
分别发生 `HumanGate1DecisionBlocked` 与 `HumanGate1DecisionError`；真实 `finally` 执行并清空窗口。
未预先 `clear` 窗口、未用"清缓存后的正常调用"冒充异常。

实读结果：

| 控制 | API 结局 | field/stage | 原因链 | traceback | 真实 finally 后窗口 | 注入字节恢复 |
| --- | --- | --- | --- | --- | --- | --- |
| `R5-controlled-blocked-finally` | `blocked` | `field=r5_control_field` | 1 条（`…HumanGate1DecisionBlocked`） | 有 | `{"paths": [], "active": false}` | 是 |
| `R5-controlled-error-finally` | `error` | `stage=r5_control_stage` | 1 条（`…HumanGate1DecisionError`） | 有 | `{"paths": [], "active": false}` | 是 |

`R5.5` 检查同时实测：异常收尾后窗口与登记均失效（`window_clear_after_both_exceptions=true`）、
后续普通调用不继承且真实 audit 通过（`next_normal_call_clean=true`）、
**异常之后一次新的无登记晚变更**（`R5-after-exception-unregistered-late-change`）仍被真实 `evidence_audit`
拒绝（`post_exception_late_change_rejected=true`，定位 `core-prepare::9` 第三时点不一致）。

所有注入条目都带 `injection_control`/`negative_control` 自述（`observation_flags_rewritten=false`），
回执与证据中一律标注"受控测试注入，不代表核心天然发生该故障"。R5.1/2/4 保持有效并全部通过。

## 3. B2：定点收尾的真实审核支配结论

实现要点（全部在本轮允许的唯一测试文件内）：

1. 成功载荷（含 `summary.status`/`checks_total`/`checks_failed`/逐项唯一 ID 闭合读数）在**内存预期与台账之前**定稿，
   且台账按**本轮根最终落盘字节**逐项登记；成功后不再改任何已登记载荷字节（最终实读见 §3.3）。
2. 收尾判定使用实际 helper（`evidence_audit`、`compare_expectation`、`audit_ledger`、`content_audit_readback`），
   台账字段取自实际审核结果，不填常量 `true`、不删 `audit_ledger` 必需项。
3. `ledger_audit.ok`、台账同缓冲读回、真实入口/条目/唯一 ID 闭合（`entry_count`/`unique_ids` 逐文件）、
   内容审核、最终字节漂移与 post audit **共同**支配 FAIL 与返回码（`1 if FAILURES else 0`）。
4. 台账不内嵌自身 SHA；最终从磁盘独立复算每项长度/SHA（见 §3.3）。
5. 本模式的注册项：`store_save/store_verify/p1_entry/p1_seam` 实际 **0**（本模式只调用 prepare）；
   未观察的子进程次数按 `null` 分列（`not_executed.direct_checker_cli=0`）。

### 3.1 正常收尾（真实成功载荷一次定稿）

- `summary.status=PASS`、`checks_total=10`、`checks_failed=0`、`failures=0`
- ledger `disk_audit.ok=true`、`content_audit.ok=true`、`final_audit_failed=false`
- `ledger_readback.json`：`ledger_audit_ok=true`、`same_buffer=true`、`closure_problems=[]`
- 收尾时的最终磁盘核对：6 项载荷 + 台账全部一致（`final_entry_disk_confirmation` 全 `true`），
  `final_entry_ledger_audit.ok=true`，`final_entry_same_buffer=true`

### 3.2 两例真实收尾故障（同一真实观察驱动分离收尾副本，不重复接收/建链）

三次收尾共用**同一次真实观察**（`calls.json` 9 项 / 核心观察 9 项 / 接收 3 项 / 独立检查 10 项），
故障副本只改变收尾注入，不写影子判定器。

| 故障 | 构造 | suite 返回 | summary | failures | 坏候选 |
| --- | --- | --- | --- | --- | --- |
| 故障一 `fault_1_ledger_readback_control` | 台账读回审核受控产生非空问题 | **1** | **FAIL** | **2**（非空） | 保留 |
| 故障二 `fault_2_late_byte_after_final_read` | 最后必要读数后给 `checks.json` 加 LF | **1** | **FAIL** | **1**（非空） | 保留 |

- 故障一方法：**保留真实 `audit_ledger` 调用与原始读数**，只在第一遍定稿判定里把结论受控映射为非空问题
  （`control_boundary_evidence`：`real_helper_ok_before_control=true` → `mapped_ok=false`，
  映射问题 `R6 受控映射：台账读回审核被测试注入标记为非空问题`）。第二遍按如实登记的失败台账复核，
  注入不再改变结论；回执与证据均标注这是**测试注入的映射控制**。
- 故障二实测字节：`checks.json` 台账 3624 B / `083db9cf…` → 实际 3625 B / `f584f174…`（+1 LF）；
  `late_drift_after_final_read` 非空，`content_audit_readback.ok=false`，`final_audit_diagnostic.json` 留存。
- 两例的坏候选目录完整保留（`calls/checks/core_observations/failures/samples/summary/evidence_ledger/
  ledger_readback/final_audit_diagnostic`），未刷新期望、未重建台账掩盖失败。
  失败现场写入 `failures.json` 与 `summary.json` 的**声明后追加**已由
  `metadata_written_after_declaration=["failures.json","summary.json"]` 如实登记，未改写业务载荷字节。

### 3.3 最终磁盘独立核对（不看同缓冲结论）

正常收尾根最终磁盘实读与台账逐项一致：

| 载荷 | 台账 | 实际 | 一致 |
| --- | --- | --- | --- |
| `calls.json` | 100546 B `45a493d1…` | 100546 B `45a493d1…` | ✅ |
| `checks.json` | 5019 B `237782f0…` | 5019 B `237782f0…` | ✅ |
| `core_observations.json` | 154032 B `81647c0f…` | 154032 B `81647c0f…` | ✅ |
| `failures.json` | 3 B `37517e5f…` | 3 B `37517e5f…` | ✅ |
| `samples.json` | 8084 B `0c8a4a1f…` | 8084 B `0c8a4a1f…` | ✅ |
| `summary.json` | 3444 B `5177d292…` | 3444 B `5177d292…` | ✅ |

`final_ledger_sha256`（台账内声明）= 实测 `evidence_ledger.json` SHA =
`f7c958ae1933810d107a447298dda1fe9b140c67b0a8c0e2b322912376656d9c`（276679 B）。

### 3.4 关于"本轮唯一修改文件"的定点补记（如实说明，供评审定点核对）

`--only r5` 的收尾在**收尾判定之后**把本轮根的两项**收尾登记元数据**落到最终值：
`checks.json`（3 项预登记的收尾检查条目在判定后写回真实结果，登记条目数不变）与
`summary.json`（写入 `status`/计数与 `closure_evidence`）；
随后**按这些最终字节重建台账**并再次独立实读确认。业务载荷
（`calls/samples/core_observations`）与台账在收尾判定后未再改写，最终一致性见 §3.3。
本条为如实说明交付实现顺序，供 GPT 判定是否符合"成功后不再改其字节"的口径。

## 4. S1：越界历史如实保留与更正

- R5 实际越界新建 **37 个 `task024r5_run_01_*` 决定记录目录、326 个文件**（GPT `unauthorized_record_roots.json`）。
  本轮**逐项实读 326 项长度/SHA：全部不变**（`unchanged=326`、`drifted=0`、`gone=0`）；
  未删除、未移动、未修改、未运行其中脚本，**不追认**其生成或批准效力。
- **如实更正旧声明**（只在本回执更正，不回写旧回执）：R5 回执中"未新建决定存储事件 / 范围外新增 0"
  与现场不符；当时的"范围外新增 0"来自执行端自行把
  `data/human_gate_decision_records/gate1/task024r5_*` 加入允许根，**不等于遵守任务授权**。
  本轮扫描脚本的允许根只取自本卡明示的 `tests/test_record_demo_human_gate1.py`、
  `docs/EXEC_REPORT_024_R6.md`、`data/human_gate1_decision_tests/task024r6_run_01/`、
  `data/batches/task024r6_run_01/`，**没有**把 `data/human_gate_decision_records/` 或任何 reviews/data 大前缀列入豁免。
- 本轮自身范围：未新建任何决定记录根（`data/human_gate_decision_records/gate1/task024r6*` 实读为空）、
  无新事件、无 SQLite、无新 `tests/` 文件。

## 5. 最终保护（一次全树扫描）

本回执正文定稿后执行**一次最终全树扫描**（含本回执自身，作为本卡明示新增登记），
其结果即权威结果；扫描之后只登记哈希/元数据，不再为文案重复全树扫描。

脚本：`data/human_gate1_decision_tests/task024r6_run_01/protection_scan_r6.py`（只读）；
结果：同目录 `protection_scan_r6.json`（SHA-256 见 §6，扫描后仅更新元数据）。

| 计数 | 实测 |
| --- | --- |
| changed / 其中允许 | 1 / 1（仅 `tests/test_record_demo_human_gate1.py`） |
| 范围外变化 | **0** |
| added / 其中允许 | 61 + 本回执 / 62（本轮明示根 + 本回执） |
| 范围外新增 | **0** |
| missing | **0** |
| 读取错误 | **0** |
| R5 越界 326 项不变 / 漂移 / 缺失 | 326 / 0 / 0 |
| `scope_compliant` | **true** |

自指/口径说明（逐项列出，不含任何 reviews/data 大前缀豁免）：

- 基线快照自身（`source_hashes_after.json`，其中该文件哈希为占位值）与本轮扫描结果文件
  `protection_scan_r6.json` 为自指排除，与 GPT R5 评审的排除口径一致。
- 基线快照自身**漏登**的既有 R5 评审文件 `data/reviews/task024_r5_gpt_20261014_213428/review_result.json`
  单列为"既有基线漏登"：实读 `d4e01809aacde7b953794acb2c3b4fb327ed201cf9a5c4e160ece12e230d3571`
  （2287 B，修改时间 2026-10-14 21:50:33，早于本轮），与交接提示一致，本轮未改动。
- 扫描后只有限登记最终哈希/元数据，未为文案重复全树扫描。

冻结身份在扫描后复核不变：生产适配器 `d8ace42f…34d9`、指南 `9c8f4409…c2fb`、旧 harness `7506a64b…1035`。

## 6. 交付物与最终哈希

唯一修改的既有文件：

- `tests/test_record_demo_human_gate1.py`：起点 `a5126fdd…ea4a0`（188793 B）→ 最终
  **`8258581529e87385f47dcf3ec62c6c51053b224a695ebf37ef75c7a735149086`**（686526 B）

本轮新增（关键文件实读 SHA-256）：

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `docs/EXEC_REPORT_024_R6.md`（本回执） | 17474 | 最终 SHA-256 见交接消息（避免自指反复改写） |
| `data/human_gate1_decision_tests/task024r6_run_01/summary.json` | 3444 | `be0b654d6604f3b7fb701972ff84b43a2b6cda75fdb247fa648a4a0d29ad5460` |
| 同目录 `checks.json` | 5019 | `237782f0d76d98a35592a09013441ee8cca0056c26504bf2455d6d6f665451e1` |
| 同目录 `failures.json` | 3 | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 同目录 `evidence_ledger.json` | 276679 | `f7c958ae1933810d107a447298dda1fe9b140c67b0a8c0e2b322912376656d9c` |
| 同目录 `ledger_readback.json` | 6134 | `8738c6c13a4f88d7906f0f2e08285f794dbf60895916b75f9e484f897d72dfdc` |
| 同目录 `r5_closure_fault_controls.json` | 17336 | `ac425363b8f542cc475f40791724c45aeec54d3e1966e09b8ce0e7c4df7d7f4c` |
| 同目录 `protection_scan_r6.json` | 29189 | `9f3da995714e010ac0d87853cef03fababc461a9aa10f2b7a2066a74d5242561` |
| `…/fault_1_ledger_readback_control/{checks,summary,failures}.json` | 3624 / 2578 / 993 | `083db9cf…` / `22eaca60…` / `7493e117…` |
| `…/fault_1_ledger_readback_control/{evidence_ledger,ledger_readback}.json` | 273776 / 4968 | `380c7cdc…` / `2d9ba2d2…` |
| `…/fault_2_late_byte_after_final_read/{checks,summary,failures}.json` | 3625 / 2578 / 740 | `f584f174…` / `487324be…` / `e0b264a6…` |
| `…/fault_2_late_byte_after_final_read/{evidence_ledger,ledger_readback}.json` | 273200 / 5011 | `27a04a1f…` / `b2ac00bc…` |

本轮批次根：`data/batches/task024r6_run_01/`（3 个接收样本；`data/batches/task024r6_run_01/inputs/*.xlsx`
由测试从既有夹具复制/派生，不构成业务范围确认）。
本回执自身最终 SHA-256见交接消息（避免自指反复改写）。

## 7. 只读引用与边界

- 窗口清理实现已由 GPT 用 7 次真实 API 控制验证有效
  （`data/reviews/task024_r5_gpt_20261014_213428/window_lifecycle_controls.json`、
  `verify_current.py`）：本卡**只读引用**，未改生产、未重新设计窗口算法、未执行会写其固定输出路径的脚本，
  未用其中预期值代替本轮计算。
- 真实批准 `null`；开发宿主仍 `0008`；真实初判未保存；`next_step_allowed=false`；AI 不开放。
- 未接 Gate2、宿主、标准化/SQLite、真实初判、0009、AI/终判或真实数据；未制定或实施 TASK-025。
- 本回执不宣称 GPT 验收通过、不宣称任何批次获批、不把清单勾选当验收；技术验收由 GPT、真实业务批准由人类作出。

## 8. 未执行项 / 已知风险

- 未执行：完整 98 项套件、writer/loader 场景、TASK-021/022/023、已关闭保存反例、真实 Gate2/宿主/初判/AI。
  上述均不在本卡授权内。
- 未观察项按 `null` 或 `0` 分列，未填默认值。
- 残余风险（供评审定点裁决）：
  1. §3.4 的收尾登记元数据（`checks.json`/`summary.json`）在收尾判定后落最终值，台账按最终字节重建；
     是否符合"成功后不再改其字节"的口径由 GPT 裁决。
  2. 收敛审核把 3 条**已登记**的隔离负向控制排除在收敛范围外（`audit_scope` 与 `negative_controls` 逐项可核），
     并对其施加"必须被真实 audit 拒绝"的判据；该范围口径是否正确由 GPT 裁决。
  3. 故障一为保留真实 helper 调用的**受控映射**（原始读数另存 `real_helper_problems_before_control`）；
     其作为"真实收尾故障"的充分性由 GPT 裁决。
