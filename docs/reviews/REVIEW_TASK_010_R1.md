# TASK-010-R1 复验：主体修复有效，仍需限定修复

结论：**CHANGES_REQUIRED**。不推进 TASK-011。GPT 未修改交付代码、测试或指南；主理人无需另做检测或批准，只需转交本单与 TASK-010-R2。

## 1. 已完成的修复

交付版本 `TASK-010-workflow-host-1.1`，核心/测试/指南哈希前缀分别为 `e3805601 / e0cbe2c9 / f9a537b0`。

GPT 在全新容器 `data/workflow_host_tests/task010r1_gpt_20261011_111932` 实际重跑测试，退出 0，入口报告十组 PASS、失败 0。但入口有一项故障测试误判通过，见 F05，不能仅凭总退出码验收。

上一轮 17 个独立观察本次全部达到预期，另核对异常类别及目标原因。合法 pending/approved 恢复正常且只读；M01—M03 清单矛盾、C01—C05 checkpoint 协议/延续、S01 null state 均明确阻断；真实非 ZIP 工作簿使 receiver/start/status 返回 2；C12 质量失败恢复为 1 且保存真实诊断；T01/T02 分别只在 0002/0001 写完后改变新快照、各命中一次，本次操作均不报告成功。

因此：**F01、F04 关闭；F02、F03 主体已修，保留下述局部缺口；F05 证据尚未闭合。**不重开已解决的状态机、绑定和收尾检查。

## 2. F02 剩余：0001 的接收命令未核对

位置：`scripts/run_demo_workflow.py` 的 `_verify_start_operation()`，交付版第 563 行起。必需键包含 `receiver_command`，但未比较其内容与清单保存的真实接收命令。

独立 R01：复制一个新测试批次，仅把 `0001.operation.receiver_command` 改为 `["OTHER-COMMAND"]`，其余字段不变。公开 CLI `status` 仍返回 0、`DEV_GATE1_PENDING`。应拒绝操作摘要与实际调用记录矛盾；status/record 共用恢复入口都应生效。

这是一处操作留痕一致性缺口，不表示发生真实批准，也不要求身份认证或安全隔离。

## 3. F03 剩余：接收成功后的宿主自身失败没有完整留痕

位置：`_save_receiver_logs()`（第 701 行起）只保存两份文本；`start_dev_batch()`（第 922 行起）仅在接收器自身返回质量/运行失败时创建失败清单。读取、分类、核验成功接收材料时发生的宿主故障会直接退出；`_require_failure_manifest()` 目前也只能表达 receiver 退出 1/2。

独立 R02：真正调用冻结 receiver，实际退出 0、READY；在本轮新故障批次保留质量报告原文件，再将原路径设为目录，使宿主读取时实际触发 Windows `PermissionError`。宿主返回 `WorkflowHostError`，但 `workflow/` 只有 stdout/stderr，没有结构化真实 command/exit 记录，也没有失败宿主清单。随后 `status` 返回 1，误称“不是本宿主创建的”，而非恢复本宿主运行失败的诊断与退出 2。

应分别保存 **receiver 实际结果**与**宿主自身结果**：receiver 实际是 0，不能为表达宿主失败而伪造为 2。批次已创建且仍可写时，立即保存实际调用留痕；在成功宿主清单/checkpoint 建立前发生自身故障，应保存可恢复的宿主失败记录。已有成功清单或半 checkpoint 的收尾失败仍保留原现场，不覆盖旧文件。

原有 receiver 退出 1/2 分支已通过，不要撤销或重写其口径。

## 4. F05 剩余：writer 假阳性与漏计

交付测试第 1046 行起的 `FaultyHandle` 只有 `write`/`__getattr__`，缺少上下文管理特殊方法。真实 writer 进入 `with open(...)` 时先报 **TypeError：不支持上下文管理协议**，并没有执行目标 `write()`，也没有抛目标 OSError。测试只要求捕获包装错误、拦截 open、文件存在，仍登记 `ok=true`。GPT 新跑及交付最终容器均存在此结果；新跑的“半文件”实际为 **0 字节**。

GPT 使用具有正确 `__enter__/__exit__` 的新测试代理做正向对照：原生产 writer 实际写入 40 字节后抛指定 OSError，打开/写入/抛错各命中 1；宿主转换为 `WorkflowHostError`，异常链仍为目标 OSError，旧 0001 字节不变，恢复明确拒绝半 JSON。因此本项首先修验证器，不要求重写生产 writer。

入口计数亦有遗漏。根据本次新跑的 30 份接收清单，以原始批次 ID/接收时间及 checker 启动记录去重，实际为 **14 次接收启动、14 次 checker 启动、16 份测试副本**。入口却报告 13/12/11：漏了 API T02 接收、运行失败 checker，以及原 G7 的五份副本。`api_calls=9` 还混入三次控制器造样调用，公开宿主 API 实际为六次。T02 本入口注入两次，与“一次”的说明不符；GPT 独立一次注入已证明 F04 成立。

下一轮需修正实际 write/OSError 的计数、异常链与部分字节断言；验证 helper 对“类别正确、目标原因错误”必须判失败；分别统计 CLI、宿主 API、控制器造样、真实接收/checker、副本，不硬编码旧案例名字，不以质量报告存在代替启动。

## 5. 证据、保护与停止

GPT 本轮证据根目录：`data/reviews/task010_r1_20261011_111932/`。

- `regression_execution.json`、`regression.stdout.txt`、`regression.stderr.txt`：完整入口重跑。
- `independent_results.json`、`supplemental_results.json`、`independent_validation.json`：原 17 个观察及目标原因复核。
- `remaining_results.json`：接收命令、宿主读取故障及恢复、真实部分写入对照；三个要求未满足、两个对照满足。逐案 stdout/stderr、实参、变更与异常链另存同目录。
- `count_audit.json`：逐份清单去重、调用位置、0 字节 writer 误判、T02 两次注入。
- `acceptance_summary.json`、`protected_files_comparison.json`、`source_hashes_after.json`：最终结论与保护基线。

GPT 额外独立调用为公开宿主 CLI 18 次、宿主 API 4 次，控制器造样 3 次；另实际接收 3 次。与被重跑的测试入口计数分开，不推断 CLI 内部未观测的控制器次数。

本轮前后既有文件 0 变化、0 缺失。对 TASK-010 的 16340 项基线，仅 DeepSeek 本轮授权的核心/测试/指南三文件变化；14691/13330/12546/10236/8547/6511/4902/874 基线均 0 变化、0 缺失。完整明细以保护 JSON 为准。

GPT 计数核验脚本首次运行曾误读故障样例中被改名的 `batch_status`、误写一个观察案例名，随后修正并成功运行；未改交付文件，未把这些脚本失败当作产品结果。

未执行 TASK-002 至 TASK-009 全套重跑、无边界 fuzz、TASK-011、正式契约、任何真实 Gate、人类判断或 AI 建议。下一步仅按 `docs/tasks/TASK-010-R2.md` 修剩余三处。
