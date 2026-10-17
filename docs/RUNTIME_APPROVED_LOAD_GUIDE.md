# Gate1 批准后的标准化与 SQLite 装载接入指南（TASK-028）

本指南描述 `scripts/runtime_gate1.py` 在 TASK-028 后新增的两个公开 API。范围**止于计算阶段**：
`status = RT_NORMALIZED`。不生成 Gate2 材料请求或决定，不做筛查/事实/初判/AI/终判，
不接 LLM/网络/UI/ERP，不修改开发宿主 0001—0008，不新增 0009。**本层不授予任何批次批准。**

## 1. 公开 API（本脚本共七个，仍无 CLI）

```text
build_runtime_registry / read_runtime_registry / prepare_runtime_gate1_request   # TASK-026
save_runtime_gate1_decision / verify_gate1_effective_approval                    # TASK-027
run_gate1_approved_load(batch_dir, runtime_dir, *,
                        scope_dir, event_relative, database_path)                # TASK-028
inspect_gate1_approved_load(batch_dir, runtime_dir, *,
                            scope_dir, event_relative, database_path)            # TASK-028
```

旧五 API 语义未变。两个新 API 成功均返回**恰六键**：
`stage_version`（`TASK-028-approved-load-1.0`）、`status`（`RT_NORMALIZED`）、`batch_id`、
`run_binding_sha256`、`artifacts`、`boundaries`。`boundaries` 封闭八键且全部严格 `false`：
`gate2_approved`、`screening_allowed`、`ai_enabled`、`initial_judgment_recorded`、
`audit_conclusion_formed`、`identity_authenticated`、`source_authenticity_proven`、
`next_step_allowed`。

## 2. 前提：当前 Gate1 必须真实有效

两者都真实调用现有 `verify_gate1_effective_approval`，并要求
`effective is True`、`decision == "APPROVE"`、`actor_kind == "HUMAN_DECLARED"`、`reasons == []`。
**不接受**调用方传入的 status/approved，不调用开发控制器伪造放行。合法 `HOLD`/`REJECT`、
缺失记录、错绑定、失败现场、技术锁或材料变化时：**两计算核心增量 0，且不创建 load_dir 与数据库叶**。
`BLOCKED` 批次 + `APPROVE` 仍由既有 Gate1 规则拒绝。

## 3. 目录与路径

- 计算输出目录 `load_dir`：`runtime_dir` **同级**固定名 `<runtime 登记叶名>.load`，技术名来自已核验
  的显式 runtime 路径，不由业务 ID 拼路径；登记叶仍是**不可扩充的二文件**，因此计算产物不会使
  既有 Gate1 核验因未知项失效。
- `load_dir` 必须**从未存在**（既有空目录也拒绝），由本层独占 `mkdir` 作为该次计算的唯一写入点；
  同一登记不能换输出目录重复计算。
- `database_path` 显式提供，只允许 `data/sqlite_tests` 的**严格后代**且固定文件名
  `runtime.sqlite3`，所在叶目录必须从未存在并由本层独占创建（上级本轮根可预建）。
- 拒绝与来源、登记、事件、`load_dir` 相等或互为祖先的路径；逐级 reparse 检查后再核对解析路径；
  已存在的库、staging、未知项一律拒绝；不扩大冻结 SQLite 核心的允许根。

## 4. 固定执行顺序（run）

1. 实读核验参数/登记/当前来源/Gate1 事件，保存**同缓冲字节与对象读数**；真实 Gate1 核验通过后
   才准备计算输出（前提或路径拒绝时**不建** `load_dir` 与数据库目录）。
2. 独占建 `load_dir` 与数据库叶，写 `started.json` 并精确读回。不生成新的 actor、人类时间、
   原因、决定或 `event_id`。
3. 每次调用计算核心之前复确认已消费的来源/Gate1/登记字节仍等于起始读数，再真实调用
   `normalize_workbook(batch_dir / "source/input.xlsx", quality_report)` **一次**；`quality_report`
   来自本次同缓冲读取且与 Gate1 材料绑定一致；完整返回保持不改，调用前后验证其消费输入未变。
4. 按规范 `canonical UTF-8 + 单 LF` 独占写 `normalized.json` 并读回；真实调用
   `load_normalized_to_sqlite(normalized, database_path)` **一次**。只传本次真实标准化对象与显式新路径，
   不传答案册/规则筛查/开发批准。
5. 保存并读回该次完整 `load_report`：要求 `DEV_SQLITE_VERIFIED`、冻结 `store_version`/
   `schema_version`/`normalization_version`、`mode = DEVELOPMENT_TEST_ONLY`、
   `next_step_allowed` 严格 `false`、`normalized_payload_sha256` 与本次对象闭合；实读数据库字节与
   报告 `database_sha256` 相等；四表行数与标准化 `records` 交叉核对（不复制核心整套勾稽算法）。
6. 复核当前 Gate1 仍有效、共享运行绑定未变；最后独占写 `artifacts.json` 并读回。全部必要语义消费
   结束后，按起始读数/本次 writer 缓冲/核心返回绑定复确认来源、登记、事件、静态代码与本阶段文件、
   数据库字节与固定集合；通过才返回 `RT_NORMALIZED`。末次确认后不再读取候选构造成功输出。

冻结核心保留其自身标记：`NORMALIZATION_VERSION = TASK-004-normalized-1.1`、
`STORE_VERSION = TASK-005-sqlite-load-1.2`、`mode = DEVELOPMENT_TEST_ONLY`、`next_step_allowed = false`。
本层只声明“当前合成计算已由具体 Gate1 前提约束”。

## 5. 固定产物与失败语义

成功时 `load_dir` **恰四文件**：`started.json`、`normalized.json`、`load_report.json`、
`artifacts.json`，无 `failure.json`、无未知项；数据库叶只含 `runtime.sqlite3`。

- `started.json` 封闭八键：`started_version`（`TASK-028-approved-load-start-1.0`）、`batch_id`、
  `source_batch_relative`、`runtime_relative`、`scope_relative`、`event_relative`、
  `database_relative`、`bindings`；`bindings` 封闭四键
  `registry_file_sha256` / `gate1_record_file_sha256` / `gate1_record_fingerprint` /
  `run_binding`（完整六项对象），全部来自本次实读，不采信调用方摘要。
- `artifacts.json` 封闭十一键：`artifacts_version`（`TASK-028-approved-load-artifacts-1.0`）、
  `batch_id`、`run_binding_sha256`、`started_file_sha256`、`registry_file_sha256`、
  `gate1_record_file_sha256`、`gate1_record_fingerprint`、`normalized_file_sha256`、
  `normalized_payload_sha256`、`load_report_file_sha256`、`database`（恰
  `relative`/`file_sha256`/`byte_size`，路径与显式参数一致）。规范对象指纹与文件字节 SHA **分列**，
  不内嵌 `artifacts` 自身 SHA。
- 失败时仅在本次已建 `load_dir` 独占写 `failure.json`，六键
  `failure_version`（`TASK-028-approved-load-failure-1.0`）、`kind`（严格 `BLOCKED` 或 `ERROR`）、
  `stage`、`field`、`reason`、`cause_chain`；保留核心异常原因与 cause/context；诊断自身再失败保留
  主次原因。不声称数据库错误已回滚，不删除半写/旧文件/失败事实，不重试覆盖。尚未建目录时正常
  传播错误，不为诊断新造目录。

## 6. 只读恢复（inspect）

`inspect_gate1_approved_load` 只读：**先检查有效 `failure.json`** 并按 `kind` 如实阻断
（`BLOCKED` → `Blocked`、`ERROR` → `Error`），再解析其余文件（半写 `artifacts.json` 不得遮蔽诊断）。
成功路径严格核对键集/类型/常量、相对路径/身份/摘要/来源关系、两个完整核心结果与数据库实读，
并真实核验当前 Gate1；已知产物存在**不能**放宽登记叶或 scope 模型。只读路径在全部语义消费之后
做一次有界字节/集合/路径确认；不调用 normalizer/loader，不写 failure，不修复现场。

## 7. 测试入口

```text
# 正常观察并定稿（out-dir 必须从未存在；只读复用已核验小样，本轮新接收 0 次）
.venv\Scripts\python.exe -B tests\test_runtime_approved_load.py \
    --out-dir data\runtime_approved_load_tests\task028_run_01

# 收尾控制（源目录只读；必须另给从未存在的新 out-dir）
... --out-dir <新目录> --replay <既有观察目录> \
    --mutate none|ledger-replaced|late-drift|candidate-return|drop-call
```

- 六组最低验收：正常 APPROVE（两核心各 1 次→四文件+数据库+只读 inspect）、HOLD 与缺/错 Gate1
  绑定对照、路径拒绝三类、两处 Error 映射、`artifacts` 真实半写与数据库晚变更、观察与计数分列。
- 收尾：定稿内存观察为独立预期（审核期间不刷新）；磁盘台账实读回核（与本次待写缓冲比较）；
  末次确认后才决定成功；失败或漂移支配顶层 1／磁盘 FAIL／非空 failures，坏目标保留。
- 控制实测：`none` → 0/PASS；`ledger-replaced`（磁盘台账改 `[]`）→ 1/FAIL（`ledger_mismatch`）；
  `late-drift`（末次诊断写入后 checks 加 LF）→ 1/FAIL（`drift:checks.json`）；
  `candidate-return`/`drop-call` closure-only → 1/FAIL。
- 计数口径：公开 API 计数只取 `public_api_calls_by_name_profile`；normalizer 与 SQLite loader 按
  **原函数 code 对象**分列；Gate1 内部 P1/store/冻结 prepare 计数单列，不并入公开 API；
  `inspect` 的 normalize/loader 计数必须为 0。

## 10. TASK-028-R1 修正要点（补丁版本 `TASK-028-runtime-gate1-1.1`）

两 API、六键成功外层、四件计算产物、六键 `failure.json`、八键 false 边界均未改名、未新增字段，
单次计算模型不变；以下为定点修正后的确定语义。

### 10.1 起始预期与末端确认（B1）

- `run` 与 `inspect` 都在操作**开始**固定已消费来源/登记/静态代码与 Gate1 **八文件**
  （`context.json`、`receipt.json`、六份快照）的同缓冲读数；每次计算核心调用前复确认这些读数未变。
- 末端确认**只使用起始读数与本次已绑定 capture**：禁止 `_recheck_capture(_capture_file(...))`
  式自比，禁止用较晚重新采集的值覆盖初始预期。
- 数据库预期只能来自本次真实 `load_report` 绑定并已核验的 capture，并保留至终端；
  `load_report.json` 写后读回必须与本次 `report_buffer` 精确相等。
- 末端只做有界原始字节/集合/路径确认：批次顶层与四子目录、登记叶恰二文件且无 failure、
  scope 恰单事件、事件恰 `context/receipt/snapshots`、六快照无未知项、锁不存在、`load_dir` 恰四文件
  且无 failure、数据库叶恰一文件、逐级 reparse。之后不再读取候选或复算业务来决定成功。

### 10.2 完整字段闭合、严格类型与只读行数（B2）

- `started.json` / `artifacts.json` / `failure.json` 每一字段都校验或与本次独立预期精确比较：
  `started.batch_id` 与当前 Gate1 批次一致、全部相对路径与显式参数一致、`bindings` 四键与本次实读一致；
  `artifacts` 的登记/Gate1 两摘要、共享运行绑定、各文件 SHA、规范对象 SHA、`database` 三键三方闭合。
- 所有 SHA 必须是 64 位小写十六进制；`byte_size`、行数等必须是严格非负 `int`（`bool`/`float` 不得冒充）。
- `normalized` 的冻结版本、`DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false`、
  `source.{input,checker,spec}_sha256` 与本次已绑定工作簿/静态文件闭合；`load_report.source` 与
  `normalized.source` 规范相等、`run_metadata` 中 input/标准化指纹闭合、
  `round_trip_exact`/`event_allocation_balanced` 严格 `true`。
- 用**只读** SQLite 连接实际查询四业务表 `COUNT(*)`，与 `normalized.tables[*].records` 长度及
  报告计数三方一致；查询结束关闭连接，再以已绑定库字节做终端确认。不复制核心全量勾稽算法。

### 10.3 新层 I/O 与真实异常类型（B3）

- `load_dir.mkdir()`、数据库叶 `mkdir`、`failure.json` 读取等新层 I/O 都有明确阶段的错误边界：
  `OSError` → `RuntimeGate1Error(stage)` 并保留 cause；能否独占写诊断按**实际目录事实**判断，
  不删除失败目录/库，不为诊断新造目录。
- 核心异常按**实际加载模块上的真实类名**映射：`NormalizationBlocked`/`SqliteLoadBlocked`
  → 本层 `Blocked`（`kind=BLOCKED`）；`NormalizationError`/`SqliteLoadError`/`OSError`
  → `Error`（`kind=ERROR`）；其余如实 `Error`。两个计算核心都经由同一映射通道调用。
- 原始 reasons 以「类名: reason」完整保存在既有 `reason`/`cause_chain` 中（不新增 failure 字段）。
- `inspect` 先读取并核验 `failure.json` 的对象/封闭键/`kind` 严格取值，再按有效诊断拒绝；
  非法 `kind` 或非对象诊断本身定位 `Blocked`，读取 I/O 映射 `Error`。
- 核心调用前后比较 `quality_report`/`normalized` 的规范指纹：内存输入被核心改写即 `Blocked`。

### 10.4 测试入口（`--only r1`）

```text
.venv\Scripts\python.exe -B tests\test_runtime_approved_load.py \
    --out-dir data\runtime_approved_load_tests\task028r1_run_04 --only r1
... --out-dir <新目录> --replay <观察目录> --mutate none|ledger-lf|late-drift|candidate-return
```

- `--only r1` 只跑本轮正向/反例与收尾：B1 三处末端 LF 隔离反例 + 保存端 writer 返回后 DB LF +
  未知项集合覆盖；B2 八项字段反例与规范等值对照；B3 真实两 Blocked 类注入、`mkdir` 接缝 OSError、
  非法/非对象 failure；E1 真实同引用改写内存输入与四控制。
- 收尾：独立内存观察在候选读取前冻结；台账预期来自本次待写缓冲，**台账自身字节也实读核对**并纳入
  末次确认；末次确认后不再读候选 `failures`/`summary` 生成成功输出；任一失败支配真实 CLI 1 /
  磁盘 FAIL / 非空 failures，坏候选保留。
- 控制实测：`none` → 0/PASS；`ledger-lf` → 1/FAIL（`ledger_bytes_mismatch`）；
  `late-drift`（末次必要消费后 checks 加 LF）→ 1/FAIL（`drift:checks.json`）；`candidate-return` → 1/FAIL。
  失败均由审核实际判定，**不按 mutate 标志直接判失败**。

## 11. TASK-028-R2：当前实现与 R1 声明更正

当前补丁为 `TASK-028-runtime-gate1-1.2`，公开协议和目录模型不变。§10 描述过 R1 的目标与交付声明，
其中部分未在 R1 实际实现或测到；以 `REVIEW_TASK_028_R1.md` 和本节为准。旧回执/现场不改写，
`--only r1` 保留为历史入口，不作为本次验收证据。

- 两个计算入口紧前复用起始来源/登记/事件八文件的 capture，并确认固定集合与无技术锁；
  `load_report` 写后必须与本次 writer 的确切缓冲一致，不能绑定被改写后的读回哈希。
- `artifacts.database.byte_size` 严格非负整数。恢复端始终传入已绑定的工作簿 capture；
  normalized.source 使用冻结七键、非空字符串/完整哈希类型及确切 input/checker/spec 路径和 SHA；
  `net_checks` 使用冻结六键且每项严格 true。SQLite 四表只读实查沿用，不重做金额算法。
- 异常按实际模块类对象 `isinstance` 分类，原始 `.reasons` 完整写入既有 reason，cause 保留原异常。
  failure 的版本、kind、stage、field、reason、字符串列表 cause_chain 在消费前逐项检查。
- 核心观察保存同一内存引用的 before/after/API-end 三时点及完整快照；工作簿字节前后另列。
  隔离的观察器负向控制单独存于 summary.results，其完整核心记录与真实 profile 总数一起闭合；
  正式 audit 本身拒绝该控制记录，不通过标签放宽普通变化的规则。
- finish 解析/内容审核后，末次实读七载荷和台账共八文件，与本次 writer 缓冲精确比较；之后不再读取
  候选生成输出。`audit_failure.json` 仅登记写前预期，不宣称最终通过；最终判定见实际返回码、
  summary/failures。失败现场不重建台账、不回填坏候选。

本轮入口（必须使用新目录）：

```text
.venv\Scripts\python.exe -B tests\test_runtime_approved_load.py --only r2 --out-dir data\runtime_approved_load_tests\task028r2_<新轮次>
```

实际最终容器 `task028r2_gpt_run_02`：41 项/0 失败，直接登记 API 47 条；真实 normalizer 5、loader 2，
正向核心记录6与隔离负向控制1分列。新进程收尾重放只复用这次观察，计算核心新增调用0；
normal、真实审核后台账 LF、审核后 checks LF、返回值替换分别为0/PASS、1/FAIL、1/FAIL、1/FAIL。
这只是执行端实测，独立验收与批次批准仍由架构端/人类分别处理。
