# 运行层人类独立初判保存 / 只读恢复指南（TASK-040 / R1 / 041 硬化）

标识：`TASK-041-runtime-initial-judgment-recording-1.2`。实现身份：`scripts/runtime_gate1.py`
（TASK-041 唯一被修改的既有实现文件）。设计身份：TASK-039-R1 已接受的运行保存协议/案例。

本层只新增两个公开入口；**`RECORDED` / `VERIFIED` 都不是批次批准、不是身份认证，不开放 AI 或终判**。
真实批准仍 `null`，真实独立初判未保存，开发宿主 0008，`next_step_allowed=false`、`ai_enabled=false`。

TASK-041 硬化（相对 TASK-040-R1）：
1. **S8 双构造**：候选由本次真实返回/写后捕获组装（`store.save` 真实返回、H1/Hc 真实 history 返回、
   三封装 writer 缓冲）；预期只由已核验源、目标叶六文件字节与 manifest、E1/H1、本次 writer 缓冲
   **独立重建**（`_rebuild_success_040` / `_rebuild_storage_verification_040`），两者做完整 canonical
   比较。任一构造器错误都会被 `Blocked result.<差异路径>` 或 `Error audit.result` 发现。
2. **verify 末段完备**：verify 的末次确认同样传入 `target_leaf/target_captures`，复确认目标叶六件集合与
   failure；全程只读。
3. **S5 schema 复测**：`_pre_store_confirm_040` 复测 `sql/demo_schema.sql`（及归一化/装载核心），
   沿 `_capture_static_028` 口径；失败精确 Blocked 到相对路径。
4. **死代码与静默路径**：删除无调用点的 `_initial_snapshot_objects_040`/`_initial_target_name_040`；
   `_confirm_initial_history_040` 对"非本次目标缺缓冲"显式 `Blocked history.entries[i]`；坏 envelope
   failure 的缺键/未知键精确到 `failure.<子键>`。
5. **遗留**：store Blocked 的 `reasons` 原样复制（行为等价记录）；旧适配器 290568 B 正文本地无副本，
   只能以"旧文件未登记变化 0 + 旧 17 签名与既有指南一致"承担，不伪造基线。

## 1. 两个入口

```python
save_runtime_initial_judgment(
    batch_dir, runtime_dir, request_id, submission, record_relative, *,
    scope_dir, event_relative, database_path, gate2_event_relative, history_expectations)
verify_runtime_initial_judgment(
    batch_dir, runtime_dir, *, scope_dir, event_relative, database_path,
    gate2_event_relative, record_relative, history_expectations)
```

参数按签名顺序检查类型。`save` 正常调用图：公开 `prepare` 1 次 → 冻结 `store.save` 1 次 → 保存后
`history.inspect` 1 次（prepare 内部另有 1 次保存前 history，合计 2）。`verify` 只读：直接
`history.inspect` 1 次、Gate1/Gate2/fact 各 1 次；公开 prepare/store.save 0；初判 `store.verify`/core
各 m 次。硬化新增的 `_rebuild_success_040` 只在 save/verify 各调用 1 次，**单列计数，不并入业务公式**。

## 2. 阶段、失败与审核

- 成功返回恰十二键：`stage_version,status,scope,identity,record_relative,record_fingerprint,
  manifest_file_sha256,storage_verification,envelope_binding,history_verification,boundaries,note`；
  九权限边界严格 `false`；`storage_verification` 是目标完整 `VERIFIED` 返回。
- 本层阶段名：`path, lock.acquire, lock.confirm, release.lock, write.started, write.context,
  write.receipt, read.envelope, read.failure, bind.store, history.post, audit.result, save.final,
  verify.final`；冻结组件 `Error.stage` 原值传播。
- 冻结组件 `Blocked` 保留原 field 并加 `store.` / `history.` 前缀（store `reasons` 原样复制）。
  读取失败诊断：有效 `BLOCKED` 加 `runtime.failure.`（本层十一键）或 `store.failure.`（冻结 store
  十键）前缀；有效 `ERROR` 保留原 stage；坏诊断先按 schema `Blocked`，缺键/未知键精确到 `failure.<子键>`。
- **S8 审核顺序**：① 封闭 schema/严格类型/常量（含 `storage_verification` 十一键集 →
  `Blocked result.<字段>`）→ ② 候选与独立重建预期完整 canonical 比较（首差 →
  `Blocked result.<差异路径>`）→ ③ 内部内容审核（identity/记录指纹/manifest FILE/十一键稳定字段/
  历史核验/三封装 FILE 与实读缓冲）→ 非空问题抛 `Error audit.result` 且 `reasons` 保留问题列表。
- 保存失败时，只有本次已独占创建运行封装才写一次 `failure.json`（十一键，无时间字段、不覆盖坏诊断）；
  失败不删除已有成功叶/锁/半写。

## 3. 路径与布局

- 历史直接叶：`data/human_initial_judgment_records/<轮次>/<声明域>/<叶名>/`，恰六文件
  `expectations.json, judgment_result.json, manifest.json, materials.json, prior_history.json,
  submission.json`；不放 context/receipt/锁/日志。
- 运行封装：登记（runtime）叶同级 `<登记叶名>.initial/`，成功恰 `started.json, context.json,
  receipt.json`；失败时可能另有 `failure.json` 或半写。
- 技术锁：namespace 同级 `<namespace叶名>.initial_judgment.lock`，正文五技术键。
- `record_relative` 必须恰为已绑定 `namespace_relative` 加一个安全直接叶段；原路径链先于消段检查。
- 新 profile：`REGISTRY_VERSION=TASK-040-runtime-registry-1.0`、
  `CODE_MANIFEST_VERSION=TASK-040-code-manifest-1.0`、`RUNTIME_VERSION_028=TASK-040-runtime-gate1-1.0`；
  代码清单 17 项；Gate1 材料 40 项。旧 TASK-038 凭证按版本/身份拒绝，不迁移、不补签。

## 4. Windows 真实独占句柄锁

`CreateFileW` + `CREATE_NEW`，请求读/写/删除、**仅共享读**；取得后记录父目录身份、句柄
`FILE_ID_INFO`、属性、大小与本次待写缓冲；写后按同句柄读回。成功释放前核对父目录身份、原路径
file ID、持柄属性与字节，再对已持有句柄设置删除标记（优先 POSIX 语义）并关闭，最后确认原路径解除；
失败不设删除标记、保留锁/半写并关闭本次句柄；外来锁永不释放；`verify` 不取锁。

## 5. 测试入口与证据

```
.venv\Scripts\python.exe -B tests\test_runtime_initial_judgment_recording.py \
  --out-dir data\runtime_initial_judgment_recording_tests\task041_<新名>
```

正常链与场景根：`data/runtime/task041_*`、`data/human_gate_decision_records/gate1|gate2/task041_*`、
`data/sqlite_tests/task041_*`、`data/human_initial_judgment_records/task041_*`。
本入口包含：B3 取锁序控制、B1 S5 复确认控制、正常 save/verify、m=2 后来 batch 恢复、单文件漂移与
精确恢复、RC-44 B/C 角色控制（A 读路径）、RC-40/RC-08/RC-09 审核控制、H1 公共路径候选构造控制、
H3 S5 schema 漂移控制、H4 坏 failure 缺键/未知键与缺缓冲控制，以及 8 条失败场景链
（`f01, f03, f04, f05, f06, rc44b, h1_candidate_control, h3_schema_drift`）。
四项 CLI：正常 0，`--replay <正常目录> --mutate candidate-return|ledger-replaced|late-drift` 均 1。

证据文件：`expected_observations.json`、`summary.json`（含运行前固定的
`results.independent_expectations` 与 `results.hardening`）、`api_records.json`、`core_records.json`、
`checks.json`、`failures.json`、`audit_failure.json`、`file_ledger.json`。
