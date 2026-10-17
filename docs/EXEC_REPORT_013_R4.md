# TASK-013-R4 执行回执（只修 F01 的共同触发点）

任务：关闭 R3 验收唯一阻断项——F01 三个探针没有命中原任务指定的**共同边界**（status 第二次 `_read_screen_outputs` 完整返回原始对象之后）。
日期：2026-10-12。执行端：DeepSeek。验收端：GPT。
依据：`docs/tasks/TASK-013-R4.md`（唯一权威细则）、`docs/reviews/REVIEW_TASK_013_R3.md`；方法参考 `data/reviews/task013_r3_20261012_112209/focused_review.py`（只参考方法，未导入其代码）。
状态：完成并自检通过；宿主与指南冻结未改；停在 `DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED`（0005），无 0006，真实批准 0。
**本轮只跑 G10（`--only-g10`），未重跑完整入口、未重跑 MAIN/G1—G9。**

---

## 1. 结论摘要

| 项 | 结果 |
| --- | --- |
| **共同触发点** | 三个探针统一改为：保存真实 `_read_screen_outputs` 与真实 `check_dev_action`；reader wrapper **先调用真实函数**，成功返回后才增加本次调用返回计数并记事件；**计数等于 2 且尚未注入**时改本项唯一目标文件一次并**原样返回 result**；同时包装真实 `check_dev_action`（先执行真实函数，再记录完整实参/返回与事件序号）；`try/finally` 撤销两个 wrapper。不拦 `io.open`、不在读取句柄前预读/seek、不按调用栈推断消费点。 |
| **实测（三项一致）** | `reader_returns = 2`、注入后 reader 返回 `0`、`hits = 1`、返回对象指纹未变（`returned_object_unchanged = true`）、注入后控制器调用 `0`；目录差异只包含对应目标文件；本次调用 `WorkflowHostBlocked` 且原因分别指向三个目标路径；撤销两个 wrapper 后保留变更的新进程 CLI 退出 `1`；**只恢复该目标原始字节**后 CLI 退出 `0`，恢复后目录哈希集合等于调用前。 |
| **0001 造样** | 只在 `0001.json` 原始字节末尾追加一个换行；**未同步 0002 或任何后继引用**；检测点落在 `workflow/checkpoints/0001.json` 自身（`收尾复测发现 checkpoint 字节变化`），不再由 `0003.previous_file_sha256` 提前阻断。 |
| **控制器测量** | 控制器 wrapper 本次真实记录 **8 次** `check_dev_action` 调用（完整实参键、workflow `state_sha256`/phase/batch_id、返回），`after_injection` 全为 false；注入后计数 0 是**真实测量**，不是预设空列表。 |
| **时点判定与自测** | `probe_timing_verdict` 改为共同边界口径：读者返回次数由真实调用计数导出，要求 **≥2**；注入必须落在第二次返回之后（`injection_after_read_seq` 必须等于第二次返回的事件序号）；注入后不得再有 reader 返回或控制器调用。自测 6 例单列 `self_tests`（合格轨迹／缺注入／只有第一次 reader 返回／注入早于第二次返回／注入后仍有 reader 返回／注入后仍有控制器调用），实测 6/6 与期望一致，`ok=true`。**不再用“单个目标文件只读一次”放宽条件**。 |
| **定向验证** | 全新容器 `task013r4_run_01`：`--only-g10` 退出 **0**，G10-R3、G8、INTEGRITY 三项 PASS，`failures=[]`，`FINAL_ARTIFACT_READBACK ok=true`。 |

---

## 2. 实际命令与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\tests\test_screen_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"      # 0
& $py -B '...\tests\test_screen_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task013r4_smoke6' --only-g10    # 0（过程定向，全绿）
& $py -B '...\tests\test_screen_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task013r4_run_01' --only-g10   # 0（本轮最终定向验证）
```

输出要点（`task013r4_run_01`）：`测试失败 0；受保护文件前后一致: True`、`全部预期成立。`
CLI：start 16／status 25／record 15／prepare-gate2 14／record-gate2 13／screen-rules 10（成功 10＋前提拒绝 0＋运行失败 0）；进程内公开 API 16（均 `inspect_dev_batch`）；控制器进程内 create 0／prepare 14／record 28／check 98（合计 140）；进程内筛查核心 0；进程内 normalize/load 0；接收 16／checker 16；副本 0；模拟决定 28；真实批准 0。

---

## 3. F01 三项探针（共同触发点，本轮实测）

| 目标 | 造样 | reader 返回 | 注入后 reader | hits | 返回对象未变 | 注入后控制器 | 本次调用结果 | 撤销后 CLI | 恢复后 CLI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `workflow/screening/screening_report.json` | 合法 JSON 的 `findings` → 空列表 | 2 | 0 | 1 | true | 0 | `WorkflowHostBlocked`（字段 `workflow/screening/screening_report.json`：收尾复测发现本次筛查产物发生变化） | 1 | 0 |
| `workflow/gate2/load_report.json` | 原始字节末尾追加一个换行 | 2 | 0 | 1 | true | 0 | `WorkflowHostBlocked`（字段 `workflow/gate2/load_report.json`：收尾复测发现本次已消费的产物发生变化） | 1 | 0 |
| `workflow/checkpoints/0001.json` | 原始字节末尾追加一个换行（**不同步任何后继引用**） | 2 | 0 | 1 | true | 0 | `WorkflowHostBlocked`（字段 `workflow/checkpoints/0001.json`：收尾复测发现 checkpoint 字节变化） | 1 | 0 |

- after 时点沿用 R3 已通过的顺序：调用结束、两个 wrapper 撤销之后、恢复本目标原件之前采集；逐项 `after.file == after.tree` 同路径哈希、before/after 目标哈希不同；恢复后集合单独保存。
- 记录现场（`probe_records\`）：
  - `r3_f01_report_last_read.json`（`d0effd0c2f3c7d39c4d6d71cc76781409717cf333b73b2cb6e5e0257023d9fed`）
  - `r3_f01_load_report_last_read.json`（`612643dcef46e70dc894f0ac00a7699be1a2137f2545208fbd878e1dda545875`）
  - `r3_f01_0001_last_read.json`（`40b93f99e9f095a6032b4a597752a23c0e9e26dcaba5f27fe5084efaaf1c6427`）
- 每份记录含：`reader_return_events`（每次返回的序号、stage、返回对象规范指纹）、`controller_calls`（8 次真实调用的完整实参与返回、`after_injection` 标记）、`event_order`（reader 返回与控制器调用的统一递增事件序号）、`changed_paths`、`accepted_reasons`、before/after 目录哈希集合（引用独立文件 + 实际字节哈希）、撤销后 CLI 与恢复后正向、`timing_verdict`。
- 时点自测证据：`self_tests.json → f01_last_read_timing_self_test`，6 例全部与期望一致（`ok=true`），单列；`F01 三项命中次数`单列于 `r3_probes` 的 `r3_f01_<目标>_hit_count` 条目，可由记录导出。

**计数范围说明**：本轮全量 `fault_injections = 0`（仅跑 G10，未运行 G4/G5/G6 等注入组）；G10 组内 F01 三项探针的注入次数按目标单列（每项 1 次，见上表与记录）；CLI 推导次数 `cli_subprocess_core_calls_derivation = 10` 是**本组实际成功的 `screen-rules` 命令数**（本组范围，不是全局）；CLI 子进程内部核心调用不可观测，如实记 `null`。

---

## 4. 交付哈希与保护比较

| 文件 | SHA-256 |
| --- | --- |
| `tests\test_screen_demo_workflow.py`（本轮唯一修改的既有文件） | `27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca` |
| `scripts\run_demo_workflow.py`（冻结未改） | `ae5b7e24dd946a0a2186b8741b79af4173e091c362c4c210d8186e92d2cab4e2` |
| `docs\WORKFLOW_HOST_GUIDE.md`（冻结未改） | `c7963c5857580ae9f3d75e0b6c9e9d448f988b5c561745df63f60b1a92060cf5` |
| `docs\EXEC_REPORT_013_R4.md` | `f19a426022900f5540c1a2f8c4a4f0f512cd106722dc9390e4548de9cb924673`（写卡时的文件字节哈希；最终哈希同时输出到交接消息） |

保护比较相对主基线 `data/reviews/task013_r3_20261012_112209/source_hashes_after.json`（109795 项；文件 SHA-256 `d18f8b5b5915686e562617b6dc69cbd07250d1974910856af9305152dd2c8ba0`）：

- 实扫 114358 个文件（排除 `.venv`），结果 **changed = ['tests\\test_screen_demo_workflow.py']（恰 1 项）、missing = []**，无预期外变化。
- 容器内 INTEGRITY 核对 13 个受保护上游文件前后一致。
- 本轮无临时脚本残留（已按显式清单删除 `.r4_*.py`），未改历史产物、未清理项目外文件。

---

## 5. 三条完整产物路径

- 测试容器 `D:\harness work\audit_sa_project\data\workflow_host_tests\task013r4_run_01`（314 文件；`summary.json`／`checks.json`／`counts.json`／`cli_logs.json`／`entry_events.json`／`self_tests.json`／`final_readback.json`／`r3_g10_counts.json`／`probe_records\` 17 份）
- 批次父目录 `D:\harness work\audit_sa_project\data\batches\task013r4_run_01`（332 文件；**10 份 `0005`、0 份 `0006`**）
- 外置数据库父目录 `D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task013r4_run_01`（14 文件）

过程现场（保留未回写）：`task013r4_smoke1`—`smoke6`（smoke6 起 G10-R3 全绿）。

R3 已保存的完整回归证据（本轮**未重跑**，仅引用）：`D:\harness work\audit_sa_project\data\workflow_host_tests\task013r3_run_03`（11 项检查全 PASS、failures=[]、MAIN 12 条 3/5/2/2、R02 1,600,000 分）。

---

## 6. 与 R3 的差异（本轮改动点）

1. `probe_timing_verdict` 改为共同边界口径（真实 reader 返回计数 ≥2、注入必须在第二次返回之后、其后不得再有 reader 返回或控制器调用）；去掉了 F03/F02 轨迹里不相关的读者计数噪音。
2. `run_last_read_probe` → **`run_f01_probe`**：不再拦 `io.open`、不再预读/seek、不再按目标文件读取次数选位置；改为包装真实 reader 与真实 `check_dev_action`，在第二次 reader 完整返回后注入一次。
3. 0001 造样不再同步 0002；期望原因收紧为只接受 `0001.json`。
4. 目录差异比较统一为与 `_tree()` 相同的原生分隔符形式；after 的 `file_equals_tree` 同样统一。
5. 时点自测改为 6 类（共同边界四类反例），单列 `self_tests`。
6. F02/F03 证据与既有回归**未改**（保留 R3 已通过内容）。

---

## 7. 失败尝试与迭代（本轮真修，如实记录）

1. `probe_timing_verdict` 中 `problems`/`injection` 初始化晚于引用 → `UnboundLocalError`；已把初始化前移。
2. 目录差异比较用了 POSIX 形式与 `_tree()` 的原生分隔符不一致 → 修正为同一形式（含 `file_equals_tree`）。
3. 事件序号空间不一致：reads 用文件打开序号、controllers 用事件序号，导致“注入后控制器调用”被误计为 6 次（真实为 0）→ 统一为**同一个递增事件序号**（`event_seq`），真实探针记录与判定一致。
4. 自测基数误用 `probe.get("timing")`（F01 记录没有该字段）→ 改为取真实探针的完整判定 `probe_timing`。
5. 自测里“注入后仍有控制器调用”用例未把控制器放到注入点之后 → 用例改为事件序号在注入点之后；6/6 通过。

---

## 8. 未执行与边界

- 未执行：完整入口（未重跑 MAIN/G1—G9；引用 R3 `task013r3_run_03` 的已保存结果）、宿主或指南的任何修改、独立复算（R01—R04 之外）、事实底稿、AI、人类判断、正式契约、真实 Gate、UI／真实 ERP／OCR／RAG、并发锁／断电试验、无边界 fuzz、TASK-014；未新增测试模式或生产接口（沿用现有 `--only-g10`）。
- 边界：本地哈希只证明字节一致；不声称断电持久性、并发锁、身份认证或同权限防篡改。0005 是宿主**筛查完成凭证**，不是 Gate2 放行，也不代表整个 `SCREEN_AND_BUILD_FACTS` 动作或项目完成。
- 真实批准恒 0、`next_step_allowed=false`、批次目录 0 份 0006、workflow 未新增请求或决定。
