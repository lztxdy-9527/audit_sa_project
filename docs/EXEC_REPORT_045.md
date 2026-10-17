# TASK-045 执行回执：账实相符（银行流水交易级勾对）与未达账项底稿

日期：2026-10-17。交付状态：勾对器、测试、指南与证据定稿，**交 Architect 独立验收**；
本回执不宣布验收通过，不做账表/账账、不改演示脚本、不改看板。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-045_DRAFT.md`、`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`
（`DSH-SCOPE-20261017-02`）。前置：TASK-043 输入契约 v1 与 TASK-044 账证匹配已接受。
本卡**纯新增**：未修改任何既有文件。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task045_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 勾对器（唯一新增代码） | `scripts/bank_reconcile_v1.py` | 27824 B | `ef802fde1408cba06861bc821180c02510dfc20cff193a6f60c3f20797de2e88` |
| 新测试 | `tests/test_bank_reconcile_v1.py` | 15453 B | `2a442b46029fad8b3b0bd4eaa2223089f33530f2e3f31843106323e429ef4af1` |
| 指南 | `docs/BANK_RECONCILIATION_GUIDE.md` | 5878 B | `67ae604d99d3b326b2801e6812f41fa124a7f44b25cc29e293761b14a24568aa` |
| 本回执 | `docs/EXEC_REPORT_045.md` | 见 delivery.json | 见 delivery.json |

输入侧：canonical 采用已接受的 `data/evidence_inputs/task043_v1_1/`（`bank/transactions.json` 与 v1
逐字节相同）；卡 §1 原文的 `task043_v1` 作为对照。账务侧只读复用
`data/runtime/task042_dsh_01/normal.load/normalized.json`（`f440f0cf…`），绑定核对同 TASK-044。

## 2. 命令与退出码（实测）

```
.venv\Scripts\python.exe -B tests\test_bank_reconcile_v1.py --out-dir data\runtime_initial_judgment_recording_tests\task045_run_02
```

- 测试退出码 **0**；`test_report.json`：**12/12 cases PASS**（1 正常 v1.1 + 1 v1 对照 + 10 负例），
  `read_only_ok=true`（v1.1、v1、normalized/started/artifacts 前后字节不变）。
- 勾对器调用（子进程，实测）：`scripts/bank_reconcile_v1.py --input <root> --ledger-normalized …/normalized.json --out …`
  → 正常 **退出码 0、`ALL_MATCHED`、3/3 匹配**；负例均 **退出码 1**。

## 3. 正常（全部匹配）

- **v1.1 canonical**：3/3 `MATCHED`（P01→BT-2026-0001、P02→BT-2026-0002、R01→BT-2026-0003），
  依据均 `REFERENCE_INDEX`（索引声明的回单 `bank_txn_id`）；差异 0、账有实无 0、实有账无 0。
- **v1 对照**：同为 `ALL_MATCHED`（P01/R01 走 `REFERENCE_INDEX`，P02 无索引声明走 `TRIPLE` 三元组），
  证明两个输入版本一致、三元组回退可用。
- 期间合计：`OUT` 1,000,000 分 == 已结算付款 1,000,000 分（差 0）；`IN` 100,000 分 == 退款 100,000 分（差 0）；
  余额状态 `not_provided`（流水未提供期初/期末余额，不做余额算术，更不与账面存款科目比较）。
- 现金/资金口径：整笔付款金额（P01/P02 各 500000、R01 100000）与分摊金额（各付款的分摊行）分别列示，
  注明“不相加”。
- 人类核对结论：`human_conclusion=null`，报告“人类核对结论”留空并注明需另行授权与登记。

## 4. 负例（10 类，逐类精确）

| # | 类别 | 注入 | 实测分类/字段 |
| --- | --- | --- | --- |
| 1 | 金额差 1 分 | BT-2026-0001 amount 499999 | `AMOUNT_MISMATCH` / `amount_cents` |
| 2 | 日期不符 | BT-2026-0001 txn_date 2026-09-11 | `DATE_MISMATCH` / `txn_date` |
| 3 | 对方户名不符 | BT-2026-0001 counterparty_name 乙收款对象 | `COUNTERPARTY_MISMATCH` / `counterparty_name` |
| 4 | 方向错 | BT-2026-0001 direction IN | `DIRECTION_MISMATCH` / `direction` |
| 5 | 引用冲突 | BT-2026-0001 reference 改为 P02 | `REFERENCE_CONFLICT` / `reference` |
| 6 | 同一流水重复行 | 追加同 `bank_txn_id` 的流水行 | `DUPLICATE_BANK_LINE` |
| 7 | 同一流水重复匹配 | 账务副本把 P02 `bank_reference` 改为 P01 | `DUPLICATE_MATCH` |
| 8 | 账有实无 | 删除 BT-2026-0002 | `LEDGER_UNMATCHED`（P02） |
| 9 | 实有账无 | 追加 BT-2026-9999（OUT 100000 / 2026-09-25） | `BANK_UNMATCHED` |
| 10 | 期间外流水 | BT-2026-0001 txn_date 2026-10-01 | `DATE_MISMATCH` / `txn_date` |

每例保留：输入副本、命令、stdout/stderr、退出码、完整报告与差异；第 7 类使用账务 normalized 的
**副本**注入（原 normalized/started/artifacts 只读、字节不变）。未达账项两侧分列，注明“未达账项≠差错，
需人类核查”。

## 5. 只读与证据

- 只读：勾对器不写输入根/批次/账务/凭证/银行/Gate/历史；测试前后对 v1.1、v1、`normalized.json`、
  `started.json`、`artifacts.json` 做字节快照比较，`read_only_ok=true`。
- 证据根 `data/runtime_initial_judgment_recording_tests/task045_run_02/`：`test_report.json`、
  `test_stdout.txt`、`test_stderr.txt`、`command.json`、`normal_v1_1/task045_normal/…`、
  `control_v1/task045_v1/…`、每负例 `<case>/{input,task045_out/…}` 与 stdout/stderr。
- 迭代保留：`task045_smoke_01`（首次冒烟：v1.1 与 v1 双版本）、`task045_run_01`（首轮通过）、
  `task045_run_02`（定稿证据）。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task045_finalization/protection_scan.py`），基线 = TASK-043-R1 接受快照
（175436 项 / `8ceb0df0…`）：既有 changed 必须为 0；新增仅限本卡四件与 `task045_*` 证据根、
架构端已知增量（本卡 045 与 REVIEW_TASK_043_R1 等逐确切路径登记）；new missing/读取错误/未登记新增 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 7. 未执行与边界

未执行：银行对账单格式适配、OCR/影像、函证/盘点、银行余额核对（需报表层输入另行授权）、
无索引模糊匹配之外的推断、人类核对结论（不采集不虚构）、账账/账表、演示集成、AI、终判、
真实数据/强认证/物理 junction/非合作篡改/并发双进程竞态（`null` + 原因）。
结论：交易级 L1 + 期间合计；未做格式适配、未看回单影像、未函证、未做银行余额核对；
不证明来源真实，不构成审计证据或结论。
