# TASK-056 执行回执：借贷记账法六类核对引擎

日期：2026-10-18。交付状态：六类核对引擎、测试、指南与证据完成，**交独立验收**；
**既有 changed = 0**；不接 UI/Excel（TASK-057）、不做函证/监盘/期后付款、不改看板。

依据：`docs/tasks/TASK-056_DRAFT.md`（`a418f56a…`）、决策记录
`docs/decisions/DECISION_20261018_DSH_GL_DOUBLE_ENTRY.md`（`DSH-SCOPE-20261017-06` D-GL-2）。
前置：TASK-055 ACCEPTED；接受基线 `data/reviews/task055_dsh_20261018_01/source_hashes_after.json`
（**200574 项 / `65245ddf…`**）。

## 1. 新增身份（实测）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/reconcile_gl_v1.py` | 22841 B | `f7acd85deb0eb729…` |
| `tests/test_gl_reconcile.py` | 11914 B | `2c64f8ccdb26c0f9…` |
| `docs/GL_RECONCILE_GUIDE.md` | 4346 B | `936a01fe01ae75a6…` |
| `docs/EXEC_REPORT_056.md` | 本文 | — |

证据根 `task056_evidence_01/`、正常核对根 `task056_gl_01/`、测试根 `task056_run_02/`。

## 2. 六类核对（实测 ALL_MATCHED）

对 `data/evidence_inputs/gl_v1` 运行：

```powershell
.venv\Scripts\python.exe -B scripts\reconcile_gl_v1.py `
  --gl-root data\evidence_inputs\gl_v1 `
  --out-dir data\runtime_initial_judgment_recording_tests\task056_gl_01
```

- **exit 0、overall=ALL_MATCHED**；七项（六类 + 附件）全部 MATCHED：
  `journal_balance` / `trial_balance` / `ledger_to_voucher` / `general_to_subsidiary` /
  `ledger_to_report` / `bank_reconcile` / `attachments`。
- 数字与手算一致：凭证借/贷合计各 16,000.00；期末试算借 20,000.00 = 贷 20,000.00；
  期末库存 5,000.00 借、银行 11,000.00 借、应付 4,000.00 借、实收 20,000.00 贷；
  报表资产 20,000.00 = 负债+权益 20,000.00；银行日记账 11,000.00 = 对账单 11,000.00。
- 备注含“应付账款借方余额 4,000.00 已重分类为预付账款，需人类判断是否为多付/预付”，
  **不把重分类当差异**；未执行项（函证/监盘/期后付款/截止测试等）在报告中明确列出。
- 输出：`gl_reconcile_report.json`、`gl_reconcile_report.md`、`reconcile_source.json`
  （逐文件路径/长度/SHA、命令、版本；无时间戳）；只写 `--out-dir`。

## 3. 测试（实测 10/10 PASS）

`tests/test_gl_reconcile.py --out-dir …\task056_run_02`：

- 正常：`exit 0`、ALL_MATCHED、六类 + 附件、数字/备注/报告齐全。
- 负例（7 类，均 **exit 1** 且字段精确）：
  凭证贷方 +1 分 → `journal_balance`；余额表期末 +1 分 → `trial_balance`；
  明细账发生额 +1 分 → `ledger_to_voucher`；总账余额 +1 分 → `general_to_subsidiary`；
  报表项目 +1 分 → `ledger_to_report`；对账单期末 +1 分 → `bank_reconcile`；
  删附件引用 → `attachments`。
- 确定性：同输入两次运行报告 JSON/MD **字节相同**。
- 只读：GL 包、`task043_v1_1`、批次源字节不变。
- 规模：复制 GL 包构造 **200 张凭证**夹具，六类核对完成（0.125 s、报告 3792 B；仅本卡测试用，不做性能承诺）。

## 4. 证据

`task056_evidence_01/command.json`：正常命令/退出码/耗时、正常报告身份、7 个负例退出码与首条差异、
规模耗时/大小、只读快照；正常报告位于 `task056_gl_01/`；测试夹具与报告位于 `task056_run_02/`。

## 5. 保护安排与判据

定稿后**一次**全树扫描（`task056_finalization/protection_scan.py`），基线 = TASK-055 接受快照
（200574 项 / `65245ddf…`）：**既有 changed 必须为 0**；新增仅限本卡文件、`task056_*/**` 与
架构端已知增量（逐确切路径登记）；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B
锁继续冻结。

## 6. 边界

核对结果只展示证据与差异，**不构成审计结论或终判**；不接 UI/Excel（TASK-057）、不做函证/监盘/
期后付款、不改看板。真实批准 `null`、真实初判未保存、0008、`next/AI=false`。
