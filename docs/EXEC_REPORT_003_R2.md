# TASK-003-R2 执行回执（收口报告校验与最终清单）

任务：修复 TASK-003-R1 复验剩余的三组问题——A JSON 解析成功后未无条件检查对象／必需内容、B finalize 的读取／拼装／写入未纳入失败处理、C 最终清单与实际文件及未知值不一致。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-003-R2.md`、`docs/reviews/REVIEW_TASK_003_R1.md`、`docs/tasks/TASK-003-R1.md`、`docs/tasks/TASK-003_DRAFT.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务四。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| A 无条件结构校验 | JSON 解析成功即校验；`null`、空对象、缺必需键、父区段为 `null` 一律 `FAILED_RUNTIME`（退出 **2**） |
| B finalize 失败留痕 | 报告／规格／契约／日志／快照／代码副本／材料本身的采集与拼装全部兜底；清单**原子提交**（临时文件 + 替换），提交失败先同步材料为失败态再改写清单重试 |
| C 清单对应最终现场 | 正常与阻断批次的 `gate1_packet.exists=true` 且 `sha256` 与磁盘一致；`size_bytes`、`stable_during_run`、`started` 的未知值记 `null`，不再由默认零或 `None==None` 生成“已验证”假象 |
| 集成验证 | **52 个用例全部通过、失败 0**（原 21 例 + 新增 9 例 + 22 份 fixture 实跑），测试退出 **0**；预期负向案例 **35** 个 |
| 调用与日志 | 入口实际调用 **52** 次：真实 CLI **33** 次 + 内存模拟 **19** 次；**104** 个独立 stdout／stderr 日志文件 |
| fixture 兼容性 | 22 份既有 fixture 经**真实接收器**运行：**14 份退出 0（候审就绪）、8 份退出 1（质量阻断）**，报告结构校验全部通过 |
| 最终主演示批次 | `data\batches\dev_receive_003_r2_main_01`：8 项产物齐全，`DEV_GATE1_PACKET_READY`，四表 20/993/1000/1005，缺失关联净额 1 000 000 分，材料哈希与清单一致 |
| 最终验证容器 | `data\batches\task003_r2_tests_02`（471 个文件） |
| 冻结源码 | checker `a7e5eb67…`、任务二回归脚本 `555c5ef7…`、生成器 `e899aa2f…`、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| 既有文件保护 | 对 GPT R1 复验基线 **1805 个文件**与首次验收基线 **1308 个文件**分别复核：**均为 3 个变化（全部是本卡授权修改的文件）、0 个缺失** |
| 未执行 | 标准化、入库、R01—R04、AI 建议、正式契约、人工守门点、真实 ERP 接入；未安装依赖、未初始化 Git |

---

## 2. 实际修改与新增

### 2.1 修改（本卡授权的三个文件）

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\receive_demo_batch.py` | `8ae9a51139b8b82cccf7e46d81c3e9d0e14482a0328831dad5bc2d3eb96432e6` |
| `D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py` | `34c4171ed39283c443a583808785eaabbc431cea6ab0fd9483e06f53507d5459` |
| `D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md` | `7f5a35f937b0ba29f4f96a995ac08f0a4ad2653b561734af2e90e99f31f82dc1` |

### 2.2 新增

| 路径 | 说明 |
| --- | --- |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_003_R2.md` | 本回执 |
| `D:\harness work\audit_sa_project\data\batches\dev_receive_003_r2_main_01` | **最终 R2 主演示批次**（8 个文件，`DEV_GATE1_PACKET_READY`） |
| `D:\harness work\audit_sa_project\data\batches\task003_r2_tests_02` | **最终 R2 验证容器**（471 个文件：`batches\` 361、`fixture_sweep\`、`inputs\` 4、`logs\` 104、`summary.json`、`command_log.json`） |
| `D:\harness work\audit_sa_project\data\batches\task003_r2_tests_01` | 第一次 R2 运行（2 条断言口径问题，见第 8 节），按“不覆盖历史”保留 |
| `D:\harness work\audit_sa_project\data\batches\task003_r2_smoke_01` | 实现过程中的单次冒烟批次（较早修订版），保留现场 |

未覆盖、未删除任何既有批次或 GPT 证据；`dev_receive_003_main_01/02`、`dev_receive_003_r1_main_01`、`task003_tests_01/02`、`task003_r1_tests_01/02`、`task003_gpt_*`、`task003_r1_gpt_*` 全部原样保留。

---

## 3. 三组修复的落点

### A. JSON 解析成功后无条件进行对象／必需内容检查

- 解析与校验解耦：`json.loads` 成功即置 `report_readable=true` 并**无条件**调用 `validate_report()`；不再用 `report is not None` 区分“解析成功”和“没有报告”。`null` 解析为 `None` → 顶层非对象 → `validate_report` 直接判无效 → 退出 2。
- 必需内容按冻结 checker 的实际格式逐项要求（只查入口消费的内容，不重算业务规则）：
  - `row_accounting` 必须含 `suppliers`／`payables`／`payments`／`allocations` 四项，且每项含 `source_rows`／`accepted_rows`／`blocked_rows`／`blank_rows`，值为**非负整数**（布尔不算整数）；
  - `amount_summary.known_valid_subtotals_cents` 与 `complete_totals_cents` 必须是对象且含 `payables_payable_amount`／`payments_amount`／`allocations_allocated_amount` 三键（值可为整数或 `null`，**父区段不得为 null、空对象或缺失**）；`unusable_amount_cells` 必须含 `total`（整数）／`by_reason`（对象）／`sources`（数组）；
  - `structure.sheets_found` 为字符串数组；对 `sheets_found` 中实际存在的固定表，`sheet_field_mapping` 必须有对象条目，列号为**正整数或 null**；
  - `reconciliation` 必须有 `status`（`ASSESSED`／`NOT_ASSESSED`）与 `known_plus_missing_equals_master`（布尔或 `null`，**缺键不算“已提供 null”**）；诊断区段仍要求对象；
  - `issues`（数组，条目含六个字段）与 `issue_counts_by_code`（值为整数）保留原有检查；**合法空问题数组与合法金额 `null` 仍然允许**。
- 结构无效的报告保留原字节、路径、真实存在状态与可获取的哈希（`report_validation` 记录 `attempted/valid/problems/report_readable`），不进入正常材料渲染；质量阻断报告（如 C14a、C14c，金额键存在而值为 `null`）仍按 `BLOCKED_QUALITY`／退出 1。

### B. finalize 的读取、拼装、写入也纳入失败处理

- 新增 `gather_static_infos()` 与 `gather_final_infos()`：分别采集（报告、规格、契约草案）与（日志、快照、两份代码副本、候审材料本身）的存在状态与哈希；`hash_info()`／`safe_hash_file()` 兜住异常，文件存在但读不到哈希时保留 `exists=true`、`sha256=null` 并记录 `read_error`，存在性无法判断时记 `exists=null`。
- `_require_artifact()` 把“要求的产物缺失或哈希不可读”判为运行失败，因此 SPEC／报告哈希读取失败会退出 2，而不再抛出未捕获异常（原 Q03／Q04 场景）。
- 收尾顺序改为：**先采集静态信息 → 写材料 → 采集最终现场 → 状态若变化则按最终状态重写材料 → 构建并原子提交清单**；材料写入失败或状态变化时，材料会被重写为失败状态（含 `失败原因` 段落），不残留就绪状态。
- 清单改为 `commit_manifest()`：先写同目录 `batch_manifest.json.tmp`，再 `os.replace` 原子替换。首次提交在落盘字节后仍报错时，入口记录 `material_write_failures`、把材料同步为失败态，再提交一份 `FAILED_RUNTIME` 清单；两次都失败才在 stderr 写明失败与现场路径并退出 2。
- `main()` 现在同时兜住 `execute_batch()` 与 `finalize()`；`finalize()` 内部任何未预期异常都会记录并尝试提交一份 `FAILED_RUNTIME` 清单，不再以退出 1 结束。
- 失败阶段保留**首次**失败来源（`failure.stage`，另记 `failure.current_stage`），不会被后来的渲染／写入阶段覆盖。

### C. 最终清单对应最终现场，未知值保持未知

- `gate1_packet` 信息在材料写入**之后**采集，因此 `exists=true` 且 `sha256` 与磁盘一致；报告的 `exists/sha256` 也来自最终现场。
- `source.size_bytes` 初值为 `null`，只有确实取到才写入真实值。
- `stable_during_run` 改为 `stability(before, after)`：任一端为 `null` 即返回 `null`，不再因 `None == None` 写 `true`。
- `checker_invocation` 增加 `attempted`；`started` 语义明确为成功完成子进程调用记 `true`、确定没启动记 `false`、无法判断记 `null`；未启动时 `exit_code` 为 `null`，`argv` 仍保留尝试参数。
- 清单版本提升为 `TASK-003-R2-batch-manifest-1.2`，接收说明已同步；既有批次中的旧清单**不迁移、不修正**。

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

### 4.2 最终主演示批次

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' --out-dir 'D:\harness work\audit_sa_project\data\batches\dev_receive_003_r2_main_01' --source-description 'TASK-003-R2 开发验收：现有合成 ERP 导出演示文件，来源描述尚不构成人类范围确认'
```

退出码 **0**；批次状态 `DEV_GATE1_PACKET_READY`；8 项产物齐全；`manifest_version=TASK-003-R2-batch-manifest-1.2`；四表 20/993/1000/1005；缺失应付关联净额 1 000 000 分；`gate1_packet.exists=true` 且哈希与磁盘一致；`hashes.spec.exists=true`、`sha256=5df632ed…`；`source.size_bytes=104304`；`checker_invocation.attempted=true`、`started=true`、`exit_code=0`；`report_validation.valid=true`；两项批准 `null`、`next_step_allowed=false`。

### 4.3 最终集成验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r2_tests_02'
```

退出码 **0**；输出“用例总数 52，通过 52，失败 0”“入口调用 52 次（真实 CLI 33 次 + 内存模拟 19 次）”“预期负向案例 35 个”“只读输入前后哈希一致: True（受保护 39 个）”。

### 4.4 其他核验

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -`）用于与 GPT 两份基线比对哈希、核对最终批次关键字段与容器计数；未新增 `.py` 文件。

---

## 5. 用例矩阵与实际结果（52 个用例，全部通过）

### 5.1 原 21 例（保留原断言全部重跑，另加物料一致性断言）

原有用例全部通过；其中 `C01_valid`、`MAIN_demo`、`C14a_missing_column` 新增断言：**候审材料真实存在、清单 `gate1_packet.sha256` 与磁盘一致、8 项产物齐全**（此前正常批次误记 `exists=false`，本轮已修正）。
最终批次实测：`C01_valid` 完整金额 500000 分；`MAIN_demo` 四表 20/993/1000/1005、缺失关联净额 1 000 000 分；`C14a` 报告结构 `valid=true`、`REQUIRED_COLUMN_MISSING`、payables 金额 `null`。

### 5.2 R2 新增 9 例

| 用例 | 方式 | 期望／实际退出码 | 关键断言 |
| --- | --- | --- | --- |
| `R2_report_null` | 内存 | 2／**2** | 报告为合法 JSON `null`：`FAILED_RUNTIME`，`report_validation.valid` 不为 true，材料“核验未完成”，不产生就绪清单 |
| `R2_report_row_accounting_empty` | 内存 | 2／**2** | `row_accounting={}`：退出 2（空对象不算已提供四表统计） |
| `R2_report_amount_keys_missing` | 内存 | 2／**2** | 两个金额区段各缺三项必需键：退出 2 |
| `R2_report_amount_parent_null` | 内存 | 2／**2** | `known_valid_subtotals_cents=null`：退出 2（父区段不允许 null） |
| `R2_spec_hash_read_failure` | 内存 | 2／**2** | SPEC 哈希读取抛错：退出 2、清单仍保存、`spec.sha256=null` 且有 `read_error`、`exists=null`（不写成不存在） |
| `R2_report_hash_read_failure` | 内存 | 2／**2** | 报告哈希读取抛错：退出 2、原报告保留、清单仍保存、报告 `exists=null`、未崩溃 |
| `R2_manifest_commit_failure_once` | 内存 | 2／**2** | 首次提交落盘字节后报错：最终清单 `FAILED_RUNTIME`／`receive_exit_code=2`、材料不残留成功状态、记录写入失败 |
| `R2_initial_source_hash_failure` | 内存 | 2／**2** | 输入首次哈希失败：退出 2、清单仍保存、`size_bytes=null`（不填 0）、两端未知故 `stable_during_run=null`（不写 true）、checker 未启动且退出码 `null` |
| `R2_checker_launch_failure` | 内存 | 2／**2** | checker 抛 `FileNotFoundError`：退出 2、`started=false`、`attempted=true` 且保留 `argv`、`exit_code=null`、无伪报告 |

### 5.3 22 份既有 fixture 经真实接收入口运行（兼容性回归）

| 结果 | 用例 |
| --- | --- |
| 退出 **0**（`DEV_GATE1_PACKET_READY`） | C01、C02、C03、C04、C05、C06、C06b、C07、C07b、C08、C09、C09b、C10、C10b（14 份） |
| 退出 **1**（`BLOCKED_QUALITY`） | C11、C12、C13、C14a、C14b、C14c、C14d、C14e（8 份） |
| 共同断言 | 报告结构校验 `valid=true`、候审材料存在且清单哈希与磁盘一致、批准字段 `null`、`next_step_allowed=false` |

即 **14 份质量通过、8 份质量阻断**，没有被新增的结构校验误判为运行失败。

### 5.4 统计

用例 **52** 个（原 21 + 新增 9 + fixture 22），通过 **52**，失败 **0**；预期负向案例 **35** 个（含 8 份阻断 fixture），与脚本自身失败分开记录。
入口调用 **52** 次 = 真实 CLI **33** 次 + 内存模拟 **19** 次；每次调用独立 stdout／stderr，共 **104** 个日志文件；`command_log.json` 用 `mode` 区分 `cli` 与 `in_memory_simulation`。

---

## 6. 文件保护结果

- **授权修改的 3 个文件**：哈希见第 2.1 节。
- **冻结源码未变**：`scripts/check_demo_data.py` = `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8`、`tests/test_check_demo_data_regression.py` = `555c5ef7320c6fd3078264f808a5c2a43f492909058b9b0d361fb43dee09bbb6`、`scripts/make_demo_data.py` = `e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`、`docs/SPEC_V1.md` = `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236`、`docs/AUDIT_CONTRACT_DRAFT.md` = `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27`。
- **对 GPT 两份基线复核**：
  - R1 复验基线 **1805 个文件**：变化 **3**（恰为本卡授权文件）、缺失 **0**；
  - 首次验收基线 **1308 个文件**：变化 **3**（同上）、缺失 **0**。
- 集成验证内建核验：**39 个只读输入**（主演示工作簿、22 份 fixture、checker、生成器、规格、契约草案、旧回执、R2/R1 验收报告与任务卡）与 4 个测试输入副本前后哈希一致；并额外校验真实磁盘上的 checker 与接收器哈希未变。
- 依赖未变（Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未执行 `pip install`；Git 未初始化；`py_compile` 产生的 `__pycache__` 已删除。

## 7. 失败现场与旧清单保留

- 结构无效或不可解析的报告一律原样留在批次内（`checks/quality_report.json`），只在校验层面拒绝使用。
- 既有批次（`dev_receive_003_main_01/02`、`task003_tests_01/02`、`task003_r1_tests_01/02`、`dev_receive_003_r1_main_01`、`task003_r2_smoke_01`、`task003_r2_tests_01`）与 GPT 证据目录全部保留；旧清单仍为 1.0／1.1 版本语义（其中 `gate1_packet.exists=false`、`stable_during_run` 由 `None==None` 得出的问题正是本轮修复对象），**按验收要求不迁移、不修正**。
- `task003_r2_smoke_01` 是最终修订前的单次冒烟批次，其 `code_snapshot` 记录了当时版本。

## 8. 失败尝试、偏差与修复过程

1. **第一次 R2 验证运行（`task003_r2_tests_01`）50/52 通过**，两条失败都是我自己断言口径的问题，非接收器缺陷：
   - `R1_copy_io_failure`：断言要求 `checker_invocation.started is False`，而当时从未尝试启动时该字段保持 `null`。按 R2 卡“started 不能是 true、无法判断记 null、确定未启动记 false”的要求，把初始值明确为 `False`（未尝试即确定未启动），`null` 只保留给“尝试过但无法判断”的情形——这是语义收紧，不是为了让断言通过而放宽判断。
   - `R1_packet_write_failure_once`：断言要求材料含“核验未完成”，而收口后材料会按**最终状态**重新渲染（显示 `FAILED_RUNTIME` 并列出 `失败原因`），内容比单独的失败通告更完整。改为断言“材料存在、显示 `FAILED_RUNTIME`、不含 `DEV_GATE1_PACKET_READY`、含失败原因”。
   失败容器按“不覆盖历史”保留；随后在新容器 `task003_r2_tests_02` 重跑通过。**未修改任何数据、报告或既有批次来让断言变通过。**
2. **实现过程中的一处设计调整**：为避免失败的成功候选清单直接成为正式清单，清单写入改为临时文件 + 原子替换；失败注入相应针对**实际提交路径**（`commit_manifest`）进行，未通过改注入位置绕过要验证的失败。
3. **按要求未修的非阻断项**：任务二回归脚本的 `task` 显示标签维护项仍不在本卡范围。

## 9. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：标准化、SQLite 入库、业务状态机、R01—R04 筛查、AI 审计建议、正式契约、正式人工守门点、RAG、OCR、百万行压测、真实 ERP 接入；未统计召回率或误报率。
- 已知限制：
  - 报告结构校验只覆盖**入口消费**的内容，不等同于 checker 报告的完整通用 schema 校验；
  - 代码留档一致性检查用于发现普通复制故障与留档可靠性问题，**不抵御同权限恶意篡改**；
  - 原子提交依赖文件系统语义；存储彻底不可写时只能保证退出 2 与 stderr 说明，不能凭空生成文件；
  - 候审材料是开发态材料，不含风险等级或业务结论；金额 `null` 表示不可得，不得读作零。
- 本卡范围内工作已停止：未推进任务四，未代主理人审定契约、批准 Gate 1／Gate 2 或填写职业判断，未宣称已实现人工守门点。
- 等待主理人把本回执与 `data\batches\dev_receive_003_r2_main_01`、`data\batches\task003_r2_tests_02` 转交总架构师复验。
