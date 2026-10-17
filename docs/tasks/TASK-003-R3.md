# TASK-003-R3：补齐最后两处成功条件及哈希留痕

日期：2026-10-11。执行端：DeepSeek；验收：GPT；主理人负责转交。

## 1. 当前状态

R2 的 52 例已由 GPT 重跑全部通过，正常清单和材料哈希也已核实。GPT 补充复现了两处仍会错误就绪的遗漏，以及一个哈希读取的已知状态丢失问题。

先读 docs/reviews/REVIEW_TASK_003_R2.md 全文与本卡。保留当前流程，只作三处局部修复；不要继续重构接收器或增加新框架。原任务三与 R1／R2 的业务边界不变，不推进任务四。

项目：D:\harness work\audit_sa_project

解释器：D:\harness work\audit_sa_project\.venv\Scripts\python.exe

GPT 仅写验收材料与复现证据，未修改实现。

## 2. 文件范围

仅修改 scripts/receive_demo_batch.py、tests/test_receive_demo_batch.py、docs/BATCH_RECEIVE_GUIDE.md。

仅新增 docs/EXEC_REPORT_003_R3.md，以及 data/batches 下全新返修／测试目录。

其余全部只读：规格、草案、任务卡、旧回执、GPT 证据、所有既有批次／数据／答案册、生成器、任务二回归脚本及 checker。冻结 checker 哈希：

    a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8

不安装依赖、不初始化 Git；不做标准化、入库、规则、AI 建议或审批。仍是 DEVELOPMENT_ONLY、DRAFT_NOT_IN_FORCE；两项批准 null，next_step_allowed=false。

## 3. 仅修以下三项

### A. 必需一致性检查：未知也必须阻断

当前 hash_source_after 的比较只在值非 null 时执行，导致读取失败被跳过。修复这个成功条件，而不只是把 stable_during_run 记成 null。

对原输入、快照、真实接收脚本、真实 checker 在核验结束时的哈希：

- 每项必须取得有效哈希，才能判定本次一致性核验完成。
- 读取失败、文件消失或返回未知，记录对应文件、阶段、read_error，状态 FAILED_RUNTIME，入口退出 2。
- 值可保留 null；不能因 null 而跳过失败处理，不能让未知比较满足成功前提。
- 成功批次必须有原输入复制前／复制后／结束时、快照核验前／后全部相等；两个执行脚本前后哈希均已知且相等。
- 本项同样适用于 checker 本来退出 1 的批次：质量问题之外发生一致性读取错误，应升级为运行失败／退出 2。
- 不要把 hash_info 的错误信息仅通过 get('sha256') 丢掉；不伪造已验证状态，也不以新一轮成功读取抹去本次已发生的运行错误。

保留当前原子提交、失败清单／材料同步、已有代码副本比对等有效实现。

### B. 固定字段映射要检查键存在

对 structure.sheets_found 中实际存在的固定工作表，sheet_field_mapping 对应条目必须包含 SPEC_V1 四表字典中的每个固定字段键（总计 22 个固定字段）。不能只遍历当前已有 items。

- 缺少一个必需键，或对应映射对象为空：报告结构无效，FAILED_RUNTIME／退出 2，不产生就绪状态。
- 必需键存在且值为 null：这是已提供的“未映射到列”信息，按结构接受，再保留 checker 的质量阻断结果。
- 值为正整数时接受；布尔不算列号。
- 原工作簿实际缺失某张表时，不要求该表的映射条目，不能因此把合法的缺表质量报告当成格式错误。

只核实报告接口，不复制 checker 的业务逻辑，不根据答案册修报告。

### C. 哈希读取保留已知存在状态

调整 safe_hash_file／hash_info 的局部错误处理：

- 存在性已确认 true，随后读取字节失败：exists=true、sha256=null、read_error 为真实错误。
- 存在性检查本身失败，才记 exists=null。
- 文件确认不存在，记 exists=false。

上述读取错误仍导致所需核验失败，不能因为 exists=true 就放行。相应更新测试断言和说明，保持已知／未知语义一致。

## 4. 实际验证

在新容器重跑当前 52 例（已包含 22 份 fixture），保留旧断言与真实 CLI／内存模拟分类，不额外重复运行任务二整套验证。

再增加与上述修复直接相关的检查：

1. 分别仅在核验结束读取原输入、快照、真实接收脚本、真实 checker 哈希时模拟失败。复制前及复制后的哈希正常，确保测试确实进入结束分支，而不是重复覆盖“初次哈希失败”。四种情况均退出 2、FAILED_RUNTIME，保留失败原因；不能候审就绪。
2. 对 C14a 质量阻断输入叠加一次结束哈希失败，确认入口是 2，而非继续返回 1。
3. 从本次新生成的有效报告中删除一个固定字段映射键，复现 payables.payable_amount 缺键；必须退出 2。再覆盖对应映射对象为空。可用针对性结构断言验证其余固定表同样要求必需键。
4. 正例：C14a 的 payable_amount 键存在且值为 null，报告结构仍有效、入口仍为质量阻断 1；实际缺表时也不能单因缺失表的映射条目被判运行失败。
5. 存在性已知的 SPEC 文件，仅在 read_bytes 阶段模拟失败：退出 2、有失败清单，exists=true、sha256=null、read_error 非空。不要只替换整个 helper 后断言存在性未知；那不能覆盖本问题。

可参考 GPT 本轮 probe_receiver_r2.py 的复现方式，只读该文件。所有故障只在内存或新测试副本注入；不改真实源码、原文件、既有批次。新测试报告被故障注入修改时保留其修改前字节或清楚记录注入内容，不能冒称 checker 自己生成了无效报告。

如果 helper 被整体替换、在判断存在性前即抛错，exists=null 仍是合理结果；不要把它与“exists 已成功、后续字节读取失败”的案例混为一谈。

每次调用独立日志；实际数量从结果计算。预期负向案例和脚本失败分开，任何未预期错误／断言／只读保护失败使整个测试进程非零。不要为了通过新测试放宽旧断言。

建议命令（已存在则换后缀，不删历史）：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r3_tests_01'

## 5. 回执和停止

新增 EXEC_REPORT_003_R3.md：记录三项局部修复、最终哈希、完整实际命令／日志、实际结果与数量、失败尝试、未解决项、获准修改与只读文件保护情况。旧回执和旧清单保留，不迁移修补。

给出一份新主演示批次或本轮 MAIN_demo 的证明，包含正常 8 项产物、正确行数／金额、最终材料与报告哈希，以及全部必需一致性比较已知且通过。

相同问题三次仍失败或上下文不足，保存实际进度、错误和下一条命令后停止，不自行扩大修改。完成后返回 EXEC_REPORT_003_R3.md 路径和简短回执，等待 GPT。

主理人只负责转交，不需技术复测或模拟 Gate 1 批准。不要推进任务四。
