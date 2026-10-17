# TASK-048：证据链索引（线索 → 账务行 → 凭证 → 原始表行）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-047 ACCEPTED**（基线 176686 项 / `276bb699…`）。依据 `docs/decisions/DECISION_20261017_DSH_DRILLDOWN_UI_V2.md`（`DSH-SCOPE-20261017-04`）。本卡只生成**数据索引**，不生成页面/工作簿（分别由 TASK-049/050 承担）；不改任何既有文件。

## 1. 允许写入

- 新增代码 `scripts/build_trace_index.py`（仅标准库）；
- 新增测试 `tests/test_trace_index.py`；
- 新增文档 `docs/EVIDENCE_CHAIN_INDEX_GUIDE.md`、`docs/EXEC_REPORT_048.md`；
- 新增证据根 `data/runtime_initial_judgment_recording_tests/task048_*/`。
- **不允许修改任何既有文件**（changed=0）：适配器、演示脚本、契约/账证/账实/HTML 生成器、既有测试/指南、输入根、卡/评审/证据、看板。

## 2. 命令与输入

```powershell
.venv\Scripts\python.exe -B scripts\build_trace_index.py `
  --run-root data\runtime_initial_judgment_recording_tests\task046_demo_01 `
  --out-dir  data\runtime_initial_judgment_recording_tests\task048_index_01
```

- `--run-root`：已完成的演示运行根（含 `demo_summary.json`、`task043_input_check/input_registry.json`、`task044_match/voucher_match_report.json`、`task045_reconcile/bank_reconcile_report.json`）；同名业务根（`data/runtime/<run>/normal.facts/fact_packet.json`、`data/human_initial_judgment_records/<run>/bound/rec_0001/judgment_result.json|manifest.json`）与账务 `data/runtime/task042_dsh_01/normal.load/normalized.json` 只读。
- `--out-dir`：必须从未存在、位于 `data/runtime_initial_judgment_recording_tests/` 下、以 `task048_` 开头；只写该目录。
- 退出码：`0` 成功；`1` 输入内容不完整/引用不闭合（精确字段）；`2` 参数/路径错误。

## 3. 输出

1. `trace_index.json`：唯一数据源，供 TASK-049/050 读取。结构：
   - `cases[]`：每条待查事项一条（R02 线索、账证差异、账证缺失、账实差异、未达账项），字段：`case_id`、`title`（审计语言）、`severity`（`red`=差异/未取得、`yellow`=待核查线索、`green`=已核对）、`amounts`（分与元并列，数值只从既有报告复制，不重算）、`ledger_refs[]`（账务类型/ID/金额）、`voucher_refs[]`（凭证类型/ID/字段）、`source_refs[]`（工作表/行/列/原值）、`image_placeholders[]`（发票/回单占位，标注“模拟数据，无真实图像”）。
   - `ledger[]`：账务行切片（应付/付款/退款/分摊），每字段带 `source{sheet,excel_row,column_letter,raw_value,standard_value}`（取自 `normalized.json`）；**只含事项涉及的行**。
   - `vouchers[]`：凭证记录切片（发票/合同/回单/审批/入库），字段 + 来源输入文件相对路径与记录序号 + `image_placeholder`。
   - `source_rows[]`：事项涉及的原表行副本（工作表/行/各列原值），供单页比对与 Excel 复制。
   - `meta`：运行根名、批次/实体/期间、`cases_total`、`cases_per_page=50`、各分类计数、生成器版本；**不含时间戳/随机数**（确定性）。
2. `trace_index_source.json`：读取的每个输入文件（路径/长度/SHA-256）与命令。

## 4. 规则与校验

1. **数值只复制不重算**：金额/差异/合计一律取自已接受报告；索引不得出现报告之外的新数字。
2. **引用闭合**：每个 case 至少 1 个账务引用；所有 `ledger_refs`/`voucher_refs`/`source_refs` 必须能在切片或原表中解析；悬空引用 → exit 1 并给出 `case_id + 缺失字段`。
3. **多报告合并**：同一账务对象同时出现在账证与账实中时合并为一条 case 的多个"证据块"，不重复计数；缺失凭证（P02 类）生成 `red` 事项，凭证区写"未取得"并保留占位。
4. **语言**：索引中的 `title`/`label` 只用审计语言；技术标识（路径/编号/SHA）只出现在 `meta`/`source` 字段，供页面生成器隐藏或折叠。
5. **规模**：只索引事项及其切片，不复制全表；`cases` 超过 50 时仍一次生成（页面分页由 TASK-049 处理），索引文件大小与生成耗时须在证据中如实登记。

## 5. 测试与证据

- 正常（`task046_demo_01`）：cases 至少含 R02（4000 元超额）；账证/账实均 `ALL_MATCHED` 时无 red 事项；引用全部闭合。
- P02 缺证（`task046_demo_v1_neg`）：生成 red 事项（付款 P02、未取得审批单/回单），占位存在。
- 规模：复制运行根构造 **200 条事项**的合成夹具（仅用于本卡）→ 索引成功、`cases_total=200`、分页元数据正确、无悬空引用；记录生成耗时与文件大小。
- 确定性：同一输入两次生成 `trace_index.json` 字节相同。
- 只读：运行前后运行根/业务根/输入根/账务字节快照一致。
- 负例：悬空账务引用注入 → exit 1 精确字段；缺 `demo_summary.json` → exit 2。

## 6. 保护与停止

一次全树扫描，基线 = TASK-047 接受基线：既有 changed 必须为 0；新增仅限 §1 与架构端已知增量（决策记录与本卡逐确切路径登记）；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不生成页面/工作簿、不改看板、不推进账表/账账或 AI/终判。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；索引只是既有证据的导航数据，不证明凭证/流水真实，不构成审计结论。
