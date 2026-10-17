# TASK-051 执行回执：全量清单、筛选、Excel 自动筛选、源漂移与备份纪律

日期：2026-10-17。交付状态：索引 v1.1、站点全量/筛选、工作簿全量/自动筛选、测试与指南定稿，
**交独立验收**；不实现审阅表单（TASK-052）、不改演示、不改看板。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-051_DRAFT.md`（`aeb7ea71…`）、决策记录
`docs/decisions/DECISION_20261017_DSH_UI_V3_FULL_FILTER_REVIEW.md`（`DSH-SCOPE-20261017-05`）。
前置：TASK-050 ACCEPTED。起点接受快照 `data/reviews/task050_dsh_20261017_01/source_hashes_after.json`
（**179749 项 / `4f895b86…`**）。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task051_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 改动身份（恰九件，实测同缓冲长度/SHA）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_trace_index.py` | 35020 B | `441c73753dfa9be8…` |
| `scripts/build_drilldown_site.py` | 39227 B | `787c632f9fbd0fe7…` |
| `scripts/build_excel_workbook.py` | 29129 B | `eac9dfb1339cf892…` |
| `tests/test_trace_index.py` | 12201 B | `a5a649285b817c4a…` |
| `tests/test_drilldown_site.py` | 15847 B | `62805bffcf1008db…` |
| `tests/test_excel_workbook.py` | 17411 B | `bfe85a5008783e45…` |
| `docs/EVIDENCE_CHAIN_INDEX_GUIDE.md` | 3897 B | `7ac669a1d7182877…` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 2993 B | `0f2ac1d588bad07d…` |
| `docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md` | 2885 B | `d3a4484cccbc83c8…` |

新增 `docs/EXEC_REPORT_051.md` 与 `task051_*` 证据根；未改适配器、演示脚本、契约/账证/账实核对器、
输入根、TASK-047 摘要生成器、既有卡/评审/证据、看板。

## 2. 索引 v1.1（实测）

`--run-root …\task046_demo_01 --out-dir …\task051_index_01` → **exit 0**、22349 B / `b4ae3187…`：

- `ledger[]` **全量 7 行**（应付 1 / 付款退款 3 / 分摊 3），每条 `status`：**已核对一致 4、未涉及 3**；
  来源 `source{sheet, excel_row}` 已填。
- `vouchers[]` **全量 8**（`status=已取得`）；`source_rows[]` **全量 9 行**（suppliers 2 / payables 1 /
  payments 3 / allocations 3）。
- `source_identity`：源工作簿相对路径/7177 B/`8f6f2a98…`，`source_drift.status=OK`；
  每案 `review` 占位（`status=待审阅`，问题/建议/审阅人/日期 null）。
- `meta`：`ledger_total=7`、`voucher_total=8`、`source_rows_total=9`、`status_counts`、
  `cases_per_page=50`、`pages=1`、无时间戳/随机数。
- **源漂移**（复制批次源改 1 字节，`--batch-dir` 指向副本）：**exit 1、`kind=content`、错误含
  `source_drift`**、不生成索引；原批次源字节不变。

## 3. 站点 v1.1（实测）

`--index …\task051_index_01\trace_index.json --out-dir …\task051_site_01` → **exit 0**、31 页：

- 新增 `all-ledger.html`（7 行）/`all-vouchers.html`（8 行）/`all-source.html`（9 行），均带状态列、
  筛选栏与打印规则；台账/凭证/原始行页补充状态（已核对一致/未涉及、已取得、已涉及/未涉及）。
- 筛选：内嵌脚本仅做 class 切换（状态 全部/仅异常/仅合规/待审阅 + 关键词），**无 fetch/XMLHttpRequest/
  eval/WebSocket/外链**；所有行预先渲染；`@media print` 强制全量并隐藏筛选栏，页脚注明
  "打印为全量视图，筛选仅屏幕生效"。
- 链接：全部 `.html` 的 `href` **0 处不可解析**；可见文本（剥离脚本/样式）禁止词零命中；
  P02 缺证页仍显示"未取得"红色与占位。

## 4. 工作簿 v1.1（实测）

`--index …\task051_index_01\trace_index.json --out-dir …\task051_workbook_01` → **exit 0**、17903 B：

- 《台账明细》**49 行**（含表头）、12 列含状态；《凭证》**63 行**、7 列含状态；《原始表行》
  **10 行**（9 数据行 + 表头）、12 列含状态；三表 **auto_filter** 分别覆盖 `A1:L49`/`A1:G63`/`A1:L10`。
- 《说明》新增备份纪律：源文件只在接收时留存一份、生成不复制源、每次只新增小文件、项目内不删除旧证据。
- 链接仍全部可解析（内部 `#'Sheet'!Cell`），外部仅原始工作簿；元=分/100、冻结表头、A4 横向、
  严重程度底色、金额下划线提示保留。

## 5. 规模、确定性与只读（实测）

- 规模：200 条事项（`task048_scale_run_*`）→ 索引 260284 B、站点 **432 页**、工作簿 34966 B；
  链接全部可解析；耗时为秒级（本机，非性能承诺）。
- 确定性：索引/站点两次生成字节相同；工作簿两次生成字节相同（固定打包时间与核心属性）。
- 只读：生成/测试前后批次源、运行根、`data/evidence_inputs/`、账务 `normalized.json` 字节一致。

## 6. 测试（实测 3 个测试全部通过）

- `tests/test_trace_index.py`（`task051_run_01`）：**5/5 PASS**（全量/状态/漂移/确定性/负例）。
- `tests/test_drilldown_site.py`（`task051_run_04`）：**8/8 PASS**（全量页/筛选守卫/打印/链接/语言/
  P02/确定性/规模/只读）。
- `tests/test_excel_workbook.py`（`task051_run_05`）：**8/8 PASS**（全量/autofilter/状态/备份纪律/
  链接/数值/语言/确定性/规模/P02/负例）。

## 7. 保护安排与判据

定稿后**一次**全树扫描（`task051_finalization/protection_scan.py`），基线 = TASK-050 接受快照
（179749 项 / `4f895b86…`）：相对基线**既有 changed 恰上述九件**；其余全新增并逐路径登记；
missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 8. 未执行与边界

未实现审阅表单（TASK-052）、未接入演示；未做账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、
真实数据/强认证（`null` + 原因）。页面/底稿只读展示既有合成证据，不证明凭证/流水真实，不构成审计结论。
