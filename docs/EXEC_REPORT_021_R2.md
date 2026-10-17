# TASK-021-R2 执行回执（历史记录跨字段合法性与终审失败传播）

任务：按 `docs/tasks/TASK-021-R2.md` 定点修正 `docs/reviews/REVIEW_TASK_021_R1.md` 的两项剩余阻断（B类，DSH 处理）；不进入 P2。
日期：2026-10-13。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与批次批准：人类主理人。

**边界重申**：未改变 API、schema/输出常量、材料算法、业务矩阵、14 步、纯内存与固定 `false` 边界，未新增参数、历史全局发现、祖先图或磁盘核验；无 CLI/持久化/恢复/放行/网络。返回内存记录仍 **≠ 已保存 ≠ 身份认证 ≠ 批次批准 ≠ 运行放行**；未生成真实 Gate/初判/`0009`，未开放 AI/终判，未放行任何批次。

---

## 1. 起点身份与保护基线

| 项 | 起点/基线 | 实读 |
| --- | --- | --- |
| 核心 | `081f725e1374a51405a6cccdece30e8acf7eda234cf2cf531fe6ca6064e4f595`（51741） | ✅ 一致 |
| 测试 | `37108ff863b53723974d0c32ecc65d0006cd6648c06f99648dbc8a8e6e6b2ded`（100344） | ✅ 一致 |
| 指南 | `0839632e86f7df6a0809f860dfa68680c59b89a285fdecce6c75060ec94e4b5b`（17980） | ✅ 一致 |
| R1 回执（冻结，未回写） | `194cc8e5e40e708d996d2411ef2c620fec377a030fdb22f4a514cb5822918daa` | ✅ 一致 |
| 保护基线 `data/reviews/task021_r1_gpt_20261013_204526/source_hashes_after.json` | `review_result.json` 的 `verdict=NOT_ACCEPTED` | ✅ `NOT_ACCEPTED`；基线 SHA `cb4b111fe20c9911d0b4dc096fc3443ae99f6bc78386ce660507b332f43c13d8`、**133584** 项 |

未使用 TASK-020 旧基线或 R1 旧基线代替本次基线；评审根（含 `targeted_probes.py`、`final_audit_fault.py`、`probe_records.json`）与旧容器只**只读**使用，未运行、未覆盖、未回写。

---

## 2. B1 剩余：历史记录跨字段关系（逐项关闭）

**根因**：`_validate_record_full` 只校验历史记录“字段各自合法”，未把 `record.decision` 与 `quality_summary` 联动、也未核 Gate2 历史 `prior_gate1` 摘要的派生关系。

**修正**（核心，仅作用于**已提供历史**；当前前序仍按第 11 步更严格的 OK/APPROVE/同批次/同运行要求）：

- 新增 `_validate_record_decision_matrix`：历史记录也必须满足 §12 矩阵——`OK` 三决定均可；`BLOCKED` 下 `APPROVE` 拒绝（`field = …record.decision`）；`FAILED` 三种决定均拒绝（`field = …record.quality_summary.status`）。不是对评审值的黑名单，也不一律拒绝 `BLOCKED` 历史。
- 新增 `_validate_record_prior_summary_relations`（Gate2 历史记录）：`prior_gate1.gate` 必须 `GATE1`、`decision` 必须 `APPROVE`、`batch_id` 必须等于**该历史记录自身**批次、`actor_kind` 必须 `HUMAN_DECLARED`，且摘要 `event_id` **不得**等于该记录自身 `event_id`；保留原有完整键/字符串/哈希检查。比较对象是该历史记录，不是当前提交批次。
- 两者都在 `_validate_record_full` 内、位于质量/边界校验之后（第 11 步后、第 12 步前），未改变既有校验顺序与已关闭的子步行为。

**评审 8 个新反例的实际复现**（每例其他批次完整历史、非目标部分合法、正确重算 wrapper 指纹、当前输入不变）：

| 评审名称 | 本卡用例 | 实际结果（field） |
| --- | --- | --- |
| `history_quality:BLOCKED:APPROVE` | HR-01 | `…record.decision` Blocked |
| `history_quality:FAILED:APPROVE` | HR-02 | `…record.quality_summary.status` Blocked |
| `history_quality:FAILED:HOLD` | HR-02 | 同上 |
| `history_quality:FAILED:REJECT` | HR-02 | 同上 |
| `history_Gate2_summary:gate=GATE2` | HR-03 | `…record.prior_gate1.gate` Blocked |
| `history_Gate2_summary:decision=HOLD` | HR-04 | `…record.prior_gate1.decision` Blocked |
| `history_Gate2_summary:decision=REJECT` | HR-05 | `…record.prior_gate1.decision` Blocked |
| `history_Gate2_summary:batch_id=OTHER-BATCH` | HR-06 | `…record.prior_gate1.batch_id` Blocked |

另加**自我前序事件**反例 HR-07（摘要 `event_id` 等于该记录自身）→ `…record.prior_gate1.event_id` Blocked。8 项名称与评审 `probe_summary.json` 的 `expectation_failures` **只读交叉一致**（`independent_expectations.json` 中的 R1 交叉项）。

**历史正向对照（不得一律拒绝）**：HP-01 其他批次 GATE1 `HOLD`、HP-02 其他批次 GATE1 `REJECT`、HP-03 其他批次**合法 Gate2**、HP-04 `BLOCKED`+`HOLD`、HP-05 其他批次 GATE1 `APPROVE`（OK 三决定之一）、HP-06 `BLOCKED`+`REJECT`、HP-07 其他批次 **Gate2 HOLD**（摘要关系自洽）——**七例全部正常成功返回**。原 14 控制/反例（RV-01—RV-12 + 两项正常控制）仍全部满足；**C-112—C-115 仍在运行绑定目标字段被拒、C-116 正常**；原 117 设计映射、R1 字段/schema/时间/纯内存/无别名/质量矩阵/内部 Error 原因链继续保持。

---

## 3. B2 剩余：终审失败必须支配结论（逐项关闭）

**根因**：收尾重建 `ledger_final` 后虽已计算 `validation_final`，但其非空问题未进入 failures、未改变 `summary`、也未改变返回码。

**修正**（测试收尾最小实现）：终审读取（`phase="final"`，真实 `_ledger_from_disk`）→ `_validate_ledger` 得到 `validation_final`；**若非空**则：追加正式 failure、`summary.status="FAIL"`、`checks_failed` 同步、写 `final_audit_diagnostic.json`（记录该次真实读取的台账条目快照、检测到的 `missing`/`unregistered`、`dominates_exit_code=true`、后续写入清单），并**返回 1**；失败路径**不再重建台账**以避免掩盖现场。正常路径保持既有正常最终字节闭合、summary/checks 计数刷新、入口观察与权威登记双向审核。

**真实收尾故障验证**（`task021r2_fault_01/final_audit_fault.py`，故障套件目录与正常容器分开、故障现场保留不清理）：包装真实 `_ledger_from_disk`，在 `phase="final"` 的真实读取返回原字典后，仅对该套件目录的 `checks.json` **追加一个 LF**（不同步期望、不替换验证器、不改核心与旧文件）：

| 项 | 实测 |
| --- | --- |
| 注入命中 | **1**（`checks.json` 84209 → 84210 字节） |
| 终审检测 | `validated.missing = ["checks.json"]`（真实字节不符） |
| 套件返回码 | **1**（`expected_return_nonzero=true`） |
| `summary.status` | **FAIL**（`checks_failed` 同步非零） |
| `failures` | **非空**（记录“最终台账审计失败（终审失败支配结论）”） |
| 诊断留证 | `final_audit_diagnostic.json` 存在，记录检测结果与台账快照 |

故障运行与正常完整回归**分列留证**，不把故障运行称为“正常 347/0”。另将文件台账隔离改为**调用真实 audit helper** 判定（不再硬编码 `original_passes`），权威调用登记隔离（删一条真实调用即失败、原件通过）保持。

---

## 4. 实际运行与计数（正常控制）

```text
.venv\Scripts\python.exe -B tests\test_build_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_tests\task021r2_run_01
→ TASK-021-R2 测试组：380 项检查，0 项失败；核心调用 195 次（入口观察 195）；守卫命中 0
→ 退出码 0
```

| 计数项 | 值 |
| --- | --- |
| 核心公开入口调用（权威登记） | **195**（入口观察同为 **195**） |
| 按结果 | 见 `counts.json`（`unexpected=0`；1 次受控注入 error） |
| 守卫命中 | **0** |
| 编号分列 | 原设计编号 **117**；R1 维度 RV/RS/HS/HP；**R2 维度 HR-01—HR-07**（`case_map.json` 分列计数） |
| checks / failures | **380 / 0**（`summary.json` 与 `checks.json` 实读一致） |
| 台账 | 12 项最终载荷逐文件 exists/字节/SHA，读回审核 `missing=[]`、`unregistered=[]` |
| 故障套件 | 返回码 **1**、`summary=FAIL`、failures 非空（§3） |

---

## 5. 交付文件（写后实读）

| 文件 | SHA-256 | 字节 |
| --- | --- | --- |
| `scripts\build_demo_human_gate_decision.py` | `5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79` | 53584 |
| `tests\test_build_demo_human_gate_decision.py` | `472586942f9822bd249385a88607a90c5dbcf9db54730b1ea5c18296be9885a8` | 111931 |
| `docs\HUMAN_GATE_DECISION_GUIDE.md`（已同步能力、编号映射与终审传播说明） | `9345baf16297dd53a7bfeb83d5392697c08b86f11d34504f78f068546fffd980` | 20780 |
| `docs\EXEC_REPORT_021_R2.md`（本回执） | 自身最终 SHA **只在交接消息给出**（不写回自身） | 11528 |
| `data\human_gate_decision_tests\task021r2_run_01\`（正常最终容器） | 12 项载荷逐文件登记（`evidence_ledger.json`：`entry_count=12`、`validated={missing:[],unregistered:[]}`、每条与磁盘实读一致）+ 保护脚本/结果（分层登记） | — |
| `data\human_gate_decision_tests\task021r2_fault_01\`（故障现场） | `final_audit_fault.py`、`final_audit_fault_result.json`、`final_audit_fault_suite/`（含故障后 `checks.json` 与 `final_audit_diagnostic.json`） | — |

**过程容器**（保留、不回写）：`task021r2_dev_01`（局部定点运行：380/0）。

---

## 6. 过程失败与未执行事项

- 局部迭代期间修正：新增维度用例登记与编号分列检查的一次修正（原按 `C-\d+` 解析计数的检查扩展为分列计数）；此前相位的历史现场（R1 的语法/夹具升级/内部 `KeyError` 捕获、两次扫描与看板补建顺序偏差）按卡**仅登记、不回归、不清理**。
- 未执行：receiver/checker 链、宿主/控制器接线、持久化/恢复/独占保存、真实初判、AI/终判、TASK-002—020 历史业务链、旧评审脚本与旧容器工具（`not_executed`/`null`，不填默认零）。

---

## 7. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task021_r1_gpt_20261013_204526/source_hashes_after.json`（`cb4b111f…13d8`、133584 项、`verdict=NOT_ACCEPTED`）；清单自身与同目录 `review_result.json` 按**两个确切路径**单列，不豁免整个 reviews 目录；未使用 TASK-020 旧基线。
- 执行者：本卡正常容器内 `scan_protection.py`（只读项目文件、只写本容器 `protection_result.json`），**仅一次**，在本轮核心/测试/指南/回执齐备且正常完整入口与故障验证均完成后执行。
- 结果见 §7.1（扫描后有限登记）。

### 7.1 扫描结果（有限登记）

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **133630** |
| `changed` | **仅 3 个本轮修改文件**：`scripts/build_demo_human_gate_decision.py`、`tests/test_build_demo_human_gate_decision.py`、`docs/HUMAN_GATE_DECISION_GUIDE.md`；**范围外变化 0** |
| `missing` / 读取错误 / 范围外新增 | **0 / 0 / 0** |
| 本轮允许新增 | **44** 项：`docs/EXEC_REPORT_021_R2.md` + `data/human_gate_decision_tests/task021r2_*`（正常容器、故障现场、过程容器）逐项登记 |
| 基线自身与同目录 `review_result.json` | 按**两个确切路径**单列，未豁免整个 reviews 目录 |
| 扫描后动作 | 仅对本回执与保护元数据做有限身份登记（本节数值与文件身份）；**未再修改核心/测试/指南**，未重复全树扫描 |

### 7.2 正常容器与故障现场的实测数值（登记）

- 正常容器 `task021r2_run_01`：`summary.status=PASS`、`checks_total=380`、`checks_failed=0`、`core_calls_total=195`、`real_entry_observed_calls=195`；按结果 `returned=34`/`blocked=160`/`error=1`/`unexpected=0`；台账 12 项全部与磁盘一致；编号分列：原设计 **117**、R1 维度 **54**、R2 维度 **7**；权威登记隔离 `audit_copy_fails=true`（删 `call-195`）、`original_passes=true`；文件台账隔离**调用真实 audit**：副本 `unregistered=["checks.json"]`（失败）、原件通过。
- 故障现场 `task021r2_fault_01`：`suite_return_code=1`、`summary_status=FAIL`、注入命中 1、终审 `missing=["checks.json"]`、五项故障断言全真（`ok=true`），诊断文件与故障后 `checks.json`（84210 字节）保留未清理。

---

## 8. 绝对路径

- `D:\harness work\audit_sa_project\scripts\build_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\tests\test_build_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_021_R2.md`
- `D:\harness work\audit_sa_project\data\human_gate_decision_tests\task021r2_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_tests\task021r2_fault_01\`

---

## 9. 停止点

完成本卡后执行端停止本轮实施并移交 GPT 整体验收；**通过前不制定/实施 P2**。不接宿主/控制器，不生成真实 Gate 批准/真实初判/`0009`，不开放 AI 或终判；人类业务决定与契约生效确认不重开；若后续需要改变架构或业务规则，立即停止受影响处理并报告升级。
