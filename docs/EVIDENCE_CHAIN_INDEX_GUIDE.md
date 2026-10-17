# 证据链索引指南（线索 → 账务行 → 凭证 → 原始表行）

标识：`TASK-048-trace-index-1.1`。实现：`scripts/build_trace_index.py`（仅标准库）。
依据：`docs/decisions/DECISION_20261017_DSH_DRILLDOWN_UI_V2.md`、`DECISION_20261017_DSH_UI_V3_FULL_FILTER_REVIEW.md`。

## 1. 用法

```powershell
.venv\Scripts\python.exe -B scripts\build_trace_index.py `
  --run-root data\runtime_initial_judgment_recording_tests\task046_demo_01 `
  --out-dir  data\runtime_initial_judgment_recording_tests\task051_index_01
```

- `--run-root`：已完成的四相符演示运行根（只读）。
- `--batch-dir`（可选）：批次源目录，默认 `data/batches/task027r1_run_04/batch_normal`；
  仅测试源漂移时指向副本。
- `--out-dir`：必须从未存在、位于测试根下、以 `task048_` 或 `task051_` 开头。
- 退出码：`0` 成功；`1` 内容不完整/引用不闭合/源漂移（字段精确）；`2` 参数/路径错误。

## 2. 输出（v1.1）

`trace_index.json`：
- `cases[]`：待查事项（R02 线索、账证差异/缺失、账实差异、未达账项），每条含
  `review` 占位：`status=待审阅`、问题/建议/审阅人/日期为 null（本卡不采集，供 TASK-052 合并）。
- `ledger[]`：**全量**账务行（应付 1 / 付款退款 3 / 分摊 3），每条 `status` ∈
  `已核对一致 / 存在差异 / 未取得 / 未涉及`（由账证/账实报告逐项推导，不重算金额），
  并带 `source{sheet, excel_row}`。
- `vouchers[]`：**全量** 8 张凭证（含 `status=已取得`）。
- `source_rows[]`：**全量原表行** 9 行（suppliers 2 / payables 1 / payments 3 / allocations 3）。
- `meta`：`cases_total`、`ledger_total`、`voucher_total`、`source_rows_total`、`status_counts`、
  `source_identity`（源工作簿相对路径/长度/SHA-256/`source_drift`）、`review` 说明、
  `cases_per_page=50`、`pages`、分类计数；无时间戳/随机数。

`trace_index_source.json`：10 个输入（含批次清单与源工作簿）、canonical 输入根清单、命令、版本。

## 3. 规则

1. **数值只复制不重算**：金额/差异取自已接受报告。
2. **引用闭合**：每个 case 至少 1 个账务引用（实有账无除外）；悬空 → exit 1 精确字段。
3. **源漂移拒绝**：生成前校验源工作簿 SHA-256 与批次接收身份（`batch_manifest.hashes`）一致；
   不一致 → **exit 1、`source_drift`**，不生成索引。
4. **多报告合并**：同一账务对象同时出现在账证与账实时合并为一条 case 的多个证据块。
5. **规模**：全量行只做切片索引，不复制全表；`cases_per_page=50`，200 条事项一次生成。

## 4. 测试与证据

`.venv\Scripts\python.exe -B tests\test_trace_index.py --out-dir data\runtime_initial_judgment_recording_tests\task051_run_01`

- 全量计数（台账 7 / 凭证 8 / 原表行 9 / 事项 1）、状态分布（4 已核对一致 + 3 未涉及）、
  `source_identity` 与 `source_drift=OK`、每案 review 占位。
- 源漂移：复制批次源改 1 字节 → exit 1、`source_drift`、原文件不变。
- 确定性、只读、悬空引用 exit 1、缺 `demo_summary` exit 2。

## 5. 备份与版本纪律

源文件只在接收时留存一份（`data/batches/<批次>/source/`），之后只读；生成只记录哈希、不复制源；
阶段证据（Gate 决定/初判/审阅记录）各自小文件留存；生成产物每轮新目录、不覆盖（样本每轮约
0.1–1.5 MB）；里程碑可压缩归档到外部盘，项目内不删除旧证据。

## 6. 边界

索引只是既有合成证据的导航数据；不证明凭证/流水真实，不构成审计结论；
`real_approval=null`、真实初始初判未保存、`next_step_allowed=false`、`ai_enabled=false`。

## 7. v1.1 审阅字段（TASK-052）

`ledger[]`、`vouchers[]`、`source_rows[]` 与 `cases[]` 均带 `review` 占位：
`status=待审阅`、`issue/suggestion/reviewer/date=null`。合并命令 `scripts/apply_review_notes.py`
校验人类审阅记录后写回这些字段（不覆盖机器证据）；未填写记录保持 `待审阅`。

## 8. 索引 v1.2：可选 `gl` 节（TASK-057）

- 新增可选参数 `--gl-root data/evidence_inputs/gl_v1`、`--gl-report <核对报告>`；
  **两者同时提供**才生成 `gl` 节；缺省时旧行为不变（v1.2 无 gl）。
- `gl` 节只读取/复制：科目表、余额表 rows/totals、凭证分录（含附件引用）、总账、明细账、报表、
  银行对账单/日记账、六类检查状态/发现/备注/未执行项、来源身份（路径/长度/SHA）。
- 每张凭证带 `ledger_refs`（记-001↔AP01、记-002↔P01、记-003↔P02、记-004↔R01）与
  `case_refs`（CASE-0001），供站点/底稿建立只读链接。
- 确定性：无时间戳/随机数；同一输入字节相同；旧索引（无 gl）仍可被站点/底稿读取。
