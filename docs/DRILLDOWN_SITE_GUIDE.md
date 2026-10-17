# 证据链下钻 HTML 指南（多页跳转版 + 单页比对版 + 全量清单/筛选）

标识：`TASK-049-drilldown-site-1.1`。实现：`scripts/build_drilldown_site.py`（仅标准库）。
输入：TASK-048 索引 v1.1；输出：多页跳转版 + 单页比对版 + 全量清单（内嵌筛选脚本，限用途）。

## 1. 用法

```powershell
.venv\Scripts\python.exe -B scripts\build_drilldown_site.py `
  --index data\runtime_initial_judgment_recording_tests\task051_index_01\trace_index.json `
  --out-dir data\runtime_initial_judgment_recording_tests\task051_site_01
```

`--out-dir` 必须从未存在、位于测试根下、以 `task049_` 或 `task051_` 开头。
退出码：`0` 成功；`1` 索引不完整/引用不闭合（字段精确）；`2` 参数/路径错误。

## 2. 页面结构

- 问题清单 `index.html` / `index-<n>.html`（50 条/页，筛选栏，金额/事项可点，逐格比对链接）。
- 事项页 `case-<id>.html`、比对页 `compare-<id>.html`。
- 账务行 `ledger-<type>-<id>.html`（含状态与来源）、凭证 `voucher-<id>.html`（含状态）、
  原始表行 `source-<sheet>-<row>.html`（含状态）。
- **全量清单**：`all-ledger.html`、`all-vouchers.html`、`all-source.html`（50 行/页，状态列）。
- 资料接收记录 `records.html`。
- 每页：边界横幅、面包屑、返回上一层；列表页含筛选栏与打印提示。

## 3. 筛选（内嵌脚本，限用途）

- 状态下拉：全部 / 仅异常 / 仅合规 / 待审阅；关键词输入。
- 实现：脚本只切换 `body` 与行的筛选 class，由 CSS 控制显示；**不修改数据、不请求网络、
  不使用 `fetch`/`XMLHttpRequest`/`eval`/`WebSocket`/外部资源**；所有行预先渲染；
  禁用脚本时默认显示全部。
- 打印：`@media print` 强制显示全部行并隐藏筛选栏，页脚注明"打印为全量视图，筛选仅屏幕生效"。

## 4. 安全/确定性/语言

- 无外链、无图片、无外部字体；全部相对链接；动态文本 HTML 转义。
- 可见文本只用审计语言；禁止 `JSON/hash/SHA/API/script/pipeline/解析/字段类型/字节/编码/版本号`
  （脚本与样式块不计入可见文本）。
- 确定性：同一索引两次生成同名页面字节相同；只读索引。

## 5. 测试与证据

`.venv\Scripts\python.exe -B tests\test_drilldown_site.py --out-dir data\runtime_initial_judgment_recording_tests\task051_run_04`

- 全量计数（台账 7 / 凭证 8 / 原表行 9）、筛选栏与打印规则、脚本守卫（无 fetch/XHR/eval/WebSocket/外链）、
  链接零断裂、语言红线、P02 缺证红色/未取得、确定性、200 条规模（页面数/大小/耗时登记）、只读。

## 6. 边界

不接入演示；不实现审阅表单（TASK-052）；页面只读展示既有合成证据，不证明凭证/流水真实，
不构成审计结论；核对结论由审计人员填写。

## 7. 审阅表单与导出（TASK-052）

- 每条事项页与全量清单行旁提供审阅表单：审阅状态（待审阅/已审阅-相符/已审阅-不符/需补充资料）、
  审计问题描述、建议处理、审阅人、审阅日期。
- 草稿仅保存在本浏览器 `localStorage`（键含资料版本短标识 + 记录类型 + 记录 ID），页面标注
  "草稿仅保存在本浏览器，导出并合并后才成为审阅记录"。
- 导出按钮生成 `审阅记录.json` / `审阅记录.csv` 下载；不写文件、不发网络请求；
  无 `fetch`/`XMLHttpRequest`/`eval`/`WebSocket`。
- 合并后页面显示徽标（绿/红/黄/灰）并展示问题与建议；筛选增加"审阅状态"。
- 打印仍为全量视图。

## 8. 脚本正确性与交互自检（TASK-053 缺陷修复）

- **脚本语法**：CSV 拼接在生成文件中为 `lines.join('\n')`（反斜杠+n，不是真实换行）；
  全站每个 `<script>` 必须通过 `node --check`（测试逐页提取脚本执行）。
- **状态筛选**：`全部 / 仅异常 / 仅合规 / 未涉及`；行带 `abnormal / ok / neutral` 之一
  （异常=红/黄，未涉及=neutral）；已移除与审阅下拉重复的"待审阅"。
- **审阅状态筛选**：`全部 / 待审阅 / 已审阅-相符 / 已审阅-不符 / 需补充资料`，按 `rv-*` 类过滤。
- **关键词筛选**：输入非空时 body 加 `filter-keyword`，仅保留命中行（`match` 类）。
- **全站覆盖**：含筛选栏的页面必须有脚本；含审阅表单的页面必须有"导出审阅记录"按钮；
  `compare-*.html` 不含筛选栏也不含死控件。
- **导出**：JSON 含 `review_version`、`source_version`（取 body `data-review-version`，非空）、
  每条记录完整字段；CSV 数据行引号正确；不联网。
- **测试**：`tests/test_drilldown_site.py` 增加逐页 `node --check` 与 Node 伪 DOM 冒烟
  （状态下拉/关键词/审阅下拉/点击导出，断言行显隐与导出 JSON/CSV）；证据保存于
  `data/runtime_initial_judgment_recording_tests/task053_evidence_01/`（node_check.json、smoke.json）。

修复前可用的替代路径：Excel《审阅记录.xlsx》与《证据链底稿.xlsx》自动筛选；合并命令不受影响。

## 9. 口径命名、业务链条与勾稽底稿（TASK-054）

- **列名**：`机器核对结果（程序）`（原“状态”）、`人工审阅状态`（原“审阅”）、
  `人工审阅录入`（原“填写审阅”）；每张表上方有一行图例，默认待审阅，**程序不会替人写“已审阅”**。
- **口径**：`未涉及` 统一改为 `未纳入逐项核对（仅金额勾稽）`——分摊行是付款与应付之间的核销桥梁，
  当前账证/账实逐项核对不单独覆盖它，只用它做金额勾稽；不是“没问题”也不是“有问题”。
- **指引起页** `guide.html`：业务链条（供应商 → 应付单 → 发票/合同/入库单 → 付款 → 分摊 → 退款 →
  银行流水）、对账路径表、三步走、未纳入逐项核对解释、缺口声明；全站每页顶部有“口径与对账指引”链接。
- **业务勾稽底稿** `business-<AP>.html`（管理口径，不是会计分录）：按应付单分组列示应付、关联凭证、
  付款与退款、分摊（核销）、三栏式勾稽、按供应商明细表（含借方余额提示）、凭证抽查表与缺口声明；
  页内固定声明“本页为管理口径的业务勾稽，不是会计分录；借贷方向仅用于说明余额方向，未做试算平衡。”
- **缺口**：本样本没有记账凭证借贷分录、总账/明细账、科目余额表，因此**不做**试算平衡、账账/账表核对；
  需新增输入后另卡实施。全量清单保留并与勾稽底稿互相链接。

测试：`tests/test_drilldown_site.py` 增加列名/图例/guide/勾稽底稿数字与声明检查；证据保存于
`data/runtime_initial_judgment_recording_tests/task054_evidence_01/`。

## 10. 借贷核对页（TASK-057，索引含 `gl` 时）

站点新增六页：`gl-trial-balance.html`（科目余额表，期初/本期/期末借贷分列，应付 4,000 借方高亮）、
`gl-journal.html`（记账凭证分录，附件与业务单据链接）、`gl-ledger.html`（总账与明细账，逐笔余额滚动）、
`gl-report.html`（账表核对，应付 0 / 预付 4,000 重分类，资产 20,000 = 负债+权益）、
`gl-bank.html`（银行余额调节表，期初 20,000 + 收入 1,000 − 支出 10,000 = 期末 11,000，未达 0）、
`gl-checks.html`（六类 + 附件核对结果、备注、未执行项）。

- 全站每页导航含“借贷核对”入口；`business-AP01.html` 增加“查看记账凭证/借贷核对”链接。
- 数字全部取自索引 `gl` 节，不重算；纯审计语言；无外链/无 `eval`/`fetch`/`XHR`。
- 索引无 `gl` 节时（旧输入）不生成这些页，旧站点行为不变。
