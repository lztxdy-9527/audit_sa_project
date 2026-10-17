# TASK-028-R1 执行回执：批准装载的绑定、恢复与测试收尾定点修正

日期：2026-10-15。任务卡 `docs/tasks/TASK-028-R1_DRAFT.md`（B 类：DSH 执行、GPT 验收）。
依据 `docs/reviews/REVIEW_TASK_028.md`。当前 TASK-028 为 **NOT_ACCEPTED**，本回执不主张原卡通过。

## 1. 起点核对（实读）

| 对象 | 起点 | 实读 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | 143031 / `067e2416…4e1` | 一致（本卡唯一改动的既有生产文件） |
| `tests/test_runtime_approved_load.py` | 43922 / `0f9d44d9…05c` | 一致 |
| `docs/RUNTIME_APPROVED_LOAD_GUIDE.md` | 8918 / `498cc568…c1b` | 一致（本卡必要同步） |
| 评审基线 | `data/reviews/task028_gpt_20261015_182926/`（`review_result.json` + `source_hashes_after.json`） | 存在、只读引用 |

## 2. 交付物

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（补丁版本 `TASK-028-runtime-gate1-1.1`） | 151837 | `d6c8b3a04003e527662b9dddf7ac9500331245e9fb84373b87a1804e791a4020` |
| `tests/test_runtime_approved_load.py`（新增 `--only r1`） | 57220 | `fe33806303a5092b5b0bc69c1e4860b41ce152145f2a6b269c2e3cea1f729c06` |
| `docs/RUNTIME_APPROVED_LOAD_GUIDE.md`（追加 §10） | 见交接消息 | 见交接消息 |
| `docs/EXEC_REPORT_028_R1.md`（本回执） | 见交接消息 | 见交接消息（避免自指） |

两 API、六键成功外层、四件计算产物、六键 `failure.json`、八键 false 边界未改名、未新增字段、
单次计算模型未变；原五 API 前提未放宽。

## 3. 四组阻断的修正与实测

### B1 起始预期与最终字节/集合确认

实现：新增 `_capture_event_028` 在操作开始固定 Gate1 八文件同缓冲读数；末端确认重写为只用起始读数与
本次已绑定 capture（删除全部自比式 `_recheck_capture(_capture_file(...))`）；数据库末端核对改用第 5 步
由真实 `load_report` 绑定并已核验的 capture；同时复核批次顶层+四子目录、登记叶恰二文件无 failure、
scope 恰单事件、事件与快照固定集合、`load_dir` 恰四文件无 failure、数据库叶恰一文件、锁不存在。

实测（`task028r1_run_04`）：末端 DB LF / context LF / decision_result LF 三个隔离反例各自
`inspect` 定位拒绝；保存端真实 `_write_exclusive` 返回后写 DB LF → 本次拒绝 + 本层六键 failure +
坏库保留；`load_dir` 未知项 → `Blocked: load_dir`。

### B2 完整字段闭合、严格类型与只读 SQL

实现：新增 `_require_nonneg_int`（bool/float 不得冒充）与 `_read_only_row_counts`（只读连接实查四表
count 后关闭）；`started.batch_id`、`artifacts` 的登记/Gate1 两摘要与 started 绑定三方闭合；
`normalized` 版本/mode/next/source 三摘要与已绑定工作簿闭合；`load_report.source` 与标准化 source
规范相等、`run_metadata` 指纹闭合、`round_trip_exact`/`event_allocation_balanced` 严格 true；
四表报告计数与**库内实际**行数一致。

实测：错 `started.batch_id`（同步文件 SHA）、错 `artifacts.registry_file_sha256`、错 Gate1 指纹、
缺键集、`round_trip_exact=false`（同步文件 SHA）、删一条 `allocations`（仅同步外层 SHA）、
`normalized.source` 错输入 SHA、`normalized` 未知嵌套键 → 均定位拒绝；
**规范等值（键序不同）重写后 `inspect` 仍成功**对照通过。

### B3 新层 I/O 与真实异常类型

实现：`load_dir.mkdir()` 与数据库叶 `mkdir` 纳入阶段错误边界（`OSError` → `RuntimeGate1Error(stage)`
+ cause；库叶失败时按实际事实写六键诊断）；核心异常改为按**真实类名**映射，且
**`normalize_workbook` 改为与 loader 同一 `_call_frozen_entry` 通道**——这是本轮修掉的一个真实缺陷：
此前它绕过映射，`NormalizationBlocked` 会被误判为 `Error/ERROR`；`failure.json` 先验对象与
`kind ∈ {BLOCKED, ERROR}`；核心调用前后比较 `quality_report`/`normalized` 规范指纹。

实测：真实 `NormalizationBlocked` / `SqliteLoadBlocked` 各注入一次 → 本层 **Blocked + kind=BLOCKED**
且 reason 含类名；数据库叶 `mkdir` 接缝 OSError → `Error` + 六键 failure + 库叶未建 + 坏目录保留；
非法 `kind` 与非对象 `failure` → 恢复定位拒绝。

### E1 测试收尾与真实输入观察

实现：`finish` 增加台账**自身字节**实读核对（`ledger_bytes_mismatch`）并纳入末次确认；
独立内存观察在候选读取前冻结；失败诊断先定稿；末次确认后不再读候选生成成功输出。

实测四控制（各自从未存在的新目录，源只读且 SHA 未变）：`none` → **0/PASS**；
`ledger-lf` → **1/FAIL**（`ledger_bytes_mismatch`）；`late-drift`（末次必要消费后 checks 加 LF）
→ **1/FAIL**（`drift:checks.json`）；`candidate-return` → **1/FAIL**。
另有一项**真实同引用改写**控制：核心返回后改写本次 `quality_report` 内存对象 → 本次拒绝
（不使用手填标志当证明）。

## 4. 真实核心执行 / 受控映射 / 旧证据读取 / 未执行

- **真实核心执行**：`--only r1` 正常与各反例场景共真实调用 `normalize_workbook` 与
  `load_normalized_to_sqlite`（`task028r1_run_04` 完整记录 20 条嵌套核心记录，两核心各自计数闭合）；
  `inspect` 的 normalize/loader 增量 0。
- **受控映射（明确标注宿主注入）**：真实 `NormalizationBlocked`/`SqliteLoadBlocked` 各 1 次、
  数据库叶 `mkdir` OSError 1 次、核心返回后同引用改写内存输入 1 次、末端 DB/context/decision_result
  晚变更各 1 次、保存端 writer 返回后 DB LF 1 次、`load_dir` 未知项 1 次、B2 八项字段篡改各 1 次、
  非法/非对象 failure 各 1 次。全部保留坏现场，未清理。
- **旧证据读取（未重跑）**：TASK-028 评审与基线、TASK-027/026 已验收测试与指南、冻结核心与 schema、
  R1 之前开发性现场；仅只读引用，未重跑原 42 项或历史整套。
- **未执行（null + 原因）**：未新增接收批次根（卡不授权，只读复用已核验小样，本轮新接收 **0** 次）；
  未重跑 TASK-026/027 全套与冻结核心历史大组（卡明确不要求）；未建立符号链接/junction 探针
  （`not_executed`）；未触及 Gate2/筛查/事实/初判/AI/终判/宿主 0001—0008 修改/0009。

## 5. 开发性现场（保留不删除，扫描按确切路径登记）

`data/runtime/task028r1_dev_01..02`、`data/sqlite_tests/task028r1_dev_01..02`、
记录根 `.../gate1/task028r1_dev_0*_scope`（开发冒烟，含失败诊断）；
`data/runtime_approved_load_tests/task028r1_run_01..04` 与 `task028r1_ctrl_*`/`task028r1_ctrl2_*`。
全程未对任何探针目标做递归删除、移动或清理（唯一删除为经身份与内容核对的本次自建技术锁正常释放）。

## 6. 保护与收尾

一次最终全树扫描（身份见交接消息）：changed 仅允许的三份文件（指南按必要同步）；
未知新增 / 新 missing / 读取错误 / 范围外变化均为 0；139 项历史损失**单列**；27 项恢复、
旧 R5 越界 326 项、R1 偏差 19 文件逐项不变；新增按卡明示根展开为确切路径，无前缀兜底。

## 7. 边界

真实批准 `null`；宿主开发态 `0008`；`next_step_allowed=false`、`ai_enabled=false`；
`RT_NORMALIZED` 不构成执行许可、不是审计结论、不是 Gate2 批准；本轮测试夹具不构成任何批次真实批准。
完成本卡即停止实施，不推进 TASK-029/Gate2/筛查/初判/AI/终判/0009。
