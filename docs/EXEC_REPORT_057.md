# TASK-057 执行回执：把借贷核对接进站点与 Excel

日期：2026-10-18。交付状态：索引 v1.2（`gl` 节）、六页借贷核对站点、七页 Excel、测试与指南完成，
**交独立验收**；不改 GL 输入包/核对引擎/合并命令/适配器/演示/契约/既有证据/看板；不接 AI/终判。

依据：`docs/tasks/TASK-057_DRAFT.md`（`5306e02f…`）、决策记录 `DSH-SCOPE-20261017-06` D-GL-2/D-GL-4。
接受基线：TASK-056-R1 接受快照 `data/reviews/task056r1_dsh_20261018_01/source_hashes_after.json`
（**201784 项 / `8ea7c2ea…`**）。

## 1. 改动身份（恰九件，实测）

| 文件 | 长度 | SHA-256 |
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

新增 `docs/EXEC_REPORT_057.md` 与 `task057_*` 证据根。

## 2. 索引 v1.2（实测）

- 新增可选 `--gl-root` / `--gl-report`（须同时提供）；缺省时不生成 `gl` 节，旧行为不变。
- `gl` 节只读复制：科目表、余额表 rows/totals、凭证分录（含附件引用）、总账、明细账、报表、
  银行对账单/日记账、六类检查状态/发现/备注/未执行项、来源身份（9 文件 + manifest + 报告）。
- 凭证链接：记-001↔AP01、记-002↔P01、记-003↔P02、记-004↔R01；四张均 ↔ CASE-0001。
- 端点实测：`trace_index.json` 44127 B，`index_version=TASK-048-trace-index-1.2`，7 项检查、
  `overall=ALL_MATCHED`；无 gl 参数时索引不含 `gl`（测试覆盖）。

## 3. 站点六页（实测）

`task057_site_01`：**39 页**（原 33 + 6），`gl-trial-balance.html` / `gl-journal.html` /
`gl-ledger.html` / `gl-report.html` / `gl-bank.html` / `gl-checks.html` 均存在；**全站每页**导航含
“借贷核对”入口；`business-AP01.html` 增加“查看记账凭证/借贷核对”链接。

- 科目余额表：期初/本期/期末借贷分列；16,000.00 = 16,000.00；期末 20,000.00 = 20,000.00；
  应付 4,000.00 借方高亮。
- 记账凭证：记-001～004 借贷科目/金额/附件/关联账务/关联事项，可点入凭证/账务/事项页。
- 总账与明细账：应付按 AP01、银行按基本户，逐笔余额滚动。
- 账表核对：应付 0 / 预付 4,000.00 重分类；资产 20,000.00 = 负债+权益 20,000.00。
- 银行调节：期初 20,000.00 + 收入 1,000.00 − 支出 10,000.00 = 期末 11,000.00；未达 0。
- 核对结果：六类 + 附件七项全 `MATCHED`；备注含应付借方重分类提示；未执行项列示。
- 全站脚本 `node --check` **0 错误**；链接全解析；纯审计语言（无 JSON/hash/SHA 等）；无外链/`eval`/`fetch`。

## 4. Excel 七页（实测）

`task057_workbook_01/证据链底稿.xlsx`：**13 个工作表**（原 6 + 7）：
《科目余额表》《记账凭证》《总账》《明细账》《账表核对》《银行调节》《核对结果》。

- 表头冻结、自动筛选（7 页均有）；金额元/分并列、格式正确；应付 4,000 借方行高亮。
- 《记账凭证》含附件编号与关联账务；《账表核对》含重分类说明；《银行调节》含期初/收入/支出/期末
  与未达账项笔数；《核对结果》七项状态与差异数。
- 《说明》补“借贷核对为合成账套演示”。

## 5. 测试（实测全部通过）

- `tests/test_trace_index.py`（`task057_run_01`）：**6/6 PASS**（v1.2 + gl 节 checks/链接/来源）。
- `tests/test_drilldown_site.py`（`task057_run_02`）：**6/6 PASS**（六页/导航/数字/node --check/链接）。
- `tests/test_excel_workbook.py`（`task057_run_03`）：**9/9 PASS**（七页/冻结/自动筛选/数字/状态）。
- 规模：200 张凭证 GL 夹具 → 核对报告（exit 1，差异属夹具本身）→ 索引/站点（39 页）/底稿
  （44721 B）生成成功，链接全解析；耗时/大小登记（非性能承诺）。

## 6. 证据

`task057_evidence_01/command.json`：索引/站点/底稿命令与退出码、页面数、Excel 大小、逐页
`node --check` 结果、规模结果；站点根 `task057_site_01/`、底稿 `task057_workbook_01/`、
索引 `task057_index_01/`、测试根 `task057_run_0{1,2,3}/`、规模根 `task057_*_scale/`。

## 7. 保护安排与判据

定稿后**一次**全树扫描（`task057_finalization/protection_scan.py`），基线 = TASK-056-R1 接受快照
（201784 项 / `8ea7c2ea…`）：相对基线**既有 changed 恰九件**；其余全新增并逐路径登记；
missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。

## 8. 边界

GL 为合成账套；页面/底稿只读展示证据与差异，**不构成审计结论或终判**；不接 AI/终判、不改看板。
真实批准 `null`、真实初判未保存、0008、`next/AI=false`。
