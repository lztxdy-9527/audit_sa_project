# TASK-017 执行回执（开发态宿主保存模拟独立初判）

任务：按唯一权威细则 `docs/tasks/TASK-017_DRAFT.md` 把 TASK-016/R1 已验收的**冻结纯核心**接入宿主：接收调用方显式提供的模拟初判、独占保存并生成 `0008`，支持失败恢复与只读核验。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：七组有界验证全部通过；一次**全新容器**最终入口退出 **0**、**7/7 检查 PASS、failures=[]**；停在开发态 `0008` / `SIMULATED_INITIAL_JUDGMENT_RECORDED`——`phase` 仍 `DEV_GATE2_APPROVED`、`0008.workflow` 与 `0007` 严格等值、真实批准 `null`、`next_step_allowed=false`、AI 仍不允许；未建 `0009`、未开放真实判断/真实 Gate/AI。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `scripts\run_demo_workflow.py` | `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a` | `e65b8b3ee604f66808f88176e0ad870de00a479a07e6a2cc989590ddd16232c5`（487587 字节） |
| `docs\WORKFLOW_HOST_GUIDE.md` | `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8` | `856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8`（59925 字节） |
| `tests\test_initial_judgment_demo_workflow.py` | 新增 | `ef8c0eccb191b7c84c70694479f942bac553e5b52e3b17511cc4993fef6611a3`（70698 字节） |
| `docs\EXEC_REPORT_017.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**重点冻结件实测未改**：`scripts/build_demo_initial_judgment.py` = `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`；`tests/test_build_demo_initial_judgment.py` = `c0ef730e59ad78f54d7d60014289ea56ca7e79c764f9afba515c1c77449b62f3`；`docs/INITIAL_JUDGMENT_GUIDE.md` = `2bbaa876ae7a76175f3462d9395b7bbc8e4bec5b1631030ff3fe32142d0286f5`；控制器 `scripts/control_demo_workflow.py` = `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`；事实核心 `scripts/build_demo_fact_packet.py` = `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`；TASK-015 宿主测试 `tests/test_fact_packet_demo_workflow.py` = `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`。未改规格/契约草案/SQL/上游/旧测试/回执/评审/历史现场；未装依赖、未初始化 Git、未清理历史、未迁移或重签旧批次。

---

## 2. 接入实现（宿主 TASK-017-workflow-host-1.0）

- **新公开 API**：`record_simulated_initial_judgment(batch_dir, submission) -> dict`；**第九个 CLI**：
  `record-simulated-initial-judgment --batch-dir <batch> --submission-file <json>`（既有八个 CLI 保留）。
  CLI 一次读取 UTF-8 JSON 为对象后调用同一公开 API；本层保存**接收到的对象快照**，不宣称保存了外部
  提交文件的原始字节；不产生默认提交、不补事件 ID／身份／时间／assessment／reason。
- **真实核心恰调用一次**：`build_initial_judgment_record(batch_dir.name, packet, submission,
  expected_packet_sha256=<0007 已核验的 packet 规范指纹>)`；只传字符串与两个内存对象，不传 DB 路径／SQL／
  答案册／生成器／工作流；纯核心文件未被修改（哈希见上）；宿主未重写判断校验算法，也未在 `status` 中
  再次调用核心。
- **新核心从批次 start 绑定**：`HOST_BOUND_PATHS` 增加固定路径 `initial_judgment_core`
  （`scripts/build_demo_initial_judgment.py`），实测哈希进入 `bindings.host_code_sha256.initial_judgment_core`
  并随 `run_bindings` 存入 workflow；**冻结 `CONTROLLER_CODE_KEYS` 与控制器八项 `code_sha256` 协议未改**，
  未向控制器代码键插入第九项。旧批次缺该绑定或宿主代码不一致时如实拒绝（`run_bindings` 整体指纹比较）。
- **固定落盘**：`workflow/initial_judgment/` 仅含 `started.json`、`submission.json`、
  `initial_judgment.json`（核心**完整返回外层**，恰 `record`／`record_sha256`）、`artifacts.json`，
  失败时才有 `failure.json`；新协议 `TASK-017-initial-judgment-start-1.0` / `-artifacts-1.0` /
  `-failure-1.0`，`stage=initial_judgment`；既有 TASK-012/013/014/015 协议未改名。全部产物独占创建、
  UTF-8 无 BOM、明确 LF、写后读回核验；**文件字节哈希与对象规范指纹分列**。未生成 AI 草稿、未渲染判断
  页面、未改原事实 Markdown。
- **八步顺序**：① 共用恢复核验整链与上游且当前恰为合法 `0007`（完整 MATCHED 十维度 + 底稿产物）→
  ② 冻结控制器继续验证 workflow/bindings，并**显式检查 `GENERATE_AI_SUGGESTION` 真实返回
  `simulation_allowed` 严格 false** 且保留实值 → ③ 同缓冲读取 packet 与文件字节哈希并与 `0007` 初始
  读数、`artifacts`、来源绑定比较，核验数据库与三上游产物，取 submission 调用前规范指纹并做轻量预检 →
  ④ 独占建目录、保存 `started.json`（含 `at_utc` 与调用方 `occurred_at` 分列）与 `submission.json`
  并写后读回 → ⑤ 真实调用一次冻结核心，调用前／核心返回后／公开返回前按同一对象引用核验两输入指纹 →
  ⑥ 核验返回外层恰两键、record 协议/来源/原文与本次输入相符、`record_sha256` 正确、五项 `null`／两项
  `false` → ⑦ 独占保存 `initial_judgment.json`（读回严格规范相等）→ `artifacts.json`（读回）→ `0008.json`
  → ⑧ 最后一次控制器检查与数据消费之后**实读磁盘复测**本次消费的静态绑定/宿主清单、Gate2 三份 JSON 与
  数据库、筛查/复算/事实底稿产物、本层四份产物、`0001`—`0008` 全部 checkpoint，并复核两输入与核心返回未变。
- **`0008`**：`revision` 严格整数 8、`previous_file_sha256` ＝ 本次初始实读 `0007` 字节哈希、
  `operation.kind=RECORD_SIMULATED_INITIAL_JUDGMENT`、`operation` 完整内嵌 `artifacts` 及其文件指纹与固定
  相对路径；**`workflow` 与 `0007` 严格规范 JSON 等值**（不追加 `history`／`simulated_decisions`／请求／
  审批／新 phase）。合法链扩展为连续 `0001`—`0008`；`0005`／`0006`／`0007` 各自按自身 `operation` 与初始
  读数核验，不把链尾新 operation 当上游摘要。链长度上限与合法名单同步扩到 8；拒绝 `0009`、序号跳跃、
  半文件与未知项。
- **成功摘要**：保留筛查／复算／事实包摘要，新增 `initial_judgment_status=SIMULATED_INITIAL_JUDGMENT_RECORDED`
  与本层文件引用/`record_sha256`/模拟事件摘要；`completed_actions` 只增加 `SIMULATED_INITIAL_JUDGMENT`；
  `real_approvals=0`、真实批准 `null`、`next_step_allowed=false`；`ai_action_simulation_allowed` 记录冻结
  控制器**真实** `false`。未使用 `HUMAN_INITIAL_JUDGMENT_SAVED`／`AI_READY`／“主理人已初判”措辞；
  `record` 仍是冻结的 `DEV_INITIAL_JUDGMENT_VALIDATED` 协议，未改写其边界文本。
- **失败恢复**：本次真正创建本层目录后，任何失败都尽力独占保存 `failure.json`（固定协议、批次/宿主/核心
  绑定、`stage=initial_judgment`、异常类别与消息、`exception_chain`（cause/context）、严格整数目标退出码、
  观察到的产物状态）并写后读回核验；不覆盖已存在诊断；诊断保存失败时保留原始原因且不返回成功。
  共用恢复**先核验本层有效失败诊断，再解析 checkpoint 链**；核心/协议阻断→退出 1，I/O 或意外运行失败→
  退出 2；无有效失败但有未完成现场时如实拒绝、不补签；只恢复被改坏的输入不清除已保存失败事实。
- **只读 `status`**：不调用 `normalize_workbook`／`load_normalized_to_sqlite`／`screen_sqlite`／
  `verify_rule_facts`／`build_fact_packet`／`build_initial_judgment_record`；用已保存凭证、提交快照、严格
  协议、指纹与来源绑定恢复，并要求记录内嵌原文/绑定与已保存 `submission.json` 及 `0007` 一致；可调用冻结
  控制器检查动作但不写文件/事件/新诊断；`0001`—`0007` 仍按“未保存模拟初判”恢复，只有 `0008` 标记本层完成；
  在最后一次摘要读取与控制器检查之后仍实读复测本次消费的磁盘材料（含本层四份产物与 `0008`）。

---

## 3. 最终入口与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"           # 0
& $py -B -c "src = open(r'...\tests\test_initial_judgment_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_initial_judgment_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task017_run_01'                                    # 0
```

输出要点：`[PASS] G1_MAIN_INITIAL_JUDGMENT`、`[PASS] G2_PREMISE_AND_SAMPLES`、`[PASS] G3_PERSISTENCE_FAULTS`、
`[PASS] G4_LATE_CHANGE`、`[PASS] G5_BINDING_AND_PROTOCOL`、`[PASS] G6_READONLY_STATUS`、
`[PASS] G7_EVIDENCE_PROTECTION_AND_STOP`、`检查项 7：7 PASS / 0 FAIL`、
`CLI 调用 90；API 登记 20（返回 6、Blocked 14、意外 0）；实际核心调用 20；missing=0 unregistered=0`、
`0008 物理 8／可解析 7／半写 1；有效失败 5；守卫命中 0；保护比较 executed=True`、`测试失败 0`（约 7 分 34 秒）。
定点子集：`--only main|premise|persistence|late|binding|readonly|evidence|smoke`。

---

## 4. 七组检查结果与证据引用

| 组 | 结果 | 关键实测 |
| --- | --- | --- |
| G1 MAIN 正常接入 | PASS | 真实建链至 `0007`（12 条线索、`3/5/2/2`、R02 超额 `1600000` 分保留），随后以显式模拟文本保存一次并生成 `0008`；**真实核心恰调用 1 次**；两输入在调用前/后同引用指纹不变；完整返回与落盘 `initial_judgment.json` 严格规范相等；`submission.json` 快照与本次提交对象严格相等且原文保留；`record_sha256`（对象规范指纹）与 `initial_judgment_file_sha256`（文件字节哈希）**分列且不混用**；`0008` revision 严格 8、kind 正确、previous 与 `0007` 实读相符、`workflow` 与 `0007` 严格相等、真实批准 `null`、phase 未变；`status` 恢复 `0001—0008`；重复提交退出 1 且旧文件未变。证据 `probe_records/g1_main.json`。 |
| G2 前提与小样 | PASS | C03 零条可保存“暂不能判断”＋调用方原因且**未**被自动判“无问题”（`finding_ids=[]`，原文保留）；0006 早期阶段与 HOLD 批次拒绝且不建本层目录、现场不变；四个轻量预检反例（错误批次、错误 packet 指纹、真实 `HUMAN` 身份、**复用既有 Gate 事件 ID**）在建目录前拒绝且未改旧文件；一个通过轻量预检但被**真实核心**拒绝的空白 `reason` 负向：保存本层 `failure.json`（`target_exit_code=1`、`stage=initial_judgment`、完整异常链）且**无成功 `0008`**；另一个**受控 `InitialJudgmentError` 注入**（明确标注为宿主映射注入，不冒称真实核心业务失败）映射退出 2，新进程 `status` 与 CLI 均退出 2。证据 `probe_records/g2_premise_and_samples.json`。 |
| G3 有限持久化故障 | PASS | 两个独立新 C06b：`0008` **真实 writer** 半写与完整写后 sentinel。以真实独占写句柄上的**单次 write** 注入（未替换整只 writer）：写命中恰 1 次、模式 `x`、`newline="\n"`；半写场景磁盘字节与预期前半段一致；两场景新进程 `status` 均退出 2、`stage=initial_judgment`、异常链完整、旧 `0001—0007` 字节不变；完整写后抛错也未被恢复当成功（仍退出 2 且保存有效失败诊断）。证据 `probe_records/g3_persistence_faults.json`。 |
| G4 晚变更 | PASS | 4a：在写后**最后一次真实控制器动作检查**返回之后（精确观察直接调用方与次数，未硬编码全局第 N 次）仅为已消费 `fact_packet.json` 追加 LF、不改内存、不同步哈希 → **本次公开保存即拒绝**并指向该文件；撤销 wrapper 后新进程 `status` 退出 1；恢复原件后仍因有效失败事实退出 1。4b：在正常成功批次中包装**最后一次新记录摘要读取**（先返回原对象后单次更改 `initial_judgment.json`）→ 本次 `status` 即拒绝且**不写新诊断**；撤销探针并只恢复原件后 `status` 退出 0。证据 `probe_records/g4_late_change_fact_packet.json`、`g4_late_change_record.json`。 |
| G5 绑定与协议反例 | PASS | 批次 `start` 时已有 `initial_judgment_core` 宿主绑定，其哈希等于冻结初判核心实测字节哈希；操作前后静态绑定实测一致；对本轮新批次的声明副本做有限篡改（`record.source.fact_packet_sha256`、`artifacts.initial_judgment_status` 改成 `HUMAN_INITIAL_JUDGMENT_SAVED`）后 `status` 准确拒绝且不写诊断；恢复原件后 `status` 成功；真实批准未被伪造。未改真实核心/上游文件、未删有效失败事实。证据 `probe_records/g5_binding_and_protocol.json`。 |
| G6 只读恢复 | PASS | 正常 `0008` 批次在**六个真实下游函数**（`normalize_workbook`／`load_normalized_to_sqlite`／`screen_sqlite`／`verify_rule_facts`／`build_fact_packet`／`build_initial_judgment_record`）被换成计数后抛错守卫时，公开 `status` 成功且**命中全 0**；批次文件哈希集合与外置数据库字节均未变；新进程 CLI `status` 恢复 `SIMULATED_INITIAL_JUDGMENT_RECORDED`。`status` 未偷偷调用新的纯核心（本组核心调用计数为 0 增量）。证据 `probe_records/g6_readonly_status.json`。 |
| G7 证据、保护与停止点 | PASS | 90 条 CLI＋20 条 API 记录各留完整返回或完整异常+原因链与预期退出码；文件台账逐项实读存在性与 sha256、登记表与 CLI/API 原文双向一致、`missing=0`、`unregistered=0`（均为**已执行**结果并进入正式 failures）；隔离自测只删审核副本一条 registry 即失败；receiver 12／checker（receiver 启动）12／直接 checker CLI 0 分列；现场计数按 scope 分列（0008 物理 8／可解析 7／半写 1、有效失败 5、无失败恢复成功 2），未把“有文件”称为成功；未观察的子进程内部核心次数记 `null`；保护比较真实执行；停止点：全部现场无 `0009`、冻结件一致、`phase`／批准／`next_step_allowed`／AI 真实 `false` 全部正确。证据 `evidence_ledger.json`、`call_registry.json`、`scene_outcomes.json`、`probe_records/g7_protection.json`、`probe_records/g7_stop_point.json`、`isolation/isolation_result.json`。 |

---

## 5. 调用与计数（来源与 scope）

| 项 | 值 | 来源 |
| --- | --- | --- |
| CLI 调用 | 90（含九个命令，全部登记 exit code 与 stdout/stderr 原文） | `cli_logs.json`、`cli_logs\` |
| 公开 API 调用 | 20（返回 6、按预期 Blocked 14、意外 0） | `api_records.json` |
| 实际进入真实核心次数 | 20（`core_calls_observed` ＝ 各记录 `core_calls_delta` 之和 ＝ 20） | `call_consistency.json` |
| 守卫命中 | 0（六个下游函数全 0） | `probe_records/g6_readonly_status.json` |
| 台账缺失／未登记 | 0 / 0（已执行） | `evidence_ledger.json` |
| 隔离自测 | `failed_as_expected`（严格单删一条 registry） | `isolation/isolation_result.json` |
| 现场（scope＝本容器） | 批次 8；0008 物理 8／可解析 7／半写 1；有效失败 5；无失败恢复成功 2；receiver 12；checker 12；直接 checker CLI 0；故障注入 3 | `scene_outcomes.json`、`counts.json` |
| 保护比较 | 已执行（基线 124539 项、实扫 126363 文件、changed 恰为宿主与指南、missing 0、读取错误 0） | `probe_records/g7_protection.json` |

未执行的动作写 `null`（未观察的子进程内部核心次数、非本卡项），不填未测得的 0。

---

## 6. 保护比较与冻结件

本轮正确基线 `data/reviews/task016_r1_gpt_20261013_023714/source_hashes_after.json`（实际 **124539** 项、文件 SHA-256 `7d7287cf5657489c1369b0206d02c3487b2b680fcec06133c7e13d2ecd81d6ea`，与同目录 `review_result.json` 登记一致）：单次扫描 126363 文件后 **changed 恰为 `scripts/run_demo_workflow.py` 与 `docs/WORKFLOW_HOST_GUIDE.md`**、**missing=0**、读取错误 0、unexpected=[]；六个重点冻结件哈希全部一致。未沿用旧基线，未做第二次全项目扫描。

---

## 7. 过程失败尝试与修正（如实记录）

1. 0008 核验器中 `artifacts` 与实读产物的字段名不一致（`initial_judgment_file_sha256` vs `record_file_sha256`），触发 `KeyError` → 改为显式的「artifacts 字段 ↔ 实读字段」四元映射。
2. `artifacts` 一度被要求内嵌自身文件哈希（自指且不存在）→ 去掉自哈希，只核验固定相对路径；`artifacts` 文件字节哈希由 `0008.operation.artifacts_file_sha256` 承担。
3. 收尾复测误用 `gate2_paths["output_dir"]`（那是外置 SQLite 目录）拼 Gate2 JSON 路径 → 改为 `_gate2_dir(target)`。
4. `status` 中既有的「0007 最终复测」用 `chain["current_file_sha256"]`，在链尾变成 `0008` 时必然失败 → 改为按链中 revision=7 的条目取初始哈希；新增的 0008 复测同样按 revision=8 条目取。
5. `status` 的 0008 收尾一度写成「两次读回结果自比（缓存同自身比较）」→ 改为与 `0008` 声明/内嵌副本比较，并补 record 规范指纹与失败诊断存在性核验。
6. 测试侧：轻量预检「事件 ID 复用」探针最初写死了一个并不存在的 Gate 事件 ID（因此未被拒绝、后续断言连锁失败）→ 改为从 `0007.workflow.state.simulated_decisions` 读取真实事件 ID。
7. 测试侧：绑定组误读批次级 `batch_manifest.json`（接收器清单）取 `bindings` → 改为读 `workflow/host_manifest.json`（宿主清单）。

过程容器：`task017_smoke1`、`task017_smoke2`、`task017_smoke3`（接线冒烟）、`task017_smoke_a`（G1）、`task017_smoke_premise`／`premise2`（G2）、`task017_smoke_persistence`（G3）、`task017_smoke_late`（G4）、`task017_smoke_binding`（异常）／`binding2`（G5）、`task017_smoke_readonly`（G6）、`task017_diag1`（诊断）均保留未回写。

---

## 8. 产物路径

- 最终证据容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task017_run_01`（246 文件：`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`api_records.json`／`call_registry.json`／`evidence_ledger.json`／`call_consistency.json`／`scene_outcomes.json`；`cli_logs\` 180、`api_records\` 20、`probe_records\` 9、`isolation\` 1、`submissions\` 4、`decisions\` 23）
- 批次父目录：`D:\harness work\audit_sa_project\data\batches\task017_run_01`（410 文件；含 `main_01`、`g2_c03`、`g2_early`、`g2_hold`、`g2_binding`、`g2_error_injection`、`g3_partial`、`g3_throw`、`g4_late_fact`、`g4_late_record`、`g5_binding`、`g6_readonly` 等现场）
- 外置 SQLite 父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task017_run_01`（11 文件）

---

## 9. 未执行与边界

- 未执行：TASK-002—016 历史整套入口、冻结 TASK-013/014/015 宿主测试、TASK-016 完整纯核心七组、事实核心 21 组；未重跑 MAIN 之外的完整历史链。
- 未建 `0009`、未开放 AI/LLM/网络/UI/ERP、未形成终判、未建立正式契约或真实 Gate；未修改冻结事实包及其“尚未保存人类判断”说明。
- 边界：**保存模拟初判不等于真实人类独立初判已保存**，不表示身份认证、审计完成或真实 Gate 批准；`record` 仍为冻结 `VALIDATED` 协议；本地哈希只证明字节一致。`status` 不调用六个下游核心，也不为验证已保存记录再次运行纯核心。
- 未解决项：无。业务口径或身份/来源问题交 GPT/人类，不自行改规格；执行端已完成本卡，不做下一任务。
