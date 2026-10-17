# TASK-018-R1 执行回执（导出/离线核验收尾与来源身份闭合）

任务：按唯一权威细则 `docs/tasks/TASK-018-R1.md` 修两项实现阻断 B1／B2 并闭合 E1 证据登记与观察。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：六项定点检查全部通过；**全新容器**一次运行退出 **0**、**6/6 PASS、failures=[]**。B1（导出收尾 + 离线核验最后消费）、B2（来源/身份闭合）、E1（真实直接调用登记与真实缺失批次观察）均已关闭。宿主/控制器/全部纯核心/历史现场冻结、**无 0009**、真实批准 `null`、`next_step_allowed=false`、AI 未开放；未新建 batches/SQLite、未重建上游链。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `scripts\export_demo_review_bundle.py` | `baea8fd1ff9c4092aca2e120233bbff960545fc9799d8b33156c46c10147dc44` | `7b78eefca18916c44d9dbc12f73bf480308fa3717b3bb0fc2ce02f67995788a5`（73762 字节） |
| `tests\test_export_demo_review_bundle.py` | `7b385bd6ebffb5495b565be44ed818766427e1ba8c52297c8479bc7326ac88f1` | `99370503d3904c5f3a1e950e8a03eb7230c05fb473cea5ce58b1380f078ab9bc`（106411 字节） |
| `docs\DEV_REVIEW_BUNDLE_GUIDE.md` | `08ba5545c6d66c03937e3e05bedbf56544b19935d2f762e0f1a3ad0bb91e1f91` | `9a65bf991253f466b2130eebf776f936e2e9a767525bc0370da401c5a43df0c7`（11185 字节） |
| `docs\EXEC_REPORT_018_R1.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**冻结件实测未改**：宿主 `scripts/run_demo_workflow.py` = `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`；控制器 = `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`；初判纯核心 = `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`；事实核心 = `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`；TASK-017 宿主测试 = `c5b31cd798dbbb72759ae94ec65217e28ff86c453947c59cf074ed1dfa651c05`；宿主指南 = `856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8`。原 TASK-018 卡/回执/评审、交付包与全部历史现场未回写或清理。

---

## 2. B1（P1）：最后必要消费之后的实际字节核验（已关闭）

### 2.1 导出侧

`_export_inner` 在 **manifest 保存并读回 → 末次真实公开 status → 22 份来源与外置 DB 复测** 等全部必要消费之后、返回成功前，新增最后一步纯字节确认（`steps` 中为 `final_byte_confirmation`）：实读 **24 份 payload 与 manifest** 的确切字节，逐项与本次待写缓冲比较（manifest 预期即该次 writer 返回的读回哈希；清单不内嵌自身哈希），并确认固定文件集合与无 `failure.json`。22 份来源/DB 的最后实读核验保留，未用后来读数替换初始预期。

**GPT 复现的两个注入点定点实测**（各用一个全新输出，先无注入观察真实消费位置）：

| 注入点 | 命中 | 本次导出 | 消息指向 | failure | 撤销后新进程 verify |
| --- | --- | --- | --- | --- | --- |
| README.md：真实 writer 序列第 25 次（manifest）之后、`_read_sources`（来源/DB 必需消费）第 3 次即最后一次返回原缓冲之后 | 1 | `DevReviewBundleBlocked`／退出 1 | `README.md`（"最终字节确认发现输出与待写字节不一致：期望 4264 字节/b280194a…" ） | `target_exit_code=1`、`stage=export` | 退出 1 |
| manifest.json：真实 manifest writer 返回（含写后读回）之后 | 1 | `DevReviewBundleBlocked`／退出 1 | `manifest.json`（"写后读回的 manifest 字节与写入结果不一致"） | `target_exit_code=1`、`stage=export` | 退出 1 |

无注入观察记录：writer 调用共 25 次、manifest 为第 25 次即最后一次；`_read_sources` 共 3 次（初始 1＋复测 2，最后位置取自真实调用）。两个 wrapper 都调用**真实** writer/reader 并返回其原值，本轮未声称执行新的 writer 故障分支。证据：`probe_records/r1_export_tail_observation.json`、`probe_records/r1_export_tail_probes.json`。

### 2.2 离线核验侧

`verify_dev_review_bundle` 重写为**同缓冲绑定**：25 个固定文件各读一次缓冲，长度/哈希与所有必要 JSON 对象都从该缓冲取得（不再另读磁盘解析）；返回成功前在全部身份/对象消费之后做一次有限最终确认——把 25 个文件再次从磁盘实读并与初次缓冲比较，同时复核固定集合与无 `failure.json`。不与后来读数自比、不等下一次调用。

**定点实测**（只在正常包的隔离副本）：无注入观察缓冲读取恰 25 次；在**最后一次**缓冲读取返回真实原对象之后给 `evidence/workflow/initial_judgment/initial_judgment.json` 追加一个 LF → 本次 verify 即 `DevReviewBundleBlocked` 并指向该文件（"最终字节确认发现包内文件在本次必要消费之后发生变化：期望 3152 字节/4644663a…"）；撤销 wrapper 后新进程 verify 退出 1；该次核验**只**改动了被注入的那一个文件（其余全部字节与集合不变）、未写 `failure.json`；正常原包字节不变。证据：`probe_records/r1_offline_observation.json`、`probe_records/r1_offline_tail.json`。

---

## 3. B2（P2）：包内来源与身份关系闭合（已关闭）

`verify` 新增（不重写宿主协议、不调用冻结核心复算，只用包内同缓冲对象与实际字节）：

- 22 份复制件：`actual SHA == payload.file_sha256 == source_initial_file_sha256 == 历史 status 固定映射`（路径仍由固定白名单决定，不跟随清单任意路径）。
- manifest 既有来源字段与实际产物/历史 status/`0008.operation` 一致：`packet_file_sha256`、`record_file_sha256`、`checkpoint_0008_file_sha256`、`database_sha256`、`submission_file_sha256`、`artifacts_file_sha256`、`started_file_sha256`、`packet_sha256`/`record_sha256`（对象规范指纹按实际规范 JSON 单独重算）。
- 批次身份在 manifest、`source_batch`、host_status、host_manifest、batch_manifest、`0008`、`0008.workflow.state`、`record.source`、`record.simulated_initial_judgment`、`submission` 之间同属一批次（恰一个值且非 null），并与 `packet`/`record` 指纹在各声明处一致。
- `0008.previous_file_sha256` 与 `manifest.checkpoint_0008.previous_file_sha256`、`operation.previous_checkpoint_file_sha256` 均等于包内 `0007` 实际文件哈希；`0008.workflow` 与 `0007` 严格规范相等；`operation.kind`/`revision`（严格整数）正确。
- 宿主/工具身份：`host_version`、`host_code_sha256.host_code`、`initial_judgment_core`、`run_bindings_sha256` 与包内 `host_manifest`、历史 status、`0008`、`operation.bindings_sha256`/`core_sha256` 对应；导出工具实测哈希仍在 manifest。
- 边界一致：`mode`、`contract_status=DRAFT_NOT_IN_FORCE`、`real_approvals=0`（严格整数）、`gate1/gate2_approval`、`human_initial_judgment`、`ai_suggestion`、`final_judgment` 为 `null`、`next_step_allowed`/`ai_suggestion_allowed`/AI 动作实际许可严格 `false` 在 manifest、status、`0008`、record 间一致；`revision`/计数使用严格类型（`_is_strict_int`，布尔与浮点不被接受）。非法结构为可定位的 `DevReviewBundleBlocked`（退出 1）；运行/I-O 仍为 `DevReviewBundleError`（退出 2，保留 cause）。

**四个格式合法反例定点实测**（各独立隔离副本、25 固定文件与 24 清单齐全、可解析；前三个只改合法 64 位声明，第四个仅更新候选 status 的 payload 大小/SHA 而保持 c06b 的 `0008`/record/submission 未改）：

| 反例 | 本次 verify | 指向矛盾字段 |
| --- | --- | --- |
| `manifest.canonical_fingerprints.packet_file_sha256` = 64×`0` | `DevReviewBundleBlocked`／退出 1 | `canonical_fingerprints.packet_file_sha256`（必须等于实际事实包文件字节哈希） |
| 首份复制件 `source_initial_file_sha256` = 64×`0` | `DevReviewBundleBlocked`／退出 1 | `payloads[batch_manifest.json].source_initial_file_sha256` |
| `manifest.checkpoint_0008.previous_file_sha256` = 64×`0` | `DevReviewBundleBlocked`／退出 1 | `manifest.checkpoint_0008.previous_file_sha256`（必须等于包内 0007 实际文件哈希 `ffde47ba…`） |
| manifest/host_status/`source_batch` 批次改 `OTHER-BATCH`（仅同步 status payload 大小/SHA） | `DevReviewBundleBlocked`／退出 1 | `batch_id`（包内批次身份必须同属一批次） |

正常包字节未被反例改动。证据：`probe_records/r1_identity_negatives.json`（含每次完整异常与消息）。`COPIED_BYTES_ONLY` 含义不变：只说明包内自洽，不证明来源业务真实性、不作身份认证、不重新批准批次。

---

## 4. E1：真实直接调用登记与必要观察（已关闭）

- **共享直接宿主读取全部登记**：`status_of` 现在经 `record_api` 走冻结公开 `HOST.inspect_dev_batch`，每次调用保存完整实际返回或完整异常+`traceback`+cause 链+字段，并记入 `DIRECT_HOST_STATUS_CALLS`。本轮直接登记调用 2 次（`r1_direct_status_initial`、`r1_direct_status_registered`），均有 `return_path` 与文件哈希。
- **观察器绑定实际使用的模块**：在导出工具与测试共用的同一个宿主模块实例上包裹（`install_host_observer`），按**真实代码帧**把每次进入宿主分列为 `test_direct` 与 `tool_nested`（精确文件名判定，测试文件不计入工具内部）。本轮宿主代码帧共 11 次：**直连 3／嵌套 8**，与已登记条数**不要求相等**，两个 scope 分别给出。
- **真实缺失批次观察已纠正**：原 `g2_missing_batch` 实际是工具 `_resolve_source_batch` 的 `is_dir` 前置拒绝（宿主代码帧 0），本轮**另列**为"工具前置拒绝"（实测工具嵌套宿主增量 0）；并**新增一次已登记的真实 `HOST.inspect_dev_batch` 缺失批次调用**（`r1_direct_status_missing_batch`），真实进入宿主代码帧（直连增量 1）并捕获宿主原生 `WorkflowHostBlocked`，完整链保留（`exception_chain = [WorkflowHostBlocked]`，消息指出 `batch_dir` 不存在）。未新建任何批次或伪造空现场。
- **R1 入口实际运行**：registry／引用双向核验与逐文件 `exists`+SHA 台账、完整异常/traceback 链、隔离自测（只删审核副本一条 registry 即失败 `failed_as_expected`）、正确保护与停止点检查，均进入正式 `failures`；`missing=0`、`unregistered=0` 来自**已执行**检查（未测项记 `null`）。

---

## 5. 定点入口、执行与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\export_demo_review_bundle.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"                 # 0
& $py -B -c "src = open(r'...\tests\test_export_demo_review_bundle.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"             # 0
& $py -B '...\tests\test_export_demo_review_bundle.py' --out-dir '...\data\review_bundle_tests\task018r1_run_01' --only r1                                    # 0
```

输出要点：`[PASS] R1_NORMAL_EXPORT_AND_DETERMINISM`、`[PASS] R1_EXPORT_TAIL_BYTE_CONFIRMATION`、`[PASS] R1_OFFLINE_TAIL_BYTE_BINDING`、`[PASS] R1_SOURCE_IDENTITY_RELATIONS`、`[PASS] R1_REGISTRATION_AND_OBSERVATION`、`[PASS] R1_EVIDENCE_PROTECTION_AND_STOP`、`检查项 6：6 PASS / 0 FAIL`、`CLI 调用 4；公开 API 登记 15（返回 6、预期协议阻断 9、意外 0）；宿主代码帧 直连 3／嵌套 8；missing=0 unregistered=0`、`守卫命中 0；保护比较 executed=True；测试失败 0`（约 3 分 31 秒）。

`--only r1` 不自动调用 `build_c06b_batch`，仅只读复用 `data/batches/task018_run_06/c06b` 与其宿主推导的外置 DB；未跑完整七组、smoke、MAIN/零条、源晚变更、真实 writer 故障或历史入口。默认定点组：正常包（六真实下游守卫下真实导出一次、正常核验与新进程 CLI 0，C06b 事实 1 条 R02=1、判断原文与开发边界不变）→ 导出收尾两目标 → 离线最后消费 → 四身份反例 → 登记/观察 → 证据/保护/停止点收尾。

---

## 6. 调用与计数（来源与 scope）

| 项 | 值 | 来源 |
| --- | --- | --- |
| CLI 调用 | 4（工具 verify／注入后拒绝各 2） | `cli_logs.json` |
| 公开 API 登记 | 15（返回 6、预期协议阻断 9、意外 0） | `api_records.json` |
| 宿主代码帧（直连／工具嵌套） | 3 / 8（共 11） | `host_code_entries.json`、`counts_scope.json` |
| 测试直接登记宿主调用 | 2（正常 + 真实缺失批次） | `probe_records/r1_registration.json` |
| 成功包／失败现场／隔离副本 | 2（`r1_normal`、`r1_observe`）／2（`r1_tail_README_md`、`r1_tail_manifest_json`）／5 | `counts_scope.json` |
| 守卫命中 | 0 | `probe_records/r1_normal_export.json` |
| 台账 missing／unregistered | 0 / 0（已执行检查值） | `evidence_ledger.json` |
| 隔离自测 | `failed_as_expected` | `isolation/isolation_result.json` |
| 未执行项 | 真实 writer 句柄故障 `null`（仅引用原现场）、MAIN／零条链 `false`、子进程内部核心 `null` | `counts_scope.json` |

**scope 说明**：本轮定点只读复用 `data/batches/task018_run_06/c06b`（37 文件、外置 DB `d5f09d2c8593991891344175e7bb1f97e1bf41c8a6e4fd1aec94f3253625a68c`），未新建批次或 SQLite；成功包 2 个、失败现场 2 个、隔离副本 5 个均在本轮新导出根下，未改动旧现场。

---

## 7. 保护比较与停止点

正确基线 `data/reviews/task018_gpt_20261013_051328/source_hashes_after.json`（实际 **131256** 项、文件 SHA-256 `791571d67f7dc036a4d8f7eece30e6b459810dbca4a2393c16a04adb401ce249`，与同目录 `review_result.json` 登记一致）：**单次完整扫描** 132187 文件后 `changed` **恰为**本卡允许的三个既有文件（`scripts/export_demo_review_bundle.py`、`tests/test_export_demo_review_bundle.py`、`docs/DEV_REVIEW_BUNDLE_GUIDE.md`）、`unexpected_changes=[]`、`missing=[]`、读取错误 0、六个重点冻结件一致。本轮新增产物（`docs/EXEC_REPORT_018_R1.md`、两个新数据根）为新增项，不在基线内；文档写入后**未再扫全树**（仅按卡要求对本轮新增产物作有限身份登记：`source_tree_hashes.json`、`probe_records/r1_source_unchanged.json`）。

停止点：`phase=DEV_GATE2_APPROVED`、`next_step_allowed` 严格 `false`、真实批准 `null`、`ai_suggestion`/`ai_suggestion_allowed=false`、`0008.workflow` 与 `0007` 严格相等、无 `0009`、无 `0008` 之后的新 checkpoint；只读源批次 37 文件与外置 DB 字节在本轮前后一致，正常包字节未被任何反例改动。

---

## 8. 辅助记录澄清（卡 §4，不回写旧回执）

- 原回执"21 条预期协议阻断"实为 **18 条 `DevReviewBundleBlocked` + 3 条 `DevReviewBundleError`**；本轮分列登记（本轮定点为 9 条预期协议阻断、0 条意外）。
- 原 `failure_only_bundles` 文案不准确：那 3 个目录是**失败现场**，实际保留 `late_change_bundle` 的 24 份 payload、`g4_payload_partial` 的半写文件、`g4_manifest_throw` 的 24 份 payload 与完整 manifest（符合失败保留原则）；旧现场未清理。
- 原 `duplicate_path` 反例通过追加第 25 项触发条目数拒绝，未单独命中重复路径分支；本轮未触及该反例，不改旧现场。

---

## 9. 过程失败尝试与修正（如实记录）

1. 重写离线核验时误删了 `_verify_manifest_shape`，`verify` 报 `NameError` 被兜底映射为退出 2 → 补回该函数并加入严格整数/身份/边界检查。
2. 观察器最初用子串判断"是否工具内部调用"，测试文件名 `test_export_demo_review_bundle.py` 含该子串导致全部误判为 `tool_nested`（直连 0）→ 改为**精确文件名**匹配，直连／嵌套分列正确（3／8）。
3. 首轮把 `BASELINE` 仍指向 TASK-017-R1 基线，导致"changed=[]"假通过 → 改为本卡 R1 基线 `task018_gpt_20261013_051328`（131256 项），复扫得到 changed 恰为三个允许文件。
4. 早前在项目根创建的过程脚本 `.t18r1_*.py` 已从项目内移除（它们不在 R1 基线内，不影响 missing）；R1 基线已跟踪的 `.t18_fix1.py` **保持原样未动**。

过程容器：`data/review_bundle_tests/task018r1_smoke`／`task018r1_smoke_a`／`task018r1_smoke_b` 及对应导出根保留未回写。

---

## 10. 产物路径

- 测试证据根（新）：`D:\harness work\audit_sa_project\data\review_bundle_tests\task018r1_run_01`（169 文件：`summary.json`／`checks.json`／`counts.json`／`counts_scope.json`／`cli_logs.json`／`api_records.json`／`host_code_entries.json`／`call_registry.json`／`evidence_ledger.json`／`source_tree_hashes.json`；`probe_records\` 8、`api_records\` 15、`cli_logs\` 8、`isolated_r1\` 5、`isolation\` 1）
- 导出根（新）：`D:\harness work\audit_sa_project\data\review_bundles\task018r1_run_01`（102 文件；成功包 `r1_normal`、`r1_observe`；失败现场 `r1_tail_README_md`、`r1_tail_manifest_json`）
- 只读源批次（既有，未改）：`D:\harness work\audit_sa_project\data\batches\task018_run_06\c06b`
- 只读外置 DB（既有，未改）：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task018_run_06\c06b\audit.sqlite3`

---

## 11. 未执行与边界

- 未重跑：完整七组、smoke、MAIN/零条建链、源晚变更、`_write_exclusive` 真实 writer 半写/完整后 sentinel 故障（**仅引用原现场并明确"读取证据，未重跑"**，本轮实现未触及该路径）。
- 未新建 batches/SQLite、未重建上游链、未迁移/补签/覆盖/删除或清理历史；未安装依赖、未初始化 Git、未新增通用框架。
- 仍未到 `0009`、无 AI/LLM/网络/UI/ERP、无正式契约或真实 Gate；**模拟初判已保存 ≠ 真实人类独立初判已保存**；导出包内自洽不等于身份认证或来源业务真实性；离线核验仍为 `COPIED_BYTES_ONLY`。
- 未解决项：无。业务前提与真实流程由人类决定；执行端已完成本卡，不做 TASK-019。
