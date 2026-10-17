# TASK-011 执行回执（实际标准化、SQLite 装载，停在 Gate2 待确认）

任务：在新宿主版本上增加唯一新动作 `start → Gate1 pending → 显式模拟 APPROVE → prepare-gate2（真实标准化 + 真实装载 + 保存材料）→ DEV_GATE2_PENDING → 停住`。
日期：2026-10-11。执行端：DeepSeek。依据：`docs/tasks/TASK-011_DRAFT.md`、`docs/reviews/REVIEW_TASK_010_R4.md`、`docs/WORKFLOW_CONTROL_GUIDE.md`、`docs/NORMALIZATION_GUIDE.md`、`docs/SQLITE_LOAD_GUIDE.md`、`docs/WORKFLOW_HOST_GUIDE.md`。
状态：完成并自检通过，**停在 `DEV_GATE2_PENDING`**；未实现或提交任何 Gate2 决定，未推进 TASK-012。

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 新增动作 | `prepare_dev_gate2(batch_dir)` + CLI `prepare-gate2 --batch-dir <批次>`；`start`／`status`／`record-simulated-decision` 的签名与语义保留 |
| 真实上游调用 | 通过**子进程之外的直接函数调用**实际运行冻结 `normalize_demo_data.py`（`normalize_workbook`）与 `store_demo_sqlite.py`（`load_normalized_to_sqlite`），不复制其逻辑、不放宽装载路径、不加生产测试开关 |
| 固定数据库路径 | 由宿主按批次推导：`data/sqlite_tests/workflow_gate2/<批次相对 data/batches 的完整路径>/audit.sqlite3`；调用者不能指定；目标库／`.staging`／本次输出目录已存在时，在调用上游**之前**拒绝 |
| 落盘协议 | `workflow/gate2/{normalized.json, load_report.json, artifacts.json}`（失败再加 `failure.json`）+ `checkpoints/0003.json`（仅 `PREPARE_GATE2`／Gate2 pending）；`0001`／`0002` 字节不变 |
| 恢复核验 | `status` 支持 `0001`、`0001+0002`、`0001+0002+0003`；`0003` 必须由 `0002`（合法 Gate1 APPROVE）与**本次实际材料**经冻结 `prepare_dev_gate` 复算完整预期返回后逐项一致；仅核外层哈希不会通过 |
| 未完成／失败 | `workflow/gate2/` 已开始而无完整有效 `0003` → `status` 说明准备未完成／失败并拒绝；重复 `prepare` 始终拒绝；不重试、不复用、不自动删除 |
| 版本 | 宿主 `TASK-011-workflow-host-1.0`；清单 `TASK-011-host-manifest-1.0`；checkpoint `TASK-011-checkpoint-1.0`；旧版本明确拒绝（不迁移旧批次） |
| 开发态边界 | `mode=DEVELOPMENT_TEST_ONLY`、`contract_status=DRAFT_NOT_IN_FORCE`、`next_step_allowed=false`、真实 `gate1_approval`／`gate2_approval` 恒为 `null`、模拟决定固定 `SIMULATED_HUMAN` + `SIMULATED_TEST_ONLY` |
| 开发验证 | 全新容器真实回归**退出 0、failures=[]**，9 组检查全部 PASS；**Gate2 只是待确认，不是已放行** |

## 2. 文件与产物

| 文件 | SHA-256 |
| --- | --- |
| `scripts\run_demo_workflow.py`（修改，v1.3 → v1.0/TASK-011） | `2c94507a15b922f9f7e8fb83f6ae8fec8f56550552ce325e4f3d19569b39a03a` |
| `docs\WORKFLOW_HOST_GUIDE.md`（修改） | `20180d9cfdb51fa38f2121e42514b1e41b94a1798acb01e2c4a8b68669362dc6` |
| `tests\test_prepare_demo_gate2.py`（新增验证入口） | `8fdca2b44994bea1410368b536d67268fe972f46e415cd640014cf362029e730` |
| `docs\EXEC_REPORT_011.md` | 本文件（新增） |

- 最终测试容器：`data\workflow_host_tests\task011_final_01`（123 个文件；`summary.json`／`checks.json`／`cli_logs.json`／`cli_logs/`／`count` 相关证据／`writer_evidence.json`／`writer_full_expected_0003.json`／`self_tests.json`／`final_readback.json`／`stdout.txt`／`stderr.txt`）。
- 最终批次父目录：`data\batches\task011_final_01`（23 个叶子目录 / 371 个文件）。
- 最终外置开发数据库目录：`data\sqlite_tests\workflow_gate2\task011_final_01`（17 个子目录 / 16 个文件，含各批次 `audit.sqlite3`）。
- 过程现场：`data\workflow_host_tests\task011_01`、`data\batches\task011_01`、`data\sqlite_tests\workflow_gate2\task011_01`（保留，不回写）。

## 3. 真实命令与退出码

```powershell
& $py -B -c "compile(open(r'...\scripts\run_demo_workflow.py', encoding='utf-8').read(), 'x', 'exec'); print('compile OK')"          # 0
& $py -B -c "compile(open(r'...\tests\test_prepare_demo_gate2.py', encoding='utf-8').read(), 'y', 'exec'); print('compile OK')"    # 0
& $py -B '...\tests\test_prepare_demo_gate2.py' --out-dir '...\data\workflow_host_tests\task011_final_01'                          # 0
```

逐步独立进程（恢复路径即真实重启路径，摘自主样本 MAIN）：

```text
start                      exit 0   phase DEV_GATE1_PENDING
status                     exit 0   phase DEV_GATE1_PENDING，simulated_action_allowed=false
record-simulated-decision  exit 0   phase DEV_GATE1_APPROVED（显式模拟 APPROVE；下游调用 0）
prepare-gate2              exit 0   phase DEV_GATE2_PENDING（真实标准化 + 真实装载 + 保存材料）
status                     exit 0   phase DEV_GATE2_PENDING，action_checked=SCREEN_AND_BUILD_FACTS，allowed=false
prepare-gate2（重复）       exit 1   “workflow/gate2/ 已开始存在：不重试、不复用、不自动删除”
record-simulated-decision  exit 1   “已进入 Gate2 准备并停在 DEV_GATE2_PENDING：Gate1 决定不可重复提交，Gate2 决定不在本卡范围”
```

最终容器汇总输出：

```text
CLI 调用：start 14、status 18、record 12、prepare-gate2 7；宿主 API 10；控制器调用 8
真实接收 14、checker 13、标准化 3、装载 2、副本 8、故障注入 11、真实批准 0
测试失败 0；受保护文件前后哈希一致: True（13 个）
```

**计数口径**：CLI 与宿主 API 分列（CLI 侧的真实标准化／装载发生在子进程内，本入口无法观测，故单独列“进程内观测调用”3／2，不用它冒充 CLI 侧次数）；`receiver_starts` 由独立 `receive_invocation.json` 记录去重统计；副本 8 份统一登记来源且不计新接收；被拒绝的探针不计上游调用；故障注入 11 次；模拟决定 3 条、**真实批准 0**。

## 4. 独立金额与数据库字节核验（MAIN，开发测试固定值）

| 项目 | 实测 | 期望 |
| --- | --- | --- |
| 四表行数（suppliers／payables／payments／allocations） | `20 / 993 / 1000 / 1005` | 同左 |
| 已结算付款主表／分摊 | `267949329` / `267949329` | 相等 |
| 已结算退款主表／分摊 | `700000` / `700000` | 相等 |
| 资金净额 | `267249329` | = 已知 `266249329` + 缺失 `1000000` |
| `net_checks` 六项 | 全部严格 `true` | 同左 |
| `round_trip_exact` / `foreign_key_check` / `integrity_check` | `true` / `clean` / `ok` | 同左 |
| 数据库字节哈希 | `load_report.database_sha256` = 实读文件字节哈希；`artifacts.database_sha256` 相同 | 一致 |
| 对象指纹 | `load_report.normalized_payload_sha256` = `artifacts.normalized_payload_sha256` = 实读 `normalized.json` 的对象规范指纹 | 一致 |
| 来源绑定 | `normalized.source.input_sha256` = `load_report.source.input_sha256` = 批次 `run_bindings.input_sha256` | 一致 |
| Gate1 前序 | `0003.operation.gate1_decision_sha256` = `0002` 内模拟 APPROVE 正文规范指纹 | 一致 |

小样 C02 与 C07b 各自走完整真实流程到 Gate2，按自身记录数与金额核对（**不**用 MAIN 金额当通过条件）；C07b 的缺失应付关联净额非零且仍正常形成 Gate2 请求（`master_net = known + missing`），保留为业务事实。

## 5. 重启恢复与负向目标原因

- 恢复：新进程 `status` 在 `DEV_GATE1_PENDING`、`DEV_GATE1_APPROVED`、`DEV_GATE2_PENDING` 三种状态均复现；Gate2 pending 时 `action_checked=SCREEN_AND_BUILD_FACTS`、`simulated_action_allowed=false`、`actions_simulated_allowed.NORMALIZE_AND_LOAD=false`、`next_step_allowed=false`；`0003` 的完整 workflow 由 `0002` + 本次实际材料复算逐项相等（含 history 前缀与 Gate1 请求保留）。
- 前提拒绝（异常类别 + 目标原因同时核验，标准化／装载调用 0）：Gate1 `pending`／`HOLD`／`REJECT` 的 `prepare-gate2` 均 `WorkflowHostBlocked`；质量坏例 C12 接收即阻断且无下游调用；接收层有限回归：非 ZIP 运行失败批次真实 `receive.exit_code=2` 未被宿主改造，`status` 返回 2；C12 的 `status` 恢复 `BLOCKED_QUALITY` → 1。
- 锁定与冲突：Gate2 pending 后重复 `prepare`（exit 1）、重复 `record`（exit 1）、无 `0004`、数据库与 `0003` 字节不变；旧宿主版本副本（`manifest_version=TASK-010-*`）明确拒绝（“旧宿主版本…请用本版本新建批次”）；无宿主清单的普通接收批次拒绝（“不是本宿主创建的”）；数据库路径冲突在调用上游前拒绝且不覆盖已有文件。
- 产物篡改（同步外层引用后逐项命中目标原因）：`normalized.json` 字节 → `normalized_file_sha256`；`load_report.json` 字节 → `load_report_file_sha256`；数据库字节 → `database_sha256`；`0003` 顶层链引用 → `previous_file_sha256`；操作摘要 → `materials_sha256`。另两项**只改内层指纹**（保持外层 `state_sha256` 自洽）：`operation.normalized_payload_sha256` → 命中；`operation.gate1_decision_sha256` → 命中，证明恢复不是只核外层哈希。
- 有限上游错误（wrapper 先调用**真实上游**再抛上游异常类型，命中各 1 次，明确标注为测试内依赖故障）：`NormalizationBlocked` → 宿主 `WorkflowHostBlocked`/exit 1；`SqliteLoadError` → `WorkflowHostError`/exit 2；两者都尽力独占保存 `failure.json`（含原始 sentinel），此后 `status` 恢复对应的 1／2 且重复 `prepare` 拒绝。
- 0003 真实 writer 有限部分写入：重定向内置 `open` 仅拦截新批次的 `0003.json`，捕获生产 writer 传入的**完整文本**（**14 220 580 UTF-8 字节**），实际写 40 字节后抛独有 sentinel `OSError`：opens／writes／raises **各 1**，异常链 `WorkflowHostError.__cause__ == OSError(sentinel)`，旧 `0001`／`0002` 调用前后字节哈希相同，半文件保留，后续 `status` 拒绝，未宣告成功。完整文本副本以 `newline="\n"` 保存。
- 写后产物变化：包装**真实** `_write_exclusive_json`，在 `0003` 写完后改变本次 `load_report.json` 字节 → 本次操作**未返回成功**，后续 `status` 拒绝。
- 守卫：`status` 只读（进程内 `status` 期间禁止子进程调用（计数器 0）与网络，批次树前后逐文件字节一致，未调用标准化／装载）；静态 AST 守卫证明宿主只导入标准库（无 `requests`／`urllib`／`socket`／`openai`）、无筛查／复算／底稿／生成器调用、**唯一**子进程调用点（冻结接收器）。
- 两项隔离自测（`self_tests.json`）：探针判据“类别正确但目标原因不符 → 判失败、类别+原因相符 → 通过”；计数核验在**内存副本**去掉一条调用记录后判不一致。自测单列，不向正式 `failures` 塞假失败。
- 最终产物：`summary.json`／`checks.json`／`cli_logs.json` 由同一最终对象一次落盘并读回比对一致（`final_readback.json` 的 `ok=true`、`readback_problems=[]`），落盘后未再改计数。

## 6. 历史保护与未执行项

- 主基线 `data/reviews/task010_r4_20261011_125204/source_hashes_after.json`（26215 项）：**仅宿主与指南两项变化、缺失 0**，其余全部未变。
- 更早基线按**累计变化**表述：`task010_r3`(24341)／`task010_r2`(21691)／`task010_r1`(18533)／`task010`(16340) 均为**宿主+指南+旧测试**三项累计变化；`task009_r2`(14691)／13330／12546／10236／8547／6511／4902／874 全部 **0 变化、0 缺失**。
- 冻结上游、`tests/test_run_demo_workflow.py`、旧批次、旧数据库、GPT 证据、旧回执／任务卡／验收单一个字节未改；测试内建 13 个受保护文件前后哈希一致。
- 未执行（不主张通过）：Gate2 决定的实现与提交、`prepare`/`record` Gate2、R01—R04 筛查、独立复算、事实底稿、AI 建议、正式契约、真实 Gate 批准、人类判断保存、UI、真实 ERP、并发／锁／断电持久性、无边界 fuzz；未重跑 TASK-002—010 整套历史测试（旧入口 `tests/test_run_demo_workflow.py` 未运行，其旧静态范围断言未用于本卡）。
- 边界：本地哈希只证明字节一致，不证明来源真实；不提供身份认证或同权限防篡改；模拟流程不等于主理人真实批准；`DEV_GATE2_PENDING` **不是** Gate2 已放行。

## 7. 失败尝试

1. `0003` 校验初版要求保留**全部**请求，但 Gate2 请求本就是本次新增 → 改为只要求完整保留 Gate1 请求、并显式要求 `0002` 的 Gate2 请求为 `null`。
2. 同对象重抛（`raise mapped from exc` 且 `mapped is exc`）把 `__cause__` 自引用，异常链丢失 sentinel → 改为同对象时直接 `raise` 保留原始链。
3. 测试把“前序引用”误改到 `operation.artifacts` 内 → 被 artifacts 一致性先拦下；改为只改 `0003` 顶层 `previous_file_sha256`。
4. `status` 只读守卫起初用 CLI 验证并全局替换 `subprocess.run`，把测试自身的 CLI 启动也拦掉 → 改为**进程内**调用 `inspect_dev_batch` 做守卫，CLI 另作正向确认。
5. 静态守卫初版用子串匹配，被 `state["requests"]` 与绑定哈希表路径误判 → 改为 AST 检查导入、禁止调用与唯一子进程调用点。
6. MAIN 的“标准化／装载次数”初版用进程内计数器统计 CLI 路径（恒为 0）→ 改为按本次真实产物与 `prepare` 返回核验，计数器只用于进程内 API 探针。
7. 首次冒烟时 `record` 在合法 `0003` 链上误报“现场不完整” → 按 revision 分支修正原因文案。
