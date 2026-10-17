# SQLite 装载说明（TASK-005）

版本：TASK-005-sqlite-load-1.2（TASK-005-R2 起）/ demo-schema-1.0；日期：2026-10-11；执行端：DeepSeek；依据：`docs/tasks/TASK-005_DRAFT.md`、`docs/tasks/TASK-005-R1.md`、`docs/tasks/TASK-005-R2.md`、`docs/reviews/REVIEW_TASK_005.md`、`docs/reviews/REVIEW_TASK_005_R1.md`、`docs/reviews/REVIEW_TASK_004_R1.md`、`docs/NORMALIZATION_GUIDE.md`、`docs/SPEC_V1.md` 第 2—4 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2、3 节。

本文说明开发态 SQLite 装载核心的**公共 API、六表结构与关键约束、NULL 应付关联为何允许、事务与失败产物、SQL 勾稽与往返方式、真实测试命令**，以及它**尚未**接入正式流程的边界。

> 本模块是 `DEVELOPMENT_TEST_ONLY`：不接正式业务流程，不建立契约或批准命令，不自动推进 Gate 1／Gate 2。
> **入库通过不表示没有业务线索，也不是审计结论。**

---

## 1. 公共 API

函数签名：

```python
def load_normalized_to_sqlite(normalized: dict, database_path) -> dict: ...
```

合法调用示例：

```python
from scripts.store_demo_sqlite import load_normalized_to_sqlite

report = load_normalized_to_sqlite(normalized, database_path)
```

- 读取内存中的标准化结果，写入**全新**数据库，返回本次装载核对报告；调用方负责保存报告。
- 本核心**不重跑标准化、不写回 Excel、不接收业务批次批准**。
- 只有前提检查、单事务装载、数据库独立核对、提交、**严格关闭**、无覆盖发布与最终文件哈希**全部成功**，才返回 `batch_status = DEV_SQLITE_VERIFIED`；该状态**只表示开发数据库装载已核对**，`next_step_allowed` 始终为 `false`。
- **正常路径的关闭必须成功**：`close()` 抛异常时立即中止成功流程，按 `阶段=close_database` 抛 `SqliteLoadError`，**不继续哈希暂存库、不发布、不返回成功报告**；即便随后的错误清理再次尝试关闭并成功，也不会把本次调用恢复成发布成功。
- 异常类型（两种，语义不同）：
  - `SqliteLoadBlocked`：输入不满足装载前提（版本／模式／质量结果／结构／字段类型／**完整单元格来源**），或**入口**目标路径越界、已存在等**写入前**拒绝。不建库（连暂存库也不创建）、不返回成功报告。
  - `SqliteLoadError`：文件、数据库约束或一致性运行错误，保留**阶段、路径与原始异常**（异常链），并按失败发生的时点如实说明数据与文件状态：
    - **提交前失败**（建 schema／写入／同一事务内核对）：数据事务已回滚，保留空 schema 暂存库，**六张表数据行数均为 0**，无目标文件，不返回成功报告；
    - **提交后失败**（关闭／暂存哈希／发布／最终哈希）：**不声称已回滚**——暂存库保留已提交数据；若目标文件已存在（例如发布时晚出现）则保持其原字节不变；错误信息中给出阶段、目标与暂存路径、`数据事务已提交`、`目标文件已发布`、暂存库六表实际行数与目标文件是否存在。
  - 发布阶段遇到已有目标属于 `SqliteLoadError`（不是写入前阻断）；入口检查发现目标已存在仍为 `SqliteLoadBlocked`。

### 1.1 装载前提（本层实际需要的标准数据契约）

- `normalization_version` 必须是已验收的 `TASK-004-normalized-1.1`，`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`；
- `quality_report.result == "pass"`；`amount_reconciliation.normalized_equals_report is True` 且 `checks` 非空全为 `true`；
- 四张表都存在 `records`／`blank_rows`／`extra_columns`，且 `row_accounting[sheet].normalized_rows` 等于记录数——**缺失不等于空表**；
- 每条记录的 `data` 业务字段与本版固定字段**完全一致**；必填文本是实际 `str`，可空字段只接受 `str` 或 `None`，金额是实际 `int` 且非 `bool`、严格为正，日期是标准 ISO 日期字符串；**禁止为入库做 `str()`／`int()` 转换或自动改写字段**；
- 每条 `source.workbook_sha256` 等于本结果来源哈希，`sheet` 与原 Excel 行号可用；`cells` 覆盖该表全部固定输入字段——**不静默丢来源**。
- **每个单元格来源必须完整**：`cells[字段]` 至少包含 `excel_data_type`、`encoding`、`raw_value`、`python_type`、`input_field`、`column_index`、`column_letter`、`cell`、`target_field`、`standard_value` 十个键。其中：
  - `raw_value` **必须存在这个键**（值可以是 `None`：合法空原值与缺键是两回事）；
  - `column_index` 为 `>=1` 的整数且非 `bool`；`column_letter` 必须与该列号对应；`cell` 必须等于「列字母 + `source.excel_row`」——因此**正常重排列顺序仍然保真**，坐标矛盾会被拒绝；
  - `encoding` 与 `excel_data_type` 必须是已验收取值之一，`python_type` 为非空字符串；
  - `target_field`／`standard_value` 与 `data` 对应。
  缺键、类型不符或坐标矛盾一律 `SqliteLoadBlocked`（给出字段路径），**写入前拒绝且不创建目标或暂存库**，也不补造来源或删除不完整记录后继续。

这层只检查装载所需契约，不是完整 ERP 质量校验器；身份、退款合法性与业务范围仍依赖上游真实 checker／标准化流程。本地哈希不证明来源真实性，也不抵御同权限篡改。

### 1.2 路径边界

数据库路径只允许 `data/sqlite_tests` 中的**新文件**：解析绝对路径后核对范围，拒绝根目录、越界或已存在目标，均在写入前停止。测试容器本身也必须全新，不覆盖、不删除历史。

## 2. 数据库结构（六张表）

| 表 | 内容 |
| --- | --- |
| `suppliers` | `supplier_id`（TEXT 主键）、`supplier_name` |
| `payables` | `ap_id`（TEXT 主键）、`ap_number`、`supplier_id`（→ suppliers）、`ap_date`、`payable_amount_cents`（INTEGER 分）、`currency` |
| `payments` | `payment_id`（TEXT 主键）、`transaction_type`、`original_payment_id`（可空自关联）、`payee_supplier_id`（→ suppliers）、`payment_date`、`amount_cents`（INTEGER 分）、`currency`、`settlement_status`、`bank_reference`（可空） |
| `allocations` | `allocation_id`（TEXT 主键）、`payment_id`（→ payments）、`ap_id`（**可空、无外键**）、`allocated_amount_cents`（INTEGER 分）、`original_allocation_id`（可空自关联） |
| `source_records` | 每条业务记录一条来源：`table_name`、`record_id`、`workbook_sha256`、`sheet`、`excel_row`、`cells_json`；主键 `(table_name, record_id)` |
| `run_metadata` | 本次装载元数据（键值对） |

业务金额**只用** `*_cents` 整数分列，不另存“元”业务金额列。

### 2.1 关键约束

- 四表业务主键为 `TEXT PRIMARY KEY NOT NULL`；字符串**原样保存**，保留前导零、空格与标点（不做 `trim` 或格式改写）。
- 日期／枚举为文本并带 `CHECK`（日期匹配 `YYYY-MM-DD`；`currency='CNY'`；`transaction_type IN ('PAY','REFUND')`；`settlement_status IN ('SETTLED','PENDING','FAILED','VOIDED')`）。
- 金额列要求 `typeof(...) = 'integer'` 且 `> 0`。
- 付款约束：`PAY` 不得有 `original_payment_id`，`REFUND` 必须有；已结算必须有非空 `bank_reference`，非结算必须为空。
- 索引：`payments` 上**已结算** `bank_reference` 的部分唯一索引；`allocations` 上 `(payment_id, ap_id)` 的部分唯一索引（`ap_id IS NOT NULL`），以及 `ap_id IS NULL` 时按 `payment_id` 唯一的**另一条部分唯一索引**——SQL 的普通 `UNIQUE` 会放过多个 `NULL`，未指定 `ap_id` 的重复组合必须靠这两条索引拦住。
- 外键：`payables.supplier_id`、`payments.payee_supplier_id` → `suppliers`；`allocations.payment_id` → `payments`；`original_payment_id`／`original_allocation_id` 为**可空自关联**，使用 `DEFERRABLE INITIALLY DEFERRED`，因此**不要求原付款／原分摊出现在 Excel 较早一行**。
- 事务开始前启用 `PRAGMA foreign_keys = ON` 并实际核验为 `1`。

### 2.2 为什么 `allocations.ap_id` 允许 NULL 且不设外键

`ap_id` 表示“这笔分摊指向哪张应付”。实务上它可能**未指定**（空值）或**在应付台账中找不到**（台账外标识），这两种情况都是需要保留的业务事实，而不是要删除或修正的脏数据：

- 设成外键会强制要求台账存在，等于**改动/删除**这些业务事实；
- 把空值改写成某个值会**伪造**关联对象；
- 因此只做基本类型约束（`NULL` 或非空文本），由 SQL 勾稽把它们分别统计为“空 `ap_id`”与“台账未找到”，两者都保留。

## 3. 事务、失败现场与成功定义

**真实执行顺序**（TASK-005-R1 起）：

```
前提检查 → 路径检查 → 建空 schema（executescript，在数据事务之前）
→ BEGIN → 写入业务表／来源记录／运行元数据
→ 在同一未提交事务内从数据库读取并完成全部独立核对（数量、金额、分组、逐笔分摊、
  已结算总额、净额、外键、完整性、往返、运行元数据）
→ COMMIT → 严格关闭连接 → 无覆盖发布 → 最终文件哈希 → 返回 DEV_SQLITE_VERIFIED
```

**两类关闭的处理不同**：

- **正常路径（严格关闭）**：关闭必须成功。`close()` 抛异常即按 `阶段=close_database` 抛 `SqliteLoadError`，中止成功流程——不哈希暂存库、不调用发布、不返回成功报告；错误信息保留目标／暂存路径与原始异常链。此时数据事务已提交，因此说明提交为真、发布为假，并保留已提交暂存库及实际行数。
- **已有错误后的清理（尽力关闭）**：只作尽力清理，关闭再失败仅作为附记（例如“清理时关闭连接失败：…”），**不覆盖最初的写入／核对／文件错误**；也不为了隐藏关闭失败而丢弃仍需清理的连接引用。附记不影响主错误类型与主要差异。

- 所有业务、来源与运行元数据在**同一个数据事务**内；事务内不使用会误提交的 `executescript`。SQLite 允许本连接读取本事务未提交的记录，因此**核对不需要先提交**。
- 数量、金额、分组、逐笔分摊、净额、外键、完整性、往返与运行元数据核对**全部通过后才提交**。
- **提交前失败**：按实际事务状态回滚，保留空 schema 暂存库（六表 0 行），无目标文件、无成功报告；不回填、不删除失败现场冒充回滚，也不只清空部分表。
- **提交后失败**（关闭／暂存哈希／发布／最终哈希）：保留真实现场，错误信息说明阶段与已发生的事务／文件状态，**不虚报六表零行、不宣称文件不存在**；已有目标文件的字节保持不变。
- 采用**暂存库 + 无覆盖发布**：写入 `<目标名>.staging`，全部核对、提交与严格关闭成功后才发布；**不使用可覆盖目标的 `os.replace`**，发布层首选硬链接（目标已存在即 `FileExistsError`），硬链接不可用时回退为独占创建（`open(..., 'xb')`）后复制字节——两条路径都**不会覆盖、不会先删除**既有目标。
- 提交后各阶段的文件状态**以实际磁盘为准**，不笼统承诺每个阶段都仍有暂存文件：发布成功后暂存文件被删除（只留目标文件）；发布被拒绝或最终哈希失败时目标文件可能不存在，而暂存文件通常仍在且已含提交数据——错误信息会给出阶段、目标／暂存路径、`数据事务已提交`、`目标文件已发布`、暂存库六表**实测**行数与目标文件是否存在。
- 若错误发生在文件发布之后，保留实际文件与失败阶段，如实报告，不宣称文件不存在。
- 未执行 `PRAGMA foreign_keys` 核验、未通过全部核对、未提交、**关闭未成功**、未取到最终哈希时，都不返回成功报告。

## 4. SQL 勾稽与往返（全部从数据库实际读取）

对照数字不直接把传入 JSON 复制成“SQL 结果”，而是先查询再比较：

1. 四表行数分别与标准化结果相等；`source_records` 数量与对应关系完整，每条业务行恰有一条来源（左连接检查孤立行）。
2. 三个金额字段分别 `SUM`，与标准化完整金额逐项相等；付款按类型／状态分组后用 SQL 与标准化分组**双向**比较（含非结算组）。
3. 每笔资金事件 `amount_cents` 等于其全部分摊 `allocated_amount_cents` 之和（含非结算与未匹配部分）。
4. 已结算 `PAY`／`REFUND` 主表总额分别等于对应分摊总额。
5. 净额：主表净额 = 已知应付关联净额 + 缺失应付关联净额，缺失再分空 `ap_id`／台账未找到，并与标准化三项完整净额及缺失分类对照。主表资金总额**单独从 `payments` 计算**，分摊总额按 `allocations` 粒度计算，**两者不相加**，不会因一对多连接重复累计主表金额。
6. `PRAGMA foreign_key_check` 无问题、`PRAGMA integrity_check` 返回 `ok`（**不是审计结论检查**）。
7. **往返**：从业务表与 `source_records` 按原 Excel 行号重建每条 `data`／`source`／`cells`，与传入记录**逐项精确相等**（JSON 解码后核对来源内容，不只断言 `cells_json` 非空，也不只比较总数或总金额；残缺的 `cells` 对象不可能靠“与自身比较相等”通过，因为装载前已要求十个必需键完整）。
8. **运行元数据**：从 `run_metadata` **实际读取**（不把待插入的 Python 列表当读取结果），核验键集合完整、无预期外键，并与**本次生成一次**的预期逐项比较：`schema_version`／`store_version`／`mode`／`next_step_allowed=false`／`batch_status`／`input_sha256`／`normalized_payload_sha256`／冻结版本哈希／装载器与 schema 哈希／`created_at_utc`，以及 `table_row_counts_json` 与 `normalization_context_json` **解码后的结构精确相等**（含版本、来源、质量摘要、数量金额、空白行、额外表／列与限制）。核对时不重新生成时间或指纹。

真实空表的 `SUM` 无行可按 0 展示；缺失／无效金额**不得**用这种方式填零。不要求应付金额等于付款金额；本卡不计算超付、重复付款、风险等级或损失。

## 5. 装载报告

返回报告包含：`batch_status`、`store_version`、`schema_version`、`mode`、`next_step_allowed`、数据库路径与**最终字节哈希**、`normalized_payload_sha256`、四表行数与来源记录数、三项 SQL 合计对照、付款分组、已结算主表／分摊总额、主表净额与缺失分类、`net_checks`、`foreign_key_check`／`integrity_check`、往返记录数与 `round_trip_exact`、`run_metadata`（实际读回的键值摘要与行数）、`scope_limits`。

`normalized_payload_sha256` 是对**完整传入对象**按固定 JSON 规则（`sort_keys`、紧凑分隔符、`allow_nan=False`）序列化后的哈希，是**对象规范化指纹**，不是某个旧 JSON 文件的字节哈希。

SQL 对业务值一律参数绑定，表名／列名只来自固定白名单（`sql/demo_schema.sql` 与模块内的固定字段表）。

## 6. 真实测试命令

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_05'
```

- 测试容器必须是 `data\sqlite_tests` 内**尚不存在**的子目录；越界、指向该目录本身或已存在时在写入前退出 2。
- 每个案例保存输入副本、真实 checker 报告与独立 stdout／stderr、新标准化结果、数据库及装载报告（或明确的失败记录）。
- 覆盖：主文件与 14 份质量有效 fixture（全部入库并往返精确相等）、8 份质量阻断 fixture（不建可用数据库）、三个小正例（无资金事件；前导零／首尾空格／单引号标识保真；退款与原分摊引用放在原记录之前）、路径拒绝（同一路径二次装载、越界路径）、内存注入（金额字符串／bool、重复业务主键、缺失强制资金关联）、事务中途故障（回滚且暂存库无半批数据），TASK-005-R1 新增的六项定点回归（核对阶段失败须回滚、单元格来源缺原值／类型／坐标须写入前阻断含错误坐标变体、发布阶段目标晚出现须拒绝覆盖、运行元数据未写入与对象指纹被改错须被发现），以及 TASK-005-R2 新增的两项：**正常关闭报错必须中止发布**（发布函数调用次数为 0、目标不存在、已提交暂存库保留完整行数）、**原错误后清理关闭再报错不得掩盖原错误**（主错误仍是核对差异，关闭失败仅作附记）。
- 退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。质量阻断、装载阻断、运行失败与测试失败分开统计。

## 7. 边界（尚未做，也不在本卡范围）

- 未接入正式业务流程：不读取 `data/batches` 作为处理对象，不修改任何旧 `batch_manifest.json`，不推进任何既有批次。
- 未实现 R01—R04 筛查、AI 建议、判断表、正式契约、批准命令或状态机；**入库通过不等于获准筛查**，后续 SQL 筛查须经人工放行后另行开展。
- 不计算超付、重复付款、风险等级或损失；不导出 AI 结论。
- 报告检查覆盖本层消费的标准数据契约，不宣称完整 ERP 质量校验或真实模板兼容性。
- 原始 Excel 字节仍是原始载体；本地哈希不证明来源真实性，也不抵御同权限篡改。
