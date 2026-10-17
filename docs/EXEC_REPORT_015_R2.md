# TASK-015-R2 执行回执（补齐定点验收入口的证据收尾）

任务：按唯一权威细则 `docs/tasks/TASK-015-R2.md` 修复 late-controller 定点入口的证据收尾（E1）：登记表/文件台账/现场计数/保护比较必须真实执行并进入正式判定，不得输出未执行的默认零。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：E1 已关闭。**宿主冻结未改**；本轮最终定点入口退出 **0**、**2/2 检查 PASS、failures=[]**，且 evidence/protection 收尾真实执行（非默认零）。

---

## 1. 起点与写后哈希

| 文件 | 起点 | 写后 |
| --- | --- | --- |
| `tests\test_fact_packet_demo_workflow.py` | `3f60cfff088d289358adcb24a4f85fa61787d8245399c921f46f48cc7991af26` | `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e` |
| `scripts\run_demo_workflow.py` | `67788bd0…f35a`（本卡冻结） | **未改** `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `ed4f13be…07b8`（本卡冻结） | **未改** `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8` |
| `docs\EXEC_REPORT_015_R2.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**冻结件核对（本轮实测）**：`scripts/build_demo_fact_packet.py` `f4998d92…8b62`、`tests/test_build_demo_fact_packet.py` `46d426e7…eb36`、`docs/FACT_PACKET_GUIDE.md` `48c051be…ff9d`、`scripts/crosscheck_demo_rules.py` `8fe75bfe…3ad2`、`tests/test_crosscheck_demo_workflow.py` `f3453383…cf43`、`tests/test_screen_demo_workflow.py` `27c432db…8eca` 均一致。原 TASK-015 卡/回执、R1 卡/回执、两份验收记录、GPT 现场一律只读，未补写缺失登记以追认旧入口。

---

## 2. E1 关闭证据（late-controller 真实收尾）

新增小型 `finalize_evidence(mode, scenes)`，在 `--only late-controller` **成功返回前**真实执行并落盘：

1. **调用登记与文件台账**：本次收集的 `call_registry` 独占保存为 `call_registry.json`；CLI/API 记录保存；文件台账 `evidence_ledger.json` 逐项实读核对存在性与 sha256；登记表与 CLI/API 记录**双向一致**（记录未登记进台账、调用未登记进登记表、登记表多余条目、未登记 CLI 原文、CLI/API 文件数与记录数不符）；异常文件含真实 `traceback`（取自 `exception.__traceback__`）与完整链。实测 **missing=0、unregistered=0**，均为**已执行**结果。
2. **隔离自测（有限）**：只从审核副本 `isolation/evidence_ledger_minus_one.json` 删除一条权威登记（文件台账与真实文件不动），真实 audit helper 判失败；原件仍通过。实测去掉 `cli:r1_late_normalized_start／stdout_path` → `调用未登记进权威登记表：cli:r1_late_normalized_start`；未再建业务链。
3. **现场计数（四个现场，从磁盘导出并落盘 `scene_outcomes.json`）**：正常对照 1、晚变更失败 3；复算 MATCHED **4**；底稿 READY 报告 **4**；`0007` 物理 **4**／可解析 **4**；带失败诊断 **3**；无失败且恢复成功 **1**；半写 **0**。明确记录：有 READY 报告/完整 `0007` 不等于整个公开操作成功。计数语句已修（物理用 `is_file`、可解析另计、MATCHED 从真实 `crosscheck_report` 读取、保留 `batch` 标识），不再出现 `KeyError: 'batch'`。
4. **receiver/checker 逐批核对**：`host_manifest.receive` 与 `receive_invocation.json` 命令/退出码一致；`checker_invocation` 的 `report`/`stdout_log`/`stderr_log` 逐项实读 `exists`+`sha256`。实测 receiver 启动 **4**、receiver 内 checker started 且退出 0 **4**；直接 checker CLI **0**（与内部启动分列）。
5. **正常对照（新批次 r1_normal_control）**：真实核心**恰 1 次**；完整真实返回单份保存 `core_returns/r1_normal_control_build_fact_packet_return.json` 并与落盘 `fact_packet.json` **严格规范 JSON 相等**；`packet_sha256`（核心返回）＝磁盘 packet 规范指纹；Markdown 磁盘字节**精确等于**返回字符串 UTF-8 字节；三输入在**调用前／核心返回后／公开调用完成后**三时点指纹一致（进入断言）。进程内核心计数注明范围：`build_fact_packet_inprocess=1` 只覆盖本次实际包装的正常对照调用，反例的进程内核心调用未做外部观察，故不称“全部进程内调用总数”；子进程内部次数为 **null**（未观察，不推定为 0）。
6. **操作前文件与停止点**：三反例逐项核对——注入期间**只有故意注入的目标文件**变化（`injected_period_changed_files` 恰为目标），恢复后**全部操作前文件不变**（`restored_period_changed_files=[]`），新 `0007` 与本层产物不属于操作前文件、不误报新增；`0001`—`0006` 始终不变。全部现场**无 0008**；成功对照 `0007` `revision=7`（严格整数）、`operation.kind=BUILD_FACT_PACKET`、`previous_file_sha256` 与 `0006` 实读哈希相符、`workflow` 与 `0006` 严格相等、真实批准 `null`、`next_step_allowed=false`。
7. **保护比较（本轮正确基线）**：`data/reviews/task015_r1_gpt_20261013_004706/source_hashes_after.json`（实际 **123108** 项，文件 SHA `a4a0e9b56be3baeba72a488e871466b4bc08cc5c62430c6245f38bfdfd95c48b`）：单次扫描 **123618** 文件后 changed **恰为 `tests/test_fact_packet_demo_workflow.py`**、**missing=0**、unexpected=[]、读取错误 0；宿主/指南/六件冻结哈希另核对一致。未沿用旧 118788 项基线。扫描与比较结果落盘 `protected_scan.json`、`probe_records/r2_protection.json`。

收尾产物（`data\workflow_host_tests\task015r2_run_03`）：`call_registry.json`、`evidence_ledger.json`、`scene_outcomes.json`、`protected_scan.json`、`isolation/isolation_result.json`、`probe_records/r2_protection.json`、`probe_records/r2_stop_point.json`、`probe_records/r2_normal_control.json`、`summary.json`、`counts.json`、`checks.json`、`cli_logs.json`、`api_records.json` —— 均**实际存在**（已读回）。

---

## 3. 实际命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\tests\test_fact_packet_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0
& $py -B '...\tests\test_fact_packet_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task015r2_run_03' --only late-controller       # 0（2/2 PASS）
```

输出要点：`[PASS] R1_LATE_CONTROLLER_GATE2_DISK_RECHECK`、`[PASS] R2_EVIDENCE_FINALIZER`、`定点模式 only=late-controller：2 项检查、0 项失败；missing=0 unregistered=0`。
按卡 §4 未再次运行 MAIN、smoke、完整八组、持久化故障组、事实核心 21 组或 TASK-002—014 历史入口；`0007` 半写/完整后 sentinel 的真实 writer 方法宿主未变，**本轮只保留证据引用、未重跑**。其他模式（b1/g4/late/smoke）改为明确声明未执行证据收尾与保护比较，`missing/unregistered` 写 **null**、`not_executed` 列明，不再填未测得的 0。

---

## 4. 公开调用与引用计数（来源与 scope）

| 项 | 值 | 来源 |
| --- | --- | --- |
| CLI 调用 | 31（`start` 4／`record-simulated-decision` 4／`prepare-gate2` 4／`record-simulated-gate2-decision` 4／`screen-rules` 4／`crosscheck-rules` 4／`status` 7） | `cli_logs.json` 与 `cli_logs/` 原文双向核对 |
| 公开 API 调用 | 5（`build_dev_fact_packet` 4、`inspect_dev_batch` 1） | `api_records.json` 与 `api_records/` 单份返回/异常 |
| 进程内观测核心 | `build_fact_packet` 1（仅正常对照包装调用；反例未外部观察）；`screen_sqlite` 0、`verify_rule_facts` 0（本模式未包装）；子进程内部次数 **null** | 包装观察器 |
| 现场（scope=本定点模式） | 批次 4；复算 MATCHED 4；底稿 READY 4；`0007` 物理 4／可解析 4／半写 0；带失败 3；无失败且恢复成功 1；receiver 4；checker（receiver 启动）4；直接 checker CLI 0；模拟决定 8；真实批准 0；副本 0；故障注入 3 | `scene_outcomes.json`、`counts.json` |

---

## 5. 过程失败尝试与修正（如实记录）

1. 首次接线脚本锚点不匹配导致 finalizer 未接入（`assert` 失败，文件未写），随后按正确锚点重做；过程容器 `task015r2_run_01` 保留（未执行收尾）。
2. 正常对照首版只断言 API 返回与调用次数，未断言完整核心返回、packet 规范相等与 Markdown 精确字节；按卡 §3.3 补齐并进入断言。
3. 反例首版只做“旧 checkpoint 不变”核对；改为逐反例记录注入期间变化文件集合与恢复后变化集合，要求注入期间恰为目标、恢复后为空。
4. `finalize_evidence` 首版只写 `summary.json`，未落 `checks/counts/cli_logs/api_records`；补齐后重跑最终容器 `task015r2_run_03`。
5. 早期模式（b1/g4/late/smoke）原会打印默认 `missing=0/unregistered=0`；改为显式 `null` + `not_executed` 列表。

过程容器：`task015r2_run_01`（finalizer 未接入）、`task015r2_run_02`（收尾未落标准记录文件）保留未回写。

---

## 6. 三条完整产物绝对路径

- 定点容器（本卡最终）：`D:\harness work\audit_sa_project\data\workflow_host_tests\task015r2_run_03`（125 文件：`summary/checks/counts/cli_logs/api_records/call_registry/evidence_ledger/scene_outcomes/protected_scan` + `cli_logs\` 93 + `api_records\` 5 + `probe_records\` 7 + `isolation\` 2）
- 批次父目录：`D:\harness work\audit_sa_project\data\batches\task015r2_run_03`（131 文件；含 `r1_late_normalized`／`r1_late_load_report`／`r1_late_artifacts` 三个失败现场与 `r1_normal_control` 成功现场；`0007` 4 份、`0008` 0 份）
- 外置 SQLite 父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task015r2_run_03`（4 文件）

---

## 7. 对 R1 回执不符之处的更正（只写在本回执）

- R1 回执 §7 所列 `call_registry.json`、`evidence_ledger.json`、`scene_outcomes.json` 与保护扫描/比较产物在 R1 容器中**确实不存在**（R1 入口跳过收尾却输出默认零）；本轮改由 `finalize_evidence` 真实落盘并读回，R1 旧回执未改。
- R1 回执所称“进程内核心 1 次”只覆盖正常对照；本轮明确标注观察范围，不称全部进程内调用总数。
- 注入哈希引用一律取本轮最终容器 `task015r2_run_03` 的实读值，不与过程容器混用。

---

## 8. 未执行与边界

- 未执行：MAIN、smoke、完整八组、持久化故障组、事实核心 21 组、TASK-002—014 历史入口；`0007` 半写/完整后 sentinel 未重跑（宿主未变，保留引用）。
- 未建立正式契约或真实 Gate、未保存或预填人类判断、未生成 AI 建议、未接网络/LLM/UI、未建 `0008`、未实施 TASK-016。
- 边界：本地哈希只证明字节一致；不声称抵御任意时点并发篡改。停在开发态 `0007` / `FACT_PACKET_RECORDED`，真实批准 `null`、`next_step_allowed=false`。
- 未解决项：无。
