# TASK-043-R1 独立验收（DSH Architect）

结论：**ACCEPTED**（附一项已登记残差，见 §3）。2026-10-17，DSH 架构/测试验收端对"输入补充 v1.1（补齐 P02 审批单与银行回单）"独立复验。v1 未动、v1.1 内容与哈希自洽、已接受匹配器在 v1.1 上全匹配；唯一冲突是已接受校验器的版本常量硬编码（卡级冲突），已如实记录并延后到 TASK-046 一并关闭。

## 1. 交付与输入身份

- 新输入根 `data/evidence_inputs/task043_v1_1/`：manifest 1268 B / `151c35fc…`，`input_version=task043-input-1.1`，八文件哈希与字节一致；发票/合同/入库/流水/占位五个文件与 v1 **逐字节相同**；approvals 298 B、bank_receipts 731 B、links 945 B（按卡追加）。
- 追加记录精确：`V-APR-0002`（P02/500000/APPROVED）、`V-BR-0003`（BT-2026-0002/PAY/500000）、`L-0007`（PAYMENT_APPROVAL→V-APR-0002）、`L-0008`（PAYMENT_BANK_RECEIPT→V-BR-0003）。
- v1 未动：`task043_v1` manifest 仍为 1268 B / `5a9c3bb3…2172d54`；其 9 文件字节与 TASK-043 接受身份一致。
- 回执 `docs/EXEC_REPORT_043_R1.md` 5468 B / `c10ef847…db32`。

## 2. 架构端独立运行（不复用执行端结论）

自行编写并运行 29 项检查（`verify_r1.py`，全通过）：

- **已接受校验器对 v1.1 原样**：exit 1，`reason_count=1`，唯一 `MANIFEST_VERSION`（期望 1.0、实际 1.1）——版本守卫按代码工作，其余字段无差异。
- **内容等价副本**（v1.1 全量复制，仅 `input_version` 回落 1.0）：exit 0、`INPUT_V1_ACCEPTED`，计数 **凭证 8**（INVOICE 1 / CONTRACT 1 / BANK_RECEIPT 3 / APPROVAL 2 / GOODS_RECEIPT 1）、links 8、bank 3。
- **已接受匹配器对 v1.1 原样**：exit 0、`ALL_MATCHED`、**8/8 MATCHED**；R02 抽样含 AP01/P01/P02/R01，P02 证据为 `V-APR-0002`/`V-BR-0003`，`human_conclusion` 恒 null。
- **只读**：我的三次运行前后，v1、v1.1、ledger 数据库与 normalized 全部字节不变。

## 3. 裁决（执行端二选一）与残差

采用 **A**：接受 v1.1 的版本元数据（`task043-input-1.1`），不以"把版本改回 1.0"作为 canonical 状态。理由是版本应反映内容（v1.1 内容确实新增了 P02 凭证），内容等价副本通过已证明**除版本外全部语义校验成立**，as-is 唯一拒绝项正是版本守卫。

**已登记残差（不阻断，纳入 TASK-046）**：已接受 `input_contract_v1.py` 的 `INPUT_VERSION` 硬编码为 `task043-input-1.0`。TASK-046 须使校验器接受声明版本集 `{task043-input-1.0, task043-input-1.1}`、在登记中原样回显 `input_version`、拒绝未知版本，并在 v1.1 原样上 exit 0；在此之前，v1.1 的 canonical 契约证据以本评审 §2 的"版本单因拒绝 + 内容等价通过"承载，不作为最终演示口径。

## 4. 保护与历史

执行端一次全树扫描：基线 175375 项 / `849d2202…`，`changed=0`（含 v1 全部 9 文件）、missing 0、读取错误 0、新增 36 项全登记；架构端独立扫描复核（`data/reviews/task043r1_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 5. 边界

未做：代码/测试/指南/卡修改、演示集成、账实（TASK-045 待放行）、人类核对结论、AI/终判、真实数据/强认证。本卡只补输入数据，不证明凭证真实，不构成审计结论。

## 6. 接受与下一卡

发布新接受基线 `data/reviews/task043r1_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-045（银行账实勾对）**；TASK-046 将并入"校验器版本兼容 + 演示集成 + 求职稿更新"。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
