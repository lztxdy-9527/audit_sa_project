# TASK-003-R3 复验通过：开发态接收成果冻结

日期：2026-10-11（北京时间）。验收端：GPT。结论：ACCEPTED_DEVELOPMENT_SCOPE。

TASK-003 及 R1—R3 在当前任务范围内通过。接收入口可以为合成工作簿建立原始快照、运行已验收 checker、保存日志与版本，并生成开发态 Gate 1 候审材料。此前的两处错误就绪路径及存在性记录问题已经修复；不再要求 TASK-003-R4。

这项架构验收不构成人类 Gate 1／Gate 2 批准，也不使正式契约生效。现有批次继续保持 next_step_allowed=false。

## 1. 实际执行与证据

GPT 在全新容器执行：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r3_gpt_20261011_045827'

实际退出 0：61 例通过、0 例失败；34 次真实 CLI、27 次内存模拟、122 份调用日志。44 个预期负向案例正确拒绝或阻断，不能将它们解释为测试失败。22 份既有 fixture 仍为 14 份质量通过、8 份质量阻断。

GPT 另外复用上轮只读 probe_receiver_r2.py，对当前 R3 实现重新运行四项独立复现；这些调用不计入上述 61 例：

- T01：原输入只在核验结束时哈希读取失败，现为退出 2、FAILED_RUNTIME，保留该次错误。
- T02：真实 checker 只在结束时哈希读取失败，现为退出 2、FAILED_RUNTIME，未将未知稳定性当成通过。
- T03：真实 checker 生成新报告后，删除 payables.payable_amount 映射键，现为报告结构无效、退出 2。修改前报告字节另存，未冒称无效报告来自 checker。
- T04：SPEC 的 exists 已成功，但随后 read_bytes 失败，现为退出 2，同时保留 exists=true、sha256=null 和读取错误。

另外对实际有效报告逐个删除四表共 22 个固定字段映射键，全部被结构检查拒绝。此项是结构函数检查，不冒称 22 次接收 CLI。

本轮证据目录：

    D:\harness work\audit_sa_project\data\reviews\task003_r3_20261011_045827

其中 command_log.json、regression.stdout.txt、regression.stderr.txt 记录完整回归命令与输出；independent_command_log.json 及四组日志记录独立复现；mapping_required_keys_checks.json、normal_batch_inspection.json、protected_files_comparison.json 和 acceptance_summary.json 记录补充核对。

## 2. 正常材料和质量阻断核对

核对 DeepSeek 的 dev_receive_003_r3_main_01，以及 GPT 新容器中的 MAIN_demo、C01_valid、C14a_missing_column：

- 各有正常 8 项产物；原输入与快照逐字节哈希相等。
- 原输入的三次哈希、快照的两次哈希均已知且相等；两份执行源码起止一致，留档副本与当前源码一致。
- 最终候审材料、报告、日志和代码副本的清单哈希与实际文件相等。
- 主数据四表为 20／993／1000／1005 行；主表净额 267249329 分 = 已知应付关联净额 266249329 分 + 缺失关联净额 1000000 分。主表与分摊未重复累计。
- C01 净额为 500000 分。C14a 保持 BLOCKED_QUALITY；其 payable_amount 映射键存在且值为 null，报告结构有效；不可用的完整勾稽金额仍为 null。
- 全部保持 DEVELOPMENT_ONLY、DRAFT_NOT_IN_FORCE、两项批准 null、next_step_allowed=false。

R3 的四种结束哈希失败、质量阻断叠加哈希失败、空映射、实际缺表等相关用例均按修复卡要求成立。

## 3. 冻结版本和文件保护

本次通过的版本 SHA-256：

- scripts/receive_demo_batch.py：5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6
- tests/test_receive_demo_batch.py：6374a5d7ead327fbc65fbeaefe3a9377daba58eb0dcfea731847616df87b6c96
- docs/BATCH_RECEIVE_GUIDE.md：fccadcdd098d76ccf9f7061e4fafac72b3aba95e64ea53f3e794c1ad8dafbcfd
- docs/EXEC_REPORT_003_R3.md：bf0f18d57cfc6171d6c9c7bbf79b67f0291e57e16017197876aef37c4dfc9ab1

GPT 本轮开始前记录的 4902 个已有文件，测试及独立复现结束后全部未变。对上轮 3225 文件基线，只有修复卡授权的接收器、接收测试和接收说明三个文件变化；任务二 874 文件基线全部未变。没有改写原始数据、旧批次或旧回执。

GPT 本轮没有修改实现代码，只新增验收证据、本验收记录及下一张任务草案。

## 4. 有限验收与下一步

报告结构检查覆盖接收入口消费的字段，不等同于完整通用 schema 验证。本地哈希与留痕用于普通错误发现和追溯，不宣称抵御同权限恶意篡改；存储彻底不可写时不能保证落盘失败清单。这些已说明的限制不阻断当前开发任务。

非阻断标签：测试汇总的 task 仍显示 TASK-003-R1；manifest_version 仍为 TASK-003-R2-batch-manifest-1.2。后者沿用字段布局版本，实际实现由上述源码哈希识别。保留历史，不为标签再开启接收器返修；验收记录明确对应 R3。

下一张 TASK-004_DRAFT.md 仅开发和测试标准化核心、逐单元格来源及转换勾稽，暂不接入既有接收批次，不做 SQLite 或规则筛查。这样将“转换正确”与“流程放行”分成两次可验收的小任务。正式接入前仍须另行建立契约与人工守门控制，不能用开发测试代替批准。

主理人当前只需转交本验收记录与任务四草案，无需技术复测，也无需现在模拟 Gate 1 批准。
