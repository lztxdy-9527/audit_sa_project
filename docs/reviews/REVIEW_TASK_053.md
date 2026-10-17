# TASK-053 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-18，DSH 架构/测试验收端对"筛选/导出修复"独立复验。**本次我实际执行了页面脚本**：逐页 `node --check`、用伪 DOM 冒烟验证筛选/关键词/导出，不再只做静态检查。缺陷记录 `REVIEW_TASK_052_CORRECTION.md` 所述问题已关闭。页面只读展示既有合成证据，不构成审计结论。

## 1. 改动身份（恰三件 + 回执）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_drilldown_site.py` | 49420 B | `76526ff79995b186edd2779ddc557bf54ee9f2bb96d19f0c2694144151300829` |
| `tests/test_drilldown_site.py` | 23354 B | `fdcf7820c1dd7c81d372d90f3aa706678acd8742b912632f8601a883b00ad30b` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 5291 B | `c42080d38820e9455844d6f38b26db0340eeb4b1e0e1546eeec512b7e9ae9c4b` |
| `docs/EXEC_REPORT_053.md` | 5347 B | `f62d0fe9fd1315c720b442b50648d0f2ddc3ef48cc0e44188aed53585cacd2a0` |

## 2. 架构端独立运行（35 项检查全过）

- **重建站点**：从已接受索引 `task051_index_01` 与合并索引 `task052_merge_01` 重建，均 exit 0。
- **脚本语法**：对重建站点的**每一页**提取 `<script>` 执行 `node --check`：**0 失败**；生成代码中 CSV 拼接为 `lines.join('\n')`（反斜杠+n），不再是真实换行。
- **静态守卫**：状态下拉含"未涉及"、不含"待审阅"；审阅下拉四类齐全；含筛选栏的页面都有脚本；含审阅表单的页面都有导出按钮；`compare-*` 无筛选栏。
- **伪 DOM 冒烟**（用执行端提供的 harness 跑**我重建的页面**）：
  - 列表页：`status_abnormal`、`ok_hidden`、`status_ok`、`rvf_mismatch`、`filter_keyword`、`keyword_matches`、`keyword_hides` 全为 true；
  - 合并列表页：`json_export`、`json_review_version`、`json_source_version`、`json_records`、`json_fields`、`csv_export`、`csv_lines`、`csv_quotes`、`export_buttons` 全为 true；
  - 合并事项页：导出 JSON 可用、`source_version` 非空。
- **测试复跑**：`tests/test_drilldown_site.py` → 4/4 PASS。
- **链接/语言**：重建站点链接 0 断裂、无外链、可见文本禁止词零命中。
- **只读**：重建前后索引、`data/evidence_inputs/` 字节不变。

## 3. 保护与历史

执行端一次全树扫描：基线 193228 项 / `b2767d2a…`，**changed 恰三件**、missing 0、读取错误 0、新增 1989 项全登记；架构端独立扫描复核（`data/reviews/task053_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 缺陷关闭与边界

- `REVIEW_TASK_052_CORRECTION.md` 所列缺陷（脚本语法、关键词失效、"待审阅"隐藏全部、compare 死控件、缺少导出按钮）**全部关闭**。
- TASK-052 的机器证据、合并逻辑、审阅记录与版本绑定不受影响。
- 未改索引/Excel 生成器、合并命令、适配器、演示、核对器、输入根、既有卡/评审/证据、看板。

## 5. 接受与下一卡

发布新接受基线 `data/reviews/task053_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-054（口径命名 + 勾稽底稿/明细表/凭证抽查表 + 缺口声明）**，卡身份 `c5f4b179…6d47e1`（已按人类反馈修正：管理口径，不是会计分录；不做试算平衡/账账/账表）。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
