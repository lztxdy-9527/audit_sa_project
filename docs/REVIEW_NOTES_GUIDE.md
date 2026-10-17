# 网页审阅、导出与合并指南（TASK-052）

标识：`TASK-052-review-1.0`。实现：`scripts/apply_review_notes.py`（唯一新增代码）；
站点表单/导出由 `scripts/build_drilldown_site.py` 生成。
依据：`docs/decisions/DECISION_20261017_DSH_UI_V3_FULL_FILTER_REVIEW.md`（`DSH-SCOPE-20261017-05` D-UI3-3）。

边界：审阅记录是**人类输入**；网页只存浏览器草稿、不写证据目录；合并命令不覆盖机器证据；
不构成审计结论或终判；`real_approval=null`、真实初判未保存、0008、`next/AI=false`。

## 1. 网页填写与导出

- 每条事项页/全量清单行旁有审阅表单：审阅状态（待审阅 / 已审阅-相符 / 已审阅-不符 / 需补充资料）、
  审计问题描述、建议处理、审阅人、审阅日期（手工输入，不预填）。
- 草稿仅保存在本浏览器 `localStorage`（键含资料版本短标识 + 记录类型 + 记录 ID）；
  页面标注"草稿仅保存在本浏览器，导出并合并后才成为审阅记录"。
- 导出按钮生成 `审阅记录.json` 与 `审阅记录.csv`（含 `review_version`、资料版本短标识、
  每条记录字段）；不写文件、不发网络请求；无 `fetch`/`XMLHttpRequest`/`eval`/`WebSocket`。

## 2. 合并命令

```powershell
.venv\Scripts\python.exe -B scripts\apply_review_notes.py `
  --index data\runtime_initial_judgment_recording_tests\task052_index_01\trace_index.json `
  --review-notes data\runtime_initial_judgment_recording_tests\task052_review_01\审阅记录.json `
  --out-dir data\runtime_initial_judgment_recording_tests\task052_merge_01
```

校验：`review_version`；`source_version` 必须与索引 `source_identity` 短标识一致（不一致 →
exit 1，提示"审阅结论对应旧资料版本"）；`record_type ∈ {case, ledger, voucher, source}` 且记录存在；
状态枚举合法；非"待审阅"必须填写审阅人、审阅日期（YYYY-MM-DD）、审计问题描述；长度上限；
禁止 HTML 片段（`<`/`>`）。任一不满足 → exit 1 精确字段。

输出（全部新文件，不覆盖原索引/原底稿/机器证据）：
- `审阅记录.xlsx`（列：编号/事项或记录/审阅状态/审计问题描述/建议处理/审阅人/审阅日期/
  对应资料版本/审阅记录版本；自动筛选）；
- 合并后的 `trace_index.json`（每项 `review` 字段；未填写保持 `待审阅`）；
- `task049_site/`（徽标、问题、建议、审阅状态筛选、表单与导出）；
- `task050_workbook/证据链底稿.xlsx`（全量 + 自动筛选）；
- `merge_source.json`（输入/输出身份、审阅记录版本 = 记录文件 SHA 短标识）。

## 3. 测试与证据

`.venv\Scripts\python.exe -B tests\test_review_notes.py --out-dir data\runtime_initial_judgment_recording_tests\task052_run_03`

- 正常合并：徽标/问题/建议/审阅人/日期、审阅记录.xlsx、合并索引、站点与底稿。
- 负例：资料版本不符、未知记录、非法状态、非待审阅缺必填、HTML 注入（exit 1 精确字段）。
- 确定性：两次合并产物字节相同；只读：原索引/审阅文件/批次/输入不变。
- 规模：200 条事项 + 20 条审阅记录合并成功，链接全解析，耗时/大小登记。

## 4. 边界与未执行

不接 AI/终判、不接演示、不改看板；未做账表/账账、影像/OCR、外部查验、函证/盘点、真实数据/强认证
（`null` + 原因）。审阅记录不覆盖机器证据，不构成审计结论。
