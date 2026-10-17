# TASK-023-R1评审：实现阻断关闭，helper完整证据仍缺一层

日期：2026-10-14。结论：**NOT_ACCEPTED**。TASK-023与R1暂不关闭，不制定TASK-024。仅转 `docs/tasks/TASK-023-R2.md` 的B类测试证据修正；生产适配器、配置、全部上游冻结，GPT未改实现。

## 1. 本轮实际复验及已关闭部分

证据根 `data/reviews/task023_r1_gpt_20261014_031403/`。

GPT实际运行当前原样公开CLI到新 `task023r1_gpt_normal_20261014_031403`：**0、70项检查、0失败**。登记prepare37、P1实际代码帧3、receiver CLI7。来源声明/全部冻结SHA/必需null字段/严格config布尔、真实checks子目录junction拒绝及lstat映射、请求换行/tab和decision_review批次保真、质量映射/P1对照均通过。原先对data/递归历史树的快照问题不再出现。**B1、B2、B3、E2关闭，不重开生产实现。**

新 `task023r1_gpt_drift2_20261014_031403` 的真实终审reader返回原缓冲后，只给checks.json追加LF，命中1 → **套件1、summary FAIL、failures非空**，最终目标SHA等于注入后SHA，被改文件保留。字节漂移不再被第二次写入掩盖，该项关闭。

后述两个完成故障场景均用轻量代码帧观察器独立观察到**prepare37、真实冻结validate_report14**；原P1观察器继续记录3。观察器只记录调用，不改入参/返回，不调用额外核心；正常CLI没有包装。完整命令、stdout、summary、故障状态和独立观察见各result及verification_summary.json。

GPT有限读回执行端正常与本轮正常两份台账，各12项字节/长度/SHA一致、内容与登记审核均ok。执行端自报与GPT实跑分列，未运行TASK-021/022或宿主历史入口。

## 2. 唯一剩余阻断：helper完整观察没有持久保存，也没有实际条目闭合

HelperObserver确实包裹冻结模块实际validate_report函数。但其payload仅在内存传给收尾helper：

- 最终bodies/PAYLOAD_FILES及深拷贝expectation中均无helper完整载荷；磁盘只有helper ID/total及总数审核摘要，14条真实输入/返回/异常记录未保存。
- 观察entry只保留input_type/input_fingerprint，没有实际输入快照，不能独立复核当次受控输入。
- _final_registry_audit只比较payload.total_helper_calls与helper_records.total，未核对records实际长度、ID集合及完整载荷；helper_call_ids也未用于闭合。

GPT在新 `task023r1_gpt_helper_entry2_20261014_031403` 包装**真实HelperObserver.payload**：先取得原返回，再只删除一条完整entry，保留total=14，不改真实helper执行/输入/返回，不改prepare或writer/audit分支。独立函数代码帧仍为14，candidate.records实际13。结果：**套件0、70项0失败、summary PASS、failures=[]**，登记helper审核仍ok。

这不是要求新增身份认证或审计保证，而是TASK-023/R1已经要求的“完整实际helper观察落盘、实际调用与完整记录闭合”。只把两个声明总数互相比对不能证明14条实际调用均有完整证据。当前正常台账自洽也不能补回未保存的载荷。

证据：helper_entry2_result.json含真实14条原件、13条候选、被删entry及独立代码帧观察；finite_audit.json记录磁盘文件集合和审核值。R2须只补此层，不再改来源/路径/ID/快照算法。

## 3. 身份与过程记录

适配器 `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4`（56069字节）、测试 `e739df9b55de87ad758333def339cfc3838caae641b1eaf71b63467bf1afa518`（80889）、指南 `025b2241a8e6d5ab0347b6993f80a09ef47937c5ef407477305414d713cd007f`（11629）与交接一致。R1回执实读13839字节、SHA `882c19ce9f403972d6064ffaa59282c347f552b721a217bc461b44ccee74be50`；交接只给字节数、未给SHA，本轮登记实际身份，不视为不一致。配置、P1、存储、契约、宿主/控制器仍匹配冻结值。

GPT初版独立观察器对每个Python代码帧解析路径，造成不必要耗时；只终止本轮两个解释器，保留未完成的drift场景，改为先筛两个目标函数名，再比较文件路径。正常CLI**未重跑**，两个故障分别在新的drift2/helper_entry2根完成。该中断场景不计为完成的故障验证，完整过程见reviewer_process_correction.json及初版脚本副本。此为验收脚本问题，不归咎生产实现。

## 4. 保护与后续

GPT一次最终全树扫描，基线140867项、SHA `ffba9184f3f297bd6797bf1e510d33a4568f928b1088ea3ca93a3139fef14156`。实扫**141937文件**：**changed恰为adapter/test/guide三项；范围外变化、missing、读取错误、范围外新增均0**。执行端新回执/九个显式根、前轮两项确切自指元数据、本轮评审/四个观察场景及批次根按确切路径分类，无目录前缀豁免，旧junction与中断现场保留。扫描后仅有限更新本轮评审/元数据，不再扫描项目树。R2基线完整SHA/项数及两个确切自指排除见同目录review_result.json。

R2只处理测试中helper输入/返回/异常的完整保存、真实观察计数与载荷闭合、候选磁盘审核。生产代码冻结，不接存储、历史、宿主、Gate2、真实初判或AI；真实批准null、next=false不变。人类继续操作看板，技术验收不批准任何批次。
