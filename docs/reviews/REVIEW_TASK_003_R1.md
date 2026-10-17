# TASK-003-R1 复验：仍需返修

日期：2026-10-11（北京时间）。验收端：GPT。结论：CHANGES_REQUIRED，完成 TASK-003-R2 后再复验，不推进任务四。

来源声明保真、两个源码留档比对及上次列出的具体故障案例已经修好。本次剩余问题仍属于 TASK-003-R1 已要求的“报告有效性、统一失败处理、真实文件状态与未知值”，没有增加新业务功能。

## 1. 实际通过的验证

GPT 使用项目解释器独立运行更新后的集成脚本：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r1_gpt_20261011_041850'

退出 0：21 个案例全部通过；11 次真实 CLI、10 次内存模拟，42 份独立 stdout／stderr 日志；34 个受保护输入及测试输入副本未变。

另外，GPT 将原有 22 份 fixture 逐一交给真实接收器和真实 checker：14 份质量通过、8 份质量阻断，全部符合预期，没有被新增报告校验错误归为运行失败。这验证了当前实现对既有合法质量报告的兼容性。

检查 DeepSeek 的 dev_receive_003_r1_main_01、GPT 新建的 MAIN_demo／C01_valid／C14a_missing_column：实际都有 8 项产物；快照与输入字节相等；两个源码副本与本次版本相等；主文件四表数量仍为 20／993／1000／1005。来源声明的首尾空格与换行能够原样保存。

所有运行仍为 DEVELOPMENT_ONLY，契约仍为 DRAFT_NOT_IN_FORCE，两项人工批准均为 null，next_step_allowed=false。正常接收与质量阻断主流程没有发生业务口径变化。

## 2. 剩余问题与证据

以下 Q01—Q07 都在内存中替换函数，只产生全新测试批次；真实源码、规格、原 Excel 和既有证据均未修改。

### G03-R1-01：报告为 null 或缺少内部必需内容，仍能候审就绪（P1）

源码位置：receive_demo_batch.py 第 113—228、458—514 行附近。

- Q01_report_null：模拟 checker 退出 0，报告文件为合法 JSON `null`。读取后的 Python 值为 None，绕过了 `if report is not None` 内的结构检查。实际接收入口退出 0、DEV_GATE1_PACKET_READY、failure_reasons 为空；report_validation 却是 attempted=false、valid=null，材料写着“核验未完成”。
- Q02_empty_required_content：以本轮新生成的有效 C01 报告为模板，仅将 row_accounting、amount_summary.known_valid_subtotals_cents、amount_summary.complete_totals_cents 改为空对象，其余报告及两个哈希有效。实际退出 0、report_validation.valid=true、DEV_GATE1_PACKET_READY；候审材料缺少四表行数与三项金额。

第一种情况是顶层对象检查的遗漏；第二种情况是只循环已有键，没有要求必需键存在。空对象不代表“报告已经完整”。

既有 checker 无论质量通过或阻断，都会输出四张固定表的 row_accounting 项、每表四个数量字段，以及两个金额区段的三项固定键。质量不可用时金额键的值为 null，不能把“允许值为 null”理解成“整个区段可以缺失或为空”。无需重新计算业务规则，只需检查接收材料实际使用的内容。

### G03-R1-02：finalize 仍有未捕获错误，清单写入失败可能残留成功状态（P1）

源码位置：receive_demo_batch.py 第 553—558、614—626、853—899、946—951 行附近。

- Q03_spec_hash_io_failure：只在最终清单读取 SPEC 哈希时模拟 OSError。实际异常穿出 finalize，进程退出 1，没有清单和材料，虽然批次目录可写。
- Q04_report_hash_io_failure：只在 artifact_info 读取已生成报告的哈希时模拟 OSError。实际同样退出 1、没有清单和材料。
- Q05_manifest_write_failure_after_bytes：首次写入清单时，先保存完整字节，再模拟写入／关闭报错；后续写入能力正常。入口实际退出 2，但磁盘中的清单仍为 DEV_GATE1_PACKET_READY、receive_exit_code=0、failure_reasons 为空，候审材料也保留成功状态。

main 的统一捕获目前只包住 execute_batch，没有覆盖 finalize 内全部读取与拼装。失败留痕的生成过程本身不能依赖所有文件都可再次读取。清单提交失败后，应尽可能保存失败状态，不能只在终端说失败而留下可修正的成功清单。

Q05 是可恢复的模拟写入错误，不是要求程序在磁盘完全不可写时凭空生成文件。原任务允许这种不可写情形仅退出 2 并说明现场；但本案例后续可写，必须尝试保存真实失败状态。

### G03-R1-03：清单与磁盘现况、已知证据不一致（P2）

源码位置：receive_demo_batch.py 第 261、446、583、604—612、645、853—885 行附近。

- 普通正常批次和 C14a 质量阻断批次中，gate1_packet.md 实际存在并可计算哈希，最终清单却统一记为 exists=false、sha256=null。DeepSeek 的最终主演示批次同样如此。原因是清单在材料写入前构建，正常路径没有刷新后再落盘。
- Q06_source_hash_io_failure：输入初次哈希失败，入口能退出 2、保存 FAILED_RUNTIME；但未执行的文件大小查询显示 size_bytes=0，接收器和 checker 两项哈希均为 null，却显示 stable_during_run=true。这些值实际未知，不能由默认零或 None==None 生成已验证事实。
- Q07_checker_start_failure：模拟 checker 子进程无法启动并抛 FileNotFoundError。入口能退出 2、保存失败，但 checker_invocation.started=true，退出码为 null，实际没有启动。记录“曾尝试启动”和“已经启动”需要区分。

正常清单的材料存在状态和哈希必须来自写入后的现场；失败时未知值为 null。当前执行中的初始变量不是最终证据。

## 3. 文件保护与版本

本轮复验前的 1805 个现有文件全部未改动或丢失。

对照任务三首次验收的 1308 文件基线，只有获准的 receive_demo_batch.py、test_receive_demo_batch.py、BATCH_RECEIVE_GUIDE.md 三项变化，0 个缺失。对照任务二 R2 原始 874 文件基线，全部未变。

实际源码／说明哈希与返修回执相符：

- 接收器：c5985d74298d8f6bca19cefce567f8ba147c78ed657841ab3784ad65d1b2eb70。
- 接收器测试：7a2ddf7cfd6bf6198aec76e45bc8ed73ba3f2f2647760514d45a36cae5d96695。
- 接收说明：c8e2dff590cbc3bace48c34972a1e68abea1eaa592582609a2f2909c03c01ed6。
- 冻结 checker：a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8。

## 4. 证据和下一步

证据目录：

    D:\harness work\audit_sa_project\data\reviews\task003_r1_20261011_041850

acceptance_summary.json 汇总结果；independent_probe_summary.json 保存 Q01—Q07 观察；normal_batch_inspection.json 保存普通批次的材料清单问题；fixture_sweep_summary.json 保存 22 份兼容性结果；command_log.json、各自日志和 probe_receiver_r1.py 提供完整复现方法；source_hashes_before／after.json 提供保护记录。

新测试容器：

    D:\harness work\audit_sa_project\data\batches\task003_r1_gpt_20261011_041850

其 batches 是 21 例回归，fixture_sweep 是 22 例真实接收，independent_probes 保留 Q01—Q07 的现场。目录后缀采用 UTC 时间。

把本报告与 TASK-003-R2.md 全文转交 DeepSeek。只修剩余收口问题，不重做已通过的来源保真、代码留档和业务模型。主理人不需执行技术测试或模拟 Gate 1 批准；修复后返回 EXEC_REPORT_003_R2.md，由 GPT 再验收。
