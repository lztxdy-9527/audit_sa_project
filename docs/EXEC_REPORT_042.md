# TASK-042 执行回执：运行层演示就绪（至人类初判）与后置 AI 只读扩展点

日期：2026-10-17。交付状态：演示脚本、文档与证据定稿，**交 Architect 独立验收**；本回执不宣布验收通过，
不改看板、不推进 AI/终判。真实批准 `null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。

依据：`docs/tasks/TASK-042_DRAFT.md`（`b8b4a6b5…6113fa`）、决策记录
`docs/decisions/DECISION_20261017_DSH_DEMO_SCOPE_AND_AI_DEFERRAL.md`（`ee0272fc…fc4be2`，
`DSH-SCOPE-20261017-01`）、`docs/reviews/REVIEW_TASK_041.md`（`25c27fd0…c659dcc`）。
接受基线：`data/reviews/task041_dsh_20261017_01/source_hashes_after.json`（173529 项 / `5a05a245…`）。

本卡**只新增**：`scripts/run_runtime_demo.py`、`docs/RUNTIME_DEMO_AND_AI_EXTENSION_GUIDE.md`、
`docs/EXEC_REPORT_042.md` 与 `task042_demo_*` 证据根；**未修改**任何既有文件（适配器/测试/指南/旧回执/旧证据/旧卡与评审根）。

本回执在最终扫描之前定稿，**不预填扫描结果**；扫描数字、最终身份与确切新增清单在
`data/runtime_initial_judgment_recording_tests/task042_finalization/delivery.json` 与同根 `protection_result.json`。

## 1. 交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 演示入口（唯一新增代码） | `scripts/run_runtime_demo.py` | 见 delivery.json | 见 delivery.json |
| 演示/AI 扩展点指南 | `docs/RUNTIME_DEMO_AND_AI_EXTENSION_GUIDE.md` | 见 delivery.json | 见 delivery.json |
| 本回执 | `docs/EXEC_REPORT_042.md` | 见 delivery.json | 见 delivery.json |

适配器、测试、指南仍为 TASK-041 接受身份（404971/`f5c7c396…`、69930/`ac9c9573…`、7202/`8cef7745…`），未改。

## 2. 单命令演示（实测）

```
.venv\Scripts\python.exe -B scripts\run_runtime_demo.py --out-dir data\runtime_initial_judgment_recording_tests\task042_demo_02
```

- 退出码 **0**；stdout 单行 JSON（`status=PASS`、`record_fingerprint=8645eee5…f20d02`、
  `status_verified=RT_HUMAN_INITIAL_JUDGMENT_VERIFIED`、`boundaries_all_false=true`、`rule_counts_r01_r04=[0,1,0,0]`）。
- 调用序列（全部公开 API，按 `command.json` 与 `demo_summary.json.steps` 实测）：
  `build_runtime_registry` → `prepare_runtime_gate1_request` → `save_runtime_gate1_decision` →
  `run_gate1_approved_load` → `prepare_runtime_gate2_request` → `save_runtime_gate2_decision` →
  `run_gate2_approved_screen` → `run_gate2_rule_crosscheck` → `run_gate2_fact_packet` →
  `prepare_runtime_initial_judgment_request` → `save_runtime_initial_judgment` → `verify_runtime_initial_judgment`。
  未直接调用私有内部函数。
- 人类值来源：Gate1/Gate2 决定原文 = `data/decision_protocol_checks/task020r2_run_01/fixture_values.json`
  `BASE1`/`BASE2`；初判 event2 六原文 = `data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json`。
- 首次迭代 `task042_demo_01` 因读取事实包 `period` 字段位置错误失败，现场原样保留（仅新建根，无演示产物）；
  定稿演示为 `task042_demo_02`。

## 3. 可阅读产物（实测值）

`data/runtime_initial_judgment_recording_tests/task042_demo_02/demo_summary.json`、`demo_readme.md`：

- 批次 `batch_normal`（源批次只读复用 `data/batches/task027r1_run_04/batch_normal`）；
  实体 澄明商贸有限公司 / 人民币（CNY）/ 2026-09-01 至 2026-09-30 / 截至 2026-09-30 / 整数分。
- Gate1 `APPROVE`（指纹 `a4a5d2f4…b920`），Gate2 `APPROVE`（指纹 `898fce4c…ea27`，prior=Gate1 指纹）。
- R01–R04 = **0 / 1 / 0 / 0**（total 1）；R02 超额合计 **400000 分**；均为待核查线索，不是舞弊/损失/审计结论。
- 事实包：`data/runtime/task042_demo_02/normal.facts/fact_packet.json`。
- 初判记录：`data/human_initial_judgment_records/task042_demo_02/bound/rec_0001`，
  `RT_HUMAN_INITIAL_JUDGMENT_VERIFIED`，`record_fingerprint=8645eee5…f20d02`，
  manifest FILE `43b88bad…c253`，身份 批次 `batch_normal` / 人类事件 `2` / 技术请求 `DEMO-REQ-IJ-0001`。
- 六文件（恰六件）与三封装（恰三件）清单含长度/FILE；九权限边界全部 `false`；
  输出内写明“合成演示，不是批次批准、不是身份认证，不开放 AI/终判；`real_approval=null`”。

## 4. 后置 AI 只读扩展点（实测）

```
.venv\Scripts\python.exe -B scripts\run_runtime_demo.py `
  --inspect-record data\human_initial_judgment_records\task042_demo_02\bound\rec_0001 `
  --inspect-out data\runtime_initial_judgment_recording_tests\task042_demo_02\inspect_record.json
```

- 退出码 **0**；独立进程输出 `mode=read_only_inspect`、`status=HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED`、
  identity/`record_fingerprint`/manifest FILE/六文件/九边界/事实包相对路径。
- **零写入**：运行前后对记录目录 + 声明域 + 运行封装做同缓冲快照并比较相等（`zero_write=true`，
  快照 9 个文件前后一致）。
- **不触发业务算法**：`algorithm_modules_imported=[]`、`algorithm_builds=0`；不导入运行时适配器
  （`runtime_adapter_imported=false`）、不新增公开 API（`new_public_api_required=false`）、
  未修改适配器/测试/指南。即"只读接入、不返工已接受层"的可验证证据。

## 5. 五条约束与边界

指南 `RUNTIME_DEMO_AND_AI_EXTENSION_GUIDE.md` 写明 D-SCOPE-3 五条：只读消费 `VERIFIED` 记录/材料/事实；
19 API 与 17 代码清单封闭；边界显式 `ai_enabled=false`、`next_step_allowed=false`、不预留开关；
AI 输出与人类初判分域、人类记录不可覆盖/补签、AI 建议标注非人类来源；接入需新协议/案例卡与人类另行授权。
本卡不实施 AI 建议、不实施人类终判、不使用真实数据、不做强认证。

## 6. 证据与保护

证据根 `data/runtime_initial_judgment_recording_tests/task042_demo_02/`：`command.json`（命令原文/退出码/序列）、
`demo_stdout.txt`、`demo_stderr.txt`、`inspect_stdout.txt`、`inspect_stderr.txt`、`demo_summary.json`、
`demo_readme.md`、`inspect_record.json`（含只读前后快照对比）。
定稿后**一次**全树扫描（`task042_finalization/protection_scan.py`），基线 TASK-041 接受快照
（173529 项 / `5a05a245…`）：相对该基线**既有 changed 必须为 0**；新增仅 `scripts/run_runtime_demo.py`、
两份文档与 `task042_demo_*` 确切路径；新 missing/读取错误/身份漂移 0；139 历史损失、27 恢复、326 越界、
19 命名、TASK-030 41 B 锁继续冻结。扫描后只做有限自身元数据读回。

## 7. 未执行与边界

未执行：真实数据、真实批次批准、强认证、AI 建议实施、人类终判实施、物理 junction、非合作篡改证明、
并发双进程真实竞态（`null` + 原因）。本演示不批准任何真实批次，不认证身份，不开放 AI 或终判。
