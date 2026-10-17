# TASK-003-R1 执行回执（补齐失败留痕、报告有效性与代码留档一致性）

任务：修复 TASK-003 验收发现的四组问题——A 运行失败未统一归为退出 2 且成功清单写得过早、B JSON 可解析不等于报告结构有效、C 未验证源码留档与执行版本一致、D 来源声明未原样保存。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-003-R1.md`、`docs/reviews/REVIEW_TASK_003.md`、`docs/tasks/TASK-003_DRAFT.md`、`docs/AUDIT_CONTRACT_DRAFT.md`、`docs/SPEC_V1.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务四，未宣布任何业务批次获得批准。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| A 运行失败统一归口 | 阅读／复制／哈希／日志／checker／报告校验／材料渲染与写入的任何运行错误都由入口捕获 → `FAILED_RUNTIME`（退出 **2**）；材料写入失败时不再遗留就绪清单 |
| B 报告结构校验 | 新增对所消费区段的类型／存在性校验；`[]`、`structure` 为数组、缺必需区段、JSON 语法错误、哈希不符、退出码与 `result` 矛盾 → 全部退出 **2**，原报告保留不改写，材料写“核验未完成”，**不出现“0 个问题”** |
| C 代码留档一致性 | `code_snapshot/` 两份副本均与本次执行版本逐字节比对；不等即退出 **2**（清单记录比较结果与被比哈希） |
| D 来源声明保真 | 只用 `strip` 判空，清单 `source_description` 保存**传入原字符串**；29 字符含首尾空格与换行的声明逐字符一致 |
| 集成验证 | **21 个用例全部通过、失败 0**（原 10 例 + 新增 11 例），测试进程退出 **0**；预期负向案例 **18** 个 |
| 调用统计 | 入口实际调用 **21** 次：真实 CLI **11** 次 + 内存模拟 **10** 次；21 次调用各有独立 stdout／stderr（**42** 个日志文件） |
| 最终主演示批次 | `data\batches\dev_receive_003_r1_main_01`：8 项产物齐全，`DEV_GATE1_PACKET_READY`，四表 20/993/1000/1005，缺失关联净额 1 000 000 分，报告结构与代码留档校验均通过 |
| 已冻结源码保护 | checker `a7e5eb67…`、原回归脚本 `555c5ef7…`、生成器 `e899aa2f…`、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| 既有文件保护 | 对 GPT TASK-003 验收记录的 **1308 个文件**重新核对：**3 个变化（全部是本卡授权修改的文件）、0 个缺失** |
| 未执行 | 标准化、SQLite 入库、R01—R04、AI 建议、正式契约、正式人工守门点、真实 ERP 接入；未安装依赖、未初始化 Git |

---

## 2. 实际修改与新增

### 2.1 修改（本卡授权的三个文件）

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\receive_demo_batch.py` | `c5985d74298d8f6bca19cefce567f8ba147c78ed657841ab3784ad65d1b2eb70` |
| `D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py` | `7a2ddf7cfd6bf6198aec76e45bc8ed73ba3f2f2647760514d45a36cae5d96695` |
| `D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md` | `c8e2dff590cbc3bace48c34972a1e68abea1eaa592582609a2f2909c03c01ed6` |

### 2.2 新增

| 路径 | 说明 |
| --- | --- |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_003_R1.md` | 本回执 |
| `D:\harness work\audit_sa_project\data\batches\dev_receive_003_r1_main_01` | **最终 R1 主演示批次**（8 个文件，`DEV_GATE1_PACKET_READY`） |
| `D:\harness work\audit_sa_project\data\batches\task003_r1_tests_02` | **最终 R1 验证容器**（168 个文件：`batches\` 120、`inputs\` 4、`logs\` 42、`summary.json`、`command_log.json`） |
| `D:\harness work\audit_sa_project\data\batches\task003_r1_tests_01` | 第一次 R1 验证运行（1 条断言写错，见第 8 节），按“不覆盖历史”保留 |

未覆盖、未删除任何既有批次或证据：`dev_receive_003_main_01/02`、`task003_tests_01/02`、`task003_gpt_20261010_221610`、`data\reviews\*`、`data\generated\*` 全部原样保留。旧批次由修订前版本的源码生成，其 `code_snapshot` 保存了当时使用的版本。

---

## 3. 四项修复的落点

### A. 运行失败返回 2，并尽可能留下真实失败现场

- 主流程改为 `BatchState` + `execute_batch()` + `finalize()`：接收阶段全部步骤（哈希、建目录、复制、代码留档、checker 调用、报告读取与校验、核验后哈希复核）在入口统一捕获异常；任何异常写入 `failure_reasons` 与 `failure.exceptions`，状态固定为 `FAILED_RUNTIME`、退出 **2**。
- **不再把运行错误落成退出 1**：退出 1 现在只表示 `BLOCKED_QUALITY`（报告结构有效 + checker 退出 1 + 一致性通过）。
- 批次创建后失败时保留现场：不删除、不覆盖、不自动换目录重跑；清单记录失败阶段（`failure.stage`）、异常类型与消息、已产生文件的**真实存在状态**与哈希（`artifact_info()` 现场读取）、以及 checker 是否启动与实际退出码。
- 快照只写了一部分时：`hashes.snapshot_written=false`，`snapshot_matches_source` 为 `true/false/null` 三态之一（不完整时不写成 `true`），候审材料不把它描述为完整快照；快照不可信时跳过 checker 并在日志写明原因，不虚构命令与退出码。
- **材料写入顺序调整**：先渲染并写入 `gate1_packet.md`，最后写 `batch_manifest.json`，且清单从磁盘现况重建。因此材料写入失败时，最终清单是 `FAILED_RUNTIME`，**不会遗留 `DEV_GATE1_PACKET_READY`**；材料第一次写入失败会重试一次（失败态材料），重试仍失败则记录 `failure.material_write_failures`。
- 连清单都无法写入时：退出 **2**，并在 stderr 打印失败原因、无法保存的文件名与现场目录，不假装保存成功。

### B. 校验报告结构，缺失信息不得补成零问题

- 新增 `validate_report()`，只核验本入口消费的区段与类型，不复制 checker 业务规则：
  - 顶层必须是对象；`result ∈ {pass, issues_found}`；`workbook.sha256`、`checker.sha256` 为非空字符串；
  - `structure`（含 `sheets_found` 数组、`sheet_field_mapping` 两层对象、列号为整数或 `null`）；
  - `row_accounting`（四个行数字段为整数，布尔不算整数）；
  - `issues`（数组，条目含 `code/sheet/excel_row/column/value/detail`）；
  - `issue_counts_by_code`（值为整数）；`amount_summary`（含 `known_valid_subtotals_cents`、`complete_totals_cents`、`unusable_amount_cells.total/by_reason/sources`，金额值为**整数或 `null`**）；`reconciliation`（`status ∈ {ASSESSED, NOT_ASSESSED}`、比较字段为布尔或 `null`、`diagnostic_known_valid_subtotals_cents` 为对象）。
- 结构无效、JSON 语法错误、报告缺失、哈希不符、退出码与 `result` 矛盾 → `FAILED_RUNTIME`/退出 2；**原报告文件原样保留**（不改写、不重存、不补造），清单的 `report_validation` 记录 `attempted/valid/problems/report_readable`。
- 结构无效时 `state.report` 保持 `None`，材料走“核验未完成”分支：不显示问题数、不显示金额、不出现“未记录数据质量或范围问题”。**合法的 `null` 金额继续接受**；结构正确的质量阻断报告（如 C14a 缺列、C14c 金额不可解析）仍按 `BLOCKED_QUALITY` 处理，不会被误判为运行失败。

### C. 验证两份源码留档与实际执行版本相等

- 复制留档后立即比对：`code_snapshot/receive_demo_batch.py` 与入口执行版本、`code_snapshot/check_demo_data.py` 与 checker 执行版本，副本缺失、不可读或不相等均退出 2；执行期源码稳定性检查保留（`stable_during_run`）。
- 清单 `code_snapshot.<文件名>` 记录 `exists / sha256 / expected_sha256 / matches_source`，可追踪比较结果。
- 核验仍使用**原 checker CLI**（真实 checker 文件本身未被替换或被指向答案册）。本项是留档一致性检查，不宣称抵御同权限恶意篡改。

### D. 原样保存来源声明

- `--source-description` 只在**判空**时使用 `strip()`；清单 `source.source_description` 保存传入原字符串，并在清单中注明该处理方式。
- 候审材料展示时对 `|` 与换行做转义（`display_escape`），这是展示处理；清单仍存原声明。来源描述依旧是未经验证的声明。

---

## 4. 完整执行命令与实际退出码

```powershell
$py   = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$recv = 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py'
$tst  = 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py'
```

### 4.1 语法检查

```powershell
& $py -m py_compile 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py'
& $py -m py_compile 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py'
```

退出码均 **0**。

### 4.2 最终主演示批次（修订后接收器）

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' --out-dir 'D:\harness work\audit_sa_project\data\batches\dev_receive_003_r1_main_01' --source-description 'TASK-003-R1 开发验收：现有合成 ERP 导出演示文件，来源描述尚不构成人类范围确认'
```

退出码 **0**；批次状态 `DEV_GATE1_PACKET_READY`；8 项产物齐全（原始快照 104 304 字节、质量报告、两份日志、两份代码留档、清单、候审材料）；`manifest_version=TASK-003-R1-batch-manifest-1.1`；四表 20/993/1000/1005；缺失应付关联净额 1 000 000 分；`report_validation.valid=true`；两份代码留档 `matches_source=true`；`gate1_approval=null`、`gate2_approval=null`、`next_step_allowed=false`。

### 4.3 最终集成验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r1_tests_02'
```

退出码 **0**；输出“用例总数 21，通过 21，失败 0”“入口调用 21 次（真实 CLI 11 次 + 内存模拟 10 次）”“预期负向案例 18 个”“只读输入前后哈希一致: True（受保护 34 个）”。

### 4.4 其他核验

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -`）用于与 GPT TASK-003 验收记录的 1308 个文件比对哈希、核对最终批次关键字段与容器计数；未新增 `.py` 文件。

---

## 5. 用例清单与实际结果（21 个用例，全部通过）

### 5.1 原有 10 个用例（保留原断言，全部重跑）

| 用例 | 期望／实际退出码 | 关键断言 |
| --- | --- | --- |
| `C01_valid` | 0／**0** | `DEV_GATE1_PACKET_READY`；快照与源一致；两份代码留档与执行版本一致；报告核验本批次快照；完整金额 500000 分；批准字段 null |
| `MAIN_demo` | 0／**0** | 四表 20/993/1000/1005；缺失关联净额 1 000 000 分；勾稽 `ASSESSED` 且相等 |
| `C14a_missing_column` | 1／**1** | `BLOCKED_QUALITY`；报告结构校验 `valid=true`；`REQUIRED_COLUMN_MISSING`；金额为 `null` |
| `C14c_amount_invalid` | 1／**1** | `BLOCKED_QUALITY`；`AMOUNT_INVALID`；完整金额 `null`；不可用单元格已计数 |
| `unreadable_xlsx` | 2／**2** | `FAILED_RUNTIME`；无质量报告；快照保留；材料写明核验未完成且不填零 |
| `RERUN_same_out_dir` | 2／**2** | 拒绝覆盖；既有批次全部文件前后哈希一致 |
| `PARAM_out_of_bounds` | 2／**2** | 越界目录未被创建 |
| `PARAM_batches_root_itself` | 2／**2** | `data/batches` 仍在；未新增其他批次目录 |
| `PARAM_missing_input` | 2／**2** | 批次目录未被创建 |
| `SNAPSHOT_mismatch_simulated` | 2／**2** | 复制成功但字节不同 → `FAILED_RUNTIME`；`snapshot_matches_source=false`；不生成报告；`next_step_allowed=false` |

### 5.2 新增 11 个用例（对应返修卡第 4 节）

| 用例 | 方式 | 期望／实际退出码 | 关键断言 |
| --- | --- | --- | --- |
| `R1_source_description_raw` | CLI | 0／**0** | 含首尾空格与换行的 29 字符声明：清单 `source_description` **逐字符一致**（实测长度 29 = 29） |
| `R1_source_description_blank` | CLI | 2／**2** | 全空白描述在建批次前拒绝，批次目录未创建 |
| `R1_copy_io_failure` | 内存 | 2／**2** | 部分字节写入后抛 `OSError`：`FAILED_RUNTIME`、`failure.stage=copy_snapshot`、部分快照保留且更小、无伪报告、checker 未启动且退出码为 `null` |
| `R1_report_array` | 内存 | 2／**2** | 报告为合法 JSON 数组：`FAILED_RUNTIME`，不产生就绪清单，原报告保留，材料不显示零问题 |
| `R1_report_structure_array` | 内存 | 2／**2** | 顶层与哈希正确但 `structure` 为数组：退出 2，不产生就绪清单 |
| `R1_report_missing_sections` | 内存 | 2／**2** | 仅有 `result` 与两个哈希：退出 2；材料**不出现“问题总数：0”或“未记录数据质量或范围问题”** |
| `R1_report_invalid_json` | 内存 | 2／**2** | JSON 语法错误：退出 2，记录 `read_report` 阶段异常，原错误报告保留 |
| `R1_code_snapshot_mismatch_check_demo_data.py` | 内存 | 2／**2** | checker 留档被追加字节：`matches_source=false`，失败原因含“源码留档” |
| `R1_code_snapshot_mismatch_receive_demo_batch.py` | 内存 | 2／**2** | 接收器留档被追加字节：同上 |
| `R1_packet_write_failure_once` | 内存 | 2／**2** | 材料第一次写入抛 `OSError`：`FAILED_RUNTIME`、`receive_exit_code=2`、记录写入失败；重试后材料存在且写明核验未完成 |
| `R1_packet_write_failure_always` | 内存 | 2／**2** | 材料始终无法写入：清单仍保存，`gate1_packet.exists=false`，记录实际缺失，无就绪状态 |

统计：**用例 21 个，通过 21，失败 0**；预期负向案例 **18** 个（上表中退出码非 0 的用例），与脚本自身失败分开记录，见 `task003_r1_tests_02\summary.json` 的 `expected_negative_cases`。
调用与日志：**真实 CLI 11 次 + 内存模拟 10 次 = 21 次**，每次调用（含内存模拟）单独保存 stdout／stderr，共 **42** 个日志文件；`command_log.json` 用 `mode` 字段区分 `cli` 与 `in_memory_simulation`，并登记日志路径。

---

## 6. 文件保护结果

- **本卡授权修改的 3 个文件**：`scripts/receive_demo_batch.py`、`tests/test_receive_demo_batch.py`、`docs/BATCH_RECEIVE_GUIDE.md`（哈希见第 2.1 节）。
- **冻结源码保持不变**：`scripts/check_demo_data.py` = `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8`、`tests/test_check_demo_data_regression.py` = `555c5ef7320c6fd3078264f808a5c2a43f492909058b9b0d361fb43dee09bbb6`、`scripts/make_demo_data.py` = `e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`、`docs/SPEC_V1.md` = `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236`、`docs/AUDIT_CONTRACT_DRAFT.md` = `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27`。
- **对 GPT TASK-003 验收记录的 1308 个既有文件**重新核对：**3 个变化（恰为本卡授权文件）、0 个缺失**。
- 集成验证内建核验：**34 个只读输入**（主演示工作簿、22 份 fixture、checker、生成器、规格、契约草案、旧回执三份、两份验收报告、原任务卡）与 4 个测试输入副本，测试前后哈希全部一致；并额外校验真实磁盘上的 checker 与接收器哈希未变。
- 依赖未变（Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未执行任何 `pip install`；Git 仍未初始化；`py_compile` 产生的 `__pycache__` 已删除。

---

## 7. 不完整 / 无效报告的现场保留

结构无效或不可解析的报告**一律原样留在批次内**（`checks/quality_report.json`），只在校验层面拒绝使用：

| 批次（测试容器内） | 报告内容 | 处理 |
| --- | --- | --- |
| `R1_report_array` | `[]` | 保留原文件；`report_validation.valid=false`；材料“核验未完成” |
| `R1_report_structure_array` | 顶层正确、`structure` 为数组 | 保留；拒绝渲染，不产生就绪清单 |
| `R1_report_missing_sections` | 仅 `result` 与两个哈希 | 保留；不补零、不显示零问题 |
| `R1_report_invalid_json` | 语法错误文本 | 保留；记录解析异常 |
| `R1_copy_io_failure` | 无报告（快照不可信，跳过 checker） | 部分快照与说明日志保留 |
| `R1_packet_write_failure_always` | 报告有效，但材料无法保存 | 清单记录 `gate1_packet.exists=false` 与实际缺失 |

## 8. 失败尝试、偏差与修复过程

1. **第一次 R1 验证运行（`task003_r1_tests_01`）20/21 通过**：失败项是我自己写的断言错误——`R1_report_invalid_json` 断言 `report_validation.valid is False`，但 JSON 语法错误时结构校验根本不会执行，该字段保持 `null`。**接收器行为本身正确**（退出 2、`FAILED_RUNTIME`、原报告保留、材料写明核验未完成）。修正的是**测试断言**（改为 `valid is not True`，并新增“记录了报告解析异常”断言），随后在新容器 `task003_r1_tests_02` 重跑通过；失败的容器按“不覆盖历史”保留，未删除。**未修改任何数据、报告或源码来让断言变通过。**
2. **运行前发现并修正的设计问题**：最初把“复制写入部分字节后抛错”与“复制成功但字节不同”混用同一个模拟函数，会让“快照与源不一致”分支走到异常路径。改为两个独立模拟（`partial_copy_failure` 抛错、`tampered_copy_success` 不抛错但字节不同），分别覆盖两条失败分支。属运行前修正，未产生失败运行。
3. **按要求未修的非阻断项**：任务二验收记录中的回归摘要 `task` 显示标签问题仍不在本卡范围，未改动已验收源码。
4. **旧批次保留**：`dev_receive_003_main_01/02`、`task003_tests_01/02` 由修订前入口生成，保留现场；其 `code_snapshot` 记录的是当时版本，这正是批次留痕的预期行为，不是错误。

## 9. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：标准化、SQLite 入库、业务状态机、R01—R04 筛查、AI 审计建议、正式契约、正式人工守门点、RAG、OCR、百万行压测、真实 ERP 接入；未统计召回率或误报率。
- 已知限制：
  - 报告结构校验只覆盖**本入口消费**的区段，不等同于 checker 报告的完整 schema 校验；
  - 代码留档一致性检查用于发现普通复制故障与留档可靠性问题，**不抵御同权限恶意篡改**，不是签名或权限隔离；
  - 候审材料是开发态材料，不含风险等级或业务结论；金额 `null` 表示不可得，不得读作零；勾稽沿用 checker 的保守方案；
  - 无法写入任何文件时，入口只能保证退出 2 与 stderr 说明，不能凭空生成清单。
- 本卡范围内工作已停止：未推进任务四，未代主理人审定契约、批准 Gate 1／Gate 2 或填写职业判断，未宣称已实现人工守门点。
- 等待主理人把本回执与 `data\batches\dev_receive_003_r1_main_01`、`data\batches\task003_r1_tests_02` 转交总架构师复验。
