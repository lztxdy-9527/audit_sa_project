# TASK-016-R1 验收及TASK-016整体关闭记录

日期：2026-10-13；验收端：GPT。

结论：**通过。TASK-016与TASK-016-R1技术验收完成，可由人类在DSH关闭两卡。** B1严格指纹和B2守卫登记均已独立复验关闭；下一卡为 `docs/tasks/TASK-017_DRAFT.md`。

验收止于开发态模拟初判纯核心VALIDATED，不表示真实人类判断已保存或身份已认证。宿主本轮未改，仍停0007，真实批准null、next_step_allowed=false、AI未开放。

## 1. 最终交付身份

GPT实读哈希与交接一致，复验前后不变：

- 核心 `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`。
- 纯核心测试 `c0ef730e59ad78f54d7d60014289ea56ca7e79c764f9afba515c1c77449b62f3`。
- 指南 `2bbaa876ae7a76175f3462d9395b7bbc8e4bec5b1631030ff3fe32142d0286f5`。
- R1回执 `2b31a540a4b2cc8a607308fe1fa9de46dfac138c653580fe9efbecfac224f9cd`。

宿主仍为 `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`，TASK-015宿主测试仍为 `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`；控制器、事实核心、原卡/回执/评审及三份packet保持冻结。选定文件完整哈希见本轮selected_hashes_before/after。

## 2. 实际复验与证据层级

执行端最终 `task016r1_final` 自报定点2/2 PASS、退出0；GPT读取相应完整证据，另实际执行交付 `--only r1` 一次：新容器 `data/initial_judgment_tests/task016_r1_gpt_20261013_023714`，退出0、2/2 PASS、failures=[]。

外部观察器绑定交付测试实际使用的test.CORE真实API代码帧。守卫期间只在内存记录，结束后落盘；直接观察**真实核心14次**，4次返回、10次Blocked，与14条登记逐个标签对应。不是仅把执行端自身计数再抄一遍。

证据位于 `data/reviews/task016_r1_gpt_20261013_023714/`：run_review.py、actual_core_code_frames.json、reference_audit.json、verification_result.json及本轮新容器。GPT未重跑all模式、宿主、上游或历史测试；本轮复验未出现需修正的观察/断言失败。

执行端额外运行过程容器task016r1_allcheck，保存七组PASS和48/48记录；GPT仅实读该摘要，不称为本轮GPT完整复跑。其额外全量运行超出卡中定点复验要求，登记为过程范围偏差，不因已独立关闭的问题再要求补跑或追改历史证据。

## 3. B1关闭

共同helper采用无首尾锚点的64位小写十六进制模式及fullmatch，未strip/截断/转小写。四项来源、expected和submission指纹都使用共同检查。

GPT实际运行四个来源LF反例：每项独立内存深拷贝、长度65，expected/submission按候选对象重新计算，均InitialJudgmentBlocked，field精确为fact_packet.bindings对应字段；没有借外层指纹不匹配提前拒绝。CRLF/尾随空格/大写/expected LF/submission LF等有限对照也通过，单独submission非法时指向其字段。

C06b、MAIN12条、C03零条合法对照返回协议/来源指纹/线索序列正确，record规范指纹和原文保留正确，零条不自动产生无问题结论。所有实际调用的packet/submission同一引用调用前后规范指纹一致。

## 4. B2关闭

守卫内仅执行一次真实核心，解除守卫后record_observed_api保存那一次完整实际返回，没有再次调用补记录。GPT捕获的守卫内返回与该条持久返回严格规范相等；守卫命中全0。

外部实际14次、登记14条、覆盖真实核心14次一致；逐标签对应，完整返回/异常文件存在且sha256正确，原因链/字段诊断保留。正常与守卫返回固定五项null、两项false，纯内存VALIDATED边界未改变。

严格单删registry的副本自测已改正，GPT再次调用真实audit helper确认原件通过、仅删一条登记后失败；未修改真实file_ledger或证据文件。G4旧反例描述在新回执更正为22+11=33，旧回执保持冻结。

## 5. 保护与整体验收范围

GPT本轮定点入口执行一次完整保护扫描，基线124275项，实扫124523文件：changed恰为本轮获准核心/测试/指南三项，missing=[]、unexpected=[]、读取错误0；宿主与旧测试冻结，三份packet一致。扫描字典由实际函数返回帧保存为current_scan.json，不重复扫描项目树。

原TASK-016正常七组、确定性/无别名/纯内存/协议反例已有上一轮GPT实际证据；本轮只修共同格式检查和登记，并完成对应定点复验。合并证据足以接受限定纯核心范围，不追认此前65字符非法来源为合法，不把原47条登记称为48条。

本轮最终保护读数source_hashes_after.json及文件哈希/项数登记在review_result.json，供TASK-017使用。该读数不是Git恢复点；不迁移历史凭证。

## 6. 下一任务

TASK-017只接入冻结纯核心到开发态宿主，保存显式模拟submission/完整record并增加0008；工作流状态仍与0007相等，控制器冻结、AI始终真实false。新核心纳入现有宿主专属host_code_sha256绑定，从start实测；不改变控制器八项代码协议。详细前提、保存/失败恢复、只读status、晚变更及有界测试均在下一卡。

真实人类初判、真实Gate/正式契约、AI建议及终判仍未提供或批准。DSH由人类操作，GPT本轮未访问看板或关闭卡片。
