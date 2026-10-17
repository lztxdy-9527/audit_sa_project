# TASK-012-R1：补齐决定收尾检查，纠正测试计数

执行端：DeepSeek；独立验收：GPT；主理人转交本卡全文。项目根目录：`D:\harness work\audit_sa_project`。

**先读本卡与 `docs/reviews/REVIEW_TASK_012.md`，本轮仅修复 F01—F03，完成后停止。TASK-013 未获启动。**

## 1. 先建立正确上下文

宿主已实现真实接收、Gate1 显式模拟决定、真实标准化/SQLite、Gate2 pending、Gate2 显式模拟决定及新进程恢复。当前是 `TASK-012-workflow-host-1.0`，CLI 恰 5 个子命令。

GPT 已实际重跑原有新测试：8 组 PASS。但另做有限独立检查发现：

1. 新写入 0004 不在 record 的最后一次 checkpoint 复测集合里。
2. record 与 Gate2 status 的静态绑定复测早于最后一次必要控制器调用。
3. 新测试重复计算两次公开 API、漏记四次控制器入口，且把副本/半文件混为决定数。

三种决定、停止态、0004 完整重放、Gate2 材料核验、半文件拒绝和完整写后抛错的恢复约定已正常，不重写这些协议。

原业务范围与上游口径不变。仍 `DEVELOPMENT_TEST_ONLY`、`DRAFT_NOT_IN_FORCE`、真实批准 null、next_step_allowed=false；模拟 APPROVE 后只声明允许筛查，宿主不执行筛查。

## 2. 允许修改及保护

仅改三个既有文件：

- `scripts/run_demo_workflow.py`
- `tests/test_record_demo_gate2_decision.py`
- `docs/WORKFLOW_HOST_GUIDE.md`

仅新增 `docs/EXEC_REPORT_012_R1.md` 和全新测试容器、批次、固定推导的 SQLite 目录。所有旧回执/验收单/任务卡/GPT 证据、旧批次与数据库不改、不删、不覆盖。

冻结控制器、接收器、checker、标准化器、装载器、schema/规则 SQL、筛查/复算/底稿、SPEC、契约草案、Excel/答案册，以及旧 `test_prepare_demo_gate2.py` 和 `test_run_demo_workflow.py` 全部保持原字节。不增加生产模块、依赖、Git、接口或命令。

起点完整 SHA-256：

- 宿主 `0e1a95dfe7c65dad9c5c54cb043fbe3dc7756632f2f3962bfab6df55f29b0e76`。
- 本轮可修改测试 `84dfac91c66c8ad33b9a2441a4c72ba6b1ab022f02744f0ac1d6b816e0877c7b`。
- 指南 `2396be82cae2e19378367c16fe21faacaf9ac8c84e05b179e2fb7ecd3c992fdb`。
- 旧 TASK-011 测试 `11d4fe57690ff5d5438aaf25b9a3953ced9a1e500ccef1620f61f39ec548b4e4`。
- 旧 TASK-010 测试 `852bf336cd2d259e43b4da9eee539a52f48253767c52ff9327f62e12015f5f8c`。

主保护基线：`data/reviews/task012_20261011_162219/source_hashes_after.json`；恰为上述三个既有文件允许变化，其余 0 变化、0 缺失。更早基线按起点累计授权核对：task011_r2 中 TASK-012 测试尚不存在，仍只有宿主/指南 2 项既有变化；不要把它写成 3 项。

实现版本升为 `TASK-012-workflow-host-1.1`。本轮不改变持久化字段结构，host-manifest/checkpoint/artifacts/failure 固定协议版本可以保持现行 `TASK-012-*-1.0`；实现版本与协议版本分开写清，材料中随 HOST_VERSION 生成的 prepare_version 与最终代码一致。用最终固定代码新建批次，不迁移、不放松旧代码绑定。

冻结前缀仍为：控制器 a6b7b8e1、接收器 52195620、checker a7e5eb67、标准化 a2bae49e、装载器 1abfad89、schema 7e0c6463、筛查 1b123766、复算 8fe75bfe、底稿 f4998d92、SPEC 5df632ed、契约 af405cb6；保存实际完整哈希。

## 3. F01：0004 必须进入提交最终复测

当前 `gate2_expected["checkpoints"]` 在写 0004 之前建立，只有前三份。补齐收尾预期，使最后一次必要控制器调用之后，真正复测 **0001—0004** 的磁盘字节。

- 旧三份仍用本次初始同缓冲读取获得的哈希。
- 0004 使用本次真实 writer 返回的文件字节哈希，不能在收尾重新读取已经变化的文件后，把新值当作预期。
- 保留现有写后完整链重放、当前 checkpoint 与 writer 哈希比较、旧 checkpoint 不变检查。
- 差异报 WorkflowHostBlocked，给出 checkpoint 路径、预期和实际；保留现场，不删除或重试 0004，不报 READY。

新增定向回归：在 record 最后一次 SCREEN 动作检查真实返回后，仅修改新 0004 的 `operation.phase_after`，wrapper 随后返回原结果。原实现本次错误返回 0；修复后本次必须退出 1／WorkflowHostBlocked 并指向 0004，真实修改命中 1、before!=after；撤销 wrapper 后新进程 status 仍拒绝。另保留未变化正向对照。

GPT 复现脚本只作定位参考：`data/reviews/task012_20261011_162219/independent_review.py` 中 `final_action_change("F01_record_checkpoint4_tail", "checkpoint")`。不得改 GPT 脚本、数据或以硬编码 case 名解决。

## 4. F02：两个 Gate2 入口在最后一次控制器调用后真实复测绑定

范围为 `record_simulated_gate2_decision` 与 `inspect_dev_batch` 的 Gate2 恢复分支，不扩大到重构全部宿主。

将成功收尾所依赖的静态绑定真实测量放在该入口最后一次必要控制器调用之后、返回成功之前。比较本次操作开始的绑定和创建绑定；从磁盘重新读实际字节，不能使用 `context_after["measured_bindings"]` 等旧对象代替。保留产物、数据库、manifest、checkpoint、failure 的最终核验，不因增加绑定复测而移动或省掉它们。

保证此成功路径上后续没有会消费这些材料的必要控制器调用；如果有，最终复测必须在其之后。目标是既有有限流程的一致性，不能宣称原子快照或同权限防篡改。

新增两个定向探针，各只改全新批次 `source/input.xlsx` 一次，冻结原控制器真实调用先完成：

1. Gate2 record 最后一次 SCREEN 动作检查返回时改快照；本次 record 1／WorkflowHostBlocked，指出 snapshot/绑定变化，含预期与实际；撤销 wrapper 后新进程 status 1。
2. 已决定 Gate2 状态的 status 最后一次动作检查返回时改快照（原版本为 other_actions 中最后一次 SCREEN）；本次 status 1，撤销 wrapper 后新进程 status 1。

两个探针都记录真正修改前后哈希、阶段/调用顺序、真实修改命中 1、完整调用结果/异常。不能只靠下一次 status 拒绝判通过。用语义明确的有限 wrapper 命中目标，不无限枚举时序，也不要以固定内部调用总数作为业务协议。

保留 status 对 0004 晚变更当次拒绝的对照；未变化的 Gate2 pending/APPROVED/HELD/REJECTED 均应继续正常恢复。

## 5. F03：在测试侧统一观察真实入口，分清文件与决定

只调整本轮可改测试，不给生产加计数或故障开关。

- 公开宿主 API 由实际入口事件导出，含 helper 进入的 inspect、直接调用、抛错前已进入的调用；同一次调用只能记一次，删除 G7 调用点与 run_api 的重复累加。
- 宿主内部控制器重放用底层真实入口观察；故障 wrapper 直接调用保存的原函数时也要记录，不得绕过计数。造样/宿主内部重放分列，不把包装器进入次数当作真实核心执行次数。
- CLI 子进程与进程内分列；未观测的内部次数仍写 null，推导值明确单列。normalize/load 的失败前真实进入仍计入。
- 不把 `rglob("0004.json")` 当作已保存决定数。至少分列原始文件数、可解析原始记录、副本记录、半文件；涉及“合法决定已保存”的口径必须有恢复/重放证据，完整 JSON 不是充分条件。HOLD/REJECT 同样是决定，完整写后异常但经独立 status 验证已提交的记录如实单列。副本用 Path 层级或统一路径格式识别，不拼混 Windows 反斜杠与 `/`。
- receiver/checker 的真实身份与调用记录对应，副本排除；启动登记与记录做双向核对，报告 missing/unregistered，保留删除一条记录必失败的隔离自测，增加内存中的未登记记录必须被识别的对照。
- summary/checks/日志与回执的同名口径一致，最终落盘读回后不再修改计数。匹配器自测继续隔离，不污染正式 failures。
- G6 已真实捕获但未保存的 writer 完整 text 要以原 UTF-8 字节另存（可解析的完整 checkpoint），核对其文件字节数和 SHA-256；将旧 0001—0003 调用前后两组真实哈希、阶段顺序、sentinel 异常链、部分文件实际字节数写入 writer 证明文件，不能只保存“旧文件未变”布尔值。复用原 G6 故障，不增加无关故障组合。

GPT 原版本观察值（19/117/原始文件9=完整原始7+副本1+半文件1）仅解释旧回执误差，**不是修复后目标值**。新增探针会改变计数，本轮全部从实际新留痕导出。旧回执不回写。

## 6. 测试、说明与新回执

保留原 8 组有限回归，不删掉失败案例或放松原因匹配。新增上述三项缺口探针，可并入现有 G7 或另设有限组，组数按实际；不要求重跑历史冻结入口。

尤其保留：三种模拟决定与停止态、C07b 未匹配关联、错误决定字段、完整 0004 重放及旧链不变、数据库/报告变化、未知 0005、真 writer 半文件及真实完整待写字节捕获、准备 failure 优先阻断、status 只读守卫、无筛查调用。

**决定保存失败约定不变**：完整合法 0004 写后抛错，本次仍失败，撤销 wrapper 后独立 status 可以验证已保存决定并恢复对应状态；这不追认原调用成功。不新增决定失败标记，不把它误套为准备阶段的 failure 协议。

所有新增负向同时匹配异常类别与目标原因，保存完整实参/返回/异常链、调用时序、before/after、旧文件保护与撤销后的新进程 CLI 日志；不只留布尔值或截断错误。只读既有 Excel，答案册隔离。

指南更新实现版本与最终复测说明，澄清统计口径。新 `EXEC_REPORT_012_R1.md` 列明三文件和回执完整 SHA-256、实际命令/退出码、所有新计数的来源、三条完整产物路径、F01/F02/F03 对应证据、逐项保护、失败尝试和未执行项。没有运行的检查不写通过。

完成后停在 Gate2 决定后的开发状态，等待 GPT 独立验收。**不推进 TASK-013，不执行筛查/复算/底稿/AI，不建立正式契约，不签真实 Gate，不保存或预填人类判断，不新增 UI/真实 ERP/压测。主理人无需手动运行测试或审批。**
