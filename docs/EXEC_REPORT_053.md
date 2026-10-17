# TASK-053 执行回执：修复下钻站点筛选与导出（脚本语法 + 关键词 + 状态/审阅筛选 + 全站覆盖）

日期：2026-10-18。交付状态：站点生成器/测试/指南修复完成，**交独立验收**；
证据已按人类可执行方式保存（逐页 `node --check` + Node 伪 DOM 冒烟 + 重建站点）。
不接 AI/终判、不接演示、不改看板。

依据：`docs/tasks/TASK-053_DRAFT.md`（`e5675231…`）、缺陷记录
`docs/reviews/REVIEW_TASK_052_CORRECTION.md`（`9988cb6e…`）。前置：TASK-052 ACCEPTED。
起点接受快照 `data/reviews/task052_dsh_20261017_01/source_hashes_after.json`
（**193228 项 / `b2767d2a…`**）。本卡**改既有恰三件**，其余全新增。

## 1. 缺陷复现（修复前，已留证）

对 `task052_merge_01/task049_site/all-ledger.html` 提取 `<script>` 执行 `node --check`：

```
SyntaxError: Invalid or unexpected token
  download('审阅记录.csv', lines.join('
                                    ^
```

原因：生成器把 JS 的 `lines.join('\n')` 写成了真实换行，整段脚本语法错误 → 下拉/关键词/导出
事件均未绑定。另：关键词筛选的 `body.filter-keyword` 从未设置；状态下拉"待审阅"映射到
不存在的 `.review` 行类，会隐藏全部行；`case/ledger/voucher/source` 页有审阅表单但无导出按钮。

## 2. 改动身份（恰三件，实测同缓冲长度/SHA）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_drilldown_site.py` | 49420 B | `76526ff79995b186…` |
| `tests/test_drilldown_site.py` | 23354 B | `fdcf7820c1dd7c81…` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 5291 B | `c42080d38820e945…` |

新增 `docs/EXEC_REPORT_053.md` 与 `task053_*` 证据根；未改索引/Excel 生成器、合并命令、适配器、
演示、契约/账证/账实核对器、输入根、既有卡/评审/证据、看板；**未修改 TASK-052 已接受基线**。

## 3. 修复内容（实测）

1. **脚本语法**：生成 HTML 中为 `lines.join('\n')`（反斜杠+n，非真实换行）；全站 31 页每个
   `<script>` 均通过 `node --check`（正常站点与合并站点均 0 错误）。
2. **关键词筛选**：`apply()` 在查询非空时设置 `body.filter-keyword`；不匹配行隐藏（冒烟断言）。
3. **状态下拉**：`全部 / 仅异常 / 仅合规 / 未涉及`，移除"待审阅"；行类 `abnormal / ok / neutral`
   （异常=红/黄，未涉及=neutral）；冒烟断言异常行可见、合规行隐藏。
4. **审阅状态下拉**：`全部 / 待审阅 / 已审阅-相符 / 已审阅-不符 / 需补充资料`，按 `rv-*` 过滤；
   冒烟断言 `rvf-mismatch` 生效。
5. **全站覆盖**：含 `.filter-bar` 的页面都有脚本；含 `.review` 表单的页面都有"导出审阅记录"按钮
   （列表筛选栏 + 每张表单各一，脚本绑定全部按钮）；`compare-*.html` 无筛选栏、无死控件。
6. **导出内容**：JSON 含 `review_version`、`source_version`（取 body `data-review-version`，非空）、
   每条记录字段完整；CSV 数据行引号正确；不联网、无 `fetch`/`XMLHttpRequest`/`eval`/`WebSocket`。

## 4. 验证（可复跑）

- **逐页语法**：对 `task053_site_01`（由已接受 `task051_index_01` 重建）与
  `task053_site_merged_01`（由 `task052_merge_01` 合并索引重建）逐页提取脚本执行 `node --check`：
  **0 错误**（结果 `task053_evidence_01/node_check.json`）。
- **Node 伪 DOM 冒烟**（无第三方依赖）：模拟状态下拉/关键词/审阅下拉/点击导出，断言 body 类、
  行显隐、`rvf-*`、JSON 的 `source_version` 非空与记录数=表单数、CSV 行数与引号；4 个页面全部通过
  （结果 `task053_evidence_01/smoke.json`）。
- **测试**：`tests/test_drilldown_site.py --out-dir …\task053_run_04` → **exit 0、4/4 PASS**
  （静态语法/守卫、伪 DOM 冒烟、回归（链接/语言/P02）、确定性/规模）。
- **回归**：链接 0 断裂、可见文本禁止词零命中、P02 缺证红色"未取得"仍在、两次生成字节相同、
  200 条规模站点生成成功。
- **只读**：重建只写 `task053_*` 新目录；`task051_index_01`、`task052_merge_01` 合并索引与既有站点
  字节不变（`read_only.unchanged=true`）。

## 5. 证据

`data/runtime_initial_judgment_recording_tests/task053_evidence_01/`：`command.json`（命令/退出码/
耗时）、`node_check.json`、`smoke.json`、`smoke_harness.js`、`smoke_*.js`、`site_normal|site_merged`
日志；站点根 `task053_site_01/`、`task053_site_merged_01/`；测试根 `task053_run_04/`。
修复前缺陷复现记录见 `REVIEW_TASK_052_CORRECTION.md`；本回执不修改该记录。

## 6. 保护安排与判据

定稿后**一次**全树扫描（`task053_finalization/protection_scan.py`），基线 = TASK-052 接受快照
（193228 项 / `b2767d2a…`）：相对基线**既有 changed 恰上述三件**；其余全新增并逐路径登记；
missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。

## 7. 边界

真实批准 `null`、真实独立初判未保存、0008、`next/AI=false`。页面只读展示既有合成证据，
不构成审计结论；TASK-052 的机器证据、合并逻辑、审阅记录与版本绑定不受本卡影响。
