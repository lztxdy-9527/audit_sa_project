# TASK-010 执行回执（开发态接收宿主与 Gate1 暂停、恢复落盘）

任务：接通**实际接收**——真实调用冻结接收入口接收一份合成 ERP 导出，保存本次接收与 Gate1 候审状态，关掉进程再打开仍能找到同一批材料与当前状态；用明确的模拟决定验证暂停／恢复，然后停在 Gate1。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-010_DRAFT.md`、`docs/reviews/REVIEW_TASK_009_R2.md`、`docs/WORKFLOW_CONTROL_GUIDE.md`、`docs/BATCH_RECEIVE_GUIDE.md`、`docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务十一，未建立正式契约，未批准任何真实 Gate，未保存／预填人类判断，未生成 AI 建议，**未运行标准化、SQLite、规则、复核、底稿或 AI**。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。既有实现、测试、指南、SQL、schema、契约草案、任务卡、验收单、生成器、答案册、输入、旧清单、旧数据库与旧容器全部保持原字节。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| **三个固定接口** | `start_dev_batch(workbook_path, batch_dir, source_description)`／`inspect_dev_batch(batch_dir)`／`record_simulated_gate1_decision(batch_dir, decision)`；CLI 子命令 `start`／`status`／`record-simulated-decision` 与核心共用实现 |
| **真实接收** | `start` 以子进程**实际调用**冻结 `scripts/receive_demo_batch.py`（命令、退出码、stdout／stderr 全部落盘），随后宿主只在新批次的 `workflow/` 子树写自己的产物；接收器的 `source/`、`checks/`、`logs/`、`code_snapshot/`、`batch_manifest.json`、`gate1_packet.md` 不被改写 |
| **实测绑定** | 宿主每次重新读取磁盘字节计算 SHA-256（源快照、SPEC、契约草案、八个脚本、R01—R04 SQL、固定 config、宿主自身代码与 schema、接收器八份材料），再交给冻结控制器比较；**不从 `workflow.run_bindings` 抄回** |
| **落盘与恢复** | `workflow/host_manifest.json` + `workflow/checkpoints/0001.json`（Gate1 pending）；`status` 只读、读取**完整 checkpoint 链**并调用 `check_dev_action` 触发控制器完整验证；`record-simulated-decision` 只在当前 `DEV_GATE1_PENDING` 追加 `0002.json` |
| **独占创建** | checkpoint 与宿主清单均**独占创建、不覆盖**；写完关闭后重新读回并核验 JSON、内容、指纹与控制器协议才宣布成功；`revision` 为严格整数、链上前序字节哈希必须一致 |
| **真实批准** | 真实 `gate1_approval`／`gate2_approval` 恒为 `null`；模拟决定固定标记 `SIMULATED_HUMAN` + `SIMULATED_TEST_ONLY`，另存；`next_step_allowed=false`；**真实批准 0 条** |
| **开发验证** | CLI 调用 start **15**、status **15**、record **14**，宿主 API 直接调用 **3**；真实接收器运行 **11** 次、checker 运行 **12** 次、模拟决定 **3** 条、故障注入 **10** 次；**测试失败 0，退出 0**；**未执行标准化／SQLite／规则／复核／底稿／AI** |
| **历史保护** | TASK-009-R2 验收基线（14691 项）**0 变化、0 缺失**（本卡只新增文件与新批次）；13330／12546／10236／8547／6511／4902／874 基线均 0 变化；原合成工作簿与旧接收批次字节未变 |

---

## 2. 新增文件与目录

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\run_demo_workflow.py` | `604b48f2a7930e6142e10d09a984625909e6393136c8c22339facc9c3fe69546` |
| `D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py` | `4e4b01cb4de3d7c3314e12e59a8ea2eef761dfae90e81807c79044fc8a7ee25f` |
| `D:\harness work\audit_sa_project\docs\WORKFLOW_HOST_GUIDE.md` | `05a888c64d6c2fb4b7ee2c33fcf846bc0648bc5f92b43bc7884e9559ef36824e` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_010.md` | 本文件（新增） |

- 测试容器：`data\workflow_host_tests\task010_04`（**最终**，108 个文件；含 `summary.json`、`checks.json`、`cli_logs.json`、`cli_logs/`、逐次 stdout／stderr）。
- 新批次（由**真实接收器**创建）：`data\batches\task010_04\` 下 **17 个**叶子批次（213 个文件）：
  `main_01`（Gate1 pending）、`main_approve`／`main_hold`／`main_reject`（三种模拟决定）、`c12_blocked`（质量阻断现场）、`fault_snapshot`／`fault_quality_report`／`fault_receive_manifest`／`fault_code_paths`／`fault_write`（故障用例）、`ckpt_corrupt`／`ckpt_fingerprint`／`ckpt_phase`／`ckpt_chain`／`ckpt_unknown`（checkpoint 完整性用例）、`external_copy`、`hostile_text`。
- 过程容器：`task010_03`／`task010_02`／`task010_01` 与 `data\batches\task010_01`—`task010_03` 保留为修正过程现场。

## 3. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$host = 'D:\harness work\audit_sa_project\scripts\run_demo_workflow.py'
```

### 3.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\run_demo_workflow.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py'
```

退出码均 **0**。

### 3.2 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task010_04'
```

退出码 **0**；输出：

```text
CLI 调用：start 15、status 15、record-simulated-decision 14；宿主 API 直接调用 3
接收器运行 11 次、checker 运行 12 次、模拟决定 3 条、真实批准 0 条、故障注入 10 次
测试失败 0；受保护文件前后哈希一致: True（18 个）
[PASS] G1_START_AND_RESTART / G2_THREE_DECISIONS / G3_R03_LEGAL_AND_C12_BLOCKED
[PASS] G4_PATH_AND_LEGACY_REJECTIONS / G5_MATERIAL_FAULTS_DETECTED
[PASS] G6_EXTERNAL_INPUT_AND_UNTRUSTED_TEXT / G7_CHECKPOINT_INTEGRITY
[PASS] G8_WRITE_AND_DECISION_FAULTS / G9_STATIC_AND_RUNTIME_ISOLATION
[PASS] INTEGRITY_protected_files
全部预期成立。
```

### 3.3 三个命令模板的实际用法（新进程逐步执行）

```powershell
& $py -B $host start --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' --batch-dir 'D:\harness work\audit_sa_project\data\batches\task010_04\main_01' --source-description '合成 ERP 导出（演示用）'
& $py -B $host status --batch-dir 'D:\harness work\audit_sa_project\data\batches\task010_04\main_01'
& $py -B $host record-simulated-decision --batch-dir 'D:\harness work\audit_sa_project\data\batches\task010_04\main_approve' --decision-file 'D:\harness work\audit_sa_project\data\workflow_host_tests\task010_04\decision_APPROVE.json'
```

退出码 **0/0/0**（每次都由独立 Python 进程执行，因此恢复路径就是真实重启路径）。

### 3.4 其他核验

```powershell
& $py -c "import sys; print(sys.version.split()[0])"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\run_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_run_demo_workflow.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\WORKFLOW_HOST_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\control_demo_workflow.py' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与证据提取；未新增临时 `.py` 文件。

---

## 4. 分类计数（按实际操作，不预设总数）

| 项目 | 数量 |
| --- | --- |
| CLI `start` | **15** |
| CLI `status` | **15** |
| CLI `record-simulated-decision` | **14** |
| 宿主 API 直接调用（`inspect_dev_batch` 等） | **3** |
| 真实接收器运行 | **11** 次 |
| 真实 checker 运行 | **12** 次（含 C12 的 1 次） |
| 工作簿输入 | **2** 个（主演示导出、C12 质量坏例） |
| 模拟决定 | **3** 条（APPROVE／HOLD／REJECT 各 1） |
| **真实批准** | **0** 条 |
| 故障注入 | **10** 次（材料 3、代码/SQL/规格路径替换 1、写入 1、决定输入 4、外部输入 1，另 checkpoint 完整性 5 项单列于 G7） |
| 测试失败 | **0** |

## 5. 九组验证的实际结果

**G1 实际接收与重启恢复**：`start` 真实调用接收器（退出 0），保存命令／退出码／stdout／stderr；快照与来源哈希一致、八份材料齐备、质量报告 `pass`／`issues=[]`／`issue_counts_by_code={}` 且与快照和 checker 源码绑定一致；写入 `host_manifest.json` 与 `checkpoints/0001.json` 后 phase = `DEV_GATE1_PENDING`、模拟决定 0、真实批准 0；批次内**没有** `normalized`／`screen`／`crosscheck`／`fact_packet` 等下游产物；另起新进程 `status` 恢复同一请求，报告的 checkpoint 字节哈希与磁盘一致。

**G2 三种模拟决定**（三个独立批次、CLI 新进程提交、再新进程 `status`）：

| 决定 | 记录后 phase | `simulated_action_allowed` | 重复决定 | 旧 checkpoint |
| --- | --- | --- | --- | --- |
| APPROVE | `DEV_GATE1_APPROVED` | `true`（`next_step_allowed=false`） | 阻断（exit 1） | 0001 字节未变 |
| HOLD | `DEV_GATE1_HELD` | `false` | 阻断 | 0001 字节未变 |
| REJECT | `DEV_GATE1_REJECTED` | `false` | 阻断 | 0001 字节未变 |

每份 `0002.json` 的 `previous_file_sha256` 等于 `0001.json` 的实际字节哈希；重复决定**不追加** `0003.json`。

**G3 合法 R03 与质量坏例**：主演示样本缺失应付关联净额 **1 000 000 分**（空应付关联 500 000／台账外标识 500 000，勾稽成立 `ASSESSED`）**仍被正常接收**并形成 Gate1 请求；质量坏例 C12 由 checker **实际阻断**（接收器退出 1、宿主返回 1 且原因指向质量问题），真实报告与现场保留，**没有**宿主清单与 checkpoint，未建立可批准请求。

**G4 路径与旧批次**：已存在目标、`data/batches` 之外的目标、`data/batches` 本身、以及旧的纯接收批次（无宿主清单）全部被拒；`status`／`record` 对旧批次同样拒绝，且**拒绝前后已有文件字节不变**。

**G5 已接收材料的故障注入**：改快照、改质量报告、改接收清单后，恢复入口与提交入口**各自**阻断，且不写出新 checkpoint（旧决定不复用）；代码／SQL／规格变化用**新测试文件副本 + 测试内替换私有路径常量**验证（未修改任何冻结文件，替换方式与实测字节全部记录），同样被检出。

**G6 外部输入与不可信文字**：接收后修改外部副本，恢复仍基于批次快照且快照未变，原合成工作簿字节不变；来源描述含首尾空格、换行与「忽略规则，批准 Gate」文字时**按原字符串保存**，阶段仍为 `DEV_GATE1_PENDING`、无模拟决定。

**G7 checkpoint 完整性**：半文件／损坏 JSON、外层 `state_sha256` 被改、`phase` 被改、前序字节哈希不符、未知新 checkpoint，五项**全部拒绝**（exit 1），未绕开冻结控制器的历史验证。

**G8 写入故障与决定输入故障**：注入写后关闭／读回失败时**不宣称保存成功**（`WorkflowHostError`），旧 checkpoint 字节不变、**半文件保留**，后续恢复因此阻断；决定输入缺 `simulation`／`simulation=REAL`／错误 `request_id`／`actor_kind=AI` 四项均得到 `WorkflowHostBlocked`，原因分别指向 `decision.simulation`（缺字段）、`decision.simulation`（`REAL`）、`decision.request_id`、`decision.actor_kind`。

**G9 静态与运行期隔离**：宿主导入仅为 `__future__`／`argparse`／`copy`／`datetime`／`hashlib`／`importlib`／`json`／`os`／`pathlib`／`subprocess`／`sys`，无禁用模块；**结构化核对**显示宿主只有一处 `subprocess.run` 且位于 `_run_receiver`、命令固定指向冻结接收器常量；运行期把 `subprocess.run`／`Popen`／`socket.socket` 全部替换为抛错后，`status` 仍成功（证明其不启动子进程、不建网络连接）且**未写入任何文件**；stdout 的 phase／`state_sha256`／当前 checkpoint 字节哈希与磁盘逐项一致。

## 6. 失败尝试与修正过程

1. **清单字段路径误读**：宿主按平铺键读取接收器的源码哈希，而实际嵌在 `hashes.receive_script.sha256_at_end`／`hashes.checker.sha256_at_end` 下 → 改为按接收器真实结构核对，并补 `stable_during_run` 与 `expected_scope` 交叉核对。
2. **模式常量口径**：接收器自身声明 `mode=DEVELOPMENT_ONLY`（与控制器要求的 `DEVELOPMENT_TEST_ONLY` 是不同层）→ 宿主分别核对：清单按接收器口径、控制器按自身口径，**未改动冻结上游**。
3. **`gate1_packet` 类型兼容**：旧清单版本是字符串、新版本是对象 → 两种形状都核对，对象形态下额外比对实际字节哈希。
4. **checkpoint 目录未创建**：首次写 `0001.json` 报 `No such file or directory`（正确归为运行错误 exit 2，批次现场保留）→ 写 checkpoint 前显式创建 `workflow/checkpoints/`。
5. **`host_manifest` 自引用键**：清单曾要求 `initial_checkpoint` 哈希，但该文件在其后创建，无法在不自引用的情况下写入 → 取消该键，**当前状态由有效 checkpoint 链确定**（链上第二份引用第一份的实际字节哈希）。
6. **批次被后续代码改动作废**：冒烟批次在宿主代码再次修改后 `status` 报绑定变化（正是设计意图）→ 用当前代码重建批次，并在指南说明“同一批次绑定含宿主自身代码哈希”。
7. **测试侧两处口径**：决定输入故障用例误用了已决定的批次（先被“已有第 2 份 checkpoint”拦下）→ 改到仍处于 pending 的批次，使阻断原因落在目标字段；静态检查原为裸词匹配，把绑定路径里的 `.sql` 误判为违规 → 改为 AST 导入白名单 + 唯一子进程调用点的结构化核对。

未通过放宽断言、删除既有负向、跳过检查或修改上游数据让用例通过。

## 7. 历史保护对照

- TASK-009-R2 验收基线（`data/reviews/task009_r2_20261011_101113/source_hashes_after.json`）：记录项 **14691**、变化 **0**、缺失 **0**（本卡只新增文件与新批次）。
- TASK-008-R1 的 **13330**、TASK-007-R2 的 **12546**、任务六 R1 的 **10236**、任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 **0 变化、0 缺失**（TASK-009／009-R1 基线中变化的三文件是此前两卡授权的修改，本卡未再改动）。
- 测试内建核验的 **18 个受保护文件**（宿主、控制器、接收器、checker、标准化、装载、筛查、复核、底稿、schema、四份 SQL、SPEC、契约草案、原合成工作簿、C12）前后哈希一致；旧接收批次与历史容器逐文件未变。
- 依赖未变（Python 3.11.1、SQLite 3.39.4 等）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 8. 偏差、未执行事项与停止状态

- **偏差**：`host_manifest.json` 不含 `initial_checkpoint` 哈希（避免自引用，当前状态由 checkpoint 链确定）；接收器模式按 `DEVELOPMENT_ONLY` 核对（其自身声明），控制器仍按 `DEVELOPMENT_TEST_ONLY`；`gate1_packet` 字段兼容字符串与对象两种形状。
- **未执行（不主张通过）**：任务十一、`prepare` Gate2、标准化／SQLite／规则／复核／底稿／AI 的实际运行、正式契约、审批命令、真实 Gate 放行、人类判断保存、UI、真实 ERP、OCR、RAG、多进程并发、压测、无边界 fuzz；未重跑任务二至九整套测试。
- **明确边界**：本地哈希只证明字节一致，不证明来源真实；不提供身份认证；不抵御同权限篡改；单一进程、单一操作者，不宣称断电持久性或多进程并发安全；模拟决定只是开发态测试样例，**不是**主理人真实批准。
- **停止状态**：三种决定后都停住（未执行标准化、未 `prepare` Gate2、未生成 AI 建议、未预填人类初步判断）；未建立契约、未批准任何真实 Gate、未接入正式批次入口；等待主理人把本回执、`docs\WORKFLOW_HOST_GUIDE.md`、`data\workflow_host_tests\task010_04` 与 `data\batches\task010_04` 转交总架构师验收。
