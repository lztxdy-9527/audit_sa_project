# TASK-028 执行回执：Gate1 批准后的标准化与 SQLite 装载接入

日期：2026-10-15。任务卡 `docs/tasks/TASK-028_DRAFT.md`（C 类：GPT 制定接线与边界，DSH 实施）。
本卡只完成计算阶段，停在 `RT_NORMALIZED`；不生成 Gate2 请求/决定，不做筛查/事实/初判/AI/终判。

## 1. 前提与起点核对（实读）

| 对象 | 起点（卡内） | 实读 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | `336cf30e…c79f` / 111301 | 一致（本卡唯一改动的既有文件） |
| TASK-027 当前测试 / 指南 | `66b82df9…c4d4` / `b6759e6f…e88b` | 一致（未改） |
| normalizer `scripts/normalize_demo_data.py` | `a2bae49e…2310` | 一致，入口 `normalize_workbook(workbook_path, quality_report)`，`TASK-004-normalized-1.1` |
| SQLite 核心 `scripts/store_demo_sqlite.py` | `1abfad89…a446` | 一致，入口 `load_normalized_to_sqlite(normalized, database_path)`，`TASK-005-sqlite-load-1.2`、`DEV_SQLITE_VERIFIED`、`SQLITE_TESTS_ROOT=data/sqlite_tests` |
| schema `sql/demo_schema.sql` | `7e0c6463…8205` | 一致 |
| ACCEPTED 前提 | `data/reviews/task027_r2_gpt_20261015_173156/review_result.json` + 同根 `source_hashes_after.json` | 存在、只读引用 |

## 2. 交付物

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（修改，实现版本 `TASK-028-runtime-gate1-1.0`） | 143031 | `067e24161d62fc2f3883d844e0dfe716e30f2fe7dcf2fd22fcfedb0ff69fc4e1` |
| `tests/test_runtime_approved_load.py`（新增） | 43922 | `0f9d44d93d9695fb652809502b996099bae8a6ca606ce3bd15657fa8fd39c05c` |
| `docs/RUNTIME_APPROVED_LOAD_GUIDE.md`（新增） | 8918 | `498cc568712d4ae6988e174dd960097091a911588e6ca7a3fa2a31956e4f6c1b` |
| `docs/EXEC_REPORT_028.md`（本回执） | 见交接消息 | 见交接消息（避免自指） |

未修改任何旧测试/指南/回执。

## 3. 实现（只改 `runtime_gate1.py`，只新增两个公开 API，无 CLI）

- `run_gate1_approved_load(batch_dir, runtime_dir, *, scope_dir, event_relative, database_path)`
- `inspect_gate1_approved_load(...)`
- 两者成功均恰六键：`stage_version`(`TASK-028-approved-load-1.0`)、`status`(`RT_NORMALIZED`)、
  `batch_id`、`run_binding_sha256`、`artifacts`、`boundaries`（封闭八键全严格 false）；旧五 API
  未改名/未改输出/未放宽前提。
- 前提：真实调用现有 `verify_gate1_effective_approval` 并要求 `effective is True`、`APPROVE`、
  `HUMAN_DECLARED`、`reasons == []`；不接受调用方 status/approved，不调用开发控制器伪造放行。
- 固定顺序：核验 →（前提/路径拒绝时不建目录）→ 独占建 `load_dir`（登记叶同级 `<name>.load`）与
  数据库叶 → 写读 `started.json`(八键) → 每次核心调用前复确认已消费字节未变 →
  `normalize_workbook` **一次** → 写读 `normalized.json` → `load_normalized_to_sqlite` **一次** →
  写读完整 `load_report` 并核对状态/冻结版本/`DEVELOPMENT_TEST_ONLY`/`next_step_allowed=false`/
  摘要/数据库实读字节/四表行数 → 复核 Gate1 与登记字节 → 写读 `artifacts.json`(十一键) →
  全部语义消费后末端有界复确认 → 返回六键。
- 失败仅在本次已建 `load_dir` 独占写六键 `failure.json`（`kind` 严格 `BLOCKED`/`ERROR`，
  保留核心原因与 cause 链），不重试覆盖、不清理、不声称回滚；未建目录时不新造目录。
- `inspect` 只读：先查有效 failure 再解析其余文件，按 kind 阻断；成功路径严格核对键集/类型/常量/
  路径/身份/摘要/来源关系、两完整核心结果与数据库实读，并真实核验当前 Gate1。

## 4. 六组最低验收（`data/runtime_approved_load_tests/task028_run_04`，42 项检查 0 失败）

| 组 | 实测 |
| --- | --- |
| 正常 APPROVE | 两核心各真实 1 次；`run` 返回 RT_NORMALIZED（六键、artifacts 11 键、八键 false）；`load_dir` 恰四文件、数据库叶恰 `runtime.sqlite3`；落盘 `load_report` 与核心完整返回 canonical 相等；输入前后指纹真实取得且未变；四表行数（2/1/3/3）与标准化 `records` 交叉核对；`inspect` 只读成功且 artifacts 与 run 完全一致 |
| HOLD / 缺错绑定 | HOLD（夹具 0002 SHA 核对）→ `run` Blocked 且**两核心增量 0、load_dir 与库叶未建**；错材料绑定保存即定位拒绝；无 Gate1 事件时 run 拒绝且两核心 0；BLOCKED+APPROVE 仍被既有规则拒绝 |
| 路径拒绝 | 既有（空）`load_dir`、既有数据库父叶、越界库路径三类定位拒绝、现场不变、不新建 `load_dir` |
| 两处 Error 映射 | 标准化后受控异常 → `Error`+六键 failure(kind=ERROR) 且 loader 未执行；数据库已发布后受控异常 → `Error` 且**已发布库保留**+failure；`inspect` 均按诊断拒绝 |
| 半写与晚变更 | `artifacts.json` 真实独占句柄半写 → 本次拒绝、坏字节与诊断保留；loader 返回后改数据库字节 → 本次拒绝、坏字节保留；`inspect` 只读拒绝 |
| 观察与计数 | 公开 API 计数单列（build 12/prepare 23/save 11/verify 9/run 10/inspect 5）；normalizer 与 loader 按**原函数 code 对象**分列（5/4）；Gate1 内部 P1/冻结 prepare/冻结 store 单列（19/44/10）；`inspect` 的 normalize/loader 计数 **0**；`subprocess_internal_counts=null`（本轮不启动子进程，接收产物只读复用） |

**收尾控制**（各自从未存在的新目录，源目录只读且 SHA 未变）：`none` → **0/PASS**；
`ledger-replaced`（磁盘台账改为 `[]`）→ **1/FAIL**（`ledger_mismatch`）；
`late-drift`（末次诊断写入后 checks 加 LF）→ **1/FAIL**（`drift:checks.json`）；
`candidate-return` → **1/FAIL**；`drop-call` → **1/FAIL**（`api_records_missing:call_050`）。
失败均由台账/字节/独立预期审核实际判定，非由 mutate 标志直接返回。

## 5. 真实执行 / 映射注入 / 只读复用 / 侦察 / 未执行

- **真实执行**：本卡生产代码真实调用 normalizer 5 次、SQLite loader 4 次（在各验收组与错误组中
  分别计数）；公开 API 共 50 次调用；冻结 P1 19 次、冻结 prepare 44 次、冻结 store.save 10 次
  （由 Gate1 核验与保存路径真实触发）。
- **映射注入（受控，明确标注为宿主注入）**：标准化后异常 1 次、数据库发布后异常 1 次、
  `artifacts.json` 真实独占句柄半写 1 次、loader 返回后数据库字节变更 1 次；
  另有 R1/R2 既有的 Gate1 侧注入（不属于本卡核心）。均保留现场未清理。
- **只读复用**：本轮**新接收 0 次**，批次接收产物只读复用
  `data/batches/task027r1_run_04/{batch_normal,batch_blocked}`；人类字段仅取原登记
  0001/0002 原文，测试标签在证据外层。
- **侦察调用（如实登记，不计入交付证据）**：开发期曾真实调用 `normalize_workbook` 一次以取得其
  返回形状（只读，未写任何文件），以及在 `task028_dev_01..05` 五次开发冒烟中真实调用两核心
  （其中 dev_01–04 为逐次修缺陷的失败现场，含 `failure.json`，**保留未清理**；dev_05 成功）。
- **未执行（null + 原因）**：未重新接收批次（卡允许只读复用）；未重跑 TASK-027 全套或冻结核心
  历史大组（卡明确不要求）；未建立符号链接/junction 探针（普通路径验证已覆盖，链接类反例如实
  `not_executed`）；未调用标准化/SQLite 以外的下游（Gate2、筛查、事实、初判、AI、终判、宿主
  0001—0008 修改、0009 生成均未触及）。

## 6. 开发性现场与命名（如实登记，保留不删除）

`data/runtime/task028_dev_01..05`、`data/sqlite_tests/task028_dev_01..05`、
记录根 `data/human_gate_decision_records/gate1/task028_dev_0*_scope`（开发冒烟现场，含失败诊断）；
`data/runtime_approved_load_tests/task028_run_01..04` 与 `task028_ctrl*_*`（测试入口各次运行与
控制副本，其中 `task028_ctrl_*` 为早期同名控制目录、`task028_ctrl2_*` 为最终控制副本）。
另有一次只读侦察未写盘（见 §5）。全部将在最终扫描中按**确切路径**逐条登记。

## 7. 保护与收尾

一次最终全树扫描（见交接消息中的身份）：当前基线内新增 missing / 范围外变化 / 范围外新增 /
读取错误均为 0；139 项历史损失**单列**；27 项恢复、旧 R5 越界 326 项与 R1 偏差 19 文件逐项不变；
新增按本卡明示根展开为确切路径，无目录前缀兜底。全程未对任何探针目标做递归删除、移动或清理
（唯一删除动作为实现内经过身份与内容核对的本次自建技术锁正常释放）。

## 8. 边界

真实批准 `null`；宿主开发态 `0008`；`next_step_allowed=false`、`ai_enabled=false`；
正式契约 V1 与 D1/D2/D3 既有授权未变（不代表批准任何批次）；`RT_NORMALIZED` 只表示当前合成
计算已由具体 Gate1 前提约束，**不构成执行许可、不是审计结论、不是 Gate2 批准**。
本轮测试夹具不构成任何批次真实批准。不实施 TASK-028 之后的任务。
