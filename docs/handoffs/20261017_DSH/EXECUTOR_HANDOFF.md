# DSH执行落地端交接

先读同根START_HERE、HANDOFF_MANIFEST，核最后accepted及TASK-040卡SHA，再读卡和已接受运行保存协议1.1/44例全文。本文件帮助安排实施；任何摘要不能替代任务卡的准确范围和常量。

## 1. 当前可立即做的工作

TASK-040前提已满足：TASK-039-R1已独立ACCEPTED。实施目标只是在既有单一 `scripts/runtime_gate1.py` 增加 `save_runtime_initial_judgment(...)` 和 `verify_runtime_initial_judgment(...)`，接冻结初判core/store/history，建立新profile下合成保存与只读恢复。卡上两个精确签名、版本/schema、S1—S9/V1—V8不变。不提前实现AI、终判或下一业务步骤。

唯一既有可改文件runtime_gate1.py：290568 B / SHA `ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a`。三新增交付为卡列的test_runtime_initial_judgment_recording.py、新GUIDE、EXEC_REPORT_040；所有证据/运行/Gate/SQLite/历史叶及锁写入根按卡展开确切路径。既有组件、旧测试/指南、任务卡、正式契约、生效登记和旧证据冻结，不为让旧静态checker适配新版本而修改它。

新profile目标19 API/17代码/40 Gate1材料。只变卡指定三个profile版本，原TASK-039保存stage/status/封装/锁版本、TASK-034字段契约、原请求版本保持。代码改变后新登记和夹具事件，不能改旧凭证。原17 API签名和规则保持，公开prepare仍拒绝同batch历史；恢复的私有共享材料分支不能变公共绕过参数。

## 2. 建议实施顺序

1. 有限读核起点、TASK-040全部身份/范围，登记准确新根及输出计划。实读源码，梳理可有限复用的capture/confirm/严格schema/异常及TASK-038材料物化；不要执行旧测试run/main。
2. 先做局部私有实现及本轮纯技术Windows锁控制：真实独占句柄、共享方式、file ID/父身份、写读回及按句柄成功释放/失败保留。能力不满足就按协议错误失败，报告准确原因，不改成路径盲删或创建即DELETE_ON_CLOSE。
3. 在适配器内作有限材料分支复用并实现两入口。正常save调用公开prepare一次+冻结store.save一次+post-history一次；verify真实history一次，私有当前Gate/fact来源证明，不额外目标verify或调用公开prepare。每层完整返回与独立来源闭合，不能复制算法。
4. 新指南先固定schema/字段顺序/异常阶段/调用图与权限，再写有限自测。Python始终-B。尽量在不建业务链时修局部问题，定稿代码后建立正常新profile小样链，不能在代码改变后沿旧链宣称成功。
5. 按卡问题族验证。持续保留原件、坏字节、半写/失败/锁和实际观察；所有setup与正式调用分开。主正常链复用，持久失败需具名隔离。卡允许最多一开发链、一正常最终链、至多八必要失败链；每条失败全链登记必要性，不能为每字段重复跑全链，也不能为复用而清锁/删叶。超过上限或需改冻结政策先向架构端报告。
6. 完整内容与独立内存预期、台账自身实际读回、末次字节确认决定main/summary/failures；四个实际新进程replay 0/1/1/1，新增业务调用0。实际计数按原代码对象/父调用，预期公式和旧观察不算新调用。
7. 源码/测试/新指南/回执及所有局部输出定稿，再唯一一次保护扫描。交付delivery及回执后停止，交DSH架构独立验收。不要自行接受、推进TASK-041或改看板。

## 3. 容易误实现的关系

FILE=SHA256确切字节，FP=SHA256规范JSON对象；按字段来源取值，不能按*_sha256后缀分类。尤其run_binding_sha256、request_sha256、packet_canonical_sha256及normalized/screening/crosscheck对象摘要是FP；登记/三封装/六快照/manifest文件描述是FILE，长度/FILE/对象同一次缓冲。writer读回对本次待写缓冲，最终确认对操作开始/本次writer缓冲，不重新采后自比。

S3固定完整prepared/H0/P0与独立M；原submission直接交冻结store，started不填未知event/actor，不先序列化非法值。S6完整十一键S与四输入和六缓冲绑定；E1恰E0加本次S的已核验manifest；H1精确旧叶+本次目标。context原H0/S/H1，receipt最后写。旧P0和expectations不改成H1。

恢复当前Hc全域含自身，取目标完整VERIFIED结果。保存H1的FP不能用当前更大Hc替代；旧P0不能由当前域减自身生成；当前材料整对象来自当前真实Gate/fact源，不以存储候选作为当前独立预期。新其他batch合法历史可追加，旧引用/旧叶/目标仍完整不变。完整返回、False/0与0/0.0、反序首报都按严格canonical/schema审核。

锁为namespace同级普通文件，五技术键、无新owner/人类时间/随机；namespace放在task040根内子目录，以保证同级锁仍在允许根内。任何既有锁拒绝，不接管。成功只按本次持有句柄删除并确认完成；失败不设置删除标记，保留实际状态再关资源；verify不取锁、不写、不取时钟/随机/网络/子进程。两输出根不原子，独立六快照成功但context/receipt/最终检查/释放失败仍运行层失败。

有效failure优先；坏failure先schema。Blocked/Errors按实际类映射，原field/stage/reason/reasons/cause/secondary不丢；本层failure十一键且不新增时间，只在本次独占封装创建后写一次、不覆盖。诊断故障不盖主异常。真实半写仅包装真实writer句柄，不能整函数造假；receipt真实返回后sentinel在write.receipt边界。

## 4. 已登记人类字段与测试样本

正常批次只读复用 `data/batches/task027r1_run_04/batch_normal`，工作簿FILE `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`。独立测试事实R01/R02/R03/R04=0/1/0/0、R02超额400000分，不能写入生产算法。

Gate APPROVE原文源 `data/decision_protocol_checks/task020r2_run_01/fixture_values.json`，只取已登记人类字段；技术批次/请求/路径/材料及前序绑定可以按当前新链构造。不得根据初判夹具反造Gate批准。

初判源1：`data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`。六原文为event_id="1"、actor_id="1"、declaration_note="1"、decided_at_raw="2026-10-16"、assessment="通过"、reason="无明显不一致且合规"。源2：`data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json`，event_id="2"，其余五项沿首份，人类已明确提供。两份都是仅合成测试、八权限false，不批准批次。具体SHA见卡及manifest。

不要为补正例创造event3、新合法时间、身份或原因；未提供的正例null+原因。负例可以缺字段/错类型/技术绑定，但不能伪造新的合法人类声明。非空/后来其他batch历史setup按卡复用已接受原六件或有限独立store构造，标明证据层级，不冒称第二条运行层save成功。

## 5. 输出与保护

交付至少包含四交付身份（适配器/新测试/指南/回执）、实际版本及完整17/40清单、44例的实测/引用/未执行映射、完整观察与输入三时点、直接/嵌套调用图、Win32锁平台实证、主/次异常及半成功产物、四CLI真实stdout/stderr/退出码、exact新增清单、保护结果与未执行原因。回执写“交付待验收”，不自称ACCEPTED。

正常save前n叶：history2、initial store.verify=2n+1、core总2n+2（构建1，其余核验），直接core0；verify当前m叶：history1、initial verify/core=m、公开prepare/save0。既有Gate/fact图沿卡；正式窗口标准化/装载/SQL/复算/fact build0；提前失败按真实前缀计。初判core的persisted仍false；运行九权限false，不因为落盘设true。

唯一最终全树扫描以TASK-039-R1接受快照为基线，允许既有变化仅runtime_gate1.py；本次交接四文件和旧快照自身/review_result作为已知授权增量逐确切路径登记，不能前缀豁免或改基线。新missing/未知新增/读取错误/身份漂移0；139历史损失、27恢复、326越界、19命名及TASK-03041 B锁保持单列。扫描后仅有限自身元数据读回，不为局部错误重扫树。

真实批准null、真实初判未保存、开发宿主0008、next/AI=false。合成测试保存不改变该真实业务状态。完成后交架构端，不清现场、不实施下一卡。
