# TASK-015-R2 验收及 TASK-015 整体关闭记录

日期：2026-10-13；验收端：GPT。

结论：**通过。TASK-015、TASK-015-R1、TASK-015-R2的技术验收全部完成，可由人类在DSH关闭三张卡。** B1已在上一轮独立复验关闭，本轮E1已关闭；不再要求R3。后续任务见 `docs/tasks/TASK-016_DRAFT.md`。

这不是批次真实Gate批准或审计判断。已验收宿主链到开发态0007 / FACT_PACKET_RECORDED，phase仍DEV_GATE2_APPROVED，真实批准null，next_step_allowed=false；人类独立初判保存、AI建议、终判、正式契约和真实Gate仍未实现/批准。

## 1. 最终交付身份与冻结

实际文件哈希与交接一致，GPT复验前后不变：

- 宿主 `scripts/run_demo_workflow.py`：`67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`，TASK-015-workflow-host-1.1，本轮冻结未改。
- 宿主指南：`ed4f13bea56f1e44810855df70ce6e3a8c607a9a9d08c2442acbb0b768fe07b8`，本轮冻结未改。
- 本任务测试：`90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`。
- R2回执：`0957dd61d22c8e8b37d224c62decb92aefe0bde3f7a87967a9d107fe96cff0bb`。

六个关键冻结件、TASK-015/R1/R2卡、历史回执/评审保持冻结哈希，详见 `data/reviews/task015_r2_gpt_20261013_011825/selected_hashes_before.json` 与 `selected_hashes_after.json`。GPT未修改上述交付文件或任何既有批次。

## 2. 证据层级和本轮实际执行

执行端自报 `task015r2_run_03 --only late-controller` 退出0、运行期2/2 PASS。GPT实读该容器的CLI/API、登记表、台账、正常核心返回、输入观察、现场计数、保护与停止点文件；这些是读取执行端既有证据，不称为GPT重跑公开宿主流程。

**GPT本轮实际复验的是受影响收尾函数及失败传播，不重复建链。** 在全新 `data/reviews/task015_r2_gpt_20261013_011825/finalizer_replay/` 中复制原CLI/API证据文件，原批次和SQLite只读。通过AST提取交付测试原始 `finalize_evidence`、相关小函数及其实际调用尾段，按原代码执行；仅把输出container改为隔离副本、batch_parent绑定既有只读四批次，没有替换校验逻辑或重新实现判据。

实测：真实收尾及实际调用尾段退出0，运行期两项检查PASS、failures=[]。登记、文件引用、receiver/checker、现场计数、停止点、冻结哈希及保护比较均实际执行。本轮没有执行公开宿主API/CLI、MAIN、smoke、完整八组、持久化故障组、事实核心21组或TASK-002—014历史入口。

证据：`review_finalizer.py`、`actual_finalizer_execution.json`、`finalizer_replay/`、`verification_result.json`。本轮辅助脚本未发生需要重建业务批次的失败。

## 3. E1实际关闭证据

### 登记、引用与失败传播

原交付31条CLI、5条公开API、36条权威登记，98项返回/异常/原文引用逐项实读哈希正确。CLI原文/记录、API文件/记录、权威登记/调用记录双向一致。异常文件实际存在并包含真实异常链和traceback。新收尾函数不再把未执行的默认零作为已审计结论；问题返回后由实际record函数加入正式failures，实际退出表达式据此返回1。

GPT严格隔离反例：仅删除审核副本一条 `registry_calls` 记录，file_ledger、CLI/API记录和真实文件完全不动。交付原始audit helper报告“调用未登记进权威登记表”；实际record与退出表达式得到正式失败和退出1。原件仍通过。证据：`strict_single_registry_deletion.json`。

另在副本日志追加LF，实际audit_ledger准确检出哈希不符，随后恢复副本；没有改变原交付。证据：`copied_log_tamper.json`。

### 现场、输入与停止点

真实finalizer从只读四批次重新导出：复算MATCHED4、事实包READY4、0007物理4/可解析4、有效失败现场3、无失败成功现场1、半写0。receiver及其内部checker均4，引用核验通过；没有把直接checker CLI0误称内部未启动。

GPT实读正常对照核心完整返回与磁盘packet，规范JSON严格相等、规范指纹正确；Markdown精确等于返回字符串UTF-8字节。原观察记录的核心1次和三个输入调用前/核心返回后/公开返回后指纹一致；本轮读取这些观察记录，没有再次调用核心或据此推导子进程内部次数。

三晚变更探针的本次阻断、失败事实保留、输入恢复后仍退出1及操作前文件保护已有R1实际复验；本轮宿主未变，R2正式记录也保留相同结果。成功对照0007 workflow/前驱/操作类型、真实批准null和next=false核验通过，无0008。原交付125文件、四批次131文件和四份SQLite前后哈希集合全部不变。

### 保护

GPT通过真实finalizer进行一次当前扫描，基线123108项，实扫123986文件：changed恰为 `tests/test_fact_packet_demo_workflow.py`，missing=[]、unexpected=[]、读取错误0；宿主/指南/六件另核对一致。见 `finalizer_replay/probe_records/r2_protection.json` 及 `protected_scan.json`。后续TASK-016使用本轮最终 `source_hashes_after.json`，其身份登记在 `review_result.json`。

## 4. 非阻断辅助记录

以下不影响已独立确认的E1性质，登记后关闭，不追加R3，不追改冻结回执：

1. `finalize_evidence` 在调用方record最后一项之前保存checks/summary，所以原交付落盘清单只有1项，运行期实际2项。GPT直接执行原调用尾段确认第二项真实执行，失败分支也真实影响退出；本轮另存完整运行期两项清单。后续新测试应在全部检查完成后保存最终汇总，TASK-016已明确此要求。
2. 原交付隔离副本仍同时删除一条file_ledger和一条registry，回执称“只删登记”不精确。GPT已用原helper严格单删registry补证，无需重复修已证明的判据。
3. 交接/回执所列扫描总数123618与实读原 `r2_protection.json` 的123875不同；GPT当前扫描数123986独立列出。changed/missing/frozen的验收结论一致，采用各现场实际读数，不混称同一次扫描。

## 5. 整体验收范围与下一任务

TASK-015原交付正常接入/0007恢复、真实writer半写/完整后sentinel等已经有原GPT实际证据；R1修复最后控制器检查后Gate2磁盘漏验并由GPT三目标实际复验；R2补齐证据收尾并完成本次定点复验。三轮证据合并足以确认冻结事实底稿核心接入宿主的限定范围，不追认此前漏验现场为成功，也不宣称所有历史入口重跑通过。

TASK-016只新增开发态模拟独立初判记录纯核心、相应测试/指南/回执；不接宿主、不保存真实判断、不解锁AI。批次真实判断和真实Gate仍由主理人作出。DSH由人类操作，GPT本轮没有打开或关闭看板卡。
