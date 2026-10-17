# TASK-014 验收记录

日期：2026-10-12。验收端：GPT。结论：**不通过，返回 TASK-014-R1 定点修正；不关闭 TASK-014，不推进 TASK-015。**

当前交付的正常复算路径已真实跑通，但存在一次调用内的失败误报成功，以及影响验收结论的测试和证据缺口。执行端的 `7/7 PASS` 不能作为本轮通过依据。TASK-013-R4 的既有通过结论不受影响，由人类按既有记录在 DSH 关闭其卡片。

## 1. 交付身份与证据层级

六项写后实测哈希均与交接消息相符，记录于 `data/reviews/task014_gpt_20261012_213445/source_hashes_before_selected.json`，独立小样运行后仍相同。

- 宿主：`1c12f065cafbf0fb65a2036c51f086dd544b77abffc5aa237cd892950e11d083`。
- 指南：`44718decb24e1a2319fab722a411100caa7f3a4b9cf33c774bb9a1f8b6034472`。
- 新测试：`97b89bbc157abeb391a37143e8f87114cf161e73f37ee14f2c89bef823bd9675`。
- 回执：`ec3a00282347ba94bff61f29439797f59dd324b5783601857007159fe8ea37d0`。采用外置交接哈希，无需回写自身。
- 冻结复算核心：`8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`。
- TASK-013 测试：`27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca`。

执行端自报完整入口退出 0。GPT 读取了交付容器 `task014_run_02` 的回执、summary、调用日志和故障现场；其中 summary 的确为七项 PASS。**GPT 未重跑该完整入口、MAIN 或 TASK-002—013 历史入口。** GPT 另在全新 C06b 批次实际建链、调用冻结核心，并完成下面的定点复验；这些实测与执行端自报分别记录。

## 2. 已验证的正常行为

独立小样的冻结复算核心真实调用一次，完整返回另存 `actual_core_return.json`，与落盘报告严格规范 JSON 相等；复算输入在该次核心调用前后指纹相同。C06b 复算条数为 R01/R02/R03/R04 = 0/1/0/0。

0006 的 revision 为严格整数 6，前序指向 0005 实际字节哈希，完整 workflow 与 0005 相等；无 0007，两项真实批准 null、next_step_allowed=false，数据库字节与 artifacts 声明一致。同进程替换复算、筛查、标准化、装载四个真实函数为调用即失败后，公开 `inspect_dev_batch` 正常恢复，调用命中为零，批次目录字节集合不变。详见 `final_readback.json` 与 `same_process_readonly.json`。

## 3. 阻断项

### B1 / P1：最后一次复算摘要读取后的变更仍返回 READY

宿主 `inspect_dev_batch` 在第 3192 行读取最后一次复算输出前调用 `_verify_crosscheck_tail`，其后检查返回对象及 checkpoint/Gate2，却未再次核验磁盘复算产物。返回对象仍为原始对象时，报告在该次读取成功后被改动，本次调用会错误返回 `status=READY`、`crosscheck_status=RULE_CROSSCHECK_RECORDED`。

GPT 先在正常调用中实测读取顺序：第 1 次来自 `_verify_crosscheck_operation`，第 2 次来自 `inspect_dev_batch` 的摘要读取。随后只在第 2 次真实 reader 返回后单次改报告的 `recomputed_facts.findings`，wrapper 原样返回，返回对象指纹不变。**当前 API 错误成功；撤销 wrapper、保留变更的 CLI 退出 1；只恢复报告原件后 CLI 退出 0，目录集合恢复一致。** 唯一变化路径是 `workflow/crosscheck/crosscheck_report.json`。

交付 G5 在 `hits==0` 时注入，实际 `reader_returns=1`，测的是第 1 次读取后变更。记录把它称作“最后一个读取边界”，不能证明任务卡要求，且掩盖上述实现缺陷。证据：`positive_reader_sequence.json`、`late_final_reader_probe.json`、两份 CLI 原文。

### B2 / P2：半写现场没有恢复原失败诊断与退出类别

GPT 只读实跑交付 `g4_partial` 的新进程 status：有效 `crosscheck/failure.json` 明确记录 `WorkflowHostError`、`target_exit_code=2`，恢复却先解析半写 0006，返回 `WorkflowHostBlocked`／退出 1，只剩 JSON 解析错误。`_load_host_context` 先调用 `_load_checkpoint_chain`，再读取复算失败诊断，导致有效运行失败被遮蔽。这不满足任务卡第 5 节的“相同诊断和退出类别”。

交付 G4 只检查恢复 `!=0`，因此漏检。失败诊断还把复算 writer 故障记成 `stage=prepare_gate2`，没有保存原始 cause 结构；交付故障记录也只保存包装消息。半写分支另行打开文件并重造 writer，未按任务卡复用真实 writer 故障方法。证据：`partial_recovery.json`、`delivery_partial_status.stdout.txt`，以及交付 G4 两份原记录。

### B3 / P2：验收证据存在无效观察和缺少计数审计

这些是影响“已经验证”结论的证据问题，需要修正测试和新回执，不能只改说明文字：

- G6 在父进程安装核心禁用补丁，实际 status 通过 `subprocess.run` 执行，补丁未进入子进程。输入“before”副本也是在真实核心返回后取得，再与同一时点指纹比较，不能证明调用前后不变。GPT 的补证说明当前正常行为可行，但不能追认原测试的方法。
- 交付容器 `core_returns/` 为空，`summary.core_records=[]`；G1 真实返回只留指纹，未独立保存完整原返回。故障记录不含完整异常链；所谓 `full_text_bytes` 使用字符数，且未保存待写完整 UTF-8 文本供复验。
- 测试没有公开 API 调用清单、receiver/checker 双向计数核对，也没有任务卡明确要求的 missing/unregistered 正式失败判定及“缺一条记录会失败”隔离自测。`matched_batches` 只在 G1 手动加一次，不能代表所有真实 MATCHED 报告。现有 CLI 日志可以独立核对，但不能替代缺失的正式测试门槛。

修正只需保存现有入口的直接记录与文件引用，不要求再造通用观察框架。GPT 的独立调用数见 `final_readback.json`：公开 API 共 9 次、CLI status 3 次、实测复算核心 1 次；原 probe_summary 中的 8 是经过通用 api 记录器的子计数，另有直接调用的晚变更 API 1 次，已明确区分。

### B4 / P2：复算输入与 started 协议未按卡完成

`crosscheck_dev_batch` 通过 `_read_gate2_outputs` 取得 normalized。该 helper 第 960 行先 `_read_json`，第 964 行再另读文件计算哈希，未用同一读取缓冲绑定对象与字节。筛查报告已使用同缓冲 helper，normalized 尚未完成任务卡第 3 节第 3 步要求。新增 `started.json` 也只保存 normalized/screening 文件哈希，缺少卡上明确要求的两项规范对象指纹；恢复端未要求这些字段。此项为静态审阅确认的协议缺口，没有将其表述为已复现的业务金额错误。

## 4. 保护比较、执行边界与停止

完整保护比较结果见本轮 `protected_files_comparison.json`：基线 115029 项，单次实扫 116050 文件，changed 恰为宿主/指南两项，missing=[]、unexpected_changes=[]。当前树单次扫描见 `source_hashes_scan.json`；不对嵌套历史基线重复扫描。下一轮差异读数 `source_hashes_after.json` 以该扫描加本轮已知新增评审文件的最终哈希组成，不构成本任务通过。最终机器结论另存 `acceptance_summary.json`。

独立核对交付 CLI 共 76 次、原始 stdout/stderr 共 152 文件，现有日志引用 missing/unregistered 均为空，七个 CLI 分项计数与 counts.json 相符。交接中“65 份 CLI 原文”登记为非阻断的说明错误，不回写旧回执。已有 8 份 MATCHED 报告不等于 8 次成功完成，其中包含 writer 故障现场；counts.json 的未限定 `matched_batches=1` 应在 R1 改为准确命名或从记录推导。完整 ledger 见 `delivery_evidence_audit.json`。

GPT 实际命令为项目 Python `-B` 执行本轮 `independent_probe.py`、`final_readback.py`、`scan_and_audit.py`。前两者退出 0 表示取证脚本完成，**不代表 TASK-014 验收通过**。发现 B1 后停止扩大运行范围，没有重复完整建链或重跑交付完整入口。

本轮新增评审文档、修正卡与独立证据；未修改交付源码、指南、既有测试、回执、历史批次或数据库。对交付半写现场仅执行只读 status。唯一变更探针只操作 GPT 自建批次报告，已恢复原字节。

本轮证据目录：`D:\harness work\audit_sa_project\data\reviews\task014_gpt_20261012_213445`。
独立批次父目录：`D:\harness work\audit_sa_project\data\batches\task014_gpt_20261012_213445`。
独立数据库父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task014_gpt_20261012_213445`。

返回 `docs/tasks/TASK-014-R1.md`，仍只接独立复算；本轮不建立真实 Gate、不执行事实底稿或 AI。
