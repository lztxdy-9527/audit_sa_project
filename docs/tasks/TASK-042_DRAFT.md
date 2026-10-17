# TASK-042：运行层演示就绪（至人类初判）与后置 AI 只读扩展点

分类 C；Architect 设计、执行端实施、Architect 独立验收。生效前提：`docs/reviews/REVIEW_TASK_041.md` 的 ACCEPTED 与 `data/reviews/task041_dsh_20261017_01/source_hashes_after.json`（构建中，随本卡同轮发布）。依据人类 2026-10-17 指示（`docs/decisions/DECISION_20261017_DSH_DEMO_SCOPE_AND_AI_DEFERRAL.md`）：**优先做到人类初判、使项目可演示；后置 AI 只预留只读扩展点，不实施**。

本卡**只新增演示与文档**，不改已接受实现、不改协议/案例/契约、不新增业务 API、不开放 AI/终判/真实数据/强认证。

## 1. 允许写入

允许新增：`scripts/run_runtime_demo.py`（演示入口，唯一新增代码）、`docs/RUNTIME_DEMO_AND_AI_EXTENSION_GUIDE.md`、`docs/EXEC_REPORT_042.md`；证据根 `data/runtime_initial_judgment_recording_tests/task042_demo_<轮次>/`、`data/runtime/task042_demo_*`、`data/human_gate_decision_records/gate1|gate2/task042_demo_*`、`data/sqlite_tests/task042_demo_*`、`data/human_initial_judgment_records/task042_demo_*`（锁留在本轮根内）。**不允许修改**任何既有文件（适配器/测试/指南/旧回执/旧证据/TASK-040·041 卡与评审根、`task040_*`、`task041_*`）；根不是前缀豁免，新增逐确切路径登记。

## 2. 演示脚本要求

1. **单命令**：`.venv\Scripts\python.exe -B scripts\run_runtime_demo.py --out-dir data\runtime_initial_judgment_recording_tests\task042_demo_01`；`--out-dir` 必须从未存在且位于 `data/runtime_initial_judgment_recording_tests/` 内。
2. **只走真实公开 API**：注册 → Gate1 请求/保存 → 装载 → Gate2 请求/保存 → 筛查 → 复算 → 事实 → `prepare_runtime_initial_judgment_request` → `save_runtime_initial_judgment` → `verify_runtime_initial_judgment`；人类提交值仅用已登记夹具（event2 六原文），技术请求/批次可构造；不得直接调用私有内部函数绕过公开入口。
3. **可阅读输出**：写 `demo_summary.json` + `demo_readme.md`，至少含：批次/实体（澄明商贸有限公司、CNY、2026-09、截至 2026-09-30）、Gate1/Gate2 决定摘要、R01–R04 待核查线索计数、事实包路径、初判 `VERIFIED` 记录相对路径与 `record_fingerprint`、六文件与三封装清单、九边界 false。
4. **边界声明**：输出内必须写明"合成演示，不是批次批准、不是身份认证、不开放 AI/终判；`real_approval=null`"。
5. **确定性/隔离**：新独立根；不读不写旧证据；重复运行使用新 `--out-dir`（既有目录拒绝）；失败保留现场，不清理。

## 3. 后置 AI 只读扩展点（不实施 AI）

1. 文档 `RUNTIME_DEMO_AND_AI_EXTENSION_GUIDE.md` 写清五条约束（见决策记录 D-SCOPE-3）：只读消费 VERIFIED 记录/材料/事实、19 API 封闭、边界 false、分域存放、另行授权。
2. **只读消费者实证**：脚本增加只读模式 `--inspect-record <初判记录目录>`，独立进程读回该 `VERIFIED` 记录并输出摘要（identity、record_fingerprint、manifest FILE、六文件清单、边界 false、事实包路径）；该模式**零写入**（运行前后目标目录集合与字节不变，须在证据中给出前后快照对比）。
3. 实证必须证明：读取无需修改适配器/测试/指南，无需新增公开 API，不触发任何业务算法（算法/装载/SQL/复算/事实 build 均为 0）。这即是"可延展性"的可验证证据；将来 AI 卡在此之上新增模块与入口。

## 4. 证据与保护

- 证据根 `task042_demo_<轮次>/`：命令原文、stdout/stderr、退出码、`demo_summary.json`、`demo_readme.md`、只读模式前后目录快照对比、完整清单。
- 一次全树扫描，基线 = TASK-041 接受基线：相对该基线**既有 changed 必须为 0**；新增仅限 §1 所列（逐确切路径登记）；新 missing/读取错误/身份漂移 0。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结。
- 回执 `docs/EXEC_REPORT_042.md` 列：命令与退出码、可阅读产物、只读实证、扫描结果、未执行项。交付后停止待独立验收；不改看板、不自称 ACCEPTED、不推进 AI/终判。

真实批准 `null`、真实初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。演示脚本与只读实证都不批准真实批次，也不开放 AI 或终判。
