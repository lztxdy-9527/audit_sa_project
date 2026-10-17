# TASK-018-R2 执行回执（批次ID字符串类型定点修正）

任务：按唯一权威细则 `docs/tasks/TASK-018-R2.md` 修新增阻断 B3（批次ID字段校验）。依据 `docs/reviews/REVIEW_TASK_018_R1.md`。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：B3 已修复并有定点实测证据；**全新容器**一次运行退出 **0**、**4/4 PASS、failures=[]**。原 B1/B2/E1 与真实 writer 证据明确引用、**未重跑**；未重跑 R1 六组、旧七组、smoke、源晚变更、MAIN/零条、上游或历史入口。宿主/控制器/全部核心/指南/历史现场冻结、**无 0009**；未新建 batches/SQLite、未重建上游链。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `scripts\export_demo_review_bundle.py` | `7b78eefca18916c44d9dbc12f73bf480308fa3717b3bb0fc2ce02f67995788a5` | `0b2f7b288cc49327a124a6defad5b1d9ddd09856d6c907b6120536d932e32577`（74648 字节） |
| `tests\test_export_demo_review_bundle.py` | `99370503d3904c5f3a1e950e8a03eb7230c05fb473cea5ce58b1380f078ab9bc` | `042b20e33a37577a9c2c69050b4d34ca082dbfa862f9e061a54a3b0eeeb78fcf`（122778 字节） |
| `docs\EXEC_REPORT_018_R2.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**冻结件实测未改**：宿主 `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`；控制器 `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`；初判纯核心 `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`；事实核心 `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`；TASK-017 宿主测试 `c5b31cd798dbbb72759ae94ec65217e28ff86c453947c59cf074ed1dfa651c05`；**指南 `9a65bf991253f466b2130eebf776f936e2e9a767525bc0370da401c5a43df0c7` 按卡保持冻结未改**。旧卡/回执/评审、R1 交付包与全部历史现场未回写、未清理。

---

## 2. B3 修正实现（唯一实现改动）

1. **`_verify_manifest_shape` 的 `source_batch.batch_id`**：删除"不是 64 位哈希"的错误排除，改为明确的**非空字符串**检查（不 strip、不截断、不改大小写、不转数字、不强制 `str`）；同一处的身份字符串检查（`host_version`）也去掉了相同的错误排除，仍要求非空字符串身份精确一致。
2. **`_require_identity_relations` 的十处批次身份**：在构造 distinct 集合或做等值比较**之前**，逐字段确认 ID 为**非空字符串**，否则抛 `DevReviewBundleBlocked` 并给出精确字段路径（`manifest.batch_id`、`manifest.source_batch.batch_id`、`host_status.batch_id`、`host_manifest.batch_id`、`batch_manifest.batch_id`、`checkpoint_0008.batch_id`、`checkpoint_0008.workflow.state.batch_id`、`record.source.batch_id`、`record.simulated_initial_judgment.batch_id`、`submission.batch_id`）；之后才构造集合做同批次判定。保留原字符串精确比较。
3. **未做的事**（按卡）：不全局捕获 `TypeError`/`AttributeError`，不把非字符串强制 `str`，不放宽任何 SHA 字段的完整 64 位小写十六进制要求，不改 `verify` 的 I/O、末尾字节确认、来源映射或身份算法，不新增校验框架。

---

## 3. 定点验证（`--only r2`，全新容器一次运行）

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B '...\tests\test_export_demo_review_bundle.py' --out-dir '...\data\review_bundle_tests\task018r2_run_02' --only r2     # 0
```

输出要点：`R2_NORMAL_CONTROL_EXPORT`、`R2_ID_TYPE_PROTOCOL_BLOCK`、`R2_LEGAL_STRING_SHAPE`、`R2_EVIDENCE_PROTECTION_AND_STOP` 全部 `[PASS]`；`检查项 4：4 PASS / 0 FAIL`；`CLI 调用 2；公开 API 登记 8（返回 3、预期协议阻断 5、意外 0）；helper 对照 9；宿主代码帧 直连 1／嵌套 2；missing=0 unregistered=0`；`守卫命中 0；保护比较 executed=True；测试失败 0`（约 3 分 43 秒）。

### 3.1 正常对照（第 1 项）

复用只读源 `data/batches/task018_run_06/c06b`：最终工具真实 `export` 一次（六个真实下游函数计数抛错守卫下，**命中 0**）+ 公开 API `verify` + 新进程 CLI `verify` **均 0**；包 **25 文件／24 payload**、22 份复制件与源字节及真实 status 初始绑定逐项一致、C06b 事实 **1 条（R02=1）**、判断原文（assessment/reason/actor_id/occurred_at/event_id 与提交一致）与开发边界不变。入口**开始前**取得源 37 文件与外置 DB 哈希快照（`pre_entry_source_hashes.json`），全部定点结束后比较：**源 37 文件未变、DB 字节未变（`d5f09d2c…a68c`）、正常对照包未变**。证据 `probe_records/r2_normal_control.json`、`probe_records/r2_protection_and_scope.json`。

### 3.2 协议类型反例（第 2 项，只改 `manifest.source_batch.batch_id`）

| 候选声明 | 公开 verify 结果 | 字段 | CLI | 候选是否被改 |
| --- | --- | --- | --- | --- |
| `[]` | `DevReviewBundleBlocked` | `manifest.json.source_batch.batch_id` | 新进程 **退出 1** | 否 |
| `{}` | `DevReviewBundleBlocked` | 同上 | — | 否 |
| `null` | `DevReviewBundleBlocked` | 同上 | — | 否 |
| 整数 `7` | `DevReviewBundleBlocked` | 同上 | — | 否 |
| 布尔 `True` | `DevReviewBundleBlocked` | 同上 | — | 否 |

五例均在正常包的隔离副本内**只**改该字段，payload/哈希/25 固定文件/24 清单不变；**无原生 `TypeError`、无 `unverifiable`/`unhashable` 文案、无退出 2**；消息指向精确字段；`verify` 只读、未写 `failure.json`；正常包字节不变。每例保存完整实际异常、`traceback`、原因链与候选身份（`probe_records/r2_id_type_negatives.json`、`api_records/r2_id_*.exception.json`、`cli_logs/r2_id_array_cli.*`）。

### 3.3 合法字符串形状（第 3 项，shape helper 对照）

直接调用实际 shape helper `_verify_manifest_shape`（在内存副本上，**不是完整包改绑成功、不是真实批次运行、不是公开 API**）：普通 ID `c06b`、前导零字符串 `0abc123`、**64 位小写十六进制 `a×64`**、`0×64` **均通过**（不再误拒，原字符串原样保留、不被当作 SHA 字段要求或禁止值）；同 helper 下五类非法类型均 `DevReviewBundleBlocked` 并指向 `manifest.json.source_batch.batch_id`。证据 `probe_records/r2_shape_helper.json`、`helper_records/r2_shape_*.{return,exception}.json`。

### 3.4 证据/只读/保护收尾（第 4 项）

- 登记分列：公开工具 API 8（返回 3、预期协议阻断 5、意外 0）、CLI 2、**helper 对照 9**（与公开调用分列，均留完整返回或完整异常+`traceback`+链+字段）；真实观察工具内部宿主 status 与六个核心守卫（命中 0）；子进程内部核心次数 `null`（未观察，不推定）。
- 台账：registry 与记录双向比较、文件台账逐项实读 `exists`+SHA，`missing=0`、`unregistered=0`（**来自已执行检查**，进入正式 `failures`）；隔离自测只删审核副本一条登记即失败（`failed_as_expected`）。
- 保护：**单次完整扫描** R2 基线 `data/reviews/task018_r1_gpt_20261013_144137/source_hashes_after.json`（实际 **132537** 项、文件 SHA `8d8576a5c4cf947fc83834cfaf532d96167f38689a81570696b1b1008f86bd0c`，与同目录 `review_result.json` 登记一致）→ 实扫 133037 文件后 `changed` **恰为**本卡允许的两个文件、`unexpected_changes=[]`、`missing=[]`、读取错误 0、六个重点冻结件一致；文档写后**未再扫全树**，仅有限登记本轮新增产物身份。
- 停止点：`problems=[]` —— `phase=DEV_GATE2_APPROVED`、真实批准 `null`、`next_step_allowed` 严格 `false`、无 `0009`（checkpoint 止于 `0008.json`）。

---

## 4. 调用与计数（scope）

| 项 | 值 | 来源 |
| --- | --- | --- |
| CLI | 2 | `cli_logs.json` |
| 公开 API 登记 | 8（返回 3、预期协议阻断 5、意外 0） | `api_records.json` |
| helper 对照 | 9（对照 4 + 非法类型 5） | `helper_records.json`、`probe_records/r2_shape_helper.json` |
| 宿主代码帧（直连／工具嵌套） | 1 / 2 | `host_code_entries.json` |
| 成功包／失败现场／隔离副本 | 1（`r1_normal`，正常对照）／0／5 | `counts_scope.json` |
| 守卫命中 | 0 | `probe_records/r2_normal_control.json` |
| 台账 missing／unregistered | 0 / 0 | `evidence_ledger.json` |
| 未执行项 | 真实 writer 故障 `null`（引用原现场）、R1 六组/旧七组/smoke/源晚变更/MAIN/零条 `false`、子进程内部核心 `null` | `counts_scope.json` |

**scope 说明**：本定点只读复用 `data/batches/task018_run_06/c06b`（37 文件）与其宿主推导外置 DB（`d5f09d2c…a68c`），未新建批次或 SQLite；正常对照包 1 个，其余五类类型反例与四个 shape 对照均为**隔离副本或内存对象**。

---

## 5. 过程失败尝试与修正

1. R2 首轮 `R2_EVIDENCE_PROTECTION_AND_STOP` 失败：helper 对照记录未进文件台账（`missing=6`）——原因是我的台账补丁只落在旧七组收尾函数上，未落在 R2 复用的 R1 收尾函数 → 在 `group_r1_finalize` 内补上 helper 记录的台账项（`helper:<label>`）后 `missing=0`。
2. R2 模式横幅最初仍打印"（七组）" → 修正为按 `--only` 显示 R1/R2 定点模式（纯显示修正）。

过程容器：`data/review_bundle_tests/task018r2_run_01`（修正前）与 `data/review_bundles/task018r2_smoke`（手动探针）保留未回写。

---

## 6. 产物路径

- 测试证据根（新）：`D:\harness work\audit_sa_project\data\review_bundle_tests\task018r2_run_02`（167 文件：`summary.json`／`checks.json`／`counts.json`／`counts_scope.json`／`cli_logs.json`／`api_records.json`／`helper_records.json`／`host_code_entries.json`／`call_registry.json`／`evidence_ledger.json`／`pre_entry_source_hashes.json`；`probe_records\`、`helper_records\`、`api_records\`、`cli_logs\`、`isolated_r2\`、`isolation\`）
- 导出根（新）：`D:\harness work\audit_sa_project\data\review_bundles\task018r2_run_02`（25 文件，正常对照包 `r1_normal`）
- 只读源（既有未改）：`D:\harness work\audit_sa_project\data\batches\task018_run_06\c06b`
- 只读外置 DB（既有未改）：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task018_run_06\c06b\audit.sqlite3`

---

## 7. 未执行与边界

- 未重跑：R1 六组、旧七组、smoke、源晚变更、`_write_exclusive` 真实 writer 半写/完整后 sentinel 故障（**读取证据、未重跑**）、MAIN/零条、上游与历史入口；B1/B2/E1 与原 writer 证据均明确引用。
- 未新建 batches/SQLite、未重建上游链、未迁移/补签/覆盖/删除或清理历史、未安装依赖、未初始化 Git、未新增通用框架；指南按卡保持冻结。
- 仍未到 `0009`、无 AI/LLM/网络/UI/ERP、无正式契约或真实 Gate；**模拟初判已保存 ≠ 真实人类独立初判已保存**；本次是字段类型校验修正，不涉及业务口径、审计判断、身份认证或批准变更。
- 未解决项：无。业务前提与真实流程由人类决定；执行端已完成本卡，不做 TASK-019。
