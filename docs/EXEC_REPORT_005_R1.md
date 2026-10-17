# TASK-005-R1 执行回执（SQLite 装载四项定点修订）

任务：修订 TASK-005 验收发现的四处缺口——F01 独立核对在 COMMIT 之后、F02 缺少单元格原值／类型／坐标仍报成功、F03 发布会覆盖检查后新出现的目标、F04 独立核对未读取运行元数据。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-005-R1.md`、`docs/reviews/REVIEW_TASK_005.md`、`docs/tasks/TASK-005_DRAFT.md`、`docs/SQLITE_LOAD_GUIDE.md`、`docs/reviews/REVIEW_TASK_004_R1.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未做 R01—R04 筛查，未建立契约或审批控制，未推进任务六。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧 `EXEC_REPORT_005.md` 保留为历史，未回写。

---

## 1. 结论摘要

| 项目 | 修订结果 |
| --- | --- |
| **F01** 核对与提交顺序 | 改为 **建空 schema → BEGIN → 写入业务／来源／元数据 → 同一未提交事务内完成全部独立核对 → COMMIT → 关闭 → 无覆盖发布 → 最终哈希**。提交前失败按实际事务状态回滚：暂存库六表 **0 行**、无目标库、无成功报告 |
| **F02** 完整单元格来源 | 装载前核验每个固定字段的十个必需键（含 `raw_value` **键必须存在**，值可为 `None`）、`column_index` 为正整数非 bool、`column_letter` 与列号对应、`cell` =「列字母 + 原 Excel 行号」、`encoding`／`excel_data_type` 为已验收取值；缺失或坐标矛盾 → `SqliteLoadBlocked` 并给出字段路径，**写入前拒绝且不创建目标或暂存库** |
| **F03** 无覆盖发布 | 最终发布不再使用 `os.replace`：首选 `os.link`（目标已存在即 `FileExistsError`），不支持时回退为独占创建（`open(..., "xb")`）后复制字节；**不覆盖、不先删除**既有目标，发布阶段冲突为 `SqliteLoadError`，入口冲突仍为 `SqliteLoadBlocked` |
| **F04** 运行元数据核对 | `verify_database` 从 `run_metadata` **实际查询**，核验键集合完整、无预期外键，并与**本次生成一次**的预期逐项比较（含模式、`next_step_allowed=false`、输入与对象指纹、冻结／装载器／schema 哈希、四表行数、完整标准化上下文解码后精确相等）；缺项或不一致即回滚 |
| 失败状态如实报告 | 错误信息区分**提交前**（已回滚、六表 0 行）与**提交后**（不声称回滚；暂存库保留已提交数据、目标文件是否存在与实际字节为准），并附阶段、目标／暂存路径、`数据事务已提交`、`目标文件已发布`、暂存库六表实测行数 |
| 开发验证 | **39 个案例全部符合预期，测试失败 0**：入库成功 **18**、质量阻断 **8**、装载阻断 **6**、运行失败 **7**；真实 checker CLI **26** 次；测试进程退出 **0** |
| 版本 | 装载实现版本提升为 `TASK-005-sqlite-load-1.1`；**schema 版本与文件保持 `demo-schema-1.0`／原字节** |
| 上游冻结 | 标准化器 `a2bae49e…`、checker `a7e5eb67…`、接收器 `52195620…`、生成器 `e899aa2f…`、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| 历史保护 | GPT 的 TASK-005 验收基线 **7506 个文件**：**3 个变化（恰为本卡授权文件）、0 个缺失**；TASK-004-R1 基线 6511 个、TASK-003-R3 基线 4902 个、任务二基线 874 个：均 0 个变化 |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 | 说明 |
| --- | --- | --- |
| `D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py` | `6128f09b64eb5ef8554e448b023d382cb142bcb3c933e198c138d9c740d7fc35` | F01—F04 实现 |
| `D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py` | `6cc9c932e369e7e0452613bc7425731d641b9d8c7d4c7ae30aaf7a5a40162914` | 原 33 例保留 + R1 新增 6 例 |
| `D:\harness work\audit_sa_project\docs\SQLITE_LOAD_GUIDE.md` | `15cbb356b31d212000261bef3cc127461cc00c9673c7e66cb541b9432500b48f` | 事务顺序、来源前提、元数据核对、无覆盖发布、提交前后失败区别 |
| `D:\harness work\audit_sa_project\sql\demo_schema.sql` | `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205`（**未变**） | 本轮不需要改表结构 |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_005_R1.md` | 本文件 | 新增回执 |

新增测试容器（`data\sqlite_tests\`）：`task005_r1_02`（**最终**，190 个文件）、`task005_r1_01`（同 39 例、版本串仍为 1.0 的现场）、`task005_r1_smoke_01`（四项修订的单点冒烟）、以及上一轮 `task005_05` 等历史容器。全部保留，未覆盖。

---

## 3. F01—F04 逐项实现与对应案例

### F01 提交前完成全部核对

实现：`load_normalized_to_sqlite()` 重新编排为「建空 schema → `BEGIN` → 写入 → **同一连接、同一未提交事务内** `verify_database()` → `COMMIT` → 关闭 → `publish_database()` → 最终哈希」。事务内不使用 `executescript`；自关联仍为可延迟，未改变原 Excel 行顺序；真实空付款正例仍通过。失败时按实际状态回滚；错误信息追加 `_state_notes()`（阶段、目标／暂存路径、是否已提交、是否已发布、暂存库六表实测行数、目标文件是否存在、回滚／关闭异常），不掩盖最初错误。

| 案例 | 注入 | 实际结果 |
| --- | --- | --- |
| `Q01_verify_failure_rolls_back` | C01 内存副本 `table_totals.payables_payable_amount.normalized += 1` | `SqliteLoadError`，摘要含“数据库独立核对未通过”，差异含 `500000` 与 `500001`；`数据事务已提交=False`；**暂存库六表全为 0**（suppliers/payables/payments/allocations/source_records/run_metadata）；无目标库；无成功报告 |

### F02 装载前核验完整单元格来源

实现：新增 `CELL_REQUIRED_KEYS`（十个键）、`ALLOWED_ENCODINGS`、`ALLOWED_EXCEL_DATA_TYPES`，并在 `_check_record()` 内对每个固定字段核验：十个键齐全（`raw_value` 必须存在，允许 `None`）、`column_index` 为 `>=1` 整数且非 bool、`column_letter == get_column_letter(column_index)`、`cell == f"{column_letter}{source.excel_row}"`、`encoding`／`excel_data_type` 属于已验收取值、`python_type` 非空字符串、`target_field`／`standard_value` 与 `data` 对应。全部检查在 `require_loadable()` 内，即**在任何文件创建之前**。

| 案例 | 注入 | 实际结果 |
| --- | --- | --- |
| `Q02_cell_missing_provenance` | `suppliers.records[0].cells.supplier_id` 只保留 `input_field`／`target_field`／`standard_value` | `SqliteLoadBlocked`，消息含“缺少必需来源字段”与字段路径 `tables.suppliers.records[0].cells.supplier_id`；**无目标库、无暂存库** |
| `Q02b_cell_wrong_coordinate` | `payables.records[0].cells.ap_id.cell` 改为与实际列号／行号不符的 `Z9` | `SqliteLoadBlocked`，指出坐标关系不符（`.cell` 应为实际列字母 + 原行号）；无暂存库 |
| 合法空原值不被误挡 | 正常 18 个输入（含 `original_payment_id`／`bank_reference`／`ap_id` 为空的单元格，其 `raw_value` 为 `None`） | 全部入库成功且 `round_trip_exact=true`；正常列位置与行号保留（P2 列重排、P3 行序调整均通过） |

### F03 无覆盖发布

实现：新增 `publish_database()`：先调用 `pre_publish_hook()`（默认无操作，仅作测试接缝），再用 `os.link(staging, target)` 发布——目标已存在即 `FileExistsError` → `_publish_conflict()` 抛 `SqliteLoadError`（含阶段、目标／暂存路径、“未覆盖、未删除目标字节”与原异常）；`os.link` 因文件系统不支持而失败时回退 `_copy_no_clobber()`（`open(target, "xb")` 独占创建后复制，同样遇既有目标即失败）。发布成功后删除暂存文件。**代码中已无 `os.replace`**。

| 案例 | 注入 | 实际结果 |
| --- | --- | --- |
| `Q03_target_appears_before_publish` | 发布前钩子在核对成功、发布之前向目标写入 `MARKER-Q03-EXISTING-TARGET` | `SqliteLoadError`，含“拒绝覆盖”与 `阶段=publish_database`；**标记字节原样保留**（读回等于写入内容）；无成功报告；如实说明 `数据事务已提交=True`、`目标文件已发布=False`，暂存库保留已提交数据（未假报回滚） |
| `N1_same_path_again` | 入口即已存在目标（对已入库库再次装载） | `SqliteLoadBlocked`（含“已存在”），原库字节哈希未变，仍等于原装载报告中的 `database_sha256` |
| `N2_out_of_range_path` | 目标位于 `data/sqlite_tests` 之外 | `SqliteLoadBlocked`（含“必须位于”），目标与其父目录均未创建 |

### F04 运行元数据纳入数据库核对

实现：`verify_database(connection, normalized, expected_metadata)` 从 `run_metadata` 实际 `SELECT`，比较键集合（缺失／多余均报差异）、逐键值，并对 `schema_version`、`store_version`、`mode`、`next_step_allowed`、`batch_status`、`input_sha256`、`normalized_payload_sha256` 单独报告实际值与预期值；`table_row_counts_json` 与 `normalization_context_json` **解码后**与本次预期结构精确比较。预期元数据在装载前生成**一次**（`created_at_utc` 只生成一次），核对时不重新生成时间或指纹；指纹仍是完整传入对象的固定 JSON 序列化哈希。

| 案例 | 注入 | 实际结果 |
| --- | --- | --- |
| `Q04_metadata_not_written` | `insert_run_metadata` 替换为不写任何行 | `SqliteLoadError`，原因含“run_metadata 缺少必需键”（列出 17 个键）；**暂存库六表全为 0**；无目标库；无成功报告 |
| `Q04b_metadata_fingerprint_wrong` | 写入时把 `normalized_payload_sha256` 末位改错一位 | `SqliteLoadError`，原因含 `normalized_payload_sha256` 实际值与预期值不一致；暂存库六表全为 0 |
| 正常路径 | 无注入 | 元数据 17 行，`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`、`batch_status=DEV_SQLITE_VERIFIED`，报告新增 `run_metadata` 摘要 |

---

## 4. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 4.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py'
```

退出码均 **0**。

### 4.2 四项修订的单点冒烟

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r1_smoke_01\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r1_smoke_01\report.json'
```

随后在内存中依次调用标准化 API 与 `load_normalized_to_sqlite()`（正常路径 + Q01—Q04 注入）。checker 退出 **0**；正常路径 `DEV_SQLITE_VERIFIED`、往返精确、暂存文件已发布并清理；Q01/Q04 回滚后六表全 0；Q02 写入前阻断且无暂存库；Q03 目标标记保留。

### 4.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r1_02'
```

退出码 **0**；输出“案例 39 个：入库成功 18、质量阻断 8、装载阻断 6、运行失败 7；checker CLI 调用 26 次；测试失败 0”“受保护文件前后哈希一致: True（34 个）”。
命令与日志：`data\sqlite_tests\task005_r1_02\command_log.json`（26 次 checker 调用的完整 `argv`、退出码、独立 stdout／stderr 路径）、`summary.json`（统计、逐案结果、保护核对）；各案例目录内保存 `input.xlsx`、`checker_report.json`、`normalized.json`、`demo.sqlite`／`load_report.json` 或失败记录，注入案例另有 `injected_normalized.json` 与 `injection_note.txt`。

### 4.4 其他核验

```powershell
& $py -c "import sys, sqlite3; from importlib.metadata import version; print(sys.version.split()[0], sqlite3.sqlite_version)"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\sql\demo_schema.sql' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\SQLITE_LOAD_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对、失败现场六表行数核验与统计；未新增 `.py` 文件。

---

## 5. 实际结果与数量

| 项目 | 数量 |
| --- | --- |
| 案例总数 | **39**（原 33 + R1 新增 6） |
| 入库成功 | **18** |
| 质量阻断（上游标准化阶段阻断） | **8** |
| 装载阻断 | **6**（金额字符串、bool 金额、入口已存在目标、越界路径、缺来源字段、错误坐标） |
| 运行失败 | **7**（重复主键、缺失资金关联、原 I5 中途失败、Q01 核对阶段失败、Q03 发布阶段冲突、Q04 元数据缺失、Q04b 对象指纹错误） |
| 预期负向合计 | **21** |
| 真实 checker CLI 调用 | **26** |
| 测试失败 | **0** |

原 18 个正常输入（主文件、14 份 fixture、无资金正例、标识保真、退款先出现）继续通过并逐项往返相等；主文件仍为四表 20／993／1000／1005 行、净额 267 249 329 分 = 已知 266 249 329 + 缺失 1 000 000 分；C03 净额仍为 1 000 000 分。原 8 份质量阻断、金额字符串／bool、重复主键、缺失资金关联与原 I5 中途失败的处理不变。

### 5.1 各失败阶段的文件与六表实际状态

| 阶段 | 案例 | 目标文件 | 暂存库六表 | 报告 |
| --- | --- | --- | --- | --- |
| 写入前（前提／路径） | Q02、Q02b、I1、I2、N1、N2 | 不存在（N1 为既有库，字节未变） | 不创建 | 无成功报告 |
| 事务内写入失败 | I3、I4、I5 | 不存在 | 全部 0 行（已回滚） | 无成功报告 |
| 事务内核对失败 | Q01、Q04、Q04b | 不存在 | 全部 0 行（已回滚） | 无成功报告 |
| 提交后发布失败 | Q03 | **已存在且字节原样保留（标记未变）** | 保留已提交数据（如实说明，不假报回滚） | 无成功报告 |

## 6. 失败尝试与修正过程

1. **旧流程的顺序错误（本轮修订对象）**：原实现在 `COMMIT` 之后才调用 `verify_database`，导致核对失败仍留下已提交数据与 `VERIFIED` 元数据——已按 F01 改为事务内核对。
2. **`_cleanup()` 中误用模块级 `global` 记录关闭异常**：改为闭包 `close_notes` 列表，异常说明随 `reasons` 一并给出，不掩盖最初错误。
3. **冒烟脚本的断言位置写错**：`Q04` 的检查断言写成 `str(exc)`（只含摘要）而非 `exc.reasons`，一度显示“未拒绝”；实际差异在 `reasons` 中，只读 SQL 亦确认六表为 0。正式测试改为断言 `reasons`，并新增 `Case.reasons` 采集。
4. **`Q01` 断言最初写法无意义**（用 `or True` 兜底）：改为断言失败确实发生在数据库核对阶段（摘要含“数据库独立核对未通过”），同时断言事务未提交与六表 0 行。
5. **版本串不一致**：说明文档头部写 1.1 而模块常量仍为 1.0；已把 `STORE_VERSION` 提升为 `TASK-005-sqlite-load-1.1` 并重跑最终验证（`task005_r1_01` 为 1.0 版本串现场，保留）。
6. 未修改上游代码、规格、契约草案、旧回执与任何历史测试产物；未向 GPT 的验收目录追加结果；所有注入只作用于内存副本或本轮新测试文件。

## 7. 历史保护对照

- GPT 的 TASK-005 验收基线（`data/reviews/task005_20261011_055303/source_hashes_after.json`）**7506 个文件**：变化 **3**（`scripts\store_demo_sqlite.py`、`tests\test_store_demo_sqlite.py`、`docs\SQLITE_LOAD_GUIDE.md`，恰为本卡授权文件）、缺失 **0**。
- TASK-004-R1 验收基线 **6511 个**、TASK-003-R3 验收基线 **4902 个**、任务二 R2 基线 **874 个**：均 **0 个变化、0 个缺失**。
- `sql/demo_schema.sql` 保持原字节 `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205`；上游冻结哈希见第 1 节。
- 测试内建核验：**34 个受保护文件**（冻结脚本、schema、规格、契约草案、上游说明与回执、标准化测试、主演示输入与 22 份 fixture）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 8. 偏差、未解决问题与停止状态

- **偏差**：本轮新增测试接缝 `pre_publish_hook()`（默认无操作）与 `row_state()` 取证函数；它们只用于在“核对成功、发布之前”注入故障与如实报告失败现场，不改变正常路径行为。装载实现版本提升为 1.1，schema 版本保持 1.0（未改表结构）。
- **未执行（不主张通过）**：R01—R04 筛查、AI 审计建议、判断表、正式契约、批准命令、业务状态机、RAG、OCR、百万行压测、真实 ERP 接入；未重跑任务二、三、四的整套测试（按要求只重验冻结哈希与历史文件无变化）。
- **已知限制**：装载前提只覆盖本层消费的标准数据契约，不等同于完整 ERP 质量校验；`PRAGMA foreign_key_check`／`integrity_check` **不是审计结论检查**；入库通过**不表示没有业务线索**；本地哈希不证明来源真实性，也不抵御同权限篡改；无覆盖发布解决的是本地装载的“不覆盖已有文件”承诺，不构成抵御恶意同权限篡改的安全隔离。
- **停止状态**：未接入 `data/batches`、未修改任何旧 `batch_manifest.json`、未建立契约或批准指纹控制、**未宣称已实现 Gate 1／Gate 2 放行**，未开始任何规则筛查、未推进任务六。
- 等待主理人把本回执与 `docs\SQLITE_LOAD_GUIDE.md`、`data\sqlite_tests\task005_r1_02` 转交总架构师复验。
