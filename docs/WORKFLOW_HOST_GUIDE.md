# 开发态接收宿主指南（TASK-017）

版本：TASK-017-workflow-host-1.0（实现版本；TASK-017 新增模拟初判层，协议为 `TASK-017-initial-judgment-start-1.0`／`TASK-017-initial-judgment-artifacts-1.0`／`TASK-017-initial-judgment-failure-1.0`；既有持久化协议版本仍为 `TASK-012-*-1.0`，筛查协议为 `TASK-013-screen-start-1.0`／`TASK-013-screen-artifacts-1.0`／`TASK-013-screen-failure-1.0`，本卡新增复算协议为 `TASK-014-crosscheck-start-1.0`／`TASK-014-crosscheck-artifacts-1.0`／`TASK-014-crosscheck-failure-1.0`，TASK-015 新增事实底稿协议为 `TASK-015-fact-packet-start-1.0`／`TASK-015-fact-packet-artifacts-1.0`／`TASK-015-fact-packet-failure-1.0`）；日期：2026-10-12；执行端：DeepSeek；依据：`docs/tasks/TASK-012_DRAFT.md`、`docs/tasks/TASK-012-R1.md`、`docs/reviews/REVIEW_TASK_012.md`、`docs/tasks/TASK-011-R2.md`、`docs/tasks/TASK-010_DRAFT.md`、`docs/tasks/TASK-010-R1.md`、`docs/tasks/TASK-010-R2.md`、`docs/tasks/TASK-010-R3.md`、`docs/reviews/REVIEW_TASK_010_R2.md`、`docs/tasks/TASK-011_DRAFT.md`、`docs/tasks/TASK-011-R1.md`、`docs/reviews/REVIEW_TASK_011.md`、`docs/reviews/REVIEW_TASK_010_R4.md`、`docs/reviews/REVIEW_TASK_010.md`、`docs/reviews/REVIEW_TASK_010_R1.md`、`docs/reviews/REVIEW_TASK_009_R2.md`、`docs/WORKFLOW_CONTROL_GUIDE.md`、`docs/BATCH_RECEIVE_GUIDE.md`、`docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md`。

本宿主把**实际接收**与任务九的**纯内存控制内核**接起来：收到一份 ERP 导出 → 留原始快照并核验 → 保存本次接收与 Gate1 候审状态 → 显式模拟 `APPROVE` 后**真实运行标准化与 SQLite 装载** → 保存完整核对材料并停在 Gate2 待确认 → 记录一次**显式模拟的 Gate2 决定**（`APPROVE`／`HOLD`／`REJECT`）→ 关掉进程再打开仍能找到同一批材料、本次产物与当前状态。**本版本不运行筛查、复核、事实底稿或 AI；只保存显式模拟决定，不执行筛查，也不提交任何真实批准。**

> 不是正式契约，也不是任何真实 Gate 的批准。真实 `gate1_approval`／`gate2_approval` 恒为 `null`；
> 模拟决定另存并固定标记 `SIMULATED_TEST_ONLY`；`next_step_allowed=false`；
> `mode=DEVELOPMENT_TEST_ONLY`；`contract_status=DRAFT_NOT_IN_FORCE`。

---

## 1. 九个可复制命令模板

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$workflowScript = 'D:\harness work\audit_sa_project\scripts\run_demo_workflow.py'
$root = 'D:\harness work\audit_sa_project'
```

> 变量名用 `$workflowScript`：PowerShell 的 `$Host` 是 `Constant, AllScope` 自动变量，**不能赋值**。
> 下文含 `<新父目录>`／`<新叶子>`／`<容器>` 的路径是**模板占位符**，不是已经执行过的成功命令。
> 三条命令使用同一组变量；下面的 `data\batches\<新父目录>\<新叶子>` 请换成**尚不存在**的路径。

**① 实际接收一次并停在 Gate1（叶子目录必须尚不存在，且位于 `data\batches` 内）**

```powershell
& $py -B $workflowScript start `
  --workbook "$root\data\generated\demo_20260930_a\input\erp_export.xlsx" `
  --batch-dir "$root\data\batches\<新父目录>\<新叶子>" `
  --source-description "合成 ERP 导出（演示用）；来源条件未知，按声明限制处理"
```

**② 读取并验证当前状态（只读，不写任何文件）**

```powershell
& $py -B $workflowScript status --batch-dir "$root\data\batches\<新父目录>\<新叶子>"
```

**③ 提交一份**完整**的模拟 Gate1 决定（决定正文来自 JSON 文件；本宿主不默认 APPROVE、不自动补字段）**

```powershell
& $py -B $workflowScript record-simulated-decision `
  --batch-dir "$root\data\batches\<新父目录>\<新叶子>" `
  --decision-file "$root\data\workflow_host_tests\<容器>\decision_approve.json"
```

**④ 真实标准化并装载，形成 Gate2 待确认请求（只接受**本版本新建**且已显式模拟 `APPROVE` 的批次）**

```powershell
& $py -B $workflowScript prepare-gate2 --batch-dir "$root\data\batches\<新父目录>\<新叶子>"
```

- 本命令**真实调用**冻结的 `normalize_demo_data.py` 与 `store_demo_sqlite.py`：先标准化本批次 `source/input.xlsx`，再写入下列**固定外置开发数据库**，最后保存材料并停在 `DEV_GATE2_PENDING`。
- 数据库路径由宿主按批次位置推导，调用者不能指定：
  `data\sqlite_tests\workflow_gate2\<批次相对 data\batches 的完整路径>\audit.sqlite3`
  （例如 `data\batches\task011_01\main_01` → `data\sqlite_tests\workflow_gate2\task011_01\main_01\audit.sqlite3`）。
  这是开发批次数据库暂时位于批次目录之外的明确架构选择，**不表示生产部署已完成**。
- **不重试、不复用、不自动删除**：目标数据库、`.staging` 或本次输出目录已存在时，在调用上游之前即拒绝；一旦 `workflow\gate2\` 已开始存在而没有完整有效的 `0003.json`，`status` 会说明准备未完成／失败并拒绝继续，需**新建批次**。

**语法检查**（直接编译源文本，不写 `.pyc`，也无需事后清理缓存）：

```powershell
& $py -B -c "src = open(r'$root\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'run_demo_workflow.py', 'exec'); print('compile OK')"
```

退出码：**0**＝本次操作成功保存或有效读取开发态（含合法 `HELD`／`REJECTED`）；**1**＝质量、协议、绑定或转移阻断；**2**＝文件 I/O、子进程或意外程序错误。stdout 是结构化 JSON，stderr 保留诊断。

## 2. 目录布局、成功与失败清单

```text
data/batches/<批次>/
  source/input.xlsx              # 接收器留下的原始快照（恢复只读这里，不再切回外部路径）
  checks/quality_report.json     # 本次实际 checker 报告
  logs/checker.stdout.txt|.stderr.txt
  code_snapshot/receive_demo_batch.py|check_demo_data.py
  batch_manifest.json            # 接收清单（接收器写，宿主只读）
  gate1_packet.md                # 开发态候审材料
  workflow/                      # 宿主新增子树（接收器产物从此不改写）
    host_manifest.json           # 宿主清单：成功、失败（含宿主层）形状
    receive_invocation.json      # 接收器实际调用记录（独占；命令／退出码／日志引用与哈希）
    receive.stdout.txt           # 接收器真实 stdout（三种结果都保存）
    receive.stderr.txt           # 接收器真实 stderr
    checkpoints/0001.json        # Gate1 pending，完整 workflow
    checkpoints/0002.json        # 一次明确模拟 Gate1 决定后的完整 workflow
    checkpoints/0003.json        # prepare-gate2 后：Gate2 pending（只可为 PREPARE_GATE2）
    gate2/                       # 本次真实产物（缺一即恢复失败）
      normalized.json            # 完整标准化结果（整数分、字符串 ID、完整 cells 原样保存）
      load_report.json           # 完整装载核对报告
      artifacts.json             # 固定相对路径、实际文件字节哈希、对象指纹、数据库字节哈希、前序引用
      failure.json               # prepare-gate2 的失败诊断（仅失败时尽力保存；与 gate2/artifacts.json 不是同一文件）
    checkpoints/0004.json        # 一次明确 Gate2 模拟决定后的完整 workflow
    checkpoints/0005.json        # 只读规则筛查完成凭证（完整 workflow 与 0004 严格相等）
    screening/                   # 本次只读筛查产物（缺一即恢复失败）
      started.json               # 本次筛查开始标记（TASK-013-screen-start-1.0）
      screening_report.json      # 冻结筛查核心本次真实返回的完整报告（原文保存，不压缩）
      artifacts.json             # 报告文件字节哈希／对象指纹、前序与数据库引用（TASK-013-screen-artifacts-1.0）
      failure.json               # 仅失败时尽力保存（TASK-013-screen-failure-1.0）
  crosscheck/                    # 独立复算产物（仅 crosscheck-rules 成功或失败后出现）
      started.json               # 本次复算开始标记（TASK-014-crosscheck-start-1.0）
      crosscheck_report.json     # 冻结复算核心本次真实返回（完整报告，不截断）
      artifacts.json             # 报告文件字节哈希／对象指纹、前序与来源引用（TASK-014-crosscheck-artifacts-1.0）
      failure.json               # 仅失败时尽力保存（TASK-014-crosscheck-failure-1.0）
  fact_packet/                   # 事实底稿产物（仅 build-fact-packet 成功或失败后出现）
  initial_judgment/              # 模拟初判产物（仅 record-simulated-initial-judgment 成功或失败后出现）
      started.json               # 本次开始标记（TASK-015-fact-packet-start-1.0）
      fact_packet.json           # 完整 JSON 事实包（保留整数分／ID／来源 entities、cells／退款事实）
      fact_packet.md             # 同次返回的完整确定性中文正文（UTF-8 无 BOM、LF、精确字节）
      artifacts.json             # 完整绑定摘要（TASK-015-fact-packet-artifacts-1.0）
      failure.json               # 仅失败时尽力保存（TASK-015-fact-packet-failure-1.0）
```

**成功清单**（`status: READY`）：`manifest_version`／`host_version`／`mode`／`contract_status` 固定值、`next_step_allowed=false`、真实批准字段存在且为 `null`、`batch_id`、`source`、`receive`（完整命令／退出码／状态／两份日志／八份材料声明）、`bindings` 与 `bindings_sha256`、`gate1_request`（`request_id`／`materials_sha256`／`scope`）。

**prepare-gate2 的失败诊断**（`workflow/gate2/failure.json`，`failure_version=TASK-012-gate2-failure-1.0`）**优先于 `0003`**：**失败记录存在就不宣告成功**——即使失败现场里同时有一份可解析的完整 `0003`，只要完整有效的失败诊断存在，`status`／`record`／`prepare-gate2` **共用恢复协议**都不再返回 READY（即使磁盘上有可解析的完整 `0003` 也不再宣告本次准备成功），按保存的类别映射退出码 2／1 并复现阶段与原因。失败诊断本身先校验后使用：非普通文件、非法 JSON、缺必需字段（`failure_version`／`recorded_at_utc`／`stage`／`exception_class`／`message`／`reasons`／`observed_outputs`）、版本不是固定值都按协议阻断并给出字段路径；`workflow/gate2/` 已开始但没有完整有效的 `0003` 且没有可读诊断时同样按协议阻断，绝不退回旧的 APPROVED 状态。原来的半文件 checkpoint（例如 40 字节 `0003.json`）仍按非法链阻断，不会因为要恢复失败类别而被跳过。

**接收层失败清单**（`status: BLOCKED_QUALITY`／`FAILED_RUNTIME`／`BLOCKED_PROTOCOL`）：保留 `source`、`receive`（完整命令、**receiver 实际退出码**、状态、调用记录引用、日志与已存在材料的真实状态）、`host_result`（**宿主自身结果**：`exit_code`／`layer=HOST|RECEIVER`／`stage`／`exception_class`／原因）、`failure`（阶段与实际原因、诊断），`checkpoints: []`，**不含 `bindings`**，也不存在 `checkpoints/` 目录。

**接收声明状态**（`receive.declaration_status`）区分三种情况：`ACQUIRED`（已取得声明，且与真实退出码一致）、`NOT_ACQUIRED`（清单不存在／不可读／无法解析，`batch_status` 如实为 `null`，`declaration_read_error` 记录具体读取错误，**不按退出码补造 READY**）、`ACQUIRED_CONTRADICTORY`（已取得但声明与真实退出码矛盾，保留原样观察值 `declared_batch_status`／`declared_exit_code`，归为宿主协议失败）。恢复时不再次要求矛盾声明已变正确。

**两层结果分开表达**：`receive.exit_code` 永远是 receiver 的真实退出码（成功 0 不会为表达宿主失败而改写成 2）；`host_result` 表达本宿主结果——receiver 1 → `BLOCKED_QUALITY`(1)、receiver 2 → `FAILED_RUNTIME`(2)、**receiver 0 但宿主在读取／核验期失败** → `FAILED_RUNTIME`(2, layer=HOST) 或协议矛盾 → `BLOCKED_PROTOCOL`(1, layer=HOST)。恢复入口按 `host_result.exit_code` 返回 1／2 并给出保存的原因，`record` 对任何失败批次一律拒绝。

| phase | 实务含义 | `simulated_action_allowed`（`NORMALIZE_AND_LOAD`） |
| --- | --- | --- |
| `DEV_GATE1_PENDING` | 已接收并停在 Gate1，等待明确决定 | `false` |
| `DEV_GATE1_APPROVED` | 记录了一次模拟 `APPROVE`；**仍不是真实批准** | `NORMALIZE_AND_LOAD` 为 `true`，可用 `prepare-gate2` 真实标准化并装载 |
| `DEV_GATE2_PENDING` | 已真实标准化并装载，材料齐备，**等待 Gate2 确认（不是已放行）** | 二者均 `false`（该 Gate2 被模拟 `APPROVE` 后 `SCREEN_AND_BUILD_FACTS` 才为 `true`；`NORMALIZE_AND_LOAD` 不再允许） |
| `DEV_GATE2_APPROVED` | 记录了一次模拟 Gate2 `APPROVE`；控制器声明筛查可行（**不是真实批准**） | `SCREEN_AND_BUILD_FACTS` 为 `true`；可用 `screen-rules` 真实执行只读 R01—R04 筛查 |
| `DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED`（`0005`） | 已真实完成一次只读筛查；phase 仍为 `DEV_GATE2_APPROVED` | `SCREEN_AND_BUILD_FACTS` 仍为 `true`；可用 `crosscheck-rules` 真实执行一次独立复算 |
| `DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` + `RULE_CROSSCHECK_RECORDED`（`0006`） | 已真实完成一次独立复算并保存复核凭证；phase 仍为 `DEV_GATE2_APPROVED` | `NORMALIZE_AND_LOAD`／`SCREEN_AND_BUILD_FACTS` 均为 `false`（已完成的动作不可重复）；`status` 只读恢复 |
| `DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` + `RULE_CROSSCHECK_RECORDED` + `FACT_PACKET_RECORDED` + `SIMULATED_INITIAL_JUDGMENT_RECORDED`（`0008`） | 已保存一份调用方显式提供的模拟初判快照；phase 仍为 `DEV_GATE2_APPROVED`、真实批准 `null`、`next_step_allowed=false`、AI 仍不允许 | `SCREEN_AND_BUILD_FACTS` 为 `false`；`status` 只读恢复；`0008` **只表示模拟记录已持久化**，不等于真实人类独立初判已保存、身份已认证或审计已完成 |
| `DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` + `RULE_CROSSCHECK_RECORDED` + `FACT_PACKET_RECORDED`（`0007`） | 已真实完成一次事实底稿构建并持久化 JSON＋Markdown；phase 仍为 `DEV_GATE2_APPROVED` | `NORMALIZE_AND_LOAD`／`SCREEN_AND_BUILD_FACTS` 均为 `false`；`status` 只读恢复并按已绑定文件核验。`0007` **只表示事实底稿已持久化**，不代表审计完成／通过或底稿已批准 |
| `DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` | 已真实执行只读规则筛查并保存完整线索报告；`0005` 是**宿主筛查完成凭证**，不是新的控制器批准或新阶段 | 重复筛查被拒绝；`next_step_allowed` 恒 `false` |
| `DEV_GATE2_HELD` / `DEV_GATE2_REJECTED` | 停止态：不能改签、不能继续；需补证／修订时新建批次 | 二者均 `false` |
| `DEV_GATE1_HELD` / `DEV_GATE1_REJECTED` | 停止态，不能改签或继续；需补证／修订时新建批次 | `false` |

checkpoint（`checkpoint_version=TASK-012-checkpoint-1.0`；宿主实现版本 `TASK-013-workflow-host-1.2`；产物摘要 `TASK-012-gate2-artifacts-1.0`、失败诊断 `TASK-012-gate2-failure-1.0`）采用**独占创建、不覆盖**：每份 checkpoint 的**对象与哈希来自同一次初始字节读取**——文件字节只读一次，JSON 解析与该缓冲的 SHA-256 绑定同一次读取，链中的 `file_sha256`、下一份 `previous_file_sha256` 比对、current 元数据与 Gate2 收尾预期全部使用这一初始 SHA；解析前后各读一次再假定同内容、或重放后覆盖初始哈希都属协议违规。`revision` 为严格整数、首份 `previous_file_sha256` 为 `null`、后续引用前一份文件的**实际字节哈希**、并引用宿主清单的**文件字节哈希**（不存在自引用）；写完关闭后重新读回核验 JSON、内容、指纹、控制器协议与操作协议，才宣布保存成功。**当前状态由有效的 checkpoint 链确定**，不靠文件名或 phase 字段；`host_manifest.json` 创建后不回写状态。

### 最终复测与计数口径（TASK-013-R1）

- **最后一次报告消费必须绑定初始声明**：`status` 构建筛查摘要所消费的报告／started／artifacts 读数必须与 `0005.operation` 的初始声明逐项一致；
  报告对象规范指纹必须等于 `0005` 声明值；`status` 不从 `0005.operation.artifacts` 内嵌副本取截止日／数据库路径／版本，而取**磁盘上已验证的 artifacts**，
  并要求内嵌副本与磁盘对象完整严格相等。
- **最终复测位置**：所有检查完成后、最后一次必要控制器调用与最后一次数据消费之后，再复测 `0001—0005`、宿主清单、接收材料与静态绑定、
  Gate2 三份 JSON 与数据库、筛查 started／report／artifacts 及失败／未知文件状态；发现变化即在**本次调用**按 checkpoint 路径阻断（含预期与实际），
  不依赖下一次 `status` 发现。
- **筛查引用核验**：`operation.report_relative`／`artifacts_relative` 必须是固定相对路径；`started.host_version`／`artifacts.host_version` 必须等于当前实现版本；
  `artifacts.host_manifest_file_sha256` 只等于**初始实读宿主清单文件字节哈希**（不得用 bindings 内容指纹替代）。
- **失败记录绑定**：`workflow/screening/failure.json` 必须含本批次 `batch_id` 与宿主 `host_version`，`target_exit_code` 为严格整数 1／2（排除 bool/float）；
  缺失或不符为协议阻断（退出 1），合法诊断继续恢复原失败类别／阶段／原因（不得降为 READY）。
- **计数口径**：公开宿主 API、控制器入口（按 `create_dev_workflow`／`prepare_dev_gate`／`record_dev_decision`／`check_dev_action` 分列）、
  筛查核心实际入口、CLI 子进程命令（成功／前提拒绝／运行失败分列）、副本、故障注入、模拟决定与真实批准分别计；
  CLI 子进程内部的核心调用次数不可观测，如实记 `null` 并另列推导值与依据。


## 3. 状态读取验证了什么、未认证什么

`status`、`record-simulated-decision`、`prepare-gate2`、`record-simulated-gate2-decision`、`screen-rules` 与 `crosscheck-rules` 共用**同一套完整宿主恢复核验**：

1. 结算清单形状与固定值（版本、模式、草案状态、`next_step_allowed`、真实批准为 `null`）。
2. `bindings_sha256` 必须等于**清单实际 `bindings` 对象**的规范指纹；清单绑定、checkpoint 内 workflow 的创建绑定、**当前实测绑定**三者逐项一致；所有哈希必须是完整 64 位十六进制。
3. `batch_id` 与目录叶子、每份 checkpoint、workflow 一致；`host_manifest.gate1_request` 的 `request_id`／`materials_sha256`／`scope` 与 `0001` 实际请求一致。
4. `checkpoints/` 只允许从 `0001.json` 起的**连续** `0001`—`0005`；其他项（未知 `.json`、`.json.tmp` 半文件、目录、`0006`）一律拒绝；`0005` 只对应一次只读规则筛查（`kind=RUN_RULE_SCREEN`），其完整 workflow 与 `0004` **严格相等**；序号连续、前序字节哈希一致（前序一律取**初始实读**字节哈希）。
5. **操作协议**：`0001` 固定 `START_GATE1_REQUEST`（Gate1 pending、无模拟决定、无 Gate2 请求）；`0002` 固定 `SIMULATED_GATE1_DECISION`（只允许 Gate1 `APPROVED`／`HELD`／`REJECTED`、恰含本次一个决定、保留 `0001` 全部历史前缀与请求、不得退回 pending 或进入 Gate2）；操作摘要的完整决定、正文实际规范指纹、workflow 内存放的决定与 history 事件一致。
6. **状态延续**：用冻结 `record_dev_decision` 从**前一份 workflow** 与**本次实际材料／决定正文**复算完整预期返回并逐项比较——`0002` 由 `0001` 复算、`0003` 由 `0002`＋本次实际 Gate2 材料复算、`0004` 由 `0003`＋本次决定正文复算。单个 workflow 自身合法不代表这是合法的下一步操作。
6b. **接收调用一致性**：`0001.operation.receiver_command` 与**独立调用记录** `workflow/receive_invocation.json` 的命令**逐元素、逐类型**严格比较（不 `str()`、不 `strip`），并与宿主清单保存的命令一致；`receiver_exit_code` 与调用记录一致。
7. 读取结束时**再次实测**所消费的不可变文件与当前 checkpoint、宿主清单字节哈希，避免混合读取不同现场后宣称有效。
8. **失败批次**：按清单保存的 `status` 返回对应退出码（`BLOCKED_QUALITY`→1、`FAILED_RUNTIME`→2）与保存的原因，并明确该批次没有可批准请求；两个 `record` 命令与 `prepare-gate2` 对失败批次一律拒绝。
9. **`0004` 的核验**：`0003` 只为 `PREPARE_GATE2`、`0004` 只为一次 Gate2 决定；恢复时保留 `0003` 的材料与数据库核验（不因当前是决定事件而跳过），并用冻结 `record_dev_decision(0003.workflow, 决定正文, current_bindings=实测)` 复算完整预期返回逐项比较；决定总数必须恰为 2，`0001`—`0003` 的历史前缀、Gate1／Gate2 请求与既有 Gate1 决定完整保留。

**未认证**：本地哈希只证明字节一致，不证明来源真实；不提供身份认证；不抵御能重写对象与全部哈希的同权限篡改；不宣称断电持久性或多进程并发安全。`status` 不写入任何文件。

## 4. 模拟决定样例（仅测试样例，不是真实批准）

```json
{
  "event_id": "EVT-TEST-APPROVE-01",
  "batch_id": "<批次叶子>",
  "gate": "GATE1",
  "request_id": "<取自 0001.json 的 requests.GATE1.request_id>",
  "materials_sha256": "<取自 0001.json 的 requests.GATE1.materials_sha256>",
  "decision": "APPROVE",
  "actor_kind": "SIMULATED_HUMAN",
  "actor_id": "tester-01",
  "occurred_at": "2026-10-11T12:00:00+08:00",
  "reason": "测试人员模拟复核（非真实批准）",
  "simulation": "SIMULATED_TEST_ONLY",
  "confirmations": { "scope_and_source_reviewed": true }
}
```

- `HOLD`／`REJECT` 不需要 `confirmations`，但必须有说明；Gate2 的确认项为 `reconciliation_reviewed`。
- `actor_kind` 必须是 `SIMULATED_HUMAN`、`simulation` 必须是 `SIMULATED_TEST_ONLY`、`occurred_at` 必须带时区；缺字段、`REAL`、AI／SYSTEM 身份、错误 `request_id`／材料指纹、布尔当 `true` 均阻断。
- **三种决定后都停住**：不执行标准化、不 `prepare` Gate2、不生成 AI 建议、不预填人类初步判断。`APPROVE`／`HOLD`／`REJECT` 后写 `0002.json`，`0001.json` 字节不变；重复／冲突决定既不覆盖也不追加。

### 4b. Gate2 模拟决定样例（第五个命令；仅测试样例，不是真实批准）

```powershell
& $py -B $workflowScript record-simulated-gate2-decision `
  --batch-dir "$root\data\batches\<新父目录>\<新叶子>" `
  --decision-file "$root\data\workflow_host_tests\<容器>\decision_gate2_approve.json"
```

```json
{
  "event_id": "EVT-TEST-GATE2-APPROVE-01",
  "batch_id": "<批次叶子>",
  "gate": "GATE2",
  "request_id": "<取自 0003.json 的 requests.GATE2.request_id>",
  "materials_sha256": "<取自 0003.json 的 requests.GATE2.materials_sha256>",
  "decision": "APPROVE",
  "actor_kind": "SIMULATED_HUMAN",
  "actor_id": "tester-01",
  "occurred_at": "2026-10-11T16:00:00+08:00",
  "reason": "测试人员模拟复核 Gate2 材料（非真实批准）",
  "simulation": "SIMULATED_TEST_ONLY",
  "confirmations": { "reconciliation_reviewed": true }
}
```

- 只接受当前恰为 `0003`／`DEV_GATE2_PENDING` 的批次；`APPROVE` 的 `confirmations.reconciliation_reviewed` 必须是**严格布尔 `true`**（`HOLD`／`REJECT` 不要求确认项，但必须有 `reason`）。
- 宿主**不默认 APPROVE、不自动补齐身份或确认项**；`actor_kind`／`simulation`／`event_id`／`reason` 全部显式提供，`request_id`／`materials_sha256` 必须指向本批次 `0003` 的实际 Gate2 请求。
- 成功写 `0004.json`（`kind=SIMULATED_GATE2_DECISION`，前序为初始实读的 `0003` 字节哈希），`0001`／`0002`／`0003`、宿主清单、接收材料、Gate2 产物与数据库**一律不改**；重复／冲突决定不覆盖、不改签、不追加 `0005`。
- **决定保存异常的约定**：若写出完整 `0004` 之后才抛错，**原命令仍算失败**；随后请**先用 `status` 查明磁盘事实**——完整合法链则恢复为“决定已记录”，非法／不完整链则拒绝。宿主不追认原命令成功、不自动重复提交，也不要凭印象重复决定。
- 三种决定后都停住：不自动执行筛查、独立复算、事实底稿或 AI，不触发下一步；筛查与复算只由显式命令触发。**模拟 `APPROVE` 只表示控制器声明筛查可行（不是真实批准）；是否执行只读规则筛查由显式命令 `screen-rules` 决定，宿主不会自动接着跑。**

## 5. 磁盘绑定、失败处理与提交收尾

- **绑定由宿主实测、控制器比较**：每次 `status`／`record` 都重新读取磁盘字节计算 SHA-256，与创建值逐项核对，再把实测对象交给控制器；**不从 `workflow.run_bindings` 抄回一份充数**。绑定缺失、文件不可读或实际值变化都阻断，诊断给出相对路径与预期／实际值，**不自动更新旧绑定**。
- **Gate2 待确认（`0001+0002+0003`）**：`status` 实读固定 `gate2/` 产物与数据库字节，重新核对对象／材料／字节与 Gate1 前序绑定，并用冻结控制器从 `0002` 与**本次实际材料**复算完整预期返回，再与 `0003` 逐项比较；`status` 本身不执行标准化或装载。
- **三种接收结果都会保存宿主记录**：成功→完整成功清单与 `0001`；质量阻断（接收器退出 1）→失败清单 + 完整实际质量诊断，返回 1；运行失败（退出 2，含缺失质量报告）→失败清单，返回 2。两者都**不建立可批准请求**，也不补造报告或资金零值。清单与返回码矛盾按协议阻断，无法读取清单或材料按运行失败处理，都保留实际接收结果。
- **收尾复测的产物范围**：`prepare-gate2` 与 `status` 在**最后一次所需控制器调用之后、返回成功之前**，按固定路径复测本次消费的全部产物并与本次初始读取／写入值逐项比较：`normalized.json`、`load_report.json`、`artifacts.json`、推导出的数据库文件、宿主清单、全部 checkpoint 字节，以及“不得存在 `failure.json`”。任一不一致即拒绝成功（给出文件与期望／实际哈希），保留现场，后续恢复仍会拒绝。
- **Gate2 决定提交的最终复测集合**：`record-simulated-gate2-decision` 在写入 `0004` 之后，收尾预期集合**必须包含 `0001`—`0004` 四份**——旧三份用本次**初始同缓冲读取**得到的字节哈希，`0004` 用**本次真实 writer 返回的文件字节哈希**；不得在收尾重新读取已被改动的 `0004` 后把新值当作预期。因此“真实 SCREEN 动作检查返回后有人改了磁盘 `0004`”会在**本次调用**内被发现并返回 `WorkflowHostBlocked`（指向该 checkpoint 路径、预期与实际字节哈希），而不是等到下一次 `status`。
- **静态绑定收尾复测（Gate2 两个入口）**：`record-simulated-gate2-decision` 与已进入 Gate2 的 `status` 在**最后一次必要控制器动作检查之后**，从磁盘**重新读取实际字节**实测静态绑定，与**本次操作开始时**的读数逐项比较（`source/input.xlsx` 快照、SPEC、契约草案、八个上游脚本、四份规则 SQL、固定 config、宿主代码与 schema）。差异给 `WorkflowHostBlocked`，诊断指出差异字段与快照预期／实际哈希；不得用先前保存的内存读数代替这次读盘，且该复测不得移动或省掉产物／数据库／清单／checkpoint／失败诊断的最终核验。
- **`0003` 的产物引用**：`operation.artifacts_file_sha256` 保存 `artifacts.json` 的**实际文件字节哈希**（与对象规范指纹分开、不构造文件自引用）；恢复时先核形状／类型／必需键，再逐项核验 `artifacts_version`／`prepare_version`／`checkpoint_version` 固定值、`batch_id` 与 `output_relative`／`database_path` 推导一致、`host_manifest_file_sha256`／`previous_checkpoint_file_sha256`、两个文件字节哈希、`normalized_payload_sha256`、`database_sha256`、`gate1_decision_sha256`（并与 Gate2 前序决定指纹一致）。摘要两处对象相等不能代替这些语义核验。
- **checkpoint 收尾复测**：所有控制器调用结束后，宿主按固定路径逐份复测本次链上全部 checkpoint（`0001`／`0002`／`0003`，Gate2 决定提交后含 `0004`）的磁盘字节是否仍等于**本次初始读取／写入值**；一旦不同即以该 checkpoint 路径给 `WorkflowHostBlocked`（含预期（初始读取）与实际值）并拒绝成功返回，后续 `status` 仍按语义错误拒绝。该检测只覆盖一次调用内观察到的普通变化，不宣称原子快照、并发安全或同权限隔离。
- **提交收尾**：`start`／`record` 的写前比较保留，并在**独占写入、关闭、读回**之后**重新实测绑定**与 re-核 checkpoint 协议／链，确认操作前后一致才返回成功；发现变化时给出文件路径与预期／实际值、保留已写现场、不宣告有效成功、不覆盖旧 checkpoint、不自动更新绑定，后续恢复仍会发现变化。范围是普通变化检测，不宣称同权限防篡改、锁服务或并发安全。
- **外部原输入只用于首次接收**：接收后修改或移走外部源文件不改变已接收的批次快照，恢复读取批次快照。
- **只接管自己创建的批次**：没有 `workflow/host_manifest.json` 的旧接收批次一律拒绝（不为历史产物追认批准）。
- **路径约束**：批次必须解析后仍位于项目 `data/batches` 之内（含重定向），不能是 `data/batches` 本身，`start` 只接受尚不存在的新叶子目录；拒绝越界与已存在目标；不覆盖、不清空、不递归删除。

## 6. 计数口径（开发验证）

真实次数一律从本轮实际留痕导出，不硬编码、不为凑数手工加减：**receiver** 以每条 `workflow/receive_invocation.json` 加上测试侧登记的直接 `_run_receiver` 调用（无宿主调用记录）计；**checker** 按各接收身份 `batch_manifest.checker_invocation.started` 计（运行失败样本也计）；**进程内标准化／装载**由测试侧计数包装真实上游统计（故障前的真实调用也计），**CLI 子进程内**次数不可直接观测，另列为未观测（`null`）并按成功完成的 CLI `prepare-gate2` 推导分列；副本单独登记来源后排除（用路径层级识别，不拼字符串前缀）。

**公开宿主 API** 由**统一真实入口观察**导出：同一次调用只计一次，覆盖经 `status`／`record` helper 进入的 `inspect_dev_batch`、直接调用与**抛错前已进入**的调用；故障 wrapper 必须调用观察包装器，不得绕过计数或把包装器进入次数当作真实核心执行次数。**宿主内部控制器重放**、**测试造样调用**、**CLI 子进程调用**分别单列；**真实批准恒 0**。

**Gate2 决定数**不得用 `rglob("0004.json")` 的文件数冒充，须至少分列：原始文件数、可解析原始记录、副本记录、半文件（故意半写的探针单列），且“合法决定已保存”的口径必须有**恢复／重放证据**（逐份真实恢复核验，完整 JSON 不是充分条件）；`APPROVE`／`HOLD`／`REJECT` 同样是决定，完整写后异常但经独立 `status` 验证已提交的记录如实单列。计数审计要求“登记的真实启动 ↔ 独立调用记录”**双向**对应，多一条未登记记录同样要被识别，并有隔离自测（去掉一条记录必须判不一致）。

## 7. 与上游冻结件的关系

- 宿主通过子进程实际调用 `scripts/receive_demo_batch.py`（不复制其校验逻辑、不导入其私有流程），只读其 `batch_manifest.json` 与固定路径产物。
- 宿主调用 `scripts/control_demo_workflow.py` 的四个 API，不修改控制器协议；附加绑定键（宿主代码、schema、接收材料清单）属于控制器“至少包含”契约允许的扩展。
- 本宿主**真实调用**标准化（`normalize_demo_data.py`）与 SQLite 装载（`store_demo_sqlite.py`）以形成 Gate2 材料，并由 `screen-rules` 真实调用冻结 `screen_demo_sqlite.screen_sqlite`、由 `crosscheck-rules` 真实调用冻结 `crosscheck_demo_rules.verify_rule_facts`；它**不导入也不调用**事实底稿、生成器或答案册（只读规则筛查由 `screen-rules` 显式调用冻结核心 `screen_sqlite`），也不调用 LLM／网络（`status` 只读：不写文件、不启子进程、不联网）。为计算绑定哈希而读取这些源码与 SQL 文件是本任务明确允许的。

---

## 8. 第六个命令：只读规则筛查（`screen-rules`）

```powershell
& $py -B $workflowScript screen-rules --batch-dir "$root\data\batches\<新父目录>\<新叶子>"
```

- 只接受**本版本新建**、连续合法 `0001`—`0004` 且当前恰为 `DEV_GATE2_APPROVED` 的批次；`HOLD`／`REJECT`／`pending`／早期阶段／已有 `0005`／已有 `workflow\screening\` 一律在**写入之前**拒绝。
- 宿主要求冻结控制器 `SCREEN_AND_BUILD_FACTS` 的 `simulation_allowed` **严格为 `true`**：动作允许来自控制器，不从 `phase` 字符串推导，也不等于真实批准。
- 宿主**真实调用一次**冻结 `screen_sqlite(<推导数据库路径>, load_report, cutoff_date="2026-09-30")`；不自行编写 SQL／Python 规则替代核心，不读答案册或生成器。
- 报告原文保存为 `screening_report.json`（保留完整 `findings`、整数分、相关 ID、`source_rows`／`entities`／`cells`／`related_refunds` 与规则／勾稽／统计字段，不压缩成数量摘要）；`artifacts.json` 分别保存报告的**文件字节 SHA-256** 与**规范对象 SHA-256**。
- `0005.json`：`revision=5`、前序为**初始实读** `0004` 字节哈希、`kind=RUN_RULE_SCREEN`；其完整 `workflow` 与 `0004.workflow` **严格相等**（筛查不改变控制器状态、不新增决定或请求，模拟决定恒为 2 条）。
- 成功后在**最后一次必要控制器调用之后**复测 `0001`—`0005`、宿主清单、接收材料与静态绑定、Gate2 三份产物与数据库、`screening/` 三份产物；不一致即拒绝并保留现场，不宣告成功。
- **`0005` 是宿主筛查完成凭证，不是新的控制器批准或新阶段**，也不代表项目完成；`gate1_approval`／`gate2_approval` 恒为 `null`，`next_step_allowed` 恒为 `false`。
- 不改 `0001`—`0004`、宿主清单、接收材料、Gate2 产物或数据库；重复筛查不覆盖、不改签、不追加 `0006`。

**筛查失败与恢复**：操作开始前的拒绝**不创建** `screening/`；一旦本次已创建并开始，任何失败都会尽力独占保存 `screening/failure.json`（阶段、原始异常类别、完整原因、目标退出码与已知产物引用）。**失败记录优先于完整 `0005`**：即使磁盘上同时有可解析的完整 `0005`，恢复入口也只按失败诊断报告类别与阶段，不宣告成功；失败诊断本身非法／错版本／缺必需键／不是普通文件时按协议阻断；`started.json` 存在但既无完整成功集合又无可用诊断时视为未完成阻断。失败或未完成的批次**不能继续、改签或补跑**，需新建批次。`status` 只读：不重新调用筛查核心、不写文件，并显示 `RULE_SCREEN_RECORDED` 与 `completed_actions`。

---

## 9. 第七个命令：独立复算（`crosscheck-rules`）

```powershell
& $py -B $workflowScript crosscheck-rules --batch-dir "$root\data\batches\<新父目录>\<新叶子>"
```

- 只接受**本版本新建**、连续合法 `0001`—`0005` 且当前恰为 `DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED` 的批次；
  早期阶段／停止态／已有 `0006`／已有 `workflow\crosscheck\` 一律在**写入之前**拒绝。
- 宿主要求冻结控制器 `SCREEN_AND_BUILD_FACTS` 的 `simulation_allowed` **严格为 `true`**（仍是开发态模拟允许，
  不等于真实批准，也不从 `phase` 字符串推导）。
- 宿主**真实调用一次**冻结 `verify_rule_facts(normalized, screening_report)`：只传两个内存对象，
  **不传数据库路径、不读答案册、不调用 SQL 筛查或生成器、不回写输入**。
  `CrossCheckBlocked`（前提／结构／来源绑定／支持范围不成立）按阻断处理，`CrossCheckError`（运行失败）按
  退出码 2 处理，均保留原因链。
- 输入对象与字节哈希来自**同一次读取缓冲**：`workflow/gate2/normalized.json` 与
  `workflow/screening/screening_report.json`；复算前实读数据库字节，必须与既有装载报告声明一致。
- `workflow/crosscheck/started.json`：`start_version=TASK-014-crosscheck-start-1.0`，记录批次、宿主版本、
  运行绑定、`0005` 初始字节哈希、两个输入的文件字节哈希。
- `crosscheck_report.json`：冻结核心本次真实返回的**完整报告**（`recomputed_facts`、`observed_summary`、
  十维度 `comparison`、`differences`、`method`、`limits` 全部保留，不截断、不压缩成摘要）；
  写后读回必须与本次返回**逐项严格相等**。
- **MATCHED 判定不只看一个标志**：必须 `batch_status=DEV_CROSSCHECK_MATCHED`、`matched is True`、
  `differences=[]`、十个维度全部齐备且 `executed is True`／`matched is True`／`difference_count` 为严格整数 0，
  且 `matched_dimensions`／`unmatched_dimensions` 与实际一致。
- `artifacts.json`（`TASK-014-crosscheck-artifacts-1.0`）分别保存报告的**文件字节 SHA-256** 与**规范对象
  SHA-256**，并绑定本批次、宿主／核心版本与核心哈希、运行绑定、宿主清单与 `0005` 字节哈希、
  normalized／screening 文件与规范指纹、Gate2 artifacts、固定数据库路径与实测字节哈希、截至日与 Gate2 决定正文指纹。
- 成功才追加 `0006.json`：`revision=6`、`kind=RUN_RULE_CROSSCHECK`、前序为**初始实读** `0005` 字节哈希；
  其完整 `workflow` 与 `0005.workflow` **严格相等**（复算不改变控制器状态、不新增决定或请求）。
  对外仍为 `phase=DEV_GATE2_APPROVED`，新增 `crosscheck_status=RULE_CROSSCHECK_RECORDED`，
  `completed_actions` 增加 `RULE_CROSSCHECK`，保留筛查摘要。
- **`0006` 是宿主复算完成凭证，不是新的控制器批准或新阶段**，也不代表整个 `SCREEN_AND_BUILD_FACTS` 完成；
  `gate1_approval`／`gate2_approval` 恒为 `null`，`next_step_allowed` 恒为 `false`。
- 不改 `0001`—`0005`、宿主清单、接收材料、Gate2 产物、筛查产物或数据库；重复复算不覆盖、不改签、不追加 `0007`。

**不一致（MISMATCH）是复算核心的正常返回**：宿主完整保存报告与全部差异，给出 `BLOCKED_CROSSCHECK`／退出 1，
**不写成功 `0006`**、不自动修改筛查报告、不静默删除差异、不继续事实底稿。报告仍按协议校验来源绑定与
十维度形状，不因为“不是 MATCHED”就丢弃真实返回。

**复算失败与恢复**：操作开始前的拒绝**不创建** `crosscheck/`；一旦本次已创建并开始，任何失败都会尽力独占保存
`crosscheck/failure.json`（`TASK-014-crosscheck-failure-1.0`：固定版本、`batch_id`、`host_version`、
严格整数目标退出码、异常类别、阶段、完整原因与本次已知产物引用），并读回核验。
**失败记录优先于完整 `0006`**：即使磁盘上同时有可解析的完整 `0006`，恢复入口也只按失败诊断报告类别与阶段；
`started.json` 存在但既无完整成功集合又无可用诊断时视为未完成阻断。失败或未完成的批次**不能继续、改签或补跑**，
需新建批次。`status` 只读：不重新调用复算、筛查、标准化或装载核心，不写文件，并显示
`crosscheck_status=RULE_CROSSCHECK_RECORDED` 与 `completed_actions`。

---

## 10. 第八个命令：事实底稿（`build-fact-packet`）

```powershell
& $py -B $workflowScript build-fact-packet --batch-dir "$root\data\batches\<新父目录>\<新叶子>"
```

- 只接受**本版本新建**、连续合法 `0001`—`0006` 且当前恰为 `DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED
  + RULE_CROSSCHECK_RECORDED` 的批次；早期阶段／停止态／MISMATCH／上游失败／已有 `0007`／已有
  `workflow\fact_packet\` 一律在**写入之前**拒绝。没有合法 MATCHED `0006` 就不调用底稿核心。
- 前提要求**完整 MATCHED 十维度**（`matched is True`、`differences=[]`、每维度 `executed`／`matched`
  严格 true 且差异数为严格整数 0、差异总数 0），仅有 `phase`、`matched` 标志或一份底稿文件都不算前提满足。
- 宿主要求冻结控制器 `SCREEN_AND_BUILD_FACTS` 的 `simulation_allowed` **严格为 `true`**（开发态模拟允许，
  不等于真实批准；控制器在 `DEV_GATE2_APPROVED` 的真实返回保持不变，宿主只通过 revision／已有现场禁止重复）。
- 三个输入 `workflow/gate2/normalized.json`、`workflow/screening/screening_report.json`、
  `workflow/crosscheck/crosscheck_report.json` 的**对象与文件字节哈希来自同一次读取缓冲**；与已核验的各自
  前序凭证比较；构建前实读固定推导数据库路径，其字节哈希必须与前序材料一致。
- 宿主**真实调用一次**冻结 `build_fact_packet(normalized, screening_report, crosscheck_report)`：只传三个
  内存对象，不传数据库路径／答案册／SQL／生成器，不调用筛查或复算核心；调用前留三个对象的规范指纹，
  核心返回后与公开返回前按**保留的同一对象引用**核对未变；宿主不向输入添字段、不对返回二次加工。
  `FactPacketBlocked`→阻断／退出 1；`FactPacketError`→运行失败／退出 2（保留异常链与本层阶段 `fact_packet`）。
- 校验本次返回恰为 `{packet, packet_sha256, markdown}`、packet 版本 `TASK-008-fact-packet-1.1`、
  `batch_status=DEV_FACT_PACKET_READY`、`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed is False`、
  期间／主体／币种、三对象与工作簿绑定、`packet_sha256` = packet 规范指纹；`summary` 形状与数量必须符合
  已核验筛查报告（规则分布、线索总数、R02 超额合计）。业务公式、来源上下文与正文渲染继续由冻结核心负责。
- 固定落盘 `workflow/fact_packet/`：`started.json`、`fact_packet.json`、`fact_packet.md`、`artifacts.json`，
  失败时 `failure.json`。**三种指纹分开命名与核验**：JSON 文件字节 SHA-256、packet 规范对象 SHA-256、
  Markdown 文件字节 SHA-256。JSON 与该次返回的 packet 严格规范 JSON 相等；Markdown 磁盘字节**精确等于**
  返回 markdown 的 UTF-8 字节（无 BOM、明确 LF、不增删结尾换行、不 strip、不重写文案）。
- 成功才追加 `0007.json`：`revision` 严格整数 7（排除 bool/float）、`kind=BUILD_FACT_PACKET`、
  `previous_file_sha256` 为操作开始时实读 `0006` 字节哈希、`workflow` 与 `0006.workflow` **完整严格相等**；
  `operation` 绑定四份产物固定相对路径与实际字节哈希、packet 规范指纹、核心／宿主身份与
  `fact_packet_status=FACT_PACKET_RECORDED`，并保留 artifacts 完整内嵌副本。
- 链只扩展到连续 `0001`—`0007`；`0005`、`0006` 各自核验自身操作与各自初始前序哈希，不因链尾变 `0007`
  而误用链尾 operation／hash 提取筛查／复算摘要。
- 成功 API／`status` 保留筛查与复算摘要，新增 `fact_packet_status=FACT_PACKET_RECORDED`、`fact_packet`
  摘要与 `completed_actions` 项 `FACT_PACKET`；`phase` 仍为 `DEV_GATE2_APPROVED`，真实批准恒为 `null`，
  `next_step_allowed=false`。**`0007` 只表示事实底稿已持久化**，不代表审计完成、审计通过或底稿已批准，
  也不开放 AI 或人类判断入口；不新增 `0008`。

**失败与恢复**：操作开始前的拒绝**不创建** `fact_packet/`；一旦本次已创建并开始，任何失败都会尽力独占保存
`fact_packet/failure.json`（固定版本、`batch_id`、`host_version`、严格整数目标退出码、异常类别、准确
`fact_packet` 阶段、完整原因与 `exception_chain`、已知产物引用），并读回核验；诊断保存本身失败时如实按
运行失败返回。**失败诊断优先于完整 `0007`**：共用恢复入口在**解析 checkpoint 链之前**核验本层有效失败诊断，
半写或损坏的 `0007` 不会把运行失败 2 遮成任意 JSON 错误 1；完整 `0007` 写完后抛错而留下有效失败诊断时
也必须恢复为失败。非法 JSON／版本／身份／类型或非文件诊断为协议阻断 1；只有 `started.json`／部分结果
而无成功集合是未完成阻断，不退回旧 READY。不自动删现场、补签、续写或重试。

`status` 只读恢复 `0001`—`0007`；`0007` 时按已绑定文件核验 packet／Markdown／artifacts 与三种指纹并生成
真实摘要，**不重新构建或渲染**，不调用 `normalize_workbook`／`load_normalized_to_sqlite`／`screen_sqlite`／
`verify_rule_facts`／`build_fact_packet`／`render_markdown`，不启 receiver／checker／子进程／网络，不写文件。

---

## 11. 第九个命令：保存模拟独立初判（`record-simulated-initial-judgment`）

```powershell
& $py -B $workflowScript record-simulated-initial-judgment `
  --batch-dir "$root\dataatches\<新父目录>\<新叶子>" `
  --submission-file "$root\data\<容器>\submission.json"
```

**位置**：只接受**合法的 `0007`**（`DEV_GATE2_APPROVED` + `RULE_SCREEN_RECORDED` +
`RULE_CROSSCHECK_RECORDED` + `FACT_PACKET_RECORDED`）批次；早期阶段、停止态、上游有效失败、
本层目录已存在或已有 `0008` 一律拒绝，不覆盖、不接管、不自动重试。

**显式模拟输入**：`--submission-file` 指向调用方自备的 UTF-8 JSON 对象，字段与冻结纯核心协议一致
（`docs/INITIAL_JUDGMENT_GUIDE.md`）：`submission_version=TASK-016-initial-judgment-submission-1.0`、
`event_id`、`batch_id`、`fact_packet_sha256`、`scope=BATCH_FACT_PACKET`、
`actor_kind=SIMULATED_HUMAN`、`actor_id`、`simulation=SIMULATED_TEST_ONLY`、含时区 `occurred_at`、
`assessment`、`reason`，可选 `needed_evidence` 与 `finding_notes`。本层只支持显式模拟身份，
**不生成默认提交、不补事件 ID／身份／时间／判定文本**；`assessment`/`reason` 允许“暂不能判断”
但必须带调用方给出的非空原因，零条线索也不会被自动判成“无问题”。CLI 把读到的 JSON 对象交给同一公开
API，只保存**接收到的对象快照**（`submission.json`），不宣称保存了外部文件的原始字节。

**宿主专属核心绑定**：`scripts/build_demo_initial_judgment.py` 自批次 `start` 起就加入宿主静态绑定
（`HOST_BOUND_PATHS` 的 `initial_judgment_core`），实测哈希保存在
`bindings.host_code_sha256.initial_judgment_core`，并随 `run_bindings` 一起进入 workflow 状态；
控制器仍只校验它原有的八项 `code_sha256`，**不放宽也不改控制器**。旧批次缺少该绑定或宿主代码
不一致时如实拒绝；全部演示从最终宿主新建批次，不为历史产物补签。

**固定落盘**：`workflow/initial_judgment/` 仅含 `started.json`、`submission.json`、
`initial_judgment.json`（冻结核心的**完整返回外层**，恰为 `record`／`record_sha256`）、`artifacts.json`，
失败时才有 `failure.json`；全部 UTF-8 无 BOM、明确 LF、独占创建并写后读回核验。文件字节哈希与
对象规范指纹分列，不混用。

**成功才追加 `0008.json`**：`revision` 严格整数 8、`previous_file_sha256` 等于本次初始实读 `0007`
字节哈希、`kind=RECORD_SIMULATED_INITIAL_JUDGMENT`、`operation` 完整内嵌 `artifacts` 及其文件指纹与
固定相对路径；**`workflow` 与 `0007` 严格规范 JSON 等值**（不追加控制器 `history`、
`simulated_decisions`、请求、审批或新 phase）；`phase` 仍为 `DEV_GATE2_APPROVED`，`gate1_approval`/
`gate2_approval` 仍为 `null`，`next_step_allowed=false`。链扩展到连续 `0001`—`0008`；`0005`／`0006`／
`0007` 始终按各自 `operation` 与初始读数核验，不把新的链尾 `operation` 当作上游摘要。拒绝 `0009`、
序号跳跃、半文件、未知文件或目录；**已有 `0008` 禁止再次提交（换 `event_id` 也不覆盖）**，
本卡不支持修订、撤销、合并、多份初判或自动重试。

**成功摘要**：保留此前的筛查／复算／事实包摘要，新增
`initial_judgment_status=SIMULATED_INITIAL_JUDGMENT_RECORDED`、本层文件引用与 `record_sha256`、
模拟事件摘要；`completed_actions` 只增加 `SIMULATED_INITIAL_JUDGMENT`。可以说明“已保存模拟记录”，
**不得**写成 `HUMAN_INITIAL_JUDGMENT_SAVED`、`AI_READY` 或“主理人已初判”；`real_approvals` 仍为 0，
真实批准仍为 `null`。`record` 本身仍是冻结核心的 `DEV_INITIAL_JUDGMENT_VALIDATED` 协议，其边界
文本不被改写来冒充身份认证。

**AI 许可**：本层会显式调用冻结控制器的 `GENERATE_AI_SUGGESTION` 动作检查，并把**真实返回值**
（严格 `false`）记入 `artifacts.ai_action_simulation_allowed`。该 `false` 只表示 **AI 未开放**，
不是对本次模拟记录保存的授权结论；宿主不把 `SCREEN_AND_BUILD_FACTS` 的既有许可改名为初判许可，
也不捏造新的控制器 action。

**失败与恢复**：操作开始前的拒绝**不创建** `initial_judgment/`；一旦本次已创建并开始，任何失败都会
尽力独占保存 `initial_judgment/failure.json`（固定协议、批次／宿主／核心绑定、
`stage=initial_judgment`、异常类别与消息、`exception_chain`（cause／context）、严格整数目标退出码与
观察到的产物状态）并写后读回核验。核心／协议阻断映射退出码 1，I/O 或意外运行失败映射退出码 2，
保留原因链。**失败诊断优先于完整 `0008`**：共用恢复入口在**解析 checkpoint 链之前**核验本层有效失败
诊断，半写或损坏的 `0008` 不会把运行失败 2 遮成 JSON 解析错误；完整 `0008` 写完后抛错而留下有效失败
诊断时，恢复同样按失败处理。无有效失败但有未完成现场时如实拒绝，不补签、不续写；只恢复被改坏的输入
不能清除已保存的失败事实，也不得删除诊断来凑成功。

**只读恢复**：`status` 不调用 `normalize_workbook`、`load_normalized_to_sqlite`、`screen_sqlite`、
`verify_rule_facts`、`build_fact_packet` 或 `build_initial_judgment_record`；它用已保存的凭证、
提交快照、严格协议、指纹与来源绑定恢复，并要求记录内嵌的原文与绑定仍与已保存 `submission.json`
和 `0007` 一致。`inherited` 的 `0001`—`0007` 仍按未保存模拟初判恢复；只有 `0008` 才标记本层完成。
`status` 在最后一次摘要读取与控制器动作检查之后仍会实读磁盘复测本次消费的材料（含本层四份产物、
`0008`、Gate2 材料与数据库、上游产物、宿主清单与静态绑定）。

**边界**：保存模拟初判**不等于**真实人类独立初判已保存，不表示身份认证、审计完成或真实 Gate 批准；
真实判断与批准仍由人类作出。本层不改冻结事实包及其“尚未保存人类判断”的说明，不生成 AI 建议，
不接 LLM／网络／UI／ERP，不建立 `0009`。

## TASK-014 补充说明（复算接入与 0006）

### TASK-014-R2 补充说明（验证方法与证据，宿主未改）

- **宿主在本轮保持冻结**（TASK-014-workflow-host-1.0，哈希见本卡回执）；R2 只修本任务验证入口与指南/回执。
- **失败现场文本引用**：半写与完整后 sentinel 的待写文本按确切 UTF-8 字节单独保存，并在保存后**重新读取该文件**
  计算字节数与文件哈希；实测两场景 ile_sha256 == buffer_sha256、
eread_matches_buffer=true
  （partial 76445 字节、throw 76375 字节）。
- **半写进入真实 writer**：不替换 _write_exclusive_json，只包装真实 writer 自己
  open(path, x, encoding=utf-8, newline=\n) 得到的写句柄，在其一次 write 上写前半段后抛 OSError；
  实测真实 writer 进入 1 次、写入命中 1 次、独占模式 x、
ewline=\n、磁盘半写 38222 字节与预期一致，
  异常链为 ['WorkflowHostError', 'OSError']，新进程恢复退出 2、stage=crosscheck。
- **计数口径分列**：总体从现场导出（批次 11、MATCHED 报告 8、成功凭证 6、失败现场 3、MISMATCH 1）；
  本轮流程检查批次为子集（MATCHED 4、成功凭证 4）；子进程实际执行从批次留痕导出（receiver 启动 11、
  checker 由 receiver 启动 11 且 exit_code=0 11、直接 checker CLI 调用 0）；CLI 不可观测核心次数仍为 null。
- **公开调用登记**：造样用的 screen_dev_batch 与其余公开 API 同入一个记录入口（本轮 API 记录 7 条），
  异常记录 	raceback 取自 exception.__traceback__。

---

### TASK-014-R1 补充说明（复算恢复收尾、失败优先与同缓冲输入）

- **真正最后一次摘要消费之后的复测（B1）**：`status` 在最后一次复算输出读取（摘要、报告规范指纹、内嵌
  artifacts 比较）与最后一次控制器动作检查之后、返回成功之前，重新核验本次消费文件的磁盘字节、
  复算失败诊断不存在、筛查产物与数据库、宿主清单、静态绑定与全部 `0001`—`0006` 字节；预期值只来自
  **初始同缓冲读取**或本次真实 writer 返回。实测读取顺序：第一次读取来自 `_verify_crosscheck_operation`
  （链核验），第二次来自 `inspect_dev_batch` 的摘要读取，第二次之后紧跟收尾磁盘复测。
- **失败诊断优先于链解析（B2）**：四类失败诊断（Gate2／筛查／复算，以及清单层失败）在**解析 checkpoint 链
  之前**读取并核验，因此半写或损坏的 `0006` 不会再以协议解析错误遮蔽有效的复算失败诊断。有效的
  `crosscheck/failure.json`（`target_exit_code` 严格整数 2）恢复为 `WorkflowHostError`／退出 2；协议非法诊断
  仍退出 1；MISMATCH 仍退出 1；缺失、未知 checkpoint 与非法失败记录都不会降级为 READY。
- **准确阶段与完整异常链**：复算失败诊断的 `stage` 必须属于 `crosscheck` 阶段（不再出现 `prepare_gate2`）；
  `exception_chain` 逐环保存 `class`／`message`／`stage`／`reasons`，覆盖原始 `__cause__`／`__context__`；
  失败诊断自身保存失败时如实按运行失败返回。
- **同缓冲输入（B4）**：`workflow/gate2/normalized.json` 的对象与文件字节哈希来自**同一次读取缓冲**
  （`_read_json_with_bytes`），不再先解析再另读；Gate2 `load_report`／`artifacts` 同样处理。
- **`started.json` 指纹协议**：`TASK-014-crosscheck-start-1.0` 除三份文件字节哈希外，另保存
  `normalized_payload_sha256` 与 `screening_report_canonical_sha256` 两项**规范对象指纹**；恢复端严格核验其
  与本批次实际读数、装载报告声明及复算报告来源指纹一致。文件字节哈希与对象指纹分开，不得互相替代。
- 实测计数（R1 最终入口）：CLI 调用 76 次（`start` 11／`record-simulated-decision` 11／`prepare-gate2` 11／
  `record-simulated-gate2-decision` 11／`screen-rules` 8／`crosscheck-rules` 11／`status` 13）；进程内观测
  复算核心 1 次、筛查核心 1 次；CLI 子进程内部核心次数**不可观测，记 null**。

---




- **checkpoint 链扩展到连续 `0001`—`0006`**；`0005` 的语义在链尾为 `0006` 时仍按 `0005` 自己的
  初始实读字节哈希核验，筛查摘要也始终取 `0005` 自身的操作摘要，不误用链尾 `0006` 的哈希或字段。
- **`status` 对 `0001`—`0006` 各合法阶段都返回退出码 0 与真实 phase**；`0006` 恢复时会重新核验
  `crosscheck/` 三份产物、报告对象指纹、内嵌 artifacts 副本、筛查／Gate2 产物、数据库与 `0001`—`0006` 字节，
  并在最后一次控制器调用与最后一次数据消费之后复测全部已消费对象；期望值只来自初始同源读取或本次真实 writer 返回。
- **计数口径**：复算入口（`crosscheck_dev_batch`／`crosscheck-rules`）与筛查入口分列；CLI 子进程内部的核心
  调用次数不可观测，如实记 `null` 并以成功的 CLI 命令数另行推导，不冒充进程内实测值。
- 实现版本 `TASK-014-workflow-host-1.0`；`CHECKPOINT_VERSION`／`HOST_MANIFEST_VERSION` 仍为
  `TASK-012-*-1.0`，`TASK-013-screen-*` 与 `TASK-014-crosscheck-*` 各自保持 1.0（实现版本与持久化协议版本分开表述）。

---

## TASK-013-R2 补充说明（只读恢复与最终收尾）

- **所有合法阶段都能只读恢复**：`status` 对 `0001`（Gate1 pending）、`0002`（Gate1 已模拟 APPROVE）、`0003`（Gate2 pending）、`0004`（Gate2 APPROVED／HELD／REJECTED）与 `0005`（筛查完成）都返回退出码 0 与**真实 phase**；`actions_simulated_allowed`／`simulated_action_allowed` 如实反映控制器动作允许值（停止态可读取，但动作不可继续）。此前 `screen_expected` 只在 `revision >= 5` 分支赋值却在分支外读取，会让早期阶段恢复退化为 `UnboundLocalError`／退出 2；该变量现已与筛查专属收尾一起被条件化。
- **最终复测覆盖全部已消费产物**：在**最后一次必要控制器调用与最后一次必需数据消费之后**、返回成功之前，宿主继续复测 `normalized`／`load_report`／Gate2 `artifacts`、数据库、`host_manifest`、`0001—0005`、screening `started`／`report`／`artifacts`、静态绑定与失败／未知项状态；期望值只来自**初始同源缓冲读取**或本次真实 writer 返回，不用事后新读数替换。因此本次调用内被观察到的变化会**当次**阻断（`WorkflowHostBlocked`／退出 1，消息含对应文件路径），不再等到下一次调用才拒绝。
- 实现版本 `TASK-013-workflow-host-1.2`；`CHECKPOINT_VERSION`／`HOST_MANIFEST_VERSION` 仍为 `TASK-012-*-1.0`，`TASK-013-screen-*` 仍为 1.0（实现版本与持久化协议版本分开表述）。
