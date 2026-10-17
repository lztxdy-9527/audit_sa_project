# 运行层演示与后置 AI 只读扩展点指南（TASK-042）

标识：`TASK-042-runtime-demo-1.0`。依据：人类 2026-10-17 指示
（`docs/decisions/DECISION_20261017_DSH_DEMO_SCOPE_AND_AI_DEFERRAL.md`，`DSH-SCOPE-20261017-01`）：
优先做到人类初判、使项目可演示；后置 AI 只预留**只读**扩展点、不实施。
本卡只新增演示脚本与文档，**不修改**任何既有实现/测试/指南/旧证据。

## 1. 单命令演示

```powershell
.venv\Scripts\python.exe -B scripts\run_runtime_demo.py `
  --out-dir data\runtime_initial_judgment_recording_tests\task042_demo_01
```

- `--out-dir` 必须从未存在且位于 `data/runtime_initial_judgment_recording_tests/` 内；重复运行请用新目录。
- 脚本为 `scripts/run_runtime_demo.py`（唯一新增代码），只通过已接受运行时层的**公开 API** 走完：
  注册 → `prepare_runtime_gate1_request`/`save_runtime_gate1_decision` → `run_gate1_approved_load` →
  `prepare_runtime_gate2_request`/`save_runtime_gate2_decision` → `run_gate2_approved_screen`/
  `run_gate2_rule_crosscheck`/`run_gate2_fact_packet` → `prepare_runtime_initial_judgment_request` →
  `save_runtime_initial_judgment` → `verify_runtime_initial_judgment`。
  不直接调用私有内部函数绕过公开入口。
- 人类提交值只读已登记夹具：Gate1/Gate2 决定原文取自
  `data/decision_protocol_checks/task020r2_run_01/fixture_values.json`（`BASE1`/`BASE2`）；
  初判 `event2` 六原文取自
  `data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json`。
  脚本不生成、不推导人类字段。
- 新独立根：`data/runtime/task042_demo_<轮次>`、`data/human_gate_decision_records/gate1|gate2/task042_demo_<轮次>`、
  `data/sqlite_tests/task042_demo_<轮次>`、`data/human_initial_judgment_records/task042_demo_<轮次>`
  （锁留在本轮根内）。不读不写旧证据；失败保留现场、不清理。

## 2. 可阅读产物

演示成功后，`--out-dir` 内写出：

- `demo_summary.json`：批次与实体（澄明商贸有限公司、CNY、2026-09-01 至 2026-09-30、截至 2026-09-30）、
  Gate1/Gate2 决定与记录指纹、R01–R04 待核查线索计数与 R02 超额合计、事实包相对路径、
  初判 `VERIFIED` 记录相对路径 / `record_fingerprint` / `manifest_file_sha256` / 身份、
  六文件与三封装（含长度/FILE）、九权限边界（全部 `false`）、`real_approval=null` 等边界声明。
- `demo_readme.md`：同一内容的人读版本。
- 脚本 stdout 为单行 JSON 摘要；失败时任务回执与证据保留现场，stderr 含真实 traceback。

边界：R01–R04 是待核查线索，不是舞弊、损失、控制缺陷或审计结论；`VERIFIED` 是技术核验，
不是批次批准、不是身份认证；不开放 AI 建议或人类终判。

## 3. 后置 AI 只读扩展点（不实施 AI）

```powershell
.venv\Scripts\python.exe -B scripts\run_runtime_demo.py `
  --inspect-record data\human_initial_judgment_records\task042_demo_01\bound\rec_0001 `
  --inspect-out <证据目录>\inspect_record.json
```

- 独立进程只读消费该 `VERIFIED` 初判记录（六文件 + manifest）：调用冻结 store 的只读核验
  `verify_human_initial_judgment_snapshots`，输出 identity、`record_fingerprint`、manifest FILE、
  六文件清单（长度/FILE）、九边界 false、事实包相对路径、`history_binding`。
- **零写入实证**：运行前后对"记录目录 + 声明域 + 运行封装"做同缓冲快照（路径/长度/FILE）并比较相等
  （`zero_write=true`）；不写记录命名域、不写运行封装、不新增任何文件。
- **不触发业务算法**：不导入运行时适配器，不导入归一化/装载/筛查/复算/事实 build 模块
  （`algorithm_modules_imported=[]`、`algorithm_builds=0`）；不新增公开 API、不改适配器/测试/指南。
  这就是"未来 AI 层可只读接入、不返工已接受层"的可验证证据。

## 4. 五条接口约束（D-SCOPE-3，未来 AI 卡必须遵守）

1. **只读消费者**：只读 `VERIFIED` 人类初判记录（六文件 + manifest）、事实包/材料与 Gate 决定；
   不得写人类记录命名域、运行封装或 Gate 决策。
2. **19 个公开 API 与 17 项代码清单封闭**：AI 层将来是新增模块 + 新增公开入口，不修改既有入口签名与语义。
3. **边界保持显式 false**：`ai_enabled=false`、`next_step_allowed=false`；不预留任何"打开 AI"的开关，
   将来由新卡与人类授权明确开启。
4. **分域存放**：AI 输出与人类初判分开存放，人类初判不可被覆盖、不可被"补签"；AI 建议必须标注非人类来源。
5. **另行授权**：接入前需新的协议/案例卡与人类授权；本指南与决策记录都不构成该授权。

## 5. 不授权范围

真实数据、真实批次批准、强认证、AI 建议实施、人类终判实施、物理 junction 绕过、非合作篡改证明仍未授权：
`real_approval=null`、真实独立初判未保存、开发宿主 0008、`next_step_allowed=false`、`ai_enabled=false`。
