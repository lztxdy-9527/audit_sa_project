# TASK-003-R2：收口报告校验与最终清单

日期：2026-10-11。执行端：DeepSeek；架构与验收：GPT；主理人负责转交。任务三仍未通过，不推进任务四。

## 1. 当前状态和开始前读取

任务一规格／契约草案已固定；任务二已验收通过。你完成的任务三 R1 中，来源声明保真、两个代码留档比对和原 21 个回归案例均经 GPT 重跑通过；22 份既有 fixture 的真实接收结果也全部符合预期。

剩余的是报告 null／内部必需内容、finalize 失败处理、最终清单真实性三组问题。详见 docs/reviews/REVIEW_TASK_003_R1.md。这些属于 R1 未收口部分，不增加新业务、审批或安全功能。

先读本卡、上述复验报告，以及当前 receive_demo_batch.py／test_receive_demo_batch.py。原 TASK-003_DRAFT.md 与 TASK-003-R1.md 的业务边界继续有效；若想精简实现，可整理内部小函数，不引入新框架或扩展功能。

项目：D:\harness work\audit_sa_project

解释器：D:\harness work\audit_sa_project\.venv\Scripts\python.exe

GPT 只新增复验材料和证据，没有替你修改实现。

## 2. 允许修改和冻结范围

仅修改：

- scripts/receive_demo_batch.py。
- tests/test_receive_demo_batch.py。
- docs/BATCH_RECEIVE_GUIDE.md。

仅新增：docs/EXEC_REPORT_003_R2.md，以及 data/batches 下全新返修演示／测试目录及必要文件。

其他文件全部只读，尤其是 checker、生成器、任务二回归脚本、SPEC_V1、契约草案、原输入／答案册、任务卡、旧回执、所有既有批次和 GPT 证据。不要修补历史批次里的清单；它们用于保留当时的错误现场。

冻结 checker SHA-256：

    a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8

不安装依赖、不初始化 Git、不做标准化／入库／R01—R04／AI 建议／正式契约／人工审批。继续 DEVELOPMENT_ONLY、DRAFT_NOT_IN_FORCE、两项批准 null、next_step_allowed=false。

## 3. 收口规格

### A. JSON 解析成功后，无条件进行对象／必需内容检查

不要再用 `report is not None` 区分“解析成功”和“没有报告”。JSON `null` 是解析成功但结构无效，必须 FAILED_RUNTIME、退出 2；不得候审就绪。

按冻结 checker 的实际格式，核实材料消费的内容。不要只遍历已存在的键，以致空对象自动通过：

- 顶层必须是对象；保持 result、工作簿／checker 哈希、区段类型、退出码一致性等既有检查。
- row_accounting 必须包含 suppliers、payables、payments、allocations 四项，每项有 source_rows、accepted_rows、blocked_rows、blank_rows；值为非负整数，布尔不算整数。checker 在缺表或质量阻断时也会输出这些统计项。
- amount_summary 的 known_valid_subtotals_cents 与 complete_totals_cents 必须是对象，均含 payables_payable_amount、payments_amount、allocations_allocated_amount 三个键。键的值可以是整数或 null；父区段不能为 null、空对象或缺失。unusable_amount_cells 也必须为对象，保留 total／by_reason／sources 的类型检查。
- structure.sheets_found 是字符串数组；sheet_field_mapping 是对象，对实际存在的四种固定工作表，应有对应的固定字段映射，列号为正整数或 null，布尔不算列号。未知额外工作表不要求映射；实际缺失的工作表不能因此让一份结构正确的质量阻断报告被误判为运行失败。
- reconciliation 中材料使用的 status、known_plus_missing_equals_master 必须有键；后者允许布尔或 null，不能用 get 默认值把缺键当成已提供的 null。保留诊断区段的既有类型要求。
- 保留 issues、issue_counts_by_code 等既有检查。合法空问题数组和合法金额 null 仍允许；不要把质量问题本身当作报告格式错误。

只检查接收器消费字段的存在／类型，不重新计算金额、问题总数或 checker 业务规则，不引入完整通用 schema 框架。

无效报告保留原字节、路径、真实存在状态与可获取的哈希；不可用时不传给正常材料渲染，不出现零问题或成功表述。结构有效的质量阻断报告继续 BLOCKED_QUALITY／退出 1。

### B. finalize 的读取、拼装、写入也必须能留下失败信息

把收尾阶段纳入运行失败处理。不能只捕获 execute_batch；build_manifest、artifact_info、SPEC／契约／报告／日志哈希等步骤同样可能失败。

建议将可失败的文件读取与清单对象拼装分开，保存已知信息和错误，再用这些信息生成清单。不要在错误恢复时无条件重试同一个会抛错的哈希读取，导致失败清单永远无法生成。

- SPEC 或报告等文件存在但无法读取时，保留 exists=true、sha256=null，并记录读取错误；未知存在状态允许 null，不能伪造不存在或有效哈希。
- 目录仍可写时，尽可能生成 FAILED_RUNTIME 清单与“核验未完成”材料，退出 2；不能让 finalize 抛出未捕获异常并以 1 退出。
- 清单首次写入／关闭失败，即使部分或完整字节已经落盘，也不能直接返回并遗留可避免的成功状态。后续可写时保存失败清单及失败材料，并记录原错误。
- 可采用新批次内的临时文件及原子替换，避免失败的成功候选清单直接成为正式 batch_manifest.json；实现方式由你决定。错误后的临时／部分现场按原要求保留，不删除整个批次或重跑覆盖。
- 存储彻底不可写时仍退出 2，在 stderr 写明失败及现场路径；不要求凭空生成文件，不声称已成功保存失败清单。

同一次运行内更新自己新建批次的状态是允许的；不授权改动历史批次。重建清单时保留真实原始失败阶段，不要被后来的 render／write 阶段覆盖。

### C. 最终清单对应最终现场，未知值保持未知

- 先完成材料写入，再取得该材料的实际存在状态和哈希，更新最终清单。正常与质量阻断批次的 gate1_packet.exists 必须为 true，sha256 必须与真实文件一致。不能原封不动落盘写入材料前构建的清单。
- packet、报告、日志、快照、两份代码副本的检查须对应实际文件；本卡不用给清单计算自引用哈希。只有要求的材料齐备且全部一致，才能宣布候审就绪。
- 未读取到 source.size_bytes 时用 null，不能默认 0；如果后来成功取得真实大小，可以记录真实值。
- stable_during_run=true 必须有两次有效哈希作为依据；两端都为 null 时是未知，应记 null，不能因 None==None 写 true。
- checker 启动失败时，started 不能是 true，exit_code 为 null。可以另加 attempted 字段保存尝试信息；确实无法判断是否启动时记录 null。成功完成子进程调用时再确认 started=true。
- 仍然只记录实际命令与退出码；未执行的步骤不冒充完成，不虚构报告。

如改变清单字段或版本，更新接收说明；不迁移或修正既有清单。

## 4. 固定验收矩阵

保留原 21 个回归案例及断言，新增下列检查，在全新容器执行。完整复现方法可读 GPT 证据目录中的 probe_receiver_r1.py，但不要修改或复制旧证据作为新结果。

1. 有效 C01、主演示文件和 C14a 质量阻断：除原断言外，验证最终清单的 gate1_packet.exists=true、sha256 与磁盘一致，且原有 8 项正常产物齐全。
2. JSON `null` 报告、checker 退出 0：入口必须退出 2，清单 FAILED_RUNTIME；报告不可用，不显示零问题，不出现候审就绪。
3. 以本次新生成的有效报告为模板，分别删除／清空四表行数统计、三项金额必需键；也覆盖金额父区段为 null：均是运行失败。金额键存在而值为合法 null 的质量阻断正例仍须通过结构检查。
4. 最终清单阶段 SPEC 哈希读取抛 OSError：退出 2、可写目录下保存 FAILED_RUNTIME 清单；哈希未知且有错误记录，现有文件不被虚构为不存在。
5. 最终报告文件哈希读取抛 OSError：同上，原报告保留；不能因为 artifact_info 失败而再崩溃。
6. 首次清单写入／关闭在产生字节后抛 OSError，之后可以写入：退出 2；最终正式清单 FAILED_RUNTIME、receive_exit_code=2，失败材料不含就绪状态。若采用临时文件，针对实际提交路径模拟等价故障，不能通过改变注入位置绕过要验证的失败。
7. 输入初次哈希失败且尚未取得大小／源码稳定性证据：退出 2、有失败清单；未知值不填 0，两端未知不写 stable=true，checker 未启动。
8. checker 无法启动抛 FileNotFoundError：退出 2，started=false 或有依据的 null、exit_code=null，保留尝试参数与错误，不能虚构质量报告。

继续覆盖 R1 的材料一次写入失败、永久写入失败、报告数组／缺区段／语法错误、两份代码副本不一致、来源原样保存等案例，不能为了补新问题削弱旧断言。

报告校验本次有修改，应再将 22 份既有 fixture 通过真实接收器运行一次：14 份质量通过、8 份质量阻断；不重算规则答案，不必运行任务二整套 50 例。可集成到本测试脚本或另存一次清楚的兼容性记录，不需要再建测试框架。

所有故障仅内存模拟／新测试副本，不改磁盘源码或原数据，不提供生产故障开关。每次调用独立日志，准确区分 CLI 与内存模拟。预期负向案例和脚本自身失败分开；任何断言、未预期异常或保护失败，整个测试进程非零，不宣称总体成功。

数量从实际记录统计，不预写“28 例”或“50 例全通过”。不需要在本卡继续增加与上述收口无关的故障场景、功能或性能测试。

建议命令（目录已存在时换新后缀，不删除旧目录）：

    & 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r2_tests_01'

## 5. 回执与停止

更新接收说明，新增 EXEC_REPORT_003_R2.md，记录三组修复、修改文件与最终哈希、完整实际命令／日志位置、真实用例结果及数量、失败尝试和未解决项。

只读保护清单应排除本卡获准修改的三份文件，覆盖 checker、生成器、规格、草案、原数据、旧回执、既有批次和 GPT 证据；记录前后哈希。不要把获准修改的文件变化说成保护失败，也不要因此漏掉其他只读文件。

保存新版本的主演示批次或在测试 MAIN_demo 中给出完整证明；原批次保持原样。完成后返回 EXEC_REPORT_003_R2.md 完整路径和简短回执，等待 GPT。

同一问题三次仍失败或上下文不足，按原要求保存实际进度、错误和下一条命令后停止。主理人本轮只负责转交，不需执行技术测试或模拟批准。不要推进任务四。
