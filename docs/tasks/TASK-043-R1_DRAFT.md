# TASK-043-R1：输入补充 v1.1（补齐 P02 审批单与银行回单）

分类 C；Architect 制定、执行端实施、Architect 独立验收。前置：**TASK-044 ACCEPTED**（账证匹配器已接受，且已如实暴露 P02 账有证无）。本卡只补**输入数据**，不改任何代码、不改已接受的 `task043_v1`、不改演示脚本。

## 1. 背景

TASK-043 接受输入为契约校验而设计，凭证只覆盖 AP01（发票/合同/入库）、P01（审批/回单）、R01（退款回单）；**P02（R02 超付的重复付款）没有审批单与银行回单**，导致账证核对如实报 2 条 `MISSING_VOUCHER`（TASK-044 §4）。这属 TASK-043 输入规格不足（架构端卡规格问题），不是匹配器缺陷。本卡以**新输入版本 v1.1**补齐 P02 凭证，保留 v1 原样作为历史。

## 2. 允许写入（纯新增）

- 新输入根 `data/evidence_inputs/task043_v1_1/`：复制 v1 全部文件字节，只追加下列记录并重算 manifest；
- 新增回执 `docs/EXEC_REPORT_043_R1.md`；
- 证据根 `data/runtime_initial_judgment_recording_tests/task043r1_*`。

**禁止**：修改 `data/evidence_inputs/task043_v1/`（已接受历史）、任何脚本/测试/指南/卡、批次/账务/银行/Gate/历史证据；不改演示脚本。

## 3. 必须追加的确切记录（与既有账务/流水一致）

`vouchers/approvals.json` 追加：

```json
{"voucher_id":"V-APR-0002","approval_no":"APR-2026-0002","approval_date":"2026-09-09","payment_id":"P02","amount_cents":500000,"status":"APPROVED"}
```

`vouchers/bank_receipts.json` 追加：

```json
{"voucher_id":"V-BR-0003","receipt_no":"BR-2026-0003","bank_txn_id":"BT-2026-0002","txn_date":"2026-09-10","amount_cents":500000,"direction":"PAY","counterparty_name":"甲供应商","counterparty_account":"6222020200000001","currency":"CNY"}
```

`links/index.json` 追加两条：

```json
{"link_id":"L-0007","link_type":"PAYMENT_APPROVAL","ledger_type":"PAYMENT","ledger_id":"P02","voucher_id":"V-APR-0002"}
{"link_id":"L-0008","link_type":"PAYMENT_BANK_RECEIPT","ledger_type":"PAYMENT","ledger_id":"P02","voucher_id":"V-BR-0003"}
```

`input_manifest.json`：`input_version="task043-input-1.1"`，`files[]` 重算为八个数据文件的实际长度/SHA-256（manifest 自身无自哈希）；实体/期间/批次不变（澄明商贸有限公司 / CNY / 2026-09-01～2026-09-30 / 截至 2026-09-30 / batch_normal）。其余文件（发票/合同/入库单/流水/账表占位）保持与 v1 逐字节相同。

## 4. 验收证据（本卡实际运行）

1. **契约校验（复用已接受 `scripts/input_contract_v1.py`，不修改）**：对 v1.1 运行 → 退出码 0、`conclusion=INPUT_V1_ACCEPTED`、计数 INVOICE 1 / CONTRACT 1 / BANK_RECEIPT 3 / APPROVAL 2 / GOODS_RECEIPT 1（合计 8）、links 8、bank 3。
2. **交叉验证（复用已接受 `scripts/voucher_match_v1.py`，不修改）**：对 v1.1 运行 → 退出码 0、`conclusion=ALL_MATCHED`、**8/8 `MATCHED`**、差异/账有证无/证有账无 0；R02 抽样底稿含 AP01/P01/P02/R01 且 `human_conclusion` 恒 null。
3. **v1 未变**：`task043_v1` 全部文件字节与 TASK-043 接受快照一致（逐文件 SHA 对比，登记在证据）。
4. **只读**：校验器/匹配器不写输入根、批次、账务、银行、Gate/历史；测试前后字节快照一致。

## 5. 保护与停止

定稿后一次全树扫描，基线 = TASK-044 接受基线：既有 changed 必须为 0；新增仅限 §2 与架构端已知增量（本卡与 `REVIEW_TASK_044.md`）；missing/读取错误/未登记新增 0；139 历史损失等继续冻结。交付后停止待验收；不推进 TASK-045（由其前置顺序另行放行）、不改演示、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`。本卡不证明凭证真实。
