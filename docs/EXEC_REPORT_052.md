# TASK-052 执行回执：网页审阅（表单 + 导出 + 合并）与《审阅记录.xlsx》

日期：2026-10-18。交付状态：审阅表单/导出、合并命令、测试与指南定稿，**交独立验收**；
不接 AI/终判、不接演示、不改看板。
真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-052_DRAFT.md`（`a9da2f09…`）、决策记录 `DSH-SCOPE-20261017-05` D-UI3-3。
前置：TASK-051 ACCEPTED。起点接受快照 `data/reviews/task051_dsh_20261017_01/source_hashes_after.json`
（**186238 项 / `faa4ff91…`**）。允许修改既有恰九件；新增合并命令/测试/指南/回执与 `task052_*` 证据。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task052_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 改动身份（恰九件，实测同缓冲长度/SHA）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_trace_index.py` | 36066 B | `9bc091f46276cc81…` |
| `scripts/build_drilldown_site.py` | 49344 B | `c499fdf78c304ae1…` |
| `scripts/build_excel_workbook.py` | 29152 B | `ca972c6c155c6f1f…` |
| `tests/test_trace_index.py` | 12827 B | `b2f36e90cfb055d6…` |
| `tests/test_drilldown_site.py` | 16257 B | `dad0556970f0e3ee…` |
| `tests/test_excel_workbook.py` | 17434 B | `36f4f5e080adae2e…` |
| `docs/EVIDENCE_CHAIN_INDEX_GUIDE.md` | 4245 B | `5ac0ddf32174ebf4…` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 3755 B | `316c02b014c85990…` |
| `docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md` | 3324 B | `2d97f839a6a64f79…` |

新增：`scripts/apply_review_notes.py`（15595 B / `492c3fb103483e6f…`）、`tests/test_review_notes.py`
（15388 B / `c56648955675d38f…`）、`docs/REVIEW_NOTES_GUIDE.md`（3593 B / `f6817589323063cb…`）、
`docs/EXEC_REPORT_052.md`、`task052_*` 证据根。

## 2. 网页审阅表单与导出（实测）

- 每条事项页与全量清单行旁有审阅表单：状态下拉（待审阅/已审阅-相符/已审阅-不符/需补充资料）、
  审计问题描述、建议处理、审阅人、审阅日期；草稿仅存 `localStorage`（键含资料版本短标识 +
  记录类型 + 记录 ID），页面标注"草稿仅保存在本浏览器，导出并合并后才成为审阅记录"。
- 导出按钮生成 `审阅记录.json`/`审阅记录.csv`（含 `review_version`、资料版本短标识、逐记录字段）；
  不写文件、不发网络请求；无 `fetch`/`XMLHttpRequest`/`eval`/`WebSocket`/外链（测试守卫）。
- 合并后页面显示徽标（绿/红/黄/灰）、问题与建议；筛选新增"审阅状态"；打印仍为全量视图。

## 3. 合并命令（实测）

```
.venv\Scripts\python.exe -B scripts\apply_review_notes.py `
  --index data\runtime_initial_judgment_recording_tests\task052_index_01\trace_index.json `
  --review-notes data\runtime_initial_judgment_recording_tests\task052_review_01\审阅记录.json `
  --out-dir data\runtime_initial_judgment_recording_tests\task052_merge_01
```

- **exit 0**；输出 `审阅记录.xlsx`（26 行 × 9 列，列：编号/事项或记录/审阅状态/审计问题描述/
  建议处理/审阅人/审阅日期/对应资料版本/审阅记录版本，自动筛选）、合并 `trace_index.json`
  （每条记录 `review` 字段）、`task049_site/`（31 页，徽标/问题/审阅状态筛选/表单/导出）、
  `task050_workbook/证据链底稿.xlsx`、`merge_source.json`（输入/输出身份、审阅记录版本 = 记录文件 SHA 短标识）。
- 合并结果：CASE-0001 `已审阅-相符`、P01 `已审阅-相符`、V-INV-0001 `需补充资料`、
  payables!2 `已审阅-不符`、A01 保持 `待审阅`；原索引/原底稿/机器证据未被覆盖。
- 负例（均 exit 1、字段精确）：资料版本不符（`review_notes.source_version`）、未知记录、
  非法状态、非待审阅缺必填（`.issue`）、HTML 注入（`.issue`）。
- 确定性：同索引 + 同审阅记录两次合并 → 合并索引/审阅记录.xlsx/站点/底稿**字节相同**。
- 只读：原索引、审阅文件、批次源、`data/evidence_inputs/` 字节不变。

## 4. 测试（实测全部通过）

- `tests/test_review_notes.py`（`task052_run_03`）：**8/8 PASS**（正常/5 类负例/确定性/规模/只读）。
- `tests/test_trace_index.py`（`task052_run_04`）：**5/5 PASS**（含全记录 review 占位）。
- `tests/test_drilldown_site.py`（`task052_run_08`）：**8/8 PASS**（含表单/导出/版本属性/草稿键）。
- `tests/test_excel_workbook.py`（`task052_run_06`）：**8/8 PASS**。
- 规模：200 条事项 + 20 条审阅记录 → 合并成功，站点链接全解析，耗时/大小登记（本机，非性能承诺）。

## 5. 保护安排与判据

定稿后**一次**全树扫描（`task052_finalization/protection_scan.py`），基线 = TASK-051 接受快照
（186238 项 / `faa4ff91…`）：相对基线**既有 changed 恰上述九件**；其余全新增并逐路径登记；
missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 6. 未执行与边界

未接 AI/终判、未接演示、未改看板；未做账表/账账、影像/OCR、外部查验、函证/盘点、真实数据/强认证
（`null` + 原因）。审阅记录为**人类输入**，须记录审阅人与日期；不覆盖机器证据，不构成审计结论或终判。
