# TASK-010-R2 复验：两组剩余问题

结论：**CHANGES_REQUIRED**。F02 关闭；F03、F05 各保留一组收尾问题。F01/F04 不重开，不推进 TASK-011。主理人无需手工测试或批准 Gate，只需转交本单和 TASK-010-R3。

## 1. 已证实完成的部分

交付宿主 `TASK-010-workflow-host-1.2`，核心/测试/指南哈希前缀 `d460724f / 1524ef6a / 8d568de8`。GPT 未修改这些文件。

GPT 在 `data/workflow_host_tests/task010r2_gpt_20261011_114828` 完整重跑入口：退出 0，十组检查 PASS，报告失败 0。另做 17 个独立观察，按任务要求核实后 16 个满足、一项未满足。

已通过：合法 pending/模拟决定/approved 恢复；接收命令长度、同长度值、类型三种变更的 status/record 均准确拒绝；质量报告读失败时保留 receiver 实际 0、宿主失败 2，status 恢复原运行失败；失败批次不能提交决定；真实 writer 写入 40 字节后抛目标 OSError、异常链正确、旧 0001 字节未变、半文件恢复拒绝。入口 T01/T02 各仅注入一次。

因此接收命令修复有效，writer 的真实部分写入故障事实也已成立。以下不涉及新业务规则或新安全设计。

## 2. F03：接收清单本身读失败后，失败记录不能恢复

交付版 `_require_failure_manifest()` 第 490—497 行对所有失败分支先强制 `receive.exit_code` 与 `receive.batch_status` 成功/失败枚举配对。宿主自身失败时，接收清单可能根本未能读取，状态不能预先获知。

独立 H02：冻结 receiver 确实返回 0。仅在新故障批次保留原 `batch_manifest.json`，将原路径设为目录，使宿主实际读取时触发 `PermissionError`。start 正确抛 `WorkflowHostError`，也保存了失败清单：

```text
host_result = {layer: HOST, exit_code: 2, stage: verify_receive, ...}
receive.exit_code = 0
receive.batch_status = null
无 bindings、无 checkpoint 目录；独立调用记录完整
```

随后新进程 status 却退出 **1**，原因是“receiver 退出码 0 必须对应 DEV_GATE1_PACKET_READY，实际 None”，覆盖了已保存的宿主运行失败诊断。预期为恢复宿主失败 **2**、指出接收清单读取失败。不能补造 READY 来满足自己的恢复校验。

H01 质量报告读取失败已通过；此处是同一 F03 原定范围中的“接收清单未能读取”分支。修复应区分实际退出码、已取得的清单声明、无法取得的声明、宿主自身结果，保持成功路径和 receiver 自身失败路径严格。

## 3. F05：汇总落盘早于计数修正，部分必需验证仍未留痕

GPT 独立根据原始接收清单、checker 启动记录去重确认：本次入口实际 **receiver 15、checker 15、副本 17**，CLI 16/31/17，宿主 API 7、控制器造样 3。真实次数及副本登记已纠正。

但 `summary.json` 在最终计数计算之前写入，之后只更新内存，没有再次保存。因此 stdout 和 `count_audit.json` 是 **15/15**，落盘 `summary.json` 仍是 **13/12**。审计报告还宣称没有不一致，没有比较最终持久化的两个文件。这是可复现的产物矛盾，不是口径偏好。

writer 代理已能真正写 40 字节并抛目标 OSError，不再是上一轮 TypeError 假阳性。仍有三项上轮明确要求未完成：

- `fault_state.writes` 初始化为 0，实际 write 未递增，也未断言。GPT 提取交付测试的原始 `FaultyHandle` 单独运行：实际写一次、抛错一次、部分字节 40，但其 writes 仍为 0。
- 入口未保存完整 writer 异常链/计数/旧 0001 前后字节哈希；结果仍截取 outcome 前 200 字，仅检查旧 0001 存在。GPT 独立对照证明生产行为正确，不能替代交付测试自身的必需证据。
- 没有隔离的“类别正确、目标原因错误应判失败”helper 自测。

下一轮把最终汇总和证据一次完整落盘、读回相互核对，补齐上述有限断言与留痕即可，不重写宿主或扩大测试范围。

## 4. 证据与保护

GPT 本轮目录 `data/reviews/task010_r2_20261011_114828/`：

- `regression_execution.json`、`regression.stdout.txt`、`regression.stderr.txt`：真实入口重跑。
- `independent_results.json` 及逐案完整输入/变更/输出：14 次公开 CLI、3 次宿主 API；额外真正接收 2 次，另五份测试副本。
- `H02_RECEIVE_MANIFEST_READ.result.json`、`H02_RECEIVE_MANIFEST_READ_STATUS.result.json`：原异常链、实际调用、失败清单及错误恢复。
- `independent_validation.json`：按任务要求重新核定 17 个观察，其中 16 个满足。
- `count_audit.json`、`delivered_proxy_probe.json`：32 份清单去重、最终文件计数矛盾、交付代理实际 write 与计数。
- `acceptance_summary.json`、`protected_files_comparison.json`、`source_hashes_after.json`：最终结论和下轮基线。

GPT 探针最初给两次失败批次 record 预设了单一退出码及措辞，后来按“拒绝且不写入”要求重新核定：H01 record 返回 2、H02 record 返回 1 都没有保存决定，不作为新的缺口。原观察完整保留，修正在 validation 中说明；status 恢复原运行错误 2 的要求不变。

本次验收前后所有既有文件 0 变化、0 缺失。相对 18533 项 R1 基线、16340 项 TASK-010 基线，均只有交付核心/测试/指南三文件累计变化；14691/13330/12546/10236/8547/6511/4902/874 基线全部不变。注意回执中“16340 基线 0 变化”不准确，应在新回执报告三项授权累计变化，不回写旧回执。

指南还残留 checkpoint 1.1 描述，与实际 1.2 不同，可随下轮正常版本同步修正文案；不单独作为阻断项。

未执行 TASK-011、正式契约、真实 Gate、标准化/SQLite/规则/底稿/AI、人类判断、上游整套测试或无边界 fuzz。只按 TASK-010-R3 完成上述两组收尾。
