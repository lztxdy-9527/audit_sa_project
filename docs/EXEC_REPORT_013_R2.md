# TASK-013-R2 执行回执（合法状态恢复、最终收尾与定向证据）

任务：关闭 TASK-013-R1 复验剩余三组缺口——F01 早期/停止阶段只读恢复的运行错误、F02 最后一次数据消费后的复测覆盖面、F03 探针时点与完整调用记录（含两处旧回执更正）。
日期：2026-10-12。执行端：DeepSeek。
依据：`docs/tasks/TASK-013-R2.md`、`docs/reviews/REVIEW_TASK_013_R1.md`、原 TASK-013 卡与 R1 卡。
状态：完成并自检通过，**停在 DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED**（合法早期/停止态保持不变）；未新增 0006，未执行独立复算／事实底稿／人类判断／AI，未建立正式契约、未签真实 Gate，未推进 TASK-014。

---

## 1. 结论摘要

| 缺口 | 修复与证据 |
| --- | --- |
| **F01 合法阶段只读恢复** | `inspect_dev_batch` 的 `screen_expected` 原只在 `revision >= 5` 分支赋值却在分支外读取 → 早期阶段 `UnboundLocalError`／退出 2。现与筛查专属收尾一起条件化（`screen_expected = None` 在所有分支外初始化，筛查收尾严格限定在 `revision >= 5`），**未用捕获异常返回默认成功掩盖问题**。七个阶段实测均退出 0 且返回真实 phase 与真实动作允许值（见 §4） |
| **F02 最终复测覆盖面** | Gate2 全集复测原发生在最后一次报告消费**之前**；现于**最后一次必要控制器调用与最后一次必需数据消费之后**、返回成功之前，继续复测 `normalized`／`load_report`／Gate2 `artifacts`、数据库、`host_manifest`、`0001—0005`、screening `started`／`report`／`artifacts`、静态绑定与失败／未知项状态；预期只取自初始同源缓冲读取或本次真实 writer 返回。GPT 两条反例（`load_report`、`0001`）加报告自身共三项，**本次调用即拒绝**（见 §5） |
| **F03 时点与完整记录** | 三项报告边界探针改挂在**真实 `_read_screen_outputs` 返回初始缓冲之后**（此前挂在首次 `_verify_screen_tail` 返回，时点不成立）；探针记录补齐公开入口、完整实参、`batch_dir`、预期类别与目标原因、完整异常类／消息／`stage`／`reasons`／cause 链／逐帧 traceback、wrapper 位置与命中、完整调用顺序、真实前后值、撤销后新进程 CLI 与恢复原件后的正向结果。G6 既有三方向（0005／数据库／快照）补齐 `later_cli` 与 `restored_positive` 及完整异常现场 |
| **两处旧回执更正** | ① 旧 `EXEC_REPORT_013_R1.md` 正文宿主哈希写 `95b2a2…`；实际文件与两组容器绑定都是 `11525395…`（本轮回执按实际文件报告）。② 旧回执/消息写 writer 完整待写文本 `14,223,730` 字节／`092938f5…`；**按 R1 最终容器实际文件重读为 `14,223,740` 字节／`bd287093d53bd2fe6b869f97d70ba9e5e101ee3721fc9637b5bf46618f9b1a32`**。两项说明在此更正，**旧回执不回写**；本轮最终现场的实际读数见 §5 |
| **版本** | 实现版本 → `TASK-013-workflow-host-1.2`；`CHECKPOINT_VERSION`／`HOST_MANIFEST_VERSION` 仍 `TASK-012-*-1.0`，`TASK-013-screen-*` 仍 1.0（实现与持久化协议版本分开） |
| **开发验证** | 全新容器回归 **退出 0、11 项检查全 PASS、failures=[]**（含新增 `G10_R2_STAGE_RECOVERY_AND_CONSUMER_TAILS`）；`FINAL_ARTIFACT_READBACK` 独立单列（持久化条目 11 条 + 保护核对） |

## 2. 修改文件与产物路径

| 文件 | SHA-256 |
| --- | --- |
| `scripts\run_demo_workflow.py`（实现版本 `TASK-013-workflow-host-1.2`） | `ae5b7e24dd946a0a2186b8741b79af4173e091c362c4c210d8186e92d2cab4e2` |
| `tests\test_screen_demo_workflow.py` | `e7851240930461486010f68012a497d2ff7b34d34f0633b3185e27c6b17756e3` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `c7963c5857580ae9f3d75e0b6c9e9d448f988b5c561745df63f60b1a92060cf5` |
| `docs\EXEC_REPORT_013_R2.md` | 本文件（新增；自哈希不内嵌，避免自引用） |

三条完整产物路径：

- 测试容器 `D:\harness work\audit_sa_project\data\workflow_host_tests\task013r2_run_06`（451 文件；`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`entry_events.json`／`self_tests.json`／`final_readback.json`／`probe_records\` 21 份完整记录／`core_returns\` 5 份核心真实返回）
- 批次父目录 `D:\harness work\audit_sa_project\data\batches\task013r2_run_06`（657 文件；**21 份 `0005`、0 份 `0006`**）
- 外置数据库父目录 `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task013r2_run_06`

MAIN 报告 `…\data\batches\task013r2_run_06\main_01\workflow\screening\screening_report.json`；MAIN 凭证 `…\workflow\checkpoints\0005.json`；本轮 writer 完整待写文本 `…\task013r2_run_06\g5_writer_full_expected_0005.json`。

过程现场：`task013r2_run_01`（暴露 builder 返回类型）、`run_02`（暴露阶段停点/重复建批次）、`run_03`（暴露副本作基线）、`run_04`（暴露探针未恢复原件）、`run_05`（F03 前全绿）、`task013r2_smoke`（F01/F02 定向冒烟）。均保留未回写。

## 3. 实际命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0
& $py -B -c "src = open(r'...\tests\test_screen_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_screen_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task013r2_run_06'   # 0
```

输出要点：`测试失败 0；受保护文件前后一致: True`、`全部预期成立。`。检查项 **11**：G1 MAIN、G2 小样、G3 阶段与重复、G4 报告与引用篡改、G5 真实失败、G6 最终复测三探针、G7 只读与隔离、G9 R1 协议回归、**G10_R2 阶段恢复与消费边界**、G8 计数审计与证据、INTEGRITY 保护核对（`FINAL_ARTIFACT_READBACK` 以 `final_readback.json` 独立单列）。

## 4. F01 各阶段只读恢复（本轮实测，均退出 0）

| 阶段 | API phase | CLI exit | `actions_simulated_allowed` | `completed_actions` | 只读 |
| --- | --- | --- | --- | --- | --- |
| gate1_pending（0001） | `DEV_GATE1_PENDING` | 0 | `NORMALIZE_AND_LOAD=false`、`SCREEN=false` | `[]` | 是 |
| gate1_approved（0002） | `DEV_GATE1_APPROVED` | 0 | `NORMALIZE_AND_LOAD=true`、`SCREEN=false` | `[GATE1_SIMULATED_DECISION]` | 是 |
| gate2_pending（0003） | `DEV_GATE2_PENDING` | 0 | 两者 false | `[GATE1_SIMULATED_DECISION, NORMALIZE_AND_LOAD]` | 是 |
| gate2_approved（0004） | `DEV_GATE2_APPROVED` | 0 | `NORMALIZE_AND_LOAD=false`、`SCREEN=true` | 三项 | 是 |
| gate2_held（0004） | `DEV_GATE2_HELD` | 0 | 两者 false（停止态可读，动作不可继续） | 三项 | 是 |
| gate2_rejected（0004） | `DEV_GATE2_REJECTED` | 0 | 两者 false（同上） | 三项 | 是 |
| screened（0005） | `DEV_GATE2_APPROVED` | 0 | `SCREEN=true`、`NORMALIZE_AND_LOAD=false` | 四项（含 `RULE_SCREEN`） | 是 |

每阶段均记录 API 与**新进程 CLI** 两种入口、真实 phase、动作允许值、真实批准 `null`、`next_step_allowed=false`，以及批次树**前后文件哈希逐一相同**（只读证明）。完整明细见容器 `probe_records\r2_f01_stage_recovery.json`。

## 5. F02／F03 定向证据

- **F02 三项探针**（同一专用新批次 `r2_f02_baseline`；在真实 `_read_screen_outputs` **返回初始缓冲之后**各注入 1 次）：

| 目标 | 命中 | 本次调用 | 目标原因 | 撤销 wrapper 后新进程 | 恢复原件后新进程 |
| --- | --- | --- | --- | --- | --- |
| `workflow/screening/screening_report.json` | 1 | `WorkflowHostBlocked`／1 | `screening_report.json` | exit 1 | exit 0 |
| `workflow/gate2/load_report.json` | 1 | `WorkflowHostBlocked`／1 | `workflow/gate2/load_report.json` | exit 1 | exit 0 |
| `workflow/checkpoints/0001.json` | 1 | `WorkflowHostBlocked`／1 | `workflow/checkpoints/0001.json` | exit 1 | exit 0 |

before≠after 且各有取值时点；完整记录见 `probe_records\r2_f02_<目标>_tail_after_last_read.json`（含调用顺序「控制器动作返回→读取调用/返回→注入→最终核验/拒绝」）。

- **F03 本轮最终现场实际读数**：writer 完整待写文本 **`14,223,730` 字节／`4e8b7a63c0b089a0fa51354ca2501a3876f77cc5f19eaafed5860925f78d2dd8`**（可解析为完整 checkpoint；本轮批次名与时间戳不同，故与 R1 现场数值不同——**旧回执更正值以上表 §1 的 R1 现场读数为准**）。
- **G6 既有三方向**已补齐 `later_cli`（保留改动现场、撤销 wrapper 后新进程 CLI 仍拒绝）与 `restored_positive`（恢复原件后退出 0），以及 `public_entry`／`arguments`／`batch_dir`／完整异常（类、消息、`stage`、`reasons`、cause 链、逐帧 traceback）与完整调用顺序。

## 6. 真实计数（本轮实际留痕导出）

CLI：start 30／status 51／record 28／prepare-gate2 27／record-gate2 25／screen-rules 21（成功 16＋前提拒绝 5＋运行失败 0）；进程内公开宿主 API **18**（含经 helper 进入的 `inspect_dev_batch`）；控制器进程内**按函数分列** create 0／prepare 18／record 36／check 129（合计 183；check+record 子集 165 已标注）；筛查核心进程内 **5 = 宿主执行 4 + 测试直接再调用 1**（CLI 内部记 `null`，成功 CLI 数 16 另列）；接收 **30**／checker **30**（双向 missing/unregistered 均为空）；副本 1；故障注入 24；模拟决定 53；**真实批准 0**。normalize/load 本进程未进入记 **0**。

## 7. 保护结果

- 主基线 `data/reviews/task013_r1_20261012_052724/source_hashes_after.json`（63204 项）：**恰为本轮授权的三个既有文件变化、缺失 0**（宿主／测试／指南）。
- 更早按累计授权集合核对：`task013`（58748）三项累计；`task012_r2`（53983）仍仅宿主+指南两项；`task009_r2`（14691）及更早 13330／12546／10236／8547／6511／4902／874 **全 0 变化、0 缺失**。
- 冻结上游与三个旧测试逐项未变（控制器 `a6b7b8e1`、接收器 `52195620`、checker `a7e5eb67`、标准化 `a2bae49e`、装载器 `1abfad89`、schema `7e0c6463`、**筛查核心 `1b123766`**、复算 `8fe75bfe`、底稿 `f4998d92`、SPEC `5df632ed`、契约 `af405cb6`、旧测试 `852bf336`／`11d4fe57`／`184ccb39`）；旧回执、历史批次、GPT QA 与基线未回写。
- 三个交付文件 UTF-8 无 BOM；本轮临时补丁脚本按**显式白名单**删除，无 `__pycache__` 残留，未使用通配符清理、未删除项目外文件。

## 8. 失败尝试（均为本轮真修，未放宽断言）

1. 新组首个 builder 返回了 `run_cli` 的结果字典而非批次路径 → `_tree` 报 `AttributeError`；改为显式 `start` 后返回路径（`task013r2_run_01`）。
2. `gate1_approved` 误用走到 `DEV_GATE2_APPROVED` 的 `chain_to_approved`；筛查基线被同一 builder 建了两次导致 `start` 冲突 → 改为 0002 正确停点与本组单独建链（`run_02`）。
3. F02 基线误用 `copy_batch`：副本的 `artifacts.database_path` 按批次相对路径派生，被宿主合法拒绝（非本轮缺口）→ 改为专用新批次（`run_03`）。
4. 探针循环末尾把**改动后的**内容写回，污染后续两项 → 改为循环结束保持原件恢复（`run_04`）。
5. `_full_exception` 定义位置晚于 G6 调用点（会 `NameError`）→ 前移到 helper 区（`run_05` 前）。

## 9. 未执行与边界

- 未执行：独立复算（R01—R04 之外）、可读事实底稿、AI 建议、人类判断保存、正式契约、真实 Gate、UI／真实 ERP／OCR／RAG、并发锁／断电试验、无边界 fuzz、TASK-014；未重跑 TASK-002—012 整套历史入口（三个旧测试入口未改未跑，本卡最小回归由新入口覆盖）。
- 边界：本地哈希只证明字节一致；不声称断电持久性、并发锁、身份认证或同权限防篡改；此处验证的是**已承诺的有界调用内变化检查**。`0005` 是宿主**筛查完成凭证**，**不是** Gate2 放行，也不代表整个 `SCREEN_AND_BUILD_FACTS` 动作或项目完成。
- 真实批准恒 **0**、`next_step_allowed=false`、workflow 未新增请求或决定。
