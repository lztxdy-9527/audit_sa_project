# TASK-057 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-18，DSH 架构/测试验收端对"GL 借贷核对接入站点与 Excel"独立复验。索引 `gl` 节、六个 GL 页面、Excel 七页、导航与链接、脚本语法与只读均成立；架构端自跑复现。页面/底稿只读展示合成账套证据，不构成审计结论。

## 1. 改动身份（恰九件 + 回执）

| 文件 | 长度 | SHA-256（前 16） |
| --- | --- | --- |
| `scripts/build_trace_index.py` | 40398 B | `901dcdb95c9d3505…` |
| `scripts/build_drilldown_site.py` | 84699 B | `4caf937057ad5ee4…` |
| `scripts/build_excel_workbook.py` | 41211 B | `a66dea2bcfda6223…` |
| `tests/test_trace_index.py` | 15135 B | `a89f9992bbaeecec…` |
| `tests/test_drilldown_site.py` | 30068 B | `5ed9754b29cbbb20…` |
| `tests/test_excel_workbook.py` | 19812 B | `906a477d7f390ab1…` |
| `docs/EVIDENCE_CHAIN_INDEX_GUIDE.md` | 5031 B | `1099138c52829162…` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 8017 B | `078786c89a13920d…` |
| `docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md` | 4029 B | `878147d6550d759e…` |
| `docs/EXEC_REPORT_057.md` | 5365 B | `c77909216dbe7b25…` |

## 2. 架构端独立运行（49 项检查全过）

- **索引 v1.2**（我重建）：exit 0；`gl` 节含科目表、余额表、凭证分录、总账、明细账、报表、银行、**7 项检查**（overall ALL_MATCHED）、未执行项、来源；4 张凭证分录；**记录↔账务↔事项链接正确**（记-001→AP01、记-002→P01、记-003→P02、记-004→R01，均→CASE-0001）。
- **向后兼容**：不带 `--gl-root/--gl-report` 生成旧索引，**无 `gl` 节**。
- **站点**：39 页；`gl-trial-balance/gl-journal/gl-ledger/gl-report/gl-bank/gl-checks` 六页齐全；`business-AP01` 有"借贷核对"链接；**逐页 `node --check` 0 错误**；链接全解析、无外链；GL 页面含 **16,000.00 / 20,000.00 / 4,000.00 / 11,000.00 / 未达账项 / MATCHED**；语言禁止词零命中。
- **Excel**：新增 **科目余额表 / 记账凭证 / 总账 / 明细账 / 账表核对 / 银行调节 / 核对结果** 七页；自动筛选均在；包含 4000/20000/11000 等关键数。
- **测试**：索引 6/6、站点 6/6、工作簿 9/9 全过。
- **只读**：GL 包、核对报告、`task043_v1_1`、运行根字节不变。

## 3. 保护与历史

执行端一次全树扫描：基线 201784 项 / `8ea7c2ea…`，**changed 恰九件**、missing 0、读取错误 0、新增 924 项全登记；架构端独立扫描复核（`data/reviews/task057_dsh_20261018_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 边界与下一卡

- GL 为合成账套；页面/底稿只读，不构成审计结论或终判；未接 AI/终判。
- 发布新接受基线 `data/reviews/task057_dsh_20261018_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-058（数据投放指引与目录骨架）**，卡身份 `0992f440…03d480e0`。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
