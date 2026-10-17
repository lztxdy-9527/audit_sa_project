# TASK-046 执行回执：四相符一条命令演示 + 校验器版本声明集 + 求职稿/最终入口更新

日期：2026-10-17。交付状态：四相符集成、版本声明集、两份文档与证据定稿，**交最后一轮独立验收**；
本回执不宣布验收通过，不改看板、不推进账账/账表或 AI/终判。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-046_DRAFT.md`（`f72a0f90…`）。前置：TASK-045 ACCEPTED。起点接受快照
`data/reviews/task045_dsh_20261017_01/source_hashes_after.json`（**175890 项 / `b99e0cdc…`**）。
本卡**改既有恰四件**（§1），其余纯新增。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task046_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 改动身份（恰四件，同缓冲长度/SHA）

| 文件 | 长度 | SHA-256 | 改动 |
| --- | --- | --- | --- |
| `scripts/input_contract_v1.py` | 36194 B | `622f47b9acb54a3c943bb4fbaa56923718cc88a0b7976a560685b59afad8b351` | 版本声明集 `{task043-input-1.0, task043-input-1.1}`；登记/拒收原样回显 `input_version`；其余校验不变 |
| `scripts/run_runtime_demo.py` | 34519 B | `8f264a2d9f06b7ea3d82f8f0ef51f343f6c126ba0f6affcf58babe3f162bf40a` | 既有链后只读调用契约/账证/账实核对器；`--evidence-input`（默认 v1.1）；差异不被吞掉 |
| `docs/JOB_DEMO_PLAYBOOK_20261017.md` | 14339 B | `1b4c265d28c4e11341f81348ce658bb1b32acc8ca67803ce77fbaabfd93efe8f` | 四相符口径、演示命令/产物更新 |
| `docs/FINAL_ACCEPTANCE_ENTRY.md` | 11843 B | `34a621665e033a3bebd059021a0637d17acbaa81a9753c161f359248b901a7fd` | 任务链、接受基线、交付身份、演示证据更新 |

未改：适配器、输入根（v1/v1.1）、voucher_match/bank_reconcile、测试、指南、既有卡/评审/证据、看板。

## 2. 校验器版本声明集（关闭 R1 残差）

- v1.1 原样：**exit 0、`INPUT_V1_ACCEPTED`**、凭证 8（回单 3/审批 2/其他 3）/ links 8 / bank 3；
  `input_registry.json` 的 `input_version` 原样回显 `task043-input-1.1`。
- v1 原样（回归）：**exit 0**、`INPUT_V1_ACCEPTED`、凭证 6 / links 6 / bank 3；回显 `task043-input-1.0`。
- 未知版本副本（`task043-input-1.2`，仅版本位不同）：**exit 1、唯一 `MANIFEST_VERSION`**，detail
  “必须为 task043-input-1.0 或 task043-input-1.1 之一”；其余校验未变。

## 3. 四相符一条命令（实测 exit 0）

```
.venv\Scripts\python.exe -B scripts\run_runtime_demo.py --out-dir data\runtime_initial_judgment_recording_tests\task046_demo_01
```

`demo_summary.json`（`four_way`）与 `demo_readme.md` 实测：

- 契约：`INPUT_V1_ACCEPTED`（凭证 8；links 8；流水 3）；
- 账证：**8/8 `MATCHED`**，差异 0 / 账有证无 0 / 证有账无 0；R02 抽样 AP01/P01/P02/R01；
  P02 证据 V-APR-0002 / V-BR-0003；
- 账实：**3/3 `MATCHED`**（P01→BT-2026-0001、P02→BT-2026-0002、R01→BT-2026-0003，均 `REFERENCE_INDEX`）；
  期间合计 OUT 1,000,000 == 已结算付款、IN 100,000 == 退款，差异 0；未达账项 账有实无 0 / 实有账无 0；
  余额 `not_provided`（不做余额算术、不与账面存款科目比较）；
- 人类核对结论：`null`（不采集、不虚构）；
- 层级：`FIELD_LEVEL_L1_AND_TRANSACTION_LEVEL_L1`；耗时约 95 秒（非性能结论）。
- 记录：`RT_HUMAN_INITIAL_JUDGMENT_VERIFIED`，`record_fingerprint=58f8d81e…f509f`，九边界全 false，
  R01–R04 = 0/1/0/0。

## 4. 负例（现场保留，差异不被吞掉）

| 负例 | 输入 | 结果 |
| --- | --- | --- |
| P02 缺证 | `--evidence-input data/evidence_inputs/task043_v1` | 契约通过（v1 合法）；账证 `DIFFERENCES_FOUND`、**2 条 `MISSING_VOUCHER`**（P02 × APPROVAL/BANK_RECEIPT）、6/8 MATCHED；账实仍 3/3；**演示 exit 1**，summary 已写 |
| 未知版本 | 副本 manifest 改 `task043-input-1.2` | 契约 **`MANIFEST_VERSION` 整批拒收**（唯一 reason）；**演示 exit 1**，rejection.json 保留 |

原输入不改（v1 缺证为数据事实；未知版用副本注入）。证据：`task046_demo_v1_neg/`、`task046_demo_badver_neg/`、
`task046_badver_input/`。

## 5. 既有四 CLI 回归（实测 0/1/1/1）

`tests/test_runtime_initial_judgment_recording.py --replay data/runtime_initial_judgment_recording_tests/task041_run_05`
（新 out 根 `task046_regress_*`）：正常 **0**、内容反例（candidate-return）**1**、台账替换（ledger-replaced）**1**、
末次读后漂移（late-drift）**1**。日志在 `task046_run_01/cli46_*.log`。

## 6. 只读与证据

- 只读：演示/负例运行前后，`task043_v1`（9 文件）、`task043_v1_1`（9 文件）、账务 normalized/started/artifacts
  字节快照完全一致（`readonly_before.json == readonly_after.json`）；输入/凭证/银行/账务/Gate/历史均未写。
- 证据根 `data/runtime_initial_judgment_recording_tests/task046_run_01/`：`command.json`（命令/退出码/四 CLI）、
  `demo_stdout|stderr.txt`、`demo_v1_neg_stdout|stderr.txt`、`demo_badver_neg_stdout|stderr.txt`、
  `readonly_before|after.json`、`cli46_task046_regress_*.log`。
- 演示运行根 `task046_demo_01/`：`demo_summary.json`、`demo_readme.md`、`task043_input_check/`、
  `task044_match/`、`task045_reconcile/`，以及 `data/runtime/task046_demo_01/`、
  `data/human_gate_decision_records/gate1|gate2/task046_demo_01/`、`data/sqlite_tests/task046_demo_01/`、
  `data/human_initial_judgment_records/task046_demo_01/`。
- 迭代保留：`task046_smoke_demo_01`（首跑字段缺失）、`task046_smoke_demo_02`（通过）、`task043_smoke_contract_01/02`
  （版本集单测冒烟，v1.1/v1 各一次）。

## 7. 保护安排与判据

定稿后**一次**全树扫描（`task046_finalization/protection_scan.py`），基线 = TASK-045 接受快照
（175890 项 / `b99e0cdc…`）：相对该基线**既有 changed 恰 §1 四件**（逐文件登记 baseline→current）；
其余均为新增（本回执、`task046_*` 根、`task043_smoke_contract_*` 冒烟根、架构端已知增量逐确切路径登记）；
missing/读取错误/未登记新增/身份漂移 0；139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 8. 未执行与边界

未执行：账账/账表（需报表层输入与另行授权）、银行余额核对、影像/OCR、外部查验、函证/盘点、
人类核对结论采集、AI 建议、人类终判、真实数据/强认证/物理 junction/非合作篡改/并发双进程竞态（`null` + 原因）。
本演示仍为合成数据，不证明凭证/流水真实，不构成审计结论。
