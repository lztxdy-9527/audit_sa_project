# TASK-011-R1：修复恢复收尾、产物绑定与真实计数

执行：DeepSeek；验收：GPT。根目录：D:\harness work\audit_sa_project。先读 docs/reviews/REVIEW_TASK_011.md、本卡和 TASK-011_DRAFT.md；以本卡的收窄修复范围为准。

**本轮只关闭 F01—F04，不推进 TASK-012。**正常主链已经实际跑通，不重写架构、不新增 Gate2 决定或下游动作。

## 1. 范围和基线

仅允许修改三个既有文件：

- scripts/run_demo_workflow.py
- tests/test_prepare_demo_gate2.py
- docs/WORKFLOW_HOST_GUIDE.md

只新增 docs/EXEC_REPORT_011_R1.md，以及全新 data/workflow_host_tests/<新容器>/、data/batches/<新父目录>/、data/sqlite_tests/workflow_gate2/<新批次相对路径>/。

起点完整哈希：
宿主 2c94507a15b922f9f7e8fb83f6ae8fec8f56550552ce325e4f3d19569b39a03a；
测试 8fdca2b44994bea1410368b536d67268fe972f46e415cd640014cf362029e730；
指南 20180d9cfdb51fa38f2121e42514b1e41b94a1798acb01e2c4a8b68669362dc6。

主保护基线：
data/reviews/task011_20261011_133022/source_hashes_after.json。
相对该基线只允许上面三项变化，其余 0 变化、0 缺失。所有冻结上游、旧 test_run_demo_workflow.py、旧回执/验收单/任务卡、GPT 证据、旧批次和数据库、原合成 Excel/答案册全部不改。新旧基线累计变化如实分别说明。

因为恢复协议与 0003 引用将变化，宿主/清单/checkpoint 明确同步升至 TASK-011 对应 1.1；指南、测试固定期望保持一致。用最终固定代码新建批次，不迁移旧批次、不放宽旧版本绑定。仅修改版本常量与对应协议预期，不删除既有行为验证来“适配”。

不安装依赖、不建 Git，不修改装载路径限制或控制器。不改业务规则/金额/标识符口径。

## 2. F01：失败诊断不能被完整 0003 掩盖

必须复现 GPT 的精确情形：在本轮新批次上，wrapper 先调用真实 _write_exclusive_json 完成 0003，再抛带 sentinel OSError 原因链的 WorkflowHostError。prepare 返回失败且 failure.json 保存；撤销 wrapper 后正常 status 不得返回 READY。

将失败/未完成状态约束接入所有恢复入口的共用协议，不能仅在 revision < 3 时看 failure.json。只要完整有效的失败诊断存在，即使有可解析的完整 0003，也不得宣告本次准备成功；恢复其类别/阶段/原因和 1/2。不删除失败文件、不自动回退/重试、不把失败请求当成可继续状态。record/prepare 同样不能复用该现场。

失败文件的容器、必需字段、版本、原因列表/错误类别应先校验后使用。未知/非文件/非法 JSON/不完整诊断不得静默忽略，应协议阻断。保留原来半文件 checkpoint 的协议阻断行为：不能为恢复失败类别而跳过非法链；尤其原 40 字节 0003 仍不得作为有效状态。

成功正向必须没有 failure.json；正常完整 0003 仍可恢复。测试保存完整 prepare 异常、failure.json 和随后无 wrapper 的 status 返回，而不是只测一个 bool。

## 3. F02：统一核验所有已消费产物的收尾一致性

输入/代码 run_bindings 继续冻结在创建时。新产物仍通过独立 artifacts/checkpoint 引用，禁止把它们补进旧 run_bindings。

恢复/prepare 成功收尾时，保存并复测本次消费的固定 normalized.json、load_report.json、artifacts.json、数据库，以及相关 checkpoint/manifest 和失败状态。收尾应位于最后一次所需控制器调用之后、返回成功之前；与本次初始读取/本次写入值逐项一致，才能返回。不能只重测输入/代码及数据库，遗漏材料文件。路径固定，不能跟随清单读取任意文件。

保留当前写后核验，同时增加以下三个有界探针，各在本轮新副本/新批次中，命中次数必须为 1：

- status 初次材料核验后，在纯 prepare_dev_gate 重放返回时改变数据库字节；
- 同一时点仅改变 load_report.json 字节；
- 实际 prepare 的第二次 prepare_dev_gate（0003 保存后的重放）返回时，仅改变 load_report.json 字节。

本次调用应按目标路径拒绝成功；撤销 wrapper 后正常 status 也拒绝。记录真正 before/after 字节哈希、完整调用返回/异常、注入时点与次数。加上对应未变化正向，证明没有误拒绝正常新批次。

这只是检测一次调用内被观察到的普通变化，不宣称原子快照、并发安全或同权限隔离。不扩大到无边界 race/fuzz。

## 4. F03：完整 artifacts 引用与声明核验

0003.operation 必须保存 artifacts.json 的**实际文件字节哈希**，恢复时与固定路径实读值核对。对象规范指纹与文件字节哈希分开，不混用；不构造文件自引用哈希。

对本版本生成的 artifacts 字段先形状/类型/必需键核验，再逐项校验：

- artifacts_version、prepare_version、checkpoint_version 是当前受支持固定值；
- batch_id/output_relative/database_path 与本批次推导值一致；
- host_manifest_file_sha256、previous_checkpoint_file_sha256 等于本次实读 manifest 与旧 0002 字节哈希；
- normalized_file_sha256/load_report_file_sha256 等于实际文件字节哈希；
- normalized_payload_sha256 等于实际 normalized 规范指纹，并与 load_report/operation 中声明相等；
- database_sha256 等于实际数据库字节哈希，并与 load_report/operation 中声明相等；
- gate1_decision_sha256 等于本 workflow 已验证 Gate1 APPROVE **正文**规范指纹，并与 operation、Gate2 前序一致。

操作摘要内的 artifacts 完整对象仍与磁盘对象一致；但“两处对象一致”不能代替上述语义核验。来源/代码声明按原任务卡与原创建绑定核对，不自动更新旧绑定。说明文字/来源文字仍只是数据。

保留当前完整 Gate2 材料重放。缺形状或错误类型归 WorkflowHostBlocked，给出字段路径，不能退化为 KeyError/TypeError/WorkflowHostError。

回归 GPT 的五个反例：artifact 仅换行变化、三个摘要哈希各自错误、未知 artifacts_version。语义负向为进入内层校验，可在**新 QA 副本**同步 artifact 文件新哈希和 0003 摘要副本；不能改业务事实掩盖错误，不能重新计算为正确值。另用有限检查覆盖 prepare/checkpoint 版本与 host_manifest 引用，避免只修一个字段。同步步骤逐项留痕，明确是造样，不冒称上游重算。

## 5. F04：以真实调用留痕统计，不能漏掉失败或直接调用

本轮旧容器的独立证据已经确认：宿主接收记录 14 次 + G4 plain_receive 真实私有调用 1 次 = receiver 15；15 个接收身份的 checker_invocation.started 全部 true（含非 ZIP runtime_failed）。旧回执的 14/13 不准确，新回执纠正，旧文件不回写。

测试侧对宿主启动和直接 receiver 启动统一登记，分别标注调用入口、真实命令、结果、批次身份；读取接收清单中的 checker 实际 started，不手动对成功例加 1、对运行失败加 0。副本登记来源并排除；计数审计须一一对应登记与实际记录，不仅比较总数。不能因为 plain_receive 无 host receive_invocation.json 就当它没启动。旧 _run_receiver 是私有调用，不算公开宿主 API。

G6 的 blocked_normalize/failing_load 先调用 real_normalize/real_load 后抛错，当前绕过计数 wrapper。所有**实际发生的进程内调用**都要记录，含故障前真实调用；仅记录替代 wrapper 入口不够。为进程内调用与 CLI 内调用使用明确字段名。CLI 内次数如果仍未观测，写 null/未观测并分列可证实事实，不能将 3/2 冒充全部真实调用次数。允许在测试侧用观察方法记录子进程，禁止加生产测试开关或改冻结上游。

blocked_rejections 若继续保留，必须从实际结果导出并断言；否则删除这个未维护的统计项，不用常量 0。公开 API、私有造样、控制器造样、工作簿输入、副本、模拟决定及真实批准分列。

隔离计数自测在新内存副本少一条启动记录必须失败；补一条未登记记录也应被识别。matcher 自测独立，不能向正式 failures 塞假失败再删除。

最终 summary/checks/日志/计数/回执由同一最终结果保存，读回完整内容一致后输出；有读回失败时退出码与落盘状态不得互相矛盾。按实际新运行计数，不照抄本卡的旧次数。

## 6. 验证、指南与停止

compile 源文本，项目 Python -B/禁写 bytecode，全部使用全新容器和批次。保留并运行现有九组核心验证、MAIN/C02/C07b、失败接收、HOLD/REJECT、原 40 字节 writer 故障及正常只读守卫；增加本卡有界探针，负向必须同时核对异常类别和**具体目标原因**，不能只接受 exit!=0。

完整保存新探针入参/同步说明/完整返回或异常、真正前后文件哈希、故障命中与异常链、后续新进程恢复结果。先写自己的产物再核验，不读答案册。没有执行的测试不写通过。不要求重跑 TASK-002—010 整套历史入口，不扩大新功能。

指南更新失败记录与 0003 共存的处理、结束核验包含哪些产物、artifact 字节引用/语义声明和真实计数口径。修正“三个模板”但实际四个模板的旧小标题即可，不做无关改写。

EXEC_REPORT_011_R1.md 写四组修复/证据、新版本及完整哈希、新容器/路径、真实命令/次数/退出码、保护结果、失败尝试和未执行事项。解释旧计数修正，保留全部旧现场和 GPT 证据。

**完成后停止等 GPT 复验。**不实现或提交 Gate2 决定，不执行规则/复算/底稿，不建立正式契约，不签真实 Gate，不保存人类判断，不生成 AI 建议，不推进 TASK-012。主理人只转交本卡与验收单，不需手工测试或批准。

