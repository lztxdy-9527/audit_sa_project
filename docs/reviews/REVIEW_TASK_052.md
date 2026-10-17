# TASK-052 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-18，DSH 架构/测试验收端对"网页审阅（表单 + 导出 + 合并）与《审阅记录.xlsx》"独立复验。表单与草稿、合并校验、徽标与筛选、负例拒绝、确定性与只读均成立；架构端自跑复现。审阅记录是**人类输入**，不覆盖机器证据，不构成审计结论或终判。

## 1. 改动身份（恰九件 + 新增）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_trace_index.py` | 36066 B | `9bc091f46276cc817176ffd28f29795d8df57e97cda04cacbb2fe3f01f7c075d` |
| `scripts/build_drilldown_site.py` | 49344 B | `c499fdf78c304ae192b24d48a03c367aa0a1995e86988ba68f21d16b52484f7c` |
| `scripts/build_excel_workbook.py` | 29152 B | `ca972c6c155c6f1f5e3989a47e17557f837ad970b14105d037e49ffe32bc1d51` |
| `tests/test_trace_index.py` | 12827 B | `b2f36e90cfb055d6f8c1900049bd1027d171fe30f24e85fd26732525d1b07e98` |
| `tests/test_drilldown_site.py` | 16257 B | `dad0556970f0e3ee7d47c7ffc47c42f2efa2f465b90ed7b4c5e6a48e27d0fb8d` |
| `tests/test_excel_workbook.py` | 17434 B | `36f4f5e080adae2e12a5794ab5a874a58c5ddacc93947247655b90440377bcd9` |
| `docs/EVIDENCE_CHAIN_INDEX_GUIDE.md` | 4245 B | `5ac0ddf32174ebf426d4ce123165b08e8c49ffc4c262b873803256c35e95dc62` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 3755 B | `316c02b014c859903e83163d2bbba852e3391b49543a2ef3087df370f2ad8a28` |
| `docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md` | 3324 B | `2d97f839a6a64f79aa321577d9173948d124872704e958a7963ce330533055d7` |
| `scripts/apply_review_notes.py`（新增） | 15595 B | `492c3fb103483e6f03847b6b73dbd4f8765a034d05cd0f141253a61fa2ac05d2` |
| `tests/test_review_notes.py`（新增） | 15388 B | `c56648955675d38f3aafc5b868c4952aad778647e5e41ed7314efe2661ce5e9f` |
| `docs/REVIEW_NOTES_GUIDE.md`（新增） | 3593 B | `f6817589323063cb5ceba4c8fd8d68dee1fa67e85819b5cd18ae003230abe0ae` |
| `docs/EXEC_REPORT_052.md` | 5611 B | `183b4a39e2d38acd882582c8951b5988752553d4c768671ed0de41bde4f34029` |

## 2. 架构端独立运行（27 项检查全过）

- **站点（未合并）**：表单控件（审阅状态/审计问题）存在；`localStorage` 草稿、"导出审阅记录"存在；无 `fetch`/`XHR`/`eval`/`WebSocket`、无外链。
- **自造审阅记录**（3 条：CASE-0001 已审阅-不符；P01 需补充资料；A01 待审阅）→ 合并 **exit 0**：
  - 合并索引逐项 `review` 正确（CASE-0001 的问题原文保留；P01 需补充资料；A01 待审阅）；
  - `审阅记录.xlsx` 存在，表头含"审阅状态/审计问题描述/审阅人/对应资料版本"，P01 行状态正确；
  - 合并站点出现"已审阅-不符 / 需补充资料"徽标与审阅筛选；
  - `merge_source.json` 记录版本绑定；**原索引未被覆盖**。
- **负例全部 exit 1**：资料版本不符、未知记录、非法状态、非待审阅缺审阅人、HTML 注入（`<b>`）。
- **确定性**：同索引 + 同审阅记录两次合并，除 `merge_source.json` 内含输出路径外，**其余产物字节相同**。
- **测试**：审阅 8/8、索引 5/5、站点 8/8、工作簿 8/8 全过。
- **只读**：运行根、`data/evidence_inputs/`、业务根字节不变。

## 3. 保护与历史

执行端一次全树扫描：基线 186238 项 / `faa4ff91…`，**changed 恰九件**、missing 0、读取错误 0、新增 4229 项全登记；架构端独立扫描复核（`data/reviews/task052_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 边界

未接 AI/终判、未接演示、未改看板；未做账表/账账、影像/OCR、外部查验、函证/盘点、真实数据/强认证。审阅记录须记录审阅人与日期；草稿仅存浏览器、不是证据；合并后的记录不覆盖机器证据，不构成审计结论。

## 5. 接受与项目状态

发布新接受基线 `data/reviews/task052_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。**本轮 UI 需求集（全量 + 筛选 + 网页审阅 + 审阅 Excel）全部完成**。可选后续（另行授权）：把索引/站点/底稿/审阅合并接进演示主命令；账表/账账（需报表输入）；AI/终判与真实数据。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
