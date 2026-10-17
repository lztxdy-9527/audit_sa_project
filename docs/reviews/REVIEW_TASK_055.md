# TASK-055 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-18，DSH 架构/测试验收端对"GL v1 输入契约 + 合成账套"独立复验。契约校验、账套数字、确定性、9 类负例与只读均成立；架构端自跑复现。GL 为**合成账套**，不证明真实账务，不构成审计结论。

## 1. 新增身份

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_gl_demo_inputs.py` | 11397 B | `06c9d5976cc39227a137904cf65353ddf70df0d99974d7c472faa82d462f7923` |
| `scripts/gl_input_contract_v1.py` | 24113 B | `d14c7e019d5e3abbd230229101e6b6bf445cc7d71c3305085ee3c34b856d0237` |
| `tests/test_gl_input_contract.py` | 10875 B | `9e2c1f0c63d1739963d784c1e1d97b3436af5fa369c4357c5871f6a0ddb23fee` |
| `docs/GL_INPUT_CONTRACT_V1.md` | 5830 B | `1e9ae47420321a5f9906b1a120b59431c628613ef1a69f111f2102ca32859f50` |
| `docs/EXEC_REPORT_055.md` | 5082 B | `67398a87d0ae47ec2dfd39d36873a1b9d3a421ff7821668f25ccfc44edd47b57` |

输入包 `data/evidence_inputs/gl_v1/`：**10 个文件 / 11755 B**，manifest `124e0370bec176fa…`。

## 2. 架构端独立运行（26 项检查全过）

- **契约校验**：`--gl-root data/evidence_inputs/gl_v1` → exit 0。
- **重建确定性**：生成器两次输出**字节相同**，且与接受包 `gl_v1` 完全一致（可复现）。
- **独立复算**：4 张凭证；期间借/贷各 **16,000.00**；逐张借贷相等；试算期末借 **20,000 = 20,000**；应付 2202 **借方 4,000**；银行 1002 **借方 11,000**；报表资产 **20,000 = 20,000**，应付 0 / 预付 4,000（重分类）；银行 **20,000 + 1,000 − 10,000 = 11,000**；附件 8 项且凭证引用全部存在。
- **负例（9 类，全部 exit 1、码精确）**：借贷不平（`GL-ENTRY-UNBALANCED`）、未知科目（`GL-ACCOUNT-UNKNOWN`）、浮点金额（`GL-AMOUNT-TYPE`）、清单篡改（`GL-MANIFEST-SIZE/SHA`）、余额表等式（`GL-TB-EQUATION`）、明细账期末（`GL-SUB-CLOSING`）、报表不平（`GL-BS-EQUATION`）、银行期末（`GL-BANK-END`）、附件缺失/类型（`GL-ATTACH-TYPE/MISSING`）。
- **测试复跑**：10/10 PASS。
- **只读**：既有 `data/evidence_inputs/` 与批次源字节不变。

## 3. 保护与历史

执行端一次全树扫描：主基线 199571 项 / `21f77092…`，**既有 changed = 0**、missing 0、读取错误 0、新增 437 项全登记；架构端独立扫描复核（`data/reviews/task055_dsh_20261018_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 边界与下一卡

- GL v1 为合成账套；不做数据清洗；不做六类核对（TASK-056）、不接 UI、不改看板。
- 发布新接受基线 `data/reviews/task055_dsh_20261018_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-056（六类核对引擎）**，卡身份 `a418f56a…44b9e3b`。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
