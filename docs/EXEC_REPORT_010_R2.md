# TASK-010-R2 执行回执（闭合操作命令、宿主失败留痕和验证证据）

任务：修复 TASK-010-R1 复验剩余三处——F02 `0001` 接收命令未核对、F03 接收成功后宿主自身失败无留痕、F05 writer 测试假阳性与计数口径。
日期：2026-10-11。执行端：DeepSeek。
依据：`docs/tasks/TASK-010-R2.md`、`docs/reviews/REVIEW_TASK_010_R1.md`。状态：完成并自检通过，**停住等复验**；未推进 TASK-011。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **F02 接收命令** | `0001.operation.receiver_command` 与**独立调用记录**逐元素、逐类型严格比较（不 `str()`／不 strip），并与宿主清单命令一致；`receiver_exit_code` 同时与调用记录一致。新增 R01 配对回归：合法批次可 status／record；仅改 `receiver_command` 为 `["OTHER-COMMAND"]` 后 status 与 record 均阻断（原因指向该字段），record 不追加 0002 |
| **F03 两层留痕** | 新增固定 `workflow/receive_invocation.json`（独占、结构化）：真实完整命令、真实退出码、stdout／stderr 文件引用与字节哈希，**先于**任何读取／分类写入，三种结果都保存。失败清单新增 `host_result`（`exit_code`／`layer=HOST|RECEIVER`／`stage`／`exception_class`／原因）与 `status=BLOCKED_PROTOCOL`；`receive.exit_code` 恒为 receiver 真实值（成功 0 不被改写）。新增 H01：receiver 实际 0/READY，宿主读取质量报告时命中真实 I/O 故障 → 保存 `FAILED_RUNTIME`/layer=HOST/exit 2 失败清单（无 bindings、无请求、无 checkpoint 目录），新进程 status 返回 **2** 并复现原因（不再称“不是本宿主创建的”），record 拒绝 |
| **F05 writer 与计数** | `FaultyHandle` 补齐 `__enter__`／`__exit__`，真实 writer 的 with 块真正进入目标 `write()`：打开 1 次、实际写入 1 次、部分字节 **40**、抛独有 sentinel `OSError` 1 次、异常链为 `WorkflowHostError.__cause__` 即该 OSError；旧 `0001` 逐字节未变、半文件保留、后续 status 拒绝、未报告成功。T01 仅注入 `0002.json`、T02 仅注入 `0001.json`（各 1 次）。计数改为按**实际调用记录**统计并交叉核对，副本（含原 G7 五份）统一登记来源，公开宿主 API 与控制器造样分开 |
| **版本** | 宿主 `TASK-010-workflow-host-1.2`；清单 `TASK-010-host-manifest-1.2`；checkpoint `TASK-010-checkpoint-1.2`；不迁移旧批次 |
| **开发验证** | 真实接收 **15**、checker **15**（按调用记录／`checker_invocation.started`）、副本 **17**、writer 部分字节 **40**、模拟决定 **3**、**真实批准 0**、故障注入 **24**；CLI start 16／status 31／record 17；公开宿主 API **7**、控制器造样 **3**；**测试失败 0，退出 0** |
| **历史保护** | TASK-010-R1 基线（18533 项）**变化 3、缺失 0**（恰为授权三文件）；TASK-010 的 16340、14691、13330、12546、10236、8547、6511、4902、874 基线均 **0 变化、0 缺失** |

## 2. 文件与产物

| 文件 | SHA-256 |
| --- | --- |
| `scripts\run_demo_workflow.py` | `d460724fa8bdcf1cceaf50702b2a1d63212e78e253f795a70d8c3fbfad5bf4af` |
| `tests\test_run_demo_workflow.py` | `1524ef6ad3555e203bb83f7a08422f27959ea89a6a337aad6767fe6acc470bac` |
| `docs\WORKFLOW_HOST_GUIDE.md` | `8d568de8e5fadc2be7a0a8784973b1f609208776e47dace33c0a0ee582486dde` |
| `docs\EXEC_REPORT_010_R2.md` | 本文件（新增） |

- 测试容器：`data\workflow_host_tests\task010r2_04`（155 个文件；`summary.json`／`checks.json`／`cli_logs.json`／`count_audit.json`／`cli_logs/`）。
- 批次与副本：`data\batches\task010r2_04`（32 个叶子目录 / 431 个文件）；`count_audit.json` 逐条列出 15 份真实接收记录（命令与退出码）与 17 份副本的来源。
- 过程容器：`task010r2_01`—`03`、`task010r2_smoke*`（保留现场）。

## 3. 实际命令与退出码

```powershell
& $py -B -c "src = open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0
& $py -B -c "src = open(r'...\tests\test_run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"  # 0
& $py -B '...\tests\test_run_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task010r2_04'   # 0
```

输出要点：

```text
CLI 调用：start 16、status 31、record-simulated-decision 17；宿主 API 直接调用 7；控制器造样 3
真实接收启动 15 次（入口侧 13）、checker 运行 15 次（入口侧 12）、批次副本 17 份、
真实 writer 故障命中 1 次（部分字节 40）、模拟决定 3 条、真实批准 0 条、故障注入 24 次
[PASS] R2_COUNT_AUDIT 计数与实际调用记录一致（接收 15、checker 15、副本 17）
测试失败 0；受保护文件前后哈希一致: True（18 个）
```

**入口侧 13/12 与记录 15/15 的差异**：入口侧只在 CLI `start` 成功创建批次时累加，而 T02（写后变化）与 H01（宿主读取故障）经**进程内 API** 真实启动了接收器；调用记录是权威口径，审计已核对一致（无未留痕启动）。旧回执的 13/12/11 与 `api_calls=9` 口径不再使用，旧回执未回写。

## 4. 三项剩余缺口的实测

- **R01**：`status` 与 `record` 均返回 1，原因 `workflow/checkpoints/0001.json.operation.receiver_command 不可用：参数个数必须与真实调用记录一致：1 != 9`（逐元素比较），未追加 `0002`；合法批次仍可 status／record（正向控制保留）。
- **H01**：注入命中 1（真实 receiver 先以 exit 0/READY 返回，随后质量报告原路径被替换为目录，原文件保留为 `quality_report.original.json`）→ `start` 抛 `WorkflowHostError`（原因：读取该材料失败、路径不是普通文件）；失败清单 `status=FAILED_RUNTIME`、`host_result={layer:HOST, exit_code:2}`、`receive.exit_code=0`（未篡写）、`checkpoints: []`、无 checkpoint 目录、材料状态如实记为 `exists:false`；新进程 `status` 返回 **2** 并复现原因；`record` 拒绝且不建 checkpoint。
- **F05**：真实 writer 故障断言全部成立（打开 1／写入 1／部分字节 40／抛错 1／异常链 sentinel OSError／旧 0001 未变／半文件保留／status 拒绝／未报成功）；T01 与 T02 各恰命中 1；负向探针均同时核验异常类别与目标原因。

## 5. 历史保护与边界

- 保护基线 `data/reviews/task010_r1_20261011_111932/source_hashes_after.json`：记录 18533 项，变化 **3**（本卡授权三文件）、缺失 **0**；更早 16340／14691／13330／12546／10236／8547／6511／4902／874 基线全部 0 变化、0 缺失；测试内建 18 个受保护文件前后哈希一致。
- 冻结 receiver／checker／控制器与全部上游未改；未装依赖、未初始化 Git、未加生产故障开关；运行使用 `-B` 与禁写 bytecode，语法检查用编译源文本（未产生 `.pyc`）。
- 未执行：TASK-011、`prepare` Gate2、标准化／SQLite／规则／复核／底稿／AI、正式契约、真实 Gate、人类判断、UI、真实 ERP、并发与压测、无边界 fuzz；未重跑 TASK-002—009 全套。
- 本地哈希只证明字节一致，不证明来源真实；不提供身份认证；不抵御同权限篡改；模拟决定只是开发态测试样例，**不是**真实批准。

## 6. 失败尝试

1. **宿主导入补丁的 PowerShell 引号**：内联脚本多次被吞掉双引号导致替换不生效 → 改用写文件方式打补丁并逐次编译校验。
2. **目录化材料先被判为“协议矛盾”**：`_material_infos` 对“存在但不是普通文件”返回 `exists:false`，使 H01 落到 `BLOCKED_PROTOCOL`(1) 而非宿主运行失败(2) → 改为抛 `WorkflowHostError`，并给失败留痕用不抛错变体，避免“保存失败清单本身失败”。
3. **`progress` 未在拒绝分支初始化**：路径拒绝用例触发 `NameError`，退出码变 2 → 把 `progress` 提到 `try` 之前。
4. **副本计数漏计**：G7 的五份副本由独立局部 helper 创建、未登记 → 统一 `register_copy` 登记来源，审计改为排除嵌套副本并以调用记录为准。
5. **审计口径**：初版把“入口侧计数”当权威导致不一致 → 改为以调用记录为准、入口侧仅作交叉核对（入口侧多于记录才判失败）。
