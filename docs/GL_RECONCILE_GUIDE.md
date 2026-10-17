# GL 六类核对引擎指南

标识：`TASK-056-gl-reconcile-1.0`。实现：`scripts/reconcile_gl_v1.py`（仅标准库）。
依据：`docs/decisions/DECISION_20261018_DSH_GL_DOUBLE_ENTRY.md`（`DSH-SCOPE-20261017-06` D-GL-2）；
输入：TASK-055 已接受的 `data/evidence_inputs/gl_v1/`（合成账套）。

边界：只做**核对与差异报告**，不做审计结论；不接 UI/Excel（TASK-057）、不做函证/监盘/期后付款；
真实批准 `null`、真实初判未保存、0008、`next/AI=false`。

## 1. 命令

```powershell
.venv\Scripts\python.exe -B scripts\reconcile_gl_v1.py `
  --gl-root data\evidence_inputs\gl_v1 `
  --out-dir data\runtime_initial_judgment_recording_tests\task056_gl_01
```

退出码：`0` 全部 `MATCHED`（允许备注）；`1` 存在 `DIFFERENCES_FOUND` / `INCOMPLETE`；
`2` 参数/路径错误。只写 `--out-dir`（须位于测试根下、以 `task056_` 开头、从未存在）。

## 2. 六类核对（+ 附件附加）

| id | 名称 | 规则 | 差异字段 |
| --- | --- | --- | --- |
| `journal_balance` | 凭证平衡 | 逐张借贷相等；期间借贷合计相等 | `entry_id / debit_total / credit_total` |
| `trial_balance` | 试算平衡 | 期初/本期/期末借贷两两相等；逐科目 `期初+借−贷=期末`（按方向） | `account_code / expected / actual` |
| `ledger_to_voucher` | 账证 | 总账/明细账按科目发生额 = 凭证按科目汇总；明细账凭证号/日期可追溯 | `account_code / ledger_debit|credit / voucher_debit|credit`（追溯：`entry_id / expected / actual`） |
| `general_to_subsidiary` | 账账 | 总账余额 = 明细账合计（按科目，含方向）；明细逐笔余额滚动正确 | `account_code / general / subsidiary`（滚动：`entry_id / expected / actual`） |
| `ledger_to_report` | 账表 | 科目余额 = 报表项目（含应付借方余额 4,000.00 重分类为预付 4,000.00）；资产 = 负债+权益 | `report_item / ledger_value / report_value` |
| `bank_reconcile` | 账实（银行） | 日记账余额 = 对账单期末；`期初+收入−支出=期末`；逐笔一致；未达账项分列 | `date / amount / journal_balance / statement_balance`（未达：`side`） |
| `attachments` | 附件（附加） | 附件引用存在、类型匹配（应付确认：发票/合同/入库；付款：审批/回单；退款：回单）、金额一致 | `entry_id / voucher_id / expected / actual` |

## 3. 输出

- `gl_reconcile_report.json`：`checks[]`（`{id,title,status,findings[],summary{}}`）、
  `summary`（六类状态 + `statuses` + `overall` + `notes[]`）、`period`、`batch_id`、
  `checks_performed`、`unperformed[]`、`boundaries`。
- `gl_reconcile_report.md`：审计人员可读版（六类分节、差异表、备注、未执行项、边界）。
- `reconcile_source.json`：每个 GL 文件路径/长度/SHA、命令、版本；无时间戳。

正常样本：`overall=ALL_MATCHED`，发布备注含“应付账款借方余额 4,000.00 已重分类为预付账款，
需人类判断是否为多付/预付”。

## 4. 测试与证据

`.venv\Scripts\python.exe -B tests\test_gl_reconcile.py --out-dir data\runtime_initial_judgment_recording_tests\task056_run_02`

- 正常：`exit 0`、`ALL_MATCHED`、六类 + 附件全 MATCHED；借贷合计 16,000.00 = 16,000.00、
  期末试算 20,000.00 = 20,000.00、报表 20,000.00 = 20,000.00、银行 11,000.00 = 11,000.00。
- 负例（7 类，均 `exit 1`）：改凭证贷方 1 分 → `journal_balance`；改余额表期末 1 分 →
  `trial_balance`；改明细账发生额 1 分 → `ledger_to_voucher`；改总账余额 1 分 →
  `general_to_subsidiary`；改报表项目 1 分 → `ledger_to_report`；改对账单期末 1 分 →
  `bank_reconcile`；删附件引用 → `attachments`。
- 确定性：同输入两次运行报告 JSON/MD 字节相同；只读：GL 包、task043 输入、批次不变。
- 规模：200 张凭证夹具六类核对完成（耗时/大小登记，不做性能承诺）。
- 证据：`task056_evidence_01/`（`command.json`、正常报告、负例摘要、只读快照）。

## 5. 未执行（明确列出）

函证（银行/往来）、监盘（存货）、期后付款、截止测试、收入/成本截止分析、关联方与舞弊专项程序；
这些不能由六类数字勾稽替代。

## 6. R1 补强（TASK-056-R1）

- **账账（B1）**：general_to_subsidiary 现在**逐科目**比较 ledger_general 期末余额与
  	rial_balance 期末（含方向），**无明细账的科目也参与**；原“总账↔明细账”比较保留。
  差异字段：ccount_code / general_closing / trial_closing。
- **账表（B2）**：ledger_to_report 增加报表内部平衡：	otal_assets_cents = 资产分项之和、
  	otal_liabilities_equity_cents = 负债+权益分项之和、且两者相等。差异字段：
  
eport_item / expected_total / actual_total；原逐项目与重分类比较保留。
- **账证（B3）**：ledger_to_voucher 在总账口径之外，**同时**对每个有明细账的科目比较
  明细账发生额合计 = 凭证汇总；差异 finding 带 source=subsidiary。
- **测试**：新增 B1（1001 无明细账科目期末 +1 分）、B2（报表合计 +1 分）、B3（明细账发生额 +1 分）
  三个变异用例，均必须 exit 1；原有 7 类负例回归保留（共 13 例）。
