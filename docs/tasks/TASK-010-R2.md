# TASK-010-R2：闭合操作命令、宿主失败留痕和验证证据

执行：DeepSeek；验收：GPT。项目根目录 `D:\harness work\audit_sa_project`。先读 `docs/reviews/REVIEW_TASK_010_R1.md`、本卡和当前三个交付文件，按需查上轮卡。

**TASK-010-R1 主体修复有效，尚未验收通过。**F01/F04 关闭，不重写架构。本轮只处理 F02/F03/F05 的剩余缺口；不要推进 TASK-011。

## 1. 修改与保护边界

只修改三个既有文件：

- `scripts/run_demo_workflow.py`
- `tests/test_run_demo_workflow.py`
- `docs/WORKFLOW_HOST_GUIDE.md`

新增 `docs/EXEC_REPORT_010_R2.md`、一个全新的 `data/workflow_host_tests/<容器>/` 和 `data/batches/<测试父目录>/`。不要回写旧回执/任务卡/验收单、GPT 证据、旧批次或失败现场。

主保护基线为 `data/reviews/task010_r1_20261011_111932/source_hashes_after.json`：仅上述三文件可变化，其余既有文件 0 变化、0 缺失。TASK-009-R2 的 14691 项及 13330/12546/10236/8547/6511/4902/874 旧基线全部不变。

宿主版本统一为 `TASK-010-workflow-host-1.2`。新增字段需要调整宿主清单/checkpoint 版本时统一说明，不迁移旧批次，不放松固定协议。三个公开宿主 API/CLI 命令不变；开发态、契约草案、真实批准 null、`next_step_allowed=false` 不变。

冻结 receiver/checker/控制器及全部上游不改。不安装依赖，不初始化 Git，不建正式契约，不标准化/入库/运行规则/生成底稿或 AI，不预填人类判断，不加生产故障开关。

## 2. F02 剩余：完整核对 0001 接收命令

`_verify_start_operation()` 目前只要求 `receiver_command` 键存在。将它与保存的真实完整接收调用记录逐项严格比较，核容器和参数类型，不能仅比较脚本名或 `command[2]`，不能对参数 `str()`/strip 后再比较。来源描述中的空格、换行仍原样保存。

若第 3 节新增独立调用记录，宿主清单及 0001 操作摘要需与该记录一致；使用固定批次内路径，不据调用记录执行命令或访问任意路径。

新增配对回归：合法原命令仍能 status/record；仅改新批次副本的 `0001.operation.receiver_command` 为 `["OTHER-COMMAND"]`，status 与 record 均阻断，原因必须指向该字段与真实调用矛盾，record 不追加 0002。保持上一轮所有已通过的清单/延续/形状/写后绑定探针。

## 3. F03 剩余：分别记录接收结果与宿主自身失败

实际子进程返回后，只要新目标已创建且仍可写，**先保存独占、结构化的实际调用记录**，再读取/分类/核验接收产物。建议固定 `workflow/receive_invocation.json`，也可用同等固定名称。记录真实完整 command、真实退出码、stdout/stderr 的固定文件引用及字节哈希；原日志保留。无法启动不虚构返回结果；记录自身写失败必须明确报告，不能宣称留痕成功。

成功、receiver 质量失败、receiver 运行失败、receiver 成功但宿主后续失败均保留真实调用；host_manifest 不能是唯一保存 command/exit 的地方，因为它尚未创建时也可能出错。

将**宿主结果**与**receiver 实际结果**分开表达：

- receiver 1 + BLOCKED_QUALITY：延续现有质量失败处理，start/status 返回 1。
- receiver 2 + FAILED_RUNTIME：延续现有运行失败处理，start/status 返回 2。
- receiver 实际 0 + READY，但宿主在读取/核验期间发生 I/O 运行错误：保存本宿主 FAILED_RUNTIME 的失败清单和阶段/异常类别/具体路径/原因；start/status 返回 2；receiver 实际退出码仍为 0，不能篡写为 2。
- 接收材料协议矛盾按既有错误分类明确拒绝，保留实际调用及诊断；不得被解释为质量通过或可批准请求。

范围重点是**真实接收返回之后、成功宿主清单/checkpoint 建立之前**的宿主失败。新批次仍可写时保存失败宿主记录；无 bindings、无请求、无 checkpoint 目录，不建立空壳 workflow。恢复入口识别本宿主失败现场并返回保存的宿主结果；record 始终拒绝。无宿主调用/清单的旧纯接收批次仍不接管。

已创建成功 host_manifest 或半 checkpoint 后的失败继续保留不可变现场并阻断；不得为新增失败分支而覆盖旧清单、旧 checkpoint 或自动修复绑定。保存诊断也失败时如实保留可用日志/调用记录并报告失败，不宣称恢复记录已完整保存。

新增实际故障回归 H01：调用冻结 receiver 确实返回 0/READY 后，仅在**新故障批次**保留质量报告原文件，将原路径设为目录，触发宿主真实读取错误；也可用等价、命中计数明确的有限底层读 I/O 故障，不能用整体替换宿主函数直接抛目标异常。预期为：

1. 目标读取故障确实发生；实际调用记录中 receiver exit=0，完整命令/日志可查。
2. 宿主保存自身运行失败记录，异常类别/阶段/路径清楚，无请求/checkpoint。
3. 新进程 status 返回 2、原因仍指向宿主读取故障，不能称作旧纯接收批次；record 返回阻断且不建 checkpoint。
4. 原 receiver 退出 1/2 的测试继续通过；合法成功批次不受影响。

不增加真实认证、锁服务、并发控制、超时重试或安全隔离设计。

## 4. F05 剩余：让验证证明目标故障，纠正计数

### 4.1 真实 writer 故障

修正 `FaultyHandle` 的上下文管理行为，使真实 `_write_exclusive_json` 的 with 块能进入目标 `write()`；代理 `__enter__` 返回正确代理，`__exit__` 正常关闭底层文件。生产 writer 本次 GPT 正向对照已能正确处理目标 OSError，先修测试，不作无必要重写。

只拦截新故障批次的目标 0002。实际 write 写入部分内容后再抛独有 sentinel OSError，分别保存打开、实际写入、写入字节、实际抛错次数。严格断言：

- 目标打开/写入/抛错均恰命中 1；部分文件字节数 >0 且小于完整预期文件。
- 捕获类别为 WorkflowHostError，异常链为目标 OSError 且 sentinel 一致。TypeError、其他路径错误或仅文件存在不得通过。
- 旧 0001 逐字节未变；新半文件保留；后续 status 按半 JSON/不完整现场拒绝；未报告提交成功。

保存完整异常信息与因果链，不只截取结果前 200 字。新增隔离的 helper 自测：类别正确但原因不符必须判失败，自测结果另存，不污染正式 failures。所有目标负向探针至少同时核验类别与原因。

T01 只在真实 0002 writer 完成后改变新快照；T02 只在真实 0001 writer 完成后改变新快照，两者各恰命中 1。当前 T02 对 host_manifest 和 0001 都注入，实测为 2，需收窄测试目标；F04 本身不重开。

### 4.2 实际计数

本次 GPT 重跑现有入口：CLI start/status/record 为 16/29/16；公开宿主 API 为 6，控制器造样 API 为 3；真实 receiver/checker 启动为 14/14，副本 16，接收清单文件合计 30。现有 summary 的 13/12/11 与 api_calls=9 混合口径不准确，旧回执不改，在新回执纠正。

下一轮有新增 H01 等探针，计数会变化，**不要照抄上述数值**。用实际执行留痕统计：

- CLI 的 start/status/record 调用各计；公开宿主 API 与控制器造样分别计。未观测到的 CLI 内部控制器调用不推测。
- receiver 实际启动包含 CLI 与 API 两条路径；启动前路径拒绝不计。checker 按实际 started 记录计，运行失败也计，不能用 quality_report 文件是否存在代替。
- 所有复制批次统一记副本及来源，含原 G7 五份副本；副本不计真实接收/checker。保留原始调用标识便于去重。
- 将声明数与逐条命令/调用记录、原始接收清单、checker_invocation、复制记录相互核对，另存 `count_audit.json` 或等价汇总；对不一致判失败，不靠手工最后覆盖计数。
- 故障触发、模拟决定和真实批准分别统计；真实批准仍为 0。

## 5. 指南、回执与停止

同步调用记录、成功/失败清单、receiver/host 两层结果、恢复方式、异常分类与版本。PowerShell 继续用 `$workflowScript`。含 `<新父目录>` 等占位符的代码标为模板，不写成已执行的成功命令；回执列本轮真实命令和退出码，保留实际参数与空格。

一次全新容器完整回归，保持原 G1—G9、R1 全部有效检查，并新增本卡限定探针。先做源文本 compile 检查，继续 `-B`/禁写 bytecode；不重跑 TASK-002 至 TASK-009 全套，不作无边界 fuzz。源代码更新使旧开发批次绑定失效，测试均新建，不迁移旧现场。

新增 `EXEC_REPORT_010_R2.md`：列三个文件完整哈希、新容器/批次/副本路径、F02/F03/F05 逐项证据、真实调用及独立计数、writer 目标 OSError/实际部分字节/异常链、文件保护与失败尝试。没执行的检查不写通过。

完成后停住，交回执和指南等 GPT 复验。不要 prepare Gate2、建立正式契约、签真实 Gate、保存人类判断或生成 AI 建议，不推进 TASK-011。主理人只需整体转交本卡及验收单，无需人工检测或批准。
