# TASK-014-R1 验收记录

日期：2026-10-12；验收端：GPT。结论：**不通过，返回 TASK-014-R2；宿主 B1/B2/B4 的本轮定点修复已确认，剩余为 B2 测试方法及 B3 验收证据问题。** 不关闭 TASK-014/R1，不推进 TASK-015。

## 1. 交付身份与证据层级

六项实测哈希与交接一致，独立复验前后相同，见 `data/reviews/task014_r1_gpt_20261012_221645/source_hashes_before_selected.json` 与 `source_hashes_after_selected.json`：

- 宿主 `8cf41ca8da12c77f5fc2a9827c936971aeeafd93a963746cc778a9c1d72031f7`。
- 指南 `322c333a21b73719edee7d74814e422d5ea88bd16bf834244bb7d95ec37fb2ad`。
- 本任务测试 `54f71aeaa49e7dfe2bde5abd8810266f5cc0656dceb8fc409855587441316f18`。
- 回执 `72c116946bf35fe807c4f241543b10cf11e9287d095cd72dbde6216266ed1ff8`，14034 字节；不需回写自身。
- 冻结核心 `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`；TASK-013 测试 `27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca`。

执行端自报完整入口退出 0；GPT 读取的 `task014r1_run_03/summary.json` 确为十项 PASS。**GPT 未重跑完整入口、MAIN 或历史整套任务。** 本轮实际运行交付入口的 `--only b1`，该模式实际执行 B1/B2/B4 三项检查，退出 0、三项 PASS；另在一份全新小样上复验真实 writer 的半写 I/O 故障。

## 2. 已关闭的实现问题

**B1 通过。** 正常调用中实测复算输出读取顺序为链核验第 1 次、摘要读取第 2 次，第 2 次后确有收尾复测。只在第 2 次真实返回后单次修改报告，本次 API 指向该报告阻断，撤销补丁后的 CLI 退出 1，恢复原件后退出 0。交付代码已补上之前缺少的最后摘要读取后的复测。

**B2 宿主行为通过，测试方法未关闭。** 交付小样的失败诊断恢复已保持 `crosscheck` 阶段和退出码 2。GPT 另外保留真实 `_write_exclusive_json` 函数，在其实际 `open(..., mode='x', newline='\n')` 得到的写句柄上产生一次半写 I/O 故障，实测真实 writer 进入一次、写入命中一次、独占模式 `x`，待写 76706 字节、部分 38353 字节。当前抛 `WorkflowHostError`，cause 为原始 `OSError`；failure 保存两环原因，stage=crosscheck、退出 2；新进程 status 同为退出 2，旧文件变化为空。证据：`actual_writer_partial_probe.json`、`actual_writer_pending_0006.json`、`real_writer_api_records.json` 及 CLI 原文。

**B4 通过。** Gate2 三个对象与各自文件哈希均使用 `_read_json_with_bytes`；started 的两项规范对象指纹已保存且恢复严格核验。定点篡改指纹会字段阻断，还原后成功。未迁移旧容器，旧协议不兼容属于已说明的预期行为。

因此下一轮冻结当前宿主，不继续改动已通过的实现部分。实现已通过的局部检查不等于本任务整体通过。

## 3. 剩余阻断

### R1-B2-E / P2：半写用例仍绕过真实 writer，待写文件引用不实

测试第 441 行附近的半写替身仍自行 `json.dumps`、`open(path, 'wb')`、写一半后抛错，没有调用真实 `_write_exclusive_json`。GPT 使用函数代码对象的直接入口观察，在交付定点模式中实测：**partial 的目标 0006 真实 writer 进入 0 次，throw 进入 1 次**。不能将 partial 称为已验证真实 writer 路径；本要求已经在 R1 卡第 3 节明确规定，不是本轮新增。

两份 pending 文件的元数据还与保存文件的真实字节不符：partial 声明 76445 字节，实测 78012；throw 声明 76375，实测 77942；两个声明 SHA-256 均不等于各自文件实际 SHA-256。原因是 `write_text` 的换行转换，而记录哈希来自另一个内存缓冲。任务要求的是可重新读取验证的真实文本/字节引用，不能把内存缓冲哈希标成文件哈希。证据：`submitted_subset_observation.json`、`delivery_evidence_audit.json`。

### R1-B3 / P2：输入观察和正式计数审计仍未满足修正卡

1. `capturing_verify` 第 594 行起先调用 `real_verify(...)`，再记录 `normalized_before_sha256` 与 `screening_before_sha256`，随后复制输入。所谓 after 也来自这个调用后副本。**仍是两个调用后值的比较**，与 R1 前相同，代码旁“调用前快照”注释及回执说法均不能成立。
2. `screen_batch(tamper=True)` 第 293 行直接调用 `host.screen_dev_batch(target)`，未经过 `record_api`。其成功现场及 `g3_mismatch_tamper_source.json` 已保存，但六条 API 登记没有该次公开调用。现有登记表与台账只能证明已被 recorder 收集的六条互相吻合，仍会把这个真实遗漏判为 missing/unregistered=0。
3. `checker_invocations=0` 与十一份批次 `batch_manifest.json` 矛盾。十一份均保存真实 checker argv、started=true、exit_code=0 和 stdout/stderr；checker 由 receiver 子进程启动，不是“本卡没有直接调用，所以实际调用为零”。须区分直接调用与真实下游执行，并按已存在的留痕双向核对。当前回执“checker 调用 0”是实质计数错误。
4. MATCHED 报告与成功凭证计数仍只在 G1/G2 手动递增。磁盘实际有 8 份 MATCHED 报告，6 份可解析 0006 且无 failure 的批次；counts 却写 4/4。需明确统计范围并从记录导出，不能以同名指标混用子集和总体。这里没有把 8 份报告都称为成功：两份属于 writer 故障。

完整文件、命令与清单证据保存于 `delivery_evidence_audit.json`。另外，API 异常文件的 `traceback` 为 `NoneType: None`，因为 `traceback.format_exc()` 在 except 之后调用；异常类别/原因链仍有内容，但该字段不能称为完整 traceback，应随测试修正。现有隔离自测可检测所删的登记项，却未覆盖实际已经漏登的造样公开入口及 receiver/checker 绑定，不足以关闭本轮 B3。

## 4. 保护与停止

独立保护比较及机器结论见本轮 `protected_files_comparison.json`、`acceptance_summary.json`。当前树单次扫描 117416 文件：R1 基线 116059 项，仅宿主/指南/本任务测试变化；R4 基线 115029 项，仅宿主/指南变化；两组 missing=[]、unexpected_changes=[]。不重复扫描嵌套历史基线。下一轮 `source_hashes_after.json` 由该次扫描加本轮已知新增评审文件的最终哈希组成，作为差异读数，不表示 TASK-014/R1 通过。

GPT 未修改宿主、指南、交付测试、回执或任何历史容器。新故障探针仅在 GPT 新建批次运行；交付 `task014r1_run_03` 只读。未运行事实底稿、AI、人类判断、真实批准、0007 或 TASK-015。看板由人类在 DSH 操作，TASK-014 及修正卡保持未关闭。

本轮取证脚本退出 0 表示复验/取证完成，最终任务判定仍是不通过。执行命令与实际来源层级见机器结论。

评审证据：`D:\harness work\audit_sa_project\data\reviews\task014_r1_gpt_20261012_221645`。
定点容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task014r1_gpt_20261012_221645`。
批次父目录：`D:\harness work\audit_sa_project\data\batches\task014r1_gpt_20261012_221645`。
数据库父目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task014r1_gpt_20261012_221645`。

返回 `docs/tasks/TASK-014-R2.md`，只修测试方法、证据和说明。
