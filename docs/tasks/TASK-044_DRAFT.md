# TASK-044：账证相符 L1（凭证字段级核对）与抽样核对底稿

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-043 ACCEPTED**（输入契约 v1 与输入登记）。依据 `DSH-SCOPE-20261017-02`：只做**字段级 L1**；不做影像/OCR/外部查验；不采集人类核对结论；不采集、不虚构任何人类字段。

## 1. 起点与允许写入

起点：TASK-043 接受基线（输入根 `data/evidence_inputs/task043_v1/`、`input_registry.json` 及其接受快照）。账务侧只读复用一份已接受运行证据中的规范化账务数据（`.../normal.load/normalized.json`，记录相对路径与 sha256，并核对其 bindings 与本批次/期间一致）。

允许新增：`scripts/voucher_match_v1.py`（唯一新增代码）、`tests/test_voucher_match_v1.py`、`docs/ACCOUNT_VOUCHER_MATCH_GUIDE.md`、`docs/EXEC_REPORT_044.md`；证据根 `data/runtime_initial_judgment_recording_tests/task044_*`。**不允许修改任何既有文件**（changed=0）；不改演示脚本（演示集成留待后续卡）；不写输入根、批次、账务、凭证、银行数据。

## 2. 匹配规则（L1，全部以输入索引为基础）

对账务侧的每个对象，按 `links/index.json` 取对应凭证，逐字段比对：

| 账务对象 | 凭证 | 核对内容 |
| --- | --- | --- |
| 应付单 AP | 发票（≥1 张） | 发票 `total_cents` 合计 == 应付 `payable_amount_cents`；每张 `seller_supplier_id` == 应付 `supplier_id`；发票日期 ≤ 截至日 |
| 应付单 AP | 合同 | 合同 `amount_cents` == 应付金额；`counterparty_supplier_id` == 应付 `supplier_id` |
| 应付单 AP | 入库/验收单 | 入库单 `amount_cents`（多张合计）== 应付金额；`supplier_id` 一致 |
| 付款 PAY | 审批单 | 1:1；金额相等；`status==APPROVED`；`payment_id` 一致 |
| 付款 PAY | 银行回单（凭证） | 1:1；金额、日期、收款方名称一致；`direction==PAY`；回单 `bank_txn_id` 与付款 `bank_reference` 一致（若索引声明） |
| 退款 REFUND | 银行回单（凭证） | 1:1；金额、日期、`direction==REFUND`；关联原付款与原分摊（`original_payment_id`/`original_allocation_id`）与退款凭证一致 |

索引完整性与唯一性已在 TASK-043 契约层校验；本卡只做**语义核对**（金额/税额/日期/对方/状态/方向/求和）。金额一律整数分精确比较；ID 按原字符串比较（不去空格、不改大小写、不抹前导零）。

## 3. 输出（每项状态 + 差异分类 + 抽样底稿）

分类枚举固定：`MATCHED`、`AMOUNT_MISMATCH`、`TAX_TOTAL_MISMATCH`、`DATE_MISMATCH`、`COUNTERPARTY_MISMATCH`、`STATUS_MISMATCH`、`DIRECTION_MISMATCH`、`SUM_MISMATCH`（多张凭证合计不符）、`MISSING_VOUCHER`（账有证无）、`EXTRA_VOUCHER`（证有账无/索引指向未使用凭证）、`REFUND_LINK_MISMATCH`。

输出 `voucher_match_report.json` + `voucher_match_report.md`：
- 全量逐项状态（AP/PAY/REFUND × 凭证类型）；
- 差异清单：账务 ID、凭证 ID、字段、实际值、预期值、分类；
- 未匹配清单：账有证无、证有账无；
- **抽样底稿**（程序选取，非审计抽样方法学）：对 R02 线索涉及的 AP01/P01/P02/R01，列出每条凭证核对证据与差异；**“核对结论”列必须为空**（不采集、不虚构人类字段），并注明“人类核对结论需另行授权与登记”。

只读纪律：本卡进程不得写账务/凭证/银行/批次；证据根只写本次报告与命令输出。

## 4. 测试与证据

- 正常：全部 MATCHED（合成数据设计为一致），R02 抽样底稿完整。
- 负例（复制输入副本注入，每类一条，精确字段）：金额差 1 分、税额合计不符、日期越界/错日、对方名称不一致、审批未通过、方向错、多发票合计不符、账有证无、证有账无、退款关联原分摊错。
- 每例保留命令、stdout/stderr、退出码、报告与差异；原输入与既有证据不改。
- 结论必须写：L1 字段级核对；未查看影像、未做发票/回单外部查验、不证明凭证真实。

## 5. 保护与停止

定稿后一次全树扫描，基线 = TASK-043 接受基线；既有 changed 必须为 0；新增仅限 §1 与架构端已知增量（决策记录与本卡/043/045 卡短语路径）；missing/读取错误/未登记新增 0；139 历史损失等继续冻结。交付后停止待验收；不改演示、不改看板、不推进 TASK-045（由架构端验收后另行放行）。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`。
