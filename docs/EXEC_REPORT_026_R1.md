# TASK-026-R1 执行回执：补齐登记来源/恢复/末端与实际测试证据

日期：2026-10-15。任务卡：`docs/tasks/TASK-026-R1_DRAFT.md`（`9bba426a33eec5e0eb83b452623150a6ff528245bb734986a284a17235d7bc1e`）。
依据：`docs/reviews/REVIEW_TASK_026.md`（`8d6b9476aeeae4c4a923e2f63869d370d846fb5a81f493f6b1e3ac622e476750`，**NOT_ACCEPTED**）。
分类：**B 类定点修复**（DSH 实施、GPT 验收）。只处理 B1/B2/B3/E1，未新增功能、架构、案例体系或业务判断；
未修改冻结 prepare/P1/store/契约/宿主/控制器；未推进 TASK-027。

## 1. 起点核对（只读实读）

| 对象 | 要求 | 实读 | 一致 |
| --- | --- | --- | --- |
| `scripts/runtime_gate1.py` | `360be2f50d441f0c7d8c883704bba3da6c57b57920ef6e83ed4bce7b4db834a5` / 43166 | 同 | ✅ |
| `tests/test_runtime_gate1_registry.py` | `f15681114d59b5a08ccf2d6643afb0a981828d3318d6f7382c8011fdc389f633` / 39889 | 同 | ✅ |
| `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md` | `3928887b9f8fee78766aca488afd101143c5b30e0cb05e6a69c571d20ffce62e` / 5932 | 同 | ✅ |
| 基线 `data/reviews/task026_gpt_20261015_024732/source_hashes_after.json` | 见同根 `review_result.json`（157436 项） | 同 | ✅ |
| 冻结准备器 | `ce23671f…0ac4`（本层对它有**独立预期**常量） | 同 | ✅ |

## 2. 交付物

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（修改） | 55702 | `d27d3289245d6ddffa4da9aac0c11848795e9a13f606a891f5458af5ede0e6e8` |
| `tests/test_runtime_gate1_registry.py`（修改） | 45350 | `2e46a9e48fee042bb13672188c9d441a4f1bdfed9ddbb191bc72207007a10e0d` |
| `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md`（修改） | 7048 | `cede81881a0822c713f0e27b385980c24c7b6287c68ab0e5bda33300ae7d85f2` |
| `docs/EXEC_REPORT_026_R1.md`（本回执） | 见交接消息 | 最终 SHA 见交接消息（避免自指） |
| `data/runtime_gate1_registry_tests/task026r1_run_01/`（正向轮次证据） | — | 见 §6 |
| `data/runtime_gate1_registry_tests/task026r1_auditfail/`（失败支配证据） | — | 见 §6 |
| `data/batches/task026r1_run_01/`、`data/runtime/task026r1_run_01/` | — | 逐项见保护扫描新增登记 |

## 3. B1 关闭依据：三 API 末端确认以**操作起始读数**为准

- 新增 `_capture_file()`：一次实读取字节 + 长度 + SHA；所有消费读数（批次八文件、项目材料、
  自脚本字节、两份登记输出、冻结准备器自身）都经它固定。
- `build`：来源八文件与项目材料、自身字节在**写盘前**固定；两份输出预期来自**本次待写缓冲**；
  写盘后读回与缓冲逐字节比较；随后 `_recheck_capture` 对**全部消费文件 + 两份输出**做原始字节
  复确认，并核对叶目录集合、两份输出的 reparse 与 scope 未被创建。
- `read`：登记/readback/自身字节各自固定后，除结构/派生核验外，末端再复确认三者与目录集合。
- `prepare`：来源与登记读数固定后，末端复确认批次八文件、项目材料、自身字节、**registry 与 readback**、
  目录集合与 scope 状态；任一漂移即 Blocked 并指向目标。

**最低定点复现（本轮实测，包装真实 reader 在指定读数之后注入一次变化）**：

| 注入点 | 实际结果 |
| --- | --- |
| `prepare` 读到 `source/input.xlsx` 之后追加 LF | 本次拒绝：`RuntimeGate1Blocked: prepare.batch_manifest.json.hashes.source_before_copy`（批次清单声明的输入 SHA 与实读不符）；撤销后恢复成功 |
| `prepare` 读到 `runtime_registry.json` 之后追加 LF | 本次拒绝：`RuntimeGate1Blocked: runtime_registry.json`（末端字节不一致） |
| `prepare` 读到 readback 之后新增 `failure.json` | 本次拒绝：目录集合异常（指向登记叶） |
| `prepare` 读到 readback 之后新增未知文件 | 本次拒绝：目录集合异常（指向登记叶） |
| 无注入对照 | 成功，`request_sha256` 稳定 |

`build` 侧同类接缝由 §4 的半写注入覆盖：写 readback 时真实抛 `OSError`，生产 writer 自身映射为
`RuntimeGate1Error(write.readback)`，不再出现“写后 hook 假装半写”。

## 4. B2 关闭依据：封闭 schema、静态/派生关系、I/O 映射

`read` 现在**先判类型再消费**，并完整核验：

- 顶层 13 键键集；`registry_version`/`note` 常量；`scope_ref` 前缀 + 记录根后代 + reparse 链；
  `batch_files` 恰 8 项、`batch/` 前缀、严格非负整数长度、恰好为接收批次八文件集合、升序唯一；
  `code_manifest` 恰 14 项 2 键形状（等于冻结 13 项 + 本脚本）；`rules_manifest` 恰 4 项 4 键、
  `rule_id`/`rule_version`/路径逐项闭合；`config.config_ref` 常量；`input.input_ref` 常量；
  `contract` 三键与冻结契约 SHA；`run_binding` 四键/六字段形状与严格类型。
- 跨字段派生：`run_binding.code.manifest_fingerprint == 指纹(code_manifest)`、
  `rules.manifest_fingerprint == 指纹(rules_manifest)`、`code.file_sha256 == 清单中本脚本条目`、
  `config/input` 与 `registry.config`/`registry.input` 一致、`batch_files` 的输入条目与 `registry.input`
  长度/SHA 一致、`run_binding_sha256 == 指纹(run_binding)`、readback 四项与登记正文/文件/长度/内层摘要一致。
- 静态身份：核对**本次**处理的 13 项冻结代码、4 项规则、冻结配置与**冻结准备器**
  （`FROZEN_PREPARE_SHA256` 独立预期常量，不依赖其自身不在 `FROZEN_PROJECT_SHA` 的事实）
  以及本脚本本次字节；`_SELF_BYTES` 全局缓存已删除，改用每次实读（`self_sha256()`）。

**最低反例（同一审核 helper 之外，直接用 API 复现；每项均同步全部外层摘要）**：

| 反例 | 结果 |
| --- | --- |
| `note=""` | Blocked `registry.note` |
| `contract_effective=false` | Blocked `registry.contract.contract_effective` |
| `code_manifest.entries=[]` | Blocked `registry.code_manifest.entries` |
| `config.file_sha256` 错值 | Blocked（`readback.registry_sha256` 之后按内容判定） |
| `input` 未知键 | Blocked `registry.input` |
| `batch_files[0].byte_size=1.0` | Blocked `registry.batch_files[0].byte_size` |
| 内层 `manifest_fingerprint` 尾 LF（同步 `run_binding_sha256` 与全部外层摘要） | Blocked `registry.run_binding.code.manifest_fingerprint` |
| 顶层 `[]` / `code_manifest=["not-an-object"]` | Blocked（无原生 AttributeError/TypeError 泄漏） |
| 真实 `Path.iterdir` 抛 `OSError` | `RuntimeGate1Error(list.runtime_dir)`，保留原因 |

## 5. B3 关闭依据：scope 计划路径语义 + 逐级路径

- `_check_scope_dir` 改为：Gate1 记录根**严格后代**、**必须尚不存在**（父目录存在）、reparse 链检查；
  **已存在（含空目录）即拒绝**。`_validate_registry` 只核验 `scope_ref` 的形状/后代/reparse，不要求存在；
  三 API 末端都会拒绝“scope 在操作期间被创建”。
- 指南与测试的反向断言已同步改回（指南 §2 `scope_dir` 条目 + 测试 3.5—3.8）。
- 逐级路径：`_reject_reparse_chain` 按**原始绝对路径**逐级 `lstat`，再 resolve 复查；
  `lstat`/`exists` 的真实 `OSError` 映射为 `RuntimeGate1Error(stage)`；批次固定子目录/文件、
  项目文件、运行文件、两份输出均逐级检查。

**已知空目录 `data/human_gate_decision_records/gate1/task026_run_01_scope`**：
由**本执行端在 TASK-026 实施时**创建（作为 `scope_dir` 参数的空目录容器，命令为
`New-Item -ItemType Directory`），TASK-026 评审已登记其存在与时间。按本卡要求**保留不动、不追认、不删除**；
本轮 R1 的新 scope 一律使用**尚不存在**的新路径（`task026r1_run_01_scope` 等），未创建任何 scope。

## 6. E1 关闭依据：可信、可重复的小型测试收尾

- **入口约束**：`--out-dir` 必须在 `data/runtime_gate1_registry_tests/` 之下且为**新目录/空目录**；
  本轮根 `data/runtime/task026r1_run_01`、`data/batches/task026r1_run_01` 均**从未存在**；
  **删除**了旧的固定路径与递归删除旧现场的 `fresh_leaf` 行为（旧 `task026_run_01` 只读保留）。
- **真实半写**：包装真实 `open`，使生产 writer 打开的**真实独占句柄**（模式 `xb`）一次 `write`
  仅写入部分缓冲后抛 `OSError`：实测 `bytes_written=175 / expected=351`、`mode="xb"`；
  生产 writer 自身映射 `RuntimeGate1Error(write.readback)`，叶内留下五键 `failure.json`
  （`cause_chain` 含真实 `injected partial write (real exclusive handle)`），坏字节保留，
  `read` 拒绝该目录。旧的“写完之后 hook 抛错”已删除（`INJECTION_HOOKS` 与 `_run_injection` 一并移除），
  晚变更观测改为测试包装**真实 reader**（`_capture_file`）。
- **守卫装在真实入口**：在**实际运行路径**的模块对象上替换（`scripts/build_demo_human_gate_decision.py`
  的 P1 入口、`scripts/store_demo_human_gate_decision.py` 的两个快照入口、
  `scripts/store_demo_sqlite.py` 的装载入口）；`summary.guards` 记录每个被守卫模块的真实 `__file__`。
  本轮 28 次公开 API 调用（含 `prepare` 内部嵌套 read）实测 `guard_hits=[]`、`p1_entry_calls=0`、
  `store_calls=0`、`downstream_calls=0`。
- **观测与证据**：`api_records.json` 按 `call_id` 记录每次公开 API 的完整返回外层键、关键输入、
  返回/磁盘 SHA 与前后文件读数；冻结准备器**嵌套调用次数**单独计数（`observed.prepare_calls`），
  不与公开 API 条数混称；接收器 CLI 记录命令、真实 stdout/stderr 与返回码（normal=0、blocked=1）。
  子进程内部计数按 `null` + 原因登记。
- **定稿与读回**：`summary/checks/failures/api_records/file_ledger` 一次写出并读回，同一审核 helper
  核验 canonical 形态、`checks_total`/`checks_failed`/`failures` 双向一致、`call_id` 唯一且与
  `summary.api_call_ids` 相等、文件台账逐项长度/SHA。
- **失败支配入口**：`--audit-fail` 在定稿前注入一次检查失败 → 磁盘审核不通过 →
  `summary.status=FAIL`、`failures.json` 非空、入口返回**非零**（证据根
  `data/runtime_gate1_registry_tests/task026r1_auditfail/`）。隔离副本删一条 API 记录由同一 helper
  以 `api_call_ids_mismatch` 检出（`isolated_audit.json`）。

**正向轮次实测**：`status=PASS`、`checks_total=71`、`checks_failed=0`、`audit_ok=true`、
`guard_hits=[]`、`prepare_calls=15`、`p1_entry_calls=0`、`store_calls=0`、`downstream_calls=0`。

**证据读回与失败支配的精确状态**：

- `audit.json`：`audit_ok=true`、`problems=[]`、`checks_total=71`、`checks_failed=0`、
  `api_records=3`（`call_001` build / `call_002` read / `call_003` prepare）、`ledger=4`。
- 检查 `6.2` 为**最终读回**：对磁盘上六份证据文件（summary/checks/failures/api_records/
  file_ledger/audit）复读字节并与定稿读数比较，确认无末尾漂移。
- 隔离副本（`isolated_audit/`，在 `6.1` 检查建立**之前**复制）：其 `checks_total=69`、
  `api_records=2`（人为删掉最后一条），同一审核 helper 以 `api_call_ids_mismatch` 检出
  （`audit_ok=false`）。因此 `6.1` 的检出理由为“副本内 API 记录数与 `summary.api_call_ids` 不一致”，
  如实登记、不夸大。
- `--audit-fail` 轮次（`task026r1_auditfail/`）：定稿前注入一次检查失败 →
  `summary.status=FAIL`、`failures.json` 非空、入口返回**非零**（实测退出码 1），
  `audit_after_injection.json` 留存。

## 7. 本轮真实执行 / 注入 / 旧证据读取 / 未执行

- **真实执行**：冻结接收器 CLI 两次（checker 子进程真实退出码 0 与 1）；冻结准备器真实调用
  （`build` 1 次 + `prepare` 每请求 1 次，共 15 次）；本层三 API；独立 canonical/字段/文件 SHA 复算。
- **注入（同进程包装真实函数）**：真实独占句柄半写 1 次；晚变更 4 处（来源、登记本体、新增 failure、
  新增未知项）；枚举 `OSError` 1 次；`--audit-fail` 检查失败注入 1 次；隔离副本删 API 记录 1 次。
- **读取旧证据**：TASK-025 修正版基样、TASK-026 的评审记录与旧交付只读引用；旧 `task026_run_01`
  现场只读保留，**未重跑旧测试入口**（其会删除旧目录）。
- **未执行 / not_executed**：symlink 例因本机 `WinError 1314`（无创建特权）**not_executed**；
  `mklink /J` junction 在 `cmd` 下同样未建立（返回码非 0，`paths.junction_not_executed` 记录原文）——
  **未以其他方式冒充真实路径执行**；未调用 P1/store/标准化/装载/Gate2/筛查/初判/AI/终判；
  未创建决定记录、SQLite、运行 profile、宿主检查点；未重跑历史入口或全量套件。

## 8. 更正旧声明（只写新回执，不改旧文件）

- 旧回执/旧扫描所称“半写注入”实为**完整 registry 写完之后**由生产 hook 抛错；本轮改为真实独占
  句柄半写，并如实登记字节数/模式/原因链。
- 旧回执所称“P1/store/下游入口 0”由加载**另一无关 module** 的假守卫支持；本轮改为在真实入口模块上
  装守卫并记录模块 `__file__`。
- 旧回执所称“隔离副本被 API 拒绝”是业务反例，不替代证据登记审核；本轮另用同一审核 helper
  对**证据副本**删记录检出，并单独验证入口非零。

## 9. 保护与历史留证

- 最终一次全树扫描（`protection_scan_026r1.py` / `protection_scan_026r1.json`，
  `a250c954da04e92333f22a1f037b4a54b6273320815e2db9106d3692db8ba158`）：
  基线 `data/reviews/task026_gpt_20261015_024732/source_hashes_after.json`（157436 项，实读 157438 项）；
  `changed = 3`，**恰为本卡三份修改文件**（`scripts/runtime_gate1.py`、
  `tests/test_runtime_gate1_registry.py`、`docs/RUNTIME_GATE1_REGISTRY_GUIDE.md`）；
  `out_of_scope_changed = 0`；`added = 74` 且 `allowed_added = 74`、`out_of_scope_added = 0`
  —— 新增项以**逐条确切路径**登记（`ALLOWED_ADDED_EXACT`，不再使用 `startswith` 目录前缀豁免；
  `ALLOWED_ADDED_PREFIXES` 为空集），条目覆盖本回执与四个本轮根下的每个实测新增文件；
  `missing = 0`、`read_errors = 0`；R5 越界 326 项逐项不变；`scope_compliant = true`。
- 旧 R5 越界 326 项逐项不变、不追认；旧 harness 不列恢复例外。
- **空目录范围**单独如实登记（文件哈希扫描不覆盖空目录）：
  `data/human_gate_decision_records/gate1/task026_run_01_scope`（TASK-026 由本执行端创建，保留不动）；
  本轮未新增任何空目录作为 scope，`task026r1_run_01_scope` 始终不存在（测试 3.5 断言）。

## 10. 待 GPT 裁决

1. 三 API 末端“以操作起始读数复确认”的范围是否满足原卡（含 readback/目录集合/failure/scope 状态）；
2. 恢复 schema 的封闭键/严格类型/派生关系清单与 I/O 错误映射口径；
3. scope 计划路径语义与逐级 reparse 检查；已知空目录的来源说明方式；
4. 真实半写与守卫安装方式、证据登记与失败支配入口的实现是否足够可复核。
