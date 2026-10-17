# TASK-053：修复下钻站点筛选与导出（脚本语法 + 关键词 + 状态/审阅筛选 + 全站覆盖）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-052 ACCEPTED**（基线 193228 项 / `b2767d2a…`），缺陷见 `docs/reviews/REVIEW_TASK_052_CORRECTION.md`：页面内嵌脚本在 `lines.join('\n')` 处写成真实换行，整段脚本语法错误，**筛选与导出全部失效**。

## 1. 允许修改/新增

**允许修改（changed 恰三件）**：`scripts/build_drilldown_site.py`、`tests/test_drilldown_site.py`、`docs/DRILLDOWN_SITE_GUIDE.md`。
**允许新增**：`docs/EXEC_REPORT_053.md`、证据根 `data/runtime_initial_judgment_recording_tests/task053_*/`。
**禁止**：改索引/Excel 生成器、合并命令、适配器、演示、契约/账证/账实核对器、输入根、既有卡/评审/证据、看板。**不修改 TASK-052 已接受基线**（缺陷记录单独归档）。

## 2. 必须修复的缺陷

1. **脚本语法**：生成 HTML 中的 CSV 拼接必须写成 `lines.join('\n')` 的转义形式（生成文件里是反斜杠+n，不是真实换行）；全站每个 `<script>` 都必须通过 `node --check`。
2. **关键词筛选真实生效**：输入关键词后，不匹配的行必须隐藏；实现方式自定（建议 `body.filter-keyword tr.row:not(.match){display:none}`，`apply()` 在查询非空时给 body 加 `filter-keyword`）。
3. **状态下拉**：`全部 / 仅异常 / 仅合规 / 未涉及`；**移除 "待审阅"**（与审阅状态下拉重复且旧映射会隐藏全部行）。行必须有 `ok / abnormal / neutral` 之一（异常=红/黄，未涉及=neutral）。
4. **审阅状态下拉**：`全部 / 待审阅 / 已审阅-相符 / 已审阅-不符 / 需补充资料`，按 `rv-*` 类过滤。
5. **全站覆盖**：每个含 `.filter-bar` 的页面都必须有脚本；每个含 `.review` 表单的页面都必须有可用的"导出审阅记录"按钮；`compare-*.html` 若有筛选栏则加脚本（否则移除筛选栏），不得留"死控件"。
6. **导出内容**：JSON 含 `review_version`、`source_version`（取 body `data-review-version`，必须非空）、每条记录字段完整；CSV 引号正确；不得联网。

## 3. 测试（必须能拦住这次缺陷）

1. **语法**：从每个生成的 `.html` 提取 `<script>`，逐个 `node --check`；任何失败即测试失败（node 缺失时跳过并记录，但本机 node v24 可用）。
2. **静态守卫**：断言生成代码中 `lines.join('` 后紧跟转义 `\\n` 而非真实换行；断言 `filter-keyword` 类会被设置；断言状态选项不再含"待审阅"；断言 `.filter-bar` 页面都有脚本、`.review` 页面都有导出按钮。
3. **功能冒烟（Node 伪 DOM，无第三方依赖）**：构造伪 `document`（querySelector/querySelectorAll/addEventListener/classList、localStorage、Blob/URL、anchor click 捕获），执行页面脚本：
   - 改状态下拉 → 断言对应 body class 变化、异常/合规行显隐正确；
   - 输入关键词 → 断言不匹配行被隐藏；
   - 改审阅下拉 → 断言 `rvf-*` 类生效；
   - 点导出 → 断言 JSON 的 `source_version` 非空、记录数与表单数一致；CSV 行数与引号正确。
4. **回归**：链接完整、无外链、转义、语言红线、打印全量、确定性、只读、规模（200 条）沿用。
5. **证据**：从 `task051_index_01`（已接受索引）与 `task052_review_01`（已接受审阅记录）重建站点与合并站点；保存每个页面 `node --check` 结果、冒烟输出、命令与退出码到 `task053_evidence_01`。

## 4. 验收标准（架构端）

- 我用 `node --check` 逐页复核，并用**自己的**伪 DOM 冒烟复跑筛选/关键词/导出；
- 打开合并站点，操作下拉/输入/导出均有反应；
- changed 恰三件且身份登记；其余全新增；139/27/326/19/TASK-030 41 B 锁继续冻结。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；页面只读展示既有合成证据，不构成审计结论。
