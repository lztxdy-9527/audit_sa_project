# TASK-017：开发态宿主保存模拟独立初判

日期：2026-10-13。供人类转交DeepSeek。GPT负责架构/验收，执行端负责本卡实现/测试/调试，人类负责真实判断、真实批准和DSH操作。

## 1. 目标与边界

将TASK-016/R1已验收的冻结纯核心接入宿主，接收调用方显式提供的模拟初判，独占保存并生成0008，支持只读恢复。顺序固定：合法0007事实底稿 → 显式模拟提交 → 保存模拟记录；不自动生成或预填任何判断。

本卡只支持SIMULATED_HUMAN / SIMULATED_TEST_ONLY。保存模拟初判不等于真实人类独立初判已保存，更不表示身份认证、审计完成或真实Gate批准。不能从聊天、测试答案册或事实金额代填assessment/reason；允许暂不能判断及调用方原因。

**停止在开发态0008 / SIMULATED_INITIAL_JUDGMENT_RECORDED。** 冻结控制器不扩展；phase仍DEV_GATE2_APPROVED，0008.workflow与0007严格等值，真实批准null、next_step_allowed=false、AI仍不允许。无0009、AI/LLM/网络/UI/ERP、终判、正式契约或真实Gate；不修改冻结packet及其“尚未保存人类判断”banner。

## 2. 允许路径与冻结

允许修改且仅修改两个既有文件：

- `scripts/run_demo_workflow.py`，起点 `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`。
- `docs/WORKFLOW_HOST_GUIDE.md`，起点 `ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8`。

只新增：

- `tests/test_initial_judgment_demo_workflow.py`
- `docs/EXEC_REPORT_017.md`
- 本轮唯一的 `data/workflow_host_tests/task017_<唯一>/`、`data/batches/task017_<唯一>/`、`data/sqlite_tests/workflow_gate2/task017_<唯一>/`。

其余既有文件及历史现场冻结，包括本卡、全部规格/契约草案/SQL/上游/控制器/旧测试/回执/评审。重点冻结：

- 新纯核心 `scripts/build_demo_initial_judgment.py` = `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`。
- 纯核心测试 = `c0ef730e59ad78f54d7d60014289ea56ca7e79c764f9afba515c1c77449b62f3`。
- 纯核心指南 = `2bbaa876ae7a76175f3462d9395b7bbc8e4bec5b1631030ff3fe32142d0286f5`。
- 控制器 `scripts/control_demo_workflow.py` = `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`。
- 事实核心 = `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`。
- TASK-015宿主测试 = `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`。

保护基线为 `data/reviews/task016_r1_gpt_20261013_023714/source_hashes_after.json`，文件哈希和项数见同目录review_result.json。changed只能为宿主与宿主指南，missing=[]、读取错误0；单次扫描复用。不得安装依赖、初始化Git、清理历史、迁移或重签旧批次；哈希不替代版本恢复点。

## 3. 固定接入接口与新核心绑定

宿主版本升 `TASK-017-workflow-host-1.0`。新增公开API：

`record_simulated_initial_judgment(batch_dir, submission) -> dict`

新增第九个CLI：

`record-simulated-initial-judgment --batch-dir <batch> --submission-file <json>`

既有八个CLI保留。CLI一次读取UTF-8 JSON为对象并调用同一公开API；本层保存接收到的submission对象快照，**不宣称保存了外部提交文件的原始字节**。JSON排版可以按既有writer序列化，所有字符串值须完整保留。CLI不产生默认提交，不补事件ID/身份/发生时间/assessment/reason。

真实核心恰调用一次：

`build_initial_judgment_record(batch_dir.name, packet, submission, expected_packet_sha256=<0007已核验的packet规范指纹>)`

仅传上述字符串/内存对象，不传DB路径、SQL、答案册、生成器、工作流或核心额外输入；不改纯核心。不为恢复status再次调用核心；不在宿主重写一套判断校验算法。

**新核心从批次start就绑定**：在宿主现有HOST_BOUND_PATHS增加固定`initial_judgment_core`路径，实测哈希保存在bindings.host_code_sha256.initial_judgment_core。复用宿主整体绑定及规范指纹核验；保留冻结CONTROLLER_CODE_KEYS和控制器八项code_sha256协议，不往其代码键中插入第九项，不改控制器。实际控制器保留run_bindings中宿主扩展并比较整体指纹，初判核心的实读和语义校验仍由宿主负责。

旧批次缺该绑定或宿主代码不一致时如实拒绝；全部演示从最终宿主新建，不给历史产物补签。新核心自身协议仍是TASK-016-initial-judgment-record-1.0 / submission-1.0。

## 4. 固定落盘与操作顺序

新层目录固定为 `workflow/initial_judgment/`，仅含：

- `started.json`
- `submission.json`（传入对象的保存快照，未补可选字段/未改写原文）
- `initial_judgment.json`（**核心完整返回外层**，恰为record/record_sha256）
- `artifacts.json`
- 失败时才有 `failure.json`

新协议分别为 `TASK-017-initial-judgment-start-1.0`、`TASK-017-initial-judgment-artifacts-1.0`、`TASK-017-initial-judgment-failure-1.0`。本层stage固定`initial_judgment`。既有TASK-012/013/014/015协议不改名；不得出现隐式AI草稿、渲染判断页面或修改原事实Markdown。

按以下顺序执行，复用小型helper，不新造I/O观察框架或全面重构：

1. 共用恢复核验整条链与上游，**当前恰为合法0007**，含完整MATCHED及事实底稿；phase严格DEV_GATE2_APPROVED，无有效失败/未完成/未知项。0001—0007预期来自各次初始同缓冲读数。已有本层目录、已有0008或任何重复操作一律拒绝，不覆盖/不接管/不自动重试。
2. 确认静态绑定含start时实测的新核心哈希且仍一致。冻结控制器继续验证当前workflow/bindings；显式检查GENERATE_AI_SUGGESTION真实返回simulation_allowed严格false并保留实值。该false表示AI未开放，**不是对本次模拟记录保存的授权结论**。初判保存由本卡授权与宿主0007前提约束，不捏造新的控制器action，也不把SCREEN_AND_BUILD_FACTS许可改名成初判许可。
3. 从同一读取缓冲取得packet对象及文件字节哈希，与0007的初始packet规范指纹、文件指纹、artifacts及source绑定比较；核验所消费的上游及数据库实读一致。对submission取调用开始时规范指纹，保留原引用；轻量预检batch_id/packet指纹/模拟身份及事件唯一性，错误时在建目录前拒绝。事件ID不得复用当前workflow.history/已有模拟Gate决定的event_id。具体文本/备注/协议校验由冻结纯核心执行，不自行生成或修正字段。
4. 独占创建本层目录并保存started：绑定batch_id、宿主/核心版本及实测代码哈希、host_manifest和run_bindings指纹、0007初始文件哈希、packet文件与规范指纹、submission初始规范指纹、必要上游引用。宿主记录时刻at_utc与调用方occurred_at分列，不用前者替代后者。独占保存submission快照并同缓冲读回，必须与本次消费对象规范等值。
5. 真实调用一次冻结核心；调用前/核心返回后/公开返回前按保留的同一对象引用核验packet/submission指纹，不回写输入。Blocked映射宿主退出1，Error或意外/I/O映射退出2，保留原因链，调用方明确stage。
6. 核验返回外层恰两键；record协议/状态/来源/原文与本次输入相符，record_sha256正确；字段集按冻结核心指南固定，不默许未知字段/漏项；五项null、next_step_allowed/ai_suggestion_allowed严格false。source批次、packet规范指纹、entity、四项来源和finding_ids按原序准确；可选键规范化按冻结核心，不将省略键与空列表误判为原文改变。保留完整本次返回指纹作后续写入预期。
7. 独占保存initial_judgment完整返回，读回严格规范相等；再保存artifacts并读回，最后保存0008。UTF-8无BOM、明确LF，文件字节哈希来自本次writer返回/写前明确字节，逻辑规范指纹另列；不能用读回的新对象产生新的正确答案。所有固定路径、协议字段及内嵌artifacts逐项核对，不只看状态字符串。
8. 在最后一次必要控制器检查、最后一次摘要读取或数据消费之后、返回成功之前，**实读磁盘复测**本次消费的静态绑定/宿主清单、Gate2三份JSON与DB、筛查/复算/事实底稿产物、新层四份产物、全部0001—0008；预期来自初始读数或本次writer返回。再次确认无新增失败/未知项，保留输入及完整核心返回未变。不得用缓存同自身比较，不得靠下次status才发现本次晚变更。

不得以循环验证追求抵御任意时点并发篡改；只承诺上述明确观察点和不可变材料核验。

## 5. artifacts、0008与成功摘要

artifacts至少完整绑定：固定协议/路径、batch_id、host/core版本/哈希、run_bindings/host_manifest、0007路径和初始哈希、packet文件/规范指纹、submission文件/规范指纹、started文件哈希、输出文件哈希/record规范指纹、submission_event_id、actor_kind/simulation、固定开发态状态及null/false边界。路径必须为本批次固定路径，不信任文件自报的任意绝对路径。

0008继续使用既有checkpoint外壳：revision严格整数8，previous_file_sha256等于本次初始实读0007哈希，operation.kind=`RECORD_SIMULATED_INITIAL_JUDGMENT`，operation完整内嵌artifacts及其文件指纹/固定引用。**workflow与0007严格规范JSON等值**，不追加控制器history、simulated_decisions、请求、审批或新phase；初判的event_id仅作为本层提交事件保存，不冒充Gate决定。

合法链扩展至0001—0008；0005/0006/0007始终按各自operation及初始读数验证，不能把新的链尾operation拿作上游摘要。拒绝0009、序号跳跃、半文件、未知文件/目录。已有0008禁止再次提交，即使换event_id也不覆盖；本卡不支持修订、撤销、合并、多份初判或自动重试。

成功API/status保留此前筛查/复算/事实包摘要，新增`initial_judgment_status=SIMULATED_INITIAL_JUDGMENT_RECORDED`及已核验文件引用/record指纹/模拟事件摘要；completed_actions只增加`SIMULATED_INITIAL_JUDGMENT`。可标明已保存模拟记录，不能写HUMAN_INITIAL_JUDGMENT_SAVED、AI_READY或“主理人已初判”。record本身仍为冻结VALIDATED协议，不修改其纯核心边界文本来冒充身份认证。

real_approvals=0，真实批准null、next_step_allowed=false；AI许可必须为冻结控制器实际false。其既有原因文案即使未区分模拟/真实组件也不改冻结控制器，指南说明边界即可。不要篡改actions_simulated_allowed的真实值；SCREEN_AND_BUILD_FACTS的既有许可与“宿主禁止重复执行”分列。

## 6. 失败恢复与只读status

有本层现场后失败要独占保存failure，含固定协议、batch/host/core绑定、stage=initial_judgment、异常类别/消息/原因、exception_chain（cause/context）、target_exit_code及观察到的产物状态，并读回核验。不覆盖已存在诊断；诊断保存也失败时保留原始原因，不返回成功，不清理现场。

**共用恢复先读取和核验有效failure，再解析checkpoint链**，避免半写0008遮蔽运行失败；有效失败事实优先于物理存在的完整0008。核心/协议阻断返回1，I/O或意外运行失败返回2，不让上游默认stage误标本层。无有效failure但有未完成现场时如实拒绝，不补签/续写。只恢复被故意改坏的输入不能清除已经保存的失败事实；不删failure凑成功。

status只读恢复，不能调用normalize_workbook、load_normalized_to_sqlite、screen_sqlite、verify_rule_facts、build_fact_packet或build_initial_judgment_record；不得为了验证保存的记录再次运行纯核心。用保存凭证/输入快照/严格协议/指纹/来源核验恢复，完整记录内嵌的原文及绑定必须与已保存submission和0007一致。

status可调用冻结控制器检查动作，但不能写入文件、事件/访问时间或新诊断。0001—0007仍正常恢复且未保存模拟初判；0008才标记本层完成。status在最后一次摘要读取和控制器动作检查之后仍须复测本次消费的磁盘材料，不能新增尾部读取漏验。

## 7. 有界验证

先用C06b正常小样和一个必要前提反例验证接线；局部错误定点修正。最终入口为 `tests/test_initial_judgment_demo_workflow.py --out-dir <全新容器>`，只做本卡必要的有限检查，最后一次完整最终容器从最终代码创建；不反复整套建链。可提供定点子集，若作为最终交付，仍须真实执行本子集证据/保护收尾。

1. **MAIN正常接入**：一次真实建链至0007，12条、3/5/2/2、R02超额1600000分保留；提交测试显式模拟文本后至0008。实际核心恰1次、两输入保留引用三时点不变、完整真实返回单份保存并与输出严格相等；原submission快照准确，record规范指纹/文件指纹分列，0008.workflow/前驱/边界正确。既有各阶段status可在同一条建链中有限检查，不重复另建完整MAIN。
2. **前提与小样**：C03零条可保存暂不能判断/调用方原因，不自动判无问题；早期（含0006）、HOLD、本层目录已存在、重复0008拒绝且旧文件不变。绑定不符batch_id/packet指纹、真实HUMAN身份、复用Gate事件ID等可在同一个合法0007正常提交前做只读预检反例，避免为每项反复建链。至少一个通过轻量预检但由真实核心拒绝的空白reason负向，准确保存本层failure且无成功0008；另一个受控InitialJudgmentError映射退出2，说明注入层级，不把替身调用声称为真实核心执行。
3. **有限持久化故障**：两个独立新C06b场景，0008真实writer半写和完整写后sentinel。半写不得替换整只writer，以真实独占open句柄上的单次write注入；观察模式x/UTF-8/LF、命中1、实际半写字节、完整待写字节及哈希读回一致。新进程status均退出2，stage正确、异常链完整，旧0001—0007字节不变。完整0008后抛错也不能被恢复当成功。
4. **晚变更**：一个独立新C06b，在写后最后一次真实控制器检查返回之后，仅为已消费fact_packet.json追加LF、不改内存/不同步哈希；本次公开保存即Blocked1并指向目标，撤销wrapper后的新进程status1，恢复原件后仍因有效failure退出1。另在本轮正常成功批次中，包装最后一次新记录摘要读取，先返回原对象后单次更改initial_judgment.json；本次status即拒绝且不写诊断，撤销该探针并只恢复原件后status0，旧0001—0008不变。精确观察真实位置，勿硬编码全局第N次读取/控制器调用。
5. **绑定与协议反例**：明确start时已有initial_judgment_core宿主绑定，操作前/后实测一致。用本轮新批次的声明副本做有限核心绑定/固定路径或内嵌artifacts字段篡改，status准确拒绝；只撤销探针注入，不改真实核心/上游文件、不删有效失败事实。无需重新跑纯核心全部协议/时间/指纹边界反例。
6. **只读恢复**：正常0008在六个真实下游函数被换成“计数后抛错”守卫时，公开status成功且命中全0、批次及外置DB哈希集合不变；新进程CLI成功。记录本层核心与公开API实际调用数，status不得偷偷调用新的纯核心。
7. **证据、保护和停止点**：全部公开API（包括造样和守卫那次）/CLI调用登记完整返回或异常、真实traceback/链、预期退出；台账实读哈希、登记表和CLI/API原文双向核对、missing/unregistered进入正式failures。receiver/checker由现场各批次真实启动记录导出，直接CLI与内部启动分列；未观察子进程核心次数为null。现场计数按scope分列物理/可解析0008、有效失败、无失败恢复成功，不把有文件称为成功。正确本轮基线只宿主/指南变化，冻结件一致、无0009/AI/真实判断/批准。全部检查结束后保存最终checks/summary，不遗漏最后一项。

不要求TASK-002—016历史整套入口、冻结TASK-013/014/015宿主测试、TASK-016完整纯核心七组或事实核心21组；本卡新正常链仅为接线和恢复提供必要证据。不要把已有QA自报或未运行测试当成GPT实际复验。

## 8. 交付与验收

指南明确九个CLI、显式模拟输入格式、host专属核心绑定、固定文件/指纹口径、0008工作流未变、失败优先恢复、旧批次不迁移、无修订/重试、AI真实false及真实人类判断仍未实现。不写生产默认判断模板；测试样本文本醒目标注模拟用途。

新回执给完整最终源文件哈希、命令/退出、逐项检查证据、真实核心和公开调用计数及scope、最终failures、正确保护比较、失败尝试/未解决项，以及本轮测试容器/批次父目录/SQLite父目录三条绝对路径。回执自身最终哈希只给交接消息，不回写自指或历史回执。

业务/来源绑定错误、伪判断/批准、失败误报成功、未真实调用核心、改冻结件及影响验收结论的证据错误阻断；旧文案/已补证辅助计数如实登记，不为非阻断事项重复整套回归。业务口径矛盾交GPT/人类，不自行改规格。

执行端完成后停止本卡实施，不做下一任务。GPT验收通过后按主理人持续授权继续制定下一卡；真实Gate、真实审计判断及是否建立正式契约由人类明确决定。DSH关闭由人类操作。
