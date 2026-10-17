# TASK-015-R1 执行回执（修复事实底稿构建收尾漏验 Gate2 磁盘文件）

任务：按唯一权威细则 `docs/tasks/TASK-015-R1.md` 修复 B1：`build_dev_fact_packet` 在最后一次必要控制器动作检查之后，未实读 Gate2 `normalized.json`／`load_report.json`／`artifacts.json` 与数据库字节，导致磁盘变化仍返回 `READY`。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：B1 已关闭并有定点实测证据（三个目标文件各自独立批次复现）；本轮定点入口退出 **0**、**1/1 检查 PASS、failures=[]**；未注入正常对照批次公开构建与新进程 `status` 均成功；停在开发态 `0007` / `FACT_PACKET_RECORDED`。

---

## 1. 起点与写后哈希

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `scripts\run_demo_workflow.py` | `707cd16ecf9ebeefba2e459f3e468ae3379459adc5cbf426bfb394173eedb75d` | `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a` |
| `tests\test_fact_packet_demo_workflow.py` | `5f7dacfa07f54587dc835a0e5462470a6638178b5cb642c01af55d491cad9c0d` | `3f60cfff088d289358adcb24a4f85fa61787d8245399c921f46f48cc7991af26` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8` | **未改**（`ed4f13be…07b8`；本卡该文件非必改） |
| `docs\EXEC_REPORT_015_R1.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

实现版本由 `TASK-015-workflow-host-1.0` 补丁升为 **`TASK-015-workflow-host-1.1`**（必要补丁升级：宿主代码绑定哈希变化，旧批次按既有规则如实拒绝，全部演示从最终代码创建新批次）。核心接口、八个 CLI、既有协议版本、`workflow` 与 `0006` 相等、真实批准 `null`、`next_step_allowed=false` 均不变。

**关键冻结件核对（实施前后一致）**：

| 冻结件 | SHA-256 |
| --- | --- |
| `scripts/build_demo_fact_packet.py` | `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62` |
| `tests/test_build_demo_fact_packet.py` | `46d426e7c262f3b5c773ba6717e5b3e002c34783d11d24a5bd3c43b80effeb36` |
| `docs/FACT_PACKET_GUIDE.md` | `48c051be9bfca3659560c73e4693892ecd1a72629fba7401698eb87f8657ff9d` |
| `scripts/crosscheck_demo_rules.py` | `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2` |
| `tests/test_crosscheck_demo_workflow.py` | `f34533833d0fa0ac41274f1c847f933ecaf8110de65e35acc43c8bf12393cf43` |
| `tests/test_screen_demo_workflow.py` | `27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca` |

原 TASK-015 卡/回执、本卡/验收记录、六个关键冻结件、上游/SQL/规格/契约草案均未回写；未装依赖、未初始化 Git、未迁移凭证、未清理历史。

---

## 2. B1 关闭证据

**实现（`build_dev_fact_packet` 收尾）**：

- Gate2 三份 JSON 改为**实读磁盘**后与**操作开始时已绑定的同缓冲读数**比较：`gate2_normalized_file_sha256` ← `file_sha256(_gate2_dir(target)/normalized.json)`、`gate2_load_report_file_sha256` ← `load_report.json`、`gate2_artifacts_file_sha256` ← `artifacts.json`，数据库字节同样实读。不再是“旧 `gate2_outputs` 缓存同其自身相等”。
- 追加对象级复测：收尾再次 `_read_gate2_outputs`，三份对象与本次消费对象规范 JSON 相等、三份文件字节哈希与本次消费读数一致。
- 预期来源仍是操作开始时的同缓冲读数与已核验链读数（`screen_expected`／`crosscheck_expected`），不由末尾新读数产生新预期；不新造 I/O 框架，`status` 未退化，`0005`／`0006` 各自的核验读数与链尾分流未被改动。
- Gate2 磁盘变化 → `WorkflowHostBlocked`／退出 1 并指出目标文件；已创建本层现场后如实保存 `fact_packet/failure.json`（`target_exit_code=1`、`stage=fact_packet`）；即使 `0007` 已完整写入，恢复仍尊重有效失败诊断。

**实测（`data\workflow_host_tests\task015r1_run_01`）**：每个目标文件用**独立本轮新批次**复现，只包装真实 `check_dev_action`（先调用原实现；仅在其直接调用方为 `build_dev_fact_packet` 且**第二次**（写后最后一次）真实返回之后，给目标文件追加一个 LF，原返回对象原样交回，不同步任何哈希）：

| 目标文件 | 直接动作检查次数 | 注入命中 | 控制器原返回 | 文件 SHA 前 → 后 | 本次构建 | 失败诊断 | 撤销 wrapper 后 CLI | 只恢复原件后 CLI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `workflow/gate2/normalized.json` | 2 | 1 | 严格 `true` | `ca0fe538…d367` → `eb1611b2…d2bd` | `WorkflowHostBlocked`／1，消息指向该文件 | `target_exit_code=1`、`stage=fact_packet` | 退出 **1** | 退出 **1**（有效失败事实未被清除） |
| `workflow/gate2/load_report.json` | 2 | 1 | 严格 `true` | `eff92eae…2f25` → `7945d5f4…ea9d` | 同上 | 同上 | 退出 **1** | 退出 **1** |
| `workflow/gate2/artifacts.json` | 2 | 1 | 严格 `true` | `6f64579a…4a83` → `65a2d8ea…a76d` | 同上 | 同上 | 退出 **1** | 退出 **1** |

三项均满足卡 §2 要求：**本次即拒绝**（不是下一次 `status` 才发现）、消息指出相应文件、准确 `fact_packet` 阶段与退出 1。三份探针记录见 `probe_records/r1_late_{normalized,load_report,artifacts}.json`（含完整 API 记录引用、注入参数、前后哈希、控制器原返回与两段 CLI 原文）。

**对照与连带复核**：

- 未注入的正常新批次 `r1_normal_control`：公开构建成功（核心调用 1 次）、新进程 `status` 退出 **0**、`fact_packet_status=FACT_PACKET_RECORDED`。
- 五个真实下游函数（`normalize_workbook`／`load_normalized_to_sqlite`／`screen_sqlite`／`verify_rule_facts`／`build_fact_packet`）被替换为计数后抛错守卫时，公开 `inspect_dev_batch` 仍成功、命中计数全 **0**。
- 旧 `0001`—`0006` checkpoint 与非故意注入文件的前后哈希不变（`old_checkpoints_unchanged=true`）。

---

## 3. 实际命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"       # 0
& $py -B -c "src = open(r'...\tests\test_fact_packet_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_fact_packet_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task015r1_run_01' --only late-controller      # 0（1/1 PASS）
& $py -B '...\tests\test_fact_packet_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task015r1_run_02' --only smoke              # 0（G1＋G2 两项 PASS）
```

`--only smoke` 仅用于确认 B1 改动未破坏正常字段路径（MAIN 建链至 `0007`、Markdown 字节精确相等、`0007` 形状／`workflow` 相等）与小样到达 `0007`；**未按卡 §3 之外重跑八组、MAIN 之外的完整入口、事实核心 21 组或 TASK-002—014 历史入口**。

---

## 4. 计数与标签更正（非阻断项）

原交付两项计数标签有误，本轮按卡 §4 在获准修改测试时更正为清晰分列（`scene_outcomes.json` 与 `counts.json`）：

- `crosscheck_matched_reports_total`（复算 MATCHED 报告）与 `packet_ready_total`（事实包 READY）**分开**；旧字段 `matched_reports_total` 现等同复算 MATCHED 计数，不再把 packet READY 称为 MATCHED 报告。
- `voucher_0007_physical_total`（物理文件）／`voucher_0007_parseable_total`（可解析）／`voucher_0007_half_written_total`（半写不可解析）／`success_vouchers_0007_total`（可解析或无失败且**经恢复核验**的成功凭证）／`fact_packet_failure_scenes`（有效失败）分列，保留各自 scope 说明。
- 本轮定点容器不含八组现场，上述总体计数由 `--only all` 容器导出；定点容器只导出本组记录（CLI 31 条、API 5 条、missing 0／unregistered 0）。

---

## 5. 保护比较与冻结哈希

保护基线 `data/reviews/task015_gpt_20261013_001516/source_hashes_after.json`（实际文件读数 **121959** 项，文件 SHA-256 `1b8f7f70e4c941529fe8ab49351de9de86a3a98c08985885226b657ff88ccdcc`）：单次扫描 122840 文件后 changed **恰为** `scripts/run_demo_workflow.py` 与 `tests/test_fact_packet_demo_workflow.py`（本卡授权两项）、**missing=0**、unexpected=[]；指南未变。六个关键冻结件哈希全部一致，原 TASK-015 卡与既有评审/回执未回写。

---

## 6. 过程失败尝试与修正（如实记录）

1. 宿主首次改动直接使用 `gate2_paths["normalized_path"]`（`_gate2_paths` 只返回数据库相关路径）→ `KeyError`；改为由 `_gate2_dir(target)` 组合固定文件名。
2. 定点探针首版按“第 2 次 `check_dev_action`”注入 → 实际第 2 次属于 `_load_checkpoint_chain` 的链核验（一次 build 共 15 次控制器调用，直接构建动作只在第 7 与第 15 次），导致注入落在步骤 3 之前并以 `0003.artifacts_file_sha256` 名义阻断；改为按“直接调用方为 `build_dev_fact_packet` 且动作等于 `SCREEN_AND_BUILD_FACTS`”计数，注入点落在写后最后一次真实动作检查之后。
3. 探针脚本首版在 `start` 之前创建批次目录、把决定文件写到不存在的目录、未清理同名 SQLite 父目录 → 序列失败；逐一修正后复跑。
4. 测试脚本 `counts` 初始化缺新字段、`scene_records` 未带 `crosscheck.matched` → 补齐后再跑定点组。

本轮一次失败留痕：`task015r1_probe1`（注入点错误，落在链核验）、`task015r1_count`（控制器调用计数诊断）、`task015r1_probe2`（注入点修正后三目标全绿，作为 B1 主要证据）均保留未回写。

---

## 7. 三条完整产物绝对路径

- 定点容器（B1 主证据）：`D:\harness work\audit_sa_project\data\workflow_host_tests\task015r1_run_01`（116 文件：`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`api_records.json`／`call_registry.json`／`evidence_ledger.json`／`scene_outcomes.json`／`probe_records\` 含三份 `r1_late_*` 与汇总）
- 定点批次父目录：`D:\harness work\audit_sa_project\data\batches\task015r1_run_01`（131 文件；含 `r1_late_normalized`／`r1_late_load_report`／`r1_late_artifacts` 三个失败现场与 `r1_normal_control` 成功现场）
- 定点 SQLite 父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task015r1_run_01`（4 文件）

连带复核容器：`data\workflow_host_tests\task015r1_run_02`（`--only smoke`，G1＋G2 PASS）。

---

## 8. 未执行与边界

- 按卡 §3 未重跑完整八组、MAIN 之外的完整入口、事实核心 21 组、TASK-002—014 历史入口；`0007` 半写/完整后 sentinel 的真实 writer 方法与正常场景已有 GPT 实际通过证据，**本轮未重跑**（B1 修复未触及该路径）。
- 未建 `0008`、未保存人类判断或 AI 建议、未建立正式契约或真实 Gate、未实施后续任务。
- 边界：本地哈希只证明字节一致；不声称抵御任意时点并发篡改。`0007` 只表示事实底稿已持久化。
- 未解决项：无。若后续需要改冻结核心或业务口径，按卡保存现场交回 GPT/人类。
