# TASK-040-R1 执行回执：定点修正（S5 复确认 / S9·V8 末次确认 / 取锁序 / S8 审核契约 + E1—E4）

日期：2026-10-17。交付状态：修正、测试、指南与证据定稿，**交 Architect 独立验收**；本回执不宣布验收通过，
不改看板、不推进后续卡。真实批准仍 `null`，真实独立初判未保存，开发宿主 0008，`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-040-R1_DRAFT.md`（`4e5cd14a…fa4dca1`）与 `docs/reviews/REVIEW_TASK_040.md`（`082bea97…249091`）。
当前接受基线仍为 TASK-039-R1（168839 项 / `43fa7288…ccae2`），本卡不替换。`task040_run_05`、`task040_dev_01`、
架构端 `data/reviews/task040_dsh_20261017_01/` 与 `task040_dsh_01*` 全部原样冻结，未删移、未清理、未重跑其 run/main。

本回执在最终保护扫描之前定稿，**不预填扫描数字**；R1 扫描实际结果、四件最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task040_r1_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 四件交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 适配器（唯一修改的既有文件） | `scripts/runtime_gate1.py` | 399395 B | `f9ec5d21500eda5ace0d43f0223b48b6728a7b8e409173b2de73e2efa13274c3` |
| 新测试 | `tests/test_runtime_initial_judgment_recording.py` | 62351 B | `bdeece7a50dbfa7f17f7e4f0f01480046314dfb014ce7ea0e9369ed9d9ab3c99` |
| 新指南 | `docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` | 7147 B | `f258ed99700f1cde521a44425fcbd0faedbebaeaa13b9ba8d764825fa94b0a61` |
| 本回执 | `docs/EXEC_REPORT_040_R1.md` | 见 delivery.json | 见 delivery.json |

起点 TASK-040 四件身份（只读核对，不改）：适配器 389797 B / `7b326715…8345d`，测试 46473 B / `a4e285fe…4ddef`，
指南 7807 B / `673844fe…2e12`，回执 11196 B / `65776fe2…afd5d`。设计协议/案例与冻结 core/store/history 未变。

## 2. 阻断级修正点与确切代码位置

**B1 S5 复确认** — 新增 `_pre_store_confirm_040`（L5802），在 `save_runtime_initial_judgment` 中于
started 写回之后、冻结 `store.save_human_initial_judgment_snapshots` 之前调用（L6081–6083）。
复确认内容：batch 顶层/子目录集合与八文件字节、静态/冻结准备器/自身、登记两文件、Gate1/Gate2 事件与
snapshot 集合及 event failure、load 目录集合与 failure、数据库目录集合、Gate1/Gate2 技术锁、
声明域成员与旧叶六字节（`history.entries[i].<file>`）、`record_relative` 原路径链与父域、自锁句柄身份/
属性/缓冲、started writer 缓冲（字段 `started.json`）。失败时不调用 store/core、不建目标叶、不刷新预期。
实测（`task040_r1_run_02` 正常链控制）：篡改 Gate1 事件后复确认 `Blocked gate1_event.context.json`，
`store.save`/初判 core 增量均 0 且目标叶不存在；精确恢复后同类复确认通过（B1.1—B1.4）。

**B2 S9/V8 末次确认** — `_confirm_initial_sources_040`（L5892）改为复用冻结
`_confirm_gate2_terminal_030`（L5902，内部再调 `_confirm_approved_terminal`）的 set/failure/lock 口径，
再补：screen/crosscheck/facts 输出目录集合与 failure 及字节、历史域成员/旧叶六字节与冻结组件、
目标叶六件集合与 failure 及字节、三封装三件集合与 failure。save 末段调用 L6185，verify 末段调用 L6568
（verify 同时重查目标六件 writer 缓冲）。集合/failure/锁任何差异均 Blocked，不删移现场。

**B3 取锁序** — `history_expectations` 的 schema、`expected_namespace_relative`、`expected_declared_scope`
与全部路径关系校验移到 `lock.acquire` 之前（L6007–6018），取锁在 L6029。实测：错声明域
`Blocked history_expectations.expected_namespace_relative`、错 scope
`Blocked history_expectations.expected_declared_scope`，两次均无本次锁/叶/封装且 prepare/store/core/history 业务增量为 0；
真实独占句柄控制锁存在时 `Blocked lock`，控制锁按已持有句柄释放后无残留（B3.1—B3.4）。

**B4 S8 返回审核契约** — `_audit_initial_success_040`（L5648）重写为三段：① 封闭
schema/严格类型/常量，映射 `Blocked result.<字段>`（含 `storage_verification` 十一键集）；
② 候选与本次独立构造的十二键成功预期完整 canonical 比较，首差映射 `Blocked result.<差异路径>`；
③ 内部内容审核（identity/record_fingerprint/manifest FILE/十一键稳定字段/历史核验/三封装 FILE 与实读缓冲），
非空问题抛 `RuntimeGate1Error("audit.result", …)` 且 `reasons` 保留问题列表；状态按入口分别校验
（save=`INITIAL_SAVE_STATUS`、verify=`INITIAL_VERIFY_STATUS`）。候选构造改为
`_initial_started_040`（L5721）/`_initial_context_040`（L5754）/`_initial_receipt_040`（L5772）/
`_build_success_040`（L5784）；save 审核 L6177，verify 审核 L6559。

## 3. 必需证据族（E1—E4）

**E1 RC-40（实测）** — 以真实审核函数（未替换）做两组控制：
`E1.1` 候选形状合法、只替换 `storage_verification.judgment_result.record.human_initial_judgment.assessment`
并同步重算其内部 `record_fingerprint`，独立预期不刷新 → `Blocked result.storage_verification.judgment_result.record.human_initial_judgment.assessment`；
`E1.2` 候选与独立预期同时改动 `identity.event_id`（canonical 相等）→ 内部审核非空 →
`Error audit.result`，`reasons=["identity"]`；保存/恢复在该分支不返回成功值（该场景的 check 失败即外层 summary/failures/退出码非 0，
不存在“内部 FAIL 而外层 0”）。

**E2 RC-44 A/B/C（实测，三值均为完整 64hex）** —
A：包装真实 `_initial_started_040` 输出，仅 `source_binding.registry_binding.run_binding_sha256`
以登记文件 FILE 替 FP → `Blocked started.source_binding.registry_binding.run_binding_sha256`（S4，封装未创建，锁保留）；
B：包装真实 `_initial_context_040` 输出，仅 `context.prepared_request.request_sha256` 以 request 的“文件式”摘要
（canonical+LF）替对象 FP → `Blocked context.prepared_request.request_sha256`（S8，封装仅 started+failure，锁保留）；
C：正常链上仅把 receipt 的 `context_file_sha256` 替换为 context 对象 FP → `Blocked receipt.context_file_sha256`（V3），
精确恢复 receipt 原件后恢复成功（R7）。三变体先前更早前提全部合法，预期未刷新。

**E3 独立预期先于候选（实测台账）** — 测试在运行候选前由卡公式/结构常量固定
`results.independent_expectations`（`declared_before_run=true`：十二键/十一键键集、九边界、目标叶与封装集合、
H0/H1/Hc 索引、save 与 verify m=1/m=2 调用图公式），随后以实际观测逐项比较（S1—S11、V1—V4、R1—R3）；
`storage_verification` 十一键键集与 `context.store_save_result` 的 STORED 常量断言在审核内与测试侧分别执行。
三种 replay mutate 保留。

**E4 RC-22 与严格类型（实测）** — f03 改为包装 `Path.open` 返回的真实句柄代理：真实 writer 打开并写入半份后
OSError（`half_writer_hit` 记录到目标叶 expectations.json 路径），真实 `store._write_exclusive` 执行过；
结果 `Error write.expectations.json`。RC-08：`boundaries.execution_allowed=false→0` →
`Blocked result.boundaries.execution_allowed`；`byte_size` 整数→同值 float →
`Blocked result.envelope_binding.files[0].byte_size`。RC-09：两类矛盾、字典顺序与其反序两次首报同一字段
`result.record_fingerprint`；纯键序不同的合法候选规范等值通过。

## 4. 正常链与调用图（实测，非预测）

正常链 `task040_r1_run_02`：78 项 check 全通过、`api=23`、`core=446`、退出码 0、failures 空。
n=0 保存：prepare 1、store.save 1、保存后 history 1（总 history 2）、初判 store.verify 1、core 2；
Gate1 6、Gate2 5、inspect 5/2/1/1、render 1、Gate store 核验 11、Gate core 11、冻结准备器 6、算法/SQL/事实 build 0。
m=1 恢复：history 1、prepare 0、save 0、store.verify 1、core 1；m=2：store.verify 2、core 2；Gate/fact 嵌套图同上。
原 `submission` 引用三时点一致、原 `history_expectations` 未改写；目标叶六件、封装三件、锁已解除；
核心 `persisted=false`、`record_status=HUMAN_INITIAL_JUDGMENT_VALIDATED`。

## 5. 失败场景（同一定稿代码，8 条 = TASK-040 同口径上限）

| 场景 | 实测结果 | 现场 |
| --- | --- | --- |
| f01_bad_submission | `Blocked store.submission.assessment` | started+failure；无叶；锁保留 |
| f02_stale_materials | `Blocked store.submission.request_binding.materials_fingerprint` | 同上 |
| f03_store_half_write | `Error write.expectations.json`（真实句柄半写） | 半写叶+失败+封装 failure；锁保留 |
| f04_context_half_write | `Error write.context` | 六快照+started+半 context+failure；锁保留 |
| f05_receipt_sentinel | `Error write.receipt` | 完整 receipt 保留为失败现场 |
| f06_release_failure（函数级注入） | `Error release.lock`，绝不返回 RECORDED | 六快照+三封装+failure；锁保留 |
| rc44a_started_role | `Blocked started.source_binding.registry_binding.run_binding_sha256` | 封装未创建；锁保留 |
| rc44b_request_role | `Blocked context.prepared_request.request_sha256` | started+failure；锁保留 |

锁不存在拒绝（f07 口径）折叠为正常链 `save.lock_control` 控制（真实独占句柄先持有 → `Blocked lock`，
无锁/叶/封装残留）。失败现场全部保留，未删移。

## 6. 四项 CLI 控制（各自新进程、新 out-dir）

| 控制 | 命令要点 | 退出 | 摘要 |
| --- | --- | --- | --- |
| 正常 | `--out-dir ...task040_r1_run_02` | 0 | PASS，78/78，failures 空 |
| 内容反例 | `--replay ...task040_r1_run_02 --mutate candidate-return` | 1 | `api_records_mismatch:call_004` |
| 台账替换 | `--replay ... --mutate ledger-replaced` | 1 | `ledger_mismatch`/`ledger_bytes_mismatch`/`drift:file_ledger.json` |
| 末次读后漂移 | `--replay ... --mutate late-drift` | 1 | `drift:checks.json` |

## 7. 44 例映射的真实层级

逐例映射写入 `summary.json` 的 `results.case_map`，按“实测 / 引用已接受证据 / 未执行”三层措辞，不再把
S4/S8/V3 的逐字段核对写成存在而实际不存在。实测新增：RC-08/09/11/12/13/17/22/40/44 与 RC-29/30/44C；
引用：RC-02/06/10/20/21/26/38/39；未执行：RC-03/15/16/18/19（坏锁类型）/23（坏 schema failure）/28/33/34/35/36/37，
原因逐条登记（第二注册叶/第二事件链、会永久锁定唯一正常链、超出本轮链预算）。

## 8. 非阻断项

- 参数类型检查按签名顺序（save/verify 两入口均已按签名顺序先行）。
- 坏 failure 双前缀已去除：本层坏诊断字段为 `failure.<子键>`，store 坏诊断字段为 `store.failure.json.<子键>`；
  有效映射仍为 `runtime.failure.<原field>` / `store.failure.<原field>`。
- store Blocked 的 `reasons` 仍为 `[reason]`（行为等价，仅记录）。
- 旧适配器 290568 B 正文本地无副本，**无法证明旧正文逐字未变**；只能核实旧 17 API 签名与既有指南一致、
  旧文件中未登记变化为 0（保护扫描）。

## 9. 未执行与业务边界

物理 junction（无权限）、真实数据、强认证、AI、终判、并发双进程真实竞态、非合作篡改证明均未执行：
`null` + 原因。真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。
本卡交付后停止实施，交 Architect 独立验收；不推进 TASK-041、不改看板。

## 10. 保护安排与判据

R1 全部交付/证据定稿后，仅执行**一次**新的全树扫描（`task040_r1_finalization/protection_scan.py`），
基线 TASK-039-R1（168839 项 / `43fa7288…`），根层排除与接受快照相同的 `.venv/.git/__pycache__`。判据：

- 相对基线**既有 changed 仅** `scripts/runtime_gate1.py`；
- 新 missing 0、未登记新增 0、读取错误 0、身份漂移 0；
- 全部新增按**确切文件路径**登记（执行端 TASK-040 的 1018 项、架构端评审根与 `task040_dsh_01*`、
  本卡 `task040_r1_*` 与既有交付文件），不使用目录前缀豁免；接受快照与旧 `review_result` 不改；
- 139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认、不重建。

扫描数字、四件最终身份与确切新增清单见 `task040_r1_finalization/delivery.json` / `protection_result.json`。
