# TASK-015-R1：修复事实底稿构建收尾漏验Gate2磁盘文件

日期：2026-10-13。依据 `docs/tasks/TASK-015_DRAFT.md` 与 `docs/reviews/REVIEW_TASK_015.md`。原卡业务范围、冻结核心、协议和开发态0007停止点继续有效；本卡只修B1，不重新实现底稿或推进后续任务。

## 1. 已确认问题与授权路径

GPT实际复现：最后一次真实控制器动作检查返回后，仅给normalized.json追加LF，build_dev_fact_packet仍错误返回READY；撤销wrapper后新进程status退出1，恢复原件后退出0。构建收尾的Gate2三项比较使用旧gate2_outputs读数，缺少对应磁盘实读；不是需要改业务规则或控制器的矛盾。

允许修改：

- `scripts/run_demo_workflow.py`，起点 `707cd16ecf9ebeefba2e459f3e468ae3379459adc5cbf426bfb394173eedb75d`。
- `tests/test_fact_packet_demo_workflow.py`，起点 `5f7dacfa07f54587dc835a0e5462470a6638178b5cb642c01af55d491cad9c0d`。
- `docs/WORKFLOW_HOST_GUIDE.md`，起点 `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8`，只更新受影响说明，非必改。

只新增 `docs/EXEC_REPORT_015_R1.md`、本轮全新 `data/workflow_host_tests/task015r1_<唯一>/`、`data/batches/task015r1_<唯一>/`、`data/sqlite_tests/workflow_gate2/task015r1_<唯一>/`。其余既有文件和历史现场全部冻结，包括原TASK-015卡/回执、本卡/验收记录、六个关键冻结件、所有上游/SQL/规格/契约草案。不得安装依赖、初始化Git、迁移凭证或清理历史。

本轮保护读数为 `data/reviews/task015_gpt_20261013_001516/source_hashes_after.json`，以实际文件读数/项数为准，**只允许上述三个既有文件变化，missing=0**。本读数冻结未通过验收的当前交付，不是已验收声明。一次当前扫描即可，不重复扫历史嵌套基线。

## 2. 定点实现要求

在build_dev_fact_packet最后一次必要控制器检查与最后一次必需数据消费之后、成功返回之前，重新实读并比较本次实际消费的Gate2 normalized.json、load_report.json、artifacts.json及数据库字节；预期来自**操作开始时已绑定的同缓冲读数**，不能从末尾新读数产生新预期，也不能用旧缓存自身相等充当复测。

继续覆盖同次消费的筛查/复算/底稿文件、宿主清单、静态绑定、0001—0007，以及各层失败/未完成/未知项状态。复用已验收的小型收尾helper或直接明确检查；不新造I/O观察框架、事件状态机或全面重构。不要因此退化status、丢掉0005/0006各自的核验读数或把链尾operation混用于上游摘要。

Gate2磁盘变化应为WorkflowHostBlocked / 退出1并指出目标文件；已创建本层现场后如实保存fact_packet失败诊断，不返回成功。即使0007已经完整写入，后续恢复仍须尊重有效失败诊断。只恢复被改输入不能清除失败事实，不自动删除/重试/补签。

核心接口、八个CLI、现有协议版本、workflow与0006相等、真实批准null、next_step_allowed=false等均不变。实现版本可作必要补丁升级并在指南/回执明确；所有演示从最终代码创建新批次，旧批次绑定不迁移。

## 3. 有界复验

新增明确的定点模式（如 `--only late-controller`），只执行以下受影响检查；不要再次完整跑MAIN、八组、事实核心21组或TASK-002—014历史入口。

1. 新C06b正常完整链至0007：真实核心1次、完整返回单份保存，packet/规范指纹/Markdown准确落盘，三个输入同一引用前后不变；公开构建及新进程status均成功，五个下游函数守卫下status仍只读成功。已通过的金额/上下文业务不重造预期。
2. 最后控制器检查后晚变更：先在正常调用中直接观察真实动作检查位置；只包装真实check_dev_action，先调用原实现，最后一次直接构建动作检查真实返回后，单次更改一个Gate2文件磁盘字节，原返回对象原样返回。以normalized.json为主复现；load_report.json和Gate2 artifacts.json各做一个同类有限对照（每项独立本轮新批次，避免复用失败凭证）。可以追加一个LF，不改对象/金额，不同步任何哈希。不能把注入放到早期读取或下一次status才发现。
3. 每个反例本次API必须WorkflowHostBlocked且指出相应文件，并留下准确fact_packet阶段、退出1、完整原因链；撤销wrapper后的新进程status仍退出1。只恢复原输入后应**仍因有效failure退出1**，不要删诊断来凑恢复成功；另一个未注入正常新批次提供退出0对照。旧0001—0006及非故意注入文件的前后哈希不变，所有注入前后字节/哈希、命中及真实控制器返回留痕。
4. 证据仍经统一公开API/CLI记录，文件引用实读核验并进入正式failures；正确本轮保护比较、冻结哈希和开发态停止点进入正式判定。0007半写/完整后sentinel的真实writer方法及此前正常场景已有GPT实际通过证据，保留引用并明确本轮未重跑；只有修复实际触及那些路径才定点补验。

本轮只要求一次全新容器最终定点入口。局部测试断言/观察错误先定点处理，勿反复整套建链。GPT反例脚本见 `data/reviews/task015_gpt_20261013_001516/run_targeted.py` 的after_controller和 `late_gate2_controller_probe.json`；复用注入原则，不复制其完整建链脚本或依赖硬编码调用次数。

## 4. 非阻断证据事项及回执

原交付两项计数分类有误：matched_reports_total实际数packet READY（7），真实复算MATCHED为10；half_written_vouchers最终筛出完整后throw而非partial。GPT已独立补证，不另设验收阻断。可在本卡修改测试时改为清晰的复算MATCHED/事实包READY/0007物理文件、可解析、半写、有效失败/已恢复成功分列，并保留scope；不据旧名称宣称错误分类正确。原隔离性质也已由GPT严格单条registry删除补证，非必重跑项。

新回执给完整源文件哈希、实际定点命令/退出码、B1关闭证据、输入/旧链保护、真实异常/CLI原文、实际调用计数及其来源、正确保护基线、失败尝试和未解决项。回执最终自身哈希仅写交接消息，不回写旧回执或追求自指。给本轮测试容器/批次父目录/SQLite父目录三条绝对路径。

完成后停在开发态0007，交GPT验收，执行端不实施后续任务、不建0008、不保存人类判断/AI建议、不建立正式契约或真实Gate。GPT在验收通过后按主理人持续授权制定下一卡；业务决定和真实批准仍由人类作出，DSH由人类操作。
