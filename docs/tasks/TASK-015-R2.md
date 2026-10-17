# TASK-015-R2：补齐定点验收入口的证据收尾

日期：2026-10-13。唯一新增范围依据 `docs/reviews/REVIEW_TASK_015_R1.md`；TASK-015 与 R1 的业务边界继续有效。

**B1 实现已由 GPT 实际复验关闭。本卡冻结宿主，只修测试证据最终收尾，不重做事实底稿集成。**

## 1. 允许路径与冻结边界

只允许修改既有 `tests/test_fact_packet_demo_workflow.py`，起点 SHA-256：

`3f60cfff088d289358adcb24a4f85fa61787d8245399c921f46f48cc7991af26`。

只新增 `docs/EXEC_REPORT_015_R2.md` 及本轮唯一的新容器：

- `data/workflow_host_tests/task015r2_<唯一>/`
- `data/batches/task015r2_<唯一>/`
- `data/sqlite_tests/workflow_gate2/task015r2_<唯一>/`

不得修改其他既有文件或历史现场。特别冻结：

- 宿主 `scripts/run_demo_workflow.py` = `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`。
- 宿主指南 = `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8`。
- 六个关键冻结件、原任务卡/回执/评审/R1 卡/本卡均不变。

保护基线为 `data/reviews/task015_r1_gpt_20261013_004706/source_hashes_after.json`，按实际文件读数核验项数与哈希，哈希在同目录 `review_result.json` 交付登记。该读数含当前已复验宿主，不表示 R1 证据入口已验收。**相对本基线 changed 只能是本任务测试、missing=0**；宿主必须另核对上述冻结哈希。一次当前扫描即可，不递归反复扫描嵌套历史基线。

不安装依赖、不初始化 Git、不清理历史、不迁移旧凭证；不实施 TASK-016。

## 2. 唯一待修问题

late-controller 产生公开调用记录，但跳过 G7/G8，仍将默认 missing=0/unregistered=0 当作已审计结果输出并成功退出；回执列出的登记表、文件台账和保护产物不存在。新 G7 计数还存在 `item['batch']` KeyError，不能直接打开原分支解决。

复用现有记录和小型函数，使 **late-controller 本卡最终入口** 在成功返回前真实执行下列收尾；不新造通用 I/O 框架、事件系统或大规模测试重构。可提取小型 finalizer，其他旧模式如尚未审计必须明确 scope/未执行，不能用默认零声称通过；本卡不要求为所有模式另跑一轮。

## 3. 收尾与正式判定

### 3.1 调用登记和文件引用

将本次实际收集的 call_registry 独占保存为 `call_registry.json`，保存 CLI/API 记录、文件台账 `evidence_ledger.json`，逐项实读核对存在性和 sha256。核对实际登记表与 CLI/API 记录双向一致；核对 CLI stdout/stderr/return 文件与记录、API return/exception 文件与记录双向一致。异常文件含真实 traceback 与完整链。

missing/unregistered 及哈希不符必须加入本次正式 failures 并影响退出码；不能只保存观察或打印 0。最终摘要要能证明检查已执行，记录适用范围；不检查的字段用 null/未执行说明，不填未测得的 0。

保留一个有限隔离验证：只从审核副本删除一条权威登记（其他真实文件和文件台账不动），真实 audit helper 必须判失败；原件仍通过。只运行证据函数，不因此再建业务链。

### 3.2 本轮现场计数与 receiver/checker

由本次四个现场导出并保存 `scene_outcomes.json`：正常对照 1、晚变更失败 3；复算 MATCHED 4；底稿 READY 报告 4；0007 物理/可解析 4，带失败诊断 3，无失败且恢复成功 1，半写 0。明确：有 READY 报告/完整 0007 不等于整个公开操作成功。

逐批次核对 host_manifest.receive 与 receive_invocation；逐项实读 checker report/stdout/stderr 的 exists+sha256。预期 receiver 启动 4、receiver 内 checker started 且退出0为4；直接 checker CLI 为0，与内部启动次数分列。

修复新计数语句的缺失键及语义：物理文件用 is_file、可解析另计；从真实 crosscheck_report 读取 MATCHED；保留 batch 标识而不引用缺失字段。若保留完整模式的对应新计数，使用已有历史现场对计数/收尾函数做有限只读验证即可，**不跑完整模式**。

进程内核心计数注明实际观察范围。正常对照必须真实调用1次；如果反例调用未做外部观察，不把只包正常路径得出的1称为全部进程内调用总数。子进程内部次数继续为未观察，不推定为0。

### 3.3 正常对照与停止点

复用 R1 定点模式已有四个独立新批次，不增加第五批：三份 JSON 的晚变更仍在本次阻断，stage/退出/异常链准确，撤销 wrapper 及只恢复输入后新进程均退出1；失败事实不删除。

正常 C06b 对照必须把真实完整核心返回、三个保留输入引用的调用前/核心返回后/公开返回后指纹落盘并进入断言：核心1次、输入不变，packet规范JSON与返回严格相等、packet指纹准确、Markdown精确UTF-8字节；不能只记录 calls 或检查公开API返回。

守卫下 status 成功、五个下游命中0、前后批次目录哈希集合不变。逐反例核对所有操作前文件，仅允许故意注入目标在注入期间变化，恢复后全部操作前文件不变；旧0001—0006始终不变。新0007及本层产物不属于操作前文件，不误报其新增。

全部现场无0008；成功对照0007 workflow与0006相等、previous_file_sha256引用正确、revision严格7、operation.kind=BUILD_FACT_PACKET；phase仍DEV_GATE2_APPROVED，真实批准null，next_step_allowed=false。

### 3.4 保护

本轮正确基线扫描、冻结宿主/指南/六件哈希、停止点检查真实执行，保存扫描与比较结果，进入正式 failures。不得沿用旧118788项基线作为本卡基线，也不能只在回执声明手工通过而不保存证据。

以上成功时才输出整个定点验收入口通过。故障/引用缺失/保护失败均返回非零，不能因业务组1/1 PASS跳过后续判定。

## 4. 有界运行与交付

先用现有现场只读检查 finalizer/计数及隔离性质，局部错误定点修正；最后从最终测试代码执行**一次全新容器的 `--only late-controller`**，包含本卡真实收尾。无需再次运行 MAIN、smoke、完整八组、持久化故障组、事实核心21组或TASK-002—014历史入口。

0007半写/完整后sentinel已由GPT通过，宿主未变，本卡只保留证据引用，明确未重跑。原R1与GPT现场一律只读，不补写缺失登记以追认旧入口。

新回执给出源文件最终完整哈希、命令/退出、实际检查清单和正式failures、公开调用与引用计数/来源/scope、正确保护结果、所有产物真实路径及未执行项。修正R1声明与实际不符之处只写在新回执，不改旧回执；注入哈希引用本次最终容器实读值，不混用过程容器。自身哈希只在交接消息给出。

完成后停止本轮实施，交GPT验收。仍停开发态0007；不建立正式契约/真实Gate，不保存人类判断/AI建议，不接网络/LLM/UI。GPT在TASK-015整体验收通过后继续制定下一卡；真实批准和审计判断、DSH关闭均由人类作出。
