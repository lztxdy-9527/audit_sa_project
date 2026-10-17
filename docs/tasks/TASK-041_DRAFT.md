# TASK-041：TASK-040-R1 已接受实现的硬化（S8 双构造 / verify 末段 / schema / 死代码）

分类 C；Architect 设计、执行端实施、Architect 独立验收。生效前提：`data/reviews/task040_dsh_r1_20261017_01/review_result.json` 正式 ACCEPTED（本卡与之同时发布，不得先于其执行）。本卡只做**实现与证据硬化**，不新增业务能力、不改已接受设计/协议/案例、不开放 AI/终判/真实数据/强认证，不推进目标链下一业务步骤。

## 1. 身份与允许写入

起点：`scripts/runtime_gate1.py` 399395 B / `f9ec5d21500eda5ace0d43f0223b48b6728a7b8e409173b2de73e2efa13274c3`；`tests/test_runtime_initial_judgment_recording.py` 62351 B / `bdeece7a50dbfa7f17f7e4f0f01480046314dfb014ce7ea0e9369ed9d9ab3c99`；`docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` 7147 B / `f258ed99700f1cde521a44425fcbd0faedbebaeaa13b9ba8d764825fa94b0a61`。接受基线：`data/reviews/task040_dsh_r1_20261017_01/source_hashes_after.json`。

允许修改：上述适配器、新测试、指南（仅这三件既有文件）。允许新增：`docs/EXEC_REPORT_041.md`；证据根 `data/runtime_initial_judgment_recording_tests/task041_<场景>/` 及 `data/runtime/task041_*`、`data/human_gate_decision_records/gate1|gate2/task041_*`、`data/sqlite_tests/task041_*`、`data/human_initial_judgment_records/task041_*`（锁仍留在 `task041_*` 根内）。冻结：设计协议/案例、冻结 core/store/history、正式契约/生效登记、旧测试与旧指南、TASK-040/040-R1 全部卡与回执、`task040_run_05`、`task040_dev_01`、`task040_r1_run_01/02`、两轮架构端评审根与 `docs/reviews/REVIEW_TASK_040*.md`。不删移、不清理、不重跑旧 run/main。

## 2. 必须硬化项（对应 REVIEW_TASK_040_R1 §5 残差）

**H1 S8 双构造（首要）。** 取消 `success = copy.deepcopy(expected_result)` 充当候选的做法，建立两条独立路径：
- **候选**：由本次实际返回/写后捕获组装（`store.save` 真实返回、H1 真实 history 返回、三封装 writer 缓冲与回读）。
- **预期**：只能由已核验源、H1 目标、本次 writer 缓冲**独立重建**——例如用目标叶六文件字节 + manifest FILE 重新构造 `storage_verification` 十一键、用 E1 与 writer 缓冲重建 `history_verification`/`envelope_binding`、用 S3 固定 identity 重建 `identity`；不得直接引用候选对象或其派生副本。
- 两者做完整 canonical 字节比较，任一构造器错误都必须能被发现；schema/类型矛盾仍 `Blocked result.<字段>`，内部内容审核非空仍 `Error audit.result` 并保留 `reasons`。
- **公共路径可达性证据**：测试至少一例通过公共入口（包装候选或预期构造路径，不直调 `_audit_initial_success_040`）使上述比较或内部审核拒绝，并记录精确 `result.*` 字段/`audit.result` 与 store/core 增量。

**H2 verify 末段完备。** `_confirm_initial_sources_040` 在 verify 末段同样传 `target_leaf/target_captures`，复确认目标叶六件集合与 failure，保持只读；不得因此新增写。

**H3 S5 schema 复测。** `_pre_store_confirm_040` 补 `sql/demo_schema.sql` 静态 schema 复测（沿 `_capture_static_028` 口径），失败精确 Blocked。

**H4 死代码与静默路径。** 删除或实现无调用点的 `_initial_snapshot_objects_040`/`_initial_target_name_040`；`_confirm_initial_history_040` 的 `if buffers is None: continue` 改为显式判定（非本次目标旧叶缺缓冲必须 Blocked）；坏 envelope failure 缺键/未知键须精确到 `failure.<子键>`（不得只报 `failure`）。

**H5 非阻断遗留（可同卡）。** store Blocked `reasons` 行为等价记录；旧适配器 290568 B 正文不可证明，继续以"旧文件未登记变化 0 + 旧 17 签名与既有指南一致"承担，不伪造基线。

## 3. 场景与证据

- 新具名根 `task041_<场景>/`，同一定稿代码身份；正常链一条 + 必要失败场景不超过 8 条（含 H1 公共路径控制、H3 schema 漂移控制）。失败现场（锁/半写/坏字节）保留。
- 调用图与既有 19 API/17 代码/40 材料不变；save n=0 与 verify m=1/m=2 的图仍须等于卡公式（`save`：prepare 1、store.save 1、后 history 1、总 history 2、store.verify 1、core 2；`verify`：prepare/save 0、history 1、store.verify/core 各 m）；算法/SQL/装载/复算/事实 build 0。任何因硬化新增的内部调用必须单列，不得混入业务公式。
- 测试须保持：独立预期先于候选（`independent_expectations` 口径）、78 项既有 check 全部保留或按硬化等价替代（数量可减但不得降低覆盖），四 CLI 0/1/1/1 重新实测，44 例映射按"实测/引用/未执行"三层据实更新。

## 4. 定稿、保护与停止

定稿后**一次**全树扫描，基线改用**本卡接受基线**（`source_hashes_after.json` at `data/reviews/task040_dsh_r1_20261017_01/`）：相对该基线既有 changed 仅允许适配器/测试/指南三件；其余一切新增（`task041_*` 与 `docs/EXEC_REPORT_041.md`）逐确切路径登记，无前缀豁免；新 missing/读取错误/未登记新增/身份漂移 0。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

回执 `docs/EXEC_REPORT_041.md` 列：H1—H5 逐项代码位置与实测、公共路径可控性证据、调用图、CLI 退出码、扫描结果、未执行项与原因。交付后停止待独立验收；不推进下一业务步骤、不改看板、不自称 ACCEPTED。

真实批准 `null`、真实初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。本卡不批准任何真实批次，不认证身份，不进入 AI 建议或终判。
