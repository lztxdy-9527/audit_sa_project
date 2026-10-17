# TASK-040-R1：TASK-040 定点修正（S5/S9/S8 流程、证据族与映射）

分类 C；Architect 制定、执行端实施、Architect 独立验收。生效前提：`docs/reviews/REVIEW_TASK_040.md` 的 NOT_ACCEPTED 观察现场保持原样；本卡只修正该 review 列出的阻断与证据缺口，**不**扩大业务权限、**不**推进 TASK-041、不开放 AI/终判/真实数据/强认证。当前接受基线仍为 TASK-039-R1（168839 项 / `43fa7288b88d3deb806d215352ce1a91b02f841a32eebdd03b3f0f9ec02ccae2`），本卡不替换它。

## 1. 起点身份与允许写入

起点为本轮交付：适配器 `scripts/runtime_gate1.py` 389797 B / `7b3267153cbaf192360403e92d429d45af701bec6cd3f4f1bb1d7dcbf508345d`；测试 46473 B / `a4e285fe…4ddef`；指南 7807 B / `673844fe…2e12`；回执 11196 B / `65776fe2…afd5d`。设计仍为已接受 TASK-039-R1 协议/案例（`0b92e862…6b2db` / `177d5801…729b`），冻结 core/store/history、正式契约、生效登记、旧测试/指南、旧证据、TASK-040 卡本身、架构端 `data/reviews/task040_dsh_20261017_01/` 及 `docs/reviews/REVIEW_TASK_040.md` 全部只读冻结，不删移、不清理、不重跑其 run/main。

允许修改：`scripts/runtime_gate1.py`；`tests/test_runtime_initial_judgment_recording.py`；`docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md`；新增 `docs/EXEC_REPORT_040_R1.md`。允许新增证据根 `data/runtime_initial_judgment_recording_tests/task040_r1_<场景>/`、`data/runtime/task040_r1_*`、`data/human_gate_decision_records/gate1|gate2/task040_r1_*`、`data/sqlite_tests/task040_r1_*`、`data/human_initial_judgment_records/task040_r1_*`（域内锁仍留在本轮 `task040_r1_*` 根内）。根不是前缀豁免；新增逐确切文件路径登记。不得改旧 `task040_run_05`、`task040_dev_01`、失败场景根或架构端评审根；不得修改或补签旧凭证/旧回执。

## 2. 必须修正的实现偏离（阻断级）

**R1-B1 S5 复确认。** 在 started 写回比较之后、调用冻结 `store.save_human_initial_judgment_snapshots` **之前**，按协议 S5（第 66 行）复确认并 Blocked：S3 开始依赖（登记/事件/装载/数据库/停点源）、H0 旧叶六字节与集合、`record_relative` 原路径链、自锁句柄身份与属性、started writer 缓冲。复确认不通过的字段精确到来源（如 `batch.<名>`、`gate1_event.<名>`、`history.entries[...]`、`started.json`），且**不得**调用 store/core、不得建目标叶、不得刷新独立预期。

**R1-B2 S9/V8 末次确认。** 复用冻结 `_confirm_approved_terminal`／`_confirm_gate2_terminal_030` 的集合/failure/锁口径（若因 040 上下文确需另写，必须逐项对齐）：batch 顶层与子目录集合、登记叶集合与 failure、Gate1/Gate2 scope/event/snapshot 集合与 event failure、load 目录集合与 failure、数据库目录集合、Gate1 锁 `_lock_path_for(leaf)`、Gate2 锁；save 末段重查目标叶六件集合与 failure、verify 末段重查三封装集合与 failure/锁不存在。任何集合/failure/锁差异必须 Blocked，且不得删移现场。

**R1-B3 取锁序。** `history_expectations` 的 `expected_namespace_relative`／`expected_declared_scope`（RC-12/RC-13）与全部路径关系校验必须移到 `lock.acquire` 之前；参数/域/scope/名单形状错时**不产生**本次锁、叶、封装，业务调用 0。取锁后仍按 S2/S3 重新实读。

**R1-B4 S8 返回审核契约。** Blocked 字段基名改为 `result.`；内部内容审核产生非空问题时抛 `RuntimeGate1Error("audit.result", …)` 并保留问题与 `reasons`，不得硬填 true；`status` 按入口分别校验 save_status/verify_status，不接受“两者任一”。

## 3. 必须补齐的证据族（缺一即不得判 PASS）

**R1-E1（RC-40）** 至少一例“形状合法、摘要自洽但完整内容错”：在真实源固定后，只替换候选的完整内容并同步重算其内部摘要，独立预期不刷新；要求 `Blocked result.<字段>` 精确定位；再以一例使内部内容审核返回非空问题，要求 `Error audit.result` 并支配外层 summary/failures/退出码（不得内部 FAIL 而外层 0）。
**R1-E2（RC-44）** A/B/C 三变体隔离执行：A 仅 `source_binding.registry_binding.run_binding_sha256` 以登记文件 FILE 替 FP；B 仅 `context.prepared_request.request_sha256` 以包含文件 FILE 替 FP；C 仅 `receipt.context_file_sha256` 以 context 对象 FP 替 writer FILE；三值仍为完整 64hex，先前更早前提合法。分别在 S4/S8/V3 精确 Blocked 对应字段，预期不刷新。
**R1-E3（独立预期先于候选）** 测试 harness 必须先由卡公式/结构常量与磁盘字节固定独立预期台账（api/core/12 键/11 键/九边界/集合），再运行候选并与之全量 canonical 比较；禁止 `run()` 之后再 `freeze_expectations()` 使首次 audit 恒等。补 `storage_verification` 十一键键集与 `context.store_save_result` 状态常量断言；三种 replay mutate 保留。
**R1-E4（RC-22 与严格类型）** f03 改为**包装真实 writer 句柄**写半份后 OSError（不得整体替换 `store._write_exclusive`，真实 writer 必须执行过）；补 RC-08/09 的严格 False/0、int/float、反序多错首报动态核对（可用本轮小样/内存接缝，不新建大规模链）。

非阻断项同卡处理：参数类型按签名顺序检查；去掉 `failure.failure.*`／`store.failure.failure.*` 双前缀；指南与回执中的映射/措辞必须与实际证据层级一致（引用旧证据与实测分列）。

## 4. 定稿、保护与停止

修正后建立一条定稿代码的 `task040_r1_*` 正常链与必要失败场景（同一定稿代码身份；失败场景上限与 TASK-040 相同，超过则报告 Architect）。新链用同三 profile 常量；旧 TASK-040 登记按 code FILE 拒绝，不改旧凭证。四 CLI 控制（正常 0、内容反例 1、台账替换 1、末次读后漂移 1）须在新根重新实测。

局部实现/测试/指南/回执/完整观察定稿后，仅一次全树保护扫描：基线 TASK-039-R1（168839 项 / `43fa7288…`）；相对该基线**既有** changed 仍只允许 `scripts/runtime_gate1.py`；其余一切新增（执行端 TASK-040 的 1018 项、架构端 `data/reviews/task040_dsh_20261017_01/` 与 `task040_dsh_01*`、本卡新增）逐确切路径登记，不使用目录前缀豁免；新 missing/未登记新增/读取错误/身份漂移 0。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认、不重建。扫描后只做有限自身元数据读回。

回执 `docs/EXEC_REPORT_040_R1.md` 须列：逐阻断修正点与确切代码位置、RC-40/RC-44/RC-22 实测现场、调用图（按实际前缀）、四 CLI 退出码、44 例映射的真实层级（实测/引用/未执行）、完整保护结果、未执行项。交付后停止待独立验收，不推进任何后续卡、不改看板、不自称 ACCEPTED。

真实批准 `null`、真实初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。技术修正不批准真实批次，不认证身份。
