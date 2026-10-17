# TASK-018 执行回执（开发态只读审阅包导出与离线核验）

任务：按唯一权威细则 `docs/tasks/TASK-018_DRAFT.md` 新增独立只读审阅包导出与离线核验工具。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：七组有界验收全部通过；一次**全新容器**最终入口退出 **0**、**7/7 检查 PASS、failures=[]**。宿主与控制器**未改**、无 `0009`；真实批准 `null`、`next_step_allowed=false`、AI 未开放；未生成判断、AI 建议、候选等级、终判、正式契约或真实 Gate。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 状态 | SHA-256 |
| --- | --- | --- |
| `scripts\export_demo_review_bundle.py` | 新增（55102 字节） | `baea8fd1ff9c4092aca2e120233bbff960545fc9799d8b33156c46c10147dc44` |
| `tests\test_export_demo_review_bundle.py` | 新增（61960 字节） | `7b385bd6ebffb5495b565be44ed818766427e1ba8c52297c8479bc7326ac88f1` |
| `docs\DEV_REVIEW_BUNDLE_GUIDE.md` | 新增 | `08ba5545c6d66c03937e3e05bedbf56544b19935d2f762e0f1a3ad0bb91e1f91`（见交接消息给出的写后哈希；本表不写回自身哈希） |
| `docs\EXEC_REPORT_018.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**重点冻结件实测未改**：宿主 `scripts/run_demo_workflow.py` = `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`（TASK-017-workflow-host-1.1）；TASK-017 宿主测试 = `c5b31cd798dbbb72759ae94ec65217e28ff86c453947c59cf074ed1dfa651c05`；宿主指南 = `856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8`；初判纯核心 = `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`；控制器 = `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`；事实核心 = `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`。未改规格/契约草案/SQL/上游/旧测试/回执/评审/历史现场；未装依赖、未初始化 Git、未迁移或补签旧批次、未清理现场。

---

## 2. 工具实现要点

- **独立工具**：`export_dev_review_bundle(batch_dir, out_dir)` 与 `verify_dev_review_bundle(bundle_dir)`，CLI `export`／`verify`；**不新增宿主第十子命令**，不调用宿主保存/标准化/装载/筛查/复算/底稿/初判核心，不导入旧测试、答案册或生成器作为实现依赖。标准库 + 按现有方式加载冻结宿主。
- **前提**：真实调用冻结公开 `inspect_dev_batch` 并要求 `READY`＋合法 `0001—0008`＋`SIMULATED_INITIAL_JUDGMENT_RECORDED`＋`FACT_PACKET_RECORDED`＋完整 `MATCHED`（`matched=true`、`difference_count=0`、无未匹配维度）＋开发模式＋`real_approvals=0`＋`next_step_allowed` 与 AI 动作实际许可严格 `false`。不信任调用方 status；宿主协议／前提阻断映射为 `DevReviewBundleBlocked`（退出 1）、宿主运行失败映射为 `DevReviewBundleError`（退出 2），异常链保留原始宿主异常（G2 用明确测试替身分列核对传播，未冒充真实业务链复验）。
- **路径**：`out_dir` 解析后必须在 `data/review_bundles/<本轮根>/` 之下且从未存在（既有目录含空目录拒绝）；拒绝等于源批次／外置数据库、互为祖先／后代、越出导出根；检查通过后独占创建。
- **白名单与精确字节**：恰 22 份固定来源（相对层级保留在 `evidence/` 下）＋`host_status.json`＋`README.md`＝24 份 payload，最后 `manifest.json`（共 25 个文件）。不扫描复制任意目录；每份来源一次读取同一缓冲，取长度／SHA-256／JSON 对象，输出复制**确切字节**（JSON 不重排、Markdown 不改行不加 BOM 不改 banner／判断原文）。文件字节哈希与 packet／record 规范指纹**分列**。
- **初始预期**只来自第一次真实合法 status 的 22 份绑定哈希（逐项固定映射并核对 status 声明的相对路径）；哈希要求完整 64 位小写十六进制。
- **收尾顺序**：① 路径/前提/白名单与初始预期（失败不创建输出）→ ② 独占写 24 份 payload 并读回比较 → ③ 末次真实 status 必须与第一次**严格规范相等** → ④ 实读 22 源文件与 DB 字节对比初始预期、复核 24 份输出 → ⑤ 最后独占保存 manifest 并读回 + 固定文件集合与无 failure。
- **失败现场**：输出创建后任何失败**只在新输出目录**写 `failure.json`（`TASK-018-dev-review-bundle-failure-1.0`、`stage=export`、目标退出码、异常类型/原因/完整链、已完成步骤）；不改源批次、不向宿主写诊断、不清理半写输出、不重试覆盖；诊断也失败时如实抛出并保留原异常。
- **离线核验**：只读包内固定文件，**不读取原批次/DB/宿主/核心**；检查协议/固定集/24 项大小与 SHA/路径重复与越界/指纹后缀/缺件与未知文件/`failure.json`/`0008.workflow` 与 `0007` 严格相等/记录与清单指纹一致/真实批准仍 `null`；成功 `DEV_REVIEW_BUNDLE_VERIFIED`、`scope=COPIED_BYTES_ONLY`，并标明包内 status 是历史快照。
- **README**：固定模板、UTF-8 无 BOM/LF，前部明确合成数据/开发演示/模拟初判已保存/真实人类初判未保存/真实 Gate 未批准/AI 未开放；事实数值直接取已核验返回（未重新筛查或计算金额）；不生成或改写 `assessment`/`reason`，无候选结论或取证意见；保留原 `fact_packet.md` 的既有 banner。
- **确定性**：相同源与代码导出到两个不同新目录，24 份 payload 与 manifest 逐字节相同；清单不内嵌自身哈希，也不含导出目标绝对路径、当前时间或随机 ID。

---

## 3. 最终入口与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\export_demo_review_bundle.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"                # 0
& $py -B -c "src = open(r'...\tests\test_export_demo_review_bundle.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"            # 0
& $py -B '...\tests\test_export_demo_review_bundle.py' --out-dir '...\data\review_bundle_tests\task018_run_06'                                              # 0
```

输出要点：`[PASS] G1_EXPORT_AND_DETERMINISM`、`[PASS] G2_PRECONDITIONS_AND_PATHS`、`[PASS] G3_LATE_CHANGE`、`[PASS] G4_WRITE_FAULTS`、`[PASS] G5_VERIFY_NEGATIVES`、`[PASS] G6_READONLY_AND_STOP`、`[PASS] G7_EVIDENCE_AND_PROTECTION`、`检查项 7：7 PASS / 0 FAIL`、`CLI 调用 12；公开 API 登记 26（返回 5、预期/意外异常 21（预期协议阻断 21、意外 0））；冻结 status 调用 11；missing=0 unregistered=0`、`导出包 3；包内文件 75；payload 72；真实 writer 故障 2；晚变更探针 1；核验反例 7；守卫命中 0；保护比较 executed=True`、`测试失败 0`（约 3 分 58 秒）。定点子集：`--only export|preconditions|late|writefaults|verifyneg|readonly|evidence|smoke`。

---

## 4. 七组结果与证据引用

| 组 | 结果 | 关键实测 |
| --- | --- | --- |
| G1 正常导出与确定性 | PASS | 同一新 C06b 批次分别经公开 API 与 CLI 导出至两个新目录：各 25 份文件与 24 项清单齐全、两份成功包**逐文件字节相等**；逐项对比源同缓冲字节、第一次 status 的初始绑定哈希与复制件三者一致；`record` 的 `assessment`/`reason`/`actor_id`/`occurred_at`/`event_id` 与提交原文严格一致；README 无 BOM/LF 且前部声明真实人类初判未保存；事实包无内嵌自身指纹；离线 verify 成功（24 项 payload、`scope=COPIED_BYTES_ONLY`）。C06b 事实数量 1（R02=1）。证据 `probe_records/g1_export_and_determinism.json`。 |
| G2 前提与路径 | PASS | 已有包目录、既有**空目录**、输出等于源、输出位于源内、越出导出根、父路径六类反例均 `DevReviewBundleBlocked` 且未创建输出、源批次与 DB 字节未变；真实缺失批次由冻结宿主拒绝；宿主前提阻断与运行失败经明确测试替身分列核对：分别按 `DevReviewBundleBlocked`（链含 `WorkflowHostBlocked`）与 `DevReviewBundleError`（链含 `WorkflowHostError`）传播。证据 `probe_records/g2_preconditions_and_paths.json`。 |
| G3 晚变更 | PASS | 包装真实末次 status（导出内部恰第 2 次调用）在其返回真实原对象之后给 `fact_packet.md` 追加一个 LF、不同步哈希：本次导出即 `DevReviewBundleBlocked` 且消息指向该文件、新输出留有效 `failure.json`（`target_exit_code=1`、`stage=export`）、无成功返回；撤销 wrapper 保留变更后真实 `status` 退出 1，恢复仅该原件后退出 0；恢复后源批次全部原字节相等、`0001—0008` 齐全、未向宿主写失败诊断。证据 `probe_records/g3_late_change.json`。 |
| G4 写入失败 | PASS | 复用同一合法源、两个全新输出：一次真实 `write` 半写后抛 `OSError`（payload）与 manifest 真实完整写入后抛 sentinel。两例均记录真实 open 模式 `xb`、写命中恰 1 次、确切待写 UTF-8 字节（半写 3742 字节与待写缓冲前半一致，完整 throw 的磁盘哈希＝缓冲哈希）；导出运行失败退出 2 并留有效 `failure.json`（`target_exit_code=2`）；离线 verify 拒绝该不完整包；源/DB/旧包不变；**未重跑宿主 `0008` writer 故障**。证据 `probe_records/g4_write_faults.json`。 |
| G5 离线核验反例 | PASS | 只在成功包的隔离副本上：改一个 payload 字节、清单哈希加 LF、重复清单路径、越界清单路径、加未知文件、留 `failure.json`、来源字段改绝对路径——全部 `DevReviewBundleBlocked`；原成功包字节不变；把宿主公开 status 与导出根常量替换为“调用即抛错／不存在”后离线核验**仍成功**，证明不依赖原批次/宿主，且不跟随来源字段中的绝对路径。证据 `probe_records/g5_verify_negatives.json`。 |
| G6 只读与停止点 | PASS | 六个真实下游函数（含初判纯核心）计数抛错守卫下 `export` 与 `verify` 均成功、命中 0；观察到冻结公开 status 确实被调用（本轮 11 次）；源批次文件哈希集合、外置数据库字节与 `0008` 字节前后不变；`0008.workflow` 与 `0007` 严格相等；无 `0009`；真实批准 `null`、`next_step_allowed` 与 AI 实际许可严格 `false`。证据 `probe_records/g6_readonly_and_stop.json`。 |
| G7 证据与保护收尾 | PASS | 12 条 CLI＋26 条 API 记录各留完整返回或完整异常+traceback/链/字段；权威 registry 与记录双向一致、文件台账逐项实读 exists+SHA，`missing=0`、`unregistered=0`（均为**已执行**值并进入正式 failures）；隔离自测只删审核副本一条登记即失败；保护比较单次扫描：**changed=[]、missing=[]、读取错误 0**；计数从磁盘现场导出并注明 scope（成功包 3、失败目录 3、隔离副本 7、未执行 MAIN/零条链记 false、子进程内部核心记 null）。证据 `evidence_ledger.json`、`call_registry.json`、`isolation/isolation_result.json`、`probe_records/g7_protection.json`、`counts_scope.json`。 |

---

## 5. 源 22 份与 payload 24 份逐项比对（本轮最终容器）

- **22 份来源**：每份都比对了三处——源批次文件字节哈希、第一次真实 status 的初始绑定哈希、包内复制件字节哈希，三者一致（G1 逐项断言，`probe_records/g1_export_and_determinism.json` 的 `file_set` 与 `manifest`）。
- **24 份 payload**：`manifest.json` 逐项记录 `role`／`relative`／`bytes`／`file_sha256`（复制件另记 `source_relative` 与 `source_initial_file_sha256`），离线 verify 逐项核对大小与 SHA 后计数 24；两份确定性导出之间 24 份 payload 与 manifest 逐字节相等。
- **分列口径**：文件字节哈希（如 `packet_file_sha256`／`record_file_sha256`）与对象规范指纹（`packet_sha256`／`record_sha256`）在 status、manifest 与 README 中分别记录，未相互冒充。

---

## 6. 调用与计数（来源与 scope）

| 项 | 值 | 来源 |
| --- | --- | --- |
| CLI 调用 | 12（宿主 9＋工具 3） | `cli_logs.json`（24 份原文） |
| 公开 API 登记 | 26（返回 5、预期协议阻断 21、意外 0） | `api_records.json` |
| 冻结公开 status 调用 | 11（含导出 2×3 次与状态检查） | `status_calls.json` |
| 成功导出包 / 包内文件 / payload | 3 / 75 / 72 | `counts_scope.json`（磁盘现场导出） |
| 仅失败目录（只有 failure.json） | 3（G3 晚变更 1＋G4 两场景） | 同上 |
| 隔离核验副本 | 7 | 同上 |
| 真实 writer 故障 | 2（半写＋完整后 sentinel），模式 `xb`、命中各 1 | `probe_records/g4_write_faults.json` |
| 晚变更探针 / 核验反例 / 守卫命中 | 1 / 7 / 0 | 同上与 `g6_readonly_and_stop.json` |
| 未执行项 | `main_chain_executed=false`、`zero_finding_chain_executed=false`、`subprocess_internal_core_calls=null` | `counts_scope.json` |

---

## 7. 保护比较

基线 `data/reviews/task017_r1_gpt_20261013_041026/source_hashes_after.json`（实际 **128451** 项、文件 SHA-256 `a54692ceaca126cc283867a88991d7e0c1329e2875aa5d5935be1cedab417803`，与同目录 `review_result.json` 登记一致）：单次扫描 131032 文件后 **changed=[]（本卡对既有文件零改动）**、**missing=[]**、读取错误 0；六个重点冻结件哈希全部一致。本卡新增的四个文件（工具、测试、指南、回执）与三个数据根均为新增项，不在基线内，故不产生 changed。指南与回执写入之后对最终树复扫一次的结果一致（见 probe_records/g7_protection_final_tree.json：changed=[]、missing=[]、读取错误 0、六个冻结件一致）。

---

## 8. 过程失败尝试与修正（如实记录）

1. 测试最初加载了**另一个**宿主模块实例，导致替身／守卫／观察不作用于导出工具实际调用的对象（G2 替身无效、G3 注入未命中）→ 改为统一使用 `EXPORTER._host()` 的同一模块实例。
2. 宿主协议／运行异常最初被工具的兜底 `except Exception` 统一映射为 `DevReviewBundleError`，丢失“前提 vs 运行”分列 → 新增 `_call_status` 显式映射：宿主 `WorkflowHostBlocked`→`DevReviewBundleBlocked`（退出 1）、宿主 `WorkflowHostError`→`DevReviewBundleError`（退出 2），并在异常链中保留原始宿主异常。
3. G2 的替身断言最初期望原始宿主异常类型 → 改为期望工具映射后的类型并断言异常链含宿主类别。
4. 计数最初用累计器，会把“有 manifest 但留下 failure.json”的目录算成成功包、把守卫导出的第三个包漏掉 → 改为从磁盘现场导出并明确区分成功包与仅失败目录。

过程容器：`data/review_bundle_tests/task018_run_01`…`run_05`（修正前各轮）与 `task018_smoke1`（早前手动冒烟）均保留未回写。

---

## 9. 四条绝对根路径

- 测试证据根：`D:\harness work\audit_sa_project\data\review_bundle_tests\task018_run_06`（248 文件：`summary.json`／`checks.json`／`counts.json`／`counts_scope.json`／`cli_logs.json`／`api_records.json`／`status_calls.json`／`call_registry.json`／`evidence_ledger.json`；`cli_logs\` 24、`api_records\` 26、`probe_records\` 7、`isolated_bundles\` 7、`isolation\` 1、`pending_bytes\` 1）
- 导出根：`D:\harness work\audit_sa_project\data\review_bundles\task018_run_06`（128 文件；成功包 `api_bundle`／`cli_bundle`／`guard_bundle`，仅失败目录 `late_change_bundle`／`g4_payload_partial`／`g4_manifest_throw`）
- 新批次根：`D:\harness work\audit_sa_project\data\batches\task018_run_06`（37 文件；仅 `c06b` 一个批次）
- 外置 SQLite 根：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task018_run_06`（1 文件）

---

## 10. 未执行与边界

- 未执行：MAIN 或零条建链（对应实测数不填）、TASK-002—017 历史入口、冻结旧测试与事实核心/初判纯核心的完整组；未重跑宿主 `0008` writer 故障（GPT 已读原现场，仅保留引用）。
- 未改宿主/控制器/纯核心/规格/契约草案/SQL/历史现场；**无 `0009`**、无 AI/LLM/网络/UI/ERP、无 PDF/Office 转换、无压缩上传、无新依赖。
- 边界：导出包**不是**完整批次备份、不是可恢复宿主目录、不构成身份认证或独立审计保证；离线核验只确认包内文件与清单一致（`COPIED_BYTES_ONLY`），不证明原始业务真实性，也不重新批准批次；**模拟初判已保存不等于真实人类独立初判已保存**；真实批准仍 `null`、`next_step_allowed=false`、AI 未开放。有限收尾不承诺阻止任意时点并发篡改。
- 未解决项：无。业务前提与真实流程由人类决定；执行端已完成本卡，不做下一任务。
