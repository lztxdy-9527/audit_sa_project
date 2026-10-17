# TASK-013-R2：修复合法状态恢复与最终收尾，补齐定向证据

执行：DeepSeek；验收：GPT；人类主理人转交。项目：`D:\harness work\audit_sa_project`。修完停住，不推进 TASK-014。

## 1. 必读与本轮结论

先读 `docs/reviews/REVIEW_TASK_013_R1.md`、本卡、原 TASK-013 与 R1 卡、当前宿主及测试。

R1 的固定引用、内嵌 artifacts 一致性与失败身份检查已经独立复现通过，保留，不重做业务规则。报告自身在真实最后一次读取之后变化也能被当前实现拒绝。然而，恢复入口引入了早期阶段运行错误，最终复测仍漏掉先前消费的 Gate2 材料及旧 checkpoint；部分故障证据的取值时点和完整性仍未达 R1 要求。

本卡只收尾这三组缺口。不扩功能，不做无边界 fuzz，不把测试全绿作为充分验收。

## 2. 文件与版本授权

仅修改三个既有文件：

- `scripts/run_demo_workflow.py`，起点 SHA-256 `115253956e4fbcccbc096af3d673b081f42b9d0fe9bc587f536151297bd9eec4`。
- `tests/test_screen_demo_workflow.py`，起点 SHA-256 `14e96b7567ea6cab0ba9fd13d48a25b2f928fefb80517155f245a30e3c44c000`。
- `docs/WORKFLOW_HOST_GUIDE.md`，起点 SHA-256 `f2bbb6faae16647023abf789a2e611012023ff73b856fa096ddcf5a475f47345`。

仅新增 `docs/EXEC_REPORT_013_R2.md`、全新测试容器/批次父目录/按既有规则推导的外置数据库父目录。旧回执、历史批次、GPT QA/基线、旧测试及所有上游模块/SQL/schema/SPEC/契约草案/Excel/答案册一律不动。

主保护基线为 `data/reviews/task013_r1_20261012_052724/source_hashes_after.json`。已有文件恰允许以上三项变化、其他 0 变化、0 缺失；更早按累计授权集合核对。实现版本升为 `TASK-013-workflow-host-1.2`；TASK-012 与 TASK-013 screen-* 持久化协议版本保持现行 1.0，不迁移、不补签旧批次。代码固定后创建最终全新现场。

不安装依赖、不建 Git、不清理旧文件或项目外副本；不使用通配符删除。仅新目录中的本轮临时文件可按显式白名单处理。

## 3. F01：所有合法阶段均应能只读恢复

`inspect_dev_batch` 的 `screen_expected` 只在 revision >= 5 分支赋值，却在分支外读取。GPT 实际创建的两条小样链在 0001、0002、0003、0004 各节点调用 status 均出现 `UnboundLocalError` 并退出 2；对交付容器的 Gate1 pending、Gate2 pending、Gate2 HELD/REJECTED 四次真实 CLI 也均退出 2。

修复变量生命周期和条件分支，使筛查专属收尾只在合法筛查状态执行。不得用捕获异常后返回默认成功掩盖问题。

定向正向回归覆盖：Gate1 pending、Gate1 APPROVED、Gate2 pending、Gate2 APPROVED（尚未筛查）、Gate2 HELD、Gate2 REJECTED，以及现有筛查完成状态。合法批次 status 应退出 0，返回真实 phase 和真实动作允许值；停止态可读取，但动作不可继续。API 与新进程 CLI 都须覆盖此修复，优先复用本轮现有小样与 G3 场景，避免大量重建 MAIN。

每个节点保留 checkpoint/phase/实参/返回值、真实批准 null、next_step_allowed=false 与前后文件哈希，证明只读；不要只测试“不允许筛查”。原有非法现场的阻断分类不放宽。

## 4. F02：最后一次数据消费后的复测覆盖全部已消费产物

GPT 两个有限反例均在第二次 `_read_screen_outputs` **返回初始缓冲之后**注入一次：

1. 给本批次 `workflow/gate2/load_report.json` 追加一个换行；本次 status 仍 READY/0，下一次才因 `load_report_file_sha256` 拒绝。
2. 给本批次 `workflow/checkpoints/0001.json` 追加一个换行；本次 status 仍 READY/0，下一次才因链前序文件哈希拒绝。

原因是 Gate2 全集复测发生在最后一次报告消费之前，新增的最后一次 `_verify_screen_tail` 只覆盖 screening 三文件、数据库及 screening 目录状态，未复测 Gate2 三文件、manifest、旧 checkpoint 和 Gate2 失败状态。

实现可复用现有 helper 或集中收尾，但**最后一次必要控制器调用和最后一次必需数据消费之后**，成功返回前须继续覆盖所有本次已消费材料：normalized/load_report/Gate2 artifacts、数据库、host_manifest、0001—0005、screening started/report/artifacts、静态绑定与两处失败/既有未知项状态。预期来自初始同缓冲读取或本次真实 writer 返回，不能以事后新读数替换；不要再消费未经核验的新版本。

不要求原子快照或并发安全，也不扩展为同权限防篡改测试。此处验证的是已承诺的有界调用内变化检查。

有界回归固定为**同一专用小样基线上的三项**：真实最后一次报告读取返回原缓冲后，分别改报告、load_report、0001。每项命中 1、before/after 真实且不同；本次必须 WorkflowHostBlocked/退出 1 并指向对应文件；撤销 wrapper 后新进程也拒绝，恢复原件后新进程退出 0。可串行恢复复用，不能改历史现场。若消除后续读取，选择实际唯一/最后读取返回处注入，不按旧次数凑命中。

保留原三个 G6 方向及 F02/F03 已通过的语义反例，不删除、不弱化原断言。筛查提交入口的既有全集收尾继续保留。

## 5. F03：探针时点、完整调用记录及回执对应最终现场

### 真正的报告读取边界

当前 `g6_f01_report_tail_change` 包装首次 `_verify_screen_tail` 返回，但该时点之后宿主才再次调用 `_read_screen_outputs`。其错误实际在后续读取指纹比较处触发，不能称“最后一次报告读取返回之后”。GPT 另用实际第二次报告读取返回后的包装确认了报告自身最终复测可用。

将本轮三项报告边界探针挂在**真实报告读取返回原缓冲之后**，记录完整“控制器动作返回→读取调用/返回→注入→最终核验/拒绝”顺序。注入点不能根据文字注释推断；不得因旧点不存在而零命中通过。

### 完整故障现场

当前 G6 三份记录及报告探针只有 helper 名称、完整消息和部分哈希；缺实际公开宿主调用实参、异常类别/阶段/完整 cause/traceback，数据库与快照方向还缺撤销后新进程与恢复原件后的正向记录。这未达到 R1 已列明的要求。

仅补齐这些已有 G6 与本轮新增探针的记录即可：实际公开函数名、完整 args/kwargs（或可恢复内容寻址引用）、batch_dir、预期类别与目标原因、返回或完整异常/链/traceback、wrapper 位置/命中/调用顺序、真实前后哈希、后续 CLI 完整命令及 stdout/stderr 引用、恢复原位正向结果。保持 summary 可摘要，逐条提供完整记录路径与文件字节 SHA-256；不能以私有 helper 名称冒充完整调用实参。探针类别与目标原因须同时断言。

原 writer 的完整待写文本、真实旧 0001—0004 前后值、sentinel、核心真实返回与落盘逐项相等、正式缺记录/未登记审计规则、控制器按函数分列计数均已改善，保留，不重造；本轮计数按实际留痕导出，不照抄 R1 的 22/22 或 94。normalize/load 若本进程未进入，明确 0；CLI 内部实际未观测记 null，与有依据的推导分列。

### 回执的两处更正

旧 `EXEC_REPORT_013_R1.md` 正文宿主哈希写 `95b2a2…`，实际文件、用户交接消息及两组容器绑定都是 `115253…`。最终交付容器 writer 文件实际是 **14,223,740 字节 / `bd287093d53bd2fe6b869f97d70ba9e5e101ee3721fc9637b5bf46618f9b1a32`**，并非旧回执/消息的 14,223,730 / `092938f5…`。两项均在新回执说明更正，旧回执不回写；新数值必须从本轮最终现场实际文件读出，不把以上旧轮实际值当本轮目标。

## 6. 完成与停止

源文本编译→最终固定代码→新容器实跑→统一落盘读回→退出码；FINAL_ARTIFACT_READBACK 与 checks 的计数继续如实分列。不得把未跑的旧整套入口写成通过。

回执提供修改文件和新回执完整 SHA-256、三个完整产物目录、实际执行命令/退出码、修复与失败尝试、三个缺口的闭环证据、真实计数与保护差异。GPT 再次独立验收。

保持 DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED，或相应合法早期/停止态。**真实批准 0，next_step_allowed=false；不新增 0006、不执行独立复算/事实底稿/人类判断/AI、不建立正式契约、不推进 TASK-014。**
