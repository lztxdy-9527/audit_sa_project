# TASK-040-R1 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对 TASK-040-R1 定点修正独立复验。上一轮 REVIEW_TASK_040 判定的 4 项阻断偏离（B1—B4）与 4 项证据缺口（E1—E4）均已按卡闭合，且交付在架构端自跑下可复现。接受的是**合成运行层初判保存/只读恢复的实现与证据**，不是批次批准、不是身份认证、不开放 AI/终判/真实数据。上一轮 NOT_ACCEPTED 现场与 `task040_run_05`/`task040_dev_01`/架构端第一轮评审根全部原样冻结。

## 1. 交付身份（实读同缓冲）

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | 399395 B | `f9ec5d21500eda5ace0d43f0223b48b6728a7b8e409173b2de73e2efa13274c3` |
| `tests/test_runtime_initial_judgment_recording.py` | 62351 B | `bdeece7a50dbfa7f17f7e4f0f01480046314dfb014ce7ea0e9369ed9d9ab3c99` |
| `docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` | 7147 B | `f258ed99700f1cde521a44425fcbd0faedbebaeaa13b9ba8d764825fa94b0a61` |
| `docs/EXEC_REPORT_040_R1.md` | 12848 B | `e4bbd14037386d048833a944a7376adb64e411eb204857fa4e5196062754cf3f` |

起点 TASK-040 四件身份、`docs/tasks/TASK-040-R1_DRAFT.md`（`4e5cd14a…fa4dca1`）、`docs/reviews/REVIEW_TASK_040.md`（`082bea97…249091`）、设计协议/案例与冻结 core/store/history 均未变。相对 TASK-039-R1 接受基线，唯一既有变化仍是适配器。

## 2. 阻断闭合（实读代码 + 实际运行）

- **B1 S5 复确认成立**：`_pre_store_confirm_040`（L5802）在 started 写回（L6072-6075）后、冻结 `store.save`（L6086）前无条件调用（L6081-6084）。覆盖 batch 集合/八文件、静态与冻结准备器/自身、登记两文件、Gate1/Gate2 事件与 snapshot 集合及 failure、load/数据库目录集合、Gate1/Gate2 锁、历史域成员与旧叶六字节、`record_relative` 原链与父域、自锁身份、started 缓冲。控制实测：篡改 Gate1 来源 → `Blocked gate1_event.context.json`，`store.save`/core 增量 0、未建叶（B1.1—B1.4）。
- **B2 S9/V8 成立**：`_confirm_initial_sources_040`（L5892）先调冻结 `_confirm_gate2_terminal_030`（L5902→`_confirm_approved_terminal` L2440），再补 outputs 集合/failure、历史域、目标叶六件与 failure、三封装集合与 failure；save（L6185）全参调用，verify（L6568）覆盖三封装/锁。
- **B3 取锁序成立**：类型按签名序（L5975-5990）→ history_expectations schema 与域/scope（L6011-6017）→ 目标叶/封装/锁路径存在性（L6018-6024）→ 才取锁（L6029）。实测错声明域/错 scope → 精确 Blocked 且**无本次锁/叶/封装**、业务调用 0（B3.1—B3.4）；锁存在时 `Blocked lock`、控制锁按已持有句柄释放。
- **B4 返回契约成立**：`_audit_initial_success_040`（L5648）按 `result.*` 做封闭 schema/严格类型、`storage_verification` 十一键集、完整 canonical 前缀 `result.<差异路径>`、内部问题 `Error("audit.result", reasons=[…])`、状态按入口参数化（save L6182 / verify L6564）。E1 实测：内容替换（摘要自洽）→ `Blocked result.storage_verification.judgment_result.record.human_initial_judgment.assessment`；候选与预期同改 → `Error audit.result`，`reasons=["identity"]`，不返回成功值。

## 3. 证据族

- **E1 RC-40** 两组控制实测（`results.controls.rc40_content/rc40_audit`），精确字段与 Error 类如 §2 所述。
- **E2 RC-44 A/B/C** 实测：A `Blocked started.source_binding.registry_binding.run_binding_sha256`（S4，封装未创建、锁保留）；B `Blocked context.prepared_request.request_sha256`（S8，started+failure）；C `Blocked receipt.context_file_sha256`（V3），精确恢复 receipt 后恢复成功（R7）。
- **E3 独立预期先于候选**：`tests/…:392 independent_expectations` 在 save/verify 候选之前由卡公式/结构常量固定（`declared_before_run=true`，含十二/十一键、九边界、目标叶与封装集合、H0/H1/Hc、save 与 m=1/m=2 图），S1/S4/S5/S6/S7/S8/S11/V1/V3/R1/R2 逐项以该台账比较（L629-716），不再以 SUT 自报值互比。
- **E4 RC-22 与严格类型**：f03 包装真实 `Path.open` 句柄，真实 `store._write_exclusive` 执行过，`half_writer_hit` 指向目标叶 `expectations.json`（2991 B 半写），`Error write.expectations.json`；RC-08 `false→0` → `Blocked result.boundaries.execution_allowed`，`byte_size` int→同值 float → `Blocked result.envelope_binding.files[0].byte_size`；RC-09 两类矛盾与字典反序两次首报同一 `result.record_fingerprint`。

## 4. 架构端独立实际运行（不复用执行端结论）

- **正常链复跑** `data/runtime_initial_judgment_recording_tests/task040_dsh_r1_01`：**78/78 checks、api=23、core=446、exit 0**；8 条具名失败场景在同一定稿代码下复现精确 field/stage（`store.submission.assessment`、`store.submission.request_binding.materials_fingerprint`、`write.expectations.json`、`write.context`、`write.receipt`、`release.lock`、`started.source_binding.registry_binding.run_binding_sha256`、`context.prepared_request.request_sha256`）。
- **四项 CLI**（新进程、新 out-dir）：0 / 1 / 1 / 1。
- **内容独立重算** `recompute_r1.py` 42/42 PASS：五载荷 FILE+FP 同缓冲、`record_fingerprint=FP(record)`、`run_binding_sha256=FP(run_binding)`（≠FILE、≠FP+LF）、`request_sha256=FP(request)`、receipt 对 context/started/manifest 的 FILE 绑定、H0 空/H1=1 叶、旧叶与 TASK-037 源逐字节相同、九/八边界严格 false、十二键与 `storage_verification` 十一键、status 分别 RECORDED/VERIFIED 与 SNAPSHOTS_STORED/VERIFIED、save 图等于卡公式且算法/SQL/事实 build 0。

## 5. 记录在案的残差（不阻断本轮接受，纳入下一卡硬化）

1. **S8 公共路径候选=预期副本**：save L6179 / verify L6561 为 `success = copy.deepcopy(expected_result)`，故 `_audit_initial_success_040` 的完整 canonical 比较在公共路径恒等（只有测试直调时判别）。返回对象内容仍由真实 store/H1/封装缓冲派生，且测试独立台账与本次独立重算均已另行锚定；但它不等于"两次独立构造互比"，属硬化项。
2. verify 末段（L6568）未传 `target_leaf/target_captures`，目标叶六件仅早段确认（TOCTOU 残差）。
3. S5 复确认未复测 `sql/demo_schema.sql` 静态 schema（仅 S9 复测）；坏 envelope failure 缺键/未知键只报到 `failure`；`_initial_snapshot_objects_040`/`_initial_target_name_040` 无调用点。
4. 旧适配器 290568 B 正文本地无副本，只能以"旧文件中未登记变化 0 + 旧 17 签名与既有指南一致"承担，不能声称旧正文逐字未变。

## 6. 保护、历史与业务边界

R1 交付定稿后执行**一次**全树保护扫描：基线 TASK-039-R1（168839 项 / `43fa7288…ccae2`），相对基线既有 changed 仅 `scripts/runtime_gate1.py`；全部新增逐确切路径登记（执行端两轮证据与架构端本轮自有产物），新 missing/读取错误/未登记新增 0。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`；AI/终判/真实数据/强认证未获授权，本接受不改变该状态。

## 7. 接受与下一卡

本次发布新接受基线（`data/reviews/task040_dsh_r1_20261017_01/source_hashes_after.json`）与 `review_result.json`，接受 TASK-040-R1 的合成运行层保存/只读恢复实现及证据。下一卡 `docs/tasks/TASK-041_DRAFT.md`：优先硬化 §5 残差（S8 双构造、verify 末段、schema 复测、死代码），不扩大业务权限、不进入 AI/终判。
