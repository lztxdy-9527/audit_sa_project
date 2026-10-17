# TASK-017-R1验收及TASK-017整体关闭记录

日期：2026-10-13；验收端：GPT。

结论：**通过。TASK-017与TASK-017-R1技术验收完成，可由人类在DSH关闭两卡。** B1最后一次新层读取后的收尾和B2真实纯核心观察均已独立复验关闭。下一卡为 `docs/tasks/TASK-018_DRAFT.md`；GPT未操作看板、未修改实现或冻结文件。

验收仅到开发态0008 / SIMULATED_INITIAL_JUDGMENT_RECORDED。phase仍DEV_GATE2_APPROVED，0008.workflow与0007严格等值，真实批准null、next_step_allowed=false、AI不允许；真实人类独立初判尚未保存，正式契约/真实Gate/AI建议/终判尚未提供或批准。

## 1. 最终交付身份

实读SHA-256与交接一致，复验前后保持：

- 宿主 `scripts/run_demo_workflow.py`：`3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`，TASK-017-workflow-host-1.1。
- 测试 `tests/test_initial_judgment_demo_workflow.py`：`c5b31cd798dbbb72759ae94ec65217e28ff86c453947c59cf074ed1dfa651c05`。
- 宿主指南：`856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8`，R1未改。
- R1回执：`3554f2b77cfdd47c061fffde2af5287cc1de6a479e7a192a7bb8567dccb949f4`。

初判纯核心 `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`、控制器 `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c` 及其他上游/旧测试/历史现场保持冻结；完整保护比较见下文。

## 2. 证据层级与实际复验

执行端最终容器为 `data/workflow_host_tests/task017r1_run_02`，自报2/2 PASS。GPT实读源文件和对应证据，独立重读40个引用（30份CLI原文、9份API/映射记录、1份完整真实核心返回）、39行文件台账及registry双向对应；全部文件存在且SHA匹配，异常traceback/链完整，严格单删一条registry的隔离证据有效。

GPT另实际运行交付定点入口 `--only r1` 一次，经 `data/reviews/task017_r1_gpt_20261013_041026/run_review.py` 启动，**退出0、2/2 PASS、failures=[]**。新测试容器 `data/workflow_host_tests/task017_r1_gpt_20261013_041026`；新批次和SQLite使用同名根，仅一个新C06b，建链到0008。没有重跑MAIN/零条、完整七组、保存晚变更、0008 writer两场景或历史任务入口。

独立观察使用宿主实际加载的冻结纯核心代码帧，不依赖测试自身计数；另观察record_api实际调用的公开宿主代码帧及每次批次文件树。实际公开宿主API **8次**、纯映射helper **1次**、登记记录 **9条**、真实纯核心 **1次**，CLI **15次**；子进程内部核心次数未观察，记null。正常保存核心1次；重复/只读status/四个晚变更/守卫核心0。

本轮新容器39个API/CLI文件引用也经独立实读SHA核对。证据包括 `review_execution.json`、`real_core_observation.json`、`public_api_observation.json`、`delivery_audit.json` 及实际入口产物；没有将执行端自报或既有证据读取称为GPT新运行。

## 3. B1关闭

源码最终本层复测位于后续事实底稿/复算/筛查/Gate2/DB/宿主清单/0001—0008/静态绑定消费之后，返回字典之前。初始预期补齐submission规范指纹及record指纹；四文件实读、record外层及规范指纹、0008内嵌artifacts、submission/started交叉一致和0008初始字节均复核；新增对象读取后再作有限字节确认与无failure检查，没有用新读数替换初始凭证。

实际无注入status观察到新层输出helper读取2次。四个反例分别在第二次返回原对象之后，仅向started.json、submission.json、initial_judgment.json、artifacts.json追加LF；**本次API均WorkflowHostBlocked**，消息准确指向目标。撤销wrapper保留变更后，新进程status均退出1；仅恢复目标原件后均退出0；只读status未写failure。

独立逐次文件树观察确认：每个晚变更调用只改变故意目标，0001—0008及所有非故意目标字节不变；重复和正常/守卫status没有新增或改变文件。正常保存未改操作前旧文件。四个场景复用本轮同一新批次，恢复原件，不修改冻结历史。

六个下游真实函数抛错计数守卫下status成功、命中全0，真实初判核心帧0，批次与外置DB字节不变。该结论限明确测试消费点，不宣称对任意时点并发篡改具有事务隔离。

## 4. B2关闭

RealCoreObserver绑定HOST.INITIAL_JUDGMENT_MODULE实际函数，只观察真实调用，不改入参/返回；保存观察文件在测试层完成。GPT独立代码帧计数与其真实核心1次一致，未把status或前提拒绝算成核心。

捕获的两个实际入参引用在调用前、纯核心返回后、公开保存返回后三时点规范指纹相等：本轮packet为 `e4dae1204449f419cc7edca321b089a6412529837cf343ce4c313761f64971c6`，submission为 `a393d4c96ca667d8cde10216695730782214db7f90cd411c82ff3c9dc3bb92fe`。完整真实返回由独立观察保存，与落盘initial_judgment.json严格规范相等，submission快照及0008身份/前驱/workflow保持正确。不是比较未传入核心的deepcopy，也不是拿落盘结果冒充核心返回。

真实核心计数与每个公开调用增量对应；替身错误映射明确为helper核对、核心0，未将其当作本轮真实核心失败或完整宿主映射路径重跑。

## 5. 保护、合并验收及非阻断记录

定点入口实际执行一次完整保护扫描，基线126441项，实扫**128435文件**。changed恰为获准的宿主和本任务测试，missing=[]、unexpected=[]、读取错误0，重点冻结哈希一致。扫描字典从实际保护函数返回帧保存为current_scan.json，后续只刷新本轮新增产物/文档，不重复全项目扫描。最新source_hashes_after.json身份、项数和排除项登记在review_result.json。

TASK-017原七组的正常保存、MAIN/零条、前提拒绝、宿主错误映射、保存晚变更、0008半写/完整后sentinel等证据由 `docs/reviews/REVIEW_TASK_017.md` 记录；原两项阻断此前未关闭，本轮定点关闭后合并接受限定宿主范围。原writer路径本轮没有变化，GPT未重跑：沿用上一轮对完整throw实际字节及两场景14份旧checkpoint哈希的补核，不称为本轮实测writer。

非阻断事项登记，不要求修改冻结历史：

- 当前counts/core_observations把9条登记统称“宿主API”，其中一条实际是host_api_delta=0的映射helper。实际公开宿主API为8，正常返回3/预期阻断5，helper另1；所有真实调用已登记，核心1次结论准确。今后新测试分列，不据此再建业务链或重开修正卡。
- 执行端额外运行task017r1_allcheck2完整七组，超出R1明确的定点运行要求；GPT只读取其摘要，不将其作为GPT复跑，也不以额外运行追认原伪计数。登记为过程范围偏差，后续遵守有界入口。

## 6. 下一卡与人类交接

TASK-018新增独立的开发态只读审阅包导出/离线核验，将现有22份选定来源材料与status/索引整理为可读证据包。宿主、控制器及全部核心冻结，不增加0009、不生成AI或真实判断。卡中规定同缓冲字节与初始合法status绑定、有限收尾、失败现场、离线核验含义和一个新C06b复用的有界验证。

这一步准备现有证据供人类审阅，不替人类决定是否建立正式契约、开放真实Gate或保存真实独立初判。此类业务决定仍须人类明确作出；本轮未提供真实批准。DSH由人类关闭TASK-017和R1，GPT未访问GUI或代关卡。
