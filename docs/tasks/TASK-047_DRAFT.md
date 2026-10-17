# TASK-047：离线静态 HTML 演示报告（四相符 + 线索 + 初判，只读渲染）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-046 ACCEPTED**（基线 176350 项 / `3c520328…`）。依据 `docs/decisions/DECISION_20261017_DSH_STATIC_HTML_REPORT.md`（`DSH-SCOPE-20261017-03`）：**只做只读静态 HTML**，不开服务、不装依赖、不做写操作、不改任何业务口径。

## 1. 允许写入

- **新增代码**：`scripts/build_demo_report_html.py`（唯一新增代码；仅标准库）。
- **新增测试**：`tests/test_demo_report_html.py`。
- **新增文档**：`docs/DEMO_REPORT_HTML_GUIDE.md`、`docs/EXEC_REPORT_047.md`。
- **新增证据根**：`data/runtime_initial_judgment_recording_tests/task047_*/`。
- **不允许修改任何既有文件**（changed 必须为 0）：适配器、演示脚本、契约/账证/账实核对器、既有测试与指南、输入根、卡/评审/证据、看板。

## 2. 命令行与输入

```powershell
.venv\Scripts\python.exe -B scripts\build_demo_report_html.py `
  --run-root data\runtime_initial_judgment_recording_tests\task046_demo_01 `
  --out-dir  data\runtime_initial_judgment_recording_tests\task047_report_01
```

- `--run-root`：已完成的演示运行根（必须已存在、位于 `data/runtime_initial_judgment_recording_tests/` 下）；从中读取
  `demo_summary.json`、`task043_input_check/input_registry.json`、`task044_match/voucher_match_report.json`、
  `task045_reconcile/bank_reconcile_report.json`。
- 同名业务根必须存在并可读：`data/runtime/<run名>/normal.facts/fact_packet.json`、
  `data/human_initial_judgment_records/<run名>/bound/rec_0001/judgment_result.json` 与 `manifest.json`。
- `--out-dir`：必须**从未存在**、位于 `data/runtime_initial_judgment_recording_tests/` 下、目录名以 `task047_` 开头；只写该目录。
- 退出码：`0` 生成成功；`1` 输入证据存在但内容不完整（精确字段）；`2` 参数/路径/环境错误。缺运行根或业务根文件一律 `2` 并给出缺失字段，不做猜测/兜底。

## 3. 输出

1. `index.html`：单文件、内联 CSS、**无 `<script>`、无任何 http(s) 外链/CDN/字体**、UTF-8、A4 可打印、全部动态文本 HTML 转义。
2. `report_source.json`：本次读取的每个证据文件（路径、长度、SHA-256）、`run_root` 名、生成器版本字符串、命令；不含时间戳/随机数（确定性输出）。

## 4. 页面必须包含的区块（顺序固定）

1. **边界横幅**（红黄）：合成数据、非批次批准、非身份认证、`real_approval=null`、不开放 AI/终判、"核对结论由人填写"。
2. **身份**：批次 `batch_normal`、实体（澄明商贸有限公司/CNY/2026-09-01～2026-09-30/截至 2026-09-30）、运行根名。
3. **四相符卡片**：契约（`INPUT_V1_ACCEPTED`、凭证/links/流水计数）、账证（`x/8`、差异 0、账有证无/证有账无）、账实（`x/3`、期间合计 OUT/IN 与差异、未达两侧、余额状态）、初判（状态 `VERIFIED`、记录指纹、材料指纹）。
4. **线索区**：R01–R04 计数；R02 逐条明细（应付/已付/退款/净额/超额，单位"分"与"元"并列），并列出**来源工作表与单元格**（如 `payables!E2`、`allocations!D2/D3`）。
5. **账证明细表**：8 行（账务类型/ID/金额/凭证类型/凭证ID/状态），差异与账有证无/证有账无用红黄高亮；"核对结论"列**空**并注明"由人填写，工具不采集"。
6. **账实明细表**：匹配行（账务ID/类型/流水ID/依据）、期间合计、未达账项两侧、"未达账项≠差错"提示。
7. **初判原文**：六字段（event_id/actor_id/declaration_note/decided_at_raw/assessment/reason）+ 材料/记录指纹 + "合成夹具回放、非真人审批"提示。
8. **追溯链路**：Excel 四表 → 标准化（逐格来源）→ SQL 线索 → 独立复算 → 事实底稿 → 初判 → 账证 → 账实（文字/HTML 图形均可，不用外部图片）。
9. **九权限边界**（全部 false）与**未执行项**（账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、真实数据/强认证）。
10. **页脚**：生成命令、`report_source.json` 身份摘要、"本报告不是审计结论"。

## 5. 只读、确定性、测试

- 生成器只读：运行前后对 `--run-root`、对应业务根、`data/evidence_inputs/` 做字节快照比较，必须完全一致；只写 `--out-dir`。
- 确定性：同一输入两次生成，`index.html` 与 `report_source.json` **字节相同**。
- 测试（`tests/test_demo_report_html.py`，`-B`）：
  1. 从 `task046_demo_01` 生成 → exit 0，包含 8/8、3/3、4000 元、未达 0、九边界 false 等标记；
  2. 两次生成字节相同；
  3. 断言输出无 `<script`、无 `http://`/`https://`、无外链标签；
  4. 注入测试：复制运行根到测试夹具、把批次名改为含 `<b>x</b>` 的字符串 → 生成的 HTML 中该串被转义（不出现裸标签）；
  5. 负例：`--out-dir` 已存在 → exit 2；`--run-root` 不存在 → exit 2；运行根缺 `demo_summary.json` → exit 2 且字段精确。
  6. 只读：生成前后快照一致。
- 证据：从 `task046_demo_01` 生成 `task047_report_01`（正常）；从 `task046_demo_v1_neg`（P02 缺证）生成 `task047_report_v1_neg`（报表须显示账证 6/8 与 2 条 `MISSING_VOUCHER` 高亮，生成器仍 exit 0——渲染成功，差异是内容）。保存命令、stdout/stderr、退出码、两份 `report_source.json` 与输入快照。

## 6. 保护与停止

定稿后**一次**全树扫描，基线 = TASK-046 接受基线：既有 changed 必须为 0；新增仅限 §1 与架构端已知增量（决策记录与本卡/评审逐确切路径登记）；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不把 HTML 接入演示主流程（另行评估）、不改看板、不推进账表/账账或 AI/终判。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；静态报告只读展示既有合成证据，不证明凭证/流水真实，不构成审计结论。
