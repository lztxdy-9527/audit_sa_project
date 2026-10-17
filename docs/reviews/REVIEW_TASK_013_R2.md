# TASK-013-R2 独立验收

结论：宿主的本轮功能修复通过有界独立复验，可以冻结；任务卡整体暂不通过，剩余为测试证据与回归定位问题。只发 TASK-013-R3 测试收尾卡，不推进 TASK-014。

## 实际验证

- GPT 使用项目 Python 3.11、`-B`，在全新容器 `data/workflow_host_tests/task013r2_gpt_20261012_080320` 重跑原验证入口，退出 0、11 项检查 PASS、failures 为空。独立观察入口计数为公开宿主 API 18、控制器 183、筛查核心 5；与执行端交付容器逐项核对一致。
- 另使用 C06b 小样实际新建三份批次，独立验证七个阶段的 API 与新进程 CLI status：实际 phase、两个动作允许值、真实批准 null、next_step_allowed=false、目录哈希前后不变，全部通过。
- 独立在第二次 `_read_screen_outputs` 返回原始缓冲之后分别改报告、load_report、0001。三项均命中一次；注入后控制器调用数为 0；本次即 WorkflowHostBlocked、撤销 wrapper 后 CLI 仍退出 1、恢复原件后退出 0。宿主晚变更修复有效。
- MAIN 仍为 12 条线索（3/5/2/2），R02 超额 1,600,000 分；0005 前序实读哈希、workflow 等于 0004、批准 null、0 份 0006 保持。筛查核心与冻结上游不变。
- 全量保护核对结果保存于本轮 QA 的 `protected_files_comparison.json`；四份交付物完整哈希保存于 `acceptance_summary.json`。

QA 目录：`D:\harness work\audit_sa_project\data\reviews\task013_r2_20261012_080320`。其中 `independent_results.json` 保存七阶段与三个真正末次读取探针的完整证据，`artifact_audit.json` 保存交付现场问题。

## F01：三个“最后一次读取”回归实际在第一次读取注入

`tests/test_screen_demo_workflow.py` 的 F02 wrapper 在 `hits==0` 时立即改文件。第一次 `_read_screen_outputs` 位于链恢复的 `_verify_screen_operation`，之后本应还有控制器检查和状态摘要的第二次读取。交付记录中三个探针都只有一次读取返回，已在早期检查阻断，不能证明末次消费后的守卫。

这不否定宿主修复：GPT 已独立在真实末次读取复现通过。需要把交付测试改成同一边界，防止未来移除末次守卫后测试仍误报 PASS。

## F02：时点与调用现场仍不完整

- 三个新 F02 记录的 `after.file` 在改动后取得，但 `after.tree` 在恢复原件及正向 CLI 之后取得。以 load_report 为例，记录的 after.file 为改动后哈希，after.tree 中相同路径却为 before 哈希。应在调用结束、撤销 wrapper 后且恢复文件前保存真实 after_tree；恢复后的集合单独保存。
- `g6_tail_0005_change.json` 与 `g6_f01_report_tail_change.json` 仍以私有 wrapper 为 function，缺少完整公开调用实参及完整异常现场。旧 F01 的 `_verify_screen_tail` 第一次返回点也不能标为末次报告读取。保留早期守卫用途或精确移到末次边界，并如实命名。
- 不得通过删除生产 failure.json 将失败筛查现场恢复成成功。需要成功对照时使用另外的干净小样批次。

## F03：七阶段的批准与动作未按协议完整验收

七阶段记录把 status 顶层不存在的 gate1_approval/gate2_approval 写成 `n/a`，而实际批准字段在 checkpoint 的 workflow.state。现有 `ok` 检查 phase、next_step_allowed 和只读性，没有比较预期的两个动作允许值；完整 API 返回和前后文件哈希集合也未随该记录保存。

GPT 独立核对实际结果正确。本轮只补测试：从实际 checkpoint 记录 null，断言固定预期动作，并保存公开调用、完整返回与真实哈希集合或带字节哈希的引用。

## 工作时长与执行效率

只读目录时间显示 run_01—run_06 六轮首末跨度约 92 分钟，单轮约 11—16 分钟。这能解释大部分接近两小时的耗时，但对收尾卡偏长；新增七阶段与末次读取测试使用完整 MAIN 增加了重复成本。

下一轮只改测试，新增场景使用 C06b 小样，先定向验证后运行一次最终完整入口。新 DeepSeek 对话可减少历史干扰，但不保证提速或质量；应给自包含任务卡、当前文件及冻结哈希，质量仍由验收证据保证。

停止边界：DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED；0005 是筛查凭证，真实批准 0，未执行复算、事实底稿、人类判断、AI，未新增 0006。
