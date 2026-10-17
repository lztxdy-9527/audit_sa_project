# TASK-011-R2：只修 checkpoint 初始字节与哈希的取值时点

执行：DeepSeek；验收：GPT。项目：`D:\harness work\audit_sa_project`。

先读 `docs/reviews/REVIEW_TASK_011_R1.md`、本卡及 R1 卡 §3。**F01、F03、F04 已关闭，本轮只关闭 F02 的一个剩余反例，不推进 TASK-012。**

## 1. 严格修改范围

只允许修改三个既有文件：

- scripts/run_demo_workflow.py
- tests/test_prepare_demo_gate2.py
- docs/WORKFLOW_HOST_GUIDE.md

只新增 `docs/EXEC_REPORT_011_R2.md` 及全新测试容器、批次父目录和推导的外置 SQLite 目录。所有旧回执/卡片/验收单/证据/批次/数据库、旧 test_run_demo_workflow.py 和冻结上游均不动。不安装依赖、不建 Git、不扩大功能。

起点 SHA-256：

- 宿主：e950895a747d1c2e9ec2e46ff86e733b83df13dc577ff14d985a18ca88a8fe55
- 测试：5ee6c4bda600e59280ec8aa2c79451accca5c1a7f08e36af15f5a6018e1b7c1a
- 指南：6861fec23bebb25f5f929b5bd99f90404a40e85d98ae9c2e1dada8ff21c3c8e4

新主保护基线：`data/reviews/task011_r1_20261011_142537/source_hashes_after.json`。仅上述三项可变化，其他 0 变化、0 缺失。新增文件不计作改写既有文件；旧基线按各自起点如实列累计变化。

宿主实现版本升至 `TASK-011-workflow-host-1.2`。本轮不增加字段或改变持久化形状，manifest/checkpoint/artifacts/failure 的既有 1.1 协议版本可保留；`prepare_version` 随 HOST_VERSION 使用 1.2，所有固定预期一致。最终固定代码新建批次，不迁移旧批次、不放宽旧代码绑定。

## 2. 问题与最小修复

现有 `_load_checkpoint_chain` 先解析 checkpoint，然后调用冻结控制器验证/重放，最后再 `file_sha256(entry)` 保存链哈希。期间发生的文件变化会被当作新的预期值。

对每份固定 checkpoint：

1. 初始读取文件字节到同一个缓冲。
2. 用该缓冲解析 JSON，同时计算该缓冲的 SHA-256；二者必须绑定同一次读取。
3. 链中的 `file_sha256`、下一份 `previous_file_sha256` 比对、current checkpoint 元数据、Gate2 收尾预期均使用这一初始 SHA。
4. 保留最后一次控制器调用之后的磁盘复测；变化就按 checkpoint 路径给 `WorkflowHostBlocked`，含预期/实际，不返回成功。

不能在解析前后各读一次文件再假定是同一内容；不能在重放后覆盖初始哈希；不能只给特定 0003 探针加特殊分支。共用读取逻辑自然覆盖 0001/0002/0003，保留缺文件/无法读取/非法 JSON/形状错误的既有类别、路径和异常链。

只在 checkpoint 读取与链哈希附近做必要小改动；不重写宿主、不遍历任意路径、不改控制器、不加生产测试开关。现有 F01/F03/F04 及其他收尾核验保持原行为。

## 3. 新增唯一有界负向与正向控制

GPT 复现脚本与完整证据在：

`data/reviews/task011_r1_20261011_142537/checkpoint_timing_probe.py`

`data/reviews/task011_r1_20261011_142537/checkpoint_timing_probe.json`

使用本轮新合法 C02 批次或已登记的新 QA 副本：

- 正向：无变化的 status 成功，phase 为 DEV_GATE2_PENDING，真实批准 null、next_step_allowed false。
- 负向：包装真实 `prepare_dev_gate`，先执行原函数，在 Gate2 纯重放返回时仅一次将磁盘 `0003.operation.materials_sha256` 改为 64 个 0。此时旧 JSON 已被消费。
- 本次 status 必须为 `WorkflowHostBlocked`/退出 1，原因包含 `workflow/checkpoints/0003.json` 与收尾字节变化；不能只验证下一次调用拒绝。
- 撤销 wrapper 后用新进程 CLI status 仍退出 1，原因指向 materials_sha256 的语义错误。

测试必须同时断言类别与目标原因；命中恰为 1；before 在故障调用之前取得，after 在调用结束后取得，必须不同。保存正向完整返回、负向完整异常/原因、后续 CLI 命令/stdout/stderr、真实 before/after、变更字段、注入时点和次数。不改旧现场。若用副本同步路径/对象引用，逐项记录并明确只是造样，不冒称重新通过真实上游。

不要求增加无边界 race/fuzz、文件锁、身份认证、原子快照或断电试验。

## 4. 运行、自检与交付

编译源文本，不生成 pyc。用项目 Python `-B` 和全新容器完整运行 `test_prepare_demo_gate2.py`；原十组与原有断言全部保留，加上本卡定向探针。组数按实际记录；没有执行的测试不得写“通过”。原 40 字节 writer、完整 0003 后失败诊断、报告/数据库晚变更、artifact 语义、真实计数及隔离自测均应保留通过。

计数从实际调用导出，不以 R1 的次数为目标值。公开宿主 API、私有调用、控制器造样、真实 receiver/checker、进程内 normalize/load、CLI 未观测 null 与推导值、副本/故障/模拟决定分列；真实批准保持 0。新增探针如增加 API/控制器/副本调用，要计入对应真实记录。

下一份回执纠正旧 `count_audit.json` 的引用：当前审计实际内嵌在 summary/checks 的 G9，不存在独立文件。引用本轮真实落盘位置；不回写旧回执，也不以此扩展 F04 的代码修复。

指南只补充 checkpoint 对象与哈希来自同一初始字节、收尾拒绝变化的行为及新版本。回执列清最小改动、完整文件哈希、真实命令/退出码/次数、探针证据、三条新产物路径、保护结果、失败尝试和未执行事项。

**完成后停止等待 GPT 验收。**不新增或提交任何 Gate2 决定，不执行规则/复算/底稿，不建立正式契约，不签真实 Gate，不保存人类判断，不生成 AI 建议，不推进 TASK-012。主理人只转交本卡与验收单，无需手工测试或批准。
