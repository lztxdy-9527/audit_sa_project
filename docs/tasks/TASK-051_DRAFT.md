# TASK-051：全量清单、筛选（内嵌脚本限用途）、Excel 自动筛选、源漂移与备份纪律

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-050 ACCEPTED**（基线 179749 项 / `4f895b86…`）。依据 `docs/decisions/DECISION_20261017_DSH_UI_V3_FULL_FILTER_REVIEW.md`（`DSH-SCOPE-20261017-05`）：**允许内嵌脚本，仅用于筛选**；全量清单；源漂移拒绝；不按操作复制源。

## 1. 允许修改/新增

**允许修改（changed 恰这九件）**：`scripts/build_trace_index.py`、`scripts/build_drilldown_site.py`、`scripts/build_excel_workbook.py`、`tests/test_trace_index.py`、`tests/test_drilldown_site.py`、`tests/test_excel_workbook.py`、`docs/EVIDENCE_CHAIN_INDEX_GUIDE.md`、`docs/DRILLDOWN_SITE_GUIDE.md`、`docs/EVIDENCE_CHAIN_WORKBOOK_GUIDE.md`。
**允许新增**：`docs/EXEC_REPORT_051.md`、证据根 `data/runtime_initial_judgment_recording_tests/task051_*/`。
**禁止**：改适配器、演示脚本、契约/账证/账实核对器、输入根、既有卡/评审/证据、看板；不得修改 TASK-047 摘要生成器。

## 2. 索引（trace_index v1.1）

- `ledger[]` 改为**全量**：payables / payments / allocations 全部行；每条 `status` ∈ `已核对一致 / 存在差异 / 未取得 / 未涉及`，由账证/账实报告逐项推导（不得重算金额）。
- `vouchers[]` **全量**（v1.1 为 8 张）；`source_rows[]` **全量原表行**（四张表全部数据行）；`cases[]` 保持。
- 新增 `source_identity`：源工作簿相对路径、长度、SHA-256（取自批次接收身份），以及 `source_drift` 结果。
- 新增 `review` 占位字段（状态固定 `待审阅`、问题/建议/审阅人/日期为 null），供 TASK-052 合并；本卡不采集审阅。
- 生成前校验源工作簿哈希：与批次接收身份不一致 → **exit 1、`source_drift`**，拒绝生成（不得用旧索引冒充新数据）。

## 3. HTML（双形态 + 全量清单 + 筛选）

- 新增全量页：`all-ledger.html`、`all-vouchers.html`、`all-source.html`（分页 50 行/页），每条带**状态列**；事项页/台账页/凭证页/原始行页保持并补充状态与全量引用。
- **筛选（内嵌脚本，限用途）**：状态下拉 `全部 / 仅异常 / 仅合规 / 待审阅` + 关键词输入；实现方式为给 `body` 加筛选 class、由 CSS 控制行显示，**不修改数据、不请求网络、不使用 `eval`/`fetch`/`XMLHttpRequest`/外部资源**。所有行必须**预先渲染**在 HTML 中；禁用脚本时默认显示全部。
- **打印**：`@media print` 强制显示全部行并隐藏筛选栏，页脚注明"打印为全量视图，筛选仅屏幕生效"。
- 余下规则沿 TASK-049：相对链接、面包屑、红黄绿、图像占位、纯审计语言、无外链、转义、确定性。

## 4. Excel（全量 + 自动筛选）

- 《台账明细》《凭证》《原始表行》改为全量；每条带状态列；`auto_filter` 覆盖表头数据区；冻结表头、列宽、A4 横向、元/分并列、超链接规则不变（链接数量随全量增长，须逐条校验可解析）。
- 说明页补一条备份纪律：源文件只在接收时留存一份，生成不复制源；每次生成只新增小文件。

## 5. 备份与版本纪律（写进指南并在证据中说明）

- 源文件：接收时一次（`data/batches/<批次>/source/`），之后只读；生成只记录哈希。
- 阶段证据：Gate 决定、初判、审阅记录（TASK-052）各自小文件留存。
- 生成产物：每轮新目录，不覆盖；样本每轮约 0.1–1.5 MB；不按"每次点击"复制源。
- 里程碑（验收/交付）可压缩归档到外部盘；项目内不删除旧证据。

## 6. 测试与证据

1. 全量计数：台账行、凭证 8、原表行 9（四表数据行合计，按实际输入核对）、事项数；状态分布正确。
2. 筛选守卫：HTML 含内嵌脚本但不含 `fetch`/`XMLHttpRequest`/`eval`/`WebSocket`/外链；脚本关闭视角下所有行仍在 HTML 中（按原始 HTML 文本解析计数）。
3. 打印覆盖：`@media print` 规则存在且强制显示全部行。
4. Excel：`auto_filter` 存在且范围覆盖全量；超链接全部可解析；全量行数与索引一致。
5. 源漂移：复制批次源并改 1 字节 → 索引生成 exit 1、`source_drift`，原文件不变。
6. 规模：200 条事项索引 → 全量页面/工作簿生成成功，链接全解析，登记耗时与大小。
7. 确定性、只读、转义、语言红线沿用；负例（悬空引用）仍 exit 1。

## 7. 保护与停止

一次全树扫描，基线 = TASK-050 接受基线：相对基线**既有 changed 恰 §1 九件**；其余全新增并逐路径登记；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不实现审阅表单（TASK-052）、不改演示、不改看板。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；页面/底稿只读展示既有合成证据，不构成审计结论。
