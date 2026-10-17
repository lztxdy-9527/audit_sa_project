# 输入契约 v1（账 / 证 / 银 / 表占位）

标识：`task043-input-1.0`。实现：`scripts/input_contract_v1.py`（唯一新增校验代码）。
依据：`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`（`DSH-SCOPE-20261017-02`）。
本契约只接受**已规整输入**：不做数据清洗、不做 OCR、不做银行对账单格式适配；不合契约**整批拒收**，不修、不补、不猜。

边界：合成数据；不证明凭证真实、不构成审计证据或结论；`real_approval=null`、真实独立初判未保存、
`next_step_allowed=false`、`ai_enabled=false`。本工具只读输入根与既有批次账务，不写批次、账务、凭证、
银行输入或 Gate/历史现场。

## 1. 输入根与文件集（固定）

`data/evidence_inputs/task043_v1/` 下**恰这些文件**（多一个未知文件即拒收）：

```
input_manifest.json
vouchers/invoices.json      vouchers/contracts.json   vouchers/bank_receipts.json
vouchers/approvals.json     vouchers/goods_receipts.json
links/index.json
bank/transactions.json
reports/placeholders.json     （账表占位，必须为空数组）
```

`input_manifest.json`：`input_version="task043-input-1.0"`、`batch_id="batch_normal"`、
`entity{company=澄明商贸有限公司, currency=CNY, period_start=2026-09-01, period_end=2026-09-30,
cutoff_date=2026-09-30}`、`files[]`（`relative`/`byte_size`/`sha256`，恰八个数据文件；manifest 自身不含自哈希）。

## 2. 记录 schema（★ 必填，封闭键集）

- **INVOICE**（`vouchers/invoices.json`）：★voucher_id、★invoice_no、★issue_date、★seller_supplier_id、
  ★seller_name、★buyer_name、★amount_cents、★tax_cents、★total_cents、★currency。
  `total_cents == amount_cents + tax_cents`；`amount_cents > 0`、`tax_cents >= 0`；`buyer_name` 必须等于
  manifest 实体；`currency` 必须为 CNY 且等于 manifest。
- **CONTRACT**：★voucher_id、★contract_no、★sign_date、★counterparty_supplier_id、★counterparty_name、
  ★amount_cents、★currency。
- **BANK_RECEIPT**：★voucher_id、★receipt_no、★bank_txn_id、★txn_date、★amount_cents、
  ★direction(PAY/REFUND)、★counterparty_name、★counterparty_account、★currency。
- **APPROVAL**：★voucher_id、★approval_no、★approval_date、★payment_id、★amount_cents、
  ★status(APPROVED)。不记录审批人身份，不做强认证。
- **GOODS_RECEIPT**：★voucher_id、★gr_no、★accept_date、★supplier_id、★amount_cents、★currency。
- **bank_txn**（`bank/transactions.json`）：★bank_txn_id、★txn_date、★direction(OUT/IN)、★amount_cents、
  ★counterparty_name、★counterparty_account、★summary、reference（null 或非空原字符串）。
- **link**（`links/index.json`）：`{link_id, link_type, ledger_type, ledger_id, voucher_id}`；
  `link_type ∈ {AP_INVOICE, AP_CONTRACT, AP_GOODS_RECEIPT, PAYMENT_APPROVAL,
  PAYMENT_BANK_RECEIPT, REFUND_BANK_RECEIPT}`；`ledger_type ∈ {AP, PAYMENT, REFUND}`。
  索引由输入提供（ERP 附件/关联表口径）；本卡只**校验引用完整性**，不做匹配。

金额一律**整数分**（严格 `int`，非 bool/float）；日期 `YYYY-MM-DD` 且不晚于 `2026-09-30`；
ID 保持原字符串；`voucher_id` 全局唯一、`link_id`/`bank_txn_id` 各自唯一。

## 3. 校验与拒收

1. 固定文件集合（多/少均拒）、UTF-8 JSON、顶层记录数组、ID 唯一。
2. 封闭键集、类型/必填/枚举、金额整数分且 >0（税可 0）、币种 CNY、日期格式与不晚于截止日、实体一致。
3. `total_cents == amount_cents + tax_cents`。
4. 清单哈希：每个文件实际字节长度/SHA-256 与 `input_manifest.files` 精确相等；manifest 无自哈希。
5. 索引引用：`voucher_id` 存在且凭证类型与 `link_type` 匹配；`ledger_type` 与 `link_type` 匹配；
   `ledger_id` 在既有批次账务（只读 SQLite：payables/payments）中真实存在；同一
   `(link_type, ledger_id, voucher_id)` 不重复。附加引用完整性：`APPROVAL.payment_id` 必须为批次 PAY 付款；
   `BANK_RECEIPT.bank_txn_id` 必须存在且方向匹配（PAY↔OUT、REFUND↔IN）。
6. 任何一条不满足 → **整批拒收**：写 `rejection.json`（`code`/`field`/`record`/`voucher_id`/
   `expected`/`actual`/`detail`、`batch_id`、`input_version`、`ledger_source`），不生成登记，退出码非 0。

### 用法

```powershell
.venv\Scripts\python.exe -B scripts\input_contract_v1.py `
  --input data\evidence_inputs\task043_v1 `
  --out data\runtime_initial_judgment_recording_tests\task043_<轮次>\task043_normal `
  --ledger-db data\sqlite_tests\task042_dsh_01\normal\runtime.sqlite3
```

- `--out` 必须从未存在、位于 `data/runtime_initial_judgment_recording_tests/` 下且目录名以 `task043_` 开头；
  `--ledger-db` 以 `mode=ro&immutable=1` 只读打开。
- 退出码：`0` 接受并写登记；`1` 整批拒收（写 `rejection.json`）；`2` 参数/路径/环境错误（不是契约违约）。
- 通过时写 `input_registry.json`（`registry_version`、`input_version`、`batch_id`、`entity`、逐文件
  `byte_size`/`file_sha256`、各类计数、`checks`、`conclusion=INPUT_V1_ACCEPTED`、`ledger_source`、边界），
  并做一次同缓冲读回（`registry_readback.json`：`same_buffer_readback=true`、字节数与 SHA-256）。

## 4. 拒收/登记的边界

- 拒收现场保留：输入副本、命令、stdout/stderr、退出码与 `rejection.json` 都在证据根内，不清理。
- 校验进程只读：不写输入根（正常/负例均验证输入根字节不变）、不写 ledger 数据库、不写批次/Gate/历史。
- 正常输入根为 `data/evidence_inputs/task043_v1/`；负例由测试复制副本注入，原根不改。

## 5. 测试

```
.venv\Scripts\python.exe -B tests\test_input_contract_v1.py `
  --out-dir data\runtime_initial_judgment_recording_tests\task043_run_01
```

- 正常：合法 v1 → `input_registry.json`，逐文件哈希与输入字节一致、计数与合成数据一致。
- 负例（17 类）：缺文件、多未知文件、哈希不符、voucher_id 重复、缺必填、金额非整数、金额非正、
  `total≠amount+tax`、日期越界、币种错、索引悬挂、索引重复、ledger_id 不存在、link_type/凭证类型不匹配、
  坏 JSON、顶层非数组、账表占位非空；每类一条，均整批拒收且 reason 字段精确。
- 只读纪律：测试前后规范输入根与 ledger 数据库字节不变。
