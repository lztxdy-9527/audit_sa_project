# TASK-014 草案：接入独立复算，停在复算凭证

## 1. 角色、起点与范围

你是执行端；GPT 负责架构和验收，人类负责审计判断与真实放行。项目 `D:\harness work\audit_sa_project`。先读本卡、`docs/reviews/REVIEW_TASK_013_R4.md`、`docs/RULE_CROSSCHECK_GUIDE.md` 和宿主指南相关段落；不需要重读整段历史对话。

TASK-013 已验收：宿主可以在显式模拟 Gate2 APPROVE 后真实运行筛查，写入 0005。当前开发流程为 接收 → 模拟 Gate1 → 真实标准化/SQLite → 模拟 Gate2 → 真实筛查。R01—R04、独立复算纯核心、事实底稿纯核心分别已有验收；本卡只把**独立复算纯核心接入宿主**，不重新实现四条规则。

本卡是开发态实施授权，不是正式契约或真实 Gate 批准。完成后停止，不推进 TASK-015。

允许修改两个既有文件：

- `scripts/run_demo_workflow.py`，起点 `ae5b7e24dd946a0a2186b8741b79af4173e091c362c4c210d8186e92d2cab4e2`。
- `docs/WORKFLOW_HOST_GUIDE.md`，起点 `c7963c5857580ae9f3d75e0b6c9e9d448f988b5c561745df63f60b1a92060cf5`。

只新增 `tests/test_crosscheck_demo_workflow.py`、`docs/EXEC_REPORT_014.md` 及全新本轮容器/批次/外置 SQLite 目录。不改 TASK-013 测试（冻结 `27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca`）、其他旧入口、上游模块、规则 SQL、规格、契约草案、答案册或历史产物。不能初始化 Git、安装依赖、清理历史目录或改看板代替交付。

主保护基线：`data/reviews/task013_r4_20261012_201824/source_hashes_after.json`。只允许宿主/指南两项既有文件变化、缺失 0。旧回执不回写。宿主新版本与旧批次绑定不兼容时如实拒绝，全部演示用新批次，不迁移旧批准或旧凭证。

## 2. 冻结核心与新接口

冻结 `scripts/crosscheck_demo_rules.py`：`8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`，版本 `TASK-007-crosscheck-1.2`。

必须真实调用现有 `verify_rule_facts(normalized, screening_report)`，只接收这两个内存对象。不传数据库路径、不从答案册取预期、不调用 SQL 筛查或生成器、不回写输入。`CrossCheckBlocked` 是前提阻断，`CrossCheckError` 是运行失败；两者按宿主现有异常模式转换并保留原因链。

新增 API：`crosscheck_dev_batch(batch_dir) -> dict`。

新增 CLI：`crosscheck-rules --batch-dir <existing-new-batch>`。已有六个子命令保留，共七个。CLI 退出码沿用 0/1/2，stdout 结构化 JSON、stderr 诊断。

实现版本升至 `TASK-014-workflow-host-1.0`；既有 TASK-012 checkpoint/manifest/Gate2 协议、TASK-013 screening 协议不盲目改名。新增版本单独固定为：`TASK-014-crosscheck-start-1.0`、`TASK-014-crosscheck-artifacts-1.0`、`TASK-014-crosscheck-failure-1.0`。准确更新宿主页首旧职责描述及指南。

## 3. 固定执行顺序

1. 共用恢复核验，要求当前恰为合法 0005、`DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED`。必须验证完整前序链、失败/未完成标记、来源/代码/SQL/配置/契约草案绑定及数据库字节，不只检查 phase 字符串。
2. 冻结控制器 `check_dev_action(..., SCREEN_AND_BUILD_FACTS, current_bindings=实测绑定)` 的 `simulation_allowed` 必须严格为 true。此处仍是开发态模拟允许。
3. 从既有 `workflow/gate2/normalized.json` 和 `workflow/screening/screening_report.json` 取得对象与字节哈希，解析与哈希使用同次读取缓冲；保存操作开始时不可变读数。复算前实读数据库字节与既有声明一致。拒绝已有 `workflow/crosscheck/`，不覆盖、不自动重试。
4. 独占创建 `workflow/crosscheck/`、写 `started.json`，记录批次、版本、运行绑定、0005 初始字节哈希、输入文件字节哈希与规范对象指纹。
5. **真实调用一次冻结 `verify_rule_facts`**。宿主只做接口/绑定校验和持久化，不重算业务规则。复算核心未实际调用就不得记成功。
6. 独占保存完整 `crosscheck_report.json`，关闭后读回，类型与内容严格等于该次核心真实返回。核对报告版本、开发态、截至日/期间、来源 SHA、normalized 实际规范指纹、screening 实际规范指纹与本次输入一致；JSON 文件字节哈希与规范对象指纹分别保存。
7. 按下节区分 MATCHED、MISMATCH、异常。成功时先写/读回 `artifacts.json`，再写 0006；任何收尾失败仍保留诊断，不宣告成功。
8. 最后一次控制器调用与最后一次摘要数据消费之后，复测本次所有消费对象对应的磁盘字节、静态绑定、数据库、宿主清单、0001—0006 与失败状态。预期只能来自初始同缓冲读取或本次真实 writer 返回值。不能把事后哈希当作最初预期。旧 0001—0005 前后字节不变才返回成功。

复用已有小型校验/末尾复测模式，不另造通用事件框架、I/O 读取观察器或新控制器状态机。

## 4. 成功、不一致与失败必须分开

**成功**必须同时满足：`batch_status=DEV_CROSSCHECK_MATCHED`、`matched is True`、`differences=[]`、十个维度全部存在且严格 `executed is True / matched is True / difference_count` 为整数 0（排除 bool/float），比较汇总一致。不仅检查一个 matched 标志。

固定十维度：`hit_keys, amounts_cents, related_ids, refund_facts, rule_identity, source_entities, source_rows, counts, statistics, overall_reconciliation`。字段协议与核心指南一致，缺字段/错类型是协议阻断，不能补默认值。

成功才追加 `workflow/checkpoints/0006.json`：

- revision 严格整数 6，`operation.kind=RUN_RULE_CROSSCHECK`。
- previous_file_sha256 等于操作开始时实读 0005 的字节哈希。
- workflow 与 0005.workflow 完整严格相等；不新增控制器 history、请求、决定或阶段。
- operation 绑定 started/report/artifacts 的固定相对路径、实际文件字节哈希、报告规范指纹，以及 artifacts 内嵌副本。
- artifacts 至少绑定本批次、宿主/核心版本与核心哈希、运行绑定、初始宿主清单与 0005 字节哈希、normalized/screening 文件与规范指纹、数据库固定推导路径与实测字节哈希、截至日、Gate2 决定正文实际指纹。路径与引用均严格校验，不能只检哈希长度。

对外仍为 `phase=DEV_GATE2_APPROVED`，新增 `crosscheck_status=RULE_CROSSCHECK_RECORDED`、completed_actions 增加 `RULE_CROSSCHECK`；保留筛查摘要。真实 gate1/gate2_approval 仍 null，next_step_allowed=false。0006 是复算完成凭证，不是新批准、审计结论或整个 SCREEN_AND_BUILD_FACTS 完成。

**MISMATCH 是核心正常返回的不一致结果**。完整保存报告与差异，给出 `BLOCKED_CROSSCHECK`、退出 1；没有成功 0006，不自动改筛查报告、不静默删差异、不继续事实底稿。核对报告来源绑定和差异/维度形状，不要因为“不是 MATCHED”就丢弃真实返回。结构化失败诊断可沿用本层 failure.json，必须准确说明不一致及完整报告位置。

**前提/协议阻断**退出 1，**运行/I/O 失败**退出 2。只有本次真正独占创建 crosscheck 目录后才写本次失败诊断，重复请求/早期拒绝不能污染已经成功的批次。failure.json 带固定版本、batch_id、host_version、严格 int 退出码、类别、阶段、完整原因与原始 cause；读回核验。

所有恢复入口共用失败/未完成协议：有效失败诊断不能被完整 0006 掩盖；非法 JSON/错版本/错身份/非文件诊断按协议阻断；有 started 而无成功凭证、半文件或未知 checkpoint 不退回旧 READY。诊断自身保存失败时如实报运行失败，不假称已落盘。

## 5. 恢复与边界

checkpoint 链只扩展到连续 0001—0006；0005 的语义在链有 0006 时仍按 0005 自己的初始哈希核验，不能误用链尾 0006 的哈希。特别检查现有 status 中对 0005 与 chain.current_file_sha256 的比较，避免扩展后误拒合法批次。

`status` 只读恢复 0006，核验报告/凭证/引用并返回真实摘要；不得重新调用复算、筛查、标准化或装载核心，也不得写文件。0001—0005 的合法阶段继续可恢复。真实失败/不一致批次能在新进程恢复相同诊断和退出类别。

不执行事实底稿，不调用 build_fact_packet/LLM/网络，不保存/预填人类判断，不建正式契约、不提供真实批准、不新增 0007。复算一致只表示两套确定性实现的事实核对一致，不证明来源真实性，也不抵御重写全部对象/哈希的同权限篡改。

## 6. 有界验证，避免重复长跑

新入口保持小而独立；不大量复制 TASK-013 的千行验证脚本。先用 C06b 跑通 API，再做必要负向。局部断言错误先定点诊断，不重新运行整套建链。完成后只要求一次全新容器最终入口；若成功后源码又改动，针对受影响范围复核并如实记录。

必需验证如下，不增加无边界 fuzz 或历史整套回归：

1. MAIN 完整建链至复算一次：真实返回 MATCHED，12 条筛查事实、3/5/2/2 分布及 R02 1,600,000 分保持；保存核心实际返回并逐项严格比较落盘报告。答案册不是运行依赖；比较来自冻结核心和既有事实基准。
2. 小样 C06b（退款/超额）、C03（无线索）、C07b（部分未匹配）成功；可先在同一个 C06b 新批次推进过程中验证过早调用拒绝、合法 0005、复算后 status、重复复算拒绝。HOLD/REJECT 对照选一个即可，两种状态机停止语义已由冻结控制器覆盖。
3. 一项真实 MISMATCH：在**新测试批次筛查造样阶段**包装真实 screen_sqlite，先取得真实返回，再深拷贝只改一处已存在的整数分事实，明确标注为故障造样；由宿主保存该测试报告。随后 crosscheck 必须真实接收该磁盘报告并返回 MISMATCH，保存完整差异，退出 1、无 0006，新进程 status 同类拒绝。不得把直接 raise、预写 MATCHED/MISMATCH 文字或另一个输入的报告冒充真实复算结果。必要时说明所改字段为何通过上游接口而应被独立复算发现。
4. 有限持久化故障：C06b 0006 真实 writer 半写一次；完整 0006 写完后再抛一次 sentinel。均保留现场、旧 0001—0005 前后字节不变、当前不报成功、新进程 status 非 READY。待写完整 text/部分字节、实际命中、异常 cause 与前后哈希真实留存。复用已验证故障方法，不重造 writer。
5. 一个晚变更探针：在 status 最后一次用于摘要的**真实复算输出读取成功返回原始对象之后**，只改 crosscheck_report.json 一次，wrapper 原样返回；本次即拒绝，撤销后 CLI 拒绝，恢复原件后 CLI 成功。用简短直接 wrapper 记录实际序号，不能通过提前 I/O 预读/seek 或下一次调用才发现来证明本次检测。另一个路径反例只改 0006.operation 的固定报告路径，必须指向字段阻断。
6. 0006 完整链、真实批准 null、next_step_allowed=false、无 0007；status 只读且不调用下游核心；未变化的正向恢复不能误拒；输入对象不被本层修改、数据库字节保持一致。
7. 保护核对：主基线只允许宿主/指南两项变化、缺失 0；冻结核心、规则 SQL、旧入口、历史产物不变。无需再对所有嵌套历史基线重复扫描多次，一次当前扫描可复用比较。

计数仅从实际命令/入口记录导出：CLI 与公开 API 分列，真实 receiver/checker 留痕双向对应，筛查/复算入口分列，故障实际命中/副本/模拟决定/真实批准分列。CLI 内不可观测的核心次数写 null；不把推导值冒充实测，不预设目标总数。不要求新建全部控制器调用的观察框架。计数审计的 missing/unregistered 必须影响正式判定，保留“缺一条记录会失败”的一个隔离自测即可。

每项负向同时检查异常类别及目标原因，正负实际输入、完整返回/完整异常与 cause、真实命令 stdout/stderr、调用前后哈希、文件引用保存。大对象只存一份，以相对路径和字节哈希引用，避免把全部 normalized/workflow 在每条日志反复嵌套。

## 7. 回执与停止

回执列两个修改文件、新测试及回执的完整哈希，完成内容、真实命令/退出码、用例分类、实际调用计数、故障现场、失败尝试、保护比较与未解决问题；最终回执哈希在文件写完后放交接消息，避免正文自引用。给出三条完整路径：本轮测试容器、批次父目录、外置数据库父目录。

完成前自查：成功 MATCHED 才有 0006，MISMATCH/失败不伪装成功；完整 0006 后失败仍恢复失败；0005 与 0006 各自哈希不混用；晚变更本次即拒绝；合法恢复不误拒；旧文件不覆盖；无 0007、无事实底稿/AI/人类判断/真实批准。

若发现本卡和冻结核心接口矛盾，记录具体字段及现场，停在受影响处，不改核心、不自改业务口径。完成后等待 GPT 验收，不推进 TASK-015。
