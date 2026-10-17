# 运行层 Gate1 单事件保存与有效性核验指南（TASK-027）

本指南描述 `scripts/runtime_gate1.py` 在 TASK-027 后新增的两个公开 API。范围**止于 Gate1 记录**：
不接标准化 / SQLite / Gate2 / 宿主（0001—0008）/ 初判 / AI / 终判，不生成 0009，不提供 CLI。
**登记与保存都不是批准**：`effective=true` 只说明该记录在当前材料下满足 Gate1 前提，
不构成执行许可；真实批准仍为 `null`，宿主仍为开发态 `0008`，`next_step_allowed=false`、`ai_enabled=false`。

## 1. 公开 API（本脚本共五个，仍无 CLI）

```text
build_runtime_registry(batch_dir, runtime_dir, *, scope_dir)            # TASK-026
read_runtime_registry(runtime_dir)                                      # TASK-026
prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id)       # TASK-026
save_runtime_gate1_decision(batch_dir, runtime_dir, request_id,
                            submission, event_dir, *, scope_dir)        # TASK-027
verify_gate1_effective_approval(batch_dir, runtime_dir, *,
                                scope_dir, event_relative)              # TASK-027
```

前三个 API 的语义**未放宽**：仍要求计划 scope 尚不存在（`_validate_registry` 的
`allow_existing_scope` 默认 False，只有 `verify` 的私有已核验分支为 True）。

## 2. save_runtime_gate1_decision

**每个运行登记只保存一个 Gate1 事件，一次写定**：不做追加、修改、撤销、修订链或跨 scope 发现。

成功返回外边**恰三键**：`record`（真实冻结 P1 的 17 键正文）、`record_fingerprint`、
`event_relative`。`record` 从已保存的 `snapshots/decision_result.json` 读回，并复算规范指纹核对。

保存顺序（与实现一致）：

1. 实读核验登记与调用方 `scope_dir` **严格相符**；事件路径必须是该 scope 的严格后代且**从未存在**；
   scope 初始必须不存在；全程对原始路径逐级 reparse 检查并在 resolve 后复查。
2. 获取**同级技术锁**（见 §5）。已存在即拒绝。
3. 锁内真实调用一次现有 `prepare_runtime_gate1_request`，**自行**取得当前请求与独立预期；
   不接受调用方传入 request/status，也不从 `submission` 取预期。
4. 锁内实读确认计划 scope 仍不存在，形成显式三键空历史：
   `{"declared_complete": true, "declared_scope": <scope 项目相对路径>, "records": []}`。
5. 比较 `submission` 与当前独立预期：批次、`gate=GATE1`、`request_binding.request_id`、
   `request_binding.materials_binding`、`prior_decision_binding is null`、`decision ∈ {APPROVE,HOLD,REJECT}`、
   `actor.actor_kind = HUMAN_DECLARED`，人类字符串（`decision_source`/`decided_at_raw`/`reason`、
   `actor.actor_id`/`declaration_note`）**原文保留、不代填**。错绑定不建事件。
6. **只调用一次**冻结 `store.save_human_gate_decision_snapshots`（其内部自己调用一次 P1；
   本层不做直接 P1 预调用）。真实核心拒绝**不得**形成成功事件。
7. 本层独占写 `context.json`（封闭十键）与 `receipt.json`（封闭九键，不含自身 SHA），
   canonical UTF-8 + 单 LF，并读回精确核对。
8. 全部必要消费后做一次有界原始字节/集合/路径确认：32 项来源、登记两文件、事件 2 文件 +
   快照六文件、`scope/event/snapshots` 固定集合、无 `failure.json`、静态绑定与自脚本路径字节。
9. 释放自锁后返回；**成功时锁不得残留**。

失败协议：事件已建立后的失败在本层独占写五键 `failure.json`
（`failure_version = TASK-027-runtime-gate1-failure-1.0`、`stage`、`field`、`reason`、`cause_chain`）；
没有事件可落盘时正常传播错误，**不为写诊断新造事件**；诊断自身失败保留主/次原因。
写入后失败保留半写与诊断，不覆盖、不重试、不删除凑成功；不存在任何递归删除动作。

## 3. 事件封套

```text
<scope>/
  <event>/                      # scope 恰含本次这一个事件目录
    context.json                # 十键
    receipt.json                # 九键
    snapshots/                  # 冻结 store 的六份固定文件
      decision_result.json  expectations.json  materials.json
      prior_history.json    submission.json    manifest.json
```

- `context.json` 十键：`context_version`（`TASK-027-runtime-gate1-context-1.0`）、
  `source_batch_relative`、`runtime_relative`、`scope_relative`、`event_relative`、
  `registry_file_sha256`、`request`（本次完整六键请求）、`prior_history`（显式三键）、
  `store_result`（那次真实保存的完整返回）、`boundaries`。
- `receipt.json` 九键：`receipt_version`（`TASK-027-runtime-gate1-receipt-1.0`）、`batch_id`、
  `event_relative`、`scope_relative`、`context_file_sha256`、`snapshots_manifest_file_sha256`、
  `record_fingerprint`、`registry_file_sha256`、`boundaries`。receipt 最后保存、不内嵌自身 SHA。
- 两处 `boundaries` 均为封闭五键且**全部严格 false**：`execution_allowed`、`workflow_connected`、
  `ai_enabled`、`identity_authenticated`、`source_authenticity_proven`。
- 冻结 P1 记录正文自身的 `boundaries` 是六键（`persisted`、`approved_for_execution`、
  `human_initial_judgment_saved`、`ai_enabled`、`identity_authentication`、
  `source_authenticity_proven`），核验要求全部严格 false，并显式要求
  `approved_for_execution is false`（不放行执行）。

## 4. verify_gate1_effective_approval

**只读**，失败不写任何诊断。返回**恰十一键**
（`verification_version = TASK-025-gate1-effective-approval-1.0`）：

`verification_version, batch_id, event_relative, record_fingerprint, record_file_sha256,
run_binding_sha256, materials_fingerprint, decision, actor_kind, effective, reasons`

- 指纹与文件 SHA **分列**：`record_fingerprint` 是 P1 正文的规范指纹，`record_file_sha256`
  是 `snapshots/decision_result.json` 的字节 SHA。
- 先实读事件固定集合与封套，再调用冻结 `store.verify_human_gate_decision_snapshots`
  （其内部再调用一次 P1，**次数分列**），核验全部形状/指纹/来源关系。
- 然后基于**本次已核验的事件**从显式 `runtime_dir` 核验登记与**当前**批次材料：
  私有分支要求 `scope` 恰等于 `registry.scope_ref`、事件恰是该 scope 唯一合法事件、
  `receipt.registry_file_sha256` 匹配本次实读登记、record 的六项绑定/契约/批次闭合；
  并复用同一套材料构造得到当前请求，与保存时 `context.request` 做 canonical 严格比较。
  该分支**不接受任何调用方布尔开关**绕过检查。
- `effective` 判定：仅当**完整合法记录 + `decision=APPROVE` + 记录质量 `OK` + 当前材料质量 `OK`
  + 全部绑定一致 + 无锁/无 failure/无未知项**时为严格 `true`，且 `reasons` 为空。
  合法 `HOLD`/`REJECT` 返回 `effective=false` 且 `reasons` 非空
  （当前实现：`DECISION_NOT_APPROVE` / `QUALITY_NOT_OK` / `CURRENT_MATERIALS_QUALITY_NOT_OK`）。
  结构损坏、错绑定、缺件、失败现场用**可定位 Blocked**；I/O 用 `RuntimeGate1Error` 并保留原因；
  不为凑十一键伪造未知摘要。冻结 P1/store 的异常原样传播并保留 field/stage/reason/cause。

## 5. 技术锁

- 位置：**运行登记叶的同级**，命名为 `<runtime 登记叶名>.lock`（例如
  `data/runtime/task027_run_01/registry_normal.lock`）；同一 `runtime_dir` 映射唯一锁路径。
- 锁目录内只有 `lock.json`，内容为 `lock_version`（`TASK-027-runtime-gate1-lock-1.0`）、
  `runtime_relative`、`event_relative`、`created_at`。
- 由本层独占创建（`os.mkdir`）；其他锁存在即拒绝。
- 只释放**本次实际创建**且身份/内容未变化的锁；释放失败保留完整错误。**不清理他人锁。**
  唯一允许的删除动作就是这个自锁释放。

## 6. 修改代码即新运行版本

代码清单仍恰 14 项（13 冻结脚本 + 本脚本），来源材料仍恰 32 项（31 项冻结来源 + 本脚本），
自身 SHA 实读。**任何对本脚本的修改都产生新的运行版本**：既有登记绑定旧字节，`read`/`prepare`
会以 `registry.run_binding.code.file_sha256` 拒绝，旧登记不迁移，必须用新批次/新登记/新 scope。
运行版本标记：`TASK-027-runtime-gate1-1.0`。

## 7. 测试入口

```text
# 正常观察并定稿（业务只跑一次；产物落在 data/runtime_gate1_decision_tests/<round>/）
.venv\Scripts\python.exe -B tests\test_runtime_gate1_decision.py \
    --out-dir data\runtime_gate1_decision_tests\task027_run_04

# 真实收尾重放（复用上面观察的独立副本，业务调用增量 0）
... --replay <观察目录的副本> --mutate none|checks|payload|late-checks
```

- 注入边界在**正常待写缓冲定稿并写盘之后、正式末次审核之前**（`late-checks` 在末次语义审核
  返回之后），注入只改目标字节/字段，独立期望（`expected_observations.json`）一字节不动。
- 任一审核失败或字节漂移 → 顶层返回 1、磁盘 `summary.status=FAIL`、`failures.json` 非空；
  坏候选保留，不重建期望或台账。
- `--out-dir` 必须在 `data/runtime_gate1_decision_tests/` 的**严格后代**（解析后判定，
  拒绝 `..` 越界、同前缀兄弟、根自身），且必须是新目录/空目录；本轮 `batch/runtime` 根必须从未存在。
- **禁止递归删除、移动或清理任何探针目标**；路径反例只验证“拒绝且未创建”。

## 8. TASK-027-R1 修正要点（补丁版本 `TASK-027-runtime-gate1-1.1`）

公共接口与协议名不变；以下为本轮定点修正后的确定语义。

### 8.1 save 必须绑定**本次** store 输出

- 调冻结 `store.save` 之前先复核：本次已消费的 32 项来源、登记两文件、自脚本、登记叶恰二文件集合
  与“无 failure/未知项”。任一变化即拒绝，且**不创建事件**（这也是“调用前末次来源变更”的证明点：
  该路径下 store 与 P1 的调用增量为 0）。
- store 返回后：先实读 `snapshots/manifest.json`，其**字节 SHA 必须等于该次真实返回的
  `manifest_file_sha256`**；再按该 manifest 的**封闭清单**核验五 payload 的实际长度/SHA。
  不得把 store 返回后的第一份读数直接当作“正确期望”。
- manifest 的 `fingerprints`（六键：submission / materials 快照 / materials 正文 / expectations /
  prior_history / record）必须与本次 submission、材料快照与正文、预期、**显式三键空历史**、
  返回记录指纹逐项相等；`identity`/`scope`/`boundaries` 与该次返回及常量闭合；
  五 payload 与两键 `decision_result.json` 正文与本次输入/请求/批次关系做严格 canonical 闭合。
- 末端确认补齐：批次顶层 + 四个固定子目录、登记叶恰二文件、无 failure/未知项。

### 8.2 verify 先验形状，再闭合全部来源关系

- 所有封套字段**先验对象/封闭键/严格类型/常量/哈希，再消费**：`context.boundaries=[]` 属
  可定位 `Blocked`（`context.boundaries`），不得泄漏原生异常。
- `context.source_batch_relative`/`runtime_relative` 必须等于显式规范化的项目相对路径；
  `context.registry_file_sha256` 必须等于本次实读登记文件字节且与 `receipt` 一致；
  `scope_relative`/`event_relative` 与显式参数一致。
- `context.store_result` 与本次 `store.verify` 返回**除 `status` 外全部稳定字段 canonical 相等**
  （含 `record_fingerprint`、`manifest_file_sha256`、`identity`、`scope` 与五键 false 边界）；
  不一致时按 `store_verify.stable_fields` 列出差异键。

### 8.3 写后异常与失败现场

- 真实 writer（含冻结 store 内部）在**完整写入之后**抛出的任何异常，都由本层映射为
  `RuntimeGate1Error(<stage>)` 并保留原因链与坏字节；是否写五键 `failure.json` 依**实际现场**
  （事件目录是否已存在）判断，不以滞后的“已创建”置位为准；没有事件时不为诊断造事件。
- 主错误与解锁次错误都保留（次错误追加进既有诊断的原因链）。

### 8.4 技术锁：内容 + 取得时身份

- 取得锁时记录锁目录与锁文件的身份（`st_dev`/`st_ino`/`st_ctime_ns`）与确切内容。
- 释放前核对路径 reparse、集合恰一文件、**目录身份、锁文件身份与内容**；任一项不符即保留现场、
  不释放——**同内容但身份不同的替代锁一律不得删除**。
- 取得失败只回收身份未变的自建目录；不清理他人锁；无分布式锁、自动重试或锁恢复机制。

### 8.5 测试入口（收尾与 replay 语义更新）

```text
# 正常观察并定稿（业务只跑一次；out-dir 必须从未存在）
.venv\Scripts\python.exe -B tests\test_runtime_gate1_decision.py \
    --out-dir data\runtime_gate1_decision_tests\task027r1_run_04

# 收尾控制（源目录只读；必须另给从未存在的新 out-dir）
... --out-dir <新目录> --replay <既有观察目录> --mutate none|candidate-return|drop-call|checks-flip|checks-drift
```

- 定稿内存观察为**独立预期**；磁盘 `expected_observations.json` 只是候选；审核为“独立预期 ↔ 磁盘候选”
  逐条 canonical（类型敏感）比较 + ID/条目/检查双向一致；台账由**本次待写缓冲**给出（含终审诊断缓冲）。
- `--out-dir` 必须**从未存在**且为证据根严格后代；`--replay` 的源目录**全程只读**。
- 收尾控制（closure-only）：`none` → 0/PASS；`candidate-return`（候选返回与候选 expected 同步替换、
  独立预期不变）、`drop-call`（少一条 API）、`checks-drift`（待写缓冲后 checks 字节漂移）
  → 1/FAIL（磁盘 FAIL、failures 非空、坏候选保留）。
- 探针目标一律保留：坏场景使用**独立新 scope**，不删除、不移动、不清理任何探针目标。

## 9. TASK-027-R2 修正要点（补丁版本 `TASK-027-runtime-gate1-1.2`）

仅修三组残余收尾问题；协议名、公共接口与单事件模型不变。

### 9.1 verify 的末次有界确认补登记叶与批次集合

`verify_gate1_effective_approval` 在**全部材料/结果消费之后**的最后一次确认中，除既有
`scope`／`event`／`snapshots` 固定集合与无 `failure` 外，还复查：
批次顶层与四个固定子目录集合、登记叶恰 `[runtime_registry.json, runtime_registry_readback.json]`、
**登记叶无 `failure`／未知项**。verify 仍为只读，失败不写任何诊断。

### 9.2 锁取得失败保留现场；主次错误都可见

- 取得锁时写 `lock.json` 失败**不再自动回收**该锁目录：保留锁与半写现场，传播
  `RuntimeGate1Error("lock", …)`（若为 `Blocked` 则原样传播），不删除未知身份/内容的文件。
- 无事件与已有事件两种情形，主错误与真实解锁次错误都可见：次错误以
  `release_lock: …` 追加进主错误的 args/`reason`，并在 `secondary_errors` 中列出；
  原 `field`／`reason` 主体保留。
- 已有事件时，五键 `failure.json` 在**主次错误都已确定之后一次独占写定**（原因链同时含主错误与
  `release_lock` 次错误），不再事后覆写；诊断自身再失败则保留主次原因与坏候选；
  没有事件时不为诊断造事件。有效自锁正常释放不退化。

### 9.3 测试：磁盘台账与诊断后末次确认

- `file_ledger.json` 候选**实读回核**（对象与字节同一次读取），其预期字节来自本次**待写缓冲**；
  清单覆盖全部正式载荷（含最终诊断），不内嵌自身 SHA。内存台账正确不能替代磁盘台账正确。
- 正常成功路径：先定稿诊断（由定稿内存预期决定其状态），再一次写定诊断与台账；
  末次实读覆盖正式载荷与台账；**之后不再读候选 summary/failures 生成成功输出**，改用已核验内存对象。
- 任一审核或字节失败实际支配顶层 1／磁盘 FAIL／非空 failures，保留坏目标；失败元数据可在失败路径
  如实落盘，但不再报成功。
- 控制（复用同一次观察的新副本，经实际 CLI）：`none` → 0/PASS；`ledger-replaced`
  （写后将磁盘台账改为 `[]`）→ 1/FAIL 且定位 `ledger_mismatch`；`diagnostic-drift`
  （最后一次诊断 writer 完成之后给 checks 加 LF）→ 1/FAIL 且定位 `drift:checks.json`；
  `candidate-return`／`drop-call`／`checks-drift` 作为 closure-only 对照保持。
- 计数口径：公开 API 计数只取 `public_api_calls_by_name_profile`；冻结准备模块的
  `frozen_prepare_module_original_function_profile` 是**函数计数**（含 save 内部调用），
  不是公开 API 调用数；`prepare_original_code_calls_from_test_direct` /
  `..._from_save_internal` 分列 wrapper 与原始 code 对象角色。

### 9.4 GPT 定点补正：台账确切字节与最后消费点

台账首次读回由同一缓冲产生对象与原始字节，两者分别核对本次内存清单与待写缓冲；
尾加 LF 即使不改变 JSON 对象，也必须失败。全部候选语义消费完成后，末次原始字节确认覆盖
九份载荷及台账自身，预期均来自本次待写缓冲；台账正文不内嵌自身 SHA。
成功输出使用已核验内存中的失败列表，不再读取候选 `failures.json`。失败路径保留坏目标、
不重建台账，并以退出 1、磁盘 FAIL 和非空 failures 收尾；生产适配器不受本项修改影响。

观察包装安装前保存冻结 prepare/store/P1 各原函数的代码对象；`EntryObserver` 使用该原始身份
进行 profile 计数，不把测试 wrapper 的代码对象称为核心入口。准备器 wrapper 次数由完整观察
记录条数分列，与原函数帧计数独立核对。
