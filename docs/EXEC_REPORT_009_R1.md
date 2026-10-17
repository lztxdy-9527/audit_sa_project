# TASK-009-R1 执行回执（补齐历史状态契约校验与验证留痕）

任务：修复 TASK-009 复验发现的四项缺口——F01 历史决定重放未完整验证决定协议与所有消费指纹、F02 缺字段／错类型的 workflow 被归为意外运行失败、F03 计数与序号接受数值等价的错误类型、F04 负向原因断言与完整留痕不足。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-009-R1.md`、`docs/reviews/REVIEW_TASK_009.md`、`docs/tasks/TASK-009_DRAFT.md`、`docs/WORKFLOW_CONTROL_GUIDE.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进 TASK-010，未建立正式契约，未批准任何真实 Gate，未保存／预填人类判断，未生成 AI 建议。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧 `docs/EXEC_REPORT_009.md`、上游模块、指南以外的文档与全部历史产物保持原字节。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **F01 历史协议与指纹** | 抽出可复用的 `_check_decision_fields()`，**首次 record 与 replay 共用同一套**必需键／枚举／类型／时间／身份／模拟标志／说明／确认项约束；重放时先**剥离派生字段 `decision_sha256`** 得到决定正文，核对**决定内与事件顶层两个指纹都等于正文实际规范指纹**，核对 `history` 与 `simulated_decisions` 两处记录严格一致，并重新校验 `event_id`／gate／request_id／材料指纹／批次与绑定引用；请求重放重新核验材料内容指纹、按原公式**重算 `request_id`**、重新执行 `prepare` 的材料协议，且 `requests` 不得有 history 未出现的额外请求、决定集合与 history 逐项一致；Gate2 只绑定**本 workflow 已验证 Gate1 APPROVE 正文的实际指纹** |
| **F02 错误分类** | 新增前置形状校验（`_check_request_shape`／history 与 `simulated_decisions` 条目校验）：先检容器、条目、必需键、类型与枚举再访问；协议坏输入给 `WorkflowBlocked` 并指出完整路径，不再退化为 `KeyError`／`AttributeError` → `WorkflowError`；真正的意外错误仍为 `WorkflowError` 且保留异常链 |
| **F03 严格整数** | `history.seq` 与 Gate2 四表 `row_counts` 先验**整数且非 `bool`／非浮点**（`row_counts` 还要求非负）再比数值；保存观察到的原类型，不做 `int()` 转换、不补零。`1`／`20` 可用，`true`／`1.0`／`20.0` 一律阻断；金额与确认项的原有严格检查保持 |
| **F04 断言与留痕** | 断言 helper 改为「异常类别**且**指定原因条件」同时满足才 PASS；新增 helper 自测证明「类别正确但原因不含指定标识」会被判为断言失败（该自测**不计入**最终失败数）；新增探针均核对目标字段路径；全部探针保存**完整实参**（workflow／`current_bindings`／decision／materials／action 的实际调用参数）、**完整返回值**或异常类别与消息、预期／实际、调用前后 `state_sha256` 及同步操作说明；五个关键 workflow 保存**完整 `{state, state_sha256}`** |
| **版本** | 控制内核升为 `TASK-009-workflow-control-1.1`；四个公开 API、纯内存边界与状态机语义不变 |
| **开发验证** | 真实 API 调用 **234** 次（create 42／prepare 81／record 49／check 62）；原探针 **64** 项、R1 新增探针 **15** 项、流程检查 **12** 项、helper 自测 **1** 项（通过）；**测试失败 0，退出 0**；模拟决定 2 条、**真实人类批准 0 条**；同步操作 15 次、保存对象 89 份 |
| **历史保护** | TASK-009 验收基线（13395 项）**变化 3、缺失 0**（恰为本卡授权三个文件）；TASK-008-R1 的 13330、12546、10236、8547、6511、4902、874 基线均 **0 变化、0 缺失** |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\control_demo_workflow.py` | `4230d2b0dca68032aeb69411adb5258fe55c663793a6ef780408995adb71821f` |
| `D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py` | `614d9903e32d7f2fa833427300b58d59cf2b979a430165b5cb65f7c09eee7e4f` |
| `D:\harness work\audit_sa_project\docs\WORKFLOW_CONTROL_GUIDE.md` | `0c5d196cafeb2011080516797cc876a08acf797034c62fa9236d5ba73952d93e` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_009_R1.md` | 本文件（新增） |

**未改动**：旧 `docs/EXEC_REPORT_009.md`、任务卡与验收单、上游模块与测试、四份规则 SQL、schema、规格、契约草案、底稿指南（含其非阻断文案记录）、数据库、输入、答案册、GPT 证据。

新增测试容器（`data\workflow_tests\`）：`task009_r1_04`（**最终**，99 个文件）、`task009_r1_03`／`task009_r1_02`／`task009_r1_01`（修正过程现场）。`task009_04` 等旧容器未覆盖。

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
& $py -B 'D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_tests\task009_r1_04'
```

退出码 **0**；输出：

```text
API 调用：create 42、prepare 81、record 49、check 62，合计 234
原探针 64 项、R1 新增探针 15 项、流程检查 12 项、helper 自测 1 项（成功 1）
模拟决定 2 条、真实人类批准 0 条、同步操作 15 次、保存对象 89 份、测试失败 0
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
Get-FileHash 'D:\harness work\audit_sa_project\docs\EXEC_REPORT_009.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结构化核对；未新增临时 `.py` 文件。

---

## 4. 分类计数（按真实执行，不虚报）

| 项目 | 数量 |
| --- | --- |
| `create_dev_workflow` / `prepare_dev_gate` / `record_dev_decision` / `check_dev_action` | 42 / 81 / 49 / 62 |
| API 调用合计 | **234** |
| 原探针（TASK-009 保留） | **64** 项 |
| R1 新增探针 | **15** 项 |
| 流程检查 | **12** 项 |
| helper 断言自测 | **1** 项（结果符合预期：类别正确但原因不符 → 判失败） |
| 同步操作（派生指纹） | **15** 次（记录于 `sync_operations.json`） |
| 保存对象（内容寻址） | **89** 份 |
| 关键 workflow 完整保存 | **5** 个（`key_workflows.json` + `objects/`） |
| 主流程模拟决定 | **2** 条 |
| **真实人类批准** | **0** 条（真实 `gate1_approval`／`gate2_approval` 恒为 `null`） |
| 守卫受控探测 / 守卫内正常调用 | 1 次 / 3 次（分开统计） |
| 测试失败 | **0** |

## 5. F01 十项复现探针的实际结果（全部按目标字段路径阻断）

| 探针 | 注入（同步新内存对象的派生指纹后） | 实际阻断原因（节选） |
| --- | --- | --- |
| R1_P01 | 已记录 Gate1 决定的内嵌 `decision_sha256` 改全零（两处存放位置），事件顶层保持真值 | `state.history[2].decision.decision_sha256 必须等于决定正文（不含该派生字段）的实际规范指纹` |
| R1_P02 | 用同一错误对象 `prepare` Gate2 | 同上（Gate2 请求建立前即被拦下） |
| R1_P03 | 历史决定 `actor_kind = AI` | `state.history[2].decision.actor_kind 必须是 SIMULATED_HUMAN` |
| R1_P04 | 历史 APPROVE 确认项 `scope_and_source_reviewed = false` | `...confirmations.scope_and_source_reviewed 确认项...必须严格为 true` |
| R1_P05 | 历史决定缺 `reason` | `state.simulated_decisions[0].reason 缺少必需键` |
| R1_P06 | 历史 `simulation = REAL` | `state.history[2].decision.simulation 必须固定标记 SIMULATED_TEST_ONLY` |
| R1_P07 | 待决定请求缺 `request_id` | `state.requests.GATE1.request_id 缺少必需键`（**WorkflowBlocked**，非 WorkflowError） |
| R1_P08 | `simulated_decisions` 条目为整数 `1` | `state.simulated_decisions[0] 条目必须是对象，实际 int`（**WorkflowBlocked**） |
| R1_P09 | MAIN `row_counts.suppliers = 20.0` | `...row_counts.suppliers 必须是非负整数（不接受 bool／浮点等数值等价类型），实际 float=20.0` |
| R1_P10 | 首事件 `seq = true` | `state.history[0].seq 必须是从 1 递增的连续序号…实际 bool=True` |

补充针对性检查与边界：

- `R1_history_seq_float_equivalent`：`seq = 1.0`（数值等价、类型错误）→ 阻断。
- `R1_request_id_not_deterministic`：只改 `request_id` 及其事件引用、材料不变 → 「必须等于按原公式重算的确定性请求 ID：`GATE1/BATCH-2026-09-DEMO-001/…`」。
- `R1_request_materials_protocol_violated`：改请求材料的质量结果为 `issues_found` 并**同步材料指纹与确定性 `request_id`** → 「`materials.evidence.quality_report.result 必须严格为 pass`」（进入材料协议核验，而非指纹先行拦截）。
- `R1_single_row_count_one_legal`：合法单行小样 `data/sqlite_tests/task007_r2_gpt_20261011_081630/cases/C02`（当前冻结装载器 `TASK-005-sqlite-load-1.2`，`payables` 记录数确为 **1**）→ Gate2 请求正常建立（`ok`）。
- `R1_single_row_count_true_illegal`：同小样 `row_counts.payables = true` → 阻断。
- `R1_ROUNDTRIP_KEY_WORKFLOWS`：两 Gate 正常流程的五个关键 workflow 经 JSON 序列化往返后仍可用；`03_gate1_approved` 仅允许模拟标准化、`05_gate2_approved` 仅允许模拟筛查、其余阶段与 AI 建议始终被拒、`next_step_allowed` 恒为 false、真实批准 0。

## 6. F02／F03 的行为变化

- 之前：`request` 缺 `request_id` → `KeyError` → `WorkflowError`；`simulated_decisions` 条目为整数 → `AttributeError` → `WorkflowError`。现在两者都是带完整路径的 `WorkflowBlocked`，且**没有**用 `except Exception` 把真正的程序错误改判为阻断（`WorkflowError` 分支与异常链保留）。
- 之前：`row_counts.suppliers = 20.0` 与 `history.seq = true` 因 Python 数值相等被接受。现在先验整数类型与非负性／正性，再验连续序号；观察到的原类型写入原因文本。
- 金额（整数分、非 `bool`）与确认项（严格 `true`）的原有严格检查保持不变；新增的整数检查不放松任何既有约束。

## 7. F04 断言自测与留痕

- **helper 自测**（`helper_self_tests.json`）：给断言 helper 一个「预期 `WorkflowBlocked`、但原因不含指定 sentinel」的调用，`category_ok=true`、`reason_ok=false`、helper 返回 `ok=false` → 符合预期；该自测从正式检查与失败列表中移除后单独统计，**不计入**最终测试失败数。
- **完整留痕**：每次探针记录调用函数、**完整实参**（内容寻址对象引用）、**完整返回值**或异常类别与消息（含 `reasons`）、预期与实际、`category_ok`／`reason_ok`、调用前后 `state_sha256`，以及该次调用前的**同步操作说明**（`sync_operations.json` 15 条，含字段路径与方法）。
- **完整 workflow**：`key_workflows.json` 指向五个关键 workflow 的**完整 `{state, state_sha256}`**（含 `requests`、`run_bindings`、`history`、`simulated_decisions`），可据此重建调用；`final_state.json` 保存本次主流程最终 workflow 的全部内容（约 13.9 MB）。
- 内容寻址对象目录 `objects/`（89 份）+ `object_index.json` 保证引用文件真实存在且可还原内容，**只保存哈希摘要**的做法已不再使用。

## 8. 原有回归保持

MAIN 完整两 Gate 流程、四停止态与非法决定、越级／重复／未知、守门材料失败、缺失应付关联非零仍可形成 Gate2 请求、绑定变化与跨 workflow 复用、workflow 篡改、确定性／入参不变／历史完整／不可信文字、静态与运行期隔离——原 **64** 项探针与 **9** 组流程全部保留且通过，未删除或放宽；新增 **15** 项探针与 **3** 组流程检查独立计数。真实批准数仍为 **0**。

## 9. 失败尝试与修正过程

1. **Gate2 前序指纹取用错误（核心）**：把决定指纹改为由「决定正文」计算后，`prepare_dev_gate` 仍读 `approved["decision_sha256"]`（正文已剥离该派生字段）→ `KeyError` → `WorkflowError`；由原回归捕获并改为 `canonical_sha256(approved)`（正文实际指纹）。
2. **两处存放位置的别名问题（核心）**：先前 `history` 与 `simulated_decisions` 指向同一对象，导致「两处分别改」的语义不成立、严格一致检查失去意义 → 改为保存独立深拷贝。
3. **C02 小样版本不符**：`task005_02/cases/C02` 的装载器版本是 `TASK-005-sqlite-load-1.0`，不满足 Gate2 材料协议（且不能修改旧证据）→ 改用**当前冻结装载器 1.2** 的 GPT 验收容器 `task007_r2_gpt_20261011_081630/cases/C02`（先确认其 `payables` 记录数为 1）。
4. **helper 自测失败泄漏到正式失败数（测试）**：`probe` 往 `checks` 与 `failures` 写入了两个不同对象，移除时只删掉一个 → 改为两个列表引用同一对象后再移除；自测项单独统计。
5. **单行小样的正／负用例互相影响（测试）**：合法 `prepare` 已把状态推进到 `GATE2_PENDING`，随后的非法 `prepare` 会先被阶段检查拦下而到不了 `row_counts` 检查 → 改为从同一个 `DEV_GATE1_APPROVED` 基线各自独立调用。

未通过放宽断言、删除既有负向、跳过检查或修改上游数据让用例通过。

## 10. 历史保护对照

- TASK-009 验收基线（`data/reviews/task009_20261011_092842/source_hashes_after.json`）：记录项 **13395**、变化 **3**（`scripts\control_demo_workflow.py`、`tests\test_control_demo_workflow.py`、`docs\WORKFLOW_CONTROL_GUIDE.md`）、缺失 **0**。
- TASK-008-R1 的 **13330**、TASK-007-R2 的 **12546**、任务六 R1 的 **10236**、任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 **0 变化、0 缺失**。
- 测试内建核验的 **19 个受保护文件**前后哈希一致；旧容器与 GPT 证据逐文件未变。
- 依赖未变（Python 3.11.1、SQLite 3.39.4 等）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 11. 偏差、未执行事项与停止状态

- **偏差**：`decision_sha256` 的口径固定为「决定正文（不含该字段）的规范指纹」，并同时存放于决定记录与事件顶层；`history.seq`／`row_counts` 要求严格整数（非 `bool`／非浮点）；`simulated_decisions` 与 `history` 保存**独立副本**并逐项一致。
- **未执行（不主张通过）**：TASK-010、正式契约、审批命令、状态机落盘、真实 Gate 放行、人类判断保存、AI 建议、真实批次入口接入、UI、文件／数据库字节核验、压力测试；未重跑任务二至八整套测试。
- **明确声明**：本次重放既有开发结果**只验证控制协议**，不证明真实管道按此顺序执行，也不为旧产物追认真实批准；同步派生指纹只为让内存对象自相一致以进入语义核验，**不代表**其通过真实上游重新计算，也**不是**安全隔离或防恶意篡改测试；`simulated_decisions` 不是真实人类认证。
- **停止状态**：未建立正式契约、未批准任何真实 Gate、未保存／预填人类判断、未生成 AI 建议、未接入 `data/batches`、未修改任何 `batch_manifest.json`；等待主理人把本回执、`docs\WORKFLOW_CONTROL_GUIDE.md` 与 `data\workflow_tests\task009_r1_04` 转交总架构师复验。
