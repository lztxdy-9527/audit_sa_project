# TASK-005-R2 执行回执（只修正常关闭异常被吞掉）

任务：修复 TASK-005-R1 复验发现的唯一阻断项——正常流程关闭数据库时的异常被吞掉，随后仍发布数据库并返回成功。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-005-R2.md`、`docs/reviews/REVIEW_TASK_005_R1.md`、`docs/tasks/TASK-005-R1.md`、`docs/tasks/TASK-005_DRAFT.md` 第 6 节。
状态：本卡范围内工作完成并自检通过，**停止于此**；未做 R01—R04 筛查，未建立契约或审批控制，未推进任务六。

> 命令均为完整参数、不使用省略号；未执行的验证一律写明“未执行”。旧回执未回写。

---

## 1. 结论摘要

| 项目 | 修订结果 |
| --- | --- |
| **唯一修复点** | `_cleanup()` 拆成两个函数：**正常路径 `_close_strict()`** 关闭必须成功，失败即按 `阶段=close_database` 抛 `SqliteLoadError`，**不继续哈希暂存库、不调用发布、不返回成功报告**；**错误后 `_close_quietly()`** 只作尽力清理，关闭再失败仅作附记，不覆盖最初错误，也不丢弃仍需清理的连接引用 |
| 关闭失败的如实说明 | 关闭失败发生在 COMMIT 之后：错误信息含 `阶段=close_database`、目标与暂存路径、原始异常链，并说明 `数据事务已提交=True`、`目标文件已发布=False`、暂存库六表**实测**行数（本次 C01 为 2/1/1/1/5/17）、目标文件是否存在；**不假报回滚或六表零行** |
| 恢复成功被禁止 | 正常关闭报错后，即便错误清理再次尝试关闭并成功，本次调用**不会**恢复成发布成功——异常在发布之前抛出 |
| 注释口径 | `SqliteLoadError` 类注释不再笼统称“数据事务已回滚”，改为按失败时点（提交前／提交后）解释 |
| 开发验证 | **41 个案例全部符合预期，测试失败 0**：入库成功 **18**、质量阻断 **8**、装载阻断 **6**、运行失败 **9**；真实 checker CLI **26** 次；测试进程退出 **0**（原 39 例全部保留并重跑通过） |
| 版本 | 装载实现版本提升为 `TASK-005-sqlite-load-1.2`；**schema 版本与文件保持 `demo-schema-1.0`／原字节**；公共 API 不变 |
| 上游冻结 | 标准化器 `a2bae49e…`、checker `a7e5eb67…`、接收器 `52195620…`、生成器 `e899aa2f…`、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| 历史保护 | TASK-005-R1 验收基线 **8101 个文件**：**3 个变化（恰为本卡授权文件）、0 个缺失**；TASK-004-R1 基线 6511 个、TASK-003-R3 基线 4902 个、任务二基线 874 个：均 0 个变化；schema 原字节未变 |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py` | `1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446` |
| `D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py` | `5c057ff65243977af84c6c8aad602a8e11d494019ef57b897647e23b6fb92557` |
| `D:\harness work\audit_sa_project\docs\SQLITE_LOAD_GUIDE.md` | `93bf2c821a00aff8d23a4e98c78f541e7688579bb73107ca3e4cd620542695c2` |
| `D:\harness work\audit_sa_project\sql\demo_schema.sql` | `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205`（**未变**） |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_005_R2.md` | 本文件（新增） |

新增测试容器（`data\sqlite_tests\`）：`task005_r2_01`（**最终**，196 个文件）、`task005_r2_smoke_01`（关闭失败的两次单点冒烟）。上一轮的 `task005_r1_02` 等历史容器全部保留，未覆盖。

---

## 3. 关闭错误处理方式

```text
… → COMMIT（committed=True）
    → _close_strict()          # 正常路径：关闭必须成功
         成功 → connection = None → 继续 hash_staging / publish / final_hash
         失败 → raise SqliteLoadError(阶段=close_database, 目标与暂存路径, 原始异常链)
                （不外抛即中止：不哈希暂存库、不发布、不返回成功）
    except 任意 SqliteLoadError/SqliteLoadBlocked 或未预期异常：
         → _close_quietly()    # 错误后尽力清理，仅把关闭失败记为附记
         → 追加 _state_notes()：阶段、目标／暂存路径、是否已提交、是否已发布、
           暂存库六表实测行数、目标文件是否存在、回滚异常、清理附记
```

要点：

- **严格关闭**捕获任何关闭异常（含 `sqlite3.OperationalError`）并立即转为 `SqliteLoadError`，因此发布函数不会被调用；正常路径的关闭失败不会被后续清理“抹平”。
- **尽力清理**在关闭失败时**保留连接引用**（不丢弃仍需清理的连接），只把失败写入附记；附记随 `reasons` 输出，主错误类型与主要差异保持不变。
- 关闭失败发生在提交之后，因此错误说明如实写“提交为真、发布为假”，并给出暂存库的**实际**行数；正常成功路径不受影响（关闭成功后暂存文件在发布时被删除）。

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

### 4.2 关闭错误的单点冒烟

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r2_smoke_01\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r2_smoke_01\report.json'
```

随后在内存中调用标准化 API 与 `load_normalized_to_sqlite()`：正常路径返回 `DEV_SQLITE_VERIFIED`（元数据 17 行、暂存文件已清理）；关闭注入路径抛 `SqliteLoadError`（含 `close_database` 与 `OperationalError`），发布调用 0 次、目标不存在、暂存库保留 2/1/1/1/5/17 行；核对失败叠加清理关闭失败时主错误仍为核对差异、关闭失败仅为附记。checker 退出 **0**。

### 4.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task005_r2_01'
```

退出码 **0**；输出“案例 41 个：入库成功 18、质量阻断 8、装载阻断 6、运行失败 9；checker CLI 调用 26 次；测试失败 0”“受保护文件前后哈希一致: True（34 个）”。
命令与日志：`data\sqlite_tests\task005_r2_01\command_log.json`（26 次 checker 调用的完整 `argv`、退出码、独立 stdout／stderr 路径）、`summary.json`（统计、逐案结果、保护核对）；注入案例目录内含 `injected_normalized.json` 与 `injection_note.txt`。

### 4.4 其他核验

```powershell
& $py -c "import sys, sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version)"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\sql\demo_schema.sql' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_store_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\SQLITE_LOAD_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对、发布调用计数与六表行数核验；未新增 `.py` 文件。

---

## 5. 本卡两项定点回归的实际结果

### A. 正常关闭报错不得发布（`R2A_close_failure_blocks_publish`）

注入：对本轮新 C01 标准化结果，包装 `connect_database` 返回代理连接；其余操作委托真实连接，`close()` **先释放真实句柄**再抛一次 `sqlite3.OperationalError("注入：正常关闭时抛出 sqlite3.OperationalError")`（隔离“关闭错误被吞掉”与 Windows 文件占用）。发布函数另加计数包装以证明未继续发布。注入只在内存中完成，未改真实源码。

| 断言 | 实测 |
| --- | --- |
| 抛 `SqliteLoadError` 且含 `close_database` 阶段 | 成立 |
| 含原始 `OperationalError` 及其消息 | 成立（`原始异常=OperationalError: 注入：正常关闭时抛出 sqlite3.OperationalError`） |
| 保留目标与暂存路径 | 成立（`目标路径=`／`暂存路径=` 均为本案例绝对路径） |
| 不调用发布函数 | **发布调用次数 = 0** |
| 目标文件不存在 | 成立 |
| 无成功报告 | 成立（`load_report is None`） |
| 如实说明提交为真、发布为假 | 成立（`数据事务已提交=True`、`目标文件已发布=False`） |
| 已提交暂存库保留完整行数 | `suppliers=2, payables=1, payments=1, allocations=1, source_records=5, run_metadata=17` |
| 不假报回滚为零行 | 成立（说明为“提交后的失败不声称已回滚”） |

现场：`data\sqlite_tests\task005_r2_01\cases\R2A_close_failure_blocks_publish\`（`injected_normalized.json`、`injection_note.txt`、`demo.sqlite.staging`、`checker_report.json`、日志）。

### B. 原错误后清理关闭再报错不得掩盖原错误（`R2B_cleanup_close_failure_keeps_original_error`）

注入：同样的本机 C01 内存副本把应付预期合计 **+1 分**，触发真实 `verify_database` 差异（提交前失败）；同时 `connect_database` 代理在清理关闭时再抛 SQLite 异常。

| 断言 | 实测 |
| --- | --- |
| 主错误仍是数据库核对失败 | 成立（摘要“数据库独立核对未通过，装载不成立”） |
| 保留 500000 与 500001 差异 | 成立（`payables SQL 合计 500000 分 != 标准化 500001 分`） |
| 关闭失败只作附记 | 成立（`清理时关闭连接失败：OperationalError: …`） |
| 附记未取代主错误 | 成立（`reasons` 中无 `阶段=close_database`，主错误类型未变） |
| 事务未提交且六表全为 0 | 成立（`数据事务已提交=False`；六表实测均为 0） |
| 无目标库、无成功报告 | 成立 |

现场：`data\sqlite_tests\task005_r2_01\cases\R2B_cleanup_close_failure_keeps_original_error\`。

## 6. 原 39 例结果与原统计

原 39 例（含主文件、14 份 fixture、8 份质量阻断、三个小正例、路径拒绝、五类内存注入、事务中途故障、R1 六项定点回归）**全部保留并重跑通过**，断言未放宽：主文件四表仍为 20／993／1000／1005 行，净额 267 249 329 分 = 已知 266 249 329 + 缺失 1 000 000 分；C03 净额仍为 1 000 000 分；18 个正常库往返逐项精确相等。

| 项目 | 数量 |
| --- | --- |
| 案例总数 | **41**（原 39 + R2 新增 2） |
| 入库成功 | **18** |
| 质量阻断 | **8** |
| 装载阻断 | **6**（金额字符串、bool 金额、入口已存在目标、越界路径、缺来源字段、错误坐标） |
| 运行失败 | **9**（重复主键、缺失资金关联、事务中途失败、Q01 核对失败、Q03 发布冲突、Q04 元数据缺失、Q04b 对象指纹错误、**R2A 关闭失败**、**R2B 原错误叠加清理关闭失败**） |
| 预期负向合计 | **23** |
| 真实 checker CLI 调用 | **26** |
| 测试失败 | **0** |

### 6.1 各失败阶段实际文件与六表状态

| 阶段 | 案例 | 目标文件 | 暂存库六表 | 报告 |
| --- | --- | --- | --- | --- |
| 写入前（前提／路径） | Q02、Q02b、I1、I2、N1、N2 | 不存在（N1 为既有库，字节未变） | 不创建 | 无成功报告 |
| 事务内写入失败 | I3、I4、I5 | 不存在 | 全 0（已回滚） | 无成功报告 |
| 事务内核对失败 | Q01、Q04、Q04b、R2B | 不存在 | 全 0（已回滚） | 无成功报告 |
| **提交后关闭失败** | **R2A** | 不存在 | **完整行数 2/1/1/1/5/17（不假报回滚）** | 无成功报告 |
| 提交后发布失败 | Q03 | 已存在且字节原样保留 | 保留已提交数据 | 无成功报告 |

## 7. 失败尝试与修正过程

1. **构造关闭注入时的一次设计调整**：最初考虑直接替换 `connect_database` 返回的连接对象，但那会连带影响 `PRAGMA`／`execute` 转发；改为“代理转发全部属性 + 仅覆写 `close()`，并先释放真实句柄再抛错”，既隔离 Windows 文件占用，也不改变其他数据库操作。
2. **错误信息中状态行重复**：`_close_strict()` 的 `reasons` 与随后 `_state_notes()` 追加内容一度重复列出提交／发布状态；已把状态行只保留在 `_state_notes()` 统一输出，`reasons` 保留阶段、两条路径与原始异常链。
3. **冒烟阶段的断言位置**：第一版冒烟把“拒绝”判断写在 `str(exc)`（只含摘要）上，显示为失败；实际差异在 `reasons` 中。正式测试统一断言 `reasons`，并保留 `Case.reasons` 采集。
4. 未修改上游代码、规格、契约草案、旧回执与历史测试产物；未向 GPT 旧目录再次运行或追加文件；所有注入只作用于内存接缝与本轮新测试文件。

## 8. 历史保护对照

- GPT 的 TASK-005-R1 验收基线（`data/reviews/task005_r1_20261011_061018/source_hashes_after.json`）**8101 个文件**：变化 **3**（`scripts\store_demo_sqlite.py`、`tests\test_store_demo_sqlite.py`、`docs\SQLITE_LOAD_GUIDE.md`，恰为本卡授权文件）、缺失 **0**。
- TASK-005 验收基线 7506 个中变化的 3 个即上述同一组授权文件（该基线早于 R1）；TASK-004-R1 基线 **6511 个**、TASK-003-R3 基线 **4902 个**、任务二 R2 基线 **874 个**：均 **0 个变化、0 个缺失**。
- `sql/demo_schema.sql` 保持原字节 `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205`；上游冻结哈希见第 1 节。
- 测试内建核验：**34 个受保护文件**（冻结脚本、schema、规格、契约草案、上游说明与回执、标准化测试、主演示输入与 22 份 fixture）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 9. 偏差、未解决问题与停止状态

- **偏差**：`STORE_VERSION` 提升为 `TASK-005-sqlite-load-1.2`（schema 仍为 `demo-schema-1.0`，未改表结构）；未新增测试接缝（复用既有 `connect_database`／`publish_database` 注入点）。
- **未执行（不主张通过）**：R01—R04 筛查、AI 审计建议、判断表、正式契约、批准命令、业务状态机、真实 ERP 接入；未重跑任务二至四的整套测试（按要求只重验冻结哈希与历史文件无变化）；未验证 GPT 已确认的硬链接回退复制路径等三个场景（本轮不要求重写发布实现）。
- **已知限制**：装载前提只覆盖本层消费的标准数据契约；`PRAGMA foreign_key_check`／`integrity_check` **不是审计结论检查**；入库通过**不表示没有业务线索**；本地哈希不证明来源真实性，也不抵御同权限篡改；无覆盖发布只解决本地“不覆盖已有文件”的承诺；提交后各阶段文件状态以实际磁盘为准，不笼统承诺每个阶段都留有暂存文件。
- **停止状态**：未接入 `data/batches`、未修改任何旧 `batch_manifest.json`、未建立契约或批准指纹控制、**未宣称已实现 Gate 1／Gate 2 放行**，未开始规则筛查、未推进任务六。
- 等待主理人把本回执与 `docs\SQLITE_LOAD_GUIDE.md`、`data\sqlite_tests\task005_r2_01` 转交总架构师复验。
