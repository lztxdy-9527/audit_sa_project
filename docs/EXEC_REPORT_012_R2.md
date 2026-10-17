# TASK-012-R2 执行回执（仅补测试判定和完整留痕，冻结宿主）

执行端：DeepSeek；独立验收：GPT；日期：2026-10-12（Asia/Shanghai）；项目根目录：`D:\harness work\audit_sa_project`。

依据：`docs/tasks/TASK-012-R2.md`、`docs/reviews/REVIEW_TASK_012_R1.md`。
结论：**F03-A、F03-B、指南两句已完成；宿主严格冻结未改；停在 Gate2 决定后的开发状态**。未推进 TASK-013，未执行筛查／复算／底稿／AI，未建立正式契约、未签真实 Gate、未保存人类判断。

---

## 1. 修改范围与完整哈希

| 文件 | 说明 | SHA-256 |
| --- | --- | --- |
| `scripts/run_demo_workflow.py` | **冻结未改**（实现 `TASK-012-workflow-host-1.1`） | `dc6e53db794322082c14c37ff3da09118f90f01361c0d517aa78e3562bd360a6` |
| `tests/test_record_demo_gate2_decision.py` | 改（F03-A／F03-B） | `184ccb39a7ab9e1b624000d49317d2417484f1c451a62d4cbcc36f61c2aa2564` |
| `docs/WORKFLOW_HOST_GUIDE.md` | 改（仅 §4 两处） | `dbf4b573b58f9dd6e222f18205fa06c54c88b28706d56e41673ab1fa4b315ac8` |
| `docs/EXEC_REPORT_012_R2.md` | 新增（本文件） | 见交付消息 |

起点：宿主 `dc6e53db…`、测试 `d5a18bbb…`、指南 `513e6eda…`；宿主字节与实现／持久化协议版本**均未变动**（协议仍 `TASK-012-*-1.0`）。

## 2. 三条完整产物路径

- 测试容器：`D:\harness work\audit_sa_project\data\workflow_host_tests\task012r2_final_04`（262 个文件）
- 批次父目录：`D:\harness work\audit_sa_project\data\batches\task012r2_final_04`（318 个文件）
- 外置数据库目录：`D:\harness work\audit_sa_project\data\sqlite_tests\workflow_gate2\task012r2_final_04`（13 个文件）

过程现场保留（未回写、未删除）：`task012r2_final_01`（首次运行，含一个真实失败）、`task012r2_final_02`、`task012r2_final_03` 及其对应批次与数据库目录。

## 3. 实际命令与退出码

```text
D:\harness work\audit_sa_project\.venv\Scripts\python.exe -B tests\test_record_demo_gate2_decision.py --out-dir data\workflow_host_tests\task012r2_final_04
退出码 0；10 组全部 PASS；failures=[]；受保护文件 13 个前后一致
```

源文本 compile 检查均 OK（宿主与新测试）；运行使用 `-B` 与禁写 bytecode，未生成 `.pyc`。

## 4. F03-A：缺调用记录进入 G10 正式失败

新增测试内共用判定 helper `audit_call_records(registered, records, copies)`：缺记录与未登记记录都由它产出 `problems` 与 `verdict`（副本按**路径层级**排除），**正式 G10 审计与三项隔离内存对照使用同一规则**；`missing_records` 不再追加到已经 `record()` 完成的 `g8_problems`，而是由正式审计写入 `g10_problems`。

正式审计（本轮真实材料）：`registered=17`、`records=17`、`missing_records=[]`、`unregistered_records=[]`、`verdict=PASS` ✓（与 TASK-012-R1 已核实的 17/17 一致）。

三项内存对照与判定证据（`count_self_test.json`，独立保存）：

| 对照 | 结果 |
| --- | --- |
| 完整登记与记录一致 | `verdict=PASS`，`missing=[]`，`unregistered=[]` |
| 删除一条已登记记录（`c02_hold`） | `verdict=FAIL`，`missing=['data\batches\task012r2_final_04\c02_hold']` |
| 加入一条未登记记录 | `verdict=FAIL`，`unregistered=['…__in_memory_unregistered__']` |

G10 正式判定随之改变（同一判定表达式 `g10_verdict(problems)`，与 `record()` 用法一致）：

```text
formal                          = PASS
if_one_registered_record_removed = FAIL   （缺记录 → 正式 G10 必 FAIL、入口不得退出 0）
if_one_unregistered_record_added = FAIL
```

`control_checks` 六项全 true（`complete_passes`、`dropped_record_fails_with_missing`、`unregistered_record_fails_with_unregistered`、`verdict_changes_for_both_directions`、`g10_verdict_fails_when_record_missing`、`g10_verdict_fails_when_record_unregistered`）；未把故意的 FAIL 塞进最终 `failures`，本轮真实审计材料完整，故 `failures=[]`、退出 0 ✓。

## 5. F03-B：新探针完整调用现场（不截断）

三个 G9 探针各自落盘**完整结构化记录**并读回核对（checks 中只留摘要 + 可解析引用）：

| 探针 | 完整记录 | 字节 | 读回核对 |
| --- | --- | --- | --- |
| `G9_F01_TAIL_0004_EXPECTED_SET` | `g9_probe_records\G9_F01_TAIL_0004_EXPECTED_SET.json` | 10959 | `readback_identical/message_complete/decision_body_preserved` 全 true；消息 **200** 字符 |
| `G9_F02_RECORD_STATIC_BINDING_TAIL` | `g9_probe_records\G9_F02_RECORD_STATIC_BINDING_TAIL.json` | 16551 | 三项全 true；消息 **257** 字符（> 旧 `[:240]` 截断，证明完整） |
| `G9_F02_STATUS_STATIC_BINDING_TAIL` | `g9_probe_records\G9_F02_STATUS_STATIC_BINDING_TAIL.json` | 15066 | 三项全 true；消息 **252** 字符（同上） |

每条记录含：`case`、被调用函数（解出观察包装器背后的真实入口：`task012_host.record_simulated_gate2_decision`／`task012_host.inspect_dev_batch`，并标 `called_through_observed_entry=true`）、`batch_dir`、完整实参、完整决定正文与正文指纹、预期异常类别与目标原因、`outcome`（完整异常类／消息／`stage`／`reasons`／直接 cause／**逐帧 traceback**，F01 7 帧、F02 各 6 帧）、目标文件与**真实 before/after 哈希**、命中数与注入时点、以及"冻结 `check_dev_action` 先真实返回、之后才修改磁盘"的时序说明、撤销 wrapper 后**新进程 CLI 的完整命令／退出码／stdout 与 stderr 路径引用／完整 payload**、以及正向恢复对照（`restored_control_exit=0`）。

三个探针仍在**本次调用即拒绝**（`current_call_rejected=true`、`hits=1`、`before≠after`），撤销后新进程 status 仍 exit 1。

入口事件紧凑列表落盘并逐项核对（`entry_events.json`）：`api_events=31`、`controller_events=245`、`controller_sample_events=0`，与 `host_api_calls=31`、`controller_replay_calls_inproc=245`、`controller_sample_calls=0` **逐项一致**（未为 245 次重放复制完整 workflow）；计数全部由**本轮实际留痕**导出，未硬编码任何前轮数字。

保留未退化：`writer_evidence.json`（完整待写文本另存 `writer_full_expected_0004.json`，`full_utf8_bytes=14221574`、`old_checkpoints_unchanged=true`、`cause_class=OSError`、部分文件 40 字节）；`0004` 分类=原始文件 **12**（可解析原始 **10** + 副本 **1** + 半文件 **1**），经恢复核验的合法决定 **9**，`0005=0`；未退回用 `rglob` 文件数冒充决定数。

## 6. 指南（仅两处）

1. 页首：`不实现也不提交 Gate2 决定` → `只保存显式模拟决定，不执行筛查，也不提交任何真实批准`（已核对旧表述不再出现）。
2. checkpoint 说明段：宿主实现版本 `TASK-012-workflow-host-1.0` → `TASK-012-workflow-host-1.1`；持久化协议版本仍 `TASK-012-checkpoint-1.0`。未做其他改写。

## 7. 计数（本轮实际导出）

CLI：`start 17`、`status 42`、`record-simulated-decision 17`、`prepare-gate2 12`、`record-simulated-gate2-decision 14`。
进程内：公开宿主 API **31**（含经 status helper 进入的 `inspect_dev_batch` 与抛错前已进入的调用，同一入口只记一次）、宿主内部控制器重放 **245**、测试侧控制器造样 **0**；CLI 子进程内次数仍**未观测 null**，推导值单列。
接收／质量：receiver **17**（宿主 17 + 直接 0）、checker **17**（按 `batch_manifest.checker_invocation.started`）；进程内真实标准化／装载 **3/2**；副本 **1**（登记来源、排除）；故障注入 **18**；负向拒绝 **26**；**真实批准 0**。

## 8. 保护结果

- 主保护基线 `data/reviews/task012_r1_20261011_172051/source_hashes_after.json`（50404 项）：变化 **2**（恰为授权的测试与指南）、缺失 **0**。
- `task012`（46623）仍为宿主／测试／指南 **3 项**累计授权；`task011_r2`（39831）仍只有宿主／指南 **2 项**（该基线时 TASK-012 测试未建立）；`task011_r1`（34813）与 `task010`（16340）各 **3 项**历史累计授权；`task009_r2`（14691）及更早 13330／12546／10236／8547／6511／4902／874 全部 **0 变化、0 缺失**。
- 冻结上游逐项未变：控制器 `a6b7b8e1`、接收器 `52195620`、checker `a7e5eb67`、标准化 `a2bae49e`、装载器 `1abfad89`、schema `7e0c6463`、筛查 `1b123766`、复算 `8fe75bfe`、底稿 `f4998d92`、SPEC `5df632ed`、契约草案 `af405cb6`、旧入口 `test_run_demo_workflow.py` `852bf336`、`test_prepare_demo_gate2.py` `11d4fe57`。
- 宿主内仍恰 5 个 CLI、AST 无筛查／复算／底稿调用；所有被核对 checkpoint 的真实批准均 `null`、`next_step_allowed=false`；四份文件 UTF-8 无 BOM；临时补丁脚本与 `__pycache__` 已清理。

## 9. 失败尝试

1. `persist_probe_record` 首次读回异常消息时用了错误的键路径（`outcome.exception.message`，实际为 `outcome.message`）→ 三个探针的 `message_complete=false`、G9 FAIL、入口退出 1（**按真实缺陷保留失败**，未放宽断言）→ 修正键路径后通过。
2. 完整记录最初未内嵌被调用函数，`function` 显示为观察包装器 `__main__.wrapper` → 解出 `__wrapped__` 真实入口并标注 `called_through_observed_entry`；同时把整个调用现场对象（`call`）内嵌进记录，避免字段遗漏。
3. 首次核对脚本读取 `called_through_observed_entry` 时报 KeyError，说明仅复制个别字段易漏证据 → 改为整对象内嵌并独立读回核对。
4. 保护基线比对脚本早期对"更早基线"的授权集合写得过严，一度把历史已授权的 `test_prepare_demo_gate2.py`／`test_run_demo_workflow.py` 变化误标 FAIL；据实复核后确认这些是早前任务已授权的累计变化，本轮新增仅测试与指南两项。

## 10. 未执行（不写通过）

TASK-013；筛查／R01—R04；独立复算；事实底稿；AI 建议；正式契约；真实 Gate；人类判断保存；UI／真实 ERP／压测；并发锁／断电试验；无边界时序枚举 fuzz；未重跑 TASK-002—011 历史整套入口（本卡由新入口覆盖）。

**停止状态**：停在 Gate2 决定后的开发状态（`DEV_GATE2_APPROVED`／`HELD`／`REJECTED`）；模拟 `APPROVE` **不是**真实 Gate2 放行，宿主没有筛查执行命令。等待 GPT 独立验收。
