# TASK-011-R1 执行回执（恢复收尾、产物绑定与真实计数）

任务：关闭 F01—F04 四组缺口。日期：2026-10-11。执行端：DeepSeek。
依据：`docs/tasks/TASK-011-R1.md`、`docs/reviews/REVIEW_TASK_011.md`。状态：完成并自检通过（退出 0、failures 空），**停在 DEV_GATE2_PENDING**；未实现或提交任何 Gate2 决定，未推进 TASK-012。

---

## 1. 结论摘要

| 缺口 | 修复与证据 |
| --- | --- |
| **F01 失败诊断不被完整 0003 掩盖** | 失败/未完成状态接入 `status`／`record`／`prepare-gate2` **共用恢复协议**（不再只在 `revision < 3` 时看失败记录）：只要 `workflow/gate2/failure.json` 完整有效，即使存在可解析的完整 `0003` 也不返回 READY，按保存类别映射 2／1 并复现 stage 与原因。失败文件**先校验后使用**：非普通文件、非法 JSON、缺必需字段、版本非固定值 → `WorkflowHostBlocked` + 字段路径。原 40 字节 `0003` 半文件的协议阻断保留（`g10_f01_half_0003` ✓）。成功批次不得存在 `failure.json`（`g10_f01` 正向 ✓） |
| **F02 收尾复测全部已消费产物** | 在**最后一次所需控制器调用之后、返回成功之前**按固定路径复测 `normalized.json`／`load_report.json`／`artifacts.json`／数据库／宿主清单／`0001-0003` 全部 checkpoint 字节，并断言不存在 `failure.json`；期望值取自**初次材料核验**（发生在纯 `prepare_dev_gate` 重放之前），不再事后重读。三个有界探针各命中 1：status 重放返回时改数据库、同一时点改 `load_report.json`、实际 prepare 的第二次重放返回时改 `load_report.json`；三例**本次调用即拒绝**，撤销 wrapper 后新进程 status 也拒绝；未变化正向不误拒 |
| **F03 artifacts 字节引用与语义核验** | `0003.operation.artifacts_file_sha256` 保存 `artifacts.json` **实际文件字节哈希**（与对象规范指纹分开、无自引用）；恢复时先核形状/类型/必需键，再逐项核验 `artifacts_version`／`prepare_version`／`checkpoint_version` 固定值、`batch_id`／`output_relative`／`database_path` 推导一致、`host_manifest_file_sha256`／`previous_checkpoint_file_sha256`、两个文件字节哈希、`normalized_payload_sha256`、`database_sha256`、`gate1_decision_sha256`（并等于 Gate2 前序决定指纹）。缺形状/错类型一律 `WorkflowHostBlocked` 带字段路径，未退化为 KeyError/TypeError/WorkflowHostError。GPT 五个反例全部定向命中（见 §4） |
| **F04 真实调用留痕计数** | 计数全部由本轮实际留痕导出（`receive_invocation.json`、测试侧启动登记、`checker_invocation.started`、计数包装的实际调用、副本登记、故障命中）；**一一对应**审计（登记启动 ↔ 独立调用记录；多一条未登记记录可识别）；隔离自测覆盖“少一条记录”与“多一条未登记记录”；`blocked_rejections` 常量已删除，改为从真实负向调用与探针记录导出；进程内与 CLI 次数分列（CLI 未观测 `null` + 按成功 CLI prepare 推导）；G6 故障前的真实 `normalize`／`load` 调用已计入 |
| **版本** | 宿主 `TASK-011-workflow-host-1.1`、清单 `TASK-011-host-manifest-1.1`、checkpoint `TASK-011-checkpoint-1.1`、`artifacts_version=TASK-011-gate2-artifacts-1.1`、`failure_version=TASK-011-gate2-failure-1.1`；不迁移旧批次、不放宽旧版本绑定（`g4_legacy_version` 仍拒 TASK-010 清单 ✓） |
| **回归** | 原九组（G1—G9）全部保留并继续通过；新增 G10（本轮 F01—F04 定向探针）→ 本轮实际 **10 组**，**失败 0、退出 0** |

## 2. 交付物与路径

| 文件 | 完整 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\run_demo_workflow.py` | `e950895a747d1c2e9ec2e46ff86e733b83df13dc577ff14d985a18ca88a8fe55` |
| `D:\harness work\audit_sa_project\tests\test_prepare_demo_gate2.py` | `5ee6c4bda600e59280ec8aa2c79451accca5c1a7f08e36af15f5a6018e1b7c1a` |
| `D:\harness work\audit_sa_project\docs\WORKFLOW_HOST_GUIDE.md` | `6861fec23bebb25f5f929b5bd99f90404a40e85d98ae9c2e1dada8ff21c3c8e4` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_011_R1.md` | 本文件（新增） |

**三条产物路径（供独立复验）**

- 测试容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task011r1_final_01`（1 目录 / **204 文件**；含 `summary.json`／`checks.json`／`cli_logs.json`／`cli_logs/`／`count_audit.json`／`self_tests.json`／`final_readback.json`／`r1_receipt_evidence.json`）
- 批次父目录：`D:\harness work\audit_sa_project\data\batches\task011r1_final_01`（326 目录 / **683 文件**；31 份 `0003.json`，**0 份 `0004.json`**）
- 外置开发数据库目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task011r1_final_01`（50 目录 / 33 文件，各批次 `audit.sqlite3`）

过程容器（保留现场，不回写）：`task011r1_01`～`04`、`task011r1_smoke(2|3|4)`、`task011r1_dbg` 及其对应 `data\batches\...` 与 `data\sqlite_tests\workflow_gate2\...` 目录。

## 3. 真实命令、退出码与计数

```powershell
& $py -B -c "src = open(r'...\tests\test_prepare_demo_gate2.py', encoding='utf-8').read(); compile(src, 'x', 'exec')"   # 源文本 compile OK
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec')"        # 源文本 compile OK
& $py -B 'D:\harness work\audit_sa_project\tests\test_prepare_demo_gate2.py' --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task011r1_final_01'   # 退出码 0，failures=[]
```

本轮实际计数（全部由留痕导出，不硬编码、不照抄 15/15）：

| 项目 | 本轮实际 | 口径 |
| --- | --- | --- |
| CLI `start`／`status`／`record-simulated-decision`／`prepare-gate2` | **23 / 34 / 21 / 9** | 真实子进程调用 |
| 公开宿主 API | **16** | `start_dev_batch`／`inspect_dev_batch`／`record_simulated_gate1_decision`／`prepare_dev_gate2` 的进程内调用 |
| 私有探针调用（直接调用接收器） | **1** | G4 `plain_receive` 直接 `_run_receiver`，不计公开 API |
| 控制器造样／控制器调用 | **19** | 测试副本重定向与探针重放 |
| **receiver 实际启动** | **24** | **宿主启动 23**（每条 `receive_invocation.json`）+ **直接／私有启动 1**（无宿主调用记录，测试侧登记真实命令与真实退出码） |
| **checker 实际启动** | **24** | 24 个接收身份的 `checker_invocation.started` 全部 `true`（含 `c12_blocked`=`BLOCKED_QUALITY`/exit 1 与 `runtime_failed`=`FAILED_RUNTIME`/exit 2；失败不等于未启动） |
| 进程内标准化／装载 | **11 / 10** | 计数包装真实上游，**故障前调用也计**（G6 各 1 次） |
| CLI 子进程内标准化／装载 | **未观测（`null`）** | 不可直接观测；另按成功完成的 CLI `prepare-gate2` 推导并分列 = **6 / 6** |
| 副本 | **16** | 统一登记来源后排除，不计真实接收 |
| 故障注入 | **27** | 命中计数逐项 >0 |
| 拒绝（真实负向调用） | **37** | 由 CLI 日志 `expect_exit ∈ {1,2}` 导出；探针层定向拒绝记录 28（子集） |
| 模拟决定（成功保存） | **20** | 由成功 `record-simulated-decision` 导出 |
| **真实批准** | **0** | `gate1_approval`／`gate2_approval` 抽样均为 `null` |

**计数审计（一一对应，`count_audit.json`）**：`registered_starts=24`、`host_invocation_records=23`、`direct_receiver_starts=1`、`receiver_total=24`、`receive_identities=24`、`checker_started_total=24`，`unregistered_host_records=[]`、`missing_records=[]`、`unregistered_identities=[]`、`missing_trace=[]`。
**隔离自测（`self_tests.json`）**：`probe_matcher`（类别正确但原因不符必须判失败）✓、`count_audit`（内存副本去掉一条启动记录 → 判不一致；补一条未登记记录 → 识别）✓，均不污染正式 failures。
说明：对全部 `batch_manifest.json` 不做副本排除的原始扫描为 40 个 `started=true`（24 真实 + 16 副本，副本携带其来源清单），正是登记副本数与排除逻辑的交叉印证。

## 4. F01—F04 定向命中（field path / 目标原因）

- **F01**：`g10_f01_failure_record` — 真实 writer 完成完整 `0003` 后抛 `WorkflowHostError`（`__cause__=OSError(SENTINEL-F01-POST-WRITE-OSERROR)`），注入命中 **1**；`prepare` 返回失败、`0003` 存在、`failure.json` 落盘（`failure_version=TASK-011-gate2-failure-1.1`、`stage=post_write_verify`、`exception_class=WorkflowHostError`、`observed_outputs` 为对象）；撤销 wrapper 后**新进程 status 退出 2** 并复现 sentinel 原因（不再 READY）。
  变体全部协议阻断：`failure.json.failure_version`（未知版本）、`failure.json.reasons`（缺字段）、`failure.json`（非法 JSON）、`failure.json`（非普通文件）、`0003.json`（40 字节半文件）。
- **F02**：`g10_f02_status_database`（`audit.sqlite3`）、`g10_f02_status_load_report`（`load_report.json`）——注入各 **1**，**本次 status 退出 1** 且消息含“收尾复测”，撤销后新进程 status 也拒绝（`database_sha256`／`load_report_file_sha256`）；`g10_f02_prepare_second_replay`——真实 prepare 重放 **2** 次，第 2 次返回时改 `load_report.json`，**本次 prepare 阻断**、撤销后 status 拒绝；`g10_f02_positive_control` 未变化正常批次 `status=0 / DEV_GATE2_PENDING`（真实 before/after 哈希逐项留痕）。
- **F03**：`operation.artifacts_file_sha256`（仅给 artifacts 追加换行、语义不变）、`artifacts.json.database_sha256`、`artifacts.json.normalized_payload_sha256`、`artifacts.json.gate1_decision_sha256`、`artifacts.json.host_manifest_file_sha256`、`artifacts_version`（未知版本）、`checkpoint_version`——各命中目标字段；语义反例在**新 QA 副本**上同步了 artifact 文件新哈希与 `0003` 摘要副本（造样，不宣称上游重算，不改业务事实）。
- **F04**：见 §3；`blocked_rejections` 常量已删除。

## 5. 保护结果

- 主基线 `data/reviews/task011_20261011_133022/source_hashes_after.json`（**28489** 项）：变化 **3**（本卡授权三文件）、缺失 **0**。
- 更早基线累计变化分别说明：`task010_r4`（26215）→ 2 项（宿主 + 指南；当时新测试尚不存在）；`task010`（16340）→ 3 项（宿主 + 指南 + 旧宿主测试）；`task009_r2`（14691）→ **0 变化 0 缺失**；13330／12546／10236／8547／6511／4902／874 基线同样保持 0 变化 0 缺失。
- 冻结上游逐项核对未变：控制器 `a6b7b8e1`、接收器 `52195620`、checker `a7e5eb67`、标准化 `a2bae49e`、装载器 `1abfad89`、schema `7e0c6463`、SPEC `5df632ed`、契约 `af405cb6`、旧入口 `test_run_demo_workflow.py` `852bf336`。
- 测试内建 13 个受保护文件前后哈希一致；旧回执/任务卡/验收单、GPT 证据、旧批次与数据库、合成 Excel/答案册均未回写。
- 未安装依赖、未初始化 Git、未改装载路径限制与控制器、未加生产测试开关；使用 `-B` 与禁写 bytecode，语法检查用编译源文本；交付文件 UTF-8 无 BOM。

## 6. 失败尝试（如实记录）

1. 失败诊断写入仍用旧版本字面量 `TASK-011-gate2-failure-1.0`，升版后首个 F01 冒烟被版本校验先拦住 → 改为统一使用 `FAILURE_VERSION` 常量。
2. status 的 F02 探针首版未命中：期望值在链核验**之后**才重读，读到的已是被改动的字节 → 改为由 `_verify_prepare_operation`（初次材料核验，位于纯重放之前）把期望值带出链核验，status 与 prepare 收尾统一比较。
3. F02/F03 探针首版用**子进程**调 CLI，进程内 wrapper 不生效（注入 0 命中）→ 改为同进程调用公共 API 与其冻结控制器包装。
4. F01 变体首版用复制批次，复制会改变推导数据库路径，使路径类核验先于失败诊断触发 → 改为在**全新的本版本批次**上真实构建后再注入。
5. F01 变体的 `retarget_copy` 会删除 `failure.json` → 弃用该路径，改为“构建 + 注入 + 定点改写”。
6. F02“撤销后未拒绝”一次：断言用的期望原因写成了 `audit.sqlite3`，而实际恢复诊断落在 `operation.database_sha256` → 改为按字段名断言后续拒绝原因。
7. 拒绝计数一次不一致（12 ≠ 37）：探针记录只覆盖部分组 → 改为以真实负向调用（CLI 日志）为准，并把探针记录作为子集核对。
8. 静态守卫曾误判 `.sql` 裸词 → 沿用既有结构化检查（本轮未改动该检查）。

## 7. 未执行（不写通过）

Gate2 决定的实现与提交、`record`/`prepare` Gate2、R01—R04 规则筛查、独立复算、事实底稿、AI 建议、正式契约、真实 Gate 签署、人类判断保存、UI、真实 ERP、并发/锁/断电持久性、无边界 fuzz；未重跑 TASK-002—010 整套历史入口（冻结的旧 `test_run_demo_workflow.py` 未运行，其历史静态范围断言不适用于本版本新增的下游动作）。

**停止声明**：停在 **DEV_GATE2_PENDING**（**不是** Gate2 已放行）；未实现或提交任何 Gate2 决定、未建立正式契约、未签真实 Gate、未保存人类判断、未生成 AI 建议、未推进 TASK-012；未修改任务看板，未宣布任务完成。
