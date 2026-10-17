# TASK-003-R2 复验：两处阻断遗漏，需小范围返修

日期：2026-10-11（北京时间）。验收端：GPT。结论：CHANGES_REQUIRED；执行 TASK-003-R3，不推进任务四。

R2 已修复此前列出的 null 报告、内部行数／金额缺键、最终清单与材料不一致、收尾错误及可恢复清单写入失败等具体案例。剩余两处仍会错误标记“候审就绪”，不满足原有成功条件；另有一处留痕精度问题可在同一哈希函数中一并修复。无需再次改造接收流程。

## 1. 已通过的实际复验

GPT 在全新容器运行：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r2_gpt_20261011_043946'

实际退出 0；52 例全部通过，33 次真实 CLI、19 次内存模拟，104 份独立调用日志。含 22 份既有 fixture：14 份质量通过、8 份质量阻断，未被错误归为运行失败。39 个内建受保护输入及测试输入副本未变。

GPT 另行核对 DeepSeek 的 dev_receive_003_r2_main_01、GPT 新建的 C01_valid、MAIN_demo 和 C14a_missing_column：正常 8 项产物齐全；输入与快照字节相等；源码副本与执行版本相等；最终 packet／报告哈希与磁盘一致。主文件四表仍为 20／993／1000／1005，缺失关联净额仍为 1000000 分；C01 净额 500000 分；C14a 不可用的完整勾稽金额为 null。

所有运行保持 DEVELOPMENT_ONLY、DRAFT_NOT_IN_FORCE、两项批准 null、next_step_allowed=false。

## 2. 阻断一：结束时必需哈希未知，仍然候审就绪（P1）

源码位置：receive_demo_batch.py 第 613—655 行附近。

R2 将哈希读取改为安全返回 null，后续比较却仅在“值不是 null 且不相等”时记录失败。因此，读取错误反而绕过了比较。

- T01_source_end_hash_unreadable：原输入初次及复制后的哈希均正常，只在核验结束读取原输入哈希时模拟 OSError。实际 source_after_check=null，却退出 0、DEV_GATE1_PACKET_READY、failure_reasons=[]。
- T02_checker_end_hash_unreadable：checker 初次哈希及留档均正常，只在结束时读取真实 checker 哈希失败。实际 sha256_at_end=null、stable_during_run=null，却同样退出 0、候审就绪且无失败原因。

这属于 R2 安全读取改动引入的遗漏。未知值诚实记为 null 是必要的，但不足以满足“成功前必需核验已完成”。输入／快照／两份执行源码的结束哈希都是成功条件；未知必须导致 FAILED_RUNTIME／退出 2，不能跳过。错误原因也不能在只取 get('sha256') 时丢失。

## 3. 阻断二：固定字段映射没有检查必需键（P2）

源码位置：receive_demo_batch.py 第 178—196 行附近。

T03_required_field_mapping_missing：真实 checker 对新 C01 快照运行结束后，只在该新批次报告中删除 structure.sheet_field_mapping.payables.payable_amount；原始报告字节另存为 quality_report.before_injection.json。输入、源码和两个报告内哈希均不变。

实际接收器退出 0、DEV_GATE1_PACKET_READY、report_validation.valid=true，没有发现映射缺键。原因是仍然只遍历 fields.items()，没有检查固定字段集合。

R2 卡已明确要求“实际存在的固定表应有对应固定字段映射”。应区分：

- 报告中缺少 payable_amount 这个键：报告不完整，运行失败。
- 键存在、值为 null：checker 已明确告诉接收器未映射到该列；如果报告其他结构正确，应保留 checker 的质量阻断结果。

检查固定键存在性即可，不重写 checker，也不重新计算业务金额。

## 4. 同函数内的留痕精度项（非独立阻断）

源码位置：receive_demo_batch.py 第 113—135 行附近。

T04_existing_spec_read_bytes_failure：Path.exists() 已成功返回 true，仅随后读取 SPEC 字节时抛 OSError。接收器正确退出 2、FAILED_RUNTIME，保留失败清单和材料；但清单 spec.exists=null，丢失了已知的存在事实。说明文档目前声称此时会保留 exists=true，与实现不符。

修改哈希错误处理时一并保留已取得的 exists=true；只有存在性检查本身失败时才为 null。该案例没有错误就绪，不是本次暂缓验收的单独原因。

## 5. 版本、保护与证据

实际哈希与 R2 回执一致：

- receive_demo_batch.py：8ae9a51139b8b82cccf7e46d81c3e9d0e14482a0328831dad5bc2d3eb96432e6。
- test_receive_demo_batch.py：34c4171ed39283c443a583808785eaabbc431cea6ab0fd9483e06f53507d5459。
- BATCH_RECEIVE_GUIDE.md：7f5a35f937b0ba29f4f96a995ac08f0a4ad2653b561734af2e90e99f31f82dc1。
- 冻结 checker：a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8。

本轮复验前的 3225 个现有文件全部未变。对照 R1 复验的 1805 文件基线，仅三份获准文件变化；对照任务二原始 874 文件基线，全部未变。

证据目录：

    D:\harness work\audit_sa_project\data\reviews\task003_r2_20261011_043946

其中 acceptance_summary.json、normal_batch_inspection.json、independent_probe_summary.json 保存观察；command_log.json 是 52 例回归命令，independent_command_log.json 及 probe_receiver_r2.py 保存四次补充复现；source_hashes_before／after.json 保存保护记录。

测试容器：

    D:\harness work\audit_sa_project\data\batches\task003_r2_gpt_20261011_043946

T01—T04 只在内存中注入故障；T03 仅修改新测试批次中的报告并保存修改前字节；四次均使用真实 checker，没有修改原数据、磁盘源码或既有证据。

将本报告与 TASK-003-R3.md 全文转交 DeepSeek。主理人不需技术复测或模拟 Gate 1 批准。返回 EXEC_REPORT_003_R3.md 后，由 GPT 复验；正式契约、人工放行和任务四均未启动。
