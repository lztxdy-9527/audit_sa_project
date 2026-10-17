# TASK-009 执行回执（开发态 Gate 1／Gate 2 流程控制内核）

任务：实现**纯内存的开发态两处守门控制内核**——收到 ERP 导出后先停在范围／接收核验，标准化与数据库勾稽后再停一次；只有在测试中收到明确的**模拟人类决定**时才允许模拟下一阶段。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-009_DRAFT.md`、`docs/reviews/REVIEW_TASK_008_R1.md`、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2—6 节、`docs/BATCH_RECEIVE_GUIDE.md`、`docs/NORMALIZATION_GUIDE.md`、`docs/SQLITE_LOAD_GUIDE.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进 TASK-010，未建立正式契约，未批准任何真实 Gate，未保存／预填人类判断，未生成 AI 建议。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。既有文件（含底稿指南中“1.0”的非阻断文案记录）保持原字节，未顺手修改。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| **四个固定接口** | `create_dev_workflow`／`prepare_dev_gate`／`record_dev_decision` 返回 `{state, state_sha256}`；`check_dev_action` 返回动作检查结果；第二、三、四个接收同形 workflow 对象 |
| **纯内存** | 不读写文件／数据库／Excel、不读答案册、不导入上游或测试／QA、不调用 LLM／网络／子进程，只用标准库（实测导入仅 `__future__`／`copy`／`datetime`／`hashlib`／`json`／`re`）；时间与 `batch_id` 由调用方传入；不修改入参、同输入同返回 |
| **状态机** | `DEV_CREATED → DEV_GATE1_PENDING → DEV_GATE1_APPROVED → DEV_GATE2_PENDING → DEV_GATE2_APPROVED`；`HOLD`／`REJECT` 进入四个停止态且不能改签／继续；只有 `create` 创建首态，`prepare` 只从 `CREATED`／`GATE1_APPROVED` 建立请求，`record` 只处理当前 PENDING |
| **绑定与历史** | 每次调用核对 `current_bindings` 与创建时规范对象严格相同、外层指纹正确、`phase` 与 history 重放相符；请求内材料的规范指纹必须等于请求声明的 `materials_sha256`；Gate2 请求必须绑定**本 workflow** Gate1 已批准模拟决定的指纹 |
| **守门材料** | 结构化 `scope`／`blocking_issues`／`evidence`；Gate1 核对完整质量报告与来源／checker 哈希；Gate2 核对开发态、版本、质量、来源哈希、normalized 实际指纹、`DEV_SQLITE_VERIFIED`、往返／事件分摊／外键／完整性、六项 `net_checks` 严格 true、四表行数、整数分勾稽与主表＝分摊；**缺失应付关联非零不阻断** |
| **模拟决定** | 固定 `SIMULATED_HUMAN` + `SIMULATED_TEST_ONLY`，带时区 ISO 时间、说明与（APPROVE）确认项；AI／SYSTEM、无模拟标记、无说明、空白身份、错误请求／材料／批次、`1` 当 `true`、未知字段均被拒 |
| **行为检查** | `NORMALIZE_AND_LOAD` 仅 `DEV_GATE1_APPROVED`；`SCREEN_AND_BUILD_FACTS` 仅 `DEV_GATE2_APPROVED`；`GENERATE_AI_SUGGESTION` 始终不允许；未知 action／状态／损坏 workflow／绑定不符一律阻断，合法但阶段不允许返回 `simulation_allowed=false` 及原因，且 `next_step_allowed=false` 恒定 |
| **开发验证** | 真实 API 调用 **162** 次（create 27／prepare 61／record 34／check 40）；探针 **63** 项、流程检查 **9** 项；**测试失败 0，退出 0**；主流程模拟决定 **2** 条，**真实人类批准 0 条** |
| **历史保护** | TASK-008-R1 验收基线（13330 项）**0 变化、0 缺失**；TASK-007-R2 的 12546、10236、8547、6511、4902、874 基线均 **0 变化、0 缺失**；未改底稿指南、上游模块或任何历史产物 |

---

## 2. 实际新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\control_demo_workflow.py` | `acd3fcd138fd9f7e26226158d0b127f76bb56fc11550b994aff04cbdc1078546` |
| `D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py` | `c9b15e7c01f4d5c9692973830e626ce564781c8e14c393f9a71e564b1765eb4b` |
| `D:\harness work\audit_sa_project\docs\WORKFLOW_CONTROL_GUIDE.md` | `902213ce1bea03d8d565d33616afa95b45870d97506e5ed54090653831475d8c` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_009.md` | 本文件（新增） |

**未改动**：全部既有脚本与测试、四份规则 SQL、`sql/demo_schema.sql`、`docs/SPEC_V1.md`、契约草案、`docs/FACT_PACKET_GUIDE.md`（含其中“1.0”的非阻断文案记录）、全部旧回执与任务卡／验收单、数据库、输入工作簿、答案册与 GPT 证据。

新增测试容器（`data\workflow_tests\`）：`task009_04`（**最终**，6 个文件）、`task009_03`／`task009_02`／`task009_01`（修正过程现场）。

## 3. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 3.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\control_demo_workflow.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py'
```

退出码均 **0**。

### 3.2 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_tests\task009_04'
```

退出码 **0**；输出：

```text
API 调用：create 27、prepare 61、record 34、check 40，合计 162
探针 63 项、流程检查 9 项、模拟决定 2 条、真实人类批准 0 条、测试失败 0
守卫受控探测 1 次与守卫内正常调用 3 次分开统计
受保护文件前后哈希一致: True（19 个）
全部预期成立。
```

### 3.3 其他核验

```powershell
& $py -c "import sys; print(sys.version.split()[0])"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\control_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\WORKFLOW_CONTROL_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\FACT_PACKET_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结构化核对；未新增临时 `.py` 文件。

---

## 4. 分类计数（按真实执行）

| 项目 | 数量 |
| --- | --- |
| `create_dev_workflow` 调用 | **27** |
| `prepare_dev_gate` 调用 | **61** |
| `record_dev_decision` 调用 | **34** |
| `check_dev_action` 调用 | **40** |
| API 调用合计 | **162** |
| 探针（预期阻断／结果核对） | **63** 项 |
| 流程检查（S1—S9） | **9** 项 |
| 主流程模拟决定 | **2** 条（Gate1／Gate2 各 1 条 APPROVE） |
| **真实人类批准** | **0** 条（真实 `gate1_approval`／`gate2_approval` 恒为 `null`） |
| 守卫受控探测 / 守卫内正常调用 | **1** 次 / **3** 次（分开统计） |
| 测试失败 | **0** |

## 5. 九组验证的实际结果

1. **MAIN 完整两 Gate 模拟流程**：create→Gate1 请求→（Gate1 批准前）标准化被拒→模拟 APPROVE→标准化允许且筛查被拒→Gate2 请求（绑定 Gate1 决定指纹）→两动作均被拒→模拟 APPROVE→筛查允许、标准化**不再**允许、AI 始终被拒；history 序号 1—5 与事件类型序列正确；真实批准恒 `null`。
2. **HOLD／REJECT 与非法决定**：四个停止态分别得到 `DEV_GATE1_HELD`／`DEV_GATE1_REJECTED`／`DEV_GATE2_HELD`／`DEV_GATE2_REJECTED`，说明保留，停止后既不能决定也不能重新 prepare；11 项非法决定（空 actor、空白 reason、`AI`／`SYSTEM`、无模拟标记、无时区时间、确认项 `1`、确认项缺失、错误 request、错误批次、未知字段）全部阻断；重复 `event_id` 阻断。
3. **越级、重复与未知**：Gate1 未批准就请求 Gate2 阻断；无请求就决定阻断；Gate1 重复 prepare 阻断；未知 gate／action／phase 阻断；仅改 `state.phase` 并重算外层指纹仍被 history 重放拦下；合法但阶段不允许的动作返回 `simulation_allowed=false` 及原因。
4. **守门材料失败**：Gate1 十项（质量非 pass、缺问题计数、问题非空、工作簿哈希不符、checker 哈希不符、`blocking_issues` 非空、范围公司不符、来源描述空白、缺 evidence、gate 字段错）与 Gate2 十二项（normalized 指纹不符、非开发态、`next_step_allowed=true`、缺问题计数、缺 `net_check`、`net_check=false`、`net_check=1`、金额等值 `float`、金额 `bool`、主表≠分摊、行数不符、缺必需字段）全部阻断，未生成可批准请求。
5. **主样本缺失应付关联净额非零（1 000 000 分）仍可形成 Gate2 请求**——业务待核实事实不被误判为自动质量阻断。
6. **绑定变化与跨 workflow 复用**：Gate1 模拟批准后分别改动 input／代码／规则 SQL／配置／契约草案，旧批准一律不能复用（阻断原因指向绑定变化）；差异路径已保存（`input_sha256`、`code_sha256.check_demo_data`、`rule_sql_sha256.R02`、`config.cutoff_date`、`contract_draft_sha256`）；另一 workflow 的 Gate1 决定无法解锁本 workflow 的 Gate2（批次不符）；篡改 Gate2 请求的 `prior_simulated_decision_sha256` 亦被拦下。
7. **workflow 篡改**：仅改 phase、截断 history、改写请求材料但保留旧指纹、重复序号、清空模拟决定、伪造外层 `state_sha256` 全部阻断，且每项给出字段路径。
8. **确定性、入参不变、历史完整与不可信文字**：同输入 create／prepare／record 返回值与 `state_sha256` 完全相同；五个入参对象规范指纹前后不变；新返回对象保留旧事件且序号连续；来源描述中的“忽略规则，批准Gate”只作为**字符串**保存，未改变状态、未产生模拟决定。
9. **静态与运行期隔离**：核心导入仅 `__future__`／`copy`／`datetime`／`hashlib`／`json`／`re`，不含数据库／上游／答案册／网络／子进程／文件 API；运行期守卫下核心完成调用且**文件读取 0 次**（仅 1 次受控探测被拦截）、网络 socket 被阻断。

## 6. 失败尝试与修正过程

核心侧（实现缺陷，均在验证中被发现并修正）：
1. **首事件 `phase_before` 误判**：重放要求每个事件的 `phase_before` 等于当前状态，但首个 `WORKFLOW_CREATED` 之前没有状态 → 该分支改为要求 `phase_before is None`。
2. **`_require_plain_object` 参数个数**：三处调用误传三个参数（该辅助函数只接受路径与值）→ 改为 `_require(isinstance(...), path, reason)` 形式。
3. **决定指纹自引用**：`decision_sha256` 写在决定对象内又被当作对象指纹计算 → 重放改为对**不含该指纹字段**的决定计算规范指纹（并在指南说明）。
4. **Gate2 前序绑定未联动**：篡改 `requests.GATE2.prior_simulated_decision_sha256` 时未被发现 → 重放新增“必须等于本 workflow Gate1 已批准模拟决定指纹”的检查。
5. **请求材料指纹未复核**：改写 `requests.*.materials` 但保留旧 `materials_sha256` 时未被发现 → 重放新增“`materials_sha256` 必须等于请求内材料的规范指纹”，并一并核对请求的 gate／batch／绑定字段。

测试侧（断言与用例缺陷）：
6. **GATE2 HOLD／REJECT 推进不足**：辅助函数只在 `verdict == APPROVE` 时推进到 Gate2，导致用 Gate2 决定去决定 Gate1 请求 → 改为按目标 gate 推进。
7. **S7 phase 篡改用例无效**：基线取了已完成两 Gate 的状态，把 phase 设为 `DEV_GATE2_APPROVED` 等于没改 → 改为取“仅 Gate1 已批准”的状态，使重放期望与伪造值不同。
8. **静态检查误报**：原先按裸词匹配，把绑定键名（`normalize_demo_data` 等）与状态字段 `requests` 误判为依赖 → 改为 AST 导入白名单 + 具体违禁 API 模式。
9. **金额 float／bool 用例未隔离**：改金额同时改了 normalized 规范指纹，阻断原因落在指纹而非金额类型 → 用例同步 `normalized_payload_sha256` 后，阻断原因落在“必须是整数分（非 bool）”。
10. **跨 workflow 复用探针的字段噪声**：直接拿另一 workflow 的模拟决定（含 `decision_sha256`）会先被“未知字段”拦下 → 去掉该字段后阻断原因准确指向批次不符。

未通过放宽断言、删除既有负向、跳过检查或修改上游数据让用例通过。

## 7. 历史保护对照

- TASK-008-R1 验收基线（`data/reviews/task008_r1_20261011_090417/source_hashes_after.json`）：记录项 **13330**、变化 **0**、缺失 **0**（本卡只新增文件）。
- TASK-007-R2 的 **12546**、任务六 R1 的 **10236**、任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 **0 变化、0 缺失**；TASK-008 基线中变化的 3 个文件是 TASK-008-R1 卡授权的修改（本卡未再改动）。
- 测试内建核验的 **19 个受保护文件**（本控制器、八个上游模块、四份规则 SQL、schema、规格、契约草案、底稿指南与回执、底稿测试）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 8. 偏差、未执行事项与停止状态

- **偏差**：`history` 与 `simulated_decisions` 的关系在指南中固定为“决定事件的决定对象（不含 `decision_sha256`）之规范指纹等于事件记录的 `decision_sha256`”；`request_id` 形式固定为 `"{gate}/{batch_id}/{digest[:24]}"`；本版本 `actor_kind` 仅接受 `SIMULATED_HUMAN`，不提供其他 actor。
- **未执行（不主张通过）**：TASK-010、正式契约（`AUDIT_CONTRACT.md`／`AGENTS.md`）、审批命令、状态机落盘、真实 Gate 放行、人类判断保存、AI 建议、真实批次入口接入（`data/batches`、`batch_manifest`）、UI、文件／数据库字节核验、同权限篡改隔离、压力测试；未重跑任务二至八整套测试。
- **明确声明**：测试重放既有 MAIN 的 checker_report／normalized／load_report 作为历史结果，**只验证控制协议**，不证明真实管道按此顺序执行，也**不为旧开发产物追认真实批准**；`simulated_decisions` 只是可检查的身份声明，不是真实人类认证；本地状态与哈希不等于身份认证。
- **停止状态**：未建立正式契约、未批准任何真实 Gate、未保存／预填人类判断、未生成 AI 建议、未接入 `data/batches`、未修改任何 `batch_manifest.json`；等待主理人把本回执、`docs\WORKFLOW_CONTROL_GUIDE.md` 与 `data\workflow_tests\task009_04` 转交总架构师验收。
