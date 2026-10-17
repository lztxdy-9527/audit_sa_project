# TASK-007：Python 独立复算与 SQL 事实一致性复核

执行端：DeepSeek。架构及验收：GPT。主理人负责转交。本卡授权独立复算模块的开发验证；不是正式批次放行。

项目：`D:\harness work\audit_sa_project`。

## 1. 先读与当前状态

依次读本卡、`docs/reviews/REVIEW_TASK_006_R1.md`、`docs/SPEC_V1.md` 第 3—7 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 4—6 节、`docs/RULE_SCREEN_GUIDE.md`、`docs/NORMALIZATION_GUIDE.md`。

任务六 R1 已由 GPT 实测验收：29 输入、21 规则成功、8 上游阻断；独立 QA 对 34 条线索、168 个来源实体核对，金额/关联/来源差异均为 0。退款来源缺失及非法 JSON 五项回归通过。核心版本 `TASK-006-rule-core-1.1`，四份规则 SQL 未变。上游模块均已冻结，不再修改。

GPT 本轮仅新增验收文档、任务卡和 QA 证据，没有替你编写任务七的实现。不要把 GPT 的 QA 脚本导入生产模块或直接包装成新模块。

本任务补上业务链中的“复核”：使用标准化记录，经另一套 Python 整数计算，与既有 SQL 筛查事实逐项比较。独立指实现路径分开，不是独立多智能体审计保证，也不是复算一致即可判断采购或付款合理。

## 2. 具体实务场景和目标

审计助理已经获得 SQL 筛查报告。在交给人类判断前，程序需要发现：某条缺失关联线索被漏掉、超额金额多算 1 分、退款状态展示错误、退款来源被省略等可验证差异。

本卡只解决“计算与来源是否一致”，不判断舞弊、损失、缺陷等级或是否应调整账目。完成后仍停在开发态。事实底稿展示、正式契约、Gate 控制、人类判断保存和后置 AI 建议均另行下卡。

## 3. 只新增四份文件及测试容器

- `scripts/crosscheck_demo_rules.py`：仅 Python API 的独立复算核心。
- `tests/test_crosscheck_demo_rules.py`：开发验证入口。
- `docs/RULE_CROSSCHECK_GUIDE.md`：真实接口、复算与差异口径、测试及限制。
- `docs/EXEC_REPORT_007.md`：执行回执。
- `data/sqlite_tests` 内全新测试容器，保存本任务新输入副本与产物。

其他既有文件全部保持原字节。不要修改任何上游代码、SQL、说明、回执、任务卡、验收单、答案册或历史容器；不要修改 GPT 验收目录。不要初始化 Git、安装依赖、建立 CLI 批准命令、接入 data/batches 或改变 batch_manifest。

使用现有 Python 3.11 虚拟环境；独立核心只需标准库，不需要 sqlite3 查询或 openpyxl。测试驱动可复用冻结的标准化/装载/筛查 API，并使用现有 openpyxl；不得修改其源码。

## 4. 独立 API 与输入前提

固定接口：

```python
def verify_rule_facts(normalized: dict, screening_report: dict) -> dict: ...
```

函数只接收两个内存对象，只返回报告，不写文件，不修改传入对象，不读取数据库、Excel、答案册或历史复核结果，不执行 SQL、不调用筛查核心、不导入生成器或旧测试/QA 脚本。调用方负责保存新报告。可以用标准库 json/hashlib 计算对象指纹。

输入前提至少核对：

- normalized：`normalization_version=TASK-004-normalized-1.1`、`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed is False`；quality_report 为 pass、无质量问题，四表记录及消费字段/来源完整、金额为 int 且非 bool，必需 ID 为原字符串；实际业务日期均在 2026-09-01 至 2026-09-30。
- screening_report：`batch_status=DEV_RULES_COMPUTED`、同样的 mode/next_step_allowed、`rule_core_version=TASK-006-rule-core-1.1`；截至日固定 2026-09-30、期间匹配；本层消费的 findings、counts、statistics、reconciliation、source 等字段结构可用。
- `normalized.source.input_sha256` 等于 `screening_report.load_source.input_sha256` 及其 run_metadata 对应值。
- 对完整 normalized 使用 `json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`，UTF-8 后求 SHA-256，与 screening_report.load_source 及其 run_metadata 的 normalized_payload_sha256 相等。自己实现此序列化，不导入装载器函数。对象指纹不等于 normalized.json 文件字节哈希。
- screening_report 数据库 before/after 哈希、load_source.database_sha256 相等，database_unchanged 为 True，read_only 为 `{uri_mode:ro, query_only:1}`；load_source 的装载状态/版本与上游冻结接口一致。这里只检查报告内部声明及绑定，不能声称本 API 实际读取或重验数据库字节。
- 消费的规则版本/SQL 哈希必须是本卡冻结版本，不能将别的规则口径冒充本版结果。实际文件哈希由测试驱动另行核对。

`CrossCheckBlocked`：前提、结构、来源绑定或支持范围不成立；说明字段/原因，不返回成功复核。`CrossCheckError`：运行失败，保留阶段、原始原因及异常链。金额计算不得转浮点或用容差。

有效输入中的“复算不一致”是有意义的复核结果，不当作普通运行异常丢掉。返回 `batch_status=DEV_CROSSCHECK_MISMATCH`、`matched=false` 及差异；全部一致才返回 `DEV_CROSSCHECK_MATCHED`、`matched=true`。两种结果均 mode=DEVELOPMENT_TEST_ONLY、next_step_allowed=false，不构成正式放行。

消费前提的核对不是重建完整 ERP 数据质量 checker。若上游结果或结构不成立，明确阻断；不补零、静默删记录或修复输入来获得一致。

## 5. 计算和逐项比较

### 5.1 从原始标准化记录独立复算

以 `normalized.tables.*.records[*].data` 为计算输入，用字典/分组/整数循环推导事实。不能从 screening_report.findings 反推“应有结果”，不能复用 SQL 输出的中间值或 normalized.amount_reconciliation 的汇总值作为计算答案。

- 仅 SETTLED 参与资金计算，PAY/REFUND 金额保持正数；退款按 original_allocation_id 汇总后抵减。非结算退款可以展示但不抵减。
- R01：已知应付 + 收款对象分组；逐原付款计算该应付的净分摊，等于应付金额的原付款至少两笔才命中，一组一条。net_total 只含该组符合条件的原付款。
- R02：已知应付的所有对象付款净分摊合计严格大于应付金额，一张应付一条；整数分超额不设阈值。
- R03：SETTLED PAY 的原分摊关联为空或不在应付台账，一条原分摊一条；全退后仍保留原付款事实。分别标明空关联/台账外标识，不说“没有发票”。
- R04：SETTLED PAY 原分摊可找到应付，收款对象与应付供应商原字符串不同；一条原分摊一条，全退后仍保留事实，不自动判错。
- 结构化键使用元组/字典，保留前导零、空格和引号；不能无转义拼接 ID。输出稳定排序。

另从 payments 粒度独立求 settled PAY/REFUND 主表总额；从 allocations 粒度独立求付款/退款分摊和已知应付/空关联/台账外净额，确认主表与分摊及 `master_net=known+missing`。这些是两套口径的比较，不能相加。

### 5.2 比较范围必须超出条数

逐项比较并保存差异：

1. 命中键集合、漏报、多报、重复；不要先覆盖进字典而漏掉重复。
2. 每条规则所有结构化整数分金额，含 R01 net_per_payment、R02 paid/refund/net/overpayment、R03/R04 原分摊/退款/净额。bool 不等同于 0/1，比较须保留类型差异。
3. 相关应付、原付款、原分摊、退款 ID；R03 缺失种类，R04 双方主体 ID。原付款集合不混入退款。
4. 所有相关退款摘要：关联原付款/分摊、退款 ID、金额、日期、状态和 counted_in_net。
5. 必需来源集合：相关已知应付、原付款主表/分摊、每条相关退款主表/分摊。从自己复算的相关记录推导，不能把已输出的 entities 当应有集合。检查遗漏、多余、重复；逐实体比较 workbook_sha256、sheet、excel_row、完整 cells，与 normalized 对应记录精确一致；source_rows 同样比较。同一退款主表去重；非结算和净额 0 的相关退款不能漏。
6. rule_hit_counts、rules 内的各规则 hit_count、R01 qualifier_payment_count、唯一原付款集合/数量/整笔已结算金额、R02 唯一应付超额合计、整体资金勾稽。

固定 fact/verification_prompt 文案不由复核器重新生成 AI 解释；本卡不做自然语言审计结论比对。禁止输出候选等级、判断预填或 AI 建议。

### 5.3 复核报告

报告至少包含：版本 `TASK-007-crosscheck-1.0`、开发态状态、matched、期间/截至日、输入来源哈希、normalized 对象指纹、screening_report 完整对象按相同 JSON 规范求得的指纹、方法/限制、各规则复算数量、复算事实与勾稽、逐项比较结果和 differences。

每条差异至少有 `code, hit_key（总体差异可为 null）, field_path, expected, actual`。区分缺失、null、0；不要只返回“金额不对”或只留第一条。可使用 MISSING_HIT / EXTRA_HIT / DUPLICATE_HIT / AMOUNT_MISMATCH / RELATED_IDS_MISMATCH / REFUND_FACT_MISMATCH / SOURCE_ENTITY_MISSING / SOURCE_ENTITY_EXTRA / SOURCE_ENTITY_DUPLICATE / SOURCE_ROW_MISMATCH / SOURCE_VALUE_MISMATCH / STATISTIC_MISMATCH / RECONCILIATION_MISMATCH / COUNT_MISMATCH 等明确代码，名称在说明中固定。

复算事实来自 normalized；观察事实来自 SQL 报告，不能把两者混成一份“已纠正结果”。差异保留，不能自动回写 SQL 报告或修复库。完整一致也仅证明两种实现对此输入一致，不能证明数据真实、业务合理或审计结论正确。

## 6. 开发验证

入口 `tests/test_crosscheck_demo_rules.py --out-dir <全新容器>`：仅接受 data/sqlite_tests 内不存在的目录，拒绝覆盖历史/越界。捕获本入口完整 stdout/stderr，保存 command_log.json 和 summary.json，成功与失败检查详情直接写结构化文件，不能只留局部数组或控制台打印。

### 6.1 原有 29 个工作簿输入

主文件和 22 fixture 从 `data/generated/demo_20260930_a` 只读复制；六个小样输入从已验收的下列容器对应 cases/S* 目录只读复制 input.xlsx：

`data/sqlite_tests/task006_r1_gpt_20261011_072212/cases`

这是复用已验收输入，不是读取 GPT 复核答案。不得将旧 screening_report 或 independent_review.json 当复算答案。

每个新工作簿副本经真实 checker CLI（独立 stdout/stderr 和命令）→冻结标准化 API→装载 API→SQL 筛查 API→新复核 API，分别保存新 normalized.json、load_report.json、demo.sqlite、screening_report.json、crosscheck_report.json。

预期：21 个有效输入得到 MATCHED；8 个质量阻断仍保存真实 checker 证据，登记 SQL/复核“未执行/上游阻断”，不调用复核器、不记为匹配且零命中。保留 R1 的 34 条线索与完整 168 个实体范围，尤其退款 7 条线索的 22 个实体出现项。

所有有效输入的 SQL 与独立复核初次结果都保存后，测试侧才读取答案册作额外已知案例验证：主文件仍 12 键、R02 合计 1600000 分；14 个有效 fixture 比较登记键/金额，8 个质量阻断比较原质量预期。主文件/fixture 以外六个样本预期仍按 TASK-006_DRAFT，不从当前输出反推答案。核心永不读取答案。

### 6.2 故意改错 SQL 报告，确认复核器能发现

仅深拷贝本次新计算的报告对象，每次单独改一处，保留 normalized 和其来源绑定。原报告文件/数据库不变，保存被改对象、新复核报告和期望代码。下列均须 MISMATCH，差异指到受影响键/字段，不能 MATCHED：

1. 主文件删一条 R03：漏报。
2. 复制一条 R02 改为不存在的应付键：多报。
3. 原样追加已有 finding：重复，不能字典覆盖后通过。
4. 一个 R02 overpayment 增加 1 分：金额不同。
5. R02 超额合计统计增加 1 分：统计不同。
6. C09b 保留退款摘要，删除对应退款主表证据实体：来源遗漏。
7. 一个证据实体的 cells.raw_value 改动，其他不变：完整来源值不同。
8. C09b 已结算退款 counted_in_net 改 false：退款事实不同。
9. 一个 R04 的 related_ids.payee_supplier_id 改为应付供应商：关联主体不同。
10. 主文件整体 missing_payable_link_net 增加 1 分：总体勾稽不同。
11. 仅改一个 source_rows 原 Excel 行号：行号不同。

改动不应改变报告的身份前提字段；须测到对应差异比较，不能让身份不符提前阻断然后称为差异测试通过。派生数量/统计随删增线索出现更多差异是合理的，至少必须捕获指定根本差异，不要求只报一条。

### 6.3 前提阻断、确定性与隔离

单独验证：输入源哈希不匹配；normalized 内容改动导致对象指纹不匹配；mode 非开发态；不支持截至日；normalized 的 quality_report 非 pass。均为 CrossCheckBlocked，不返回 MATCHED 或 MISMATCH 报告。保存字段/原因。

对同一合法输入复调用两次，完整返回对象精确相等；两个输入对象调用前后按规范 JSON 指纹不变。检查测试数据库前后字节不变。

检查独立核心静态导入和运行期依赖：不导入 sqlite3、筛查/装载计算函数、生成器、测试/QA 脚本；运行期禁止读取规则 SQL、evaluation、旧检测/复核答案且无此读取尝试。守卫须以受控探测确认实际生效，但探测读取不算核心读取；恢复所有内存替换。测试驱动为上游筛查读取 SQL 和为最终验证读取答案允许，守卫范围须明确区分。

## 7. 计数、冻结与回执

按真实执行分别统计工作簿输入、checker CLI、SQL 核心调用、独立复核调用、初次 MATCHED、上游阻断、预期 MISMATCH、前提阻断、复调用/隔离检查、意外运行错误及测试失败。预计负向结果不当作测试失败，也不伪装成功。保存每项负向和比较的结构化详情，入口退出 0 才表示所有断言符合预期；失败返回非零并保留现场。

核对冻结核心：screen `1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe`；规则 SQL 版本均为 TASK-006-R0x-1.0，哈希：

- R01 `7a19ff2faba088f0b498d9c5004f0a865aac4d59b6f8ed699869051ecbe5e882`
- R02 `58af03e634008fcc61426e15a7433b6370cae0180c0436136de226b8d87b08b3`
- R03 `8a4b84d9ba0ed201ea89a6d58ea5ea67deec9ab8dbe8908e246c79c76876525a`
- R04 `b60e4db078e6632c653adb4ec20f1280c7ef58c70d4496f7caa6cb5cf567ec2d`

扩充保护基线为 `data/reviews/task006_r1_20261011_072212/source_hashes_after.json`，本卡不允许其中任何旧文件改变或缺失。无需重跑任务二至六整套测试；新链路实际调用冻结 API，另核对冻结文件及历史保护。

RULE_CROSSCHECK_GUIDE 写清接口、所有输入前提、算法分开实现、差异代码、实际结果字段和“不证明数据库实读/来源真实性/审计结论”的限制。EXEC_REPORT_007 写完整新文件哈希、真实命令/退出码、逐项检查和分类计数、保护比较、失败尝试及未执行内容。不能把代码存在当运行通过。

若遇到规格/答案矛盾，记录双方原文、实际输入及差异，停止受影响部分；不修改冻结口径来消除差异。不要为展示能力制造大量无意义错误，不开展压测、真实 ERP 接入、OCR、RAG 或 UI。

## 8. 停止点

完成四份新文件和验证后，返回 EXEC_REPORT_007.md、RULE_CROSSCHECK_GUIDE.md、新测试容器路径，立即停止等 GPT 验收。

不推进任务八，不接正式批次、不批准 Gate、不创建正式契约、判断表或 AI 建议。主理人本轮只转交本卡及验收单，不需要手工检测或模拟批准。两种计算实现一致也不能替代其后的人类独立初步判断和最终判断。
