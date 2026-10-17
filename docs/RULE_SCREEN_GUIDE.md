# 只读 SQL 规则说明（TASK-006）

版本：TASK-006-rule-core-1.1（TASK-006-R1 起）；日期：2026-10-11；执行端：DeepSeek；依据：`docs/tasks/TASK-006_DRAFT.md`、`docs/tasks/TASK-006-R1.md`、`docs/reviews/REVIEW_TASK_006.md`、`docs/reviews/REVIEW_TASK_005_R2.md`、`docs/SPEC_V1.md` 第 1、3—6 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 3—5 节、`docs/SQLITE_LOAD_GUIDE.md`。

本文说明开发态只读规则核心的**公共 API、结果字段、SQL 计算粒度、退款与历史事实处理、命中键、来源与证据、验证分离方式**，以及**开发态边界**。

> 规则输出是**待核实线索**，不能直接认定舞弊、损失、控制缺陷或审计调整，也不代替审计人员的职业判断。
> 本模块是 `DEVELOPMENT_TEST_ONLY`，未接入正式业务流程，不改变任何批次或 Gate 状态，也不生成 AI 判断。

---

## 1. 公共 API

函数签名：

```python
def screen_sqlite(database_path, load_report: dict, *, cutoff_date: str = "2026-09-30") -> dict: ...
```

合法调用示例：

```python
from scripts.screen_demo_sqlite import screen_sqlite

report = screen_sqlite(database_path, load_report)
```

- 只消费**数据库**与**匹配的装载报告**；不接收答案册、场景标签或期望命中数，不导入生成器，不写任何文件（由调用方保存本次新报告）。
- 读取方式：以 SQLite URI `mode=ro` 打开（**不提供可创建连接的普通回退**），再启用并**实测** `PRAGMA query_only = ON`；只用固定 `SELECT`／CTE，不建临时表或视图，不执行 DDL／DML／`executescript`，不更新元数据；查询前后核对数据库字节哈希相等并记录。
- 只有前提、规则、证据读取、核对、严格关闭与只读保护**全部成功**才返回 `batch_status = DEV_RULES_COMPUTED`、`mode = DEVELOPMENT_TEST_ONLY`、`next_step_allowed = false`。
- 异常类型：
  - `RuleScreenBlocked`：前提／范围不成立——报告的开发态标识或版本不符、装载版本／schema 版本不符、报告路径或字节哈希与数据库不匹配、数据库缺失／越界／为未发布 `.staging`、截至日不支持、数据库 `run_metadata` 与报告不一致、业务日期超出本版范围。**不执行规则、不返回成功报告。**
  - `RuleScreenError`：文件、SQL、核对或来源读取等运行失败——含汇总溢出、来源缺项、非法 `cells` JSON、只读保护失败、正常关闭失败。保留阶段、路径与原始原因（异常链）。

### 1.1 前提核对顺序

1. 截至日必须为本版唯一支持值 `2026-09-30`（其他值明确阻断，不静默改用其他日期）。
2. 路径解析后必须是 `data/sqlite_tests` 内**已存在的最终数据库文件**；拒绝目录、缺失文件、越界路径与 `.staging`（缺失文件不会被 `sqlite3` 自动创建）。
3. 计算数据库实际字节哈希，并核对装载报告：`batch_status=DEV_SQLITE_VERIFIED`、`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed` 实际为 `False`、`store_version=TASK-005-sqlite-load-1.2`、`schema_version=demo-schema-1.0`、`database_path` 与实际输入一致、`database_sha256` 等于实际字节哈希。
4. 核对当前**冻结装载器／schema 文件哈希**与本版冻结值相符。
5. 从数据库**实际读取** `run_metadata`，核对开发态标识、装载／schema 版本、输入哈希、对象规范化指纹与装载报告相等，装载器／schema 哈希与当前冻结文件相等——不只信报告里的“成功”字符串。
6. 日期范围仍为 `2026-09-01` 至 `2026-09-30`（含当日）：若数据库存在范围外业务日期，**报告范围不符**，不以 `WHERE` 静默过滤后出完整结果。

## 2. 结果字段

成功报告包含：

| 字段 | 内容 |
| --- | --- |
| `batch_status` / `mode` / `next_step_allowed` | `DEV_RULES_COMPUTED` / `DEVELOPMENT_TEST_ONLY` / `false` |
| `rule_core_version`、`rules` | 核心版本；每规则的 `rule_version`、`sql_path`、`sql_sha256`、`hit_count` |
| `cutoff_date`、`period` | 截至日与期间（含范围核对结果） |
| `database_path`、`database_sha256_before` / `_after`、`database_unchanged` | 数据库路径与前后字节哈希（证明未改输入，不宣称防恶意篡改） |
| `read_only` | `{"uri_mode": "ro", "query_only": 1}` |
| `load_source` | 装载来源标识：装载状态、装载／schema 版本、输入哈希、对象指纹、数据库哈希、实际读回的运行元数据 |
| `overall_reconciliation` | 独立从 `payments`／`allocations` 粒度计算的总体勾稽（见第 4 节） |
| `rule_hit_counts` | R01／R02／R03／R04 与 `total` |
| `findings` | 逐条线索（见第 5 节） |
| `statistics` | 涉及的唯一原付款事件集合／数量与整笔已结算总额；R02 按唯一应付单汇总的超额合计；`rule_amounts_not_summed_as_loss=true` |
| `limits` | 固定限制说明 |

**输出稳定排序**：按 `rule_id`、再按结构化命中键排序，不依赖数据库行序、集合或随机数；每个结构化键恰好出现一次（重复即报错）。

## 3. SQL 计算粒度：先汇总退款，再关联原付款

四份固定查询位于 `sql/rules/r01.sql`—`r04.sql`，参数只有 `:cutoff_start`、`:cutoff_end`；不硬编码案例 ID、金额或种子。共同基础：

```text
settled_pay_alloc    截至日已结算 PAY 分摊（transaction_type='PAY'、settlement_status='SETTLED'、日期在范围内）
settled_refund_alloc 指向原分摊的截至日已结算 REFUND 分摊，按 original_allocation_id 先汇总
base                 每条原分摊：allocated_amount、refunded_cents、net_cents = allocated − refunded
```

退款**按 `original_allocation_id` 汇总后再关联原分摊**，因此多条退款不会令原付款金额被重复 `SUM`。`PENDING`／`FAILED`／`VOIDED` 退款不抵减；原付款与退款主表都按类型、状态与日期选取。

四条规则：

| 规则 | 粒度 | 命中条件 |
| --- | --- | --- |
| **R01** | `(ap_id, payee_supplier_id)` 分组，组内逐 `payment_id` | 仅已知应付；每笔原付款对该应付的**退款后净额**精确等于应付金额，且满足条件的不同 `payment_id` **至少两个** → 一条组线索，列出全部满足条件的付款；组内金额是符合条件付款的合计（不冒充应付的全部净付款） |
| **R02** | 唯一 `ap_id`（已知应付），跨收款对象汇总 | `net_total > payable_amount` **严格大于**才命中；输出应付、付款总额、退款总额、净付款、超额；一个应付一条，不乘付款行数，不设重要性阈值 |
| **R03** | 逐条已结算 PAY 分摊 | `ap_id` 为空或不在台账 → 一条；区分 `EMPTY_AP_ID`（未填写关联）与 `AP_NOT_IN_LEDGER`（填写的标识不在台账）；**不加“净额大于 0”过滤**，全额退款后仍保留历史缺失关联事实 |
| **R04** | 逐条能找到应付的已结算 PAY 分摊 | 主表 `payee_supplier_id` 与应付 `supplier_id` 按**原字符串精确比较**不同 → 一条；**不加“净额大于 0”过滤**，退款后仍保留历史对象差异 |

R03／R04 的基础**不把 REFUND 自身当作原付款**生成命中。付款主表**整笔金额**与**分摊金额**分开命名和展示（`payment_amount_cents` 与 `allocated_amount_cents` 不混用）。

## 4. 总体勾稽与统计口径

- 独立从数据库计算：截至日已结算 PAY／REFUND 主表总额、已知应付关联净额、缺失关联净额（`empty_ap_id` 与 `ap_id_not_in_ledger` 分开）、`master_net = known + missing`，逐项与装载报告对照；不一致即失败。
- 总体资金**单独从 `payments` 粒度计算**，不在一对多关联后 `SUM` 整笔金额；分摊金额按 `allocations` 粒度计算，两者**不相加**。
- `statistics.involved_payments` 给出四规则涉及的**唯一原付款事件**集合、数量及其**整笔已结算总额**（整笔资金口径，不能当作缺失关联分摊额或损失）。
- `statistics.r02_overpayment_total_cents` 为 R02 按唯一应付单汇总的超额合计，**不乘以**付款行数或其他规则命中数。
- 四条规则的涉及金额**不相加称为损失**；R01／R02 同时命中也不重复累计 R02 超额。

## 5. 命中键、金额命名与证据

结构化命中键（**不拼接可冲突的字符串**，不使用 `ap_id + "|" + payee` 形式）：

```text
R01: {"rule_id": "R01", "ap_id": "...", "payee_supplier_id": "..."}
R02: {"rule_id": "R02", "ap_id": "..."}
R03/R04: {"rule_id": "R03"|"R04", "allocation_id": "..."}
```

`amounts_cents`（单位一律整数分）：

| 规则 | 键 |
| --- | --- |
| R01 | `payable_amount`、`net_per_payment`（`{payment_id: 分}`）、`net_total` |
| R02 | `payable_amount`、`paid_total`、`refund_total`、`net_total`、`overpayment` |
| R03 | `allocated_amount`、`paid_amount`、`refunded_amount`、`net_amount` |
| R04 | `allocated_amount`、`payable_amount`、`refunded_amount`、`net_amount` |

每条 finding 还包含：`related_ids`（相关应付、原付款、原分摊、退款 ID；R03 另有 `missing_kind_code` 与中文 `missing_kind`，R04 另有双方 ID）、`source_rows`（`{表名: {业务 ID: 原 Excel 行号}}`）、`evidence`（从 `source_records` 读取的 `workbook_sha256`／`sheet`／`excel_row`／**完整 `cells`**，JSON 解码后保留）、`evidence.related_refunds`（相关退款的状态、分摊、`counted_in_net` 是否计入）、`fact`（固定事实描述）与 R03／R04 的 `verification_prompt`（固定的待核实提示）。

**必需来源集合（TASK-006-R1 起）**：每条线索的证据集合包含

1. 能找到的相关应付单；
2. 本条线索相关的**原付款主表**与**原付款分摊**；
3. 本条线索相关的**每条退款分摊及其引用的退款主表**（已结算与已列入 `related_refunds` 的非结算退款都须可追溯）。

退款主表与退款分摊同样经 `source_records` 读取 `workbook_sha256`／`sheet`／`excel_row`／完整 `cells`，其原 Excel 行号同时进入 `source_rows.payments`／`source_rows.allocations`；同一退款主表涉及多条相关退款分摊时只出现一次，实体、行号与退款列表稳定排序。付款全退使净额为 0 时，R03／R04 仍保留原付款与退款证据。

- `related_ids.payment_ids`／`allocation_ids` 仍**只列原付款**及其分摊；退款通过 `refund_ids`、`related_refunds` 与上述扩充实体追溯，不混入唯一原付款数量或资金统计。
- 非结算退款作为**关联记录展示**但 `counted_in_net=false`，不抵减，来源仍齐全。
- R03 没有应付记录时在 `evidence.missing` 中明示缺失，**不伪造应付或来源**。
- 来源缺项或 `cells` JSON 非法**明确失败**（`RuleScreenError`，带阶段、表名、业务 ID），不默默省略后返回“证据完整”，也不返 `DEV_RULES_COMPUTED`。
- 不输出 AI 判断字段、严重等级、自动审计结论或人类判断预填值。

## 6. 验证分离与答案隔离

- **核心不接触答案册**：不接收答案路径、不读取 `evaluation` 目录、不导入生成器；SQL 与核心代码中不含答案册／生成器引用。测试驱动以三项检查证明该边界：核心与规则 SQL 的静态文本检查、运行期文件读取守卫（在守卫下核心仍能成功且未打开答案目录）、以及 `sys.modules` 中不出现生成器模块。
- **先保存、后对照**：每个输入先保存 `screening_report.json`，**全部核心输出保存完成后**测试代码才单独读取只读答案册，逐键比较命中键、已登记金额、相关 ID 与原 Excel 行号；对照只发生在测试侧，不把答案条目复制成核心返回值。
- **必需来源集合与完整内容自动核验**：测试代码**独立**从数据库业务表推导每条线索的必需实体集合（相关应付＋原付款主表／分摊＋相关退款分摊及其退款主表），逐条检查：必需实体齐全且同一 `(table_name, record_id)` 不重复；每个实体与 `source_records` 的 `workbook_sha256`／`sheet`／`excel_row`／完整 `cells`（JSON 解码后）**逐项精确相等**；每个源行号都进入 `source_rows`；退款摘要与其实体一致且 `counted_in_net` 与状态相符。**不把当前输出的已有实体当作“应有集合”**，也不只检查非空或字段数。
- **来源失败回归**：用只读连接代理分别注入原付款主表来源缺失、退款主表来源缺失、退款分摊来源缺失、退款主表 `cells` JSON 非法、退款分摊 `cells` JSON 非法，五项都必须抛出 `RuleScreenError`（`RuleScreenBlocked` 不算通过），并断言注入确实被目标查询触发；故障注入不改数据库、不加生产测试开关。
- 上游质量未通过（真实 checker 未通过）时不进入规则阶段，登记“未执行／上游阻断”，**不写成“成功且零命中”**。

## 7. 真实测试命令

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_03'
```

- 测试容器必须是 `data\sqlite_tests` 内**尚不存在**的子目录；越界、指向该目录本身或已存在时在写入前退出 2。
- 每个工作簿输入都制作新副本，真实 checker CLI 留独立 `stdout`／`stderr` 与完整命令，再调用冻结标准化与装载 API，保存 `normalized.json`、`load_report.json`、数据库，最后调用规则核心保存 `screening_report.json`。
- 覆盖：主文件与 22 份 fixture（14 份对照 `fixture_expectations.json`，8 份登记上游阻断）、六个小补充场景（全额退款后仍保留 R03／三笔足额付款／付款对象差异叠加超额／三种非结算退款不抵减／含 `|` 与引号的分组键不碰撞／无资金事件）、三项接口边界（缺失数据库、字节与报告不符的副本、未发布 `.staging`）、确定性复调用、**逐条必需来源集合与完整 `cells` 核验**，以及**五项来源读取故障回归**（原付款主表／退款主表／退款分摊缺来源、退款主表／退款分摊 `cells` 非法）。
- 退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。输入案例数、核心调用数、复调用次数、故障注入调用次数、成功／上游阻断／接口阻断／运行错误／测试失败分开统计。

## 8. 边界（尚未做，也不在本卡范围）

- 未接入正式业务流程、正式契约或批准控制；未推进任何既有批次，未改变 Gate 1／Gate 2 状态。
- 未生成 AI 候选结论／等级，未填写人类初步或最终判断；AI 对照建议须等待未来保存本批次人类独立初步判断之后另行下卡。
- 按规格计算**重复足额付款线索**（R01）与**净付款超额线索**（R02）等确定性事实，但**不直接认定损失、舞弊、控制缺陷或审计调整**；不设重要性阈值；不导出审计调整；不计算超付损失金额、风险等级或责任归属。
- 本地哈希与只读保护用于证明**未改输入**，不声称抵御同权限恶意篡改；不证明真实 ERP 兼容性或真实数据完整性。
- 规则只按 SPEC 的确定性口径计算事实与固定提示，不代替人工核实合同、代收授权、主体映射与银行回单。
