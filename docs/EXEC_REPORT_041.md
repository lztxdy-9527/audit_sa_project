# TASK-041 执行回执：TASK-040-R1 已接受实现的硬化（S8 双构造 / verify 末段 / schema / 死代码）

日期：2026-10-17。交付状态：硬化实现、测试、指南与证据定稿，**交 Architect 独立验收**；本回执不宣布验收通过，
不改看板、不推进下一业务步骤。真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-041_DRAFT.md`（`d90ecdd8…9213f6a8`）、`docs/reviews/REVIEW_TASK_040_R1.md`、
已接受 `data/reviews/task040_dsh_r1_20261017_01/review_result.json`（`c092f4d0…c4f1b7c5`）。
接受基线：`data/reviews/task040_dsh_r1_20261017_01/source_hashes_after.json`（171449 项 / `26a0adf7…`，本卡不替换）。
`task040_run_05`、`task040_dev_01`、`task040_r1_run_01/02`、两轮架构端评审根与 `docs/reviews/REVIEW_TASK_040*.md` 全部原样冻结。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task041_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 四件交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 适配器 | `scripts/runtime_gate1.py` | 404971 B | `f5c7c3967abc8257f1eff5c55487f6ff88c68d0879161e715dc43c95e0fad4b7` |
| 测试 | `tests/test_runtime_initial_judgment_recording.py` | 69930 B | `ac9c95730065e46c0da0139ac1f37cc169d13ffe5815618e03c518c114edc75a` |
| 指南 | `docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` | 7202 B | `8cef774549ffc4d15ce92adc4da90e35c7e57421e1a1f744ca9b34c9f6de7bb7` |
| 本回执 | `docs/EXEC_REPORT_041.md` | 见 delivery.json | 见 delivery.json |

起点 R1 身份未变（适配器 399395/f9ec…、测试 62351/bdee…、指南 7147/f258…、回执 12848/e4bb…）。

## 2. H1—H5 修正点与确切代码位置

**H1 S8 双构造（首要）** — 取消 `success = deepcopy(expected_result)`。
- 候选：`_build_success_040`（L5779）只用本次真实 `store.save` 返回与真实 H1/Hc history 返回及 writer 缓冲。
- 预期：`_rebuild_storage_verification_040`（L5806）用目标叶六文件字节 + manifest 重建 `storage_verification`
  十一键；`_rebuild_success_040`（L5814）用该重建、E1/H1 独立重建历史、writer 缓冲描述与 S3/叶内 identity
  重建十二键；描述由 `_descriptor_from_capture_040`（L5797）从同缓冲重建。
- save 双构造与审核：L6213–6243；verify：L6627–6646。完整 canonical 比较（`_audit_initial_success_040` L5648 不变）
  首差 → `Blocked result.<差异路径>`；内部审核非空 → `Error audit.result`（reasons 保留）。
- **公共路径可达性**：`task041_run_05_h1_candidate_control` 包装候选构造器（公共 save 入口，不直调审核）
  改 `record_relative` → `Blocked result.record_relative`，失败前 `store.save=1 / store.verify=1 / core=2`
  （真实业务调用已执行，封装 started+context+receipt+failure，锁保留）。
- 硬化新增内部调用 `_rebuild_success_040` 单列计数（`hardening.rebuild_success`，save/verify 各 1），不并入业务公式。

**H2 verify 末段完备** — verify 的末次确认传入 `target_leaf/target_captures`（L6647–6649），
复确认目标叶六件集合与 failure；确认路径只读（未新增写）。

**H3 S5 schema 复测** — `_pre_store_confirm_040`（L5853–5857）沿 `_capture_static_028` 口径复测
`sql/demo_schema.sql`、`scripts/normalize_demo_data.py`、`scripts/store_demo_sqlite.py`。
实测 `task041_run_05_h3_schema_drift`：started 写入后改 schema → `Blocked sql/demo_schema.sql`，
`store.save=0 / core=0`，现场 started+failure、锁保留；schema 事后精确恢复。

**H4 死代码与静默路径** — 删除无调用点的 `_initial_snapshot_objects_040`、`_initial_target_name_040`；
`_confirm_initial_history_040`（L5963）对"非本次目标缺缓冲"显式 `Blocked history.entries[i]`（L5977）；
坏 envelope failure 的缺键/未知键精确到 `failure.<子键>`（`_validate_initial_failure_040` L6298）。
实测：缺 `reason` → `Blocked failure.reason`；未知键 → `Blocked failure.zzz_unknown`；
非目标缺缓冲 → `Blocked history.entries[1]`。

**H5 遗留** — store `Blocked` 的 `reasons` 原样复制（L6130，行为等价记录）；旧适配器 290568 B 正文本地无副本，
继续以"旧文件中未登记变化 0 + 旧 17 签名与既有指南一致"承担，不伪造基线、不改旧证据。

## 3. 正常链、调用图与独立预期

正常链 `task041_run_05`：**87/87 checks、api=25、core=476、exit 0**、failures 空。
save n=0：prepare 1、store.save 1、保存后 history 1（总 history 2）、初判 store.verify 1、core 2；
Gate1 6、Gate2 5、inspect 5/2/1/1、render 1、Gate store 核验 11、Gate core 11、冻结准备器 6、
算法/装载/复算/事实 build 0（`results.save_graph`）。verify m=1：prepare/save 0、history 1、store.verify 1、
core 1；m=2：store.verify/core 各 2（`results.verify_graph_m1/m2`）。硬化内部调用单列，未混入公式。
`independent_expectations` 仍先于候选固定（`declared_before_run=true`）；B1 S5 复确认、B3 取锁序、RC-40/44/08/09
控制全部保留并通过；m=2 后来 batch 恢复、单文件漂移与精确恢复、started/receipt 角色篡改与恢复均通过。

## 4. 失败场景（8 条 = 同口径上限，同一定稿代码）

| 场景 | 实测 | store/core 增量 | 现场 |
| --- | --- | --- | --- |
| f01_bad_submission | `Blocked store.submission.assessment` | 1/1 | started+failure；锁保留 |
| f03_store_half_write | `Error write.expectations.json`（真实句柄半写） | 1/1 | 半写叶+失败；锁保留 |
| f04_context_half_write | `Error write.context` | 1/2 | 半 context+failure；锁保留 |
| f05_receipt_sentinel | `Error write.receipt` | 1/2 | 完整 receipt 保留为失败现场 |
| f06_release_failure（函数级注入） | `Error release.lock`，不返回 RECORDED | 1/2 | 三封装+failure；锁保留 |
| rc44b_request_role | `Blocked context.prepared_request.request_sha256` | 1/2 | started+failure；锁保留 |
| h1_candidate_control | `Blocked result.record_relative` | 1/2 | 三封装+failure；锁保留 |
| h3_schema_drift | `Blocked sql/demo_schema.sql` | 0/0 | started+failure；锁保留 |

覆盖说明：f02（stale materials，store Blocked 同族）与 rc44a（S4 started 角色）不再重复建链——
前者由 f01 覆盖同一 store Blocked 路径，后者以正常链 `verify.started_role_tamper` 读路径控制
（`started.source_binding.registry_binding.run_binding_sha256`，V3）覆盖；两者已接受的 R1 现场继续冻结引用。

## 5. 四项 CLI（新进程、新 out-dir）

| 控制 | 退出 | 摘要 |
| --- | --- | --- |
| 正常 `task041_run_05` | 0 | PASS，87/87，failures 空 |
| `--mutate candidate-return` | 1 | `api_records_mismatch:call_004` |
| `--mutate ledger-replaced` | 1 | `ledger_mismatch`/`ledger_bytes_mismatch`/`drift:file_ledger.json` |
| `--mutate late-drift` | 1 | `drift:checks.json` |

## 6. 44 例映射与未执行

`summary.json` 的 `results.case_map` 按"实测 / 引用 / 未执行"三层重写：实测含 RC-01/05/08/09/11/12/13/14/17/22/24/25/29/30/31/32/40/41/42/43/44；引用含 RC-02/06/07/10/20/21/26/38/39；未执行：RC-03/15/16/18/19（坏锁类型）/23（坏 schema failure）/28/33/34/35/36/37，原因逐条登记（第二注册叶/第二事件链、会永久锁定唯一正常链、超出链预算）。
未执行：物理 junction（无权限）、真实数据、强认证、AI、终判、并发双进程真实竞态、非合作篡改证明（null + 原因）。

## 7. 保护安排与判据

定稿后**一次**全树扫描（`task041_finalization/protection_scan.py`），基线改本卡接受快照
`data/reviews/task040_dsh_r1_20261017_01/source_hashes_after.json`（171449 项 / `26a0adf7…`）。
判据：相对该基线既有 changed 仅适配器/测试/指南三件；新 missing 0、读取错误 0、未登记新增 0、身份漂移 0；
`task041_*` 与 `docs/EXEC_REPORT_041.md` 按确切路径登记，无前缀豁免；139 历史损失、27 恢复、326 越界、19 命名、
TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。
