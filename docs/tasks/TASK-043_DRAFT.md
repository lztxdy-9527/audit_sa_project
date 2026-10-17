# TASK-043：输入契约 v1 与合成输入扩展（账 / 证 / 银 / 表占位）

分类 C；Architect 设计、执行端实施、Architect 独立验收。依据 `docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`（`DSH-SCOPE-20261017-02`）：不做清洗/OCR/银行格式适配；只接受**已规整输入**；不合契约**整批拒收**；优先账证、账实。

本卡只做**输入契约与输入登记**，不做任何匹配、不出核对底稿（分别由 TASK-044/045 承担），不改演示脚本与既有实现。真实批准 `null`，全部合成数据。

## 1. 起点与允许写入

起点：最新接受身份 `data/reviews/project_smoke_gpt_20261017_183235/review_result.json`（173950 项 / `6f8c2787…`）；适配器 `f5c7c396…`、演示脚本 `abc25c4b…`、测试/指南等按该接受快照只读。

允许新增：`scripts/input_contract_v1.py`（唯一新增代码）、`tests/test_input_contract_v1.py`、`docs/INPUT_CONTRACT_V1.md`、`docs/EXEC_REPORT_043.md`；合成输入根 `data/evidence_inputs/task043_v1/`（见 §2）；证据根 `data/runtime_initial_judgment_recording_tests/task043_*`。**不允许修改任何既有文件**（本卡 changed 必须为 0）；只读引用 `data/batches/task027r1_run_04/batch_normal` 与既有运行证据，不写入。

## 2. 输入根与文件（v1，固定）

`data/evidence_inputs/task043_v1/` 下恰这些文件（多一个未知文件即拒收）：

```
input_manifest.json
vouchers/invoices.json      vouchers/contracts.json   vouchers/bank_receipts.json
vouchers/approvals.json     vouchers/goods_receipts.json
links/index.json
bank/transactions.json
reports/placeholders.json   （仅为账表预留，内容为空数组，本卡不做账表）
```

**input_manifest.json**：`input_version="task043-input-1.0"`、`batch_id="batch_normal"`、`entity`（澄明商贸有限公司 / CNY / 2026-09-01～2026-09-30 / 截至 2026-09-30）、`files[]`（relative、byte_size、sha256）。

**凭证 schema（每条记录必填标 ★）**：
- 发票 `INVOICE`：★voucher_id、★invoice_no、★issue_date、★seller_supplier_id、★seller_name、★buyer_name、★amount_cents（整数分）、★tax_cents、★total_cents（= amount+tax 精确）、★currency（CNY）。
- 合同 `CONTRACT`：★voucher_id、★contract_no、★sign_date、★counterparty_supplier_id、★counterparty_name、★amount_cents、★currency。
- 银行回单（凭证）`BANK_RECEIPT`：★voucher_id、★receipt_no、★bank_txn_id、★txn_date、★amount_cents、★direction（PAY/REFUND）、★counterparty_name、★counterparty_account、★currency。
- 付款审批单 `APPROVAL`：★voucher_id、★approval_no、★approval_date、★payment_id、★amount_cents、★status（APPROVED）。不记录审批人身份，不做强认证。
- 入库/验收单 `GOODS_RECEIPT`：★voucher_id、★gr_no、★accept_date、★supplier_id、★amount_cents、★currency。

**银行流水 `bank_txn`**：★bank_txn_id、★txn_date、★direction（OUT/IN）、★amount_cents、★counterparty_name、★counterparty_account、★summary、reference（可空，可为 payment_id 或 bank_reference）。

**关联索引 `links/index.json`**：每条 `{link_id, link_type, ledger_type, ledger_id, voucher_id}`；`link_type ∈ {AP_INVOICE, AP_CONTRACT, AP_GOODS_RECEIPT, PAYMENT_APPROVAL, PAYMENT_BANK_RECEIPT, REFUND_BANK_RECEIPT}`；`ledger_type ∈ {AP, PAYMENT, REFUND}`。索引由输入提供（ERP 附件/关联表口径），本卡只校验引用完整性，不做匹配。

## 3. 校验与拒收（本卡核心）

1. 文件集合、UTF-8 JSON、记录数组、ID 唯一（voucher_id / link_id / bank_txn_id）。
2. 类型/必填/枚举；金额为**整数分**且 >0（税可 0）；日期 `YYYY-MM-DD` 且不晚于 2026-09-30；币种 CNY；实体/期间与 manifest 一致。
3. 算术：`total_cents == amount_cents + tax_cents`。
4. 清单哈希：每个文件实际字节与 `input_manifest.files` 的 byte_size/sha256 相等；`input_manifest` 自身不含自哈希。
5. 索引引用：voucher_id 存在且类型与 link_type 匹配；ledger_id 在既有批次账务数据中真实存在；同一 (link_type, ledger_id, voucher_id) 不重复。
6. **任何一条不满足 → 整批拒收**：输出 `rejection.json`（精确字段/记录/voucher_id、实际与预期、批次号），不产生登记、不修不补不猜；进程退出码非 0。拒收现场保留。
7. 通过 → 输出 `input_registry.json`（input_version、batch_id、每文件 hash、各类计数、校验结论），并做一次同缓冲读回；登记只写本卡证据根，不改输入根、不改批次。

## 4. 证据与测试

- 正常：合法 v1 输入登记成功，`input_registry.json` 含全部计数/hash；账/证/银数量与合成数据一致。
- 负例（至少 10 类，逐类一条，均整批拒收且字段精确）：缺文件、多未知文件、哈希不符、voucher_id 重复、缺必填、金额非整数/非正、`total≠amount+tax`、日期越界、币种错、索引悬挂、索引重复、ledger_id 不存在。
- 每个负例保留输入副本、命令、stdout/stderr、退出码、rejection.json；原合成输入根不改（用复制副本注入）。
- 只读纪律：校验进程不得写批次、账务、凭证、银行输入；测试命令一律 `-B`。

## 5. 保护与停止

定稿后**一次**全树扫描，基线 = 本卡起点接受快照。判据：既有 changed 必须为 0（纯新增）；新增仅限 §1 所列与架构端已知增量（`docs/decisions/DECISION_20261017_DSH_FOUR_MATCH_SCOPE.md`、`docs/tasks/TASK-043_DRAFT.md`、`TASK-044_DRAFT.md`、`TASK-045_DRAFT.md` 逐确切路径登记）；新 missing/读取错误/未登记新增/身份漂移 0。139 历史损失等继续冻结。交付后停止待独立验收；不做匹配、不改演示、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；本卡不证明凭证真实，不构成审计证据或结论。
