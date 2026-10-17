# TASK-010-R3 执行回执（恢复未知接收声明，完成一致的验证产物）

任务：闭合 F03 的“接收清单不可读”分支与 F05 的最终汇总／必需证据。
日期：2026-10-11。执行端：DeepSeek。
依据：`docs/tasks/TASK-010-R3.md`、`docs/reviews/REVIEW_TASK_010_R2.md`。状态：完成并自检通过，**停住等复验**；未推进 TASK-011。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **F03 清单不可读** | 失败清单新增接收**声明状态**三分：`ACQUIRED`／`NOT_ACQUIRED`／`ACQUIRED_CONTRADICTORY`（附 `declared_batch_status`／`declared_exit_code`／`declaration_read_error`）。校验器按声明状态分支：未取得时 `batch_status` 必须如实为 `null`（**不得按退出码补造 READY**）；已取得但矛盾时必须保留原样观察值并归为宿主协议失败。成功路径协议不放松，receiver 自身 1／2 分支不变 |
| **F05 最终产物** | 调整顺序为「完成全部检查与统计 → 形成同一最终结果对象 → 一次落盘 summary／checks／cli_logs／count_audit → 读回逐项比较 → 输出与退出码」；读回矛盾或缺项判失败且不报告通过，落盘后不再改变计数。计数改为**登记的真实启动与独立调用记录一一对应**（CLI 与 API 分列、预启动拒绝不计、副本统一登记来源并排除），不再只比较总数 |
| **F05 writer 证据** | `FaultyHandle.write()` 递增真实写入计数；断言目标打开／write／OSError **各 1**、部分字节 >0 且小于该次**完整预期 checkpoint** 字节数；保存完整异常类、message、`__cause__` 类型与 message、sentinel 与一致性、旧 `0001` 前后字节哈希并断言相同（不只检查存在）、目标文件大小、写入／抛错计数与恢复结果。新增隔离 helper 自测：**类别正确但目标原因不符必须判失败**、类别+目标原因相符判通过，结果单列 |
| **计数自测** | 新增隔离计数核验自测：在**新内存审计对象**中去掉一条调用记录、保留对应启动事件，核验函数必须判不一致（自测结果 `ok=True`；未改动任何真实文件或历史证据） |
| **版本** | 宿主 `TASK-010-workflow-host-1.3`；清单 `TASK-010-host-manifest-1.3`；指南中残留的 checkpoint 1.1 文案同步为实际的 `TASK-010-checkpoint-1.2`；不迁移旧批次 |
| **开发验证** | 真实接收 **17**、checker **16**（1 份清单被替换为非文件，如实记 `unreadable_manifests`）、副本 **17**、writer 部分字节 **40**、模拟决定 **3**、**真实批准 0**、故障注入 **26**；CLI start 16／status 33／record 17；公开宿主 API **9**、控制器造样 **3**；**测试失败 0，退出 0** |
| **历史保护** | R2 基线（21691 项）、R1 基线（18533 项）、TASK-010 基线（16340 项）均**恰为本卡授权三文件的累计变化**（变化 3、缺失 0）；14691／13330／12546／10236／8547／6511／4902／874 基线全部 **0 变化、0 缺失**。上一轮回执中“16340 基线 0 变化”的表述不准确：应为累计三项授权变化；旧回执不改，此处更正 |

## 2. 文件与产物

| 文件 | SHA-256 |
| --- | --- |
| `scripts\run_demo_workflow.py` | `d42aeec3a4450d630507821e103e5b923c052e91e790644df143f5311e9475d0` |
| `tests\test_run_demo_workflow.py` | `e9554ca739753f43567eb7907ac4b11dfe8d3148a1d7b8b072cd98081dd092cc` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `2c164eff0c6e46c5d3de372c0105ccf6736a1c19db7664ff8e3e0bac89038cb3` |
| `docs\EXEC_REPORT_010_R3.md` | 本文件（新增） |

- 测试容器：`data\workflow_host_tests\task010r3_03`（161 个文件；`summary.json`／`checks.json`／`cli_logs.json`／`cli_logs/`／`count_audit.json`／`self_tests.json`／`final_readback.json`）。
- 批次与副本：`data\batches\task010r3_03`（34 个叶子目录 / 455 个文件）。
- 过程容器：`task010r3_01`／`02`、`task010r3_smoke*`（保留现场）。

## 3. 实际命令与退出码

```powershell
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0
& $py -B -c "src = open(r'...\tests\test_run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_run_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task010r3_03'   # 0
```

```text
CLI 调用：start 16、status 33、record-simulated-decision 17；宿主 API 直接调用 9；控制器造样 3
真实接收启动 17 次（入口侧 13）、checker 运行 16 次（入口侧 12）、批次副本 17 份、
真实 writer 故障命中 1 次（部分字节 40）、模拟决定 3 条、真实批准 0 条、故障注入 26 次
[PASS] R3 隔离自测：计数核验可发现缺留痕；故障匹配器要求类别+目标原因一致
[PASS] R2_COUNT_AUDIT 计数与调用记录一一对应（接收 17、checker 16、副本 17）
[PASS] R3_FINAL_ARTIFACT_READBACK 最终汇总与审计一次落盘并读回一致
测试失败 0；受保护文件前后哈希一致: True（18 个）
```

入口侧 13/12 低于记录 17：CLI 侧只在成功创建批次时累加，而 T02／H01／H02／协议对照经**进程内 API** 真实启动接收器；一一对应核对显示**缺记录清单为空**（无未留痕启动）。

## 4. F03 实测

- **H02（清单不可读）**：真实 receiver 返回 0 后，仅在新故障批次把 `batch_manifest.json` 原路径替换为目录（原文件保留为 `batch_manifest.original.json`），注入命中 1。`start` 抛 `WorkflowHostError`；失败清单：`status=FAILED_RUNTIME`、`host_result={layer:HOST, exit_code:2}`、`receive.exit_code=0`、`batch_status=null`、`declaration_status=NOT_ACQUIRED`、`declaration_read_error` 记录具体 `PermissionError` 路径、无 bindings／请求、`checkpoints: []`、无 checkpoint 目录。新进程 `status` 返回 **2** 并复现原清单读取原因（不再要求声明为 READY）。
- **协议对照（声明矛盾）**：同类操作后仅把清单 `batch_status` 改为 `BLOCKED_QUALITY`（真实退出码仍 0）→ `start` 返回 **1**，保存 `host_result={layer:HOST, exit_code:1}` 与原样观察值 `declared_batch_status=BLOCKED_QUALITY`；新进程 `status` 仍返回 **1** 并恢复原协议诊断（未退化为“失败清单自身非法”）。
- **回归保持**：H01（材料读取失败）、receiver 质量失败（C12 → 1）与运行失败（非 ZIP → 2）、命令长度／值／类型三种核对、合法成功与三种模拟决定、checkpoint 延续与写后变化测试全部继续通过；旧纯接收批次仍不被接管。

## 5. F05 实测证据

- **writer**：目标打开 1、真实 write 1、`OSError` 1，部分字节 **40** < 该次完整预期 checkpoint 下界 **368**；异常类 `WorkflowHostError`，`__cause__` 为 `OSError` 且 message 与 sentinel 完全一致；旧 `0001` 前后字节哈希相同（未变）；半文件保留；后续 `status` 拒绝；未报告提交成功。
- **隔离自测**（`self_tests.json`）：计数核验自测在去掉一条记录的**内存副本**上判不一致（`ok=True`）；故障匹配器自测三项（类别+原因相符→通过、类别正确原因不符→**失败**、类别不符→失败）`ok=True`；两项自测结果单列，未向正式 `failures` 塞入假失败。
- **最终产物**（`final_readback.json`）：`summary.json`／`checks.json`／`cli_logs.json`／`count_audit.json` 一次落盘后读回规范内容逐项一致，`summary` 与 `count_audit` 的接收／checker 次数一致，`checks`／`failures` 数量与内存一致，`ok=True`、`readback_problems=[]`。

## 6. 历史保护、边界与未执行

- 保护基线 `data/reviews/task010_r2_20261011_114828/source_hashes_after.json`：21691 项，变化 **3**（本卡授权三文件）、缺失 **0**；18533 与 16340 基线同为累计三项变化；14691／13330／12546／10236／8547／6511／4902／874 全部 0 变化、0 缺失；测试内建 18 个受保护文件前后哈希一致；旧回执、旧任务卡／验收单、历史现场与 GPT 证据未回写。
- 冻结 receiver／checker／控制器与全部上游未改；未装依赖、未初始化 Git、未加生产故障开关；使用 `-B` 与禁写 bytecode，语法检查用编译源文本（未产生 `.pyc`）。
- 未执行：TASK-011、`prepare` Gate2、标准化／SQLite／规则／复核／底稿／AI、正式契约、真实 Gate、人类判断、UI、真实 ERP、并发／超时重试／安全隔离、无边界 fuzz；未重跑 TASK-002—009 全套。
- 本地哈希只证明字节一致，不证明来源真实；不提供身份认证；不抵御同权限篡改；模拟决定只是开发态测试样例，**不是**真实批准。

## 7. 失败尝试

1. 审计扫描 `batch_manifest.json` 时命中 H02 被替换为目录的路径 → `PermissionError`；改为跳过非文件并如实记入 `unreadable_manifests`（不据此推进 checker 计数）。
2. 计数审计初版只比较总数、无法发现“启动无留痕” → 改为登记真实启动（CLI + API）与调用记录**一一对应**，并加内存副本自测。
3. 前一轮遗留的 `summary["counts"]` 提前赋值与新的最终落盘冲突（UnboundLocalError）→ 移除提前赋值，保证“先统计、再一次落盘、后读回”。
4. 补丁锚点与文件实际缩进不符导致批量替换中断 → 改为逐条精确锚点并在每批后编译校验（文件未被中途写坏）。
