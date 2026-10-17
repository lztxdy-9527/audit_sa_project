# 账实相符（银行流水交易级勾对）指南

标识：`task045-bank-reconcile-1.0`。实现：`scripts/bank_reconcile_v1.py`（唯一新增代码）。
前置：TASK-043 输入契约 v1（银行流水/索引/回单）与 TASK-044 账证匹配已接受。
依据：`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`（`DSH-SCOPE-20261017-02`）。

边界：只做**交易级 L1 + 期间合计**；不做银行对账单格式适配、不做 OCR/影像、不做函证/盘点、
**不做银行余额 vs 账面余额**（需报表层输入另行授权）；不采集、不虚构人类核对结论。
合成数据；`real_approval=null`、真实独立初判未保存、`next_step_allowed=false`、`ai_enabled=false`；
不写输入根/批次/账务/凭证/银行/Gate/历史，只写本次证据根。

## 1. 用法

```powershell
.venv\Scripts\python.exe -B scripts\bank_reconcile_v1.py `
  --input data\evidence_inputs\task043_v1_1 `
  --ledger-normalized data\runtime\task042_dsh_01\normal.load\normalized.json `
  --out data\runtime_initial_judgment_recording_tests\task045_<轮次>\task045_normal
```

- `--input`：TASK-043 输入根（只读）；`bank/transactions.json` 在 v1/v1.1 中**逐字节相同**。
  canonical 采用已接受的 `task043_v1_1`；卡 §1 原文的 `task043_v1` 作为对照（同为 ALL_MATCHED）。
- `--ledger-normalized`：已接受运行证据的 `normal.load/normalized.json`（只读）；同目录若有
  `started.json`/`artifacts.json` 则校验绑定（`batch_id`、`source_batch_relative`、
  `run_binding.input.file_sha256`、`normalized_file_sha256`、`mode=DEVELOPMENT_TEST_ONLY`）。
- `--out`：必须从未存在、位于 `data/runtime_initial_judgment_recording_tests/` 下且以 `task045_` 开头。
- 退出码：`0` 全部匹配且期间合计一致；`1` 存在差异/未达账项（报告照常输出）；`2` 参数/绑定/环境错误。

## 2. 勾对规则（确定性）

对每条账务记录（`payments` 中 `transaction_type ∈ {PAY, REFUND}`）：

1. **引用优先**：
   - 索引声明：`links` 中 `PAYMENT_BANK_RECEIPT`/`REFUND_BANK_RECEIPT` → 回单 `bank_txn_id`
     指向流水 `bank_txn_id`（依据 `REFERENCE_INDEX`）；
   - 账务 `bank_reference` == 流水 `reference` 或 `bank_txn_id`（依据 `REFERENCE_BANK_REFERENCE`）。
2. **无引用/无可用引用时**：在未匹配双方中按 `(amount_cents, txn_date, counterparty_name)`
   精确三元组匹配（依据 `TRIPLE`），要求候选唯一。
3. **1:1**：同一流水只匹配一条账务记录、同一账务记录只匹配一条流水；重复即 `DUPLICATE_MATCH` 或
   `DUPLICATE_BANK_LINE`（同一流水行重复）。

匹配后逐字段核对：金额整数分精确、日期相等、方向（付款 `OUT`、退款 `IN`）、对方户名（账务供应商名称）、
期间（`<= 2026-09-30`）；币种因流水契约无币种字段，记录为 `not_available_in_schema`（不比对）；
对方账号因账务无账号字段，记录为 `not_available_in_ledger`（不比对）。

## 3. 分类（固定枚举）

`MATCHED`、`AMOUNT_MISMATCH`、`DATE_MISMATCH`、`COUNTERPARTY_MISMATCH`、`DIRECTION_MISMATCH`、
`REFERENCE_CONFLICT`、`DUPLICATE_BANK_LINE`、`DUPLICATE_MATCH`、`LEDGER_UNMATCHED`（账有实无）、
`BANK_UNMATCHED`（实有账无，未达账项候选）。

- 引用冲突：流水 `reference` 指向**另一账务记录**（既非本账务 ID 也非 `bank_reference`）→ `REFERENCE_CONFLICT`；
  引用匹配下金额/日期/对方不符按字段类（`AMOUNT_MISMATCH` 等）报告，便于精确差异。
- 同一 `bank_txn_id` 出现多行 → `DUPLICATE_BANK_LINE`；同一流水被两条账务记录争用 → `DUPLICATE_MATCH`。
- 未匹配双方**不强行配对**：账有实无 `LEDGER_UNMATCHED`、实有账无 `BANK_UNMATCHED`。

## 4. 期间合计与余额

- `OUT` 流水合计 vs 已结算付款合计（`transaction_type=PAY, settlement_status=SETTLED`）；
  `IN` 流水合计 vs 退款合计（`transaction_type=REFUND`）；差异单列。
- 若流水提供期初/期末余额，仅做算术自洽（期初 + IN − OUT = 期末）；本输入未提供余额，状态
  `not_provided`，**不**与账面银行存款科目比较（需报表层输入，另行授权）。
- 现金/资金口径提示：整笔付款金额与分摊金额分别列示，**不相加**。

## 5. 输出

`bank_reconcile_report.json`：
- `input`/`ledger` 身份与绑定核对；
- `matched[]`：账务 ID、类型、流水 ID、依据（`REFERENCE_INDEX`/`REFERENCE_BANK_REFERENCE`/`TRIPLE`）；
- `differences[]`：账务 ID、流水 ID、字段、实际、预期、分类；
- `duplicates[]`；`unmatched`（两侧分列，注明“未达账项≠差错，需人类核查”）；
- `period_totals`（含余额状态）；`cash_fund_note`；
- `summary`、`conclusion`（`ALL_MATCHED`/`DIFFERENCES_FOUND`）、
  `verification_level=TRANSACTION_LEVEL_L1_PLUS_PERIOD_TOTALS`、`human_conclusion=null`。

`bank_reconcile_report.md`：可阅读版本，含“人类核对结论”留空。

## 6. 测试

```
.venv\Scripts\python.exe -B tests\test_bank_reconcile_v1.py `
  --out-dir data\runtime_initial_judgment_recording_tests\task045_run_01
```

- 正常（v1.1）：3/3 匹配（P01/P02/R01 均 `REFERENCE_INDEX`）、期间合计 0 差异、未达账项为空、退出码 0。
- v1 对照：同为 `ALL_MATCHED`（P02 走 `TRIPLE`），验证两个输入版本一致。
- 负例（10 类，复制输入副本注入；重复匹配用账务副本）：金额差 1 分、日期不符、对方户名不符、方向错、
  引用冲突、同一流水重复行、同一流水重复匹配、账有实无、实有账无、期间外流水。
- 每例保留输入副本、命令、stdout/stderr、退出码、报告与差异；原输入与既有证据前后字节不变。
