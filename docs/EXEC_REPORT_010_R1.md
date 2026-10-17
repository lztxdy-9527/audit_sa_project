# TASK-010-R1 执行回执（修复恢复协议、失败接收与提交收尾）

任务：修复 TASK-010 复验发现的 F01—F05——清单与 checkpoint 矛盾被接受、文件哈希链未证明状态连续、接收失败被误分类且缺失败宿主记录、写入之后未重核绑定即报告成功、验证计数与 PowerShell 示例问题。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-010-R1.md`、`docs/reviews/REVIEW_TASK_010.md`、`docs/tasks/TASK-010_DRAFT.md`、`docs/WORKFLOW_HOST_GUIDE.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务十一，未 prepare Gate2，未建立正式契约，未批准任何真实 Gate，未保存／预填人类判断，未生成 AI 建议，未运行标准化／SQLite／规则／复核／底稿／AI。

> 命令均为完整参数、不使用省略号。旧回执、任务卡、验收单、GPT 证据、旧批次与失败现场均保持原字节。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **F01 恢复核验** | 建立 `status`／`record` **共用**的 `_load_host_context`：结算清单形状与固定值（`manifest_version`／`host_version`／`mode`／`contract_status`／`status`／`next_step_allowed`／真实批准为 `null`）、`bindings_sha256` 必须等于**清单实际 bindings 对象**的规范指纹、清单绑定＝checkpoint 内创建绑定＝**当前实测绑定**三者逐项一致、哈希必须完整 64 位、`batch_id` 与目录叶子／每份 checkpoint／workflow 一致、`host_manifest.gate1_request` 与 `0001` 实际请求一致、材料按固定批次内路径与实际字节核对 |
| **F02 checkpoint 协议与延续** | `checkpoints/` 只允许 `0001.json` 与可选 `0002.json`，其他项（未知 `.json`、`.json.tmp`、目录）一律拒绝；逐份核验 `0001` 固定 `START_GATE1_REQUEST`（pending、无决定、无 Gate2）、`0002` 固定 `SIMULATED_GATE1_DECISION`（只允许 APPROVED／HELD／REJECTED、恰含本次一个决定、保留历史前缀与请求、不得退回 pending 或进入 Gate2）、操作摘要决定与正文实际指纹及 workflow 内存放决定一致；并用冻结 `record_dev_decision(0001.workflow, 决定正文, current_bindings=实测)` **复算完整预期返回**比较；形状先检后用（`state=null` 等给带路径的 `WorkflowHostBlocked`，不再 TypeError→退出 2） |
| **F03 失败接收** | 接收器返回后（批次存在且可写）**无论成功／质量阻断／运行失败**都保存真实命令／退出码／stdout／stderr；按**实际退出码与清单状态对应关系**分支：0+READY→完整成功核验与 Gate1 请求；1+BLOCKED_QUALITY→**失败清单**（完整实际质量诊断）返回 1；2+FAILED_RUNTIME→失败清单返回 2。失败清单含 `status`／`receive`／`failure`，**不含 bindings**、`checkpoints: []`、无 checkpoint 目录。`status` 可重新打开本宿主的失败批次并按保存原因返回 1／2，`record` 对失败批次一律拒绝 |
| **F04 提交收尾** | `start`／`record` 在独占写入、关闭、读回之后**重新核验 checkpoint 协议与链**并**重新实测绑定**，与操作前逐项比较一致才返回成功；发现变化时给出文件路径与预期／实际、保留已写现场、不宣告成功、不覆盖旧 checkpoint、不自动更新绑定。`status` 在读取结束后再次核验所消费的不可变文件、宿主清单与当前 checkpoint 字节哈希，避免混合现场 |
| **F05 验证与说明** | 新增 M01—M03、C01—C05、S01、T01／T02 与**真实 `_write_exclusive_json`** 的有限 I/O 故障（底层 `handle.write` 写一半后抛 `OSError`，命中 1 次）；负向探针同时核验异常类别与**目标原因**；计数按**实际启动接收器**统计并区分 CLI／API／真实接收／批次副本；指南改用 `$workflowScript`（`$Host` 是 PowerShell 自动变量）、给出未存在的新批次模板、同步成功／失败清单形状与三类退出码、语法检查改为编译源文本 |
| **版本** | 宿主 `TASK-010-workflow-host-1.1`；清单 `TASK-010-host-manifest-1.1`；checkpoint `TASK-010-checkpoint-1.1`（新增 `status`、`host_manifest_file_sha256` 字段；**未迁移旧批次**） |
| **开发验证** | CLI start **16**、status **29**、record **16**；宿主 API **9**；**真实接收启动 13** 次（原 12 场景 + 新增运行失败小样）、checker **12** 次、批次副本 **11** 份、真实 writer 故障命中 **1** 次；模拟决定 **3** 条、**真实批准 0 条**；**测试失败 0，退出 0** |
| **历史保护** | TASK-010 验收基线（16340 项）**变化 3、缺失 0**（恰为本卡授权三个文件）；TASK-009-R2 的 14691、13330、12546、10236、8547、6511、4902、874 基线均 **0 变化、0 缺失** |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\run_demo_workflow.py` | `e38056016df78a324217bce2b7c77db0191a269524a0a883a2a6f233992f664f` |
| `D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py` | `e0cbe2c9420ced09aaea4fad0096a177a655aa50ff9f69d73dd4da0b05c336c7` |
| `D:\harness work\audit_sa_project\docs\WORKFLOW_HOST_GUIDE.md` | `f9a537b0d46baa41821ca472a1c6f102e838d759395d94d99c46b2bfd76b6917` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_010_R1.md` | 本文件（新增） |

- 测试容器：`data\workflow_host_tests\task010r1_02`（**最终**，147 个文件；`summary.json`／`checks.json`／`cli_logs.json`／`cli_logs/` 逐次 stdout／stderr）。
- 真实接收批次与故障副本：`data\batches\task010r1_02\` 下 **30** 个叶子目录（376 个文件）：13 份真实接收批次（成功 11、C12 质量阻断、运行失败小样）＋11 份故障副本（M／C／S／T／真实 writer 故障）＋其余为副本的承载目录。
- 过程容器：`task010r1_01` 与 `data\batches\task010r1_01`、`task010r1_smoke*`（修正过程现场，保留）。

## 3. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$workflowScript = 'D:\harness work\audit_sa_project\scripts\run_demo_workflow.py'
```

### 3.1 语法检查（编译源文本，不写 pyc）

```powershell
& $py -B -c "src = open(r'D:\harness work\audit_sa_project\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"
& $py -B -c "src = open(r'D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"
```

退出码均 **0**（`compile OK`）。

### 3.2 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task010r1_02'
```

退出码 **0**；输出：

```text
CLI 调用：start 16、status 29、record-simulated-decision 16；宿主 API 直接调用 9
真实接收启动 13 次、checker 运行 12 次、批次副本 11 份、真实 writer 故障注入命中 1 次、
模拟决定 3 条、真实批准 0 条、故障注入 22 次
测试失败 0；受保护文件前后哈希一致: True（18 个）
[PASS] G1—G9 与 R1_RECOVERY_PROTOCOL_AND_WRITE_TAIL、INTEGRITY_protected_files
全部预期成立。
```

### 3.3 三个命令模板（新进程逐步执行，路径均为未存在的新叶子）

```powershell
& $py -B $workflowScript start --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' --batch-dir 'D:\harness work\audit_sa_project\data\batches\<新父目录>\<新叶子>' --source-description '合成 ERP 导出（演示用）'
& $py -B $workflowScript status --batch-dir 'D:\harness work\audit_sa_project\data\batches\<新父目录>\<新叶子>'
& $py -B $workflowScript record-simulated-decision --batch-dir 'D:\harness work\audit_sa_project\data\batches\<新父目录>\<新叶子>' --decision-file 'D:\harness work\audit_sa_project\data\workflow_host_tests\<容器>\decision_approve.json'
```

退出码 **0/0/0**；每次都是独立 Python 进程，因此恢复路径就是真实重启路径。

### 3.4 其他核验

```powershell
& $py -c "import sys; print(sys.version.split()[0])"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\run_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\WORKFLOW_HOST_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\control_demo_workflow.py' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本用于基线比对与证据提取；未新增临时 `.py` 文件。

---

## 4. 分类计数（按实际操作）

| 项目 | 数量 |
| --- | --- |
| CLI `start` / `status` / `record-simulated-decision` | **16 / 29 / 16** |
| 宿主 API 直接调用 | **9** |
| **真实接收启动**（批次目录由接收器创建） | **13**（原 12 场景 + 新增运行失败小样；三次路径拒绝未启动接收器） |
| 真实 checker 运行 | **12**（含 C12 与运行失败小样各 1 次） |
| 批次副本（故障用例） | **11** 份 |
| 真实 writer 有限 I/O 故障命中 | **1** 次 |
| 模拟决定 / **真实批准** | **3** 条 / **0** 条 |
| 故障注入合计 | **22** 次 |
| 测试失败 | **0** |

**计数更正（不改旧回执）**：上一轮回执写“receiver 11 是测试计数错误，实际为 12”——本轮已把计数改为按**实际启动接收器**统计：原场景为 **12** 份真实接收，本轮新增运行失败小样后为 **13**；另 **11** 份为故障副本，不是真实接收。

## 5. F01／F02 探针的实际结果（全部命中目标原因）

| 探针 | 唯一变更 | 实际阻断原因（节选） |
| --- | --- | --- |
| M01 | 清单 `mode = REAL`（同步清单字节哈希） | `host_manifest.json.mode 必须是 DEVELOPMENT_TEST_ONLY，实际 'REAL'`（status 与 record 均阻断，未追加 0002） |
| M02 | 清单 `bindings.input_sha256 = 0…0`，保留旧 `bindings_sha256` | `host_manifest.json.bindings_sha256 必须等于清单实际 bindings 对象的规范指纹` |
| M03 | 清单 `gate1_request.request_id = OTHER-REQUEST` | `host_manifest.json.gate1_request.request_id 必须与 0001 实际请求一致：'OTHER-REQUEST' != 'GATE1/base/…'`（status 与 record 均阻断，未追加 0002） |
| C01 | `0002.batch_id = OTHER-BATCH` | `workflow/checkpoints/0002.json.batch_id 必须与批次目录叶子一致` |
| C02 | `0002.operation.decision.reason` 被改 | `…operation.decision.decision_sha256 必须等于决定正文（剥离派生字段）的实际规范指纹` |
| C03 | `0002.workflow` 换回合法 `0001` pending | `…0002.json.workflow.state.simulated_decisions 必须恰含本次一个决定，实际 0` |
| C04 | 新增 `0003.json.tmp` 半文件 | `…/0003.json.tmp 本宿主只接受 ['0001.json', '0002.json']，拒绝未知项（含半文件与目录）` |
| C05 | `0002` 换成**另一份 Gate1 请求**的合法批准 workflow（前序哈希正确） | `…不是 0001 的合法延续：冻结控制器阻断该决定` ／ 完整预期返回不一致 |
| S01 | `0001.workflow.state = null` 且外层指纹同步 | `…0001.json.workflow.state 必须是对象，实际 NoneType`（**WorkflowHostBlocked 退出 1**，不再是意外程序错误） |

## 6. F03／F04／F05 的实际结果

- **C12 质量阻断**：`start` 返回 **1**，原因含 `checker 退出码=1、report_result='issues_found'`、`质量报告 result='issues_found'、issue_counts_by_code={'ALLOCATION_SUM_MISMATCH': 1}` 与实际问题条目示例；保存**失败宿主清单**（`status=BLOCKED_QUALITY`、`receive.exit_code=1`、无 bindings、`checkpoints: []`、无 checkpoint 目录）；`status` 重新打开该批次返回 **1** 并给出同样的原因。
- **运行失败小样**（新容器内的非 ZIP `.xlsx`，真实运行接收器/checker）：`start` 返回 **2**（`WorkflowHostError`，原因含 `[run_checker] checker 退出码 2`），保存 `status=FAILED_RUNTIME` 失败清单；`status` 再打开返回 **2**；两批均无 checkpoint，未建立可批准请求。
- **T01／T02**：包装**真实** `_write_exclusive_json`，在其完成写入、关闭、读回之后改变**新故障批次**快照（各命中 1 次）→ 本次 `record`／`start` **未报告成功**，后续 `status` 拒绝（退出 1），`0001`（T01 的旧 checkpoint）字节未被宿主回写。
- **真实 writer 的有限 I/O 故障**：仅对本轮新故障批次的 `0002.json` 底层 handle 注入“写一半后抛 `OSError`”（命中 **1** 次）→ 真实写入路径转换为 `WorkflowHostError`，旧 `0001` 不变、半文件保留、后续恢复明确阻断。
- **静态与运行期边界**（G9）保持：导入白名单通过、宿主唯一子进程调用点固定指向冻结接收器；守卫下 `status` 不启子进程／不建网络／不写文件；stdout 与落盘状态逐项一致。

## 7. 原有回归保持

G1—G9 全部保留且通过（真实接收与重启恢复、三种模拟决定与重复拒绝、R03 合法与 C12 阻断、路径与旧批次拒绝、材料故障注入、外部输入与不可信文字、checkpoint 完整性、写入与决定输入故障、静态与运行期隔离），未删除或放宽任何负向；新增 R1 组 14 项探针独立计数。真实批准仍然为 **0**。

## 8. 失败尝试与修正过程

1. **清单声明 checkpoint 列表与“创建后不回写”冲突**：首版在成功清单里写 `checkpoints_declared`，导致写完 `0002` 后写后核验自我矛盾（record 被自己拦住）→ 取消该字段，改由**链规则**确定（只允许 `0001` 与可选 `0002`，其他项一律拒绝），失败清单则要求 `checkpoints: []` 且**不存在** checkpoint 目录。
2. **M03 先被清单字节哈希拦住**：测试改清单后未同步 checkpoint 内引用的清单文件字节哈希 → 增加测试侧同步（仅新内存／副本），使阻断落在目标字段 `gate1_request.request_id`。
3. **T01 经 CLI 注入无效**：`record` 走 CLI 是新进程，进程内 monkeypatch 不生效 → 改为通过**宿主 API** 在进程内注入（与 T02、真实 writer 故障一致），命中计数 >0。
4. **运行失败消息误写“质量阻断”**：按分支生成消息（质量阻断／运行失败），并把质量诊断补全为 checker 退出码、报告结果、问题计数与问题条目示例。
5. **PowerShell 引号吞字符**：多次内联脚本改写被 PowerShell 吞掉双引号 → 改用编辑工具逐处修改，避免语法残片。

未通过放宽断言、删除负向、跳过检查或修改上游数据让用例通过。

## 9. 历史保护对照

- TASK-010 验收基线（`data/reviews/task010_20261011_104531/source_hashes_after.json`）：记录项 **16340**、变化 **3**（`scripts\run_demo_workflow.py`、`tests\test_run_demo_workflow.py`、`docs\WORKFLOW_HOST_GUIDE.md`）、缺失 **0**。
- TASK-009-R2 的 **14691**、TASK-008-R1 的 **13330**、TASK-007-R2 的 **12546**、任务六 R1 的 **10236**、任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 **0 变化、0 缺失**。
- 测试内建核验的 **18 个受保护文件**前后哈希一致；冻结接收器、checker、v1.2 控制器、旧批次与 GPT 证据逐文件未变。
- 依赖未变（Python 3.11.1、SQLite 3.39.4 等）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`；语法检查改为编译源文本，未产生 `.pyc`。

## 10. 偏差、未执行事项与停止状态

- **偏差**：清单与 checkpoint 协议版本升为 1.1（新增 `status`、`host_manifest_file_sha256`；取消 `checkpoints_declared`），**不迁移旧批次**（旧批次按新协议核验会阻断，符合“不迁移旧现场”要求）；`status` 对失败批次按保存状态返回 1／2。
- **未执行（不主张通过）**：任务十一、`prepare` Gate2、标准化／SQLite／规则／复核／底稿／AI 的实际运行、正式契约、审批命令、真实 Gate 放行、人类判断保存、UI、真实 ERP、OCR、RAG、多进程并发、压测、无边界 fuzz；未重跑任务二至九整套测试。
- **明确边界**：本地哈希只证明字节一致，不证明来源真实；不提供身份认证；不抵御同权限篡改；单一进程、单一操作者；模拟决定只是开发态测试样例，**不是**主理人真实批准。
- **停止状态**：三种决定后都停住；未建立契约、未批准任何真实 Gate、未接入正式批次入口；等待主理人把本回执、`docs\WORKFLOW_HOST_GUIDE.md`、`data\workflow_host_tests\task010r1_02` 与 `data\batches\task010r1_02` 转交总架构师复验。
