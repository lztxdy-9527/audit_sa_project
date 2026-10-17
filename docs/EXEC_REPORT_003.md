# TASK-003 执行回执（开发态接收、原始快照与批次留痕）

任务：把已验收的数据质量校验器接入一个很小的接收流程——单文件接收、逐字节原始快照、批次与代码版本留痕、生成开发态 Gate 1 候审材料。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-003_DRAFT.md`、`docs/reviews/REVIEW_TASK_002_R2.md`、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2—3 节、`docs/SPEC_V1.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未启动下一张任务，未宣布任何业务批次获得批准。

> 本回执只记录实际执行的命令与结果，命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 接收入口 | 新增 `scripts/receive_demo_batch.py`，三参数 CLI；参数／路径非法时**建立批次前**退出 2 |
| 主演示文件接收（卡片示例命令，最终交付批次） | 退出 **0**，状态 `DEV_GATE1_PACKET_READY`，8 个批次产物齐全 |
| 针对性集成验证 | **10 个用例全部通过**（2 个正向 + 8 个预期负向），测试进程退出 **0** |
| 原始快照 | 逐字节复制，快照哈希与源哈希一致；业务核验只读快照，报告 `workbook.sha256` 即快照哈希 |
| 一致性防护 | 原输入复制前／后／核验结束哈希、快照核验前后哈希、checker 与入口在一次执行内的稳定性全部校验；任一不一致即 `FAILED_RUNTIME`（退出 2） |
| 运行失败不留伪报告 | 无法读取的工作簿：退出 **2**、`FAILED_RUNTIME`、无 `quality_report.json`、候审材料写“核验未完成”且未知值记 `null` |
| 未伪造批准 | 所有批次 `contract_status=DRAFT_NOT_IN_FORCE`、`gate1_approval=null`、`gate2_approval=null`、`next_step_allowed=false` |
| 候审材料零歧义 | 最终批次 `gate1_packet.md` **不含 `approve` 字样**（连免责句也不再出现），只保留“不含任何批准入口或自动继续命令”的表述 |
| 已验收源码保护 | checker `a7e5eb67…`、原回归脚本 `555c5ef7…`、生成器 `e899aa2f…`、规格 `5df632ed…` 均与任务二验收一致，**未修改** |
| 既有文件保护 | 对 GPT R2 验收记录的 **874 个文件**重新核对：**0 个变化、0 个缺失** |
| 依赖 | 未安装、未升级；未初始化 Git |
| 未执行 | 标准化、SQLite 入库、R01—R04、AI 建议、正式契约、正式人工守门点、真实 ERP 接入 |

---

## 2. 实际新增的文件与产物

### 2.1 新增交付物（未修改任何既有文件）

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\receive_demo_batch.py` | `1591848ad69f7c34390e2e80bfc7af0fcd434b0835c75a22989ffc3f388fafee` |
| `D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py` | `4bbc8875a953cdf854ecbe7ea5a74965a45c08bd112f2b77777915283fef908c` |
| `D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md` | `9493c9867b486761c04cee896bcde13d1fd9cb22e3ae9f94339da19a4be9cb65` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_003.md` | 本文件 |

### 2.2 批次与验证容器（全部保留，未覆盖、未删除）

| 目录 | 文件数 | 说明 |
| --- | --- | --- |
| `D:\harness work\audit_sa_project\data\batches\dev_receive_003_main_02` | 8 | **最终交付批次**：卡片示例命令接收主演示工作簿，`DEV_GATE1_PACKET_READY` |
| `D:\harness work\audit_sa_project\data\batches\task003_tests_02` | 70 | **最终验证容器**：`batches\` 6 个批次（46 文件）、`inputs\` 4、`logs\` 18、`summary.json`、`command_log.json` |
| `D:\harness work\audit_sa_project\data\batches\dev_receive_003_main_01` | 8 | 措辞修订前的同输入批次，按“不覆盖历史”保留；其 `code_snapshot` 保存了当时使用的入口版本 `33c9f4ea…` |
| `D:\harness work\audit_sa_project\data\batches\task003_tests_01` | 70 | 措辞修订前的验证容器，同样保留为历史 |

批次内固定结构：`source/input.xlsx`、`checks/quality_report.json`、`logs/checker.stdout.txt`、`logs/checker.stderr.txt`、`code_snapshot/receive_demo_batch.py`、`code_snapshot/check_demo_data.py`、`batch_manifest.json`、`gate1_packet.md`（`FAILED_RUNTIME` 且未运行核验时没有报告文件）。

最终验证容器内的 6 个批次目录：`C01_valid`、`MAIN_demo`、`C14a_missing_column`、`C14c_amount_invalid`、`unreadable_xlsx`、`SNAPSHOT_mismatch`。参数拒绝类用例（越界、指向 `data\batches` 本身、输入不存在）在设计上不生成批次目录。

未覆盖、未删除任何既有目录：`data\generated\*`、`data\reviews\*`、原有 `checks\` 与答案册全部保持原样。

---

## 3. 接收入口实现要点

1. **三参数 CLI**：`--workbook`（单个 `.xlsx`，不递归扫描）、`--out-dir`（`data/batches` 内尚不存在的子目录）、`--source-description`（非空，原样记录为声明）。越界、指向 `data/batches` 本身、已存在、输入不存在或非 `.xlsx`、描述为空、缺少必需依赖文件，一律在建立批次前返回 2。
2. **原始快照逐字节复制**：`shutil.copyfile`，不用 openpyxl 重新保存；原单元格值、类型、行号由快照保留，本任务不另做转换后的数据表。
3. **复用已验收 checker**：`sys.executable` 调用 `scripts/check_demo_data.py` 的 CLI，输入为本批次 `source/input.xlsx`，报告写入本批次 `checks/quality_report.json`；未复制其校验逻辑，未导入生成器，未读取答案册或旧 `checks/`。
4. **不靠 stdout 判断成功**：记录完整 argv、退出码、stdout、stderr；再校验报告是否存在、可解析、`result` 与退出码是否一致、`workbook.sha256` 是否等于本批次快照、`checker.sha256` 是否等于本次执行的 checker 版本。
5. **一致性门**：原输入复制前／复制后／核验结束时哈希、快照核验前后哈希、checker 与入口脚本在一次执行内是否稳定；任一异常追加失败原因并把批次判为 `FAILED_RUNTIME`。
6. **快照不可信时不制造报告**：若复制出的快照与源字节不一致，直接跳过核验，日志写明原因，`checker_invocation.argv=null`、`exit_code=null`、报告不存在，候审材料写“核验未完成”。
7. **状态与退出码**：`DEV_GATE1_PACKET_READY`→0、`BLOCKED_QUALITY`→1、`FAILED_RUNTIME`→2；批次清单固定 `contract_status=DRAFT_NOT_IN_FORCE`、`gate1_approval=null`、`gate2_approval=null`、`next_step_allowed=false`。
8. **候审材料**：`gate1_packet.md` 首行固定“开发态候审材料，未批准，不代表可以进入标准化”，含 5 节（批次与来源／结构与行数／质量结果／金额与勾稽／下一步未执行）；`null` 表示不可得，不填零，主表与分摊金额不相加；不含风险等级、规则命中、AI 结论、批准入口或自动继续命令。
9. **可验证性设计**：逐字节复制单独成 `copy_snapshot_bytes()` 函数，使验证可以在内存中替换它来模拟复制故障，生产路径只有一种实现，未引入测试开关。

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

### 4.2 接收主演示工作簿（卡片第 6 节示例命令，目录后缀换新）

```powershell
& $py 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' --out-dir 'D:\harness work\audit_sa_project\data\batches\dev_receive_003_main_02' --source-description 'TASK-003 开发验收：现有合成 ERP 导出演示文件，来源描述尚不构成人类范围确认'
```

退出码 **0**；输出批次状态 `DEV_GATE1_PACKET_READY`、checker 退出码 0。该批次清单关键值：快照哈希与源一致、报告 `result=pass` 且 `workbook.sha256` 等于快照哈希、`report_matches_checker=true`、四表行数 20/993/1000/1005、缺失应付关联净额 1 000 000 分、勾稽 `ASSESSED` 且相等、`gate1_approval=null`、`next_step_allowed=false`；`code_snapshot/receive_demo_batch.py` 的哈希等于当前入口哈希 `1591848a…`。

### 4.3 接收入口集成验证

```powershell
& $py 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_tests_02'
```

退出码 **0**；输出“用例总数 10，通过 10，失败 0；接收入口实际调用 10 次”“预期负向案例 8 个”“只读输入前后哈希一致: True（受保护 31 个）”。

### 4.4 其他核验

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -`）用于与 GPT R2 验收记录的 874 个文件比对哈希、检查最终候审材料是否含 `approve` 字样、以及整理批次产物计数；未新增 `.py` 文件。

---

## 5. 集成验证的 10 个用例（最终容器实际结果）

| # | 用例 | 构造 | 期望／实际退出码 | 状态与关键断言 |
| --- | --- | --- | --- | --- |
| 1 | `C01_valid` | C01 案例副本 | 0／**0** | `DEV_GATE1_PACKET_READY`；快照与源一致；报告核验的是本批次快照；完整金额 500000 分；批准字段 null；候审材料含固定声明；代码副本齐全 |
| 2 | `MAIN_demo` | 主演示工作簿 | 0／**0** | 四表 20/993/1000/1005；缺失应付关联净额 1 000 000 分（保留未知 AP 的资金部分）；勾稽 `ASSESSED` 且相等 |
| 3 | `C14a_missing_column` | C14a 缺 `payable_amount` 列 | 1／**1** | `BLOCKED_QUALITY`；`REQUIRED_COLUMN_MISSING`；payables 完整金额与已知小计均为 `null`；快照保留；未变成候审就绪 |
| 4 | `C14c_amount_invalid` | C14c 金额为文本 `N/A` | 1／**1** | `BLOCKED_QUALITY`；`AMOUNT_INVALID`；payments 完整金额 `null`；不可用金额单元格已计数 |
| 5 | `unreadable_xlsx` | 纯文本伪装的 `.xlsx` | 2／**2** | `FAILED_RUNTIME`；无 `quality_report.json`；清单记录报告不存在；快照仍保留；候审材料写“核验未完成”且用 `null（不可得，不得填零）` |
| 6 | `RERUN_same_out_dir` | 对 `C01_valid` 批次目录重复调用 | 2／**2** | 拒绝覆盖，且该批次全部文件前后哈希一致（含 `batch_manifest.json`） |
| 7 | `PARAM_out_of_bounds` | `--out-dir` 指向 `data/task003_oob_probe_outside_batches` | 2／**2** | 越界目录未被创建 |
| 8 | `PARAM_batches_root_itself` | `--out-dir` 指向 `data/batches` 本身 | 2／**2** | `data/batches` 仍在；未新增其他批次目录 |
| 9 | `PARAM_missing_input` | `--workbook` 指向不存在文件 | 2／**2** | 批次目录未被创建 |
| 10 | `SNAPSHOT_mismatch_simulated` | 内存替换复制函数，使快照多出 1 字节 | 2／**2** | `FAILED_RUNTIME`；`snapshot_matches_source=false`；失败原因写明快照与源不一致；`next_step_allowed=false`；快照不可信时不生成质量报告 |

总结：**10 个用例全部通过，失败 0**；其中 **8 个是预期负向案例**（3、4、5、6、7、8、9、10），与脚本自身失败分开记录，见 `data\batches\task003_tests_02\summary.json` 的 `expected_negative_cases`。
调用与日志：命令行调用 9 次（每次 stdout／stderr 各一份，共 **18** 个日志文件）＋ 内存模拟 1 次 = 入口实际调用 **10** 次；`command_log.json` 登记每次调用的完整参数与日志路径，互不覆盖。

---

## 6. 输入与既有文件保护

- 集成验证内建核验：**31 个只读输入**（主演示工作簿、22 份 fixture、checker、生成器、规格、契约草案、旧回执三份、R2 验收报告）以及 4 个测试输入副本，测试前后哈希**全部一致**。
- 对 GPT R2 验收记录的 **874 个既有文件**重新核对：**0 个变化、0 个缺失**（本卡只新增文件，未触碰既有内容）。
- 任务二冻结版本保持不变：`scripts/check_demo_data.py` = `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8`、`tests/test_check_demo_data_regression.py` = `555c5ef7320c6fd3078264f808a5c2a43f492909058b9b0d361fb43dee09bbb6`、`scripts/make_demo_data.py` = `e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`、`docs/SPEC_V1.md` = `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236`。
- 依赖未变：Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9；本卡未执行任何 `pip install` 或升级；项目 Git 仍未初始化。
- `py_compile` 产生的 `__pycache__` 已删除，`scripts\`、`tests\` 只保留授权文件。

## 7. 偏差、失败尝试与修复过程

1. **本轮没有失败执行**：语法检查、卡片示例接收、集成验证（10 用例）均一次通过；任务二的失败记录未被改动。
2. **入口措辞修订（自发的收紧，非验收要求）**：第一版候审材料在免责句里写了“不含 approve 或自动继续命令”，虽然只是否定陈述，但机器扫描该词仍可能误判为“提供了批准入口”。为避免歧义，改为“不含任何批准入口或自动继续命令”，使最终批次的 `gate1_packet.md` **完全不出现 `approve` 字样**（已实测 `'approve' in packet == False`）。
   - 该修订使入口哈希由 `33c9f4eab308392eda7212480a0b4198295582dc20b5fb003b18b3f21341752c` 变为 `1591848ad69f7c34390e2e80bfc7af0fcd434b0835c75a22989ffc3f388fafee`。
   - 按“不覆盖历史”的规则，修订前生成的 `dev_receive_003_main_01`、`task003_tests_01` 原样保留，其 `code_snapshot/receive_demo_batch.py` 记录了修订前版本；修订后的最终交付批次为 `dev_receive_003_main_02`，最终验证容器为 `task003_tests_02`。两批输入相同、结果一致，可直接对照。
   - 这恰好演示了批次留痕的作用：**每个批次自带产生它的代码版本**，事后可回答“这批结果是用哪一版入口产生的”。
3. **运行前的一处静态修正**：验证脚本最初把 `data/batches` 子目录数量断言写成硬编码容器名，改为按实际传入的容器名比较；属运行前发现并修正，未产生失败运行。
4. **未做“为让验证通过”的调整**：未修改已验收的 checker、原回归脚本、生成器、规格、契约草案、答案册或既有数据；快照不一致的失败路径是真走失败分支，不是放宽断言。
5. **按要求未修的非阻断项**：任务二验收记录指出回归摘要的 `task` 显示标签按输出目录末级名称判断（正常目录末级为 `regressions`，故显示 `TASK-002-R1`）。按验收意见，本卡**不为此修改已验收源码**，仅在此登记。

## 8. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：标准化模块、SQLite 入库、业务状态机、R01—R04 筛查、AI 审计建议、正式契约、正式人工守门点、RAG、OCR、百万行压测、真实 ERP 接入；未统计召回率或误报率。
- 已知限制：候审材料是**开发态**材料，不含风险等级或业务结论；公司／期间／截至日为任务设定与来源声明，不能据四表证明主体真实性或历史完整性；真实 ERP 导出时间未知记为 `null`；金额 `null` 表示不可得，不得读作零；勾稽沿用 checker 的保守方案（批次有任一问题即 `NOT_ASSESSED`）。
- 本卡范围内工作已停止：未启动下一张任务，未代主理人审定契约、批准 Gate 1／Gate 2 或填写职业判断，**未宣称已实现人工守门点**。
- 等待主理人把本回执与 `data\batches\dev_receive_003_main_02`、`data\batches\task003_tests_02` 转交总架构师验收。
