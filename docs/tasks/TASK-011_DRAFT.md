# TASK-011 草案：实际标准化、SQLite 装载，停在 Gate2 待确认

执行：DeepSeek；架构与验收：GPT；主理人转交本卡。根目录：D:\harness work\audit_sa_project。

**本卡可交执行。只完成本卡，回执后停住等 GPT 验收。**先读 docs/reviews/REVIEW_TASK_010_R4.md、本卡及下面列出的现行指南。不要根据旧回执猜测现行接口，不提前推进下一任务。

## 1. 已完成什么，本次增加什么

业务是澄明商贸有限公司 2026 年 9 月人民币办公耗材采购付款的合成 ERP 导出数据。接收/质量核验、标准化、SQLite、四规则、独立复算、事实底稿、纯控制器均已分别验收。TASK-010 最终宿主 v1.3 已通过，具备真实接收、Gate1 待确认、显式模拟决定和只读恢复；目前没有执行下游标准化/装载的命令。

本次在**新的宿主版本、新建批次**上增加唯一动作：

    start → Gate1 pending → 显式模拟 APPROVE
    → prepare-gate2（真实标准化、真实装载、保存材料）
    → DEV_GATE2_PENDING → 停住

实务对应：财务导出 Excel 被接收核验；主理人模拟确认接收范围后，程序保留原值并转成标准数据，把数据入库，核对数量、金额和来源；再把完整核对材料提交 Gate2 待确认。缺失应付关联仍是保留的业务事实，不能为了勾稽把它删除。

本轮仍全部 DEVELOPMENT_TEST_ONLY，契约 DRAFT_NOT_IN_FORCE；gate1_approval/gate2_approval 均 null，next_step_allowed=false。模拟流程不等于主理人真实批准。

## 2. 修改范围与必读文件

仅允许修改两个既有文件：

- scripts/run_demo_workflow.py：以最终 v1.3 为基础增量扩展。
- docs/WORKFLOW_HOST_GUIDE.md：同步新版本、协议、目录及命令。

只新增：

- tests/test_prepare_demo_gate2.py
- docs/EXEC_REPORT_011.md
- 全新 data/workflow_host_tests/<task011容器>/、data/batches/<task011父目录>/、data/sqlite_tests/workflow_gate2/<新批次相对路径>/。

如确需一个新的生产辅助模块，应先在回执中说明设计原因并停在受影响部分，不擅自扩大交付范围。本卡设计可在现有宿主内完成。

以下既有测试、任务卡、回执、GPT QA、旧批次、旧数据库、合成 Excel/答案册及所有上游均不改：
tests/test_run_demo_workflow.py、control_demo_workflow.py、receive_demo_batch.py、check_demo_data.py、normalize_demo_data.py、store_demo_sqlite.py、screen_demo_sqlite.py、crosscheck_demo_rules.py、build_demo_fact_packet.py、schema/规则 SQL、SPEC、契约草案。

必读现行文件：

- docs/WORKFLOW_HOST_GUIDE.md
- docs/WORKFLOW_CONTROL_GUIDE.md
- docs/NORMALIZATION_GUIDE.md
- docs/SQLITE_LOAD_GUIDE.md
- scripts/control_demo_workflow.py 的 Gate2 材料核验及公共 API
- scripts/normalize_demo_data.py、scripts/store_demo_sqlite.py 的公共 API

冻结基准（前缀仅便于识别，执行时保存完整哈希）：
控制器 a6b7b8e1、接收器 52195620、checker a7e5eb67、标准化 a2bae49e、装载器 1abfad89、schema 7e0c6463、筛查 1b123766、复算 8fe75bfe、底稿 f4998d92、SPEC 5df632ed、契约 af405cb6。
本轮起点宿主 d42aeec3、指南 2c164eff、旧宿主测试 852bf336。

主保护基线：
data/reviews/task010_r4_20261011_125204/source_hashes_after.json。
相对该基线只允许宿主和指南两项既有文件变化，其余 0 变化、0 缺失。更早基线涉及历史授权变化，应区分累计变化，不照抄“全部 0”。不重跑历史测试去覆盖旧现场。

## 3. 新版本、接口与路径决策

新宿主/清单/ checkpoint 协议明确升版，例如：

- TASK-011-workflow-host-1.0
- TASK-011-host-manifest-1.0
- TASK-011-checkpoint-1.0

现有 start/status/record-simulated-decision 的命令与公共函数签名保留；record 仍只接受 Gate1 的一次显式模拟决定。新增：

    prepare_dev_gate2(batch_dir) -> dict
    prepare-gate2 --batch-dir <新批次>

新版本只接收自己创建的新批次。旧宿主版本、普通纯接收批次均明确拒绝；不修改、不迁移、不重签、不替旧产物补建批准。宿主代码变化导致旧绑定失效是预期行为。新版本发布后用固定代码重新创建测试批次，不在批次执行中继续改代码。

**装载器保持冻结，采用其现有开发输出范围。**固定数据库路径由宿主推导：

    data/sqlite_tests/workflow_gate2/<batch相对data/batches的完整路径>/audit.sqlite3

例如新批次 data/batches/task011_01/main_01 对应
data/sqlite_tests/workflow_gate2/task011_01/main_01/audit.sqlite3。

不能仅使用叶子 main_01，避免不同父目录碰撞。不让调用者提供任意数据库路径；解析并检查仍在固定根下。目标库、.staging 或该次输出目录已存在时，在业务 API 调用前拒绝，不覆盖、不删除、不换名续跑。

这个数据库是批次关联的开发数据库，暂时位于批次目录外。这是保留冻结装载器的明确架构选择；不声称生产部署已完成。禁止修改 SQLITE_TESTS_ROOT、猴子补丁放宽装载路径、复制装载逻辑，或把数据库移动/复制进批次后改写报告冒充原路径。

## 4. 真实执行顺序

prepare_dev_gate2 必须按下列依赖顺序执行：

1. 共用宿主恢复入口，完整核验接收材料、host_manifest、0001/0002 链、冻结控制器和当前磁盘绑定。当前必须恰为合法 Gate1 APPROVE 的 0002；pending/HOLD/REJECT、旧版本、绑定变化均先拒绝。
2. 用重新实测的 current_bindings 调用冻结 check_dev_action(...,"NORMALIZE_AND_LOAD",...)，要求 simulation_allowed 严格 true。不从 phase 字符串直接推导授权。
3. 检查固定输出路径与全新准备目录。先以独占 mkdir 创建 workflow/gate2/，作为本次尝试已经开始的标记。已有尝试不重试、不复用、不自动删除。
4. 使用本批次 source/input.xlsx 和 checks/quality_report.json，**实际调用** normalize_workbook(workbook_path, quality_report)。不接收外部 normalized 文件，不重用测试容器结果，不再读外部原 Excel。
5. 保存完整 normalized.json，关闭、读回、核对完整对象、文件字节哈希及规范对象指纹。整数分/字符串 ID/完整 cells 原样保存，不为展示改写数据。完整材料采用文件保存，不把数千行数据打印到 CLI stdout。
6. 把本次实际标准化返回对象传入冻结 load_normalized_to_sqlite(normalized, 固定新数据库路径)，真实建库、核对、提交、关闭、发布；保存完整 load_report.json 并读回核验。真实 API 未成功返回时不能生成“装载通过”报告。
7. 实读最终数据库字节算哈希，与本次 load_report.database_sha256 相同；normalized 对象规范指纹等于 normalized_payload_sha256；report.database_path 等于宿主推导的实际路径。核对输出源哈希/代码哈希与原绑定一致，不允许上游返回与批次无关的产物。
8. 独占保存 artifacts.json，记录固定相对路径、实际文件字节哈希、normalized 规范指纹、数据库字节哈希、版本/批次/前序 checkpoint 哈希、Gate1 模拟决定指纹。每个摘要指向实际本次完整对象。
9. 从旧 0002.workflow 调用冻结 prepare_dev_gate(...,"GATE2", materials, current_bindings=再次实测绑定)。scope 延续本批次合法范围/来源描述，blocking_issues=[]，evidence 是**本次完整 normalized + load_report**。Gate2 的 prior_simulated_decision_sha256 必须由控制器绑定本 workflow 的已验证 Gate1 APPROVE 正文实际指纹。
10. 写入新 0003.json，完整保存控制器返回；关闭/读回，重新验证下节协议、材料、数据库字节与所有输入/代码绑定，核验旧 0001/0002 前后字节不变，才宣布成功并返回 DEV_GATE2_PENDING。

输出文件是后来产生的，**不要加入创建时 run_bindings 并改写它**。静态输入/代码绑定保持创建时值；新产物通过 artifacts.json → 0003.operation 的文件哈希引用及 Gate2 materials 指纹绑定。

整个动作只运行标准化和装载，不执行筛查、复算、底稿。prepare-gate2 是显式开发命令，APPROVE 的保存动作仍不自动触发它。

## 5. 落盘协议与失败

成功布局：

    <new-batch>/workflow/
      host_manifest.json                 # 创建后不回写
      receive_invocation.json + logs     # 保留原协议
      checkpoints/0001.json              # Gate1 pending
      checkpoints/0002.json              # 显式 Gate1 模拟决定
      checkpoints/0003.json              # 只可为 PREPARE_GATE2 / Gate2 pending
      gate2/
        normalized.json
        load_report.json
        artifacts.json
        failure.json                     # 仅失败时尽力保存，不与成功共存

0003 允许且仅允许从合法 Gate1 APPROVE 0002 延续，不允许从 pending/HOLD/REJECT 越过来。revision 为实际 int 非 bool，前序/manifest 字节哈希、批次、版本、操作种类、artifacts 实际文件哈希、materials 指纹、Gate1 决定指纹与完整 workflow 互相一致；旧 history/请求/决定完整保留。

恢复 0003 时，实读固定 normalized/load/artifacts/数据库路径，不跟随清单读任意路径；重新核对字节/对象/材料绑定，再从 0002.workflow 与这些本次实际材料调用纯 prepare_dev_gate 复算**完整预期返回**，与 0003.workflow 严格比较。不能只看 phase、哈希或“有文件”。重放不再执行 normalize_workbook/load_normalized_to_sqlite。

status 支持新的合法链 0001、0001+0002、0001+0002+0003；未知/跳号/半文件/目录/0004/非法操作一律拒绝。对于 Gate2 pending，明确 output.action_checked 与允许动作对应，NORMALIZE_AND_LOAD 不再允许，SCREEN_AND_BUILD_FACTS 仍不允许；真实 next_step_allowed=false。不得仅沿用旧状态文案说“本次未执行标准化”来描述已经完成的历史事实，应区分本次 status 没有执行与该批次已完成的动作。

一旦 workflow/gate2/ 已开始存在但没有**完整有效的 0003**，status 必须说明准备未完成/失败并拒绝继续，不能忽略它退回旧 APPROVED 状态。prepare 重复调用始终拒绝，不“发现旧报告后接着跑”。失败后保留全部已产生文件和 staging，需新建批次；本卡不做恢复重试。

异常分类延续退出码 0/1/2：
- 前提/协议/普通变化：WorkflowHostBlocked，exit 1。
- 文件/标准化/装载的运行失败：WorkflowHostError，exit 2，保留原异常链及阶段。
- 上游自己的 Blocked 与 Error 按各自语义映射，不笼统把所有错误叫质量不通过。

failure.json 尽力独占保存实际失败阶段、异常类别/原因、已观察到的输出状态与路径，不填假的成功报告/哈希/rollback。若诊断本身写不成，stderr 说明；不能声称已保存。status 在完整失败诊断可读时恢复其 1/2 与原因；半文件/缺诊断的未完成尝试以协议阻断，不猜测成功。接收失败的原有 host/receiver 两层分类、真实命令和声明三态继续保留。

0003 写完后的核验发现变化，也不得宣告成功或更新旧绑定；保留失败现场并让以后 status 拒绝。宿主不声称断电持久性、多进程锁或同权限安全隔离。

## 6. Gate2 口径

沿用控制器，不自己放宽 Gate2 条件：

- normalized 1.1、store 1.2、schema 1.0，开发态与 next_step_allowed=false。
- 完整质量无未解决问题，来源哈希和实际 normalized 指纹绑定。
- DEV_SQLITE_VERIFIED、round_trip_exact、event_allocation_balanced，foreign_key_check=clean、integrity_check=ok，六项 net_checks 严格 true。
- 四表行数是实际非负 int 非 bool/float，与标准化记录数相等；金额严格整数分，逐项一致。
- 主表付款=付款分摊、主表退款=退款分摊，资金净额=已知应付关联净额+缺失应付关联净额。主表与分摊金额分别核对，不相加。
- 缺失应付关联非零可正常提交 Gate2，不认定企业没有发票，也不能改成数据质量阻断。

MAIN 已验收的固定核对值仅用于开发测试：四表 20/993/1000/1005，已结算付款 267949329 分，退款 700000 分，资金净额 267249329 = 266249329 + 1000000 分。它们不是宿主硬编码的通过条件；小样不同金额仍应通过。

## 7. 有界验证与留痕

先 compile 源文本，用项目 .venv Python -B/禁写 bytecode。在新测试入口保存自己的完整 stdout/stderr、完整 CLI 参数/退出码/API 入参引用与返回或异常，按真实调用统计。只读现有合成 Excel；不生成数据、不读答案册，不重跑任务二至九整套测试，不要求无边界 fuzz。

至少完成这些验证：

1. MAIN：新 start → 新进程 status pending → 显式模拟 APPROVE → 新进程 prepare-gate2 → 新进程 status Gate2 pending。真实调用标准化/装载各一次，材料/数据库实际哈希、全套数量金额核对、Gate1 前序绑定、完整 workflow 重放一致；旧 0001/0002 在调用前后取哈希且字节不变。正常记录 Gate1 决定时下游调用仍为 0。
2. 一组小样 C02：真实正常流程到 Gate2，不使用 MAIN 金额当通过条件；验证整数、来源、往返。另以 C07b 合法部分未匹配小样证明缺失关联仍保留并可提交；如路径名称不同，先从既有 fixture 清单核对，不猜文件名。
3. pending/HOLD/REJECT 分别 prepare 被拒绝，标准化/装载调用均 0；质量坏例 C12 真实 start 阻断，没有下游调用；原接收运行失败/H02 声明不可读行为选一个有限回归，真实 receiver 退出码不得被宿主改造。
4. Gate2 已 pending 后重复 prepare、record Gate1 决定或提交 Gate2 决定，均拒绝且文件字节不变，无 0004；旧版本/普通接收批次和数据库路径冲突提前拒绝。对旧版本仅使用本轮专供测试的新副本，不改历史批次。
5. 新测试副本分别改 normalized、load_report、数据库字节，以及 0003 前序/操作摘要，status 全部给出目标原因。另在新副本同步文件哈希后破坏 normalized_payload_sha256 或 Gate1 前序指纹，证明恢复不是只核外层哈希。不能更改真实冻结代码或历史数据库。
6. 有限错误：上游标准化拒绝一项、装载运行失败一项；wrapper 必须调用真实上游或明确标注测试内依赖故障，记录命中次数。失败无可用 Gate2 请求，现场保留，status/重复 prepare 不继续。不能靠故意错误的目录形状冒称底层 write 已命中。
7. 对 0003 的真实 writer 做一次有限部分写入 OSError：捕获该次完整 text，记录完整 UTF-8 字节数/哈希、实际部分字节、opens/write/raise 命中、异常链、调用前后旧 0001/0002 哈希、后续 status 拒绝。完整 text 副本用 newline="\n" 保存，或明确区分 Windows 换行转换后的文件哈希；不要复制已被纠正的占位下界。沿用已验收 writer，不增加生产测试开关。
8. 一项写后源快照/新产物变化探针，成功不能先返回；status 守卫证明只读、不运行子进程/标准化/装载/网络，前后文件字节一致；静态及适当运行期守卫证明未调用筛查/复算/底稿/LLM，也未读取生成器或答案册。
9. 最终 summary/checks/日志/计数由同一最终对象保存、读回后输出，落盘后不改计数。receiver/checker/normalize/load/control/公开 API 与测试造样分开；副本不能算新接收，阻断前未调用不能算调用。负向同时匹配异常类别及具体目标原因，helper 自测独立不污染正式 failures。

保留 TASK-010 的接收、失败留痕、模拟决定、绑定核验、不可覆盖与只读原则。旧 test_run_demo_workflow.py 是冻结历史验收入口；新版本多了实际下游动作，不能为让它的旧静态范围断言通过而改旧测试或隐藏功能。新入口必须覆盖本卡要求的 Gate1 关键回归，并如实说明未重跑旧整套测试。

## 8. 指南、回执与停止

指南写清新增可复制 prepare-gate2 模板、全新批次要求、版本变化、外置开发数据库固定路径、成功/未完成/失败状态和不可续跑策略。示例仅 SIMULATED_HUMAN/SIMULATED_TEST_ONLY；来源文字只作数据，无默认 APPROVE、无 AI 预判。

EXEC_REPORT_011.md 列完整哈希、两项修改/新增路径、实际调用与退出码、独立金额/数据库字节核验、重启恢复、负向目标原因、真实 writer 证据、保护结果、失败尝试及未执行项。没有执行的检查不写通过。不得将“Gate2 pending”写成“Gate2 已放行”。

完成后停在 DEV_GATE2_PENDING，返回路径与简短回执。**不实现或提交 Gate2 决定，不跑 R01—R04/复算/底稿，不建正式契约，不签真实 Gate，不保存人类判断，不生成 AI 建议，不推进 TASK-012。**主理人本轮只转交卡片和回执，无需人工检测或签署批准。

