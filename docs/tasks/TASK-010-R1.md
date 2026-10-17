# TASK-010-R1：修复恢复协议、失败接收和提交收尾

执行：DeepSeek；验收：GPT。根目录：`D:\harness work\audit_sa_project`。先读 `docs/reviews/REVIEW_TASK_010.md`、本卡，再按需查 TASK-010_DRAFT 与当前实现。

**TASK-010 尚未通过。**正常路径已接通，不重写架构；本轮仅修复 F01—F05，完成后停止，不推进任务十一。

## 1. 授权边界

只修改三个既有文件：`scripts/run_demo_workflow.py`、`tests/test_run_demo_workflow.py`、`docs/WORKFLOW_HOST_GUIDE.md`。新增 `docs/EXEC_REPORT_010_R1.md`、`data/workflow_host_tests/<全新容器>/` 与 `data/batches/<本轮全新测试父目录>/`。宿主版本统一为 `TASK-010-workflow-host-1.1`；宿主清单/checkpoint 协议若新增字段，相应统一版本并说明，不迁移旧批次。

主保护基线：`data/reviews/task010_20261011_104531/source_hashes_after.json`，仅上述三文件可变，其余 0 变化、0 缺失。TASK-009-R2 的 14691 项及更早 13330/12546/10236/8547/6511/4902/874 基线全部不变。旧回执、任务卡、验收单、GPT 证据、旧批次及失败现场不回写。

冻结接收器、checker、v1.2 控制器及全部上游不改。三个宿主 API、三个 CLI 子命令、真实批准 null、开发态/草案/next_step_allowed=false 不变。不装依赖、不建 Git/正式契约、不运行标准化/SQLite/规则/底稿/AI、不接真实材料、不增加生产测试开关。

## 2. F01：所有恢复入口共用完整宿主核验

建立 status/record 共用的恢复函数，不能 status 检一套、record 漏一套。先核容器与必需字段再访问；按成功/质量阻断/运行失败分支核验各自协议，不逼失败记录伪造 bindings 或请求。

成功批次至少核对：

- manifest_version、host_version、mode、contract_status 的固定值；next_step_allowed 严格 false、真实批准字段必须存在且为 null。
- source/receive/bindings/gate1_request 的必需形状、字段、类型；哈希完整格式，不能把缺键当 null。
- bindings_sha256 必须等于**清单实际 bindings 对象**的规范指纹；清单 bindings、workflow 创建绑定、当前实测绑定三者一致。
- batch_id 与目录叶子、每份 checkpoint、workflow 一致；host_manifest.gate1_request 的 request_id/materials_sha256/scope 与 0001 实际请求一致。
- 来源描述及成功接收状态、实际退出码与所引用接收材料的声明一致；按固定批次内路径读取，不跟随清单访问任意路径。

可在 checkpoint 中引用先创建的 host_manifest **文件字节哈希**，不存在自引用；但哈希正确不能代替上述字段协议核验。不要为了适配旧现场而放松本版本检查。

新增 M01—M03 回归：模式改 REAL、清单 bindings.input_sha256 改全零但保留旧指纹、宿主请求 ID 与 0001 不同。前三组 GPT 完整小样和调用在验收证据目录。status 与 record 均须拒绝相关矛盾；M03 不能追加 0002。只同步必要的新测试内存指纹，不改旧文件。

## 3. F02：核对 checkpoint 操作协议与状态延续

本宿主只有两个合法 checkpoint 文件：0001.json、可选 0002.json。枚举目录时拒绝其他项，包括未知 .json、`.json.tmp` 半文件、目录等；不能只筛出 .json 后忽略其余。序号/哈希链仍核验，但还要核验每份操作：

- 0001：固定 START_GATE1_REQUEST，workflow 为合法 Gate1 pending；无模拟决定，无 Gate2 请求；操作摘要的批次/请求/绑定与实际 workflow、宿主清单一致。
- 0002：固定 SIMULATED_GATE1_DECISION；只允许 Gate1 APPROVED/HELD/REJECTED；恰有本次一个决定，保持 0001 全部历史前缀/请求/绑定；不允许回到 pending、不允许进入 Gate2。
- operation 中完整决定、正文实际规范指纹、workflow 的存放决定及对应 history 事件一致。派生 decision_sha256 剥离后才算正文指纹，沿用任务九口径。
- 用冻结 `record_dev_decision(0001.workflow, 决定正文, current_bindings=实测绑定)` 验证 0002 是 0001 的合法延续，比较完整预期返回。可以复用公共 API，别复制控制器私有状态机，也别只检查“当前 workflow 自身合法”。

所有对象、列表、state/operation 等先核形状再访问；null state、缺 run_bindings 等协议错误给带字段路径的 WorkflowHostBlocked/退出 1，真正 I/O/程序故障仍退出 2 并保留异常链。

新增 C01—C05、S01：checkpoint 批次错、操作摘要决定与实际决定不同、0002 换成合法 pending、旁边有未知半文件、0002 是另一合法请求的批准状态、state=null 且外层指纹同步。全部须在目标协议/关联处阻断；保持合法 pending、三种决定、序列化往返的正向控制。

## 4. F03：先识别实际接收结果，保存失败批次的宿主记录

实际 receiver 返回后，批次已存在且可写时，保存真实完整 command/exit_code/stdout/stderr 的结构化留痕。无论成功、质量阻断还是运行失败都适用；未启动不虚构启动或退出码。日志写失败则明确说明，不宣称保存。

不要在处理退出 2 之前强求成功路径的八份材料。先核验可用的接收清单、实际退出码及状态对应关系，再按分支检查：

- 0 + DEV_GATE1_PACKET_READY：继续完整成功核验、Gate1 请求与 checkpoint。
- 1 + BLOCKED_QUALITY：保存失败 host_manifest 和完整实际质量诊断，返回 1，无可批准请求/checkpoint。
- 2 + FAILED_RUNTIME（含缺失质量报告等实际失败）：保存失败 host_manifest，返回 2，无可批准请求/checkpoint。存在/缺失/读不出保持真实状态，不补造报告或资金零值。
- 清单/返回码矛盾、无法执行或核验材料等运行问题不能降为质量通过；诊断区分协议矛盾与 I/O/执行失败，保留实际 receiver 结果。

失败 host_manifest 创建后亦不回写；具有宿主标记和真实调用记录，失败分支不要求成功绑定。status 能重新打开这个**本宿主创建的失败批次**，返回对应 1/2 和保存的原因；不能将其说成旧批次，也不能建立空壳 workflow。record 对两类失败批次都拒绝，不生成 0001/0002。

修正 G3 中“C12 不得有 host_manifest”的错误断言，改为“必须有真实失败宿主记录，不能有可批准请求/checkpoint”。保留无宿主描述的旧纯接收批次一律拒绝，不能顺便接管旧批次。

新增真实非 ZIP .xlsx 运行失败小样（只在新测试容器写入）：实际 receiver/checker 退出 2，宿主 start/status 同为 2；C12 start/status 为 1 且原因指向质量问题。两者都保留真实命令/结果/现存材料，不读答案册。此处不要改冻结接收器。

## 5. F04：核验结束字节后，才能报成功

start/record 的成功条件延伸到实际落盘之后：初始读取/绑定核验 → 操作 → 独占写入/关闭/读回 → 重核 checkpoint 协议与文件 → **重新实测绑定并比较操作前后值** → 返回成功。status 也需前后核对所消费的不可变文件，避免混合读取不同现场后宣称有效。

写前比较仍保留；不能把 record 现有两次写前 measure 当成写后检查。变化时给具体文件路径/预期实际哈希，返回阻断或恰当运行错误，保留已写现场，不宣告有效成功、不覆盖旧 checkpoint、不自动更新绑定。后续恢复仍应发现变化。范围是普通变化检测，不宣称同权限防篡改、锁服务或并发安全。

T01/T02 回归分别在真实 0002/0001 writer 完成后改变**新故障批次**快照，注入各命中 1；本次 record/start 不能返回成功，后续 status 拒绝，旧文件未被宿主回写。所有项目原输入/旧批次不动，测试替换只放测试内。

## 6. F05：真实验证与说明同步

保留九组原有场景，不删负向、不放松业务口径。新增上述明确探针，逐项保存完整实参/文件变更、实际返回或异常、期望/实际、目标原因、前后文件哈希。负向 helper 必须同时核验异常类别与目标原因，不能仅看到 exit 1 就通过；验证“类别正确、原因错”应失败。

补一个**经过真实 `_write_exclusive_json`** 的有限 I/O 故障回归，例如仅对目标新 checkpoint 的底层 handle.write 写部分内容后抛 OSError；注入命中计数必须 >0。真实 writer 应转换为 WorkflowHostError，旧 checkpoint 不变，半文件保留，恢复明确阻断。不要再用整个替代 writer 人工抛目标异常来证明 writer 自身错误处理。

按实际启动而非成功结果计 receiver/checker 次数，说明 CLI、API、真实接收和测试复制分别多少；原版 12 次真实接收 +5 份副本的记账问题在**新回执**纠正，旧回执不改。控制器计数只报告实际观测到的调用及覆盖范围，跨 CLI 进程不可见的次数不硬推或伪造。故障注入/工作簿输入/模拟决定/真实批准计数分开。

指南修复 PowerShell 自动变量 `$host`，使用 `$workflowScript`，给未存在的新批次路径模板，start/status/record 使用同一变量；保留显式模拟决定和“不自动放行”边界。同步成功/失败清单形状、恢复核验与三类退出码。语法检查用 compile 源文本，不依赖 py_compile 后删缓存；`-B` 与禁写 bytecode 继续使用。

一次全新容器完整回归即可；不重跑任务二至九整套测试、不做无边界 fuzz。源代码更新会令旧开发批次绑定失效，新版测试一律新建批次，不迁移旧现场。

## 7. 回执与停止

新 EXEC_REPORT_010_R1 列三文件完整哈希、新容器/真实接收批次/副本路径、逐项 F01—F05 结果、实际命令与退出码、目标阻断原因、实际计数、文件保护及失败尝试。未执行的检查不能写通过。

完成后交回执、指南和新容器路径，停住等 GPT 复验。不要 prepare Gate2、建立契约、签任何真实 Gate、保存人类判断或生成 AI 建议，不推进任务十一。主理人只需转交本卡与验收单，无需人工检测或批准。
