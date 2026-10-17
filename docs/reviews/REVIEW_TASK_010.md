# TASK-010 验收：需修复，暂不进入任务十一

日期：2026-10-11；验收：GPT。结论：**CHANGES_REQUIRED**。正常接收、普通重启和三种模拟决定可运行，但恢复协议、失败分类与提交收尾存在可复现缺口。真实批准仍为 0，GPT 没有修改实现。

## 1. 实际执行与认可的部分

当前交付：宿主 `604b48f2…`、测试 `4e4b01cb…`、指南 `05a888c6…`。使用项目 Python 3.11.1，真实重跑 `tests/test_run_demo_workflow.py`，新容器为 `data/workflow_host_tests/task010_gpt_20261011_104531`，新接收/测试批次位于同名 `data/batches` 父目录。

验证入口退出 0、failures=[]，十个汇总检查（九组加保护）均自报 PASS。其报告计数为 CLI start 15/status 15/record 14、直接 API 3、receiver 11/checker 12、模拟决定 3、真实批准 0。**receiver 11 是测试计数错误，实际为 12，见 F05。**

正常路径确实复用冻结接收器和控制器，没有执行标准化、SQLite、规则、底稿或 AI。八份接收材料纳入实际文件哈希；外部输入变化不会切换批次快照。GPT 新测试副本的 pending 与 approved 正向控制均成功且只读；已变动快照在下一次 status 中也会被发现。

## 2. F01：宿主清单未按完整协议核验（阻断验收）

位置：`scripts/run_demo_workflow.py:395`、`:744`、`:807`。

`_read_host_manifest` 检查部分必需键，但没有验证 mode、contract_status、manifest_version 的正确值，也没有核对 bindings 对象的实际规范指纹、gate1_request 与持久化请求。status 只比较声明的 bindings_sha256 与当前实测值；record 连这项宿主声明比较也未共用。

独立公开 CLI 复现：

- M01：仅把 host_manifest.mode 改为 REAL，status 仍退出 0 并输出硬编码开发态。
- M02：仅改 host_manifest.bindings.input_sha256，保留原 bindings_sha256，status 仍退出 0。
- M03：仅把 host_manifest.gate1_request.request_id 改为 OTHER-REQUEST，提交来自真实 checkpoint 的决定仍退出 0、追加 0002 并变为 APPROVED。

这不是要求防恶意重写整个批次，而是已有两个记录彼此矛盾仍被当成有效状态。需使用 status/record 共用的完整宿主恢复核验。

## 3. F02：文件哈希链未证明状态连续，部分记录被忽略（阻断验收）

位置：`scripts/run_demo_workflow.py:336`、`:349`。

独立复现：

- C01：仅改 0002.batch_id 为 OTHER-BATCH，status 仍成功。
- C02：仅改 0002.operation.decision.reason，不改 workflow 内真正的决定，status 仍成功；两处决定及其摘要不一致未检出。
- C03：把 0002.workflow 换成合法的 0001 pending workflow，保留原决定摘要和有效前序文件哈希，status 成功并回到 PENDING。单个 workflow 合法不代表这是合法第二次操作。
- C04：在合法 APPROVED 链旁新增 `0003.json.tmp` 半文件，status 忽略它，继续返回旧 APPROVED。文件枚举只选 `.json`，没有拒绝未知 checkpoint 项。
- C05：通过冻结控制器构造同绑定、同批次但**另一份 Gate1 请求**的合法批准 workflow，放入 0002 并匹配 operation 决定；前序字节哈希正确。status 成功，但该 workflow 的历史不是已保存 0001 的延续。
- S01：0001.workflow.state=null，外层 state_sha256 同步为 null 的正确规范指纹。恢复应报告协议阻断，实际因提前下标访问触发 TypeError，变成退出 2 的 WorkflowHostError。

需核验本宿主固定的两次操作、完整形状、批次/请求/决定引用和历史延续，不能只逐文件调用控制器再检查前序哈希。保持单一控制器，不新增另一套审计规则。

## 4. F03：接收失败被误分类且缺少可恢复宿主记录（阻断验收）

位置：`scripts/run_demo_workflow.py:436`、`:540`、`:561`。

F01_runtime_start 使用新建的非 ZIP `.xlsx`，真实执行接收器/checker，没有改上游。接收清单明确为 FAILED_RUNTIME、receive_exit_code=2；宿主先要求成功路径的全部八份材料，因没有 quality_report.json 报 WorkflowHostBlocked、退出 1。**运行失败被误报为协议/质量阻断。**

F02_runtime_status 再打开该批次，退出 1，称“不是本宿主创建的，缺少 host_manifest”。实际就是本宿主刚刚创建的失败批次，按任务卡应恢复失败状态并退出 2。C12 的 status 虽退出 1，也只报“不是本宿主创建的”，没有恢复本次质量阻断原因。

两个失败分支只留下 receive.stdout/stderr；宿主未保存实际 receiver command/exit_code 的结构化记录，也没有失败 host_manifest。失败清单不需要 bindings 或可批准请求，**不能把“不得生成可批准请求”误改成“不得保存宿主失败清单”**。当前测试 G3 恰好断言失败批次不得有宿主清单，与原卡失败恢复要求相冲突，需要修正。

## 5. F04：写入之后未重新核对绑定，仍可能报成功（阻断验收）

位置：`scripts/run_demo_workflow.py:561`、`:807`。

T01/T02 仅在 GPT 测试中包装真实 `_write_exclusive_json`：先完成它的真实写入、关闭和读回，再在本轮专供故障测试的批次修改快照。注入各命中 1 次，没有生产测试开关、没有改冻结输入。

- T01：0002 写后改变快照，record 仍返回成功和 APPROVED。
- T02：0001 写后改变快照，start 仍返回成功和 PENDING。

下一次 status 能发现变化，不能弥补本次错误的成功宣告。record 的两次 measure 都在 checkpoint 写入之前，start 也没有提交后的测量；任务卡要求一次操作内在读取与提交前后核对。需在写后、返回成功之前重新实测并比较，变化时保存失败现场并拒绝成功；status 也应避免返回混合读取的状态。

## 6. F05：验证证据、计数与使用说明需要同步修正

位置：`tests/test_run_demo_workflow.py:168`、`:546`、`:609` 及宿主指南。

- receiver_runs 只在宿主 start 退出 0 时增加，漏掉实际调用接收器的 C12。真实为成功 11 + C12 1 = **12**；三次路径拒绝没有启动 receiver。测试树的 17 个叶子批次是 **12 份真实接收 + 5 份 checkpoint 故障副本**，不能称为 17 次真实接收。副本名和原批次名已正确区分，无需禁止测试复制。
- 部分故障只断言退出码 1，不能防止被无关原因抢先阻断。R1 新增探针必须同时断言异常类别、目标字段/原因，以及不追加 checkpoint。
- 写入故障用整个替代 writer 人工抛 WorkflowHostError，并未进入真实 writer 的 write/close/readback 错误处理；不能据此声称真实关闭/读回失败路径已经验证。保留半文件场景，补一个对真实文件写入依赖的有限故障注入。
- 指南给 `$host = ...`，PowerShell 的 Host 是 `Constant, AllScope` 自动变量，不能赋值。改用 `$workflowScript` 等普通变量；示例也不要默认指向已经存在的测试批次。`-B -m py_compile` 仍可能生成 pyc，语法检查可直接 compile 文本，避免再清理缓存。

## 7. 证据、保护与交接

GPT 新证据：`data/reviews/task010_20261011_104531`。完整回归命令/退出码/日志在 regression 文件中；独立结果见 `independent_results.json`、`supplemental_results.json`、逐案例 `.result.json`、`runtime_artifacts.json`。独立共调用宿主 CLI 15 次、API 2 次；另有冻结控制器 3 次只为构造 C05 合法对照，以及 2 次额外真实接收。它们不混入原入口计数。测试副本只用于本轮故障，不宣称是新接收；真实批准始终 0。

历史保护详见 `protected_files_comparison.json`；本轮新增 QA、复验单与修复卡，既有实现/测试/指南/输入/批次/证据不回写。新冻结基线为本目录 `source_hashes_after.json`，供 R1 只授权三个文件变化。没有重跑任务二至九整套回归，也没有进行无边界 fuzz。

交接 `docs/tasks/TASK-010-R1.md`，完成 F01—F05 后再验收。主理人只转交文件，无需手工检测、签 Gate 或测试真实审批；暂不发任务十一。
