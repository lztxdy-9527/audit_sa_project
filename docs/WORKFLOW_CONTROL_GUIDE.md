# 开发态 Gate 1／Gate 2 流程控制指南（TASK-009）

版本：TASK-009-workflow-control-1.2；日期：2026-10-11；执行端：DeepSeek；依据：`docs/tasks/TASK-009_DRAFT.md`、`docs/tasks/TASK-009-R1.md`、`docs/tasks/TASK-009-R2.md`、`docs/reviews/REVIEW_TASK_009.md`、`docs/reviews/REVIEW_TASK_009_R1.md`、`docs/reviews/REVIEW_TASK_008_R1.md`、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2—6 节、`docs/BATCH_RECEIVE_GUIDE.md`、`docs/NORMALIZATION_GUIDE.md`、`docs/SQLITE_LOAD_GUIDE.md`。

本模块是**纯内存的开发态两处守门控制内核**：实务上对应“收到 ERP 导出后先停在范围／接收核验”“标准化与数据库勾稽后再停一次”。
只有在测试中收到明确的**模拟人类决定**时，才允许模拟下一阶段。本模块**不建立正式契约、不批准任何真实 Gate、不保存或预填人类判断、不生成 AI 建议**。

> 所有状态保持 `mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`、`contract_status=DRAFT_NOT_IN_FORCE`；
> 真实 `gate1_approval`／`gate2_approval` 恒为 `null`；模拟决定另列于 `simulated_decisions`，固定标记 `SIMULATED_TEST_ONLY`。

---

## 1. 公共接口

```python
create_dev_workflow(batch_id, run_bindings) -> dict
prepare_dev_gate(workflow, gate, materials, *, current_bindings) -> dict
record_dev_decision(workflow, decision, *, current_bindings) -> dict
check_dev_action(workflow, action, *, current_bindings) -> dict
```

- 前三个返回 `{"state": ..., "state_sha256": ...}`；第二、三、四个接收同形 workflow 对象（`{"state", "state_sha256"}`）。
- `state_sha256` 是对 `state` 的规范 JSON 指纹，放在外层以避免自引用；规范口径与上游一致：`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、`allow_nan=False`，UTF-8 SHA-256。
- 核心**不读写文件／数据库／Excel**，不读答案册，不导入上游或测试／QA，不调用 LLM／网络／子进程，只用标准库。
- 时间与 `batch_id` 由调用方传入；**不自动取当前时间、不生成随机身份**；不修改入参，同输入同返回。
- 异常：`WorkflowBlocked`（前提、协议或不允许的转移，带字段与原因）；`WorkflowError`（意外错误，保留阶段、原始原因与异常链）。

## 2. run_bindings（运行绑定）

至少包含：

| 键 | 内容 |
| --- | --- |
| `input_sha256` | 来源工作簿哈希 |
| `spec_sha256` | 规格文档哈希 |
| `contract_draft_sha256` | 契约草案哈希 |
| `code_sha256` | 逐文件哈希：本控制器、接收、checker、标准化、装载、筛查、复核、事实底稿 |
| `rule_sql_sha256` | R01—R04 规则 SQL 哈希 |
| `config` | 公司、期间、截至日、币种（本项目固定单公司／2026 年 9 月／CNY） |

哈希必须是**完整 64 位十六进制字符串**；配置必须等于本项目固定范围；标识符保留原字符串（不转 `int`、不 `strip` 改值）。创建时保存完整 `run_bindings` 及其规范指纹。

之后**每次调用**都核对：`current_bindings` 与创建时的完整规范对象严格相同、workflow 外层指纹正确、`state.phase` 与 history 事件顺序相符（不信任调用方填写的 phase）。任何绑定变化或缺失都阻断，并提示**建立新 workflow／新批次**，不复用旧模拟批准。

> 本层只核对调用方提交的**内存声明**，**不宣称实读了当前磁盘字节**；后续正式入口必须自行提供实测绑定。

## 3. 状态机

```text
DEV_CREATED
  → DEV_GATE1_PENDING
  → DEV_GATE1_APPROVED
  → DEV_GATE2_PENDING
  → DEV_GATE2_APPROVED
```

- 只有 `create_dev_workflow` 能创建首态 `DEV_CREATED`。
- `prepare_dev_gate` 分别从 `DEV_CREATED`（Gate1）／`DEV_GATE1_APPROVED`（Gate2）建立请求并进入对应 PENDING。
- `record_dev_decision` 只处理**当前 PENDING** 的 Gate。
- `HOLD`／`REJECT` 进入 `DEV_GATE1_HELD`／`DEV_GATE1_REJECTED`／`DEV_GATE2_HELD`／`DEV_GATE2_REJECTED`，本版本均为**停止态**：不能改成批准、不能继续、不能重新 prepare；需要补证／修订时**新建 workflow 并保留旧记录**。
- Gate2 请求绑定 Gate1 **已批准模拟决定的指纹**（`prior_simulated_decision_sha256`），拿另一个 workflow 的 Gate1 记录无法解锁。

`state` 保存：版本、原 `batch_id`、`run_bindings` 及其指纹、`phase`、两处 request、模拟决定、有序 `history`。history 记录递增序号、事件类型、gate、材料／请求指纹、完整决定及前后状态；新返回对象保留旧事件，不覆盖历史。重复事件、重复决定、冲突决定、缺失关键字段与类型错误均明确阻断。**不做数据库／文件持久化，也不声称历史不可篡改。**

### 3.1 重放校验范围（TASK-009-R1 起）

历史状态来自调用方的对象，**外层指纹正确不等于内部协议正确**。每次调用都会按 history 重放并执行与首次调用**同一套**协议约束：

- **先检容器与条目再访问**：`state`／`history`／`requests`／`simulated_decisions`／`materials`／`evidence` 必须是对应类型；每个条目必须是对象且含必需键；值类型与枚举先验后比。协议不完整给 `WorkflowBlocked` 并指出**完整路径**（不会退化成 `KeyError`／`AttributeError` → `WorkflowError`）；真正的意外错误仍是 `WorkflowError` 并保留异常链。不吞异常、不把程序错误改判为阻断。
- **决定正文与派生指纹**：合法保存的决定记录额外含派生字段 `decision_sha256`；重放时**先剥离该字段**得到决定正文，再按「首次 `record` 的同一套必需键、枚举、类型、时间、身份声明、模拟标志、说明与确认项」核验，并核对 `event_id`、`gate`、`request_id`、`materials_sha256` 及批次／绑定引用与对应事件、当前请求和 workflow 一致。**决定内的 `decision_sha256` 与事件顶层的 `decision_sha256` 都必须等于决定正文的实际规范指纹**；`history` 与 `simulated_decisions` 两处存放的记录必须严格一致。首次提交接口仍**不接受**未知字段。
- **请求**：材料内容的规范指纹必须等于请求声明的 `materials_sha256`；材料本身重新按 §4 的 `prepare` 协议核验（批次／gate／绑定／范围／证据）；`request_id` 按 §2 的确定性公式**重算比对**；`requests` 中不得存在未在 history 出现的额外请求，`simulated_decisions` 与 history 的决定**逐项一一对应**。
- **Gate2 前序绑定**：只接受**本 workflow 已验证的 Gate1 APPROVE 决定正文的实际指纹**，不使用未经核对的内嵌值。
- **事件自身的引用字段**（TASK-009-R2 起）：不只按 `event_type` 决定状态，还核验**该事件种类原本生成的字段**与权威 `state`／请求／决定一致——不强迫所有事件具有相同字段集，也不转换、补填或忽略错误引用。缺必需字段或不一致均为带路径的 `WorkflowBlocked`：

  | 事件类型 | 除 `seq`／`event_id`／`event_type`／`phase_before`／`phase_after` 外必须核验 |
  | --- | --- |
  | `WORKFLOW_CREATED` | `gate` 为 `null`；`batch_id` 与 `state.batch_id` 一致；`run_bindings_sha256` 与创建绑定一致 |
  | `GATE1_REQUEST`／`GATE2_REQUEST` | `gate` 与 `event_type` 所指 Gate 一致；`request_id`／`materials_sha256`／`run_bindings_sha256` 与对应已验证请求一致；Gate1 前序决定为 `null`，Gate2 前序决定为已验证 Gate1 批准**正文**的实际指纹 |
  | `GATE1_DECISION`／`GATE2_DECISION` | `event_id`／`gate`／`request_id`／`materials_sha256` 与已验证决定正文及当前 Gate 请求一致（正文与事件顶层 `event_id` 必须相同） |

  事件中不属于该类型的字段一律拒绝。
- **集合与次序**：结束重放时把 **`state.requests` 实际保存的对象**与按 history 重放得到的请求逐项比较——无 history 事件的额外请求或缺少实际请求都阻断；`simulated_decisions` 必须**按 history 次序**与决定事件的完整记录逐项一致（**不得重排**，不是只比 ID 集合）。
- **严格整数**：`history.seq` 必须是正整数且非 `bool`／非浮点，且从 1 连续递增；Gate2 四表 `row_counts` 必须是非负整数且非 `bool`／非浮点（见 §4.2）。保存观察到的原类型，不 `int()` 转换、不补零。

这些都是**既有协议在重放入口的一致应用**：用于发现自相矛盾的内存对象，**不是**证明历史真实，也**不抵御**能重写整个对象与全部哈希的同权限篡改。

## 4. 守门材料（materials）

结构化守门材料，不能只交一个 `passed=true`。共同必需：`batch_id`、`gate`、`run_bindings_sha256`、`scope`、`blocking_issues`、`evidence`。

- `scope`：公司／期间／截至日／币种／合成数据标志、来源描述、已知限制。来源真实性与完整性是**声明限制**（不用哈希推导真实性）。
- `blocking_issues`：列表；**非空不生成可批准请求**。

### 4.1 Gate1 evidence

`evidence.quality_report` 为完整质量报告；至少核对：`result` 严格为 `pass`、`issues` 存在且为空列表、`issue_counts_by_code` 存在且为空对象、`workbook.sha256` 与 `run_bindings.input_sha256` 对应、`checker.sha256` 与 `run_bindings.code_sha256.check_demo_data` 对应。不复制 checker 的 22 字段核验算法；结构、范围或核验失败不能靠传空 `blocking_issues` 绕过。

### 4.2 Gate2 evidence

`evidence.normalized` 与 `evidence.load_report` 为完整对象；至少核对：

- 两者开发态且 `next_step_allowed=false`；版本分别为 `TASK-004-normalized-1.1` 与 `TASK-005-sqlite-load-1.2`／`demo-schema-1.0`；
- normalized 质量 `pass` 且 `issue_counts_by_code` 存在且为空；
- `source.input_sha256` 一致；
- `load_report.normalized_payload_sha256` 等于**本次 normalized 对象的规范指纹**；
- 状态 `DEV_SQLITE_VERIFIED`；`round_trip_exact`／`event_allocation_balanced` 严格 `true`；`foreign_key_check` 为 `clean`；`integrity_check` 为 `ok`；
- `net_checks` 六项齐全且严格 `true`：`master_net_equals_known_plus_missing`、`master_net_equals_normalized`、`known_net_equals_normalized`、`missing_net_equals_normalized`、`empty_ap_id_equals_normalized`、`unknown_ap_id_equals_normalized`；
- 四表 `row_counts` 与 normalized 记录数量一致（`row_counts` 各项必须是**非负整数且非 `bool`／非浮点**；`20.0`、`true` 等数值等价类型一律阻断，合法单行小样的 `1` 正常可用）；
- 付款／退款主表及分摊总额、`master_net`／`known_payable_link_net`／`missing_payable_link_net` 为整数分（非 `bool`），与 `normalized.amount_reconciliation` 相应字段一致；主表付款＝付款分摊、主表退款＝退款分摊、`master_net`＝已知＋缺失。

**缺失应付关联净额非零不阻断**（它是业务待核实事实，不是自动质量阻断）；入库勾稽成功也**不称为无业务异常**。本层不重做装载器逐条校验，也不增加第三套规则计算。

### 4.3 request

保存完整 materials 及其规范指纹；`request_id` 由本 workflow 批次、gate、绑定指纹、材料指纹及（Gate2）前序模拟批准指纹**确定性生成**。

## 5. 模拟决定（decision）

必需字段：`event_id`、`batch_id`、`gate`、`request_id`、`materials_sha256`、`decision`（`APPROVE`／`HOLD`／`REJECT`）、`actor_kind` 固定 `SIMULATED_HUMAN`、`actor_id`、`occurred_at`（**带时区** ISO 日期时间）、`reason`、`simulation` 固定 `SIMULATED_TEST_ONLY`；全部显式传入且类型严格。

- `APPROVE` 还须提供确认项：Gate1 为 `scope_and_source_reviewed` 严格 `true`；Gate2 为 `reconciliation_reviewed` 严格 `true`。
- `HOLD`／`REJECT` 不要求确认成功，但**必须有说明**。
- `AI`／`SYSTEM` 身份、未标注模拟、无说明、空白身份、错误请求／材料／批次、把 `1` 当 `true`、缺字段、未知字段、重复 `event_id` 均**不被接受**。

> 模拟 actor 只是**可检查的身份声明**，不提供真实人类认证。核心没有正式批准接口；测试之外不得让 AI 填写这些对象来解锁真实批次。
> **历史条目同样受本节全部约束**：已保存的决定在每次重放时都会按同一套必需键、枚举、类型、身份声明、模拟标志、说明与确认项重新核验，不会因为「它已经在历史里」而被放过。

## 5.1 留痕与可重建性（测试入口）

入口把每次探针的**完整实参**（含**关键字实参**）与**完整返回值**或**异常类别与消息**、预期与实际、调用前后的指纹、以及为该次调用所做的**同步操作说明**一并保存。记录的固定形状为：

```json
{"function": "check_dev_action",
 "args":   {"arg0": {"object_path": "objects/<sha>.json", "object_sha256": "...", "file_sha256": "..."}},
 "kwargs": {"current_bindings": {"object_path": "objects/<sha>.json", "object_sha256": "...", "file_sha256": "..."}},
 "restore": "getattr(controller, saved_function)(*restored_args, **restored_kwargs)"}
```

即：先按 `object_path` 读回对象（校验 `file_sha256` 与 `object_sha256`），再 `restored_args = [args 按序]`、`restored_kwargs = {键: 值}`，然后用
`getattr(controller, saved_function)(*restored_args, **restored_kwargs)` 还原调用。**`current_bindings` 等 keyword-only 实参必须真实保存**，不得从 workflow 内的旧 `run_bindings` 推断（否则会抹去该次测试所改的绑定）。

- 阻断调用不返回新 state：记录 `returned_state: null` 并附说明，同时记录实参 workflow 的 state 在调用**前后**的规范指纹以证实未被修改（`input_workflow_unchanged`）。
- 内容寻址对象目录 `objects/<sha256>.json`（同一内容只落一份，`object_sha256` 为规范 JSON 指纹即文件名，`file_sha256` 为落盘字节指纹），`object_index.json` 给出全部对象的标签与两个指纹。
- `key_workflows.json` 保存两 Gate 正常流程的五个关键 workflow **完整 `{state, state_sha256}`**；`sync_operations.json` 记录每次派生指纹同步的字段路径、方法与说明；`checks.json`／`summary.json` 保存全部检查明细与计数；`helper_self_tests.json` 单独保存断言 helper 的自测；`replay_records.json` 保存从**保存文件**重放的结果。
- **重放验收**：保存完成后，用公共 API 从保存的 args／kwargs **重新加载**并重放五条绑定变化负向（必须再次得到指向绑定变化的 `WorkflowBlocked`，且结果与首次一致），再重放一条成功调用（完整返回与首次精确相等）；另对全部引用做离线存在性、双指纹与**参数完整性**（用函数签名 `bind()` 校验，能重建调用）核对。

断言 helper 的规则：`expect="blocked"` 时**必须同时**满足异常类别与指定的原因条件（字段路径或稳定标识），只满足类别一律判失败；helper 自测证明「类别正确但原因不含指定标识」会被判为断言失败。自测用**显式开关**隔离，**不写入主 `checks`／`failures`**，单独保存与计数（其真实 API 调用仍计入总次数，但**不充当**原探针）。

## 6. 行为检查（check_dev_action）

支持 `NORMALIZE_AND_LOAD`、`SCREEN_AND_BUILD_FACTS`、`GENERATE_AI_SUGGESTION`；返回明确的 `action`、`phase`、`simulation_allowed`（严格 bool）、`reason`、`run_bindings_sha256`、`state_sha256`，并固定 `next_step_allowed=false`。

| 动作 | 允许模拟的阶段 |
| --- | --- |
| `NORMALIZE_AND_LOAD` | 仅 `DEV_GATE1_APPROVED` |
| `SCREEN_AND_BUILD_FACTS` | 仅 `DEV_GATE2_APPROVED` |
| `GENERATE_AI_SUGGESTION` | 始终不允许（尚无人类独立初步判断保存组件） |

未知 action、未知状态、损坏 workflow、绑定不符一律 `WorkflowBlocked`，不默认放行；合法但阶段不允许的动作返回 `simulation_allowed=false` 及原因。

## 7. 完整小例子（测试协议）

```python
w = create_dev_workflow("BATCH-2026-09-DEMO-001", run_bindings)
check_dev_action(w, "NORMALIZE_AND_LOAD", current_bindings=run_bindings)   # 拒绝：DEV_CREATED
w = prepare_dev_gate(w, "GATE1", gate1_materials, current_bindings=run_bindings)
check_dev_action(w, "NORMALIZE_AND_LOAD", current_bindings=run_bindings)   # 拒绝：等待 Gate1 决定
w = record_dev_decision(w, gate1_approve, current_bindings=run_bindings)   # 测试人员显式模拟 APPROVE
check_dev_action(w, "NORMALIZE_AND_LOAD", current_bindings=run_bindings)   # 允许模拟标准化
check_dev_action(w, "SCREEN_AND_BUILD_FACTS", current_bindings=run_bindings)  # 拒绝：Gate2 未批准
w = prepare_dev_gate(w, "GATE2", gate2_materials, current_bindings=run_bindings)
w = record_dev_decision(w, gate2_approve, current_bindings=run_bindings)
check_dev_action(w, "SCREEN_AND_BUILD_FACTS", current_bindings=run_bindings)  # 允许模拟筛查
check_dev_action(w, "GENERATE_AI_SUGGESTION", current_bindings=run_bindings)  # 始终拒绝
```

实务对应：接收合成文件 → Gate1 请求出现 → 先调用标准化行为检查被拒 → 测试人员显式提供模拟 `APPROVE` → 模拟标准化行为检查允许 → 展示**已经存在**的开发标准化／装载结果 → Gate2 请求出现 → 先筛查被拒 → 第二个模拟决定后允许模拟筛查 → AI 建议仍被拒。

## 8. 真实测试命令

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\workflow_tests\task009_r1_04'
```

`--out-dir` 必须是 `data/workflow_tests` 内**尚不存在**的子目录；越界、目录本身或已存在时在写入前拒绝。核心无文件写入；全部测试输入、副本、状态、决定与日志由入口保存（`summary.json`、`checks.json`、`key_workflows.json`、`sync_operations.json`、`helper_self_tests.json`、`object_index.json`、`binding_changes.json`、`final_state.json`（完整 workflow）、`objects/`、`stdout.txt`、`stderr.txt`）。退出码：0 全部符合预期；1 断言或保护失败；2 参数或环境问题。

覆盖：MAIN 完整两 Gate 模拟流程；两 Gate 的 HOLD／REJECT 停止态与非法决定；越级／重复／未知；守门材料失败；缺失应付关联非零仍可形成 Gate2 请求；绑定变化与跨 workflow 复用；workflow 篡改；确定性、入参不变、历史完整与不可信文字；静态与运行期隔离；**R1 新增**：历史决定协议与两处指纹（内嵌指纹改全零、`actor_kind=AI`、确认项 false、缺 `reason`、`simulation=REAL`）、错误分类（请求缺 `request_id`、决定条目为整数应阻断而非意外错误）、严格整数（`row_counts` 浮点／`seq` 布尔与浮点等价、合法单行小样 `1` 可用）、确定性 `request_id` 复核、同步指纹后材料协议复核、五个关键 workflow 序列化往返可用；**R2 新增**：事件引用一致性八项（决定事件 `event_id`／`gate`／`request_id`／`materials_sha256`、创建事件 `batch_id`、请求事件 `run_bindings_sha256`、无 history 事件的额外请求、`simulated_decisions` 重排）、保存引用离线核对与从保存文件重放（五条绑定变化负向 + 一条成功调用）。

分类计数按实际 `case`／`kind` 统计，不硬编码预设总数：原探针、R1 新增、R2 新增、流程检查、helper 自测（单列）、保存文件重放分别列出；API 次数区分「入口调用」与「保存文件重放」，并给出真实总次数。

## 9. 边界与后续接入条件

- 本模块**未执行**原文件或数据库字节核验，**只核对调用方提交的内存声明**；未建立正式契约、未提供同权限篡改隔离、未实现真实入口的暂停／落盘恢复。
- `local` 状态与哈希**不等于身份认证**；`simulated_decisions` 不是真实人类批准；重放校验发现的是**内存对象自相矛盾**，不是现实篡改防御。
- 测试中同步派生指纹（外层 `state_sha256`、决定正文指纹、材料指纹与确定性 `request_id`）**只为让对象自相一致以进入语义核验**，不代表这些对象通过了真实上游重新计算，也不改任何旧证据。
- 下一步需：接入宿主入口、实测文件绑定（真实计算 `run_bindings`）、保存守门材料与实际人类决定，再按契约草案推进“人类独立初步判断 → AI 建议 → 最终判断”。
- 本版本不接入 `data/batches`、不改 `batch_manifest`、不做 UI、不改动任何既有上游模块或历史产物。
