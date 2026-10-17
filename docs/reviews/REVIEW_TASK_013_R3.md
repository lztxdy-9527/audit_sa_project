# TASK-013-R3 独立验收

结论：**CHANGES_REQUIRED，剩余一个阻断项 F01（探针边界错误）**。宿主及指南继续冻结；F02 的 after 哈希一致性、完整记录改进与 F03 七阶段证据可保留，不要求重新设计。未推进 TASK-014。

## 已核对的结果

- 交付测试文件 SHA-256 为 `fb018aa9dbea598563ccc91edb1d75bbd6b4a9525c8556daa2513560f2eb1998`。宿主 `ae5b7e24…cab4e2`、指南 `c7963c58…60cf5` 及冻结上游、旧入口未变。
- 对交付容器 `data/workflow_host_tests/task013r3_run_03` 只读核对：持久化 11 项 PASS、failures=[]，summary/checks/counts/cli_logs/self_tests 与读回结果一致。CLI 原始 stdout 与保存 payload 对应，入口事件与 27 次公开 API／256 次控制器／5 次进程内筛查核心调用一致，接收/checker 均为 38。
- 七阶段实际 API/CLI phase、动作允许值、next_step_allowed=false、checkpoint state 两项真实批准 null、三组目录哈希逐项核对通过。75 个大对象引用文件的实际字节哈希、长度、规范指纹核对通过。
- 三项 F01 记录的 after 文件哈希等于其 after.tree 同路径哈希，恢复集合等于 before。29 份 0005 中 28 份可解析、1 份为故意半写现场；0 份 0006。MAIN 仍 12 条（3/5/2/2），R02 超额 1,600,000 分；writer 完整文本、部分写入、旧 checkpoint 哈希保护证据保持。
- GPT 未启动本轮完整回归。另在新建 C06b 小样批次，使用共同的**第二次 `_read_screen_outputs` 返回之后**的边界，分别改报告、load_report、0001：三项命中 1，本次 API 退出 1、撤销 wrapper 后 CLI 退出 1、恢复单个原件后 CLI 退出 0；返回的原始对象未被更改，注入后控制器调用为 0，目录只有对应目标文件变化。实际执行公开 API 9 次、CLI status 7 次，真实批准 0。

证据目录：`D:\harness work\audit_sa_project\data\reviews\task013_r3_20261012_112209`。`artifact_audit.json` 保存交付现场核验；`correct_boundary_probes.json`、`api_calls.json`、`cli_calls.json` 保存 GPT 独立对照；保护比较见 `protected_files_comparison.json`。

## F01 为什么尚未通过

任务卡要求的共同触发点是：**status 最后一次读取筛查报告的函数返回原始对象之后，再改变三个目标之一**。这与“分别寻找三个目标文件各自最后一次被读到的位置”不同。

R3 测试改为在 `io.open` 内预读目标文件、seek 回原位、调用注入，再将句柄交还宿主。此时宿主的真正读取和 `_read_screen_outputs` 返回尚未完成，不能保证返回原始缓冲。交付报告探针因此由“摘要消费字节与初始声明不同”检查阻断，并非所要求的函数返回后的晚变更验证。

两个更直接的反例：

- `r3_f01_load_report_last_read.json` 中 `read_calls_total=0`，异常仍在 `_load_host_context → _load_checkpoint_chain → _verify_screen_operation`，尚未到达最后一次报告读取。
- `r3_f01_0001_last_read.json` 同样 `read_calls_total=0`；它改变 0001 后又同步改变 0002，实际由 `0003.json.previous_file_sha256` 阻断。原任务只要求在共同边界改 0001，不需要再次消费 0001，也不需要改任何后继文件。因此“0001 只消费一次”不能成为改变注入要求的理由。

此外，`run_last_read_probe` 将 `trace.controllers` 初始化为空，但未安装控制器观察 wrapper 填充它；记录的 0 不是对该次调用的真实测量。纯内存判定也把“只有第一次文件读取 + 注入 + 空控制器列表”判为 qualified=true（GPT 已单独调用该函数复现），无法证明共同边界已经到达。

这是一处测试方法偏离，不是新的业务规则、架构变更或宿主缺陷。不得把链上提前报错放宽为本卡的成功标准。

## 本次收窄

只发 TASK-013-R4，修正 F01 三个探针及对应时点自测、记录与计数说明。保留本轮已核验的 F02/F03 和既有回归。本轮不要求执行端再跑完整入口，使用现有 `--only-g10` 定向入口；GPT 后续也先验收该定向结果。

截图显示多个成功退出的后台运行，回执还记录了 smoke 至 smoke56 和三轮完整入口，说明大量时间消耗在测试观察器、造样和记录返工。统一触发点的既有简单 wrapper 已由 GPT 两轮验证，不需要继续开发底层文件读取观察框架。

停止边界不变：DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED，真实批准 0、无 0006，未执行独立复算、事实底稿、人类判断或 AI。
