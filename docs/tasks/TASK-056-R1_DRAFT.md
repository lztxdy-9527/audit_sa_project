# TASK-056-R1：补齐总账↔科目余额表、报表内部平衡与账证明细账覆盖

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-055 ACCEPTED**（GL v1 已接受）；TASK-056 为 **NOT_ACCEPTED**（`docs/reviews/REVIEW_TASK_056.md`）。本卡修复漏检 B1/B2/B3，重建六类核对引擎与测试。

## 1. 允许修改/新增

**允许修改（changed 恰三件）**：`scripts/reconcile_gl_v1.py`、`tests/test_gl_reconcile.py`、`docs/GL_RECONCILE_GUIDE.md`。
**允许新增**：`docs/EXEC_REPORT_056_R1.md`、证据根 `data/runtime_initial_judgment_recording_tests/task056r1_*/`。
**禁止**：改 GL 输入包、索引/站点/Excel 生成器、适配器、演示、契约/账证/账实核对器、既有卡/评审/证据、看板。

## 2. 必须修复的缺陷

### B1 总账↔科目余额表（账账补全）

- 新增/补强检查：**逐科目**比较 `ledger_general` 期末余额与 `trial_balance` 期末（含方向）；**即使该科目没有明细账**也要比较；
- 原"总账↔明细账"保留：有明细账的科目，明细账合计 = 总账期末；明细账逐笔余额滚动正确；
- 失败 finding 字段：`account_code / general_closing / trial_closing`（或明细账对应值）。

### B2 报表内部平衡（账表补全）

- `balance_sheet`：`total_assets_cents` 必须 = 资产分项之和；`total_liabilities_equity_cents` = 负债分项 + 权益分项之和；且 `total_assets_cents = total_liabilities_equity_cents`；
- 原"科目余额表↔报表项目"保留（含应付 0 / 预付 4,000 重分类）；
- 失败 finding 字段：`report_item / expected_total / actual_total`。

### B3 账证对明细账的覆盖

- `ledger_to_voucher`：总账按科目发生额 = 凭证汇总（保留）；**同时**对每个有明细账的科目，明细账发生额合计 = 凭证汇总；
- 若决定只做总账口径，必须在指南与报告中**明确写"账证不覆盖明细账"**，并保留"账账覆盖明细账"的说明；默认按补齐实现。

## 3. 验收测试（必须覆盖 B1/B2/B3）

1. **正常**：`gl_v1` → exit 0、`overall=ALL_MATCHED`、七项全 MATCHED；数字与手算一致；备注含应付借方 4,000 重分类；未执行项列示。
2. **B1 变异**：改 `ledger_general` 中**无明细账科目**（1001）期末 +1 分 → **exit 1**，`账账` 或新检查报 `DIFFERENCES`，findings 指出 1001。
3. **B2 变异**：改 `balance_sheet.total_assets_cents` +1 分 → **exit 1**，`账表` 报 `DIFFERENCES`，findings 指出合计不平。
4. **B3 变异**：改明细账某笔发生额 +1 分 → **exit 1**，`账证` 和/或 `账账` 至少一项报 `DIFFERENCES`（按实现口径写清）。
5. 原有负例回归：凭证不平衡、余额表等式、报表项目、银行期末、附件缺失/类型、清单篡改（契约层）仍 exit 1。
6. 确定性：同输入两次，报告 JSON/MD 字节相同；只读：GL 包/输入/批次不变。
7. 规模：200 张凭证夹具，六类完成，登记耗时/大小。

## 4. 证据

`task056r1_evidence_01/`：正常报告、B1/B2/B3 与原有负例输出、命令/退出码、输入快照；`delivery.json` 记录三件身份与扫描数字。

## 5. 保护与停止

一次全树扫描，基线 = TASK-055 接受基线（200574 项 / `65245ddf…`）：**既有 changed 必须为 0**（本卡只改 TASK-056 未接受的三个新文件）；其余全新增并逐路径登记；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不接 UI/Excel（TASK-057）、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；核对结果只展示证据与差异，不构成审计结论。
