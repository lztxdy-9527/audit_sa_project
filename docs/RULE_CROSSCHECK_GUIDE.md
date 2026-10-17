# 独立复算与一致性复核说明（TASK-007）

版本：TASK-007-crosscheck-1.2（TASK-007-R2 起）；日期：2026-10-11；执行端：DeepSeek；依据：`docs/tasks/TASK-007_DRAFT.md`、`docs/tasks/TASK-007-R1.md`、`docs/tasks/TASK-007-R2.md`、`docs/reviews/REVIEW_TASK_007.md`、`docs/reviews/REVIEW_TASK_007_R1.md`、`docs/reviews/REVIEW_TASK_006_R1.md`、`docs/SPEC_V1.md` 第 3—7 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 4—6 节、`docs/RULE_SCREEN_GUIDE.md`、`docs/NORMALIZATION_GUIDE.md`。

本文说明复核模块的**真实接口、输入前提、算法分开实现、逐项比较范围、差异代码、结果字段与限制**。

> 复核只回答“**计算与来源是否一致**”。两种实现一致只证明对该输入的计算一致，**不证明数据真实、业务合理，也不构成审计结论**；不生成 AI 候选结论、严重等级或人类判断预填值。

---

## 1. 公共接口

函数签名：

```python
def verify_rule_facts(normalized: dict, screening_report: dict) -> dict: ...
```

合法调用示例：

```python
from scripts.crosscheck_demo_rules import verify_rule_facts

report = verify_rule_facts(normalized, screening_report)
```

- 只接收两个**内存对象**，只返回报告；**不写文件、不修改传入对象**。
- 不读取数据库、Excel、答案册或历史复核结果；不执行 SQL、不调用筛查核心；不导入生成器或旧测试／QA 脚本；标准库仅用 `json`／`hashlib`。
- 复算来源是 `normalized.tables.*.records[*].data` 的原始标准化记录，**不从 `findings` 反推应有结果**，也不使用 `normalized.amount_reconciliation` 的汇总值作为计算答案。
- 对象指纹自行按固定 JSON 规范计算（`json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` → UTF-8 → SHA-256），**不导入装载器函数**；它是对象规范化指纹，不等于某个 `.json` 文件的字节哈希。
- 异常类型：
  - `CrossCheckBlocked`：前提、结构、来源绑定或支持范围不成立（说明字段／原因），不返回成功复核。
  - `CrossCheckError`：运行失败（保留阶段、原始原因与异常链）。金额全程整数分，**不转浮点、不用容差**。

### 1.1 输入前提

`normalized`：

- `normalization_version = TASK-004-normalized-1.1`、`mode = DEVELOPMENT_TEST_ONLY`、`next_step_allowed is False`；
- `quality_report.result = pass`，且 `quality_report.issue_counts_by_code` **必须存在、为对象且为空**（缺失、非对象或含问题计数都按前提不成立处理，不把“有未解决问题”当作无问题）；
- 四表 `records` 存在，每条的 `data`／`source`／`cells` 为对象，主键为非空原字符串且不重复；金额为 `int`（非 `bool`）；日期均为 `2026-09-01`—`2026-09-30`；`transaction_type`／`settlement_status` 在枚举内；`allocations.payment_id` 必须有对应资金事件。

`screening_report`：

- `batch_status = DEV_RULES_COMPUTED`、同样的 `mode`／`next_step_allowed = False`、`rule_core_version = TASK-006-rule-core-1.1`；
- `cutoff_date = 2026-09-30`、`period` 为 `2026-09-01`—`2026-09-30`；
- `load_source`：装载状态 `DEV_SQLITE_VERIFIED`、`store_version = TASK-005-sqlite-load-1.2`、`schema_version = demo-schema-1.0`；
- `normalized.source.input_sha256` ＝ `load_source.input_sha256` ＝ `load_source.run_metadata.input_sha256`；
- 本次计算的 `normalized` 对象指纹 ＝ `load_source.normalized_payload_sha256` ＝ `run_metadata.normalized_payload_sha256`；
- `database_sha256_before` ＝ `database_sha256_after` ＝ `load_source.database_sha256`、`database_unchanged is True`、`read_only = {"uri_mode": "ro", "query_only": 1}`；
- `rules` 中每条规则的 `rule_version`／`sql_sha256` **必须是本卡冻结值**（R01—R04 的 `TASK-006-R0x-1.0` 与四个固定哈希），不能把别的规则口径冒充本版结果。

> 这里只检查**报告内部声明与绑定**：本 API **不实际读取或重验数据库字节**，也不重建完整 ERP 质量 checker。实际文件哈希由测试驱动另行核对。前提不成立即阻断，**不补零、不静默删记录、不修复输入**以求一致。

## 2. 算法分开实现（纯 Python 整数循环）

以 `records[*].data` 为输入，用字典分组与整数循环推导：

- 仅 `SETTLED` 参与资金计算；PAY／REFUND 金额保持正数；退款按 `original_allocation_id` 汇总后抵减；非结算退款可展示但不抵减。
- **R01**：已知应付 + 收款对象分组；逐原付款计算其对应该应付的净分摊，净额精确等于应付金额的原付款**至少两笔**才命中，一组一条；`net_total` 只含该组符合条件的原付款。
- **R02**：已知应付、跨收款对象的净分摊合计**严格大于**应付金额，一张应付一条；整数分超额不设阈值。
- **R03**：`SETTLED PAY` 的原分摊关联为空或不在应付台账，一条原分摊一条；全退后仍保留原付款事实；区分 `EMPTY_AP_ID` 与 `AP_NOT_IN_LEDGER`。
- **R04**：`SETTLED PAY` 的原分摊可找到应付，且收款对象与应付供应商**按原字符串**不同；一条原分摊一条；全退后仍保留事实，不自动判错。
- 另从 `payments` 粒度独立求已结算 PAY／REFUND **主表总额**；从 `allocations` 粒度独立求付款／退款**分摊合计**与已知／空关联／台账外净额，确认主表与分摊相符且 `master_net = known + missing`。两种口径**不相加**。
- 结构化键使用元组／字典，保留前导零、空格与引号；不无转义拼接 ID；输出稳定排序。

## 3. 逐项比较范围

1. **命中键多重集**：漏报、多报、重复（先计数再比较，不先覆盖进字典）。
2. **结构化整数分金额**：R01 `payable_amount`／`net_per_payment`／`net_total`；R02 `paid_total`／`refund_total`／`net_total`／`overpayment`；R03／R04 `allocated_amount`／`paid_amount`／`refunded_amount`／`net_amount`（R04 另有 `payable_amount`）。`bool` 不等同于 `0/1`，比较保留类型差异。
3. **相关 ID**：相关应付、原付款、原分摊、退款；R03 的缺失种类，R04 的双方主体 ID。原付款集合**不混入退款**。
4. **退款摘要**：关联原付款／原分摊、退款 ID、金额、日期、状态与 `counted_in_net`。
5. **必需来源集合**：相关已知应付、原付款主表／分摊、**每条相关退款主表／分摊**；从**自己复算的相关记录**推导，**不把已输出的 `entities` 当应有集合**；检查遗漏、多余、重复，并逐实体比较 `workbook_sha256`／`sheet`／`excel_row`／完整 `cells` 与标准化记录精确一致；`source_rows` 同样比较；同一退款主表去重；非结算与净额为 0 的相关退款不能漏。
6. **计数与统计**：`rule_hit_counts`、`rules.*.hit_count`、R01 `qualifier_payment_count`、唯一原付款集合／数量／整笔已结算金额、R02 唯一应付超额合计、整体资金勾稽。

固定 `fact`／`verification_prompt` 文案不由复核器重新生成；本卡不做自然语言结论比对，也禁止输出候选等级、判断预填或 AI 建议。

### 3.1 严格类型比较（TASK-007-R1 起）

凡规格声明为**整数分**的字段，只允许 `int` 且非 `bool`：观察报告中的等值 `float`／`bool` 一律产生对应维度不一致，**不转换、不舍入、不用容差**。覆盖 `amounts_cents` 标量、R01 `net_per_payment` 各值、退款摘要金额、`statistics` 资金金额、`overall_reconciliation` 金额与明细；计数、原 Excel 行号与 `counted_in_net` 布尔标志按各自类型比较；声明为字符串的 ID 保持原类型与值，**不用 `map(str)`／`str(value)` 抹平类型差异**。每条差异记录 `expected_type`／`actual_type`。

### 3.2 多重性、规则身份与命中键类型

- **命中键的 ID 类型属于事实身份**（TASK-007-R2 起）：`rule_id` 与 R01 的 `ap_id`／`payee_supplier_id`、R02 的 `ap_id`、R03／R04 的 `allocation_id` 必须是非空**字符串**，保持原类型和值。身份键由「字段名 + 值类型 + `repr(值)`」构成，**不做 `str(value)` 归一化**——字符串 `"1"` 与整数 `1`（以及 `"True"`／`True`、`"None"`／`None`）是**不同身份**，不会合并为同一个键；用于显示或排序的字符串化只用于差异诊断配对，不承担身份归一化。合法字符串 ID（含 `"1"`、`"True"`、`"None"`、`"0001"`、含空格／单引号／竖线的值）不因外观被禁止或规范化。
- **退款摘要**：先核对元素结构与必需键，再按 `refund_allocation_id` 建立索引并检查**多重性**；重复出现报 `REFUND_FACT_DUPLICATE`（记录 ID 与实际次数），不静默覆盖、不过滤非法元素后假装列表完整。
- **规则身份**：`finding.rule_id`、`hit_key.rule_id` 与该复算事实的规则必须一致；仅改写外层 `rule_id` 时报 `RULE_ID_MISMATCH`（不重写其 `rule_id` 来消除冲突）。

### 3.3 差异代码（固定名称）

`MISSING_HIT`、`EXTRA_HIT`、`DUPLICATE_HIT`、`HIT_KEY_TYPE_MISMATCH`、`AMOUNT_MISMATCH`、`RELATED_IDS_MISMATCH`、`REFUND_FACT_MISMATCH`、`REFUND_FACT_DUPLICATE`、`RULE_ID_MISMATCH`、`SOURCE_ENTITY_MISSING`、`SOURCE_ENTITY_EXTRA`、`SOURCE_ENTITY_DUPLICATE`、`SOURCE_ROW_MISMATCH`、`SOURCE_VALUE_MISMATCH`、`STATISTIC_MISMATCH`、`RECONCILIATION_MISMATCH`、`COUNT_MISMATCH`。

`HIT_KEY_TYPE_MISMATCH` 记录命中键字段的**预期（字符串）值与原类型、实际值与实际类型**及字段路径（例如 `hit_key.ap_id`），同时因身份键不同而产生对应的 `MISSING_HIT`／`EXTRA_HIT`；`hit_keys` 维度为 `false`。

每条差异包含：

| 键 | 含义 |
| --- | --- |
| `code` | 上列固定代码 |
| `hit_key` | 受影响命中键；总体差异为 `null` |
| `field_path` | 可定位字段路径（含 `cells` 的逐叶路径） |
| `expected` / `expected_present` / `expected_type` | 复算（预期）值与**是否存在**及类型 |
| `actual` / `actual_present` / `actual_type` | 观察（实际）值与是否存在及类型 |

- **缺失使用 `*_present = false` 且类型为 `null`；显式 `null` 为 `actual = null` 且 `actual_present = true`；`0` 仍为 `0`**——删除字段与设为 `null` 得到可区分的记录。
- 完整 `cells` 不同时逐叶输出差异路径与实际预期／实际值（例如 `evidence.entities[allocations:AR01].cells.ap_id.raw_value`），**不再用提示语代替值**。
- 差异稳定排序、完整保存，不截断、不只保留第一条。

## 4. 结果字段

| 字段 | 内容 |
| --- | --- |
| `crosscheck_version` | `TASK-007-crosscheck-1.2` |
| `batch_status` / `matched` | 全部一致 → `DEV_CROSSCHECK_MATCHED`／`true`；存在差异 → `DEV_CROSSCHECK_MISMATCH`／`false` |
| `mode` / `next_step_allowed` | `DEVELOPMENT_TEST_ONLY` / `false`（两种结果都不构成正式放行） |
| `period` / `cutoff_date` | `2026-09-01`—`2026-09-30` / `2026-09-30` |
| `input_source_sha256` | 标准化来源工作簿哈希 |
| `normalized_payload_sha256` | 本次复算对象的规范 JSON 指纹 |
| `screening_report_sha256` | SQL 筛查报告按同一 JSON 规范求得的指纹 |
| `rule_core_version_checked` | 被复核报告的规则核心版本（`TASK-006-rule-core-1.1`） |
| `rule_recomputed_counts` | 各规则复算条数与 `total` |
| `recomputed_facts` | 复算 findings、`reconciliation` 与 `statistics`（**复算事实**） |
| `observed_summary` | SQL 报告命中的计数／超额合计／总体勾稽（**观察事实**） |
| `comparison` | `dimensions.<维度> = {executed, matched, difference_count}`、`difference_count`、`matched_dimensions`、`unmatched_dimensions` |
| `differences` | 差异列表（见 3.1） |
| `method` / `limits` | 方法与限制说明 |

复算事实来自 `normalized`，观察事实来自 SQL 报告，**不混成一份“已纠正结果”**；差异保留，**不自动回写 SQL 报告或修复数据库**。

**分项一致状态**：`comparison.dimensions` 固定十个维度——`hit_keys`、`amounts_cents`、`related_ids`、`refund_facts`、`rule_identity`、`source_entities`、`source_rows`、`counts`、`statistics`、`overall_reconciliation`；每项为 `{executed: true, matched: bool, difference_count: N}`，该维度存在差异时 `matched` 为 `false`。整体 `matched=true` **仅在全部维度一致且 `differences` 为空时**成立。不再使用含义模糊的 `comparison.checks`。

## 5. 真实测试命令

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_02'
```

- 测试容器必须是 `data\sqlite_tests` 内**尚不存在**的子目录；越界、指向该目录本身或已存在时在写入前退出 2。
- 每个输入：新副本 → 真实 checker CLI（独立 stdout／stderr）→ 冻结标准化 API → 冻结装载 API → 冻结 SQL 筛查 API → 独立复核 API；分别保存 `normalized.json`、`load_report.json`、`demo.sqlite`、`screening_report.json`、`crosscheck_report.json`。
- 本入口把**自身 stdout／stderr** 完整捕获到容器（`stdout.txt`／`stderr.txt`），并把每项检查的结构化详情直接写入 `crosscheck_results.json`、`mismatch_checks.json`、`precondition_checks.json`、`isolation_checks.json`、`command_log.json`、`summary.json`。
- 覆盖：主文件与 22 份 fixture（`data/generated/demo_20260930_a` 只读复制）、六个小样输入（从已验收容器 `data/sqlite_tests/task006_r1_gpt_20261011_072212/cases/S*` **只读复制 `input.xlsx`**，不使用其中旧报告作为答案）、**20 项**故意改错 SQL 报告的差异检查（含等值 `float` 金额、`bool` 统计、R01 `net_per_payment` 浮点、退款摘要重复、规则身份冲突、字段缺失与置 `null`、多维度同时改动）、**4 组命中键类型配对回归**（C04 上先做合法字符串改名的正向控制，再只改一个 `hit_key` 字段的类型：`"1"`→`1`、`"True"`→`true`、`"None"`→`null`、`"1"`→`1`）、**6 项**前提阻断检查（含质量结果 `pass` 但问题计数非空，测试侧同步两处指纹以隔离质量前提）、确定性与隔离检查。
- 命中键配对回归保存每组正向／负向输入、完整返回值、单点变更路径、预期与实际类型，写入 `hit_key_checks.json` 与 `mutations\K0*`；每个被改错的对象与其**完整复核报告**另存于 `mutations\<name>.json`／`mutations\<name>.report.json`；`mismatch_checks.json` 保存完整差异（不截断）与各维度状态。
- 全部有效输入的初次结果保存完成后，测试侧才读取答案册做额外已知案例验证（主文件 12 键、R02 合计 1 600 000 分、14 个有效 fixture 登记键）。
- 退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。工作簿输入、checker CLI、SQL 核心调用、复核调用、初次一致、上游阻断、预期不一致、前提阻断、复调用／隔离检查、意外运行错误与测试失败分别统计；预期负向结果不当作测试失败。

## 6. 限制（明确不主张的内容）

- **不证明数据库实读**：本层只检查报告内部声明与绑定，不读取或重验数据库字节。
- **不证明来源真实性**：只核对该输入下标准化记录与报告证据是否一致；不抵御同权限篡改。
- **不构成审计结论**：一致或不一致都不判断舞弊、损失、控制缺陷或是否调整账目；不设重要性阈值。
- **不替代人类判断**：两种实现一致也不能替代其后的人类独立初步判断与最终判断。
- 不修复输入、不回写报告、不自动纠正差异；不开展压测、真实 ERP 接入、OCR、RAG 或 UI。
- 本模块是 `DEVELOPMENT_TEST_ONLY`：未接入正式批次，不建立契约或批准控制，不改变 Gate 状态。
