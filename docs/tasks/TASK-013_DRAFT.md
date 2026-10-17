# TASK-013：把只读规则筛查接入开发批次

执行：DeepSeek；架构与验收：GPT；主理人负责转交。本卡可交执行。项目根目录：`D:\harness work\audit_sa_project`。**只完成本卡，提交回执后停住。**

## 1. 先读什么，当前已经做到哪里

先读 `docs/reviews/REVIEW_TASK_012_R2.md`、本卡、现行 `WORKFLOW_HOST_GUIDE.md`、`RULE_SCREEN_GUIDE.md`，再看宿主、控制器和筛查核心公共接口。需要查前序时读 TASK-012_DRAFT/R1/R2 与 TASK-011 的验收记录；历史回执不能替代现行接口。

GPT 本轮只验收并写本卡，没有替你实现任务十三。TASK-012-R2 仅修复测试和指南；**宿主实现仍是 TASK-012-workflow-host-1.1**，其 Gate2 决定实现已验收。现在宿主实际完成：

`start → Gate1 显式模拟 APPROVE → 真实标准化/SQLite → Gate2 pending → 显式模拟 APPROVE/HOLD/REJECT → 0004 → status 恢复`

规则 SQL、筛查核心、独立复算、事实底稿已分别开发验收，但当前宿主没有调用后三个模块。本卡只接入第一个：**只读规则筛查**。独立复算与可读事实底稿的宿主接入留下一张卡，不混入本次。

## 2. 对应实务场景与交付目标

澄明商贸有限公司 2026 年 9 月人民币办公耗材采购付款；截至日固定为 2026-09-30。

数据已核验并入库，开发态 Gate2 模拟 APPROVE 已记录。审计人员运行一次异常筛查，得到可回查原始 Excel 行与退款证据的规则线索 JSON。R01—R04 是待核实线索，不自动认定损失、舞弊、控制缺陷或审计调整，跨规则金额不相加。HOLD/REJECT 不得执行筛查。

本卡增加：

```text
全新批次 → 显式模拟两次 APPROVE → 合法 0004 / DEV_GATE2_APPROVED
→ screen-rules 真正调用冻结 screen_sqlite
→ 保存 screening_report / artifacts / 0005
→ 新进程 status 只读恢复 → 停住
```

**0005 是宿主筛查完成凭证，不是新的控制器批准或新阶段。**控制器不修改，workflow 仍为 DEV_GATE2_APPROVED、模拟决定恰为 2；新增独立宿主完成项 `RULE_SCREEN`。只完成 SCREEN_AND_BUILD_FACTS 动作中的筛查部分，不宣称整个动作或项目完成。

`mode=DEVELOPMENT_TEST_ONLY`、`contract_status=DRAFT_NOT_IN_FORCE`、真实 gate1/gate2 approval 恒为 null、next_step_allowed=false、真实批准 0。此阶段不生成 AI 候选结论，不预填人类判断。

## 3. 文件、版本和冻结范围

仅改两个既有文件：

- `scripts/run_demo_workflow.py`
- `docs/WORKFLOW_HOST_GUIDE.md`

只新增：

- `tests/test_screen_demo_workflow.py`
- `docs/EXEC_REPORT_013.md`
- 全新 `data/workflow_host_tests/<新容器>/`、`data/batches/<新父目录>/` 与既有规则推导的 `data/sqlite_tests/workflow_gate2/<新批次相对路径>/`。

生产逻辑继续在既有宿主内实现，不新增生产模块。源文本编译检查，不生成 pyc。无需安装依赖、初始化 Git、重造业务数据、接入真实 ERP、OCR、RAG、UI、网络或压测。

所有上游核心、SQL/schema、SPEC/契约草案、合成 Excel/答案册、所有旧测试、任务卡、回执、验收单、GPT 证据、旧批次和数据库一律不改、不删、不覆盖。尤其冻结本轮 `test_record_demo_gate2_decision.py`，不要为新范围修改旧断言或运行旧入口制造假失败。

起点完整 SHA-256：

- 宿主：`dc6e53db794322082c14c37ff3da09118f90f01361c0d517aa78e3562bd360a6`
- 指南：`dbf4b573b58f9dd6e222f18205fa06c54c88b28706d56e41673ab1fa4b315ac8`
- TASK-012 旧测试：`184ccb39a7ab9e1b624000d49317d2417484f1c451a62d4cbcc36f61c2aa2564`
- 筛查核心：`1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe`
- 控制器：`a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`

其余完整冻结哈希见本轮 QA `acceptance_summary.json`。主保护基线：`data/reviews/task012_r2_20261011_180955/source_hashes_after.json`，**只允许宿主与指南两项既有文件变化，其余 0 变化、0 缺失**。早期基线累计差异按各自授权集合报告，新增文件不计作既有文件变化。

实现版本改为 `TASK-013-workflow-host-1.0`。既有 host-manifest/checkpoint/gate2-artifacts/gate2-failure 的协议版本仍保持 TASK-012 的 1.0，不能因实现升级盲目重命名；新增筛查协议使用本卡固定版本。指南准确区分实现与协议。最终代码固定后创建全新批次，不迁移、补签或复用旧代码绑定批次。

## 4. 新增接口及真实调用顺序

保留五个既有 API/CLI 的含义。唯一新增：

```text
screen_dev_batch(batch_dir) -> dict
screen-rules --batch-dir <本版新建且 Gate2 模拟 APPROVE 的批次>
```

不提供任意数据库路径、截至日或自定义规则参数。数据库沿用 Gate2 固定推导路径。

依次执行，不能跳过前提：

1. 调用共用恢复核验。必须连续合法 0001—0004、当前恰为 DEV_GATE2_APPROVED；接收材料、代码/SQL/配置/规格/契约草案绑定、Gate2 normalized/load_report/artifacts/数据库全部有效，无准备失败或未完成状态。HOLD、REJECT、pending、早期阶段、旧版本、已有 0005 或筛查现场目录在新增写入之前拒绝。
2. 用**重新实测**的 current_bindings 调冻结 `check_dev_action(..., "SCREEN_AND_BUILD_FACTS", ...)`；要求 simulation_allowed 严格为 bool true。动作允许来自控制器，不只比较 phase 字符串。此声明不等于真实批准。
3. 保存操作开始时的全部既有 checkpoint、manifest、Gate2 产物、数据库与静态绑定哈希。独占创建 `workflow/screening/`，写 `started.json`；关闭后读回。已有目录不能接管、覆盖、清空或自动重试。
4. 使用已验证、本次实际读取的 `load_report`，真正调用冻结 `screen_sqlite(推导数据库路径, load_report, cutoff_date="2026-09-30")` **一次**。不得自行编写 SQL 或 Python 规则替代核心，不读答案册/生成器/测试预期。
5. 独占保存 `workflow/screening/screening_report.json`，关闭后读回，严格与核心实际返回相等；保留全部 findings、整数分、相关 ID、完整 source_rows/entities/cells/related_refunds 与规则/勾稽/统计字段，不能压缩成数量摘要。
6. 核验报告声明的数据库前后哈希相等且等于宿主本次实读数据库哈希；开发态、版本、截至日、load_source 与本批次来源/normalized/database 绑定一致；报告必需容器/字段/枚举/类型不完整即阻断。此处只检查接口协议与来源绑定，**不重新实现 R01—R04 算法或独立复算**。
7. 写筛查 `artifacts.json`，再写 `0005.json`。两者关闭/读回并按下节协议恢复核验。不得修改 0001—0004、manifest、接收材料、Gate2 产物或数据库。
8. 在最后一次必要控制器调用之后，完成最终复测；所有已消费文件与初始值/本次真实 writer 返回值一致才输出成功。返回实际 phase、RULE_SCREEN 完成项、0005 和报告引用、各规则命中数；不自动调用下一模块。

新批次 MAIN 应从本批次实际快照和数据库计算，不得复制旧模块测试的报告来冒充调用。

## 5. 筛查产物与 0005 恢复协议

新增 `workflow/screening/` 只允许以下文件：

- `started.json`：`TASK-013-screen-start-1.0`，batch_id、宿主版本、操作种类、开始时间、来源 0004 初始字节哈希、实测运行绑定指纹。
- `screening_report.json`：冻结核心完整原始返回对象。
- `artifacts.json`：`TASK-013-screen-artifacts-1.0`。
- 可选 `failure.json`：`TASK-013-screen-failure-1.0`。

artifacts 至少存：batch_id/host_version、固定相对报告路径及其**实际文件字节 SHA-256**、报告**规范对象 SHA-256**（字段分别命名）、started 文件哈希、0004 初始文件哈希、manifest 文件哈希、normalized/load_report/Gate2 artifacts 文件哈希、normalized payload 指纹、数据库固定推导路径及实读 SHA-256、实际筛查核心完整哈希/版本、四份 SQL 哈希、截至日、实测运行绑定指纹、Gate2 模拟 APPROVE 决定正文指纹。对决定正文计算指纹时剥离保存的 `decision_sha256`；不得自引用。

0005 顶层沿用现有 checkpoint 字段，revision 严格 int 5；previous_file_sha256 为初始实读 0004 哈希。`operation.kind=RUN_RULE_SCREEN`；保存 at_utc、固定 artifacts 路径与**实际文件字节哈希**、规范对象指纹、报告文件哈希、绑定指纹、phase_after。完整 workflow 与 0004.workflow **严格相等**，不要向控制器 history 注入自造事件，不增减请求或决定。

共用恢复入口允许连续 0001—0005；0005 仅对应本次筛查，未知项、目录、跳号、半文件、0006 一律拒绝。status 重新核验全部引用、版本/类型/路径语义及实际字节，显示 RULE_SCREEN 完成；**status 不重新调用筛查核心、不写文件**。已有 0005 后重复 screen/prepare/决定均拒绝且文件不变。

每个被读取对象与文件哈希来自**同一次字节缓冲**。最终复测的预期值只能取自初始缓冲或本次真实 writer 结果，不能事后重新读取覆盖。最终复测包含：0001—0005、manifest、接收材料与静态绑定、Gate2 三份 JSON 与数据库、screening started/report/artifacts，以及 failure/未知文件状态。在最后一次控制器调用后重新实测静态绑定。

恢复不依赖路径里含 MAIN/Cxx 等测试标签，也不引用答案。`actions_simulated_allowed` 可以继续如实显示控制器动作允许，另用宿主 `completed_actions` / `screening_status` 表明筛查已完成且不能重复；不把允许动作伪写为实际执行全部 SCREEN_AND_BUILD_FACTS。

## 6. 失败分类与恢复

沿用 `WorkflowHostBlocked`/退出 1（前提、协议、绑定、不允许动作）和 `WorkflowHostError`/退出 2（I/O、规则核心运行失败、意外程序异常），保留阶段、字段路径、原因与原始异常链。`RuleScreenBlocked` 对应 1，`RuleScreenError` 对应 2；不要把 0 条线索当运行失败。

操作开始前的拒绝不创建 screening。开始后任何失败尽量独占保存 failure，记录版本/batch_id/宿主版本、阶段、原始异常类别、完整原因、目标退出码、已知产物引用。不得删除已有文件、补造成功报告或重试。

**筛查失败标记优先于完整 0005。**与 Gate2 准备阶段一致：完整 0005 后才抛错，本次失败且 failure 留痕；后续所有共用恢复入口先验证 failure 协议，再复现失败类别/阶段/原因，不得恢复 READY。failure 本身非法 JSON/错版本/缺必需键/非文件时协议阻断，不能跳过。started 存在但无完整合法成功集合且无可用诊断时为未完成阻断。失败诊断写不出也不得报告成功，保留原始错误链与现场。

正常成功集合不应含 failure。失败/未完成批次不能继续、改签或补跑，需新建批次。以上是本地开发恢复协议，不声称断电持久性、并发锁、身份认证或同权限防篡改。

## 7. 有界验收测试

新入口使用项目 Python `-B` 和全新容器。无需运行历史整套测试。以下分组足够，不加无边界 fuzz；组数、调用数全部按实际记录，不能为凑数硬编码。

1. **MAIN 完整链**：真实 start/Gate1 模拟 APPROVE/prepare/Gate2 模拟 APPROVE/screen。筛查调用前已落盘有效 0004；核心实际调用 1；报告 12 条（R01/R02/R03/R04=3/5/2/2），R02 唯一应付超额 1,600,000 分。settled PAY 267,949,329、退款 700,000、资金净额 267,249,329=已匹配 266,249,329+缺关联 1,000,000 分；缺关联不误拦。宿主保存的报告与该次核心返回逐项严格相等。独立新进程 status 得到同一报告引用且不再次筛查，真实批准仍为 null。
2. **三种正向边界**：既有 C03 合并付款（无命中且总额不翻倍）、C07b 部分未匹配（R03 保留）、C06b 部分退款（退款实体与净额保留）。只读既有合成 Excel，各从新批次走真实流程；核对关键字段与已验收案例口径，不生成新 Excel。
3. **阶段与重复**：Gate1/pending、Gate2 pending/HELD/REJECTED、已有 0005、已有失败/未完成筛查现场、旧批次/越界路径均拒绝，核心调用 0、拒绝前后文件不变。HOLD/REJECT 仍可正常只读 status。重复执行不能新增 0006。
4. **报告与引用**：从正常批次建立登记副本，有限探针分别改报告字节、artifacts 引用、0005 前序/workflow、关键类型。若为了进入目标语义核验而同步外层指纹，只同步新副本并留痕；必须命中目标字段，不能只得到更早的任意阻断。可合并检查，无需穷举每个金额字段。
5. **真实失败现场**：一个真实生产 writer 部分写入故障，捕获其实际完整待写 text、UTF-8 字节数/哈希、实际部分文件字节、sentinel cause、旧 0001—0004 调用前/关闭后哈希；另一个完整 0005 写完后抛 sentinel，failure 优先恢复，新进程 status 退出 2；非法 failure 一项对照退出 1。不得用占位对象代替完整 text。
6. **最终复测**：三个有界探针，在最后一次控制器检查真实返回后分别改变本次 0005（提交入口）、数据库（status 入口）、输入快照（status 入口）。每次命中 1，**本次即拒绝**；撤销 wrapper 后新进程也拒绝。对比值取于调用前与句柄关闭后，正向未变化控制通过。
7. **只读与隔离**：数据库筛查前后字节哈希一致，旧产物全部不变；status 守卫下不写、不启接收/标准化/装载/筛查/网络。宿主与实际调用筛查核心均无答案册/生成器读取，无 crosscheck/fact/LLM 调用；不能仅靠裸词搜索误判路径绑定表，按导入/调用 AST 与有界运行守卫核对。
8. **真实计数与证据读回**：下节逐项落实，缺/多记录必须让正式组 FAIL 与入口非零，隔离自测另存。汇总与明细最终一次保存后读回逐项核验，不能先写成功再补计数。

既有三种模拟决定、缺失应付关联保留、严格类型、旧链重放、写后复测协议不能放宽。测试可以直接保存这次真实核心返回用于精确比较；不得预先伪造成功报告再传给宿主。测试不读答案册，MAIN/三个既有小样固定预期仅属于测试。

## 8. 留痕、计数与回执

保存 summary/checks/counts、各 CLI 原始 stdout/stderr 与真实命令/退出码、公开 API 入口事件、控制器/标准化/装载/筛查的进程内实际入口事件、接收调用记录与 checker 身份、登记副本来源、故障调用完整参数/返回或异常链/真实 before-after/后续 CLI、writer 完整待写字节与原始证据。

公开 API、私有造样、控制器造样/重放、各核心实际调用、复制、故障、模拟决定、真实批准分别计。抛错前已经进入的真实调用照计；副本不冒充接收/筛查；CLI 内部未观测填 null，若推导另列依据，不冒充实测总数。模拟决定按验证后的原始记录口径说明，不能用固定 0 代替未统计。

接收启动登记与 `receive_invocation.json` 双向一一对应；checker 按各接收身份 `started` 留痕。筛查亦按实际入口/已保存调用记录一一对应，不能只比总数。共用审计规则的 missing/unregistered **进入当前正式组 problems**，并证明少一条、多一条均令正式判定 FAIL/退出非零；自测隔离，不向正式 failures 塞假失败。

负向断言同时要求异常类别和目标原因；完整异常/traceback 与完整实参另存，不用 200/240 字符摘要替代。每份引用 JSON 读回核对，分别记规范内容指纹与文件字节哈希。最后按最终对象一次保存 summary/checks/counts/events 后读回比较再决定退出码。

回执必须给出：修改/新增文件完整哈希、准确版本、真实执行命令及失败尝试、分组/调用/故障分类、保护差异、未测边界和下列**三条完整路径**：测试容器、批次父目录、外置数据库父目录。至少指明 MAIN screening_report 和 0005 路径，便于 GPT 直接复验。

## 9. 完成与停止

完成后停在 **DEV_GATE2_APPROVED + RULE_SCREEN 已保存**；HOLD/REJECT 保持停止态。不新增 0006，不执行独立复算、可读底稿、人类判断、AI 建议、正式契约或真实批准，不推进 TASK-014。等待 GPT 独立验收。

如冻结接口与本卡有实质矛盾，记录具体字段/阶段和可复现材料，停在受影响部分；不要自行修改业务规则、上游核心或批准口径。
