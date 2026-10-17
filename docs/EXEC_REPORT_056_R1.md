# TASK-056-R1 执行回执：补齐总账↔余额表、报表内部平衡与账证明细账覆盖

日期：2026-10-18。交付状态：按 `TASK-056-R1` 修复 B1/B2/B3 三处漏检，**交独立验收**；
TASK-056 仍为 NOT_ACCEPTED（`docs/reviews/REVIEW_TASK_056.md`，`3f790c77…`），本卡只改其三个未接受文件。
既有 changed = 0（基线 TASK-055 接受快照 **200574 项 / `65245ddf…`**）。

## 1. 改动身份（三件，实测）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/reconcile_gl_v1.py` | 24785 B | `83181b8b4650e6ab…` |
| `tests/test_gl_reconcile.py` | 12683 B | `7581be89af3d7589…` |
| `docs/GL_RECONCILE_GUIDE.md` | 5461 B | `189d62de14347878…` |

新增 `docs/EXEC_REPORT_056_R1.md`、`task056r1_*` 证据根；引擎版本 `TASK-056-gl-reconcile-1.1`。

## 2. 修复内容（实测）

### B1 总账↔科目余额表（账账补全）

`general_to_subsidiary` 现在**逐科目**比较 `ledger_general` 期末余额与 `trial_balance` 期末
（含方向），**无明细账的科目（1001/3001）也参与**；原“总账↔明细账”比较保留。
差异字段：`account_code / general_closing / trial_closing`。

复验：`ledger_general.accounts.0.closing_debit` 500000→500001（1001，无明细账）→
**exit 1**，`general_to_subsidiary=DIFFERENCES`，finding
`{"account_code": "1001", "general_closing": 500001, "trial_closing": 500000}`。

### B2 报表内部平衡（账表补全）

`ledger_to_report` 增加：`total_assets_cents` = 资产分项之和；
`total_liabilities_equity_cents` = 负债+权益分项之和；且两者相等。
差异字段：`report_item / expected_total / actual_total`；逐项目与应付 4,000 重分类比较保留。

复验：`balance_sheet.total_assets_cents` 2000000→2000001（分项不动）→ **exit 1**，
`ledger_to_report=DIFFERENCES`，finding
`{"report_item": "total_assets_cents", "expected_total": 2000000, "actual_total": 2000001}`。

### B3 账证对明细账的覆盖

`ledger_to_voucher` 在总账按科目发生额 = 凭证汇总之外，**同时**对每个有明细账的科目比较
明细账发生额合计 = 凭证汇总；finding 带 `source="subsidiary"`。指南明确账证覆盖明细账。

复验：`ledger_subsidiary.subsidiaries.0.entries.0.credit_cents` 500000→500001 →
**exit 1**，`ledger_to_voucher=DIFFERENCES`，finding
`{"account_code": "2202", "source": "subsidiary", "ledger_credit": 600001, "voucher_credit": 600000, …}`。

## 3. 测试（实测 13/13 PASS）

`tests/test_gl_reconcile.py --out-dir …\task056r1_run_01`：

- 正常：`gl_v1` → exit 0、`ALL_MATCHED`、七项全 MATCHED；借贷 16,000.00 = 16,000.00；
  试算 20,000.00 = 20,000.00；应付 4,000.00 借；银行 11,000.00；报表 20,000.00 = 20,000.00；
  备注含应付借方 4,000 重分类；未执行项列示。
- **B1/B2/B3 变异**（新增）均 exit 1，检查与字段精确（如上）。
- 原有 7 类负例回归：凭证不平衡、余额表等式、报表项目、银行期末、附件缺失、明细账发生额、
  总账余额 → 仍 exit 1；清单篡改由契约层负责（TASK-055 校验器）。
- 确定性：同输入两次报告 JSON/MD 字节相同；只读：GL 包、`task043_v1_1`、批次不变。
- 规模：200 张凭证夹具六类核对完成（0.125 s、报告 3792 B；仅测试用）。

## 4. 证据

`task056r1_evidence_01/command.json`：正常命令/退出码/耗时、正常报告身份、B1/B2/B3 与原有负例
退出码/首条 finding、规模、只读快照；正常报告 `task056r1_gl_01/`；测试根 `task056r1_run_01/`。

## 5. 保护安排与判据

定稿后**一次**全树扫描（`task056r1_finalization/protection_scan.py`），基线 = TASK-055 接受快照
（200574 项 / `65245ddf…`）：**既有 changed 必须为 0**（本卡只改 TASK-056 未接受的三个新文件，
相对基线仍为新增）；其余全新增逐路径登记；missing/读取错误/未登记新增 0；
139/27/326/19/TASK-030 41 B 锁继续冻结。

## 6. 边界

核对结果只展示证据与差异，**不构成审计结论或终判**；不接 UI/Excel（TASK-057）、不做函证/监盘/
期后付款、不改看板。真实批准 `null`、真实初判未保存、0008、`next/AI=false`。
