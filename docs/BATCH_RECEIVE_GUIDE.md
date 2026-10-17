# 批次接收与 Gate 1 候审材料说明（TASK-003）

版本：TASK-003 + R1 + R2 + R3；日期：2026-10-11；执行端：DeepSeek；依据：`docs/tasks/TASK-003_DRAFT.md`、`docs/tasks/TASK-003-R1.md`、`docs/tasks/TASK-003-R2.md`、`docs/tasks/TASK-003-R3.md`、`docs/reviews/REVIEW_TASK_003.md`、`docs/reviews/REVIEW_TASK_003_R1.md`、`docs/reviews/REVIEW_TASK_003_R2.md`、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2—3 节、`docs/SPEC_V1.md`。

本文只说明**开发态接收入口怎么用、留下哪些证据、三个状态分别代表什么**。它不构成 Gate 1 批准，不构成正式契约，也不含任何审计结论。

---

## 1. 接收什么、由谁触发

接收入口 `scripts/receive_demo_batch.py` 一次只接收**一份 `.xlsx` 文件**（不递归扫描目录），为它建立**一个全新批次**，保存原始字节快照、运行已验收的数据质量校验器、记录版本与哈希、生成候审材料，然后停止。

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' `
  'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' `
  --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' `
  --out-dir 'D:\harness work\audit_sa_project\data\batches\dev_receive_003_main_01' `
  --source-description '开发验收：现有合成 ERP 导出演示文件，来源描述尚不构成人类范围确认'
```

三个参数都是必需的：

| 参数 | 说明 |
| --- | --- |
| `--workbook` | 待接收的单个 `.xlsx`；扩展名不符、文件不存在都不是文件时拒绝 |
| `--out-dir` | 必须位于 `data\batches` 内、且**尚不存在**的批次子目录；越界、指向 `data\batches` 本身或已存在时拒绝 |
| `--source-description` | 来源描述，**按传入原字符串保存**（含首尾空格与换行）；只用 `strip` 判断是否全为空白。原样记录为声明，不视为已验证事实，也不代表主理人确认了范围或导出条件 |

参数或路径不合法时**在建立批次之前**退出 2，不写任何文件；本入口不覆盖、不自动删除任何旧目录。本卡只用项目内合成数据与既有案例做开发验证，**不接收真实企业材料**。

候审材料里展示来源描述时会做 Markdown 转义（`|`、换行），那只是展示处理；`batch_manifest.json` 中始终保存传入的原声明。

## 2. 每个批次留下什么

```
<data/batches/批次名>/
├─ source/input.xlsx                 ← 原始字节快照（逐字节复制）
├─ checks/quality_report.json        ← 现有 checker 的报告（核验未完成时可以不存在）
├─ logs/checker.stdout.txt           ← 核验器 stdout
├─ logs/checker.stderr.txt           ← 核验器 stderr
├─ code_snapshot/receive_demo_batch.py   ← 本次接收入口源码留档
├─ code_snapshot/check_demo_data.py      ← 本次核验器源码留档
├─ batch_manifest.json               ← 来源、版本、哈希、结果与状态
└─ gate1_packet.md                   ← 开发态候审材料（不是批准记录）
```

四个要点：

1. **原始快照是逐字节复制**（`shutil.copyfile`），不用 openpyxl 重新保存。原始单元格值、类型、Excel 行号因此被完整保留；本任务不另做转换后的数据表。业务核验**只读快照**，报告里记录的 `workbook.sha256` 就是本批次快照的哈希。
2. **复用已验收的 checker**：入口用 `sys.executable` 调用 `scripts/check_demo_data.py` 的 CLI，没有复制它的校验逻辑，也没有修改该文件；不导入生成器、不读取答案册，也不拿旧 `checks/` 或 `evaluation/` 当本批次结果。
3. **不靠 stdout 文本判断成功**：入口记录完整命令行参数、退出码、stdout、stderr，并检查报告 JSON 的存在性、可解析性、`result` 与退出码是否一致、报告中的 workbook／checker 哈希是否与本批次一致。
4. **源码留档**：两个脚本的副本与哈希都进批次，便于回答“这批结果是用哪个版本产生的”。

## 3. 三个状态与退出码

| 状态 | 触发条件 | 接收入口退出码 |
| --- | --- | --- |
| `DEV_GATE1_PACKET_READY` | checker 退出 0，报告结构有效，且输入／快照／代码／报告一致性通过，**且要求的材料都已成功生成** | **0** |
| `BLOCKED_QUALITY` | checker 退出 1（存在质量或范围问题），报告结构有效且一致性通过 | **1** |
| `FAILED_RUNTIME` | 路径、文件、执行、一致性、报告结构或材料写入问题（含 checker 退出 2、报告缺失／无法解析／结构无效／与退出码矛盾、快照与源不一致、代码留档与执行版本不一致、checker 在运行中变化） | **2** |

- `DEV_GATE1_PACKET_READY` **只表示开发候审材料齐备**，不表示质量无问题以外的任何业务结论，也不表示可以进入标准化。
- `BLOCKED_QUALITY` 保留全部诊断材料：快照、报告、日志与问题定位都在批次里，但**不会**变成候审就绪。
- `FAILED_RUNTIME` 若批次已创建，尽量保存失败清单；无质量报告时，候审材料明确写“核验未完成”，未知数量与金额记为 `null`，**不填零、不制造零问题的伪报告**。
- 批次建立之后发生的失败**保留现场**，不删除后重跑；修复后使用新批次。

一致性检查包含：原输入复制前／复制后／核验结束时哈希、快照核验前后哈希、接收入口与 checker 在一次执行内是否保持稳定，以及**两份源码留档是否与本次执行版本逐字节一致**。任何一项不一致都会把批次判为 `FAILED_RUNTIME`（退出 2），而不是成功。

### 3.1 运行失败统一处理（TASK-003-R1 起，R2 收口到收尾阶段）

- 阅读输入、复制快照、计算哈希、创建日志、运行 checker、解析与校验报告、**渲染与写入材料、拼装与提交清单**等任何运行错误，都由入口统一捕获并归为 `FAILED_RUNTIME`（退出 2）。**运行错误不再落成退出 1（那是质量阻断的含义），也不会以未捕获异常中断。**
- 批次已创建且目录仍可写时：保留现场（含部分快照、已生成的报告等），写出 `FAILED_RUNTIME` 清单，记录失败阶段、错误类型与消息、已产生文件的**真实存在状态**与哈希、以及 checker 的实际调用情况；未启动 checker 时不虚构命令、退出码或质量报告。
- 快照只写入了一部分时，清单 `snapshot_written=false`、`snapshot_matches_source` 为 `false` 或 `null`，候审材料不会把它写成完整快照。
- **清单、材料、日志、规格与契约草案的哈希读取都做了兜底**：文件存在但读不到哈希时，保留 `exists=true`、`sha256=null` 并记录 `read_error`，这类情况本身即运行失败；**存在性检查本身失败**时 `exists=null`，文件确认不存在时 `exists=false`，不伪造“不存在”。
- **核验结束阶段的四项哈希都是成功条件**：原输入、原始快照、真实接收入口、真实 checker 在结束时的哈希必须**都取得有效值**，并与复制前／核验前的值相等，才可能候审就绪。读取失败、文件消失或取值未知时，即使值诚实地记为 `null`，也必须判为 `FAILED_RUNTIME`／退出 2——**不允许因为值是 `null` 就跳过一致性比较**；`read_error` 会一并写入失败原因。
- 该条件对 checker 本来退出 1 的批次同样生效：质量问题之外出现一致性读取错误，会**升级为运行失败／退出 2**，而不是继续返回 1。
- 清单采用**原子提交**（先写同目录临时文件，再替换正式文件），避免失败的成功候选清单直接成为正式 `batch_manifest.json`。若首次提交在落盘字节后仍报错：入口会把候审材料一并改写为失败状态，再提交一份 `FAILED_RUNTIME` 清单；两次都失败才只在 stderr 写明失败与现场路径并退出 2。
- **只有要求的材料都成功生成、且全部产物检查通过后，才会出现 `DEV_GATE1_PACKET_READY` 或 `BLOCKED_QUALITY` 清单**；失败时材料也不会残留成功状态。

### 3.2 报告结构校验

接收器只核验自己消费的报告内容，继续复用真实 checker，不复制它的业务校验逻辑。**JSON 解析成功不等于报告有效**：顶层为 `null`、空对象、缺少必需内容都会按 `FAILED_RUNTIME`（退出 2）处理，原报告文件原样保留、不改写、不补造。

必须存在且类型正确的内容（缺什么报什么，不用默认值补）：

| 区段 | 要求 |
| --- | --- |
| 顶层 | 对象；`result ∈ {pass, issues_found}`；`workbook.sha256`、`checker.sha256` 为非空字符串 |
| `structure` | `sheets_found` 为字符串数组；对**实际存在的**四张固定表，`sheet_field_mapping` 必须有对应对象，且包含该表**全部固定字段键**（四表合计 22 个），列号为正整数或 `null`（布尔不算）。缺少某个固定字段键、或该表映射对象为空 → 结构无效；键存在而值为 `null` → 接受（这是 checker 明确给出的“未映射到该列”信息）。工作簿实际缺失某张表时，不要求该表的映射条目，也不因此判成运行失败 |
| `row_accounting` | 必须包含 `suppliers`、`payables`、`payments`、`allocations` 四项，每项含 `source_rows`、`accepted_rows`、`blocked_rows`、`blank_rows`，值为非负整数 |
| `issues` / `issue_counts_by_code` | 前者为数组且条目含 `code/sheet/excel_row/column/value/detail`；后者为对象且值为整数；**合法的空数组允许** |
| `amount_summary` | `known_valid_subtotals_cents`、`complete_totals_cents` **必须存在且为对象**，均含 `payables_payable_amount`、`payments_amount`、`allocations_allocated_amount` 三个键，键值可为整数或 `null`（父区段不允许 `null`、空对象或缺失）；`unusable_amount_cells` 必须为对象并含 `total`／`by_reason`／`sources` |
| `reconciliation` | 必须有 `status`（`ASSESSED`／`NOT_ASSESSED`）与 `known_plus_missing_equals_master`（布尔或 `null`，缺键不算“已提供 null”）；`diagnostic_known_valid_subtotals_cents` 必须是对象 |

另外：报告中的 `workbook`／`checker` 哈希必须与本批次快照／本次执行版本一致，退出码与 `result` 必须一致。**金额里的合法 `null` 继续接受**；质量阻断报告可能包含缺表、缺列与有限数量／金额，只要结构正确就仍按 `BLOCKED_QUALITY` 处理，不会因为业务质量有问题而被误判成运行失败。结构无效的报告不会进入正常材料渲染：材料写明“核验未完成”，不出现“0 个问题”“未记录数据质量问题”之类成功表述。

### 3.3 源码留档一致性

`code_snapshot/` 下两份副本（接收入口与 checker）都会被比对：副本必须存在、可读，且哈希与本次执行版本相等。副本缺失、不可读或不相等，一律 `FAILED_RUNTIME`（退出 2），并在清单中记录比较结果与被比较的哈希。这项检查用于发现普通复制故障与留档可靠性问题，**不宣称能抵御同权限的恶意篡改**，也不是签名服务或权限隔离。

### 3.4 清单对应最终现场，未知值保持未知

- 候审材料**先写入**，再读取它的实际存在状态与哈希，最后才拼装并提交清单——正常与质量阻断批次的 `gate1_packet.exists` 为 `true` 且 `sha256` 与磁盘文件一致。
- 只有要求的材料齐备且全部检查通过，才会宣布候审就绪；清单不给自己算自引用哈希。
- 未知值一律记 `null`，不用默认值冒充已验证事实：

| 字段 | 语义 |
| --- | --- |
| `source.size_bytes` | 未取到真实大小时为 `null`（不用 0） |
| `hashes.<脚本>.stable_during_run` | 两端哈希都有值才比较；任一端未知记 `null`（不因 `None == None` 写 `true`）；但结束哈希未知本身已是运行失败 |
| `hashes.<产物>.exists` / `sha256` / `read_error` | 存在性确认为真、仅读取字节失败时：`exists=true`、`sha256=null`、`read_error` 为真实错误；存在性检查本身失败时 `exists=null`；确认不存在时 `exists=false`。**任何一种读不到哈希的情形都属于所需核验未完成，仍按运行失败处理** |
| `checker_invocation.attempted` | 是否尝试过启动 checker |
| `checker_invocation.started` | 成功完成子进程调用记 `true`；确定没启动记 `false`；无法判断记 `null` |
| `checker_invocation.exit_code` | 未启动时为 `null` |

清单版本随字段语义变化为 `TASK-003-R2-batch-manifest-1.2`；既有批次中的旧清单不迁移、不修正，它们保留当时的现场。

## 4. 为什么候审材料不等于 Gate 1 批准

`gate1_packet.md` 的第一行固定写明：

> **开发态候审材料，未批准，不代表可以进入标准化。**

材料里只展示可核对的事实：批次与来源声明、快照哈希、预期范围与已知限制、工作表与字段映射、四表来源／接受／隔离／空白行数、数据质量结果与来源定位、checker 给出的已知有效小计／完整金额／勾稽状态，以及下一步**拟**做什么。

它**不包含**，也不允许包含：

- 风险等级、AI 审计结论、规则命中或“通过／不通过”的业务判断；
- `gate1_approval`／`gate2_approval` 的批准人或批准时间（清单中两者固定为 `null`，`next_step_allowed` 固定为 `false`，契约状态固定为 `DRAFT_NOT_IN_FORCE`）；
- 任何批准入口或自动继续标准化的命令。

原因很直接：Gate 1 是**人**的动作。程序只能证明“收到哪份文件、核验的是哪个版本、有哪些接收限制、结果来自哪个批次”，不能代替主理人确认范围、导出条件与是否放行。金额栏位里的 `null` 表示“不可得”，不能读成零；主表与分摊是两种观察粒度，金额**不相加**。

## 5. 开发态边界（本卡未做）

- 未实现标准化、SQLite 入库、R01—R04 筛查、AI 建议、正式契约与正式人工守门点。
- 未接入真实 ERP 导出、未验证真实银行证据、未声称兼容特定 ERP 模板。
- 公司、期间、截至日与币种来自规格与任务卡设定，**不能据四张表独立证明主体真实性或业务历史完整性**；真实 ERP 导出时间未知时记为 `null`，不用接收时间冒充。
- 任务二验收记录中的 `task` 显示标签维护项属于非阻断记录，按验收意见**不在本卡修改已验收源码**。

## 6. 针对性验证

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r2_tests_01'
```

验证脚本通过命令行运行真实接收入口，覆盖 **61 个用例**：原 52 例（正向接收、质量阻断、参数拒绝、快照复制故障、来源声明保真、无效报告、代码留档不一致、材料与清单写入失败、收尾哈希读取失败、checker 无法启动、22 份既有 fixture 实跑），R3 新增 9 例——结束阶段四项必需哈希分别不可读（原输入／快照／接收入口／checker）、质量阻断输入叠加结束哈希失败应升级为退出 2、固定字段映射缺键、映射对象为空、缺表时仍为质量阻断、存在性已知但读取字节失败须保留 `exists=true`。

- 参数拒绝、质量阻断、运行失败属于**预期负向案例**，与脚本自身失败分开记录；
- 故障只在内存中替换接收器模块的函数（复制、代码留档、checker 子进程、哈希读取、材料与清单写入）或写在新测试副本上，**不修改真实 checker、项目原输入、既有批次或磁盘源码，也不提供生产故障注入开关**；
- 每次调用（含内存模拟）单独保存 stdout／stderr，`command_log.json` 区分 `cli` 与 `in_memory_simulation` 并统计两者；
- 只读输入（原主文件、22 份 fixture、checker、生成器、规格、契约草案、旧回执、既有验收报告与任务卡）在验证前后哈希不一致、或真实磁盘源码被改动时，整个验证进程返回非零；
- 退出码：0 全部预期成立；1 存在断言失败或完整性失败；2 参数或环境问题。
