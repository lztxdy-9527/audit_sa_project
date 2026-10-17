# TASK-017 验收记录

日期：2026-10-13；验收端：GPT。

结论：**暂不通过，返回TASK-017-R1定点修正。** 已独立确认真实核心接入、正常保存/0008工作流不变及六个下游只读守卫；但status在最后一次新层读取后漏验磁盘，实际误报READY，且测试把宿主API次数当真实核心次数，正常输入/核心返回观察也未落实。原卡保持待验收，不制定下一任务。

## 1. 交付身份与冻结

实际哈希与交接一致，GPT定点复验前后未变：

- 宿主 `e65b8b3ee604f66808f88176e0ad870de00a479a07e6a2cc989590ddd16232c5`，TASK-017-workflow-host-1.0。
- 指南 `856b39f81b0f37a38709636348621275cbe894bcab4174350107d62968a177c8`。
- 测试 `ef8c0eccb191b7c84c70694479f942bac553e5b52e3b17511cc4993fef6611a3`。
- 回执 `9b2bdf37935c2fc10cd30e2ab485c134a87a55d4e4e3ea466334cdcf1f237c2a`。

初判核心/纯核心测试/指南、控制器、事实核心、TASK-015测试及原TASK-017卡保持冻结。完整选定读数在本轮selected_hashes_before/after；GPT未修改交付实现或历史现场。

## 2. 证据层级和已实际通过部分

执行端 `task017_run_01` 保存七组PASS、failures=[]；GPT读取该摘要和原始证据，**没有重跑完整七组、MAIN/零条、持久化组或任何历史任务**。

GPT另建一个C06b批次 `data/batches/task017_gpt_20261013_031915/normal_c06b`，经公开API真实完成0001—0008。包装的是该宿主实际使用的INITIAL_JUDGMENT_MODULE.build_initial_judgment_record，真实核心恰调用1次；保留真实packet/submission引用，在调用前、核心返回后、公开保存返回后三时点指纹一致；完整核心实际返回单份保存，与磁盘initial_judgment.json严格规范相等，submission快照准确，0008.workflow与0007严格相等且前驱文件哈希正确。

该新批次六个下游函数计数抛错守卫下公开status成功、命中全0、批次文件哈希集合不变，新进程status0。核心绑定从start进入host_code_sha256，控制器八项代码键未改；真实批准null、phase仍DEV_GATE2_APPROVED、next=false、AI真实false。

GPT本轮执行公开宿主API12次（定点脚本11次，测试计数反例1次）、宿主CLI status3次。实际新初判核心只调用1次；接收器/装载等上游为该小样必要建链，不称为历史测试重跑。

独立证据位于 `data/reviews/task017_gpt_20261013_031915/`：run_targeted.py、actual_core_return.json、normal_core_observation.json、readonly_guard.json、api_records.json、cli_records.json等。

## 3. B1（P1）：status最后新层读取后文件已变化，仍返回READY

位置：`scripts/run_demo_workflow.py:4749`先调用_verify_initial_judgment_tail；`:4754`随后再次_read_initial_judgment_outputs取得initial_outputs_final。其后比较的是读取返回的旧缓冲；剩余收尾只覆盖上游/DB/绑定/旧链，没有再次实读本层四文件。

GPT先无注入观察，真实读取次序为：_verify_initial_judgment_operation（4173）→ inspect_dev_batch（4754）。只在后者返回原对象之后，为本轮新批次initial_judgment.json追加一个LF，不改内存/哈希/凭证：

- 文件SHA从 `11f4e17248497652c5f697f22c03d22bd3848ec6db38cad39ccd02019e67ae02` 变为 `80ae5d4539df8d9f7e9aea5c5496923ca96667c28c224824c2953d05bd34e347`。
- 命中1次，**本次公开status错误返回READY**。
- 撤销wrapper、保留变更后新进程status1；恢复仅目标原件后status0。
- status没有写诊断；所有操作前文件中仅该目标变化，恢复后整个批次哈希集合与探针前相同，0001—0008不变。

证据：unmodified_status_read_sites.json、late_status_probe.json、api/status_after_last_new_record_read.return.json及两次CLI原文。

原测试G4b（tests/test_initial_judgment_demo_workflow.py:830附近）在第一次读到新层输出时就注入，不限定inspect的最后消费点；因此其PASS不能关闭本反例。这里不是要求抵御任意时点并发篡改，而是原卡明确要求最后一次必需读取之后、成功返回之前的磁盘复测。

## 4. B2（P2）：核心观察对象错误、正常输入及返回观察缺失

位置：测试`:189`的core_recording包装record_api传入的函数，`:200`对所有宿主API套用。被计数的是record_simulated_initial_judgment/inspect_dev_batch等公开宿主入口，既非冻结纯核心入口，也非其真实执行次数。

GPT在本轮新成功批次直接调用交付record_api包装只读status，外部观察实际纯核心代码帧：**真实纯核心0次，entry.core_calls_delta却为1，所谓CORE_CALL_LOG增加1**。完整记录及观察在counter_misobservation_probe.json。由此原“20API=20实际核心”结论无效；status、前提拒绝、映射替身注入等必须分别说明，不能把宿主次数当纯核心次数，更不能要求二者相等。

测试G1在调用前构造packet_ref/submission_ref的deepcopy，但实际调用没有把这些对象传给核心；前后比较两个未被使用的副本，不能证明真实入参未变。所谓完整核心返回比较也未捕获核心返回，只读取磁盘和摘要互相比较。GPT已在新正常批次补证宿主当前实现确实调用1次且保存准确，但测试正式观察仍须修正，不能追认原方法有效。

R1要求在宿主实际核心模块上观察真实调用，保留实际两个入参引用和三时点指纹、单份完整真实返回；把宿主API、纯核心、子进程未观察与映射注入分列，所有必要证据/保护进入正式failures。

## 5. 原持久化与辅助记录补证（非独立阻断）

GPT实读原交付90条CLI和20条API的200份原文/返回/异常引用，存在性及SHA正确，记录与文件/登记表双向一致。这仅证明已登记文件一致，不使错误的核心计数成为真实观察。

原G3测试old_unchanged恒true，只检查旧checkpoint存在，未比较字节。GPT从两场景原CLI逐步输出的初始checkpoint哈希补核0001—0007共14份，全部与当前文件一致；完整throw的0008磁盘SHA确与当次缓冲SHA一致。见delivery_reference_audit.json。半写/运行失败新进程退出2已有原CLI证据，GPT没有重新运行writer，不宣称独立量到了writer入口或半写缓冲字节。

原scenes_total=8数的是物理0008，实际batch目录12；recovered_success_total=2只累加两个正常流程，未覆盖其余成功恢复场景。预期WorkflowHostError也被api_blocked计入。以上在新回执按真实scope更正，不为辅助统计再重跑全部现场。

本轮辅助审计首次只取CLI的checkpoint字段，漏掉后续命令使用的current_checkpoint/file_sha字段，14份补核数量断言失败。已定点改为识别两种真实响应字段后完成补核；未重新调用业务链。已保存的计数反例未重复执行。

## 6. 保护与后续

GPT单次当前扫描：基线124539项，实扫126437文件，changed恰为宿主与宿主指南，missing=[]、unexpected=[]、读取错误0。结果及扫描字典见protection_result.json/current_scan.json；本轮新R1保护基线另存source_hashes_after.json，身份登记在review_result.json。

交执行端 `docs/tasks/TASK-017-R1.md`。限定status收尾、真实观察/相关测试和必要指南，不改冻结核心/控制器，不重做业务范围。一个新C06b正常批次即可复验四文件只读探针与登记，无需再次完整七组或历史任务。

仍停开发态0008范围，真实人类初判未保存，真实批准null、next=false、AI未开放。DSH由人类操作，GPT本轮未访问看板或关闭卡片。验收通过后继续按持续授权制定下一卡。
