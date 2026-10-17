# TASK-017-R1 执行回执（status 最后新层读取收尾与真实核心观察）

任务：按唯一权威细则 `docs/tasks/TASK-017-R1.md` 修两项阻断——B1（`status` 最后一次新层读取之后必须实读复测）、B2（分清宿主 API 与真实纯核心、落实真实入参与完整核心返回的观察）。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：两项阻断均已修复并有定点实测证据；本轮最终定点入口在**全新容器**一次执行，退出 **0**、**2/2 检查 PASS、failures=[]**。停在开发态 `0008` / `SIMULATED_INITIAL_JUDGMENT_RECORDED`；真实批准 `null`、`next_step_allowed=false`、AI 未开放；未建 `0009`、不做下一任务。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `scripts\run_demo_workflow.py` | `e65b8b3ee604f66808f88176e0ad870de00a479a07e6a2cc989590ddd16232c5` | `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`（493659 字节；实现版本补丁升 `TASK-017-workflow-host-1.1`） |
| `tests\test_initial_judgment_demo_workflow.py` | `ef8c0eccb191b7c84c70694479f942bac553e5b52e3b17511cc4993fef6611a3` | `c5b31cd798dbbb72759ae94ec65217e28ff86c453947c59cf074ed1dfa651c05`（105670 字节） |
| `docs\WORKFLOW_HOST_GUIDE.md` | `856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8` | **本轮未改**（本卡标注该文件非必改；为保持保护读数与本轮最终容器一致，未在扫描后改动） |
| `docs\EXEC_REPORT_017_R1.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**重点冻结件实测未改**：初判纯核心 `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`；纯核心测试 `c0ef730e59ad78f54d7d60014289ea56ca7e79c764f9afba515c1c77449b62f3`；纯核心指南 `2bbaa876ae7a76175f3462d9395b7bbc8e4bec5b1631030ff3fe32142d0286f5`；控制器 `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`；事实核心 `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`；TASK-015 宿主测试 `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`。未回写旧回执/评审/卡、未迁移或补签历史批次、未装依赖、未初始化 Git。

---

## 2. B1：`status` 最后一次新层读取之后实读复测（已关闭）

**原因确认**：`status` 先调 `_verify_initial_judgment_tail`，再调 `_read_initial_judgment_outputs` 取 `initial_outputs_final`，其后只用该次读取返回的旧缓冲比较；剩余收尾只覆盖上游/DB/绑定/旧链，**没有在本层最后一次读取之后重新实读新层四文件**。

**定点修复**（`scripts/run_demo_workflow.py`，`inspect_dev_batch` 收尾）：在本层摘要/对象读取与全部必要控制器检查、上游收尾（事实底稿/复算/筛查/Gate2/DB/宿主清单/`0001`—`0008`）、静态绑定复测**全部完成之后**、构造返回值之前，增加本层最终实读复测：

1. `_verify_initial_judgment_tail`（四文件字节 + 数据库 + 目录白名单 + 无 `failure.json`）；
2. 直接 `file_sha256` 实读 `started/submission/initial_judgment/artifacts` 四文件，与 `0008` 的**初始核验读数**逐项比较（新增 `submission_canonical_sha256`、`record_sha256` 进入该预期集）；
3. 重新 `_read_json` 实读 `initial_judgment.json`，核验外层恰 `record`/`record_sha256`、`record` 规范指纹等于 `0008.operation.record_sha256`；
4. 重新实读 `artifacts.json` 与 `0008.operation.artifacts` 严格规范相等；重新实读 `submission.json` 规范指纹等于初始预期，并交叉核对 `started.json` 记录的提交指纹；
5. 实读 `0008` 字节与链中初始读数比较；确认无 `failure.json`；
6. **再走一次字节级确认**（覆盖“最后一次对象读取返回之后”的改动点）。

预期只来自 `0008` 初始核验读数或本次 writer 返回，**不用两次后来读数自比、不用新读数替换初始预期、不把检查推到下一次 status**；只读 `status` 不写失败诊断。保存 API 与失败恢复语义未改。

**定点实测**（新 C06b 批次，先无注入观察真实读取位置）：

| 目标文件 | 注入位置（真实调用位置） | 本次 status | 撤销 wrapper 后 | 恢复原件后 | 写诊断 |
| --- | --- | --- | --- | --- | --- |
| `started.json` | 第 2 次（= 最后一次）新层输出读取返回原对象之后 | `WorkflowHostBlocked`／退出 1，消息指向目标文件 | 退出 1 | 退出 0 | 否 |
| `submission.json` | 同上 | 同上 | 退出 1 | 退出 0 | 否 |
| `initial_judgment.json` | 同上 | 同上 | 退出 1 | 退出 0 | 否 |
| `artifacts.json` | 同上 | 同上 | 退出 1 | 退出 0 | 否 |

无注入观察记录：`_read_initial_judgment_outputs` 在该次 status 中恰被调用 2 次（第 1 次来自 `_verify_initial_judgment_operation`、第 2 次为 `inspect_dev_batch` 的摘要读取，`last_index=2`），四场景均只在该第 2 次返回原对象之后注入，未在早期读取注入、未硬编码全局第 N 次。每次注入前/后字节哈希、命中次数、完整异常与两次 CLI 原文均留痕；原 `0001`—`0008` 与非故意注入文件在恢复后不变。证据：`probe_records/r1_status_read_sites.json`、`probe_records/r1_late_new_layer_files.json`、`api_records/r1_late_*.exception.json`、`cli_logs/r1_late_*`。

---

## 3. B2：真实纯核心观察与分列（已关闭）

**原因确认**：原 `core_recording` 包裹的是 `record_api` 收到的**宿主函数**（`record_simulated_initial_judgment`／`inspect_dev_batch` 等），因此只读 `status`、前提拒绝也被记作“核心执行”；G1 用两个未参与调用的 `deepcopy` 作前后指纹，且“完整核心返回对比”只是磁盘/摘要互比。

**修复（测试层，不改冻结核心）**：

- 新增 `RealCoreObserver`：在**宿主实际使用的模块对象** `HOST.INITIAL_JUDGMENT_MODULE` 上包裹真正的 `build_initial_judgment_record`，全程激活；每次调用记录真实入参引用（`packet`/`submission`）、`expected_packet_sha256`、调用前与核心返回后的规范指纹、`outcome`、完整返回或完整 traceback。观察器本身不写文件，完整返回由测试层返回后单份另存。
- 计数分列：**宿主公开 API 登记数**（每次调用均登记，含前提/重复拒绝与只读 status）与**真实纯核心次数**（观察器）分列，二者**不要求相等**；每条宿主 API 记录带该次真实核心增量 `core_calls_delta`；子进程内部核心次数记 `null`。
- G1 改为使用**实际传入核心的对象引用**：三时点（调用前／核心返回后／公开保存返回后）规范指纹一致；并把观察到的**完整真实核心返回单份保存**（`core_returns/main_call1_return.json`）与落盘 `initial_judgment.json` 严格规范比对。

**定点实测（`task017r1_run_02`）**：

| 宿主 API | 真实核心增量 |
| --- | --- |
| `r1_save`（正常保存） | **1** |
| `r1_repeat`（重复提交拒绝） | 0 |
| `r1_status_baseline`（无注入只读 status） | 0 |
| `r1_late_{started,submission,initial_judgment,artifacts}.json`（四个 LF 反例） | 各 0 |
| `r1_status_guard`（六下游守卫下只读 status） | 0 |
| `r1_stub_error_mapping`（替身映射，纯映射函数核对，不建批次） | 0 |

合计：宿主 API 登记 **9**、真实纯核心调用 **1**、各 API 增量之和 **1**（一致）；未观察的子进程内部核心次数 `null`。正常保存的三时点指纹相等（`packet=93bed3ad…ca30`、`submission=96d579ec…1fe3`），完整真实返回与落盘严格等值；`0008.workflow` 与 `0007` 严格相等、前驱哈希正确、真实批准 `null`、`next_step_allowed=false`、AI 动作真实 `false`；`initial_judgment_core` 绑定自 `start` 存在且实测一致；一次重复提交被拒绝且旧文件不变。证据：`core_observations.json`、`core_returns/r1_save_call1_return.json`、`probe_records/r1_summary.json`、`probe_records/r1_stub_mapping.json`。

**守卫**：六个真实下游函数计数抛错守卫下 `status` 成功、命中全 0、批次文件与外置 DB 字节不变，该宿主 API 的真实核心增量为 0（未为了凑等式执行核心）。证据 `probe_records/r1_readonly_guard.json`。

---

## 4. 最终定点入口与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"            # 0
& $py -B -c "src = open(r'...\tests\test_initial_judgment_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_initial_judgment_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task017r1_run_02' --only r1                     # 0
```

输出要点：`[PASS] R1_STATUS_TAIL_AND_REAL_CORE_OBSERVATION`、`[PASS] R1_EVIDENCE_PROTECTION_AND_STOP`、`检查项 2：2 PASS / 0 FAIL`、`CLI 调用 15；宿主 API 登记 9（返回 3、预期/意外异常 5（预期协议阻断 5、意外 0））；真实纯核心调用 1；子进程内部核心 null；missing=0 unregistered=0`、`0008 物理 1／可解析 1／半写 0；有效失败 0；守卫命中 0；保护比较 executed=True`、`测试失败 0`（约 3 分 55 秒）。

**额外连带确认（超出本卡最低要求，如实登记）**：本轮另在过程容器 `task017r1_allcheck2` 运行了一次**保留的完整七组入口**，确认共享改动未破坏原入口：7/7 PASS、退出 0，宿主 API 20、真实纯核心 9（与各次真实保存/核心业务拒绝一致）、`missing=0`、守卫命中 0。该容器为过程容器，不作为本卡最终交付；卡要求的“仅一个新 C06b 批次”仍由 `task017r1_run_02` 满足（该容器只有 1 个批次）。

---

## 5. 调用与计数（来源与 scope）

| 项 | 值 | 来源 |
| --- | --- | --- |
| CLI 调用 | 15（含 `status`／`record-simulated-initial-judgment` 等） | `cli_logs.json`、`cli_logs\`（30 文件） |
| 宿主公开 API 登记 | 9（返回 3、预期协议阻断 5、意外 0；含 1 条纯映射核对） | `api_records.json` |
| 真实纯核心调用（本定点） | **1**（仅正常保存；status/拒绝/守卫/替身均为 0） | `core_observations.json`、`core_returns\` |
| 子进程内部核心次数 | `null`（未观察，不推定） | `counts.json` |
| 台账缺失／未登记 | 0 / 0（已执行，进入正式 failures） | `evidence_ledger.json` |
| 隔离自测 | `failed_as_expected`（严格单删一条 registry） | `isolation/isolation_result.json` |
| 现场（scope＝本定点容器，仅 1 个批次） | 批次 1；0008 物理 1／可解析 1／半写 0；有效失败 0；无失败恢复成功 1；receiver 1；checker 1；直接 checker CLI 0 | `scene_outcomes.json` |
| 保护比较 | 已执行（基线 126441 项、实扫 127674 文件、changed 恰为宿主与本任务测试、missing 0、读取错误 0） | `probe_records/r1_protection.json` |

---

## 6. 保护比较与冻结件

正确基线 `data/reviews/task017_gpt_20261013_031915/source_hashes_after.json`（实际 **126441** 项、文件 SHA-256 `8b07d991b25326d322ffcfc1ee291d295eb37cafb303d7d4ba5020cd553aea2c`，与同目录 `review_result.json` 登记一致）：单次扫描 127674 文件后 **changed 恰为 `scripts/run_demo_workflow.py` 与 `tests/test_initial_judgment_demo_workflow.py`**（本卡允许的三个文件中的两个；指南本轮未改）、**missing=0**、读取错误 0、unexpected=[]；六个重点冻结件哈希全部一致；无 `0009`、真实批准 `null`、`next_step_allowed=false`、AI 真实 `false`。

---

## 7. 辅助记录更正（不阻断，按卡 §5）

- 原回执“20 实际核心 = 20 宿主 API”**作废**：那 20 是宿主公开 API 包装次数。其真实含义是「宿主 API 20 条」；本轮定点观察为「宿主 API 9、真实纯核心 1」，原完整入口复跑为「宿主 API 20、真实纯核心 9」。新回执不再声称二者相等。
- 原 G3 `old_unchanged` 变量恒 `true`（只查旧 checkpoint 存在、未比字节）属实现瑕疵；GPT 已从原 CLI 初始输出补核两场景 14 份旧 checkpoint，本轮不重跑 writer，新回执不把它称为“实测字节不变”。
- 原 `scenes_total=8` 实际只数物理 `0008`（该容器批次为 12）；`recovered_success_total=2` 只累加两个正常流程。本轮定点按真实 scope 导出（批次 1、物理/可解析 `0008` 各 1、失败 0、恢复成功 1），未重做完整场景计数。
- 输出措辞更正：不再把预期 `WorkflowHostError` 统称 Blocked，改为「返回／预期协议阻断／意外失败」分列（本次定点：返回 3、预期协议阻断 5、意外 0）。原替身映射与真实核心调用**分列**，未执行真实核心不填 1。

---

## 8. 过程失败尝试与修正（如实记录）

1. 新增本层收尾预期集缺少 `submission_canonical_sha256`/`record_sha256`，导致无注入 `status` 与守卫下 `status` 报 `KeyError`（`WorkflowHostError`）→ 补齐预期键。
2. 替身映射首版直接对同一（已有 `0008`）批次注入替身，被前置拒绝挡在核心之前，未验证映射 → 改为对 `_map_upstream_exception` 做纯映射核对（不建批次、不调用核心），并明确原完整映射路径已在 `task017_run_01` 实际执行、本轮不重复。
3. 映射条目未落盘导致台账出现“未登记进文件台账” → 该条目改为单份落盘并登记引用。
4. 观察器每次 `start()` 会清空计数，导致保留入口只报 1 次真实核心 → 改为全程激活 + 以索引窗口取每次调用的观察；原完整入口复跑后真实核心为 9。
5. R1 允许变化集合字面量写成 `{{...}}`（集合套集合）致 `TypeError` → 改为普通集合字面量。

过程容器：`task017r1_smoke1`…`smoke5`（定点接线与断言修正）、`task017r1_run_01`（收尾预期键修复前）、`task017r1_allcheck`／`allcheck2`（保留入口连带确认）、`task017_diag1`（早前诊断）。均保留未回写。

---

## 9. 产物路径

- 最终定点容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task017r1_run_02`（60 文件：`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`api_records.json`／`call_registry.json`／`evidence_ledger.json`／`core_observations.json`／`scene_outcomes.json`；`cli_logs\` 30、`api_records\` 9、`probe_records\` 7、`core_returns\` 1、`submissions\` 1、`decisions\` 2、`isolation\` 1）
- 批次父目录：`D:\harness work\audit_sa_project\data\batches\task017r1_run_02`（37 文件；仅 `r1_c06b` 一个批次，`0001`—`0008` 与 `workflow/initial_judgment/` 四份产物）
- 外置 SQLite 父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task017r1_run_02`（1 文件）

---

## 10. 未执行与边界

- 未重跑完整七组作为本卡最终入口（另做一次保留入口连带确认，见 §4）、未重跑 MAIN/零条建链、未重做持久化两场景、未跑上游或 TASK-002—016 历史任务；保存操作的晚变更与 `0008` 半写/完整后 sentinel 路径本轮**未重跑**（GPT 已读原现场并核对），仅保留引用。
- 未建 `0009`、未开放 AI/LLM/网络/UI/ERP、未形成终判、未建立正式契约或真实 Gate；未修改冻结纯核心/控制器/事实核心与历史现场。
- 边界：**保存模拟初判不等于真实人类独立初判已保存**，不表示身份认证、审计完成或真实批准；`status` 仍为只读、不调用六个下游核心。B1 只承诺明确观察点，不追求抵御任意时点并发篡改。
- 未解决项：无。业务口径或身份/来源问题交 GPT/人类，不自行改规格；执行端已完成本卡，不做下一任务。
