# 账证相符 L1 核对指南（凭证字段级）

标识：`task044-voucher-match-1.0`。实现：`scripts/voucher_match_v1.py`（唯一新增核对代码）。
前置：TASK-043 输入契约 v1（输入根 `data/evidence_inputs/task043_v1/` 与登记）已接受。
依据：`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`（`DSH-SCOPE-20261017-02`）。

边界：只做**字段级 L1**；不查看影像、不做 OCR/清洗、不做发票/回单外部查验、不做无索引模糊匹配、
不采集、不虚构人类核对结论。合成数据；`real_approval=null`、真实独立初判未保存、
`next_step_allowed=false`、`ai_enabled=false`；不写账务/凭证/银行/批次，只写本次证据根。

## 1. 用法

```powershell
.venv\Scripts\python.exe -B scripts\voucher_match_v1.py `
  --input data\evidence_inputs\task043_v1 `
  --ledger-normalized data\runtime\task042_dsh_01\normal.load\normalized.json `
  --out data\runtime_initial_judgment_recording_tests\task044_<轮次>\task044_normal
```

- `--input`：TASK-043 v1 输入根（只读）。
- `--ledger-normalized`：已接受运行证据的 `normal.load/normalized.json`（只读）；同目录若有
  `started.json`/`artifacts.json` 则校验绑定：`batch_id`、`source_batch_relative`、
  `run_binding.input.file_sha256`、`normalized_file_sha256`、`mode=DEVELOPMENT_TEST_ONLY`；
  并校验 `source.input_sha256` 与本批次工作簿字节一致。
- `--out`：必须从未存在、位于 `data/runtime_initial_judgment_recording_tests/` 下且以 `task044_` 开头。
- 退出码：`0` 全部 MATCHED 且无账有证无/证有账无；`1` 存在差异（报告照常输出）；`2` 参数/绑定/环境错误。

## 2. 匹配规则（L1，全部以输入 `links/index.json` 为唯一关联基础）

| 账务对象 | 凭证 | 核对内容 |
| --- | --- | --- |
| 应付 AP | 发票（≥1） | 发票 `total_cents` 合计 == 应付 `payable_amount_cents`；每张 `seller_supplier_id` == 应付 `supplier_id`；`issue_date` ≤ 2026-09-30；`amount+tax==total` |
| 应付 AP | 合同 | `amount_cents` == 应付金额；`counterparty_supplier_id` == 应付 `supplier_id` |
| 应付 AP | 入库/验收单（多张合计） | `amount_cents` 合计 == 应付金额；`supplier_id` 一致 |
| 付款 PAY | 审批单（1:1） | 金额相等；`status==APPROVED`；`payment_id` 一致 |
| 付款 PAY | 银行回单（1:1） | 金额、`txn_date` 与付款日期、收款方名称一致；`direction==PAY` |
| 退款 REFUND | 银行回单（1:1） | 金额、日期、`direction==REFUND`；账内原付款 `original_payment_id` 与原分摊 `original_allocation_id` 存在且互相一致（含退款分摊金额） |

金额整数分精确比较；ID 按原字符串比较（不去空格、不改大小写、不抹前导零）。
“必需凭证类型”按输入**全局声明的 link_type** 判定：输入里出现过某类 link，则该类凭证对相应账务对象为必需；
未出现过则不要求（不把“输入未提供”误判为“账有证无”，也不缩小已声明范围）。

## 3. 分类（固定枚举）

`MATCHED`、`AMOUNT_MISMATCH`、`TAX_TOTAL_MISMATCH`、`DATE_MISMATCH`、`COUNTERPARTY_MISMATCH`、
`STATUS_MISMATCH`、`DIRECTION_MISMATCH`、`SUM_MISMATCH`、`MISSING_VOUCHER`、`EXTRA_VOUCHER`、
`REFUND_LINK_MISMATCH`。

- 单张凭证金额不符 → `AMOUNT_MISMATCH`；多张凭证合计不符 → `SUM_MISMATCH`。
- 发票 `amount+tax != total` → `TAX_TOTAL_MISMATCH`（契约层已拒绝，本层作防御性复核）。
- 账有证无 → `MISSING_VOUCHER`；证有账无（凭证未被任何索引引用）与重复引用 → `EXTRA_VOUCHER`。
- 退款账内链路问题（原付款/原分摊缺失或不一致）→ `REFUND_LINK_MISMATCH`。
- 审批单 `payment_id` 与付款不一致 → 记 `MISSING_VOUCHER`（该付款无有效审批单），差异清单保留字段级证据。
- 契约 v1 的 link 未声明 `bank_txn_id` 与付款 `bank_reference` 的直接绑定，故该可选比对不触发；
  如未来契约声明该字段，再启用。

## 4. 输出

`voucher_match_report.json`：
- `input`（输入根、input_version、manifest 身份、实体）与 `ledger`（normalized/started/artifacts 身份、
  批次与绑定核对结果、工作簿 sha256）；
- `items[]`：全量逐项状态（AP/PAY/REFUND × 凭证类型），含 `ledger_amount_cents`、`voucher_ids`、
  `status`、`differences[]`；
- `differences[]`：账务类型/账务 ID/凭证 ID/凭证类型/字段/实际/预期/分类；
- `missing_vouchers[]`（账有证无）与 `extra_vouchers[]`（证有账无/索引指向未使用凭证）；
- `summary`（逐项状态与分类计数、差异合计）；
- `r02_sampling`：程序选取 R02 线索涉及的 AP01/P01/P02/R01，逐条列出账务记录、凭证记录、核对状态与差异；
  **`human_conclusion` 恒为 null**（不采集、不虚构人类字段；人类核对结论需另行授权与登记）；
- `conclusion`（`ALL_MATCHED` / `DIFFERENCES_FOUND`）、`verification_level=L1_FIELD_LEVEL_NO_EXTERNAL_VERIFICATION`。

`voucher_match_report.md`：同一内容的可阅读版本，含“核对结论”列为空的抽样底稿。

## 5. 合成数据说明（重要）

TASK-043 接受输入为契约校验而设计：凭证覆盖 AP01（发票/合同/入库）、P01（审批/回单）、R01（退款回单）；
**P02（R02 超付的重复付款）在 TASK-043 输入中没有审批单与银行回单**。因此：

- 直接对接受输入运行 → 如实报 **2 条 `MISSING_VOUCHER`**（P02 账有证无），退出码 1；这是数据事实，
  不是匹配器缺陷，也不是审计结论。
- 卡 §4 要求的“正常：全部 MATCHED”以**一致夹具**演示：在证据根内复制接受输入并补齐 P02 审批单
  （V-APR-0002）、银行回单（V-BR-0003）与两条索引，更新 manifest 哈希；原输入根只读、不变。
  该夹具仅作为测试证据，不改变 TASK-043 接受输入，也不构成对真实批次的设计。

## 6. 测试

```
.venv\Scripts\python.exe -B tests\test_voucher_match_v1.py `
  --out-dir data\runtime_initial_judgment_recording_tests\task044_run_01
```

- 正常（一致夹具）：8/8 项 `MATCHED`、无差异、无账有证无/证有账无，R02 抽样底稿完整；退出码 0。
- 规范输入对照：2 条 `MISSING_VOUCHER`（P02 审批/回单），如实保留。
- 负例（12 类，复制夹具注入，每类一条）：金额差 1 分、税额合计不符、日期越界、错日、对方名称不一致、
  审批未通过、方向错、多发票合计不符、账有证无、证有账无、退款原分摊错、重复审批（EXTRA）。
- 每例保留输入副本、命令、stdout/stderr、退出码、报告与差异；原输入与既有证据前后字节不变。
