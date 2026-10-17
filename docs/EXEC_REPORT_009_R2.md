# TASK-009-R2 执行回执（补齐事件引用一致性与可重放留痕）

任务：仅完成 TASK-009-R1 复验后尚缺的两项——F01 事件外层引用与集合核对、F04 关键字实参留痕与 helper 自测隔离；F02（错误分类）、F03（严格整数）已由复验关闭，保持不动。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-009-R2.md`、`docs/reviews/REVIEW_TASK_009_R1.md`、`docs/tasks/TASK-009-R1.md`、`docs/WORKFLOW_CONTROL_GUIDE.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进 TASK-010，未建立正式契约，未批准任何真实 Gate，未保存／预填人类判断，未生成 AI 建议。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧 `docs/EXEC_REPORT_009.md` 与 `docs/EXEC_REPORT_009_R1.md`、上游模块、任务卡与验收单、GPT 证据与全部旧容器保持原字节。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **F01 事件引用与集合** | 重放按**事件种类**核验该种类原本生成的字段与权威 `state`／请求／决定一致（创建事件 `gate=null`／`batch_id`／`run_bindings_sha256`；请求事件 `gate` 与 `event_type` 一致且 `request_id`／`materials_sha256`／`run_bindings_sha256` 与已验证请求一致、Gate1 前序为 `null`、Gate2 前序为已验证 Gate1 批准**正文**实际指纹；决定事件 `event_id`／`gate`／`request_id`／`materials_sha256` 与决定正文及当前请求一致），并拒绝该类型不应有的字段；重放结束把 **`state.requests` 实际保存的对象**与重放结果逐项比较（拒绝无 history 事件的额外请求与缺失请求），`simulated_decisions` **按 history 次序**与完整记录逐项一致（不得重排） |
| **F04 可重放留痕** | `_capture` 深拷贝 `call_args` 与 `call_kwargs` 的**值**；probe 记录 `{"function", "args", "kwargs", "restore"}`，**keyword-only 的 `current_bindings` 真实保存**（不从 workflow 旧 bindings 推断），记录形状固定为 `getattr(controller, saved_function)(*restored_args, **restored_kwargs)`；阻断调用明确记录“无返回状态”并附实参 workflow 的 state 调用前后规范指纹；helper 自测改用**显式开关**隔离，不写入主 `checks`／`failures`，单独保存与计数 |
| **留痕验收** | 保存完成后**从保存的 args／kwargs 文件**用公共 API 重放五条绑定变化负向（全部再次得到指向绑定变化的 `WorkflowBlocked`，且与首次结果一致）+ 一条成功调用（完整返回与首次精确相等）；另对全部引用做离线存在性、双指纹与参数完整性（函数签名 `bind()`）核对 |
| **版本** | 控制内核升为 `TASK-009-workflow-control-1.2`；四个公开 API、状态机语义与开发态边界不变 |
| **开发验证** | 入口 API 调用 **272** 次（create 51／prepare 92／record 59／check 70）+ 保存文件重放 **6** 次 = **真实总次数 278**；原探针 **63**、R1 新增 **15**、R2 新增 **8**、流程检查 **14**、helper 自测 **1**（写入主 checks **0**）；**测试失败 0，退出 0**；模拟决定 2 条、**真实人类批准 0 条** |
| **历史保护** | TASK-009-R1 验收基线（13943 项）**变化 3、缺失 0**（恰为本卡授权三个文件）；TASK-009 的 13395、13330、12546、10236、8547、6511、4902、874 基线均 **0 变化、0 缺失** |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\control_demo_workflow.py` | `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c` |
| `D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py` | `09ac1328f52bad00d7e0c7711562f69dfdff1bfb3cf59c9dd5d444fb32347559` |
| `D:\harness work\audit_sa_project\docs\WORKFLOW_CONTROL_GUIDE.md` | `a806a0a1e1b3b6306a949a06bd099e0fb8b7404309765c264e1bde596ca6ab50` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_009_R2.md` | 本文件（新增） |

**未改动**：两份旧回执、任务卡与验收单、上游模块与测试、四份规则 SQL、schema、规格、契约草案、底稿指南、数据库、输入、答案册、GPT 证据与全部旧容器（`task009_04`、`task009_r1_01`—`04` 等均保留）。

新增测试容器（`data\workflow_tests\`）：`task009_r2_04`（**最终**，115 个文件）、`task009_r2_03`／`task009_r2_02`／`task009_r2_01`（修正过程现场）。

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
& $py -B 'D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_tests\task009_r2_04'
```

退出码 **0**；输出：

```text
API 调用（入口）：create 51、prepare 92、record 59、check 70，合计 272；保存文件重放 6 次；真实总次数 278
原探针 63 项、R1 新增 15 项、R2 新增 8 项、流程检查 14 项
helper 自测 1 项（成功 1，写入主 checks 0 项）
保存引用核对 86 条（含关键字实参 86 条）、重放记录 6 条、同步操作 23 次、保存对象 104 份
模拟决定 2 条、真实人类批准 0 条、测试失败 0
受保护文件前后哈希一致: True（19 个）
全部预期成立。
```

### 3.3 其他核验

```powershell
& $py -c "import sys; print(sys.version.split()[0])"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\control_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_control_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\WORKFLOW_CONTROL_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\EXEC_REPORT_009_R1.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与复现核对；未新增临时 `.py` 文件。

---

## 4. 分类计数（按实际 `case`／`kind` 统计）

| 项目 | 数量 |
| --- | --- |
| 入口 API：`create` / `prepare` / `record` / `check` | 51 / 92 / 59 / 70 |
| 入口 API 合计 | **272** |
| 保存文件重放调用 | **6**（五条绑定变化负向 + 一条成功调用） |
| **真实总 API 次数** | **278** |
| 原探针 | **63** 项 |
| R1 新增探针 | **15** 项 |
| R2 新增探针 | **8** 项 |
| 流程检查 | **14** 项 |
| helper 自测 | **1** 项（成功 1；**写入主 `checks`／`failures` 0 项**） |
| 保存引用离线核对 | **86** 条（其中含关键字实参 **86** 条，全部可 `bind()` 重建） |
| 重放记录 | **6** 条 |
| 同步操作 | **23** 次 |
| 保存对象 | **104** 份 |
| 关键 workflow 完整保存 | **5** 个 |
| 主流程模拟决定 / **真实人类批准** | 2 条 / **0 条** |
| 测试失败 | **0** |

**计数修正说明（如实解释，不改旧回执）**：上一轮回执中的“原探针 64”把 helper 自测一并计入。本轮按要求用显式开关隔离后，原探针为 **63**、helper 自测为 **1** 且不写入主 `checks`；R2 新增 8 项独立计数。

## 5. F01 八项复现探针的实际结果

| 探针 | 唯一变更 | 实际阻断原因（节选） |
| --- | --- | --- |
| R2_Q01 | 决定事件顶层 `event_id = OTHER-EVENT-ID`（正文保持真实） | `state.history[2].event_id 事件顶层 event_id 必须与决定正文一致：'OTHER-EVENT-ID' != 'EVT-Q-G1'` |
| R2_Q02 | 同事件 `gate = GATE2` | `state.history[2].gate 必须与 event_type 所指的 GATE1 一致，实际 'GATE2'` |
| R2_Q03 | 同事件 `request_id = OTHER-REQUEST` | `state.history[2].request_id 必须与对应已验证请求一致` |
| R2_Q04 | 同事件 `materials_sha256 = 0…0` | `state.history[2].materials_sha256 必须与对应已验证请求的材料指纹一致` |
| R2_Q05 | 创建事件 `batch_id = OTHER-BATCH` | `state.history[0].batch_id 必须与 state.batch_id 一致：'OTHER-BATCH' != 'BATCH-2026-09-DEMO-001'` |
| R2_Q06 | Gate1 请求事件 `run_bindings_sha256 = 0…0` | `state.history[1].run_bindings_sha256 必须与对应已验证请求的运行绑定指纹一致` |
| R2_Q07 | 放入同批次形状合法的 Gate2 请求但不添加 history 事件 | `state.requests.GATE2 必须与 history 重放结果一一对应：不得存在无 history 事件的额外请求或缺少实际请求` |
| R2_Q08 | 反转 `simulated_decisions` 顺序（ID 集合不变） | `state.simulated_decisions[0] 必须按 history 次序与决定事件记录的完整记录逐项一致（不得重排）` |

八项均只改单个引用字段（或新增整个请求／改变列表顺序）并**仅同步新内存对象的外层 `state_sha256`**；未顺手修改决定正文、请求或相关指纹来消除矛盾。同步说明记录于 `sync_operations.json`（共 23 条），变更路径与完整调用记录于 `checks.json`。

## 6. F04 可重放留痕与 helper 隔离

- **kwargs 真实保存**：`_capture` 深拷贝 `call_kwargs` 的值；probe 记录 `{"function", "args", "kwargs", "restore"}`。`current_bindings` 是 keyword-only 参数，保存在 `kwargs.current_bindings`（内容寻址对象）中，**未**从 workflow 内的旧 `run_bindings` 推断。86 条含关键字实参的记录全部通过 `inspect.signature(...).bind()` 参数完整性核对。
- **对象指纹**：每个引用同时给出 `object_sha256`（规范 JSON 指纹，即文件名）与 `file_sha256`（落盘字节指纹）；离线核对两者都校验，104 份对象全部可解析且内容未被改写；`object_index.json` 汇总标签与两个指纹。
- **阻断调用**：记录 `returned_state: null` 与说明，并附实参 workflow 的 state 在调用前后的规范指纹（`input_workflow_unchanged: true`），**不把 null 当成输入丢失**。
- **保存文件重放**：从保存的 args／kwargs 重新加载后调用公共 API——
  - 五条绑定变化负向（`S6_binding_change_input`／`code`／`rule_sql`／`config`／`contract`）全部再次得到 `WorkflowBlocked`，原因指向绑定变化，且**与首次结果完全一致**（分类与消息相同），实参指纹前后不变；
  - 一条成功调用（`S1_normalize_before_gate1_approval`）重放后的**完整返回与首次结果精确相等**；
  - 结果保存于 `replay_records.json`（含恢复的函数与参数引用、分类／原因、是否与首次一致、实参前后指纹）。
- **helper 自测隔离**：改用显式 `self_test=True` 开关，自测结果**不写入主 `checks`／`failures`**（`in_main_checks: false`），单独保存于 `helper_self_tests.json` 并单独计数；其真实 API 调用仍计入总次数，但**不充当**原探针。

## 7. 原有回归保持

MAIN 完整两 Gate 流程、四停止态与非法决定、越级／重复／未知、守门材料失败、缺失应付关联非零仍可形成 Gate2 请求、绑定变化与跨 workflow 复用、workflow 篡改、确定性／入参不变／历史完整／不可信文字、静态与运行期隔离，以及 TASK-009-R1 的全部内容（历史决定协议与双指纹、错误分类、严格整数、单行小样、确定性 `request_id`、材料协议复核、五个关键 workflow 序列化往返）——原 **63** 项探针、R1 **15** 项探针与全部流程检查保留且通过，未删除或放宽。真实批准数仍为 **0**。

## 8. 失败尝试与修正过程

1. **对象文件字节与规范指纹口径不符**：`save_object` 以可读缩进写盘、却以规范 JSON 计算指纹，导致离线核对报“内容指纹不符” → 增加 `file_sha256`（落盘字节）并与 `object_sha256`（规范内容）**同时**校验，既保持可读又保证可校验。
2. **“实参未被修改”判定口径错位**：原先用整个 workflow 的规范指纹与 `state_sha256`（仅 state）比较 → 必然不等，导致全部阻断探针误报 → 改为比较实参 workflow 的 **state 内容**在调用前后的规范指纹。
3. **伪造外层指纹用例的误报**：`S7_outer_fingerprint_forged` 本就故意把外层 `state_sha256` 写成假值，用声明值比较必然不等 → 同上改为比较 state **内容**指纹，该用例恢复为 PASS。
4. **静态检查与 helper 清理**（R1 已修，本轮复核）：静态依赖改为 AST 导入白名单 + 具体 API 模式；helper 自测改为显式开关而非依赖字典相等删除包装对象。

未通过放宽断言、删除既有负向、跳过检查或修改上游数据让用例通过。

## 9. 历史保护对照

- TASK-009-R1 验收基线（`data/reviews/task009_r1_20261011_095041/source_hashes_after.json`）：记录项 **13943**、变化 **3**（`scripts\control_demo_workflow.py`、`tests\test_control_demo_workflow.py`、`docs\WORKFLOW_CONTROL_GUIDE.md`）、缺失 **0**。
- TASK-009 的 **13395**、TASK-008-R1 的 **13330**、TASK-007-R2 的 **12546**、任务六 R1 的 **10236**、任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 **0 变化、0 缺失**。
- 测试内建核验的 **19 个受保护文件**前后哈希一致；旧容器与 GPT 证据逐文件未变。
- 依赖未变（Python 3.11.1、SQLite 3.39.4 等）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 10. 偏差、未执行事项与停止状态

- **偏差**：事件按类型核验字段集（不属于该类型的字段一律拒绝）；`state.requests` 与重放结果逐项比较、`simulated_decisions` 按 history 次序逐项比较；留痕记录新增 `kwargs`／`restore`／`file_sha256`／`input_workflow_unchanged`；helper 自测改用显式开关隔离。
- **未执行（不主张通过）**：TASK-010、正式契约、审批命令、状态机落盘、真实 Gate 放行、人类判断保存、AI 建议、真实批次入口接入、UI、文件／数据库字节核验、压力测试、无边界 fuzz；未重跑任务二至八整套测试。
- **明确声明**：internal 引用核验只是**既有协议在重放入口的一致应用**，用于发现自相矛盾的内存对象，**不是**身份认证，也**不抵御**能重写整个对象与全部哈希的同权限篡改；同步派生指纹只为让对象自相一致以进入语义核验，不代表其通过真实上游重新计算；`simulated_decisions` 不是真实人类批准。
- **停止状态**：未建立正式契约、未批准任何真实 Gate、未保存／预填人类判断、未生成 AI 建议、未接入 `data/batches`、未修改任何 `batch_manifest.json`；等待主理人把本回执、`docs\WORKFLOW_CONTROL_GUIDE.md` 与 `data\workflow_tests\task009_r2_04` 转交总架构师复验。
