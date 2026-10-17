# TASK-044 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对"账证相符 L1（凭证字段级核对）+ 差异分类 + 抽样核对底稿"独立复验。匹配器行为在**一致夹具**与**规范输入**两侧均正确，差异分类精确、人类结论列恒空、只读成立。本接受不证明凭证真实、不构成审计证据或结论。

## 1. 交付身份（实读同缓冲）

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/voucher_match_v1.py` | 38985 B | `8daa8cd858fcf435797f8cb2ee19c4692c17d2285a2f4c696de9a9c3bb4cae84` |
| `tests/test_voucher_match_v1.py` | 19470 B | `e680bf9cf3604b5c4f2e326202d06d9bc945ed54a5c7567dec00d1f3316e113b` |
| `docs/ACCOUNT_VOUCHER_MATCH_GUIDE.md` | 6858 B | `944a9917bb6249bab7e272aec979cf399bd35526c308a76916bf4dfa63b11c44` |
| `docs/EXEC_REPORT_044.md` | 7586 B | `b38777a729263b1b6b1b193fd4924cea0551778fe3cb2b410093f9afd2461a9f` |

账务只读源 `data/runtime/task042_dsh_01/normal.load/normalized.json` 18169 B / `f440f0cf…09e2`；同目录 `started.json`/`artifacts.json` 绑定核对通过。

## 2. 架构端独立运行（不复用执行端结论）

- **测试复跑**（新目录 `task044_dsh_01`）：`test_voucher_match_v1.py` → **exit 0、14/14 cases PASS、read_only_ok=true**。
- **一致夹具**（`task044_run_02/normal_consistent/input`，只读）：匹配器 → **exit 0、`ALL_MATCHED`、8/8 `MATCHED`**；R02 抽样底稿条目覆盖 AP01/P01/P02/R01，`human_conclusion` 全 null；`verification_level=L1_FIELD_LEVEL_NO_EXTERNAL_VERIFICATION`。
- **规范输入对照**（`data/evidence_inputs/task043_v1`）：匹配器 → **exit 1、`DIFFERENCES_FOUND`**，恰 **2 条 `MISSING_VOUCHER`**：`PAYMENT P02 × APPROVAL`、`PAYMENT P02 × BANK_RECEIPT`；其余 6 项 MATCHED；差异与证有账无 0。
- **只读复核**：两次运行前后，输入根与 normalized/started/artifacts 字节哈希完全一致。
- **差异字段抽样实读**：与回执一致（`AMOUNT_MISMATCH/total_cents_sum`、`TAX_TOTAL_MISMATCH/tax_cents`、`DATE_MISMATCH/issue_date|txn_date`、`COUNTERPARTY_MISMATCH/counterparty_name`、`STATUS_MISMATCH/status`、`DIRECTION_MISMATCH/direction`、`SUM_MISMATCH/total_cents_sum`、`MISSING_VOUCHER`、`EXTRA_VOUCHER`、`REFUND_LINK_MISMATCH/original_allocation_id`）。

## 3. 关于 P02 账有证无（如实认定）

TASK-043 接受输入为契约校验而设计，凭证未覆盖 P02；因此"正常全部 MATCHED"在冻结输入上不成立。执行端处理正确：**未擅自改接受输入**，如实报 2 条 `MISSING_VOUCHER`，并在证据根内用一致夹具演示全匹配、把规范输入对照保留为数据事实。责任在架构端卡规格（TASK-043 凭证计数只覆盖 AP01/P01/R01）。据此本卡接受，并另发 **TASK-043-R1**（输入补充 v1.1：补 P02 审批单 `V-APR-0002`、回单 `V-BR-0003`、索引 `L-0007/L-0008`；v1 原样冻结），使 canonical 输入完整且不返工匹配器。

## 4. 保护与历史

执行端一次全树扫描：基线 174820 项 / `c65c27cb…`，`changed=0`、missing 0、读取错误 0、新增 362 项全登记；架构端独立扫描复核（`data/reviews/task044_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 5. 边界

未做：影像/OCR、发票/回单外部查验、函证/盘点、无索引模糊匹配、人类核对结论（不采集、不虚构）、账实（TASK-045 待放行）、账账/账表、演示集成、AI/终判、真实数据/强认证。本卡不证明凭证真实。

## 6. 接受与下一卡

发布新接受基线 `data/reviews/task044_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。下一卡 **TASK-043-R1**（输入补充 v1.1），随后放行 **TASK-045**（银行账实）。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
