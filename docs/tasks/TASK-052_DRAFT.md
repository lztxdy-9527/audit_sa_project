# TASK-052：网页审阅（表单 + 导出 + 合并）与《审阅记录.xlsx》

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-051 ACCEPTED**（全量清单与筛选已接受）。依据 `DSH-SCOPE-20261017-05` D-UI3-3：审阅在页面填写、浏览器只存草稿、导出 JSON/CSV、命令校验并生成《审阅记录.xlsx》、把徽标与问题合并回站点与底稿；网页不写证据目录。

## 1. 允许修改/新增

**允许修改（changed 恰这九件）**：`scripts/build_trace_index.py`、`scripts/build_drilldown_site.py`、`scripts/build_excel_workbook.py`、`tests/test_trace_index.py`、`tests/test_drilldown_site.py`、`tests/test_excel_workbook.py`、`docs/EVIDENCE_CHAIN_INDEX_GUIDE.md`、`docs/DRILLDOWN_SITE_GUIDE.md`、`docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md`。
**允许新增**：`scripts/apply_review_notes.py`（唯一新增代码）、`tests/test_review_notes.py`、`docs/REVIEW_NOTES_GUIDE.md`、`docs/EXEC_REPORT_052.md`、证据根 `data/runtime_initial_judgment_recording_tests/task052_*/`。
**禁止**：改适配器、演示脚本、契约/账证/账实核对器、输入根、既有卡/评审/证据、TASK-047 摘要生成器、看板。

## 2. 页面审阅表单（内嵌脚本，限用途）

- 每条事项/每条全量记录旁提供：`审阅状态`（下拉：待审阅 / 已审阅-相符 / 已审阅-不符 / 需补充资料）、`审计问题描述`（多行文本）、`建议处理`、`审阅人`、`审阅日期`（手工输入，不预填）。
- 草稿：`localStorage` 按键保存（事项/记录 ID + 资料版本），页面明确标注"草稿仅保存在本浏览器，导出并合并后才成为审阅记录"。
- 导出：按钮生成 `审阅记录.json` 与 `审阅记录.csv` 下载；内容含 `review_version`、资料版本（源哈希短标识）、每条记录字段；**不写文件、不发网络请求**；`eval/fetch/XMLHttpRequest/WebSocket` 禁止；转义全部动态文本。
- 合并后（见 §3）页面显示徽标：`已审阅-相符`（绿）/`已审阅-不符`（红）/`需补充资料`（黄）/`待审阅`（灰），并显示审计问题与建议；筛选增加"按审阅状态"。

## 3. 合并命令 `apply_review_notes.py`

```powershell
.venv\Scripts\python.exe -B scripts\apply_review_notes.py `
  --index data\runtime_initial_judgment_recording_tests\task051_index_01\trace_index.json `
  --review-notes data\runtime_initial_judgment_recording_tests\task052_review_01\审阅记录.json `
  --out-dir data\runtime_initial_judgment_recording_tests\task052_merge_01
```

- 校验：`review_version`；资料版本必须与索引 `source_identity` 一致（不一致 → exit 1，精确字段，提示"审阅结论对应旧资料版本"）；每条记录 `case_id/record_id` 必须存在；状态枚举合法；非"待审阅"必须填 `审阅人`、`审阅日期`、`审计问题描述`（长度上限）；禁止 HTML 片段注入（转义检查）。
- 输出：`审阅记录.xlsx`（列：编号/事项或记录/审阅状态/审计问题描述/建议处理/审阅人/审阅日期/对应资料版本/审阅记录版本）、合并后的 `trace_index.json`（每项 `review` 字段）、以及用合并索引重新生成的站点与底稿（徽标、筛选、审阅列）。
- `审阅记录.xlsx` 与合并索引记录自身 SHA；审阅记录版本 = 记录文件 SHA 短标识；**不覆盖**原索引/原底稿/机器证据。
- 未填写的记录保持 `待审阅`，不得虚构默认"相符"。

## 4. 测试与证据

1. 表单/导出：导出 JSON/CSV 结构正确、字段齐全；草稿保存与恢复键正确；页面无 `fetch`/`eval`/外链；转义注入用例。
2. 合并：正常记录 → 徽标、问题、建议、审阅人/日期正确显示；审阅 Excel 内容与记录一致；版本绑定显示正确。
3. 负例：资料版本不符 → exit 1 精确字段；未知 case_id → exit 1；非法状态 → exit 1；非待审阅缺审阅人/日期/问题 → exit 1；HTML 注入 → 转义不执行。
4. 筛选：按审阅状态筛选生效（脚本关闭时仍显示全部行与全部徽标）。
5. 确定性：同索引 + 同审阅记录两次合并，产物字节相同。
6. 只读：原索引、原底稿、输入根、批次、账务字节不变；只新增本轮文件。
7. 规模：200 条事项 + 20 条审阅记录 → 合并成功，链接全解析，耗时/大小登记。

## 5. 保护与停止

一次全树扫描，基线 = TASK-051 接受基线：相对基线**既有 changed 恰 §1 九件**；其余全新增并逐路径登记；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不接 AI/终判、不改演示、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；审阅记录是**人类输入**，须记录审阅人与日期，不覆盖机器证据，不构成审计结论或终判。
