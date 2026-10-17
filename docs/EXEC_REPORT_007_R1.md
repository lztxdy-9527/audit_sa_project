# TASK-007-R1 执行回执（修复误报一致与差异诊断）

任务：修复 TASK-007 验收发现的四项缺口——F01 比较未统一保留金额类型、F02 退款摘要重复与 finding 规则身份未被发现、F03 分项状态与差异诊断不能准确表达问题、F04 质量前提的“无问题”条件未核对。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-007-R1.md`、`docs/reviews/REVIEW_TASK_007.md`、`docs/tasks/TASK-007_DRAFT.md`、`docs/RULE_CROSSCHECK_GUIDE.md`、`docs/EXEC_REPORT_007.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务八，未接入 `data/batches`，未批准任何 Gate，未生成 AI 判断或人类判断预填值。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧 `docs/EXEC_REPORT_007.md` 保持原字节，未回写。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **F01 类型被数值等价吞掉** | 比较层改为**严格类型比较**（`type(expected) is type(actual)` 且值相等），声明为整数分的字段等值 `float`／`bool` 一律判不一致；覆盖 `amounts_cents` 标量与 R01 `net_per_payment`、退款摘要金额、`statistics` 资金金额、`overall_reconciliation` 金额与明细；计数、原 Excel 行号与 `counted_in_net` 按各自类型比较；字符串 ID 不做 `str()` 转换。每条差异附 `expected_type`／`actual_type` |
| **F02 退款多重性与规则身份** | 退款摘要先核对元素结构与必需键、再按 `refund_allocation_id` 检查**多重性**：重复报新增代码 `REFUND_FACT_DUPLICATE`（记录 ID 与实际次数），不过滤非法元素、不静默覆盖；外层 `rule_id` 与 `hit_key.rule_id` 及复算规则不一致时报新增代码 `RULE_ID_MISMATCH` |
| **F03 状态与诊断** | `comparison.checks`（原先恒为 true）替换为 `comparison.dimensions.<维度> = {executed, matched, difference_count}`（固定十个维度），整体 `matched` 仅在**全部维度一致且差异为空**时为 true；差异新增 `expected_present`／`actual_present` 与类型元数据，**缺失（present=false）、显式 `null`（present=true, type=null）、`0`** 可区分；`cells` 差异改为**逐叶路径 + 真实预期／实际值**；差异稳定排序、完整保存不截断 |
| **F04 质量前提自相矛盾** | 前提核对新增：`quality_report.issue_counts_by_code` 必须**存在、为对象且为空**；缺失／非对象／含问题计数均 `CrossCheckBlocked`（原因指向质量前提） |
| 版本 | 复核核心版本升为 `TASK-007-crosscheck-1.1`；规则公式、上游筛查核心、四份规则 SQL、装载／标准化／checker、规格与答案册**均未改动** |
| 开发验证 | **29 个工作簿输入，测试失败 0，退出 0**：初次一致 **21**、上游阻断 **8**、初次不一致 0、前提阻断 0、意外运行错误 0；checker CLI **29** 次、SQL 核心 **21** 次、复核调用 **50** 次；**20 项**差异检查全部命中指定代码、**6 项**前提阻断全部阻断 |
| 历史保护 | TASK-007 验收扩充基线（10990 项）**变化 3、缺失 0**，恰为本卡授权三个文件；任务六 R1 的 **10236**（要求全部不变）、任务五 R2 的 8547、任务四 R1 的 6511、任务三 R3 的 4902、任务二 R2 的 874 基线均 0 变化 |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py` | `1f088312155699d611428a87595cb82a653d2b948f3e3f0843dd8f41edef6cf5` |
| `D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py` | `bf0ce9c1bfd155b49f6de3808ac6f5705b16896a084e53e84e89f06182795808` |
| `D:\harness work\audit_sa_project\docs\RULE_CROSSCHECK_GUIDE.md` | `e270e17c04a7cfb1c0187d32b0a98481f0c67353e33aa318c947a02f09406fa2` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_007_R1.md` | 本文件（新增） |

**未改动**（保持原字节）：`docs/EXEC_REPORT_007.md`（旧回执）、`scripts/screen_demo_sqlite.py`（`1b123766…`）、`sql/rules/r01.sql`—`r04.sql`（`7a19ff2f…`／`58af03e6…`／`8a4b84d9…`／`b60e4db0…`）、`scripts/store_demo_sqlite.py`（`1abfad89…`）、`sql/demo_schema.sql`（`7e0c6463…`）、`scripts/normalize_demo_data.py`（`a2bae49e…`）、`scripts/check_demo_data.py`（`a7e5eb67…`）、`docs/SPEC_V1.md`（`5df632ed…`）、答案册与全部 GPT 验收证据。

新增测试容器（`data\sqlite_tests\`）：`task007_r1_01`（**最终**，271 个文件）、`task007_r1_smoke_01`（四项修复冒烟）。旧容器 `task007_02` 等全部保留，未覆盖。

## 3. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 3.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py'
```

退出码均 **0**。

### 3.2 四项修复冒烟

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r1_smoke_01\MAIN\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r1_smoke_01\MAIN\checker_report.json'
```

随后在内存中调用标准化、装载、SQL 筛查与复核 API：正常主文件 `DEV_CROSSCHECK_MATCHED` 且十个维度全部 matched；等值 float 金额 → `AMOUNT_MISMATCH`（type int/float）；bool 统计 → `STATISTIC_MISMATCH`；重复退款摘要 → `REFUND_FACT_DUPLICATE`；规则身份冲突 → `RULE_ID_MISMATCH`；缺失与 null 记录可区分；`cells` 差异给出逐叶路径与真实值。

### 3.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r1_01'
```

退出码 **0**；关键输出：

```text
工作簿输入 29 个：初次一致 21、上游阻断 8、初次不一致 0、前提阻断 0、意外运行错误 0
checker CLI 29 次、SQL 核心调用 21 次、复核调用 50 次、预期不一致检查 20 项、前提阻断检查 6 项
[PASS] M1—M11（原 11 项）  [PASS] M12—M20（新增 9 项）
[PASS] M18_vs_M19 缺失与 null 记录可区分（actual_present=False/True、type=None/null）
[PASS] M20 两处不同维度改动均留痕（金额与行号）
[PASS] M7_cells_diagnostics 差异含可定位路径与实际值
[PASS] M4_dimensions 金额维度 matched=False 且其他维度 matched=True
[PASS] P1—P6 前提阻断 outcome=blocked
[PASS] D1_determinism / I1_static_imports / I2_runtime_guard
受保护文件前后哈希一致: True（37 个）
```

命令与日志：`task007_r1_01\command_log.json`（29 次 checker 调用）、`stdout.txt`／`stderr.txt`（本入口自身完整捕获）、`crosscheck_results.json`、`mismatch_checks.json`（**完整差异，不截断**）、`precondition_checks.json`、`isolation_checks.json`、`summary.json`；每个被改错对象与**完整复核报告**另存 `mutations\<name>.json`／`mutations\<name>.report.json`。

### 3.4 其他核验

```powershell
& $py -c "import sys, sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version)"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\RULE_CROSSCHECK_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\EXEC_REPORT_007.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结构化核对；未新增 `.py` 文件（替换比较层时使用的临时片段文件已删除）。

---

## 4. 分类计数

| 项目 | 数量 |
| --- | --- |
| 工作簿输入 | **29**（主文件 + 22 fixture + 6 小样） |
| 初次 MATCHED | **21** |
| 上游阻断（SQL／复核未执行） | **8** |
| 初次 MISMATCH／前提阻断／意外运行错误 | 0 / 0 / 0 |
| checker CLI 调用 | **29** |
| SQL 筛查核心调用 | **21** |
| 独立复核调用 | **50**（29 输入初次 21 + 差异检查 20 + 前提阻断 6 + 确定性 2 + 隔离 1） |
| 差异检查 | **20**（原 11 + 新增 9），全部命中指定代码 |
| 前提阻断检查 | **6**（原 5 + 质量前提 1） |
| 确定性／隔离检查 | **3** |
| 测试失败 | **0** |

## 5. 原回归保持 + 新增回归

### 5.1 原 11 项差异检查与 5 项前提阻断

M1—M11 与 P1—P5 全部保持 PASS（原断言未放宽、未删除）；正常 21 输入的 34 条线索、168 个来源实体与主文件 12 键／R02 超额合计 1 600 000 分不变。

### 5.2 新增 9 项差异检查

| 检查 | 注入 | 期望代码 | 实测 |
| --- | --- | --- | --- |
| M12 | MAIN R02 `overpayment` 改为等值 `float` | `AMOUNT_MISMATCH` | 命中；`expected_type=int`／`actual_type=float`；`amounts_cents.matched=false` 且 `source_entities`／`source_rows` 仍 matched |
| M13 | MAIN R01 `net_per_payment` 一个值改为等值 `float` | `AMOUNT_MISMATCH` | 命中（嵌套字典路径 `amounts_cents.net_per_payment.<id>`） |
| M14 | S6 `statistics.involved_payments.settled_amount_cents` 由 `0` 改为 `False` | `STATISTIC_MISMATCH` | 命中；`statistics.matched=false`，`amounts_cents` 仍 matched |
| M15 | C09b 原样追加一条退款摘要 | `REFUND_FACT_DUPLICATE` | 命中（记录 ID 与出现次数 1→2） |
| M16 | C09b 复制退款摘要并改动其中一份金额 | `REFUND_FACT_DUPLICATE` | 命中（不依赖“字典最后一条”） |
| M17 | MAIN 一条 R01 finding 外层 `rule_id` 改为 `R04` | `RULE_ID_MISMATCH` | 命中；`rule_identity.matched=false` |
| M18 | 删除一个 R02 `overpayment` 字段 | `AMOUNT_MISMATCH` | 命中；`actual_present=false`、`actual_type=null` |
| M19 | 将同一字段设为 `null` | `AMOUNT_MISMATCH` | 命中；`actual_present=true`、`actual_type=null`；与 M18 差异记录**不相同** |
| M20 | 同一报告同时改动金额与来源行号 | `AMOUNT_MISMATCH` + `SOURCE_ROW_MISMATCH` | 两处均留痕，`amounts_cents` 与 `source_rows` 两个维度均 `matched=false` |

### 5.3 新增质量前提检查

| 检查 | 注入 | 实测 |
| --- | --- | --- |
| P6 | `normalized.quality_report.result` 保持 `pass`，`issue_counts_by_code` 改为 `{"FOREIGN_KEY_MISSING": 1}`，并**同步** `load_source` 与 `run_metadata` 的 `normalized_payload_sha256` 为新指纹 | `CrossCheckBlocked`，原因指向 `normalized.quality_report.issue_counts_by_code`（“质量通过必须无未解决问题”） |

指纹同步只作用于内存测试对象（另存 `mutations\P6_quality_issue_counts.normalized.json`／`.report.json`），未修改任何真实文件，也不声称防恶意篡改。

### 5.4 分项状态与诊断可用性

- `comparison.dimensions` 固定十个维度，每项 `{executed: true, matched: bool, difference_count: N}`；M4 实测金额维度 `matched=false`、`difference_count≥1`，`source_entities`／`source_rows`／`counts`／`overall_reconciliation` 仍 `matched=true`——不再出现“金额差异但金额检查通过”。
- `M7_cells_diagnostics`：`cells.raw_value` 改动后差异路径为 `evidence.entities[payables:AP01].cells.ap_date.raw_value`，`expected` 为原值、`actual` 为改后值（不再是“完整 cells／与标准化记录不一致”这类替代提示）。
- 每条差异含 `code`／`hit_key`／`field_path`／`expected`／`expected_present`／`expected_type`／`actual`／`actual_present`／`actual_type`，稳定排序并完整保存（`differences_truncated=false`）。

### 5.5 确定性与隔离（保持）

复调用返回对象精确相等；两次入参规范指纹不变；测试数据库字节不变；核心静态无数据库／上游核心／答案册引用；运行期守卫下核心成功且受限路径读取 0，守卫以受控探测确认生效并全部恢复；答案册仍在**全部 21 份初次结果保存之后**才读取。

## 6. 历史保护对照

- TASK-007 验收扩充基线（`data/reviews/task007_20261011_074219/source_hashes_after.json`）：记录项 **10990**、变化 **3**（`scripts\crosscheck_demo_rules.py`、`tests\test_crosscheck_demo_rules.py`、`docs\RULE_CROSSCHECK_GUIDE.md`，恰为本卡授权文件）、缺失 **0**。
- 任务六 R1 的 **10236** 文件冻结基线：**0 变化、0 缺失**（本卡要求全部不变）；任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 0 变化、0 缺失。
- GPT 验收证据目录保持原字节（其内部哈希在基线中逐文件核对）。
- 测试内建核验的 **37 个受保护文件**（冻结脚本、schema、四份规则 SQL、规格、契约草案、上游回执与说明、筛查测试、主演示输入与 22 份 fixture）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 7. 失败尝试与修正过程

1. **比较层整体替换的接口对齐**：以脚本替换旧比较段落后，`compare_facts` 的返回值由“差异列表”变为“差异 + 维度状态”，`verify_rule_facts` 需同步改造；编译检查通过后以冒烟脚本逐项验证四个缺口，未出现失败运行。
2. **维度拆分的设计修正**：为使“只改 `source_rows` 行号”不再同时命中实体维度，把来源比较拆为 `source_entities` 与 `source_rows` 两个维度，M11 与 M6／M7 因此各自映射到准确维度。
3. **前提核对顺序**：把 `issue_counts_by_code` 检查放在对象指纹检查**之前**，使 P6 在同步指纹后仍由质量前提阻断（而不是被指纹差异提前拦下）。
4. **缺失与 null 的区分**：最初仅在 `actual` 处留 `None`，两份差异无法区分；改为 `present` + `type` 元数据后 M18／M19 记录可分辨（实测 `actual_present` False/True、类型 None/null）。
5. **替换比较层使用的临时片段文件**：写在项目外（会话工作区）并在替换后立即删除，项目目录未残留临时文件。
6. 未通过放宽断言、删除 `related_refunds`、取消证据要求或修改答案册让测试过关；未导入 GPT 的 QA 脚本到生产核心。

## 8. 偏差、未解决问题与停止状态

- **偏差**：新增两个差异代码 `REFUND_FACT_DUPLICATE` 与 `RULE_ID_MISMATCH`（卡允许新增并需同步说明，已在说明第 3.3 节固定）；原 `comparison.checks` 被 `comparison.dimensions` 取代（已在说明第 4 节固定其含义）。
- **未执行（不主张通过）**：任务八、正式事实底稿展示、正式契约、批准控制、Gate 放行、人类判断保存、后置 AI 建议、真实 ERP 接入、OCR、RAG、UI、压力测试；未重跑任务二至六整套测试（新链路调用其冻结 API 并核对哈希）。
- **已知限制**：本层只比较**报告内部声明与绑定**，不实际读取或重验数据库字节；只核对本输入下标准化记录与报告证据是否一致，**不证明来源真实性**，不声称抵御同权限篡改；复核一致**不构成审计结论**，也不替代人类独立判断；不补零、不修复输入、不回写报告。
- **停止状态**：未接入 `data/batches`、未修改旧 `batch_manifest.json`、未建立契约或批准控制、未批准 Gate、未生成 AI 建议、未替人类填写判断、未推进任务八。
- 等待主理人把本回执与 `docs\RULE_CROSSCHECK_GUIDE.md`、`data\sqlite_tests\task007_r1_01` 转交总架构师复验。
