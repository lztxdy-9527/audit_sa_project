# TASK-057：把借贷核对接进站点与 Excel（科目余额表/凭证分录/总账明细/试算/账表/银行调节）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-056 ACCEPTED**（GL 六类核对已接受）。依据 `DSH-SCOPE-20261017-06` D-GL-2/D-GL-4：把 GL 与核对结果做成审计人员可读的站点页与 Excel 底稿，只读、纯审计语言、与既有证据同源。

## 1. 允许修改/新增

**允许修改（changed 恰九件）**：`scripts/build_trace_index.py`、`scripts/build_drilldown_site.py`、`scripts/build_excel_workbook.py`、`tests/test_trace_index.py`、`tests/test_drilldown_site.py`、`tests/test_excel_workbook.py`、`docs/EVIDENCE_CHAIN_INDEX_GUIDE.md`、`docs/DRILLDOWN_SITE_GUIDE.md`、`docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md`。
**允许新增**：`docs/EXEC_REPORT_057.md`、证据根 `data/runtime_initial_judgment_recording_tests/task057_*/`。
**禁止**：改 GL 输入包、核对引擎、合并命令、适配器、演示、契约/账证/账实核对器、既有卡/评审/证据、看板。

## 2. 索引 v1.2（新增 `gl` 节，向后兼容）

- 新增可选参数：`--gl-root data/evidence_inputs/gl_v1`、`--gl-report data/runtime_initial_judgment_recording_tests/task056_gl_01/gl_reconcile_report.json`；缺省时不生成 `gl` 节（旧行为不变）。
- `gl` 节只**读取/复制**，不重算：科目表、余额表 rows/totals、凭证分录（含附件引用）、总账、明细账、报表、银行对账单/日记账、六类检查状态/发现/备注/未执行项、来源身份（路径/长度/SHA）。
- 每张凭证与既有账务/事项建立**只读链接**（记-001↔AP01、记-002↔P01、记-003↔P02、记-004↔R01；案例 CASE-0001 关联这四张）。
- 确定性：无时间戳/随机数；同一输入字节相同。

## 3. 站点新增页（每页有"借贷核对"导航与面包屑）

1. `gl-trial-balance.html`：科目余额表（期初/本期借/本期贷/期末，借贷分列，合计 20,000=20,000；应付 4,000 借方高亮）。
2. `gl-journal.html`：记账凭证分录（记-001～004，借/贷科目、金额、附件、对应业务单据；可点入凭证/原始行）。
3. `gl-ledger.html`：总账与明细账（三栏式发生额与余额；应付按 AP01、银行按基本户；逐笔余额滚动）。
4. `gl-report.html`：账表核对（科目余额表↔报表；应付 0 / 预付 4,000 重分类；资产 20,000=负债+权益）。
5. `gl-bank.html`：银行余额调节表（期初 20,000 + 收入 1,000 − 支出 10,000 = 期末 11,000；未达账项 0）。
6. `gl-checks.html`：六类 + 附件核对结果（MATCHED/DIFFERENCES、findings、备注、未执行项）。
- 既有 `business-AP01.html` 增加"查看记账凭证/借贷核对"链接；全站导航加"借贷核对"入口。
- 所有数字来自索引 `gl` 节，不重算；纯审计语言（借贷、科目、期初/本期/期末、余额方向、未达账项），不出现 JSON/hash 等技术词。

## 4. Excel 新增页

《科目余额表》《记账凭证》《总账》《明细账》《账表核对》《银行调节》《核对结果》：表头冻结、自动筛选、元/分并列、金额格式；凭证页"附件"列列出附件编号；核对结果页列六类状态与差异数；说明页补一句"借贷核对为合成账套演示"。

## 5. 测试

1. 索引：含 `gl` 节；六类状态/备注/未执行项与 `task056_gl_01` 报告一致；凭证↔账务链接正确；无 `gl` 参数时旧行为不变。
2. 站点：六个 GL 页存在、每页可达（导航/面包屑）、`node --check` 全过；数字断言（16000/20000/4000/11000/20000=20000）；`gl-checks` 七项全 MATCHED；无外链/无 eval/fetch；语言红线零命中。
3. Excel：新增七页存在、自动筛选、数字断言；总表与索引一致。
4. 链接完整、确定性、只读；规模：200 张凭证 GL 夹具 → 站点/Excel 生成成功、链接全解析。
5. 证据：`task057_*` 命令/退出码/页面数/Excel 大小/断言输出。

## 6. 保护与停止

一次全树扫描，基线 = TASK-056 接受基线：相对基线**既有 changed 恰九件**；其余全新增并逐路径登记；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不改看板、不接 AI/终判。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；GL 为合成账套，页面/底稿只读展示证据与差异，不构成审计结论。
