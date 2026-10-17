# DSH架构/测试验收端交接

先读同根START_HERE、HANDOFF_MANIFEST，再读最后接受review_result和TASK-040全文。本文件是角色与复验方法说明；具体范围、签名、常量、调用公式、链数上限以已发布TASK-040和已接受设计1.1为准。

环境为Windows/PowerShell，项目根D:\harness work\audit_sa_project；独立脚本使用项目.venv\Scripts\python.exe并始终带-B，不创建新的pycache。

## 1. 你的职责与停止条件

你接任Architect / Reviewer：设计有限任务，独立复验，发布ACCEPTED/NOT_ACCEPTED及证据；通过后接续制定下一卡。你不是当前卡执行端，不修改生产、交付测试或既有指南，不代写人类判断，不将执行PASS/勾选/看板当结论。

只新增自己的具名评审根、独立脚本/观察/保护/结果、review文档及下一任务或定点修正卡。每卡先固定确切写入范围；TASK-040可用 `data/reviews/task040_dsh_<具名轮次>/` 和 `docs/reviews/REVIEW_TASK_040.md`，如已有同名文件则另用具名版本，不覆盖。修正时也另根保全原NOT_ACCEPTED现场。不得自行创建其他执行会话或跨会话发送指令；由人类传递交付入口即可。

发现实现阻断时给准确字段/阶段、先满足的前提、实际与预期、最小复现及允许修正文件；不要直接帮执行端改实现或扩大范围。问题分类错误、必须改冻结核心/协议政策/业务权限时停止该级处理，升级并请人类裁定。日常读取、必要独立小样和已授权复验不逐项索要确认。

## 2. TASK-040独立关注顺序

先局部实读，再小型复验，最后一次保护扫描，不重跑全部历史。

1. **身份与范围。** 核当前accepted快照168839项/SHA、卡SHA、唯一可改适配器起点SHA、新交付实际delivery；核19 API/17代码/40 Gate1材料是实际完整名单，不只数量。代码改变使用新TASK-040登记及夹具Gate事件；旧38材料凭证不能改签。现有17 API签名和公开prepare同批拒绝不削弱。
2. **真实调用。** save真实公开prepare一次，冻结store.save一次，pre/post history共2；verify真实history一次，并直接真实Gate1/Gate2/fact各一次，公开prepare/save0、不另verify目标。核实际代码对象、父关系及完整载荷，区分setup、构建/核验、直接/嵌套、只读恢复render和禁止facts build。计数不能从旧replay或预期公式冒充。
3. **正常全量关系。** n=0保存/m=1恢复完整十二键返回、六快照+三封装、四输入快照与独立内存预期一致；三时点原引用不变。S6/S7/S8/V3/V5全量对象闭合，FILE/FP及长度取同一真实缓冲，预期固定早于候选，不拿两个自报摘要相同比较。
4. **历史时点。** E1仅E0加本次已核验manifest；旧P0/H0/H1及expectations不改。当前完整Hc含自身且不能排除坏其他叶。后来合法另一batch可追加并恢复目标；旧引用缺失/四字段矛盾/同event或batch重复均拒绝。不允许Hc减自身回造P0，也不把当前Hc的FP顶替保存receipt的H1摘要。
5. **人类与类型。** 六原文来自已登记event1/2；技术绑定可变，人类值不造。非法/缺失字段由冻结store/core按真实顺序报告，不先JSON序列化非法提交遮蔽。严格False/0、int/float；反序多错首报稳定。RC-44角色错误有合法64hex及成立的更早前提，不能用更早Gate/SHA错误充当角色关系拒绝。
6. **真实锁能力。** CREATE_NEW读/写/DELETE、只共享读，真实持有句柄/file ID/父身份/原字节；并发B同域拒绝且业务增量0；A正常继续。成功按本次句柄删除并确认释放，不能close后路径盲删。失败保留锁/半写，既有陌生锁不清。系统阻止物理替换与内部file-ID错控制分别报告；释放失败绝不成功。
7. **失败及半成功。** 有效运行/store failure优先，坏failure精确schema字段；Blocked/Error按实际类、原field/stage/reasons/cause/secondary保留。真实句柄半写、receipt返回后sentinel、诊断故障不盖主异常。六快照成功但context/receipt/最终确认/释放失败不能RECORDED；不回滚/删叶/清锁。
8. **晚变更。** 核心前改变应本次拒绝且store/core构建增量0；最后必要消费后单文件坏字节本次拒绝。只读例撤wrapper仍坏则继续拒绝，精确恢复本轮原件后才成功；verify不写failure/时钟/随机/网络/子进程。sticky失败和无sticky的可恢复单文件例分列。
9. **最外层收尾。** 独立预期对完整候选、实际台账读回、末次字节共同支配main/summary/failures。四个真实新进程0/1/1/1，replay新增业务调用0。不能内部诊断FAIL但外层0，不能按控制标志硬返回1。原始坏字节必须保留。

上述必须项缺真实证据时不能用静态猜测填PASS。任务卡明确允许未执行的物理junction、无合法人类夹具正例等按null+原因报告，不因此强迫绕权限或造数据。静态、私有控制、冻结证据引用、完整公开API实测四种层级清楚分开。

正常调用公式以TASK-040为准：save前n叶，initial verify=2n+1、core总2n+2（构建1）；verify当前m叶，initial verify/core=m。既有Gate1verify6/Gate2verify5/loadinspect5/screeninspect2/crosscheckinspect1/factinspect/render各1/Gatestoreverify/P1各11/冻结prepare6。SQL/标准化/装载/复算/fact build均0。失败按实际前缀计，不套公式。

## 3. 保护、结论和下一卡

先核定稿和有限身份/证据，再一次最终全树保护扫描。沿最后接受口径：项目根.venv/.git/__pycache__排除；不把data证据、失败或新交接目录整体豁免。相对接受基线，TASK-040唯一既有变化允许runtime_gate1.py；新missing/读取错误/未知新增/身份漂移0，新增逐确切路径登记。

扫描前将本交接四文件的实际SHA与HANDOFF_MANIFEST核对，单列“基线后人类授权的交接增量”，并登记接受快照自身及review_result两条元数据。不能因为handoff不在旧快照而追认整个目录可写，也不能改TASK-040卡或旧接受基线消除差异。本交接manifest无自嵌哈希，自身作为确切路径记录；其外部SHA可从本次人类会话最终答复取得。

139历史损失、27恢复、326越界、19命名及TASK-030原锁逐项保持，新missing单列。scope通过不追认历史越界。扫描后仅有限自身元数据路径读回；局部helper错误先修自己的helper并如实记，不能重复扫树或修改交付凑通过。

review至少写：明确结论、交付/卡/基线身份、独立实际运行及完整证据路径、阻断或闭合、未执行/引用旧证据、保护及历史损失、真实业务状态、下一卡/修正卡。review_result记录实际基线项数/SHA、review/证据/保护/下一卡SHA及是否执行；accepted快照排除确切self/result、有限登记。NOT_ACCEPTED只发布observed现场快照，最后accepted不被替换。

通过后下一卡根据真实缺口制定。保持每卡少量明确可复现验收，不新增通用框架、重复历史矩阵或无关重构。AI/终判/真实数据/强认证不在现有授权；涉及它们的实施方案须先交人类决定。本地合成技术记录始终不能冒充真实批次批准。最终回Codex所需入口与完整交付链见START_HERE§5。
