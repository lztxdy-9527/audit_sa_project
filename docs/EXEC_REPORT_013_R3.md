# TASK-013-R3 执行回执（只修测试证据：末次读取探针 / after 时点与完整调用记录 / 七阶段完整判定）

任务：关闭 TASK-013-R2 复验剩余三组**测试证据**缺口——F01 三个“最后一次读取”回归实际在第一次读取注入、F02 after 时点与调用现场不完整、F03 七阶段批准与动作未按协议完整验收。
日期：2026-10-12。执行端：DeepSeek。验收端：GPT。
依据：`docs/tasks/TASK-013-R3.md`（唯一权威细则）、`docs/reviews/REVIEW_TASK_013_R2.md`、`docs/EXEC_REPORT_013_R2.md`、`docs/WORKFLOW_HOST_GUIDE.md`。
状态：完成并自检通过，**宿主与指南冻结未改**，停在 `DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED`（0005）；未新增 0006，未执行独立复算／事实底稿／AI／人类判断，未提交真实 Gate 或正式契约，未推进 TASK-014。

---

## 1. 结论摘要

| 缺口 | 本轮处置与证据 |
| --- | --- |
| **F01 注入时点偏早** | 三个探针改为：先用**只读计数运行**（同一 `io.open` 观察器，不注入）确定该目标文件在本次调用里的真实读取序列与**最后一次内容消费读取**的序号，再在同一次真实调用里**只在该次读取返回原始对象之后**改磁盘一次。交付记录实测：报告注入于第 3 次读取之后（4 次读取中的最后一次 `_read_screen_outputs`）、load_report 注入于第 5 次（6 次读取中最后一次内容消费，其后还有 1 次守卫复测）、0001 注入于第 1 次（该文件在恢复链里只被消费一次）。三项均**命中 1 次**、`outcome=blocked`（本次调用内 `WorkflowHostBlocked`）、撤销 wrapper 后新进程 CLI 退出 1、恢复原件后退出 0；报告项改 `findings` 内容且保留可解析 JSON，其余两项只加换行。 |
| **F01 时点判定自测** | 新增纯内存判定 `probe_timing_verdict`：注入必须落在**最后一次内容消费读取**返回之后，其后不得再有内容消费读取或控制器调用（只比较字节的守卫读取单列）。自测 6 例单列于 `self_tests.json`（合格轨迹／缺注入／注入早于消费边界／注入后仍有两次内容消费／注入后仍有控制器调用／注入后守卫读取允许），实测 6/6 与期望一致，`ok=true`，**不并入正式 failures**。 |
| **F02 after 时点** | 六个新探针与旧三项统一改为：调用前保存原始字节与 before 文件/目录哈希 → 调用结束且 wrapper 撤销后、**恢复原件之前**保存 after 文件/目录哈希 → 逐项断言 `after.file == after.tree` 中同一文件哈希、before/after 目标哈希不同；恢复后的集合单独保存（`restored_evidence`），撤销后 CLI 与恢复后正向另列。实测 6/6 `ok=true`、`after.file_equals_tree=true`、`restored.tree_equals_before=true`。 |
| **F02 完整调用记录** | 三项新 F01/F02 探针与既有 `g6_tail_0005_change`、`g6_f01_report_tail_change` 均补齐：公开入口名、完整 `args`/`kwargs`/`batch_dir`、预期类别与目标原因、完整返回或**完整异常**（类别／未截断消息／stage／reasons／cause 链／逐帧 traceback）、命中数、真实调用顺序（含 `check_dev_action` 每次完整实参与返回）、真实 before/after、撤销后 CLI 与成功对照。大对象（完整返回、完整目录哈希集合、完整事件轨迹）独立落盘并给相对路径与实际字节 SHA-256。 |
| **F02 早期守卫命名** | 原 `_verify_screen_tail` 探针保留原断言与故障方向，改名为 `kind=early_guard` 并写明“第一次 `_verify_screen_tail` 返回后注入、不能替代末次读取探针”；筛查失败现场 `failure.json` 保留未删，成功对照使用新干净小样。 |
| **F03 七阶段完整判定** | 七阶段全部改用 C06b 小样；每阶段保存实际 API 返回与 CLI 返回（含未截断消息）、调用实参、`check_dev_action` 本次调用记录、before/after 目录哈希集合（文件引用＋实际字节哈希）。两项真实批准从**实际 `current_checkpoint` 的 `workflow.state.gate1_approval/gate2_approval`** 读出，实测 7/7 均为 `None`（不再用顶层 `n/a`）。API 与 CLI 双侧断言 phase、`next_step_allowed=false`、六种动作允许值（Gate1 pending false/false；Gate1 approved true/false；Gate2 pending false/false；Gate2 approved false/true；Gate2 held 与 rejected false/false；screened false/true）与只读性；screened 另有 `RULE_SCREEN_RECORDED` 与 `0005/RUN_RULE_SCREEN` 凭证且 phase 仍 `DEV_GATE2_APPROVED`。7/7 `ok=true`。 |
| **计数** | 本组新增计数从入口事件与实际调用记录导出：公开 API 19（均为 `inspect_dev_batch`）、控制器 162（`check_dev_action` 113／`prepare_dev_gate` 16／`record_dev_decision` 33）、CLI 98（start 16、status 25、record 15、prepare 14、record-gate2 13、screen 10）、进程内筛查核心 0、进程内 normalize/load 0（显式记 0），CLI 子进程内核心次数不可观测记 `null` 并另列推导值 24。 |
| **开发验证** | 全新容器 `task013r3_run_03` 完整入口**退出 0、11 项检查全 PASS、failures=[]**（含新增 `G10_R3_...`），`FINAL_ARTIFACT_READBACK` 独立单列 `ok=true`。 |

---

## 2. 修改文件与产物路径

| 文件 | SHA-256 | 说明 |
| --- | --- | --- |
| `tests\test_screen_demo_workflow.py` | `fb018aa9dbea598563ccc91edb1d75bbd6b4a9525c8556daa2513560f2eb1998` | 本轮**唯一修改的既有文件**（起点 `e7851240…756e3`） |
| `scripts\run_demo_workflow.py` | `ae5b7e24dd946a0a2186b8741b79af4173e091c362c4c210d8186e92d2cab4e2` | **冻结未改**（TASK-013-workflow-host-1.2） |
| `docs\WORKFLOW_HOST_GUIDE.md` | `c7963c5857580ae9f3d75e0b6c9e9d448f988b5c561745df63f60b1a92060cf5` | **冻结未改** |
| `docs\EXEC_REPORT_013_R3.md` | `c8d16e0e5593b56e19ffa7df10792ce81e86e586bc6a40a65e465ade420a4eb1`（写卡时的文件字节哈希） | 本轮回执 |

三条完整产物路径（本轮最终验证容器）：

- 测试容器 `D:\harness work\audit_sa_project\data\workflow_host_tests\task013r3_run_03`（663 文件；`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`entry_events.json`／`self_tests.json`／`final_readback.json`／`r3_g10_counts.json`／`probe_records\` 34 份完整记录）
- 批次父目录 `D:\harness work\audit_sa_project\data\batches\task013r3_run_03`（841 文件；**29 份 `0005`、0 份 `0006`**）
- 外置数据库父目录 `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task013r3_run_03`（35 文件）

关键取证文件（均在容器内，相对路径 + 实际字节哈希可由 `probe_records` 复核）：

- 三项末次读取探针：`probe_records\r3_f01_report_last_read.json`、`probe_records\r3_f01_load_report_last_read.json`、`probe_records\r3_f01_0001_last_read.json`（另有三份只读计数运行 `r3_f01_<目标>_read_calls.json`，保存该目标的完整读取序列与每帧栈尾）
- 六项 F02 探针：`probe_records\r3_f02_p0{1..6}_*_tail_after_last_read.json`
- 七阶段完整判定：`probe_records\r3_stage_<阶段>_full.json`（7 份）与汇总 `probe_records\r3_f01_f03_stage_summary.json`
- MAIN 报告 `…\data\batches\task013r3_run_03\main_01\workflow\screening\screening_report.json`；MAIN 凭证 `…\workflow\checkpoints\0005.json`
- 过程现场（保留未回写）：`task013r3_smoke`—`task013r3_smoke56`（定向小样，其中 smoke54 起 G10-R3 全绿）、`task013r3_run_01`／`task013r3_run_02`（完整入口过程现场，run_02 存在一项**仅记录字段**的 `ok` 标错，见 §7）

---

## 3. 实际命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0（冻结文件只做语法自检，未改）
& $py -B -c "src = open(r'...\tests\test_screen_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_screen_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task013r3_smoke56' --only-g10   # 0（定向小样：G10-R3 全绿）
& $py -B '...\tests\test_screen_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task013r3_run_03'              # 0（全新容器最终完整入口）
```

输出要点：`测试失败 0；受保护文件前后一致: True`、`全部预期成立。`。检查项 **11**：G1 MAIN、G2 小样、G3 阶段与重复、G4 报告与引用篡改、G5 真实失败、G6 最终复测尾探针、G7 只读与隔离、G9 R1 协议回归、**G10_R3 七阶段／末次读取／after 时点与完整调用记录**、G8 计数审计与证据、INTEGRITY 保护核对（`FINAL_ARTIFACT_READBACK` 以 `final_readback.json` 独立单列，持久化检查 11 条 + 保护核对，`ok=true`）。

---

## 4. F01 三个末次读取探针（本轮实测）

| 目标 | 只读计数运行的读取序列 | 注入点 | 命中 | 本次调用结果 | 撤销后 CLI | 恢复后 CLI |
| --- | --- | --- | --- | --- | --- | --- |
| `workflow/screening/screening_report.json` | 4 次读取：内容(1) → 守卫(2) → 内容(3) → 守卫(4) | 第 3 次（最后一次内容消费） | 1 | `WorkflowHostBlocked`（字段 `workflow/screening/screening_report.json`：本次 status 摘要消费的文件字节与 0005 初始声明不一致） | 1 | 0 |
| `workflow/gate2/load_report.json` | 6 次读取：内容(1) 守卫(2) 内容(3) 守卫(4) 内容(5) 守卫(6) | 第 5 次（最后一次内容消费，其后 1 次守卫复测） | 1 | `WorkflowHostBlocked`（字段 `workflow/gate2/load_report.json`：Gate2 材料在筛查恢复时发生了变化） | 1 | 0 |
| `workflow/checkpoints/0001.json` | 1 次内容读取（恢复链开头），其后均为守卫/链引用核验 | 第 1 次（该文件唯一消费点） | 1 | `WorkflowHostBlocked`（字段 `workflow/checkpoints/0003.json.previous_file_sha256`：链上前序引用不再成立——0001 字节已变） | 1 | 0 |

- 三项均断言：`hits==1`、注入落在只读计数运行确定的消费边界上、注入后**无内容消费读取**（load_report 另有 1 次守卫读取，单列）、注入后**无控制器调用**、after 时点文件哈希 == 同一次 after 目录集合中该文件哈希、before≠after、恢复后目录哈希集合等于调用前。
- 报告项造样为 `findings` 内容改写（保留可解析 JSON，实测注入后 `findings` 仍为列表且首条带标记），load_report／0001 只加换行字节。
- 0001 的证据细节（诚实标注）：该 checkpoint 在本次调用里**只被消费一次**，因此本探针的注入点就是这唯一一次；宿主紧随其后的链核验给出的原因字段是**后继 checkpoint 的 `previous_file_sha256`**（`0003.json`），而不是 `0001.json` 自身字段。这是该目标的读取位置决定的可接受检测点，已在记录的 `timing_verdict`／`inject` 字段与本节如实标注；它仍满足“在真实消费边界之后注入、本次调用内被拒绝、撤销后仍拒绝、恢复后通过”。
- 另有三份只读计数运行记录 `r3_f01_<目标>_read_calls.json`，保存该目标的完整读取序列（序号／内容或守卫／每次读取栈尾）与 `injection_read_seq`。

---

## 5. F02 after 时点与完整调用记录（本轮实测）

六项探针（改为“公开调用之前完成造样与引用同步”，使失败落在目标字段的语义核验上）：

| 探针 | 造样改动 | 本次调用结果（目标字段） | after==tree | 保留现场 CLI | 恢复后 CLI |
| --- | --- | --- | --- | --- | --- |
| `r3_f02_p01_report_relative` | `0005.operation.report_relative` → 非固定相对路径 | `0005.json.operation.report_relative` 不可用 | ✓ | 1 | 0 |
| `r3_f02_p02_manifest_bindings` | `artifacts.host_manifest_file_sha256` → bindings 内容指纹（同步文件引用） | `screening/artifacts.json.host_manifest_file_sha256` 不可用 | ✓ | 1 | 0 |
| `r3_f02_p03_artifacts_version` | `artifacts.host_version` → `WRONG-HOST-VERSION` | `screening/artifacts.json.host_version` 不可用 | ✓ | 1 | 0 |
| `r3_f02_p04_started_version` | `started.host_version` → `WRONG-HOST-VERSION`（同步 artifacts/0005 引用） | `screening/started.json.host_version` 不可用 | ✓ | 1 | 0 |
| `r3_f02_p05_embedded_cutoff` | `0005.operation.artifacts.cutoff_date` → 1900-01-01 | `0005.json.operation.artifacts` 内嵌副本与磁盘不一致 | ✓ | 1 | 0 |
| `r3_f02_p06_embedded_shape` | `0005.operation.artifacts` → 字符串 | `0005.json.operation.artifacts` 必须是对象 | ✓ | 1 | 0 |

每项记录包含：公开入口 `host.inspect_dev_batch`、完整实参与 `batch_dir`、预期类别与目标原因、完整异常（含逐帧 traceback 与未截断消息）、命中数、真实调用顺序、真实 before/after 目录哈希集合（引用独立文件 + 实际字节 SHA-256）、撤销后 CLI 与恢复后正向、`changed_files` 与逐文件 before/after 哈希。

**G6 两项旧记录补齐**（均在容器 `probe_records\`）：

- `g6_tail_0005_change`：填入公开入口 `host.screen_dev_batch`、`check_dev_action` 每次完整实参（动作名、`kwargs` 键、workflow `state_sha256`／phase／batch_id）与其返回、`hits`、完整异常现场、撤销后 CLI（保留改动现场仍拒绝）与恢复口径说明。
- `g6_f01_report_tail_change`：明确标注 `kind=early_guard`（第一次 `_verify_screen_tail` 返回后注入）+ 守卫说明、公开入口与实参、完整异常现场与调用顺序，并声明**不能替代** `r3_f01_report_last_read`。

---

## 6. F03 七阶段完整判定（本轮实测）

工作簿：`data\generated\demo_20260930_a\fixtures\C06b.xlsx`（SHA-256 `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`）。

| 阶段 | 实际 phase（API / CLI） | CLI 退出 | `NORMALIZE_AND_LOAD` / `SCREEN_AND_BUILD_FACTS` | 真实批准（来自当前 checkpoint `workflow.state`） | 只读（before==after×2） |
| --- | --- | --- | --- | --- | --- |
| gate1_pending（0001） | `DEV_GATE1_PENDING` / 同 | 0 | false / false | `gate1_approval=null`、`gate2_approval=null` | ✓ |
| gate1_approved（0002） | `DEV_GATE1_APPROVED` / 同 | 0 | **true** / false | 均 `null` | ✓ |
| gate2_pending（0003） | `DEV_GATE2_PENDING` / 同 | 0 | false / false | 均 `null` | ✓ |
| gate2_approved（0004） | `DEV_GATE2_APPROVED` / 同 | 0 | false / **true** | 均 `null` | ✓ |
| gate2_held（0004） | `DEV_GATE2_HELD` / 同 | 0 | false / false | 均 `null` | ✓ |
| gate2_rejected（0004） | `DEV_GATE2_REJECTED` / 同 | 0 | false / false | 均 `null` | ✓ |
| screened（0005） | `DEV_GATE2_APPROVED` / 同 | 0 | false / **true**，另有 `RULE_SCREEN_RECORDED` 与 `0005`（`kind=RUN_RULE_SCREEN`）凭证 | 均 `null` | ✓ |

每阶段的完整记录（`r3_stage_<阶段>_full.json`）含：实际 API 返回全文与 CLI 返回全文（含未截断消息）、调用实参、本阶段 `check_dev_action` 调用明细、`current_checkpoint` 路径与其 `workflow.state` 中两项批准、动作允许值、`completed_actions`、`screening_status`、before/after API/CLI 三份目录哈希集合（独立文件引用 + 字节哈希）。记录中同时给出**可接受原因**与实测原因，供独立核验对比。

---

## 7. 真实计数（本轮实际留痕导出）

**全量（本轮完整入口，`summary.json`／`counts.json`）**

- CLI：start 38／status 63／record 36／prepare-gate2 35／record-gate2 33／screen-rules 29（成功 24＋前提拒绝 5＋运行失败 0）；进程内公开宿主 API **27**（含经 helper 进入的 `inspect_dev_batch`）；控制器进程内按函数分列 `create 0`／`prepare 26`／`record 53`／`check 177`（合计 256；check+record 子集 230）；筛查核心进程内 **5 = 宿主 4 + 测试直接再调用 1**（CLI 内部记 `null`，成功 CLI 24 另列）；接收 38／checker 38（双向 missing/unregistered 均为空）；副本 1；故障注入 24；模拟决定 69；**真实批准 0**；进程内未进入 normalize/load 记 **0**。
- MAIN：12 条线索（R01 3／R02 5／R03 2／R04 2），R02 应付超额 1,600,000 分。

**本轮新增组（G10-R3，`r3_g10_counts.json`，从入口事件与实际调用记录导出，不照抄旧轮）**

- 公开 API 19（`inspect_dev_batch` 19；经 helper 进入也计入）；控制器 162（`check_dev_action` 113／`prepare_dev_gate` 16／`record_dev_decision` 33）；CLI 98（start 16、status 25、record 15、prepare 14、record-gate2 13、screen 10）；进程内筛查核心 0；进程内 normalize/load **0**（显式记录）；CLI 子进程内核心次数 **null**（不可观测）＋推导值 24（按成功的 `screen-rules` 命令推导）。

**自测（`self_tests.json`，单列，均 `ok=true`）**：`f01_last_read_timing_self_test`（6 例）、`count_audit_self_test`（双向审计隔离自测）、`screen_entry_audit`（筛查入口与 0005 一一对应）、`probe_matcher`。

---

## 8. 保护结果

- 主保护基线 `data/reviews/task013_r2_20261012_080320/source_hashes_after.json`（70930 项，文件 SHA-256 `b53bc1f959953b46bab3217f90b67e4f465924b56845898c9d423927f59a1130`）：本轮核对结果为**恰 1 项变化、缺失 0** —— 仅 `tests\test_screen_demo_workflow.py`（本卡授权范围内）。
- 冻结哈希核对：`scripts\run_demo_workflow.py` = `ae5b7e24…cab4e2`、`docs\WORKFLOW_HOST_GUIDE.md` = `c7963c58…60cf5`，与卡上冻结值逐字节一致；本轮**未修改宿主与指南**。
- 容器内 INTEGRITY 核对 13 个受保护上游文件（控制器／接收器／checker／标准化／装载器／筛查核心／复算／底稿／schema／SPEC／契约／三个旧测试）前后一致。
- 交付文件 UTF-8 无 BOM；本轮临时验证脚本按显式清单删除（`.r3_tmp_*`、`.r3_summary.py`、`.r3_final.py`），无 `__pycache__` 残留，未清理项目外文件，未改历史产物。

---

## 9. 失败尝试与迭代（均为本轮真修，如实记录）

1. **观察层拦错位置**：一开始用 `Path.open` 观察目标读取，导致 `Path.read_bytes`（`file_sha256` 走的路径）完全不被观测，读取序列只有消费读取、守卫读取丢失。改为拦 `io.open`（pathlib 两条读取路径的公共底层）后读取序列完整。
2. **观察层自身混入调用栈**：`traceback.extract_stack()[:-1]` 把观察帧排到最内层，导致守卫读取被误判为内容读取。改为 `skip=0` 并显式过滤框架帧（`open`／`read_bytes`／`read_text`／`observed_open`）。
3. **测试侧测量污染宿主轨迹**：`_tree()`／`sha256(path)` 自身读盘被观察器记为“目标读取”，使注入后凭空多出内容读取、时点判定误判。改为测量动作期间挂起观察器（`suspend`/`resume`），并让恢复、after 快照都走原始字节读取。
4. **注入点用错序号**：先用“消费序号”与“文件打开序号”混比，注入从未命中；后改为**按真实读取序号触发**，并允许其后由守卫读取在本次调用内发现变化。
5. **0001 造样的连锁反应**：只加换行会顺带破坏 0002—0005 与 Gate2 材料的前序引用，宿主会在别的字段上先阻断。收敛为“只同步 0002 的前序引用（长度不变）”，并在探针里如实标注可接受检测点为 `0003.json.previous_file_sha256`。
6. **F02 造样时点错误**：原先在“已消费 0005 之后”同步 0005 引用，失败被引到 `0005.json` 字节复测而非目标字段；改为**公开调用之前**完成造样与同步，六项均落到目标字段。
7. **自测与恢复次序**：时点判定 `max()` 在空轨迹上报错、注入钩子内部哈希把字符串当字节、恢复动作发生在观察器撤销之前导致“恢复后 CLI 仍拒绝”，均已定位并修复（现象与修法见上）。
8. **`control_ok` 门槛残留**：`run_02` 完整入口退出 0 且 11 项 PASS，但 0001 探针记录里 `ok` 字段被写成 `false`（残留 `reads_total>=2` 门槛；`problems=[]`、`timing.qualified=true`）。该字段只影响 0001 记录自身的 `ok` 标注、不影响检查判定；已改为 `>=1` 并在**全新容器 `task013r3_run_03`** 重跑完整入口复核：G10-R3 PASS、11 项全 PASS、三项 F01 记录 `ok` 均为 `true`。

---

## 10. 未执行与边界

- 未执行：宿主或指南的任何修改；独立复算（R01—R04 之外）、可读事实底稿、AI 建议、人类判断保存、正式契约、真实 Gate、UI／真实 ERP／OCR／RAG、并发锁／断电试验、无边界 fuzz、TASK-014；未重跑 TASK-002—012 整套历史入口（三个旧测试入口未改未跑，本卡最小回归由新入口覆盖）。
- 边界：本地哈希只证明字节一致；不声称断电持久性、并发锁、身份认证或同权限防篡改。`0005` 是宿主**筛查完成凭证**，不是 Gate2 放行，也不代表整个 `SCREEN_AND_BUILD_FACTS` 动作或项目完成。F02 的本轮形态验证的是“造样与引用同步之后，宿主按目标字段语义核验拒绝、撤销后仍拒绝、恢复后通过”，与 R2 的“同一次调用内改已消费产物”形态互补（后者由 F01 三项与 G6 三项覆盖）。
- 真实批准恒 **0**、`next_step_allowed=false`、workflow 未新增请求或决定；批次父目录 **0 份 0006**。
