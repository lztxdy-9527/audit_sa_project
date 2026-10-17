# 数据与错误识别规范（供数据生成 Agent 使用）

版本：2026-10-18。适用程序：`audit_sa_project`（合成演示）。本文说明**当前程序能识别哪些审计/记账错误、需要什么数据、格式限制**，便于随机生成模拟数据做测试。

> 重要：当前程序只做**机器核对**，不做数据清洗、不做影像/OCR、不做外部查验、不做 AI 建议或人类终判；任何"通过"都不构成审计结论。所有金额为**整数分**，日期为 **YYYY-MM-DD**，币种 **CNY**。

---

## 1. 两类输入包（互相独立，也可一起用）

| 包 | 用途 | 根目录 | 校验器 |
| --- | --- | --- | --- |
| **A. 业务与凭证输入（task043）** | 账证（附件核对）+ 账实（银行流水） | `data/evidence_inputs/task043_v1_1/` | `scripts/input_contract_v1.py` |
| **B. 总账账套（GL v1）** | 借贷记账法六类核对（凭证/试算/账证/账账/账表/账实） | `data/evidence_inputs/gl_v1/` | `scripts/gl_input_contract_v1.py` |

**包 A 的账务台账是固定的**（`data/batches/task027r1_run_04/batch_normal`，见 §3.5），包 A 的凭证/流水必须引用这些账务 ID 与金额，否则契约或核对会报错。**当前 CLI 不支持替换业务台账 Excel**（`run_runtime_demo.py` 里批次路径是常量）；若要测其他业务数据，需要另行改造（见 §9）。

---

## 2. 包 A：task043 输入

目录结构（8 个文件 + `input_manifest.json`）：

```
task043_v1_1/
├─ input_manifest.json
├─ bank/transactions.json
├─ links/index.json
├─ reports/placeholders.json        # 内容可为 {}；占位文件
└─ vouchers/
   ├─ invoices.json
   ├─ contracts.json
   ├─ goods_receipts.json
   ├─ approvals.json
   └─ bank_receipts.json
```

### 2.1 `input_manifest.json`

| 字段 | 要求 |
| --- | --- |
| `input_version` | `task043-input-1.0` 或 `task043-input-1.1`（未知版本整包拒绝，`MANIFEST_VERSION`） |
| `batch_id` | 必须等于账务台账的批次 ID：`batch_normal` |
| `entity` | 必须含 `company`（澄明商贸有限公司）、`currency`（CNY）、`period_start`/`period_end`/`cutoff_date`（2026-09-01 / 2026-09-30 / 2026-09-30） |
| `files` | 数组，逐项 `relative`（§2 的 8 个相对路径）、`byte_size`（整数）、`sha256`（64 位小写十六进制），**必须与实际文件一致** |

### 2.2 凭证（5 类，每类一个 JSON 数组）

所有记录**字段闭合**：只允许下表字段，出现额外字段即 `UNKNOWN_FIELD`。

| 类型（文件） | 必填字段 |
| --- | --- |
| `INVOICE`（vouchers/invoices.json） | `voucher_id`、`invoice_no`、`issue_date`、`seller_supplier_id`、`seller_name`、`buyer_name`、`amount_cents`、`tax_cents`、`total_cents`、`currency` |
| `CONTRACT`（vouchers/contracts.json） | `voucher_id`、`contract_no`、`sign_date`、`counterparty_supplier_id`、`counterparty_name`、`amount_cents`、`currency` |
| `BANK_RECEIPT`（vouchers/bank_receipts.json） | `voucher_id`、`receipt_no`、`bank_txn_id`、`txn_date`、`amount_cents`、`direction`（`PAY`/`REFUND`）、`counterparty_name`、`counterparty_account`、`currency` |
| `APPROVAL`（vouchers/approvals.json） | `voucher_id`、`approval_no`、`approval_date`、`payment_id`、`amount_cents`、`status`（必须 `APPROVED`） |
| `GOODS_RECEIPT`（vouchers/goods_receipts.json） | `voucher_id`、`gr_no`、`accept_date`、`supplier_id`、`amount_cents`、`currency` |

校验要点：
- `amount_cents`/`tax_cents`/`total_cents` 必须是**严格整数**（浮点、字符串、布尔都拒绝，`TYPE`/`AMOUNT`）；
- 发票 `total_cents` 必须等于 `amount_cents + tax_cents`（否则 `ARITHMETIC`）；
- `voucher_id` 全局唯一（`ID_DUPLICATE`）；
- 日期必须真实存在且在期间内（`DATE_FORMAT`/`DATE_RANGE`）；币种必须 CNY（`CURRENCY`）；
- 发票 `buyer_name` 必须等于清单企业名（`ENTITY`）。

### 2.3 关联索引 `links/index.json`

数组，每条：

| 字段 | 要求 |
| --- | --- |
| `link_id` | 唯一字符串 |
| `link_type` | 六种之一：`AP_INVOICE`、`AP_CONTRACT`、`AP_GOODS_RECEIPT`、`PAYMENT_APPROVAL`、`PAYMENT_BANK_RECEIPT`、`REFUND_BANK_RECEIPT` |
| `ledger_type` | 必须与 `link_type` 匹配（`AP` / `PAYMENT` / `REFUND`，否则 `LINK_TYPE_MISMATCH`） |
| `ledger_id` | 必须存在于固定台账（AP01 / P01 / P02 / R01 等，否则引用错误） |
| `voucher_id` | 必须存在于对应凭证文件，且类型匹配 |

覆盖要求（缺失会在账证核对中报 `MISSING_VOUCHER`）：
- 每个应付单：至少 `AP_INVOICE`、`AP_CONTRACT`、`AP_GOODS_RECEIPT`；
- 每笔付款：`PAYMENT_APPROVAL`、`PAYMENT_BANK_RECEIPT`；
- 每笔退款：`REFUND_BANK_RECEIPT`。

### 2.4 银行流水 `bank/transactions.json`

数组，每条字段：`bank_txn_id`、`txn_date`、`direction`（`OUT`/`IN`）、`amount_cents`、`counterparty_name`、`counterparty_account`、`summary`、`reference`。`reference` 通常是账务 ID（如 `P01`）或 `bank_reference`。

### 2.5 固定业务台账（包 A 必须匹配）

| 表 | 关键行 |
| --- | --- |
| suppliers | S001 甲供应商；S002 乙收款对象 |
| payables | AP01，S001，2026-09-05，5,000.00 元（500000 分） |
| payments | P01（PAY，5,000.00，B001）、P02（PAY，5,000.00，B002）、R01（REFUND 对应 P02，1,000.00，BR001） |
| allocations | A01（P01→AP01 5,000.00）、A02（P02→AP01 5,000.00）、AR01（R01→AP01 1,000.00，原 A02） |

净付款 9,000.00 − 应付 5,000.00 = **超额 4,000.00**（R02 线索）。

### 2.6 校验命令

```powershell
.venv\Scripts\python.exe -B scripts\input_contract_v1.py `
  --input data\evidence_inputs\task043_v1_1 `
  --out  data\runtime_initial_judgment_recording_tests\task043_check_01 `
  --ledger-db data\sqlite_tests\task042_dsh_01\normal\runtime.sqlite3
```

- `--out` 必须从未存在；成功输出 `ACCEPTED` + registry，失败输出 `REJECTED`（逐条 `code/field/detail`），**exit 1**，整包退回、不修复。
- `--ledger-db` 是固定批次的账务库；清单 `batch_id` 必须与它一致。随机数据请保持 `batch_normal` 与 §2.5 的 ID/金额，否则会被引用/金额核对拒绝或判差异。

---

## 3. 包 B：GL v1 总账账套

目录 `data/evidence_inputs/gl_v1/`，**10 个文件**：

| 文件 | 关键结构 |
| --- | --- |
| `chart_of_accounts.json` | `{"version":"gl-1.0","accounts":[{"code":"1001","name":"库存商品","type":"ASSET","direction":"DEBIT"}, …]}`；科目：1001 库存商品、1002 银行存款、2202 应付账款、3001 实收资本 |
| `journal_entries.json` | `{"version","period","entries":[{"entry_id","date","summary","lines":[{"account","debit_cents","credit_cents","description"}],"attachments":["V-…"]}]}` |
| `trial_balance.json` | `{"version","period","rows":[{"account","opening_debit","opening_credit","debit_cents","credit_cents","closing_debit","closing_credit"}],"totals"}` |
| `ledger_general.json` | `{"version","period","accounts":[{"account","debit_cents","credit_cents","closing_debit","closing_credit"}]}` |
| `ledger_subsidiary.json` | `{"version","period","subsidiaries":[{"account","closing_debit","closing_credit","entries":[{"entry_id","date","debit_cents","credit_cents","balance_debit","balance_credit"}]}]}` |
| `balance_sheet.json` | `{"version","period","assets":[{"item","amount_cents"}],"liabilities":[…],"equity":[…],"total_assets_cents","total_liabilities_equity_cents"}` |
| `bank_statement.json` | `{"version","period","account","opening_balance_cents","closing_balance_cents","entries":[{"date","direction":"OUT/IN","amount_cents","reference"}]}` |
| `bank_journal.json` | 同银行对账单结构（日记账） |
| `attachment_index.json` | `{"version","attachments":[{"voucher_id","voucher_type","amount_cents","date"}]}` |
| `gl_manifest.json` | `{"version":"gl-1.0","period","batch":{"batch_id","source_workbook","batch_manifest_sha256"},"generator_version","files":{文件名:{"byte_size","sha256"}}}` |

示例数字（happy path）：4 张凭证、借贷各 16,000.00；期初 20,000.00=20,000.00；期末库存 5,000.00 借、银行 11,000.00 借、应付 **4,000.00 借**、实收 20,000.00 贷；报表 20,000.00=20,000.00（应付 0 / 预付 4,000.00 重分类）；银行 20,000+1,000−10,000=11,000.00。

校验命令：

```powershell
.venv\Scripts\python.exe -B scripts\gl_input_contract_v1.py --gl-root data\evidence_inputs\gl_v1
```

失败 exit 1，错误码如 `GL-ENTRY-UNBALANCED`、`GL-TB-EQUATION`、`GL-BS-EQUATION`、`GL-BANK-END`、`GL-ATTACH-TYPE` 等（完整列表见 §5.4）。

---

## 4. 错误识别矩阵（当前程序真正能识别的）

### 4.1 契约层拒绝（包 A，整包退回）

| 错误码 | 触发 |
| --- | --- |
| `MANIFEST_VERSION` | `input_version` 不在 1.0/1.1 |
| `MANIFEST_BATCH` / `MANIFEST_ENTITY` | 批次/企业/期间/币种与台账不符 |
| `MANIFEST_FILES_SHAPE` / `MANIFEST_FILE_ENTRY` / `MANIFEST_FILE_SET` | 清单 files 形状、路径、文件集合不符 |
| `MANIFEST_HASH_FORMAT` / `MANIFEST_SIZE` / 哈希不符 | 清单逐文件字节数/SHA 与实际不符 |
| `REQUIRED` / `UNKNOWN_FIELD` | 缺必填字段 / 多出未允许字段 |
| `TYPE` / `AMOUNT` | 金额非严格整数 / 小于下限 |
| `DATE_FORMAT` / `DATE_RANGE` | 日期格式或越界 |
| `CURRENCY` / `ENTITY` | 币种或企业名不符 |
| `ID_DUPLICATE` | 凭证/链接 ID 重复 |
| `ARITHMETIC` | 发票 `total_cents ≠ amount+tax` |
| `ENUM` | 付款方向非 PAY/REFUND、审批状态非 APPROVED、银行方向非 OUT/IN |
| `LINK_TYPE_MISMATCH` | `link_type` 与 `ledger_type`/凭证类型不匹配 |
| `LEDGER_REF` 等 | 引用不存在/不匹配的账务或流水 |

### 4.2 账证核对（`voucher_match_report.json`）

分类（`CLASSES`）：`MATCHED`、`AMOUNT_MISMATCH`、`TAX_TOTAL_MISMATCH`、`DATE_MISMATCH`、`COUNTERPARTY_MISMATCH`、`STATUS_MISMATCH`、`DIRECTION_MISMATCH`、`SUM_MISMATCH`、`MISSING_VOUCHER`、`EXTRA_VOUCHER`、`REFUND_LINK_MISMATCH`。

结论：全 `MATCHED` → `ALL_MATCHED`；否则 `DIFFERENCES_FOUND`（逐条 ledger_id/voucher_id/field/expected/actual）。

### 4.3 账实核对（银行，`bank_reconcile_report.json`）

分类：`MATCHED`、`AMOUNT_MISMATCH`、`DATE_MISMATCH`、`COUNTERPARTY_MISMATCH`、`DIRECTION_MISMATCH`、`REFERENCE_CONFLICT`、`DUPLICATE_BANK_LINE`、`DUPLICATE_MATCH`、`LEDGER_UNMATCHED`、`BANK_UNMATCHED`。
匹配依据 `basis`：`REFERENCE_INDEX`、`REFERENCE_BANK_REFERENCE`、`TRIPLE`；另核对期间合计（OUT/IN）与未达账项（账有实无/实有账无）。

### 4.4 GL 契约错误码

`GL-FILE-MISSING`、`GL-JSON`、`GL-VERSION`、`GL-PERIOD`、`GL-BATCH`、`GL-PATH`、`GL-MANIFEST-SIZE`、`GL-MANIFEST-SHA`、`GL-ACCOUNT-UNKNOWN`、`GL-AMOUNT-TYPE`、`GL-DEBIT-CREDIT`、`GL-ENTRY-UNBALANCED`、`GL-PERIOD-UNBALANCED`、`GL-TB-EQUATION`、`GL-TB-TOTALS`、`GL-TB-CLOSING`、`GL-GL-AMOUNT`、`GL-GL-CLOSING`、`GL-SUB-GL`、`GL-SUB-TOTAL`、`GL-SUB-CLOSING`、`GL-BS-EQUATION`、`GL-BS-RECLASS`、`GL-BANK-END`、`GL-BANK-JOURNAL`、`GL-ATTACH-MISSING`、`GL-ATTACH-TYPE`、`GL-ATTACH-AMOUNT`。

### 4.5 GL 六类核对（`reconcile_gl_v1.py`）

| check id | 查什么 |
| --- | --- |
| `journal_balance` | 逐张凭证借贷相等、期间借贷合计相等 |
| `trial_balance` | 期初/本期/期末借贷两两相等；逐科目 期初+借−贷=期末 |
| `ledger_to_voucher` | 总账/明细账发生额 = 凭证按科目汇总 |
| `general_to_subsidiary` | 总账期末 = 明细账合计；**并与科目余额表逐科目一致（含无明细账科目）**；明细逐笔余额滚动 |
| `ledger_to_report` | 科目余额表 = 报表项目（含应付借方 4,000 重分类预付 4,000）；**报表合计=分项之和、资产=负债+权益** |
| `bank_reconcile` | 日记账 = 对账单；期初+收入−支出=期末；未达账项 |
| `attachments`（附加） | 凭证附件存在、类型/金额匹配 |

结论：全 `MATCHED` → `ALL_MATCHED`（exit 0）；任一差异 → `DIFFERENCES`（exit 1），findings 含字段级明细。

### 4.6 其他保护

- 源工作簿哈希漂移 → 索引生成拒绝（`source_drift`）；
- 清单被篡改 → `MANIFEST_*` / `GL-MANIFEST-*`；
- 审阅记录：版本不符、未知记录、非法状态、非待审阅缺审阅人/日期/问题、HTML 注入 → 合并命令 exit 1；
- `run_all.py`：任一步失败即停，`run_summary.failed_step` 指出步骤（`input_contract`、`gl_contract`、`demo`、`gl_reconcile`、`trace_index`、`site`、`workbook`）。

---

## 5. 当前**不能**识别的（生成数据时不要期待）

- 凭证/流水的**真实性**、发票真伪、外部查验、银行函证、监盘/盘点；
- 影像/扫描件、OCR、发票版式、银行对账单版式适配；
- 未入账负债、截止测试、期后付款、账龄分析、关联方/舞弊；
- 数据清洗（不规整整包退回，不做修复）；
- 除固定台账外的其他业务 Excel（批次路径硬编码，见 §9）；
- AI 建议、人类终判、真实批准/强认证。

---

## 6. 推荐测试配方

### 6.1 Happy path

按 §2.5 与 §3 生成完整数据，两个契约 exit 0；账证 `ALL_MATCHED`；账实 `ALL_MATCHED`；GL 六类 `ALL_MATCHED`。

### 6.2 单点错误注入（每次只改一处，保持契约通过）

| # | 改什么 | 预期识别 |
| --- | --- | --- |
| 1 | 发票 `amount_cents` 改 1 分（total 同步改以过契约） | 账证 `AMOUNT_MISMATCH` 或 `SUM_MISMATCH` |
| 2 | 发票 `total ≠ amount+tax` | 契约 `ARITHMETIC`（整包退回） |
| 3 | 付款日期改晚 1 天（审批/回单同步） | 账证 `DATE_MISMATCH` |
| 4 | 付款对象名改错 | 账证 `COUNTERPARTY_MISMATCH` |
| 5 | 删除某付款的审批链接/文件 | 账证 `MISSING_VOUCHER` |
| 6 | 增加一张无链接的发票 | 账证 `EXTRA_VOUCHER` |
| 7 | 退款 `original_payment_id` 改错 | 账证 `REFUND_LINK_MISMATCH` |
| 8 | 银行流水金额改 1 分 | 账实 `AMOUNT_MISMATCH` |
| 9 | 银行流水方向 OUT↔IN | 账实 `DIRECTION_MISMATCH` |
| 10 | 两条流水相同 reference | 账实 `REFERENCE_CONFLICT` / `DUPLICATE_BANK_LINE` |
| 11 | 删除一条流水 | 账实 `LEDGER_UNMATCHED` |
| 12 | 增加一条无对应账务的流水 | 账实 `BANK_UNMATCHED` |
| 13 | GL 某凭证贷方 +1 分 | GL `journal_balance` 差异 |
| 14 | GL 余额表某科目期末 +1 分 | `trial_balance` + `ledger_to_report` |
| 15 | GL 总账某科目期末 +1 分（含无明细账科目） | `general_to_subsidiary` |
| 16 | GL 报表合计 +1 分（分项不动） | `ledger_to_report`（报表内部平衡） |
| 17 | GL 银行对账单期末 +1 分 | `bank_reconcile` |
| 18 | GL 删除凭证附件引用 | `attachments` |
| 19 | 清单 `sha256` 改错 | 契约 `MANIFEST_HASH_FORMAT` / 哈希不符 |
| 20 | `input_version` 改未知值 | `MANIFEST_VERSION` |

> 建议：先生成 happy path 跑通，再逐条注入；每条记录"改了什么、预期 code/status、实际输出"。

---

## 7. 输出与退出码

| 命令 | 成功 | 失败 |
| --- | --- | --- |
| `input_contract_v1.py` | exit 0、`ACCEPTED` + registry | exit 1、`REJECTED` + reasons；exit 2 参数/路径 |
| `gl_input_contract_v1.py` | exit 0 | exit 1 精确 code；exit 2 参数 |
| `voucher_match_v1.py` / `bank_reconcile_v1.py` | exit 0 全 MATCHED | exit 1 有差异 |
| `reconcile_gl_v1.py` | exit 0 `ALL_MATCHED` | exit 1 `DIFFERENCES` |
| `run_all.py` | exit 0 `SUCCESS` + `outputs/<run_id>/index.html` | exit 1 `failed_step`；exit 2 目录冲突/参数 |

所有输出目录必须**从未存在**；不要覆盖既有证据。

---

## 8. 已知限制（重要）

1. **业务台账固定**：`run_runtime_demo.py` 的批次路径是常量 `data/batches/task027r1_run_04/batch_normal`；`run_all` 的 `batch_dir` 只用于只读校验，不能替换演示批次。随机测试请围绕 §2.5 的固定 ID/金额做凭证/流水变体；若要换业务台账，需要改造（新卡）。
2. **契约绑定固定账务库**：`input_contract_v1.py --ledger-db data/sqlite_tests/task042_dsh_01/normal/runtime.sqlite3`；`batch_id` 必须 `batch_normal`。
3. **金额单位**：整数分；不要用元、浮点或千分位字符串。
4. **字段闭合**：不允许额外字段（会被 `UNKNOWN_FIELD` 拒绝）。
5. **不做数据清洗**：任何不规整都整包退回。
6. **不接影像/OCR/外部查验/AI/终判**。

---

## 9. 最小示例（可直接改数值）

`links/index.json`：

```json
[
  {"link_id":"L-0001","link_type":"AP_INVOICE","ledger_type":"AP","ledger_id":"AP01","voucher_id":"V-INV-0001"},
  {"link_id":"L-0002","link_type":"AP_CONTRACT","ledger_type":"AP","ledger_id":"AP01","voucher_id":"V-CTR-0001"},
  {"link_id":"L-0003","link_type":"AP_GOODS_RECEIPT","ledger_type":"AP","ledger_id":"AP01","voucher_id":"V-GR-0001"},
  {"link_id":"L-0004","link_type":"PAYMENT_APPROVAL","ledger_type":"PAYMENT","ledger_id":"P01","voucher_id":"V-APR-0001"},
  {"link_id":"L-0005","link_type":"PAYMENT_BANK_RECEIPT","ledger_type":"PAYMENT","ledger_id":"P01","voucher_id":"V-BR-0001"},
  {"link_id":"L-0006","link_type":"REFUND_BANK_RECEIPT","ledger_type":"REFUND","ledger_id":"R01","voucher_id":"V-BR-0002"}
]
```

`bank/transactions.json`：

```json
[
  {"bank_txn_id":"BT-2026-0001","txn_date":"2026-09-10","direction":"OUT","amount_cents":500000,
   "counterparty_name":"甲供应商","counterparty_account":"6222020200000001",
   "summary":"货款支付 P01","reference":"P01"}
]
```

GL 凭证：

```json
{"version":"gl-1.0","period":{"period_start":"2026-09-01","period_end":"2026-09-30","cutoff_date":"2026-09-30"},
 "entries":[{"entry_id":"记-001","date":"2026-09-05","summary":"采购入库并确认应付",
   "lines":[
     {"account":"1001","debit_cents":500000,"credit_cents":0,"description":"库存商品入库"},
     {"account":"2202","debit_cents":0,"credit_cents":500000,"description":"确认应付 AP01"}],
   "attachments":["V-INV-0001","V-CTR-0001","V-GR-0001"]}]}
```

---

## 10. 一句话总结

**当前程序能识别：契约层的格式/引用/算术/清单错误，账证的五类附件不符与缺失/多余，账实的金额/日期/对象/方向/引用冲突与未达，GL 的借贷/试算/账证/账账/账表/账实/附件共七类勾稽错误；数据必须是整数分、ISO 日期、字段闭合、引用固定台账（batch_normal）或 GL 十文件；不做清洗/影像/外部查验/AI/终判。**
