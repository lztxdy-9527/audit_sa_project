# 离线静态 HTML 演示报告指南

标识：`TASK-047-demo-report-1.0`。实现：`scripts/build_demo_report_html.py`（唯一新增代码，仅标准库）。
依据：`docs/decisions/DECISION_20261017_DSH_STATIC_HTML_REPORT.md`（`DSH-SCOPE-20261017-03`）。
只做**只读静态 HTML**：不开服务、不装依赖、不做写操作、不改任何业务口径。

边界：合成数据只读展示；不是批次批准、不是身份认证；`real_approval=null`、真实独立初判未保存、
`next_step_allowed=false`、`ai_enabled=false`；不证明凭证/流水真实，不构成审计结论；核对结论由人填写。

## 1. 用法

```powershell
.venv\Scripts\python.exe -B scripts\build_demo_report_html.py `
  --run-root data\runtime_initial_judgment_recording_tests\task046_demo_01 `
  --out-dir  data\runtime_initial_judgment_recording_tests\task047_report_01
```

- `--run-root`：已完成的四相符演示运行根（必须存在、位于
  `data/runtime_initial_judgment_recording_tests/` 下）；读取其中的
  `demo_summary.json`、`task043_input_check/input_registry.json`、
  `task044_match/voucher_match_report.json`、`task045_reconcile/bank_reconcile_report.json`。
- 同名业务根：`data/runtime/<run名>/normal.facts/fact_packet.json`、
  `data/human_initial_judgment_records/<run名>/bound/rec_0001/{judgment_result,manifest}.json`。
- `--out-dir`：必须**从未存在**、位于同一测试根下、目录名以 `task047_` 开头；只写该目录。
- 退出码：`0` 生成成功；`1` 输入证据存在但内容不完整（精确字段）；`2` 参数/路径/环境错误
  （含缺运行根或业务根文件，给出缺失字段，不猜测/兜底）。

## 2. 输出

- `index.html`：单文件、内联 CSS、**无 `<script>`、无 `<link>`/`<img>`/`@import`/`url(`、
  无 `http://`/`https://` 外链/CDN/字体**、UTF-8、A4 可打印（`@page`）、全部动态文本 HTML 转义。
- `report_source.json`：逐输入文件（长度/SHA-256）、运行根名、生成器版本、命令（`--out-dir` 记为
  `<out-dir>` 占位以保持确定性）；**不含时间戳/随机数**，同一输入两次生成字节相同。

## 3. 页面区块（顺序固定）

1. **边界横幅**：合成数据、非批次批准、非身份认证、`real_approval=null`、不开放 AI/终判、核对结论由人填写。
2. **身份**：批次、实体（澄明商贸有限公司 / CNY / 2026-09-01～2026-09-30 / 截至 2026-09-30）、运行根名。
3. **四相符卡片**：契约（`INPUT_V1_ACCEPTED`、凭证/links/流水计数）；账证（`x/8`、差异、账有证无/证有账无）；
   账实（`x/3`、期间合计 OUT/IN 与差异、未达两侧、余额状态）；初判（`VERIFIED`、记录指纹、材料指纹）。
4. **线索区**：R01–R04 计数；R02 逐条明细（应付/已付/退款/净额/超额，分与元并列）与来源工作表/单元格
   （如 `payables!E2`、`allocations!D2/D3`、`payments!F2/F3`、`refunds!F4`）。
5. **账证明细表**：逐项（账务类型/ID/金额/凭证类型/凭证 ID/状态）；差异与账有证无/证有账无用红黄高亮；
   "核对结论"列空并注明"由人填写，工具不采集"。
6. **账实明细表**：匹配行（账务 ID/类型/流水 ID/依据）、期间合计、未达账项两侧、"未达账项≠差错"提示。
7. **初判原文**：六字段（event_id/actor_id/declaration_note/decided_at_raw/assessment/reason）+ 材料/记录指纹 +
   "合成夹具回放、非真人审批"提示。
8. **追溯链路**：Excel 四表 → 标准化（逐格来源）→ SQL 线索 → 独立复算 → 事实底稿 → 初判 → 账证 → 账实。
9. **九权限边界**（全部 false）与未执行项（账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、真实数据/强认证）。
10. **页脚**：生成命令、输入证据身份摘要、"本报告不是审计结论"。

## 4. 只读、确定性与测试

- 生成器只读：运行前后对 `--run-root`、对应业务根、`data/evidence_inputs/` 做字节快照比较，必须完全一致；
  只写 `--out-dir`。
- 确定性：同一 `--run-root` 两次生成（不同 `--out-dir`），`index.html` 与 `report_source.json` 字节相同。
- 测试（`tests/test_demo_report_html.py`，`-B`）覆盖：正常 8/8 与 3/3、4000 元、未达 0、九边界；
  两次生成字节相同；无脚本/外链；批次名注入 `<b>x</b>` 被转义不出现裸标签；负例 out-dir 已存在/run-root
  不存在/缺 `demo_summary` → exit 2，内容缺 `four_way` → exit 1（字段精确）；P02 缺证运行根
  （`task046_demo_v1_neg`）→ 账证 6/8 与 2 条 `MISSING_VOUCHER` 高亮、生成器仍 exit 0（差异是内容，不是渲染失败）。
- 证据：`task047_report_01`（正常）、`task047_report_v1_neg`（P02 缺证）、`task047_run_03`（测试 8/8）、
  `task047_evidence_01`（命令/退出码/stdout/stderr/两份 `report_source.json`/输入前后快照）。

## 5. 边界与未执行

本报告只读展示既有合成证据，不证明凭证/流水真实，不构成审计结论；不接入演示主流程（另行评估）；
不做账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、真实数据/强认证（`null` + 原因）。
