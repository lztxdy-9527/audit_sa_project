# TASK-003 验收：需返修

日期：2026-10-11（北京时间）。验收端：GPT。结论：CHANGES_REQUIRED，先完成 TASK-003-R1，不推进任务四。

任务三的开发接收流程、数据口径和人工审批边界符合方向；正常批次可以运行。阻断验收的是失败路径与一致性检查不完整，不需要重做任务一、任务二或扩大业务范围。

## 1. 实际复验及已确认成果

GPT 使用项目 Python 独立运行原集成脚本，输出到全新目录：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_gpt_20261010_221610'

脚本退出 0：10 个案例全部通过，受保护的 31 个输入未改变。这与 DeepSeek 提交的 task003_tests_02 汇总一致。10 次入口调用包含一次内存模拟，原脚本的 command_log.json 记录了其余 9 次子进程调用，不能把它说成 10 次独立 CLI。

另行检查 DeepSeek 的 dev_receive_003_main_02，以及 GPT 新运行的 MAIN_demo、C01_valid：

- 每个正常批次有约定的 8 份文件；原输入与快照字节相等，两个代码副本与当前源码相等，报告哈希相符。
- checker 的输入确为本批次快照；主文件四表来源行数为 20／993／1000／1005。
- 主文件资金净额 267249329 分＝已找到应付关联的净额 266249329 分＋缺失关联的净额 1000000 分；主表金额没有与分摊金额重复相加。
- C01 资金净额仍为 500000 分。
- mode=DEVELOPMENT_ONLY、contract_status=DRAFT_NOT_IN_FORCE；两个人工批准字段均为 null，next_step_allowed=false。没有发生正式批准、标准化、入库或规则筛查。

GPT 又进行了 8 次独立边界探查。P02—P08 的故障均在内存中注入，只作用于新测试批次；未改动磁盘源码、原始 Excel 或既有证据。P01 是真实 CLI 的来源说明保真检查。以下问题因此是可重复的程序行为，不是推测。

## 2. 需要修复的问题

### G03-01：文件失败未统一归为运行失败，成功清单写得过早（P1）

源码位置：receive_demo_batch.py 第 134—162、238—242、357—364 行附近。

- P02_copy_io_failure：在新快照写入 32 字节后模拟复制 OSError。实际进程退出 1，留下部分快照与目录，却没有 batch_manifest.json、gate1_packet.md 或 checker 日志。目录仍可写，完全可以保留失败清单。
- P07_packet_write_io_failure：只让候审材料第一次写入抛出 OSError。实际退出 1，packet 不存在，但此前已写出的清单仍为 DEV_GATE1_PACKET_READY，receive_exit_code=0，failure_reasons 为空。

这违反了“运行／文件问题退出 2”和“已创建批次后尽可能保存失败清单”的要求。退出 1 本来表示质量阻断；不能让未捕获异常也落到这个含义。候审材料没有生成时，清单不得宣称候审就绪。

修复应覆盖接收阶段的读取、复制、哈希、日志及材料写入，不应只捕获这两个示例的位置。对于存储介质彻底不可写的情况，不要求凭空生成文件；必须退出 2、明确告知保存失败及已有现场位置，不能留下可避免的成功状态。

### G03-02：JSON 可解析不等于报告结构有效（P1）

源码位置：receive_demo_batch.py 第 207—235、357—364 行及 render_gate1_packet。

- P03_report_array：模拟 checker 退出 0，但报告为合法 JSON `[]`。实际 AttributeError、退出 1，没有失败清单。
- P04_report_structure_array：报告顶层对象和工作簿／checker 哈希正确，但 structure 为数组。实际先写出 DEV_GATE1_PACKET_READY 清单，再在生成材料时崩溃，退出 1、packet 缺失。
- P08_report_missing_sections：只提供 result=pass 和两个正确哈希，缺少 structure、row_accounting、issues、amount_summary、reconciliation 等内容。实际退出 0，仍为候审就绪；材料把缺失的问题清单显示为“问题总数 0”“未记录数据质量或范围问题”，且没有应有的行数／金额。
- 对照 P06_invalid_json_control：JSON 语法错误已能正确退出 2、生成 FAILED_RUNTIME 清单。此项有效，应保留。

必须检查本次报告中需要消费的字段及类型，不能用空字典、空数组或默认零把缺失的报告内容补成成功。结构不合法的原报告要保留，但不得作为可用质量结果生成材料；未知数量和金额仍是未知。不要在接收器中重写 checker 的业务规则。

### G03-03：仅记录代码副本哈希，没有验证副本与执行版本一致（P2）

源码位置：receive_demo_batch.py 第 158—162、262—270、331—342 行附近。

P05_code_snapshot_corruption：仅在复制到新批次的 checker 留档副本后追加字节，真实 checker 和接收脚本均未改变，实际核验仍调用真实 checker。接收入口退出 0、状态 DEV_GATE1_PACKET_READY。

真实 checker 哈希为：

    a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8

损坏副本哈希为：

    42c229fc6170bb661ff940270f522f7857e40196033446380c6cfe63f4e707e8

清单虽然记下不同的值，却没有据此阻断。成功状态要求代码一致性通过，两个代码副本均应核实与相应执行版本相等。此检查用于普通复制故障和留档可靠性，不应宣称能抵御同权限恶意篡改。

### G03-04：来源说明没有原样保存（P2）

源码位置：receive_demo_batch.py 第 119、284 行附近。

P01_raw_source_description：传入 `  原始来源说明：C01 合成数据  `，清单保存为 `原始来源说明：C01 合成数据`。当前 strip 同时用于判空和存储，违反任务卡 4.1“作为声明原样记录”。

可以用 strip 判断是否全为空白，但必须保存传入的原字符串；非空说明中的空格、换行等不能自动修改。展示时可以转义 Markdown，不能改变清单里的声明。

## 3. 文件保护和证据

本轮复验前纳入保护的 1308 个现有文件均未改动或丢失。额外对照任务二 R2 的原始 874 文件基线，也全部一致。任务三这三份交付的实际哈希与回执相符：

- receive_demo_batch.py：1591848ad69f7c34390e2e80bfc7af0fcd434b0835c75a22989ffc3f388fafee。
- test_receive_demo_batch.py：4bbc8875a953cdf854ecbe7ea5a74965a45c08bd112f2b77777915283fef908c。
- BATCH_RECEIVE_GUIDE.md：9493c9867b486761c04cee896bcde13d1fd9cb22e3ae9f94339da19a4be9cb65。

验收证据目录：

    D:\harness work\audit_sa_project\data\reviews\task003_20261010_221610

其中 acceptance_summary.json、independent_probe_summary.json、normal_batch_inspection.json 记录结论与观察；command_log.json 记录真实测试命令、退出码和独立日志；probe_receive_failures.py 保存内存模拟方法；source_hashes_before／after.json 保存本轮保护基线。

新测试容器：

    D:\harness work\audit_sa_project\data\batches\task003_gpt_20261010_221610

其中 independent_probes 保留了所有新增探查批次，包含不完整的失败现场。目录后缀采用 UTC 时间；本报告日期采用北京时间。

GPT 的哈希汇总辅助命令曾因 Windows 路径键分隔符不匹配触发一次 KeyError，修正路径读取后完成了全量保护核验；此事没有改动被审程序，也不计入其缺陷或通过案例。

## 4. 交接和停止点

将本报告与 TASK-003-R1.md 一同转交 DeepSeek。只修任务三接收器、对应测试和说明，新增 EXEC_REPORT_003_R1.md 及全新测试批次；既有成果、回执和故障证据保持原样。

主理人目前只负责转交，不需要手动运行程序或模拟批准 Gate 1。返修后仍由 GPT 验收。任务四、正式契约、业务批次放行和人工职业判断均未启动。
