# TASK-040 独立验收（DSH Architect）

结论：**NOT_ACCEPTED**。2026-10-17，DSH 架构/测试验收端独立复验。实现主体（两入口、摘要角色、真实句柄锁、只读恢复、异常映射、新 profile）经验证与卡及已接受设计 1.1 一致，但存在 **4 项阻断级流程偏离**（S5 复确认缺失、S9/V8 末次集合/failure/锁确认不足、取锁早于域/scope 校验、S8 返回审核契约不符）与 **4 项必需证据缺口**（RC-40、RC-44 三变体、独立预期先于候选、RC-22 半写方式）。本文件不以执行回执的自报 PASS 为结论；最后一次接受基线仍为 TASK-039-R1（168839 项 / `43fa7288…ccae2`），本卡**未替换**接受快照。

## 1. 交付与身份

四件交付由实际同一缓冲核长度/SHA，与执行回执一致：

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | 389797 B | `7b3267153cbaf192360403e92d429d45af701bec6cd3f4f1bb1d7dcbf508345d` |
| `tests/test_runtime_initial_judgment_recording.py` | 46473 B | `a4e285feaadbac6e67be81875b84b9681081eaf9aeeedafa0070f5ebf804ddef` |
| `docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` | 7807 B | `673844fea3cd136d55a52bbb4cb9ef38c464f4416136af28458e5ed686c72e12` |
| `docs/EXEC_REPORT_040.md` | 11196 B | `65776fe2af59e4b0f121fde390b6ef5127298ef388569d6f2f0d8a14732afd5d` |

卡 `docs/tasks/TASK-040_DRAFT.md`（`a1fb5e0f…b521a1`）、设计协议/案例（`0b92e8…6b2db` / `177d58…729b`）、冻结 core/store/history 三件身份均实读匹配。相对 TASK-039-R1 接受基线，唯一既有变化为适配器；1018 项新增由执行端 `task040_finalization/protection_result.json` 逐路径登记。

## 2. 独立实际运行（架构端自跑，非引用执行端）

- **正常链复跑**：`data/runtime_initial_judgment_recording_tests/task040_dsh_01`，56/56 checks、`api=17`、`core=341`、`exit 0`、failures 空。seven 具名失败场景在同一定稿代码下复现准确 field/stage（`store.submission.assessment`、`store.submission.request_binding.materials_fingerprint`、`write.expectations.json`、`write.context`、`write.receipt`、`release.lock`、`lock`），锁/半写/坏字节全部保留。
- **四项 CLI**：架构端四个新进程 `--replay task040_run_05` → 0 / 1 / 1 / 1（`failures.json` 分别为空、`api_records_mismatch:call_001`、`ledger_bytes_mismatch+ledger_mismatch+drift`、`bytes:drift:checks.json`）。
- **内容独立重算**：`recompute.py` 49/49 PASS（只读磁盘字节）：六叶五载荷 FILE+FP 同缓冲一致、`record_fingerprint=FP(record)`、`run_binding_sha256=FP(registry.run_binding)` 且 ≠ FILE 且 ≠ FP+LF、`request_sha256=FP(request)`、receipt 对 context/started/manifest 的 FILE 绑定、H0 为空/H1 恰本次目标 1 叶/调用方名单为当前 Hc 2 叶、旧叶 `z_first` 与 TASK-037 已接受源逐字节相同、九/八边界严格 false、save 调用图逐窗口等于卡的公式且算法/SQL/事实 build 为 0、STORED 11 键与 12 键返回集合。
- **Windows 句柄锁**：`probe_locks.py` 10/10 PASS：真实 `CREATE_NEW` 独占；持锁期普通读取与重命名被拒（请求删除权+仅共享读的真实结果）；二次独占被拒；按已持有句柄释放后路径消失、可重新获取；失败现场锁恰五技术键、无 owner/时间/随机。
- **profile/拒绝路径**：`probe_profile.py` 9/9 PASS：旧 TASK-038 登记按版本/身份拒绝；19 API/17 代码/40 材料（含两个新提案固定身份）；公开 prepare 仍有同 batch 历史时拒绝且实现零写入。

## 3. 阻断级偏离（必须修正后才可接受）

**B1 S5 复确认缺失。** `save_runtime_initial_judgment` 在 started 写回比较（L5878-5881）后直接 `stage="bind.store"` 调用冻结 `store.save_human_initial_judgment_snapshots`（L5888-5891），**未在 store 前复确认** S3 开始依赖、H0 旧叶六字节/集合、原路径、锁句柄及 started writer 缓冲。协议 S5（第 66 行）明文要求该复确认；案例 RC-11（第 38 行）要求漂移时“S5 指向该来源 Blocked，store.save/core 构建增量 0”。实际后果：S3→S5 之间若发生来源/旧叶漂移，store/core 仍会执行并已建成目标叶，只在 S9 拒绝——与 RC-11 相反，且“增量 0”不可满足。

**B2 S9/V8 末次确认不足。** `_confirm_initial_sources_040`（L5701-5727；save 调用 L6014，verify L6400-6411）只做文件字节复读、输出目录固定成员与 history 成员/旧叶，未复用冻结 `_confirm_approved_terminal`（L2448-2486）与 `_confirm_gate2_terminal_030`（L3177-3188），因此漏掉：batch 顶层/子目录集合、登记叶集合与 failure、Gate1/Gate2 scope/event/snapshot 集合与 event failure、load 目录集合与 failure、数据库目录集合、Gate1/Gate2 锁。save 末段只查目标叶 failure 而不重查六件集合；verify 末段只重读三封装文件而不重查封装集合。与协议 S9（第 78 行）、V8（第 104 行）及卡§37/§60“末次原字节/集合/路径/failure/锁确认”不符。

**B3 取锁早于域/scope 校验。** `history_expectations` 的 `expected_namespace_relative` / `expected_declared_scope` 校验发生在 L5811 已独占建锁并写正文之后（L5821 → L4577-4581）。案例 RC-12/RC-13（第 39-40 行）要求“无本次锁/叶/封装”“业务 0”。实际：参数/域错会**永久留下本次锁**，等于用一次调用错误毒化该 namespace。

**B4 S8 返回审核契约不符。** `_audit_initial_success_040`（L5648-5685）以 `success.*` 为 Blocked 字段基名，协议 S8（第 76 行）明写“候选类型矛盾精确 Blocked `result.字段`；内部内容审核产生非空问题时 Error `audit.result`”。实现只产生 `Blocked success.*`，不存在 `Error audit.result` 分支；且 L5655 允许 save/verify 两个入口状态常量任一，未按入口校验（协议第 226 行 status 按入口分别为 save_status/verify_status）。

## 4. 必需证据缺口（卡明文要求，未执行或措辞超出证据）

- **E1 RC-40 未执行**：案例要求“候选合法形状替换内容 → Blocked result；内部审核 FAIL → Error audit.result 并支配外层，不回填期望”。case_map 自行登记“未注入”，但卡§5.4 明写“至少一例形状合法、摘要自洽但完整内容错，不重采预期”。
- **E2 RC-44 三变体未执行且映射虚报**：案例 RC-44（第 71 行）要求 A/B/C 三变体分别在 S4/S8/V3 精确 Blocked（`source_binding.registry_binding.run_binding_sha256`、`context.prepared_request.request_sha256`、`receipt.context_file_sha256`）。case_map 称“在 S4/S8/V3 逐字段核对”，但测试全文无该比较；S4 只比 identity 三元组、S8 只比文件集合、V3 只比调用计数。
- **E3 独立预期未先于候选**：`expected_observations.json` 由 `run()` 之后 `freeze_expectations()` 冻结（`main` L892），`build_candidate` 直接 deepcopy 该对象（`tests/test_runtime_approved_load.py` L1096-1129），故首次运行的 audit 恒等；V1（L534-541）为两次 SUT 自报值互比；无 `storage_verification` 十一键键集断言。与卡§5.8/§6“独立预期先固定、支配 main/summary/failures”不符（三种 replay mutate 仍有效，但只证明台账可校验，不证明首轮期望独立）。
- **E4 RC-22 半写方式不符且 RC-08/09 未执行**：f03 在 L704-709 用自建句柄写半份后抛 OSError，**整体替换** `store._write_exclusive`，真实 writer 从未执行；案例 RC-22（第 49 行）要求“只包装句柄写半份后 OSError，不替换整个 writer”。f06 为函数级桩（L736）可接受但回执“技术释放失败实测”措辞需注明注入层级。严格类型与反序多错首报（RC-08/09）未做动态核对。

## 5. 非阻断级问题（同卡修正即可）

参数类型检查顺序未按签名（L5775-5783 先于 L5785-5796）；坏 failure 双前缀（`failure.failure.*`、`store.failure.failure.*`，L6138/L6148 叠加 L6079-6087）；store Blocked 的 `reasons` 恒为 `[reason]`（行为等价，仅记录）；无法判定旧正文逐字未变（本地无 290568 B 基线副本，只能确认旧 17 签名与既有指南一致）。

## 6. 未执行与真实业务状态

物理 junction（无权限）、真实数据、强认证、AI、终判、并发双进程真实竞态、非合作篡改证明均未执行：null + 原因。真实批准仍 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。技术复验不批准任何真实批次，不认证身份。

## 7. 保护与历史

按“先定稿、后一次全树扫描”执行：架构端自有脚本/观察/锁实验/正常链复跑/四项 replay 全部落在 `data/reviews/task040_dsh_20261017_01/` 与 `task040_dsh_01*` 确切根内；未修改交付、生产、旧证据或看板。唯一既有 changed 仍为 `scripts/runtime_gate1.py`；新 missing/读取错误/未登记新增须为 0。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续单列冻结，不追认。实际扫描数字与逐路径登记见同根 `protection_result.json`；本文件不以文字替代扫描结果。

## 8. 下一步

发布定点修正卡 `docs/tasks/TASK-040-R1_DRAFT.md`（B1—B4 实现修正 + E1—E4 证据补齐 + 非阻断项），执行端按卡修正后重新交独立验收；本文与 `task040_run_05` 全部现场原样冻结，不删移、不清理。accepted 基线未被本结论替换。
