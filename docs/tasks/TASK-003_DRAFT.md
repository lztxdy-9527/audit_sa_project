# TASK-003：开发态数据接收、原始快照与批次留痕

日期：2026-10-11；执行端：DeepSeek；架构与验收：GPT；主理人负责转交。

## 1. 当前状态和本次目标

TASK-002（含 R1、R2）已由 GPT 验收通过。已有合成 Excel、22 个小案例、独立答案册及可用的数据质量校验器。不要重做这些成果。

本次把现有校验器接入一个很小的接收流程：指定一份合成工作簿，为它建立全新批次，保存原始字节快照，运行核验，保存版本、哈希及日志，生成一份开发态 Gate 1 候审材料，然后停止。

实务对应：企业提供一份 ERP 导出文件后，审计人员需要知道“收到哪份文件、检查了哪个版本、有哪些接收限制、后续结果来自哪个批次”。文件即使已经规范，也需要这些接收与核验记录。

本卡只做这一步，不做标准化、SQLite 入库、R01—R04、AI 建议、正式契约或人工审批功能。

项目根目录：

    D:\harness work\audit_sa_project

固定解释器：

    D:\harness work\audit_sa_project\.venv\Scripts\python.exe

现有依赖足够，不安装或升级，不初始化 Git。

## 2. 开始前读取

1. docs/reviews/REVIEW_TASK_002_R2.md：任务二通过的范围及冻结版本。
2. 本卡全文。
3. docs/AUDIT_CONTRACT_DRAFT.md 第 2、3 节：快照、批次和守门材料的边界。
4. docs/SPEC_V1.md 第 1、2.1、3.3、4 节：输入、保真、阻断和勾稽。
5. docs/DEMO_DATA_GUIDE.md 第 6 节及 checker 的 CLI／报告结构。

任务一由 GPT 写入，任务二由你完成，GPT 负责验收。旧计划不作为施工依据。正式契约仍为草案，本卡开发运行不代表主理人批准了任何业务批次。

## 3. 只允许新增的文件

- scripts/receive_demo_batch.py：接收入口。
- tests/test_receive_demo_batch.py：针对性集成验证，仅用标准库和现有依赖。
- docs/BATCH_RECEIVE_GUIDE.md：操作、产物、状态及边界说明。
- docs/EXEC_REPORT_003.md：实际执行回执。
- data/batches 下的全新子目录：本次接收批次及测试批次，可创建必需父目录。

除这些新增成果外全部只读。不得修改已验收 checker、原回归脚本、生成器、规格、契约草案、任务卡、旧回执、答案册或既有数据／证据。

任务二摘要中的 task 显示标签问题已被 GPT 记录为非阻断维护项，本卡不要为它修改旧代码。

## 4. 接收入口与输出

### 4.1 CLI

receive_demo_batch.py 接受三个必需参数：

- --workbook：指定单个 .xlsx 文件，不递归扫描目录。
- --out-dir：data/batches 内尚不存在的批次子目录。
- --source-description：非空来源描述，作为声明原样记录，不视为已验证事实或人类批准。

输出目录越界、是 data/batches 本身、已存在、输入不存在或参数无效时，退出 2，并在建立批次前停止。不得覆盖或自动删除旧目录。

本卡只用项目现有合成数据和案例运行开发验证，不接收真实企业材料。

### 4.2 每个新批次的产物

    source/input.xlsx                  原始字节快照
    checks/quality_report.json         现有 checker 的报告，读取失败时可以不存在
    logs/checker.stdout.txt            核验器 stdout
    logs/checker.stderr.txt            核验器 stderr
    code_snapshot/receive_demo_batch.py
    code_snapshot/check_demo_data.py   本次源码留档
    batch_manifest.json               来源、版本、哈希、结果与状态
    gate1_packet.md                    开发态候审材料，不是批准记录

原始快照必须逐字节复制，不能用 openpyxl 重新保存后称为原始文件。原始单元格值、类型、行号均由字节快照保留；本任务不另做转换后的数据表。

调用项目现有 checker 的 CLI，输入必须为本批次 source/input.xlsx，报告必须写入本批次的新路径。不得复制 checker 的业务校验逻辑另写一套，不读取答案册决定质量是否通过。

用 sys.executable 启动 checker，保存实际完整参数、退出码、stdout 和 stderr；不靠搜索 stdout 中的“通过”判断成功，必须结合退出码及落盘 JSON。

### 4.3 一致性与失败处理

- 记录原输入复制前哈希、复制后／核验结束时原输入哈希，以及快照核验前后哈希；成功批次这些值必须一致。
- 记录接收脚本、checker、SPEC_V1 和契约草案的哈希，并保存两个脚本副本。执行过程中 checker 若变化，或报告中的 workbook／checker 哈希不符，标为运行失败，不能出成功状态。
- checker 退出 0 时必须有新报告且 result=pass；退出 1 时必须有 issues_found 报告。报告缺失、格式无效、退出码与内容矛盾等情况按运行失败处理。
- checker 退出 2 或无法启动时，保留已创建的快照和日志，记录失败；不能制造空报告或零问题数。
- 已创建批次后的失败保留现场，不删除后重跑。同一问题修复后使用新批次。
- 不导入生成器、不读取 evaluation 或旧 checks 文件作为本批次的核验结果。

## 5. 清单和候审材料

batch_manifest.json 至少包括：

- manifest_version、batch_id（使用输出目录名）、UTC 接收时间、mode=DEVELOPMENT_ONLY。
- 原输入路径、文件名、大小、source_description；无法获知真实 ERP 导出时间时为 null，不拿接收时间冒充导出时间。
- 预期公司、期间、截至日、币种、合成开发场景声明；明确这些来自规格／任务卡，不能声称从四表独立证明了公司及全部历史完整性。
- 第 4.3 节的输入／快照哈希；接收脚本、checker、规格、契约草案的路径和哈希。
- 实际 checker 命令、退出码、报告／日志／代码副本的相对路径及存在状态；报告存在时记录其哈希。
- 契约状态 DRAFT_NOT_IN_FORCE；gate1_approval=null、gate2_approval=null、next_step_allowed=false，不伪造批准人或批准时间。
- 本次接收结果及错误原因，采用下面三个状态。

固定状态与入口退出码：

- DEV_GATE1_PACKET_READY：checker 退出 0，且输入／快照／代码／报告一致性通过；接收入口退出 0。仅表示开发候审材料齐备。
- BLOCKED_QUALITY：checker 退出 1 且一致性通过；接收入口退出 1。保留全部诊断材料。
- FAILED_RUNTIME：路径／文件／执行／一致性问题；接收入口退出 2。批次已创建时尽可能保存失败清单；创建前参数拒绝不生成批次。

gate1_packet.md 固定写明“开发态候审材料，未批准，不代表可以进入标准化”，并展示：

1. 批次、来源声明、快照哈希、预期范围与已知限制。
2. 实际工作表、固定字段映射，以及四表来源／接受／隔离／空白行数量，引用本次报告，不编造缺失值。
3. 数据质量结果、主要问题及来源定位、完整报告和日志位置。
4. checker 提供的已知小计、完整金额和勾稽状态；null 表示不可得，不能填零。主表与分摊金额不相加。
5. 下一阶段拟做标准化与入库，但本卡不执行；当前没有人类批准。

无质量报告的 FAILED_RUNTIME 材料应明确写“核验未完成”，未知数量和金额不可填成零。公司和范围属于任务设定／来源声明，不能写成真实性或完整性已被证明。

不生成风险等级、AI 结论或规则命中；不提供 approve、自动批准或继续标准化命令。正式 Gate 1 操作和正式契约将在后续单独任务中处理，本卡不宣称已实现人工守门点。

## 6. 必须实际执行的验证

新增测试脚本通过 CLI 运行实际接收入口，读取新批次产物并断言。提供 --out-dir 指定 data/batches 下全新测试容器，所有输入副本、批次和日志均放在该容器内，不覆盖历史。

至少验证以下情况：

1. C01 有效输入：退出 0；原输入未变；快照字节哈希相同；报告检查的是快照；状态 DEV_GATE1_PACKET_READY；批准字段为 null、next_step_allowed=false；完整金额仍为 500000 分。
2. 主演示文件：退出 0，四表数量 20／993／1000／1005，保留未知 AP 的资金部分，形成完整新批次。
3. C14a 缺列、C14c 金额不可解析：分别退出 1，状态 BLOCKED_QUALITY；保存快照／原问题／有限金额，不能变成候审就绪。
4. 无法读取的 .xlsx：在新测试容器中准备一个并非有效工作簿的文件，退出 2；保留接收后已有证据，状态 FAILED_RUNTIME；不得生成零问题的伪报告。
5. 同一输出路径再次调用：退出 2，已有批次全部文件前后哈希一致。
6. 输出越界、输出为 data/batches 本身、输入不存在：均在写入前退出 2。越界负向目标选项目下不存在的测试路径，验证未创建；不要使用系统目录或覆盖既有文件。
7. 原始快照一致性失败：仅在全新测试批次中模拟复制出的快照与源字节不一致，入口退出 2、状态 FAILED_RUNTIME、next_step_allowed=false。可在内存加载接收模块后模拟复制故障，不修改真实源文件或磁盘源码。

测试失败必须使整个测试进程返回非零，包括只读输入哈希不一致；不能再出现“发现完整性问题但总体成功”。每次调用日志单独保存。

测试前后核验原输入、checker、生成器、规格、契约草案和旧回执哈希。参数拒绝、质量阻断、运行失败属于预期负向案例，和测试脚本自身失败分开记。

接收示例命令（目录存在时换新后缀）：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' --out-dir 'D:\harness work\audit_sa_project\data\batches\dev_receive_003_main_01' --source-description 'TASK-003 开发验收：现有合成 ERP 导出演示文件，来源描述尚不构成人类范围确认'

测试示例命令：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_tests_01'

可以在测试脚本内统一执行主文件和边界检查，不额外重复跑一遍任务二的 50 例；本卡不得修改 checker，确有新问题时报告 GPT，不自行返修旧源码。

## 7. 说明、回执与停止

BATCH_RECEIVE_GUIDE.md 说明实际文件怎样接收、为什么保留快照、批次怎样关联报告与版本、三个状态分别代表什么，以及开发候审材料为什么不等于 Gate 1 已批准。

EXEC_REPORT_003.md 记录新增文件、实际命令与退出码、批次路径、测试断言结果、输入／旧文件保护结果、失败尝试和未解决问题。完整命令可附机器可读日志，数量从实际结果计算，未执行不得写成通过。

不要代主理人审定契约、批准 Gate 1／Gate 2 或填写职业判断。主理人当前只作转交，不需要模拟审批。

相同问题三次仍失败或上下文不足时，保存日志、实际完成点、未解决项和下一条待执行命令后停止，不自行扩展业务。

完成上述四份源码／文档交付与开发批次后停止，返回 EXEC_REPORT_003.md 的完整路径和简短摘要，等待 GPT 验收。不要提前标准化、入库、写筛查规则或继续下一张任务。
