# TASK-013-R1 执行回执（恢复协议与测试证据修复）

任务：关闭 F01（最后一次报告消费绕过一致性核验）、F02（筛查引用/元数据语义核验不完整）、F03（失败记录缺本批次与宿主身份）、F04（探针时点、留痕与计数）。
日期：2026-10-12。执行：DeepSeek。依据：`docs/tasks/TASK-013-R1.md`、`docs/reviews/REVIEW_TASK_013.md`。
状态：**完成并自检通过（退出 0、10 项检查全 PASS、failures=[]）**，停在 **DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED**；未新增 0006，未执行独立复算/事实底稿/AI，未建契约、未签真实 Gate，未推进 TASK-014。

---

## 1. 交付文件完整 SHA-256 与版本

| 文件 | SHA-256 |
| --- | --- |
| `scripts/run_demo_workflow.py`（改） | `95b2a2d2860ec0e122035ee8cb887f15ba9831fd3256bfb6f2fae126604183ed` |
| `tests/test_screen_demo_workflow.py`（改） | `14e96b7567ea6cab0ba9fd13d48a25b2f928fefb80517155f245a30e3c44c000` |
| `docs/WORKFLOW_HOST_GUIDE.md`（改） | `f2bbb6faae16647023abf789a2e611012023ff73b856fa096ddcf5a475f47345` |
| `docs/EXEC_REPORT_013_R1.md`（新增，本文件） | 自哈希不内嵌（避免自引用），在交付说明中单独报告 |

- 起点：宿主 `2e54e1d7…`、测试 `7a4d831c…`、指南 `5d1e7319…`（均已按卡修改）。
- 版本：**实现版本 `TASK-013-workflow-host-1.1`**；**既有协议版本未改名**（`CHECKPOINT_VERSION`／`HOST_MANIFEST_VERSION` 仍 `TASK-012-*-1.0`，`TASK-013-screen-start/artifacts/failure-1.0` 不变）。

## 2. 三条完整产物路径

| 项目 | 路径 |
| --- | --- |
| 测试容器 | `D:\harness work\audit_sa_project\data\workflow_host_tests\task013r1_final_01`（345 文件；含 `probe_records/` 17 份、`core_returns/` 5 份、`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`entry_events.json`／`self_tests.json`／`final_readback.json`） |
| 批次父目录 | `D:\harness work\audit_sa_project\data\batches\task013r1_final_01`（509 文件；**19 份 0005、0 份 0006**） |
| 外置数据库父目录 | `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task013r1_final_01`（21 文件） |
| MAIN 线索报告 | `…\data\batches\task013r1_final_01\main_01\workflow\screening\screening_report.json` |
| MAIN 筛查凭证 | `…\data\batches\task013r1_final_01\main_01\workflow\checkpoints\0005.json` |
| 完整新故障记录 | `…\task013r1_final_01\probe_records\`（G5 writer 现场 `g5_partial_write_0005.json`、`g5_complete_then_throw.json`；G6 四方向；F02 P01—P06；F03 四项 + 恢复） |
| writer 完整待写文本 | `…\task013r1_final_01\g5_writer_full_expected_0005.json`（原 UTF-8 字节另存） |

## 3. 真实命令与退出码

```text
D:\harness work\audit_sa_project\.venv\Scripts\python.exe -B tests\test_screen_demo_workflow.py --out-dir D:\harness work\audit_sa_project\data\workflow_host_tests\task013r1_final_01
→ 退出 0；10 项检查全部 PASS；failures=[]；13 个受保护文件前后一致
```

源文本编译检查：宿主与本测试各自 `compile()` **OK**（不生成 pyc）。过程容器 `task013r1_run_01`（首次暴露 G1/G8 两处测试口径问题）、`task013r1_run_02`（全绿）保留。

## 4. F01 闭环：最后一次报告消费不再绕过核验

- **修法**：`status` 构建筛查摘要所消费的读数（报告／started／artifacts 文件字节）**必须逐项等于 `0005.operation` 初始声明**；报告对象规范指纹必须等于 `0005` 声明值；摘要的 artifacts 取**磁盘已验证对象**并与 `0005` 内嵌副本严格相等；并在**最后一次必要控制器调用与最后一次数据消费之后**再追加一次 `_verify_screen_tail`（含 0005 自身字节），因此不再存在“摘要用新读数、最终复测早已跑完”的窗口。
- **有界回归** `g6_f01_report_tail_change`：在 status 最后一次报告读取（原缓冲）返回之后仅改报告 `findings` → **本次 status 即退出 1**（`WorkflowHostBlocked`，原因指向 `screening_report.json`），命中 1，before `d2b9f99c…` ≠ after `5e43de00…`；撤销 wrapper 后新进程 status 仍非 0。完整记录见 `probe_records/g6_f01_report_tail_change.json`。

## 5. F02 闭环：筛查引用逐项按协议核验

宿主新增核验：`operation.report_relative`／`artifacts_relative` 必须是**固定相对路径且严格字符串**；`started.host_version`／`artifacts.host_version` 必须**等于当前 HOST_VERSION**；`artifacts.host_manifest_file_sha256` **只等于初始实读宿主清单文件字节哈希**（**已删除 bindings 内容指纹的 OR 分支**）；`operation.artifacts` 保留完整内嵌副本，**先验对象/必需键/类型，再与磁盘已验证 artifacts 完整严格相等**；status 不再从内嵌副本取截止日/数据库路径/版本。

GPT 五个反例 + 一项形状对照（均从新专用小样 C02 合法基线出发，仅在新现场同步派生引用哈希，逐项留痕并恢复原位后正向通过）：

| 探针 | 变更 | 目标命中（本次即拒绝） |
| --- | --- | --- |
| F02_P01 | `operation.report_relative` → 不存在的文件 | `report_relative`（固定路径） |
| F02_P02 | `artifacts.host_manifest_file_sha256` → bindings 内容指纹（同步文件引用） | `host_manifest_file_sha256` |
| F02_P03 | `artifacts.host_version` → WRONG-HOST-VERSION | `host_version` |
| F02_P04 | `started.host_version` → WRONG-HOST-VERSION（同步 artifacts/0005 引用） | `host_version` |
| F02_P05 | 仅 `0005.operation.artifacts.cutoff_date` → 1900-01-01（真实 artifacts 仍 2026-09-30） | `operation.artifacts`（内嵌副本严格相等） |
| F02_P06 | `0005.operation.artifacts` → 字符串（形状对照） | `operation.artifacts` |

六项均 `WorkflowHostBlocked` / 退出 1、恢复原件后 status 退出 0。完整记录见 `probe_records/F02_*.json`。

## 6. F03 闭环：失败记录绑定本批次与宿主

- 真实 `_save_screen_failure` 现在写入 `batch_id`（批次叶子）与 `host_version`（当前实现版本）；`_load_screen_failure` 要求二者**存在、类型正确且分别等于当前批次/当前实现版本**；`target_exit_code` 要求**严格 int（排除 bool/float）且为 1 或 2**；其余版本/阶段/异常/原因/`observed_outputs` 检查未放宽。
- 保留“完整 0005 后 sentinel 故障”回归：原命令失败、failure 落盘、新进程 status **退出 2** 并复现原原因（failure 优先于完整 0005）。
- 以该真实诊断为基线的四项有界检查：缺 `batch_id`／错 `batch_id`／错 `host_version`／`target_exit_code=true` → **均退出 1 且指向目标字段**；恢复合法诊断后 status 仍**退出 2 且复现 sentinel**（不降为 READY）。完整记录见 `probe_records/F03_*.json`。

## 7. F04 闭环：探针时点、留痕与计数

- **时点**：G6 注入器改为按 `SCREEN_AND_BUILD_FACTS` 的**真实调用序号**触发（两个入口均为第 2 次 SCREEN，即最后一次动作检查），并登记完整调用顺序 `sequence` 与**注入后控制器调用数**（三个探针均 `after_injection_calls=0`，证明注入点确为最后一次动作检查，且无未声明后续调用）。
- **真实前后值**：`before` 改为在**注入时**取得（0005 场景为真实 writer 写出并关闭 0005 之后），非 null 且与 `after` 不同；G6a 另有生产 writer 返回的 SHA 作独立交叉核对。
- **完整故障证据**：writer 完整待写文本按**原 UTF-8 字节**另存（`g5_writer_full_expected_0005.json`，`full_utf8_bytes=14223730`，SHA `092938f5…`，可解析为完整 checkpoint）；部分文件实际 40 字节（`0 < 40 < 14223730`）；旧 `0001—0004` **调用前/关闭后两组真实哈希完全相同**（落盘）；cause 类别/消息/sentinel 一致，`traceback` 完整 **11 帧**。所有 F01—F04 与 G6 探针均保存完整函数名、完整参数、真实返回或完整异常链与后续 CLI 引用（`probe_records/` 共 17 份，`checks` 只留摘要 + 可解析引用）。
- **真实计数**（本轮实际导出，未照抄旧值）：
  - CLI：start 22／status 34／record 21／prepare-gate2 21／record-gate2 20／**screen-rules 19 = 成功 14 + 前提拒绝 5 + 运行失败 0**。
  - 进程内公开宿主 API **8**（含经 helper 进入的 `inspect_dev_batch`）；控制器入口**按函数分列**：`create_dev_workflow` 0／`prepare_dev_gate` 10／`record_dev_decision` 20／`check_dev_action` 64（合计 **94**；`check+record` 子集 84，明确标注为子集）。
  - 筛查核心（进程内可观测）**5 = 宿主执行 4 + 测试直接再调用 1**；**CLI 子进程内核心次数记 `null`**，另列推导值 14 与依据（每个成功 `screen-rules` 恰好调用一次核心）。
  - 接收 22／checker 22（双向 `missing_records=[]`、`unregistered=[]`）／副本 1／故障注入 24／模拟决定 41／**真实批准 0**。
  - **缺记录自测**改为删除一条**对应的实际记录**（`c03_merged`）→ 共用规则判定 `missing` 非空且 `verdict=FAIL`；再加一条未登记记录 → `unregistered` 非空且 `verdict=FAIL`；两者均证明**正式判定会翻为 FAIL、入口非零**，自测与正式 `failures` 隔离。
- **筛查入口对应**：每个 0005 批次都对应到一次真实入口（进程内宿主调用或成功 CLI 日志），`cli_success_without_0005=[]`。
- **G1**：MAIN 筛查改为**进程内**真实调用以捕获宿主该次核心返回；断言宿主恰好真实调用 1 次且**其返回与落盘报告严格相等**；第二次调用明确标注为“同输入独立再调用（仅业务对照）”。
- **最终落盘**：`summary/checks/counts/cli_logs/entry_events/self_tests` 一次保存并逐项读回一致；`FINAL_ARTIFACT_READBACK` **独立单列**于 `final_readback.json` 并如实打印（持久化检查条目 **10** 条 + 保护核对），不再混称已入 `checks`。

## 8. 业务回归保持

MAIN 报告仍是 **12 条 = R01 3／R02 5／R03 2／R04 2**，R02 应付超额 **1,600,000** 分；付款 **267,949,329**、退款 **700,000**、净额 **267,249,329 = 266,249,329 + 1,000,000**（缺关联保留、未误拦）；`0005` 的 `revision=5`、`operation.kind=RUN_RULE_SCREEN`、`previous_file_sha256` = 初始实读 0004 字节哈希、workflow 与 0004 严格相等、phase 仍 `DEV_GATE2_APPROVED`、模拟决定恰 2、真实批准 `null/null`、`next_step_allowed=false`；**0 份 0006**。既有三种模拟决定、三个小样（C03/C07b/C06b）、阶段与重复拒绝、0005 篡改、旧链重放、只读守卫、无复算/底稿/LLM/答案册调用均保留通过。

## 9. 保护结果

- 主基线 `data/reviews/task013_20261011_194832/source_hashes_after.json`（58748 项）：**恰好 3 项变化**（宿主、测试、指南），**缺失 0**。
- 更早基线按各自授权集合：`task012_r2`（53983）**仅宿主+指南 2 项**；`task012_r1`（50404）3 项；`task011_r2`（39831）2 项；`task009_r2`（14691）与 13330／12546／10236／8547／6511／4902／874 **全部 0 变化 0 缺失**。
- 冻结上游与三个旧测试逐项未变（控制器 `a6b7b8e1`、接收器 `52195620`、checker `a7e5eb67`、标准化 `a2bae49e`、装载器 `1abfad89`、**筛查核心 `1b123766`**、复算 `8fe75bfe`、底稿 `f4998d92`、schema `7e0c6463`、SPEC `5df632ed`、契约 `af405cb6`、旧测试 `852bf336…`／`11d4fe57…`／`184ccb39…`）。三份交付文件均 UTF-8 无 BOM。

## 10. 失败尝试与未执行项

**失败尝试（真修，未放宽断言）**：① 首轮 G1 断言“宿主真实调用核心 1 次”失败——MAIN 筛查原经 CLI 子进程（进程内不可观测），改为进程内真实调用并由观察层捕获返回；② 首轮 G8 筛查入口对应按“宿主进程内调用数”核对导致 18 vs 3 不符——改为按批次对应（进程内宿主调用或成功 CLI 日志），并新增“成功 CLI 无对应 0005”反向检查；③ F03-2 补丁锚点在 Gate2/筛查两个加载器同形，命中 2 次——改用含 `SCREEN_FAILURE_VERSION` 的长锚点（补丁断言失败即不写盘，宿主未被改坏）；④ F02-3 锚点（`bindings_sha256` 校验）出现 4 次——改用 `artifacts.batch_id` 唯一锚点；⑤ 一次遗留的 `if False else` 占位表达式已清理。

**未执行（不写通过）**：独立复算、可读事实底稿、AI 建议、人类判断、正式契约、真实 Gate、UI／真实 ERP／OCR／RAG、并发锁／断电试验、无边界 fuzz、TASK-014；未重跑 TASK-002—012 整套历史入口（本卡定向回归由新入口覆盖，旧三个入口未改未跑）。

**边界**：本地哈希只证明字节一致，不证明来源真实；不提供身份认证；不抵御同权限篡改；不声称原子快照、并发安全或断电持久性。`0005` 是宿主**筛查完成凭证**，不是 Gate2 放行，也不代表整个 `SCREEN_AND_BUILD_FACTS` 动作或项目完成。
