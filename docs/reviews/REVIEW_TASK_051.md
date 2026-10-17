# TASK-051 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对"全量清单 + 筛选（内嵌脚本限用途）+ Excel 自动筛选 + 源漂移拒绝 + 备份纪律"独立复验。全量完整性、筛选守卫、源漂移、自动筛选与规模均成立；架构端自跑复现。页面/底稿只读展示既有合成证据，不构成审计结论。

## 1. 改动身份（恰九件 + 回执）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_trace_index.py` | 35020 B | `441c73753dfa9be83f768756b66a4d005b34d8f262fc71a373e12f9c45e559f7` |
| `scripts/build_drilldown_site.py` | 39227 B | `787c632f9fbd0fe7301bd42ec01cfc5255cc06d9a3787bacada6e2302899ecfe` |
| `scripts/build_excel_workbook.py` | 29129 B | `eac9dfb1339cf8924467b57cd00d48a3f62c072611d3d45d8cfb7357987af02c` |
| `tests/test_trace_index.py` | 12201 B | `a5a649285b817c4a5d789fedc7e4c7f5ff14b6580faeba79414ebf655f7165bf` |
| `tests/test_drilldown_site.py` | 15847 B | `62805bffcf1008db7dcce4e10030127d31211af90cf8737f902b8efe0de89568` |
| `tests/test_excel_workbook.py` | 17411 B | `bfe85a5008783e45fa0b6268a69e37709d74f2926e59da256ead2d7475167325` |
| `docs/EVIDENCE_CHAIN_INDEX_GUIDE.md` | 3897 B | `7ac669a1d71828771a51d759cb4ee8437a8e179a18eb05816d8a409f19793a94` |
| `docs/DRILLDOWN_SITE_GUIDE.md` | 2993 B | `0f2ac1d588bad07dcf986ee7b8ae4f42c50b81d4bc7049f3f6119e869fcaa8b9` |
| `docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md` | 2885 B | `d3a4484cccbc83c81f53e2416974d7d16c2137edad2489442837995b48031ee7` |
| `docs/EXEC_REPORT_051.md` | 6236 B | `0f5933d8b7dec651ab20483ac228361d66c0d6b0296691aa1867167115ebe13a` |

## 2. 架构端独立运行（33 项检查全过）

- **索引 v1.1**（我的新根 `task051_dsh_01_d`）：exit 0；`cases=1`、`ledger=7`（**已核对一致 4 / 未涉及 3**）、`vouchers=8`、`source_rows=9`；`meta.source_identity.sha256=8f6f2a98…` 且 `source_drift.status=OK`；每案 `review={status:待审阅, issue/suggestion/reviewer/date:null}`。
- **源漂移**：复制批次并改源 1 字节 → 索引生成 **exit 1、`source_drift`**；原批次源哈希不变。
- **站点 v1.1**（我的新根）：exit 0；**31 页**；含 `all-ledger/all-vouchers/all-source` 全量页；全量台账页 **7 行预渲染**、状态列与"仅异常/仅合规/待审阅+关键词"筛选存在；**无 `fetch`/`XMLHttpRequest`/`eval`/`WebSocket`**；`@media print` 全量打印规则与说明存在；内部链接 0 断裂、无外链；可见文本禁止词零命中。
- **工作簿 v1.1**：exit 0；六页顺序正确；`台账明细/原始表行/凭证` **auto_filter** 均存在；内部定位链接全部可解析；《说明》含备份/接收纪律。
- **测试**：索引 5/5、站点 8/8、工作簿 8/8 全部通过。
- **规模**（200 条事项索引）：站点 **>400 页**、工作簿生成成功、链接全部可解析。
- **只读**：生成/测试前后，运行根、批次源、200 条索引、`data/evidence_inputs/` 字节不变。

## 3. 保护与历史

执行端一次全树扫描：基线 179749 项 / `4f895b86…`，**changed 恰九件**、missing 0、读取错误 0、新增 1794 项全登记；架构端独立扫描复核（`data/reviews/task051_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 边界

未实现审阅表单（TASK-052 承担）；未接入演示；未做账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、真实数据/强认证。筛选脚本仅切换显示，不修改数据；打印为全量视图；禁用脚本默认全量。

## 5. 接受与下一卡

发布新接受基线 `data/reviews/task051_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。**放行 TASK-052（网页审阅：表单 + 导出 + 合并 + 审阅记录 Excel）**。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
