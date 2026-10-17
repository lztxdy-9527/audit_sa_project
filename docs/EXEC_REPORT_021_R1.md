# TASK-021-R1 执行回执（前序/历史 record 完整校验与最终证据审核）

任务：按 `docs/tasks/TASK-021-R1.md` 定点修正 `docs/reviews/REVIEW_TASK_021.md` 的两项阻断；不进入 P2。
日期：2026-10-13。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与批次批准：人类主理人。

**边界重申**：本轮只改核心校验与测试/证据收尾；返回内存记录仍 **≠ 已保存 ≠ 身份认证 ≠ 批次批准 ≠ 运行放行**。未接宿主/控制器，未生成真实 Gate/初判/`0009`，未开放 AI/终判，未放行任何批次；真实批准仍 `null`、真实初判未保存、`next=false`。

---

## 1. 起点身份与保护基线

| 项 | 起点/基线 | 实读 |
| --- | --- | --- |
| 核心 `scripts/build_demo_human_gate_decision.py` | `1355dce0b22a90dbe1d1d08bb05c49a6d5e76c2c6b21d15a8ae6b512463d6a68`（44307） | ✅ 一致 |
| 测试 `tests/test_build_demo_human_gate_decision.py` | `f7a6c8c8a073a891c2505c69a09409e2e1f5739eebc1156d34d2ee55ac67b02b`（65762） | ✅ 一致 |
| 指南 `docs/HUMAN_GATE_DECISION_GUIDE.md` | `5a753b15c0ca378cb07b4e2fb7e782fed7b2944dc7f2cad599c8bd5f6ce50caa`（15225） | ✅ 一致 |
| 保护基线 `data/reviews/task021_gpt_20261013_195927/source_hashes_after.json` | 同目录 `review_result.json` 的 `verdict=NOT_ACCEPTED` | ✅ `verdict=NOT_ACCEPTED`；基线 SHA `c972ad8c660097adfb2bcad02b99545ca16358e7cc9c2e2cfdbc0368fd710f29`、**133481** 项 |
| 正式契约 / 协议 / 案例 / D1-D3 / 宿主与全部上游 | 冻结 | ✅ 未改（保护扫描 `changed` 仅本轮修改文件） |

未使用 TASK-020 旧基线代替本次基线；未运行或覆盖旧容器中的脚本（评审根只做**只读**交叉）。

---

## 2. B1：前序/历史 record 完整校验（逐项关闭）

**根因**：`_step11_prior` 只校验记录顶层键、部分常量/身份/摘要与选定绑定值，未对 `record` 的嵌套对象执行封闭 schema；`_step4_prior_history` 只取少量字段，已提供历史的疑似损坏对象可进入 `_step12_history`。

**修正**（核心，保留 API/常量/17 键/14 步/材料算法/质量矩阵/固定 false）：

- 新增完整记录校验：`_validate_record_header`（顶层封闭键/常量/枚举/来源/说明/时间/身份/`prior_gate1`/`note`）、`_validate_record_binding_materials`（`binding` 封闭键、`request_id`、材料指纹全串格式、`materials_files` 非空/唯一/UTF-8 升序/逐项 `relative`+字节 SHA+严格非负 `byte_size`）、`_validate_record_contract`（契约封闭键/版本/SHA/**`contract_effective` 严格 true**）、`_validate_record_run_binding`（复用 `_validate_run_binding` 的逐层封闭键/类型/哈希）、`_validate_record_quality_boundaries`（`quality_summary` 封闭键/状态枚举/**派生计数自洽**、`execution_allowed` 严格 `False`、`boundaries` 六键严格 `false`）。
- 第 11 步子序重排为 **11a 形状 → 11b 顶层 schema → 11c binding/文件成员 → 11d 正文复算 → 11e 身份 → 11f 契约 → 11g 运行绑定（含六字段与独立预期）→ 11h 质量与边界 → 11i 三处指纹闭合与历史一致**；摘要复算只是其中一项，不再替代 schema 与来源/契约声明校验。
- 新增**已提供历史合法性核验** `_validate_history_records`，位置在**第 11 步之后、第 12 步语义判定之前**：每个 member 必须 wrapper 版本常量 + 指纹格式 + **与记录正文复算一致** + **完整 record schema**；该核验是**自洽合法性**——允许合法 `HOLD`/`REJECT`、其他批次、合法 Gate2 记录，**不**要求 Gate1/APPROVE/同批次/同运行绑定。第 4 步仍只做名单规则，未把当前前序的内部常量/质量/运行语义前移。
- 未新增输入参数/输出字段/业务入口；未从 `reason` 内容或 ID 前缀推断身份或授权；未从记录摘要反推原始材料真实性。

**评审 12 个反例的实际复现**（独立对象；每例先重算记录摘要并同步提交 wrapper/独立前序预期/历史，再调用公开核心）：

| 评审名称 | 本卡用例 | 实际结果（field） |
| --- | --- | --- |
| `prior_AI_source` | RV-01 | `…record.decision_source` Blocked |
| `prior_empty_reason` | RV-02 | `…record.reason` Blocked |
| `prior_invalid_calendar` | RV-03 | `…record.decided_at_raw` Blocked |
| `prior_actor_extra` | RV-04 | `…record.actor.role` Blocked |
| `prior_actor_missing_id` | RV-05 | `…record.actor.actor_id` Blocked |
| `prior_contract_not_effective` | RV-06 | `…record.binding.contract_binding.contract_effective` Blocked |
| `prior_material_digest_LF` | RV-07 | `…record.binding.materials_fingerprint` Blocked |
| `prior_code_extra` | RV-08 | `…record.binding.run_binding.code.extra` Blocked |
| `prior_negative_file_size` | RV-09 | `…record.binding.materials_files[].byte_size` Blocked |
| `prior_nonnull_gate1_ancestor` | RV-10 | `…record.prior_gate1` Blocked |
| `prior_quality_extra` | RV-11 | `…record.quality_summary.extra` Blocked |
| `history_invalid_wrapper_and_partial_record` | RV-12 | `prior_history.records[0].wrapper_version` Blocked |

12 例全部由对应字段拒绝（不是被摘要不一致或缺历史提前拒绝）；用例名称与评审 `probe_summary.json` 的 12 项**只读交叉一致**（`independent_expectations.json.review_probe_crosscheck`）。

**新增维度覆盖**（RS-01—RS-25、HS-01—HS-10）：记录路径的常量/枚举（`record_version`/`record_status`/`decided_at_source`/`note`/`gate`）、未知与缺失嵌套键（`actor.role`、`run_binding.code.extra`、`quality_summary.extra`、`actor_id`、`request_id`、`boundaries.persisted`、契约文件 SHA）、哈希尾 LF/CRLF/空格、大写与截断（材料指纹、文件 SHA、运行绑定哈希）、bool 冒充严格整数/布尔（计数、`byte_size`、`execution_allowed=0`、字符串 `"false"`）、非法日期与无时区、非法/无序材料文件名单与非法 `relative`、契约生效类型与取值；历史错版本/非 SHA 指纹/指纹与正文不符/记录不全/SYSTEM 身份/契约未生效/非法时间/空白说明/缺 `record`/FAILED 计数矛盾。

**历史正向控制**：HP-01 其他批次合法 `GATE1 HOLD`、HP-02 其他批次合法 `GATE1 REJECT`、HP-03 其他批次**合法 Gate2 记录**（未一律当成 Gate1 前序拒绝）、HP-04 `BLOCKED` 质量且派生计数自洽的 `HOLD` 记录——四例均正常成功返回。

**回归确认**：117 个设计案例仍全部有实际调用映射；质量矩阵、时间/ID 保真、无别名、纯内存守卫、内部 Error 原因链照旧；**C-112—C-115 仍在 11f 各自目标字段被拒**（新历史核验未提前遮蔽），C-116 同版本对照仍成功；BASE1 输出记录与冻结正文 `record1` 规范相等（`15bebb48…8c19`）。

---

## 3. B2：最终证据收尾与真实入口观察（逐项关闭）

1. **最终台账不再记录收尾前文件**：改为“先写全部最终载荷 → 登记台账 → 读回审核”，台账覆盖 **12 项核心载荷**（含 `summary.json`、`checks.json`、`failures.json`、`counts.json`、`api_records.json`、`call_registry.json`、`isolation_self_tests.json` 等）。实读：**每一条台账条目与磁盘字节/SHA 完全一致**（`missing=[]`、`unregistered=[]`）；审核结论写回 `checks/failures` 后**重建台账**并在文件中记录 `post_audit_refresh.refreshed_entries`（实证刷新项为 `checks.json`），登记后未再改写任何载荷。台账不内嵌自身 SHA。
2. **真实公开核心入口观察**：`sys.setprofile` 在**真实公开入口函数代码帧的 `call` 事件**上独立计数，与测试 Registry 分列核对——本轮**入口观察 183 = 登记 183**（`entry_observer.json` + `call_registry.json.entry_observation`）；观察只写内存，不修改核心、不补调核心。
3. **调用登记↔API 记录双向审核**：按调用 ID 双向核对（重复/`missing_in_api_records`/`extra_in_api_records`/声明总数/每条含 `result`），并**从最终交付文件读回**两个载荷再核对（`evidence_ledger.json.post_audit_refresh.disk_audit`）；全部为空集、通过。
4. **权威调用登记隔离自测**：隔离副本**只删除权威登记的一条调用**（`call-183`）→ 审核必须失败（副本计数/集合与 API 记录不符），**原件仍通过**；文件台账隔离（删副本一条文件登记）另行保留，两者作用区分、不互相替代。
5. **完整输入/返回与原因链**：每次核心调用保存完整四入参快照、完整返回记录或异常类型/`field`/`stage`/`reason`/`traceback`，并**统一保存 `cause_chain`（`__cause__`/`__context__` 如实保留，无链则为空列表）**；调用前/后以**同一真实引用**取规范指纹，`inputs_unchanged` 全为真。
6. **计数来自现场**：`counts.json` 分列核心 API 调用与测试运行器进程；未执行项（receiver/checker、宿主/控制器、持久化/重放、AI/终判、历史业务链）写 `null`/`not_executed`，不填默认零。

---

## 4. 实际运行与计数

```text
.venv\Scripts\python.exe -B tests\test_build_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_tests\task021r1_run_02
→ TASK-021-R1 测试组：347 项检查，0 项失败；核心调用 183 次（入口观察 183）；守卫命中 0
→ 退出码 0
```

（首次完整入口在 `task021r1_run_01`：346 项检查、0 失败、183 次调用；因 §6.5 的计数一致性修正而由 `run_02` 取代为最终容器。）

| 计数项 | 值 |
| --- | --- |
| 核心公开入口调用（权威登记） | **183**（入口观察同为 **183**） |
| 按结果 | `returned=31`、`blocked=151`、`error=1`（受控注入）、**`unexpected=0`** |
| 按类别 | `normal=176`、`prior_prep=1`、`determinism=2`、`no_alias=2`、`injection=1`、`guard=1` |
| 守卫命中（`builtins.open`/`os.open`/`socket.socket`/`subprocess.Popen`） | **0** |
| 设计案例映射 | **117/117**，另有 R1 维度用例 RV-01—RV-12、RS-01—RS-25、HS-01—HS-10、HP-01—HP-04 |
| checks / failures | **347 / 0**（`summary.json` 与 `checks.json` 计数一致，实读核对） |

---

## 5. 交付文件（写后实读）与最终容器

| 文件 | SHA-256 | 字节 |
| --- | --- | --- |
| `scripts\build_demo_human_gate_decision.py` | `081f725e1374a51405a6cccdece30e8acf7eda234cf2cf531fe6ca6064e4f595` | 51741 |
| `tests\test_build_demo_human_gate_decision.py` | `37108ff863b53723974d0c32ecc65d0006cd6648c06f99648dbc8a8e6e6b2ded` | 100344 |
| `docs\HUMAN_GATE_DECISION_GUIDE.md`（非必改，已同步实际校验/证据能力） | `0839632e86f7df6a0809f860dfa68680c59b89a285fdecce6c75060ec94e4b5b` | 17980 |
| `docs\EXEC_REPORT_021_R1.md`（本回执） | 自身最终 SHA **只在交接消息给出**（不写回自身） | — |
| `data\human_gate_decision_tests\task021r1_run_02\`（最终完整入口容器） | 12 项载荷逐文件登记（`evidence_ledger.json`），`entry_count=12`、`validated={missing:[],unregistered:[]}`、每一条与磁盘字节/SHA 实读一致 | — |

**过程容器**（保留、不回写）：`task021r1_dev_01`、`task021r1_dev_02`、`task021r1_dev_03`（局部定点运行）、`task021r1_run_01`（先完成的完整入口；其全树扫描结果已因 §7.2 披露的扫描后修正而作废，保留原样不再回写）、`task021r1_run_02`（**最终完整入口 + 最终保护扫描**）。

---

## 6. 失败过程（如实登记）

1. 首轮测试串在 RS-18 案例出现括号不匹配（语法错误，未进入核心）→ 修正后通过。
2. 首轮本地运行曾出现 5 项失败与设计案例映射不足（TASK-021 阶段的历史现场），R1 阶段另有一次“1 项失败（C-11 未映射）”；本轮这些均已修正并在最终容器复核为 0 失败。
3. 本轮新增历史合法性核验后，原有测试中“仅 5 键的假历史 record”（C-82/C-83/C-85 的原夹具）会被该核验**先**拒绝；已按卡要求把这些夹具升级为**完整合法记录**（并新增 HP-01—HP-04 正向控制），因此第 12 步的语义重复判定仍可被独立观察到。
4. 一次核心实现自检过程中的真实内部 `KeyError`（运行绑定比较路径展开）曾被 `HumanGateDecisionError` 正确捕获并保留原因链——按卡如实登记，未伪装为协议拒绝。
5. **扫描后修正（流程偏离，如实披露，见 §7.2）**：首次全树扫描在 `task021r1_run_01` 完成后发现 `summary.json` 的检查计数（344）未包含终审阶段追加的 3 项检查、与 `checks.json`（347）不一致。修正为“审核结论写回 `checks/failures/summary` 后重建台账”，随后在**新容器** `task021r1_run_02` 重跑完整入口并**再次**执行全树保护扫描。这偏离“仅一次扫描”的纪律，故在此登记：`run_01` 的扫描结论**作废并保留**（不回写），本轮保护以 `run_02` 的扫描为最终结果；核心规则/协议/案例未因此改动。

---

## 7. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task021_gpt_20261013_195927/source_hashes_after.json`（`c972ad8c…f29`、133481 项、`verdict=NOT_ACCEPTED`），清单自身与同目录 `review_result.json` 按两个确切路径单列，**不豁免整个 reviews 目录**；不使用 TASK-020 旧基线。
- 执行者：本卡容器内 `scan_protection.py`（只读项目文件、只写本容器 `protection_result.json`），**仅一次**，在本轮核心/测试/指南/回执定稿且最终完整入口通过之后。
- 结果：见 §7.1（扫描数值在扫描后有限登记）。

### 7.1 扫描结果（有限登记）

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **133552** |
| `changed` | **仅 3 个本轮实际修改文件**：`scripts/build_demo_human_gate_decision.py`、`tests/test_build_demo_human_gate_decision.py`、`docs/HUMAN_GATE_DECISION_GUIDE.md`；**范围外变化 0** |
| `missing` / 读取错误 / 范围外新增 | **0 / 0 / 0** |
| 本轮允许新增 | **69** 项：`docs/EXEC_REPORT_021_R1.md` + `data/human_gate_decision_tests/task021r1_*` 五个容器（`dev_01`—`dev_03`、`run_01`、`run_02`）逐项登记 |
| 基线自身与同目录 `review_result.json` | 按**两个确切路径**单列，未豁免整个 reviews 目录 |
| 扫描后动作 | 仅对本回执做有限身份登记（本节数值与四个文件身份）；**未再修改核心/测试/指南**、未再重复全树扫描 |

### 7.2 扫描次数偏离（如实登记）

本轮执行了**两次**全树扫描：`task021r1_run_01` 的第一次扫描（133537 文件、changed 3、missing 0、读取错误 0、范围外新增 0、`ok=true`）在扫描后发现 `summary.json` 与 `checks.json` 的检查计数不一致（见 §6.5），遂修正测试、在 `task021r1_run_02` 重跑完整入口并执行**最终**扫描（§7.1）。第一次扫描结论**作废**、`run_01` 原样保留不回写；本轮保护以 §7.1 为准。偏离原因为“扫描后修正”，属流程纪律偏离而非静默重扫。

---

## 8. 未执行事项

receiver/checker 链、宿主/控制器接线、持久化/恢复/独占保存/失败现场文件协议、真实初判、AI/终判、TASK-002—020 历史业务链、旧评审脚本与旧容器脚本**均未运行**（`not_executed`/`null`）；未新增输入参数/输出字段/业务入口；未新增依赖、未初始化 Git；未创建批准/生效/运行配置或迁移脚本。

---

## 9. 绝对路径

- `D:\harness work\audit_sa_project\scripts\build_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\tests\test_build_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_021_R1.md`
- `D:\harness work\audit_sa_project\data\human_gate_decision_tests\task021r1_run_01\`

---

## 10. 停止点

完成本卡后执行端停止本轮实施并移交 GPT 验收；**通过后才制定 P2**。不接宿主/控制器，不生成真实 Gate/初判/`0009`，不开放 AI 或终判；人类业务决定与契约生效确认不重开，不以本卡内存结果放行任何批次。
