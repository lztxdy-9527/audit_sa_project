# TASK-005 执行回执（开发态 SQLite 入库、往返核对与 SQL 勾稽）

任务：开发可调用的 SQLite 装载核心及开发测试——把新生成的标准化结果装入新数据库，读取回来逐行对照，再用 SQL 独立勾稽数量与金额。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-005_DRAFT.md`、`docs/reviews/REVIEW_TASK_004_R1.md`、`docs/NORMALIZATION_GUIDE.md`、`docs/SPEC_V1.md` 第 2—4 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2、3 节。
状态：本卡范围内工作完成并自检通过，**停止于此**；未做 R01—R04 筛查，未建立契约或审批控制，未推进任务六。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 公共 API | `load_normalized_to_sqlite(normalized: dict, database_path) -> dict`；只提供 Python API，**无面向业务批次的 CLI**，不重跑标准化、不写回 Excel、不代签批准 |
| 异常语义 | `SqliteLoadBlocked`（前提不成立或路径在写入前被拒绝）与 `SqliteLoadError`（文件／数据库约束／一致性错误，保留阶段、路径与原始异常）分开 |
| 数据库结构 | 六张表：`suppliers`／`payables`／`payments`／`allocations` + `source_records` + `run_metadata`；金额只用整数分；`allocations.ap_id` 允许 NULL 与台账外文本且**不设外键** |
| 约束 | 业务主键 TEXT 且 NOT NULL；日期／枚举／币种 CHECK；金额 `typeof='integer'` 且 >0；已结算 `bank_reference` 部分唯一索引；`(payment_id, ap_id)` 与 `(payment_id)` 两条部分唯一索引覆盖未指定对象的分摊；自关联 `DEFERRABLE INITIALLY DEFERRED`；装载前 `PRAGMA foreign_keys` 实测为 1 |
| 事务与失败现场 | 先建空 schema，再单事务写入业务表／来源记录／运行元数据；暂存库 + 成功后更名；失败回滚并保留暂存库（零业务行、零来源、零元数据） |
| SQL 勾稽与往返 | 行数与来源覆盖、三表 SQL 合计、付款分组双向比较、逐笔分摊、已结算 PAY／REFUND、净额三项与缺失分类、`foreign_key_check`／`integrity_check`、以及按原 Excel 行号重建 `data`／`source`／`cells` 的逐项精确相等 |
| 开发验证 | **33 个案例全部符合预期，测试失败 0**：入库成功 **18**、质量阻断 **8**、装载阻断／路径拒绝 **4**、运行失败 **3**；真实 checker CLI 调用 **26** 次；测试进程退出 **0** |
| 环境 | Python **3.11.1**、SQLite **3.39.4**（标准库 `sqlite3`，未安装依赖） |
| 冻结文件 | 标准化器 `a2bae49e…`、checker `a7e5eb67…`、接收器 `52195620…`、生成器 `e899aa2f…`、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| 既有文件保护 | TASK-004-R1 验收基线 **6511 个文件**：**0 个变化、0 个缺失**；TASK-004 基线 5819 个中变化的 3 个正是当时授权的标准化文件；R3 基线 4902 个、任务二基线 874 个：0 个变化 |
| 未执行 | R01—R04 筛查、AI 建议、判断表、正式契约、批准命令、状态机、真实 ERP 接入；未安装依赖、未初始化 Git |

---

## 2. 实际新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py` | `1aae12e3c3b3c8dc661e2467aaf793668678104efab1f78b82db6d065c855407` |
| `D:\harness work\audit_sa_project\sql\demo_schema.sql` | `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205` |
| `D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py` | `7fc33bb81db41e147e20d3ac4264e595eb56fe79eb66a1264c72ff61486c293e` |
| `D:\harness work\audit_sa_project\docs\SQLITE_LOAD_GUIDE.md` | `f5f266fa858e0b90527fb27cbc94d55b41a191415f157c2a03ffbde8bbc04aed` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_005.md` | 本文件 |

新增测试容器（`data\sqlite_tests\`）：`task005_05`（**最终**，173 个文件）、`task005_04`（全部通过但统计漏计两个路径用例）、`task005_03`（P2 断言过窄，1 处失败）、`task005_02`（P2 未入库导致后续路径用例崩溃）、`task005_smoke_01`（首次冒烟 `KeyError`）、`task005_smoke_02`（成功冒烟）。全部按“不覆盖历史”保留。

未修改、未删除任何既有文件；未向旧容器补文件。

---

## 3. 公共 API 与实现要点

- **前提检查（写入前）**：版本必须为 `TASK-004-normalized-1.1`、`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`、`quality_report.result="pass"`、`normalized_equals_report` 与全部 `checks` 为真；四表 `records` 存在且 `row_accounting.normalized_rows` 与记录数一致（缺项不等于空表）；每条 `data` 字段集合与本版固定字段完全一致，必填文本为 `str`、可空字段为 `str`/`None`、金额为 `int` 且非 `bool` 严格为正、日期为 ISO 日期；`source.workbook_sha256` 等于本结果来源哈希；`cells` 覆盖固定输入字段且 `target_field`／`standard_value` 与 `data` 对应。违规抛 `SqliteLoadBlocked` 并给出字段路径。
- **路径边界**：`resolve_database_path()` 解析绝对路径后核对范围、拒绝目录本身与已存在目标，全部在写入前完成。
- **写入**：`connect_database()` 打开连接并置 `PRAGMA foreign_keys=ON`（实测必须为 1）；`execute_schema()` 建空 schema；随后显式 `BEGIN`，业务表、`source_records`、`run_metadata` 在同一事务内参数绑定写入；`COMMIT` 后进行独立核对；通过后 `os.replace` 暂存库到目标并记录最终字节哈希。
- **失败**：任何异常回滚数据事务、关闭连接，保留暂存库；异常链保留原始类型与消息。
- **可注入接缝**：`read_file_bytes()`、`connect_database()`、`execute_schema()`、`insert_business_rows()`、`insert_source_records()`、`insert_run_metadata()`，用于在内存或新测试库中模拟故障，不修改真实源码。

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

### 4.2 冒烟（主文件 → 标准化 → 入库）

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_smoke_02\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_smoke_02\checker_report.json'
```

随后在内存中调用标准化 API 与 `load_normalized_to_sqlite(normalized, 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_smoke_02\demo.sqlite')`；checker 退出 **0**，装载返回 `DEV_SQLITE_VERIFIED`，四表 20/993/1000/1005，净额 267 249 329 分，往返精确。

### 4.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_05'
```

退出码 **0**；输出“案例 33 个：入库成功 18、质量阻断 8、装载阻断 4、运行失败 3；checker CLI 调用 26 次；测试失败 0”“受保护文件前后哈希一致: True（34 个）”。
命令与日志位置：`data\sqlite_tests\task005_05\command_log.json`（逐次 checker 调用的完整 `argv`、退出码与独立 stdout／stderr 路径）、`summary.json`（统计、逐案结果、保护核对）。

### 4.4 其他核验

```powershell
& $py -c "import sys, sqlite3; from importlib.metadata import version; print(sys.version.split()[0], sqlite3.sqlite_version); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\sql\demo_schema.sql' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\SQLITE_LOAD_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与计数核对；未新增 `.py` 文件。

---

## 5. 实际结果与具体断言

### 5.1 统计（从实际结果计算）

| 项目 | 数量 |
| --- | --- |
| 案例总数 | **33** |
| 入库成功（`DEV_SQLITE_VERIFIED`） | **18** |
| 质量阻断（上游标准化阶段即阻断，不建库） | **8** |
| 装载阻断／路径拒绝 | **4**（金额字符串、bool 金额、同一路径二次装载、越界路径） |
| 运行失败（数据库约束／事务故障） | **3**（重复主键、缺失强制资金关联、事务中途故障） |
| 预期负向合计 | **15** |
| 真实 checker CLI 调用 | **26** |
| 测试失败 | **0** |

### 5.2 主演示文件（数据库实测）

| 断言 | 实测 |
| --- | --- |
| 四表行数 | 20 / 993 / 1000 / 1005 |
| 来源记录 | 与业务行一一对应（20 / 993 / 1000 / 1005），无孤立行 |
| SQL 金额合计 | payables 267 849 329、payments 270 149 329、allocations 270 149 329 分，三项与标准化逐项相等 |
| 付款分组（双向比较） | `PAY/SETTLED` 995 笔 267 949 329、`PAY/PENDING` 1 笔 500 000、`PAY/FAILED` 1 笔 500 000、`PAY/VOIDED` 1 笔 500 000、`REFUND/SETTLED` 2 笔 700 000 分（非结算组未漏） |
| 净额 | 主表净额 **267 249 329** = 已知关联 **266 249 329** + 缺失关联 **1 000 000** 分，`net_checks` 全真 |
| 往返 | 按原 Excel 行号重建 `data`／`source`／`cells`，逐项精确相等（`round_trip_exact=true`） |
| PRAGMA | `foreign_key_check` 无问题、`integrity_check` = `ok` |
| 元数据 | `mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`、`batch_status=DEV_SQLITE_VERIFIED`；库文件 8 650 752 字节，报告内哈希与磁盘一致 |

### 5.3 定点结果（全部从数据库查回）

| 案例 | 断言与实测 |
| --- | --- |
| C03 | 主表净额 **1 000 000** 分、分摊 SQL 合计 **1 000 000** 分（未因两条分摊翻倍成 2 000 000） |
| C07 | `allocations.ap_id` 为 **NULL**；缺失净额 500 000 分且全部来自空 `ap_id` |
| C07b | 一条 `AP01`（300 000 分）+ 一条 NULL（200 000 分）；已知 300 000、缺失 200 000 |
| C08 | `ap_id = "AP_MISSING"`；缺失净额来自台账未找到 500 000 分 |
| C09 | 同一查询取回 `payee_supplier_id=S002` 与 `supplier_id=S001`（收款对象差异保留） |
| C06 / C06b | `R01` 行为 `REFUND` 且 `original_payment_id=P02`；`AR01` 的 `original_allocation_id=A02`；退款金额分别为 500 000 / 100 000 分（正数） |
| C10 | 三种非结算状态 `PENDING`／`FAILED`／`VOIDED` 入库；已结算总额 0 |
| C10b | 非结算退款 `PENDING` 且 `bank_reference` 为 NULL；不计入资金净额（净额 1 000 000） |
| P1_no_funds | 无付款／分摊仍入库；资金净额 0；应付 500 000 分保留 |
| P2_identifier_fidelity | 前导零 `"0009"`、单引号 `"S'01"`、首尾空格 `" O'Brien "` 与 `" B 001 "` 原样入库；外键连接完整；来源坐标 `("payables", 2)` 保留 |
| P3_refund_before_original | 退款行在 Excel 中位于原记录之前仍入库成功；自关联引用完整（依赖可延迟自关联，不依赖行顺序） |
| I1 / I2 | 金额字符串／bool → `SqliteLoadBlocked`（不静默转换），未建库 |
| I3 | 重复业务主键 → 数据库约束报错（阶段 `insert_business_rows:suppliers`）→ `SqliteLoadError`，未产生目标库，暂存失败现场保留 |
| I4 | 分摊指向不存在的付款 → 外键阻止（阶段 `insert_business_rows:allocations`）→ `SqliteLoadError` |
| I5 | 来源记录写入阶段故障 → `SqliteLoadError`，回滚后暂存库六张表**行数全为 0**，无半批业务、来源或元数据 |
| N1 / N2 | 同一路径二次装载与越界路径均在写入前拒绝；原库字节哈希未变，越界目标未创建 |

## 6. 保护结果

- 受保护文件 **34 个**（冻结 checker、接收器、生成器、标准化器、装载脚本、schema、规格、契约草案、上游回执与说明、标准化测试、主演示输入与 22 份 fixture）在测试前后哈希全部一致。
- 基线复核：**TASK-004-R1 验收基线 6511 个 → 0 个变化、0 个缺失**；TASK-004 验收基线 5819 个中变化的 3 个正是 TASK-004-R1 卡当时授权的标准化文件；**R3 验收基线 4902 个 → 0 个变化**；**任务二 R2 基线 874 个 → 0 个变化**。
- 冻结版本实测：标准化器 `a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310`、checker `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8`、接收器 `5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6`、生成器 `e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`、规格 `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236`、契约草案 `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27`。
- 依赖未变（Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未执行 `pip install`；Git 未初始化；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 7. 失败尝试与修复过程

1. **首次冒烟 `KeyError: 'suppliers'`**：`AMOUNT_FIELDS`／`DATE_FIELDS` 缺少 `suppliers`／`allocations` 键，类型检查在供应商表上取字典失败 → 补上显式空元组后通过（现场 `task005_smoke_01`）。
2. **测试脚本语法错误**：C03 断言的多行 lambda 赋值续行非法，`py_compile` 报 `SyntaxError` → 改为括号包住的单行表达式（该次未创建容器）。
3. **P2 标识保真副本被上游正确拦下**：修改供应商 ID 时漏改 `payments.payee_supplier_id`，真实 checker 报 `FOREIGN_KEY_MISSING`（退出 1）、标准化阶段阻断、装载层按约定拒绝（**未静默入库**）→ 补齐该字段后通过。这条失败同时证明上游质量与装载前提没有被放宽。
4. **P2 断言过窄**：C01 实际有两位供应商（`S'01` 与 `S002`），我最初断言只有一条 → 改为按集合比较。
5. **路径拒绝用例崩溃**：`same_path_case.db_path = p2.db()` 在 P2 尚未成功入库时触发断言错误 → 路径用例改用已成功入库的 MAIN 案例（现场 `task005_02`）。
6. **统计漏计**：N1／N2 两个路径拒绝用例最初未加入案例列表，导致汇总只报 31 个案例 → 加入后汇总为 33，并显式给出“质量阻断／装载阻断／运行失败”拆分。
7. 全程未修改上游源码、原数据、既有批次或旧回执；所有故障只在内存副本或新测试库中注入。

## 8. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：R01—R04 筛查、AI 审计建议、判断表、正式契约、批准命令、业务状态机、RAG、OCR、百万行压测、真实 ERP 接入。
- 已知限制：装载前提只检查本层消费的标准数据契约，不等同于完整 ERP 质量校验；`PRAGMA foreign_key_check`／`integrity_check` **不是审计结论检查**；入库通过**不表示没有业务线索**；`allocations.ap_id` 的空值与台账外文本按原值保留，不构成应付关联已完整的声明；本地哈希不证明来源真实性，也不抵御同权限篡改；主表资金总额与分摊总额分别计算、**不相加**。
- 本卡范围内工作已停止：未接入 `data/batches`、未修改任何旧 `batch_manifest.json`、未建立契约或批准指纹控制、**未宣称已实现 Gate 1／Gate 2 放行**，也未开始任何规则筛查。
- 等待主理人把本回执与 `docs\SQLITE_LOAD_GUIDE.md`、`data\sqlite_tests\task005_05` 转交总架构师验收。
