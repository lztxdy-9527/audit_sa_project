# TASK-056-R1 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-18，DSH 架构/测试验收端对"借贷记账法六类核对引擎 R1"独立复验。B1（总账↔科目余额表）、B2（报表内部平衡）、B3（账证明细账覆盖）三处漏检均已修复并经定向变异验证；原七类负例回归通过。核对结果只展示证据与差异，不构成审计结论。

## 1. 改动身份（恰三件 + 回执）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/reconcile_gl_v1.py` | 24785 B | `83181b8b4650e6ab…` |
| `tests/test_gl_reconcile.py` | 12683 B | `7581be89af3d7589…` |
| `docs/GL_RECONCILE_GUIDE.md` | 5461 B | `189d62de14347878…` |
| `docs/EXEC_REPORT_056_R1.md` | 4297 B | `5a96ac1a…` |

## 2. 架构端独立复验（19 项检查全过）

- **正常**：`gl_v1` → exit 0、`ALL_MATCHED`、七项全 MATCHED；借贷 16,000=16,000；试算 20,000=20,000；应付 4,000 借；银行 11,000；报表 20,000=20,000；备注含"应付借方 4,000 重分类预付"。
- **B1 变异**（改 1001 总账期末 +1 分，无明细账科目）：**exit 1**，finding 含 `account_code=1001`——与修复前 exit 0 形成对照，漏检关闭。
- **B2 变异**（改报表 `total_assets_cents` +1 分，分项不动）：**exit 1**，`ledger_to_report` 报差异。
- **B3 变异**（改明细账某笔贷方 +1 分）：**exit 1**，`ledger_to_voucher`/`general_to_subsidiary` 报差异（账证已覆盖明细账或由账账兜底，报告写明）。
- **原七类负例回归**：凭证不平衡、余额表等式、报表项目、银行期末、附件缺失均 exit 1 且检查精确。
- **确定性**：同输入两次报告 JSON/MD 字节相同；**只读**：GL 包、`task043_v1_1`、批次字节不变。
- **测试复跑**：13/13 PASS。

## 3. 保护与历史

执行端一次全树扫描：基线 200574 项 / `65245ddf…`，**既有 changed = 0**、missing 0、读取错误 0、新增 908 项全登记；架构端独立扫描复核（`data/reviews/task056r1_dsh_20261018_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 缺陷关闭与边界

- `REVIEW_TASK_056.md` 的 B1/B2/B3 全部关闭；TASK-056 的 NOT_ACCEPTED 由本 R1 取代。
- 未接 UI/Excel（TASK-057）、不做函证/监盘/期后付款、不改看板；GL 为合成账套。

## 5. 接受与下一卡

发布新接受基线 `data/reviews/task056r1_dsh_20261018_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-057（GL 接入站点/Excel）**，卡身份 `5306e02f…bfc4632`。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
