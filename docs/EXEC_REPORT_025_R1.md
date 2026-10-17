# TASK-025-R1 执行回执：补齐共享登记到 Gate1 保存的最小落地定义

日期：2026-10-15。任务卡：`docs/tasks/TASK-025-R1_DRAFT.md`（`9f2ee3e1adf3910f68b7eac78d570e8952fc2e6f5b4114cfb991f6d7ae6a71fc`）。
依据：`docs/reviews/REVIEW_TASK_025.md`（`25392548065a0c2bb666680ae3d4a0c7c89109eb496747a3f621d28051a58ab7`，**NOT_ACCEPTED**；三个总体方向已接受）。
分类：C 类（GPT 明确架构约束 + DSH 文档落地）。**只修两份正文，未实施代码、未新增测试框架、未重跑业务链。**

## 1. 起点核对（只读实读）

| 文件 | 要求 SHA-256 | 实读 | 一致 |
| --- | --- | --- | --- |
| `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md`（起点） | `342d2d75f7b3439bb4703496ed0b910409220f39ef4af2e21b2e7ba991c5123d`（29236） | 同 | ✅ |
| `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md`（起点） | `ee394833a680e350bad7e4cc1e8a56996c1db1d6441a122f2458202d15fd476a`（13454） | 同 | ✅ |
| TASK-024 最终测试 `tests/test_record_demo_human_gate1.py` | `fc38b82c694564bdc511573173d3d6ee9caf3aa7c421d7d95e4a0788cbdc87ff`（236681） | 同 | ✅ |
| Gate1 生产适配器 `scripts/record_demo_human_gate1.py` | `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9` | 同 | ✅ |
| 基线 `data/reviews/task025_gpt_20261015_011124/source_hashes_after.json` | `5772586319bd4087477ed768f2cf3c0adead3e1f858c19337f062cd052ef8657`（157255 项） | 同 | ✅ |
| `docs/reviews/REVIEW_TASK_025.md` | `25392548…8ab7` | 同 | ✅ |
| `docs/tasks/TASK-025-R1_DRAFT.md` | `9f2ee3e1…71fc` | 同 | ✅ |

## 2. B1 关闭依据：新运行绑定可以经**唯一**新入口交给冻结 P1/store

### 2.1 唯一接线（删除“旧接口或新版本任选”）

只读实读确认的结构性事实（写入设计 §5.1）：

- 旧适配器 `scripts/record_demo_human_gate1.py` 的 `_extend_request` 断言**恰 14 项代码 / 32 项材料**；
- 旧公开保存 `save_human_gate1_decision(batch_dir, request_id, submission, event_dir, *, scope_dir=None)`
  **自身重新真实准备**（内部再调 `_frozen_request` + `_extend_request`），**不接受调用方注入** registry/run_binding。

因此**新增运行组件后的扩展绑定无法经冻结旧入口保存**。设计改为**选定唯一接线**：

```
[候选] runtime_gate1.prepare_runtime_gate1_request(batch_dir, batch_id, request_id)
  → 实读登记 + 批次八文件 + 质量报告 + 复用冻结准备器的“来源核验返回”（不从 submission 取预期）
  → 新层独立实读构造 materials（冻结 P1 七键）/ expectations（冻结 P1 八键）/ code_manifest（14 项）
  → 返回封闭请求对象（§3.2(3)）
[候选] runtime_gate1.save_runtime_gate1_decision(request, submission, event_dir, *, scope_dir)
  → [已存在] build_demo_human_gate_decision.build_human_gate_decision_record(submission, materials, expectations)
  → [已存在] store_demo_human_gate_decision.save_human_gate_decision_snapshots(out_dir, submission, materials, expectations)
  → 独占写 context.json / receipt.json 并读回；全部消费后一次完整有界确认
```

旧 `TASK-024` 的 14/32 项入口**保持原样**（零字节改动），继续只服务其自身台账；禁止把扩展清单塞进旧入口、
禁止给旧记录换摘要、禁止复制旧批准作为新决定；**不改**冻结 P1/store/契约来迁就新接线。

### 2.2 删除登记人工时间

`registered_at_raw` 参数与人工作业**已删除**；登记对象改用 `registered_at`（**程序取当前时间**），
并明确“登记动作本身不是决定/批准”。决定时间仍由人类提交并**按原文保存**（`decided_at_raw` + `HUMAN_PROVIDED_RAW`）。

### 2.3 清单正文唯一结构（消除 `<原文>` 歧义）

- 新层 `code_manifest = {"entries": [{relative, file_sha256} × 14], "manifest_version": "TASK-025-code-manifest-1.0"}`，
  `rules_manifest = {"entries": [{rule_id, rule_version, relative, file_sha256} × 4], "version": "TASK-006-rule-core-1.1"}`；
  条目为**封闭键**、无 `byte_size`、按 `relative` UTF-8 字节升序且唯一；`manifest_version` 是**常量**，
  **不存在** null 分支或“字段可含可不含”。
- **历史事实（只读记录，不复用）**：旧实现实际正文为 `{"entries": …, "manifest_version": null}`，
  其指纹 `bb286a4938477e3a81bc5e034e2ca4de6cb8f07f47b1f7bff0579af5a7cec323`
  仅作为**旧算法历史取值**登记；新层不得把新值说成旧指纹，也不得用旧值校验新清单。
- **本批代码清单构成**：14 项 = 13 项 [已存在] `CODE_FILES` + 1 项**本批主执行单文件**
  （[候选] `scripts/runtime_gate1.py`，**当前不存在**）。第 14 项的 SHA **只能在其真实存在时实读取得**，
  本设计**不给出、不编造**。旧清单第 14 项是旧适配器（`d8ace42f…34d9`），故新旧指纹必然不同。

### 2.4 最小字段表（封闭键 / 严格类型 / 常量 / 来源 + 唯一摘要正文）

写入设计 §3.2 的五张表：

1. **候选入口签名（6 个）**：`build_runtime_registry` / `read_runtime_registry` /
   `prepare_runtime_gate1_request` / `save_runtime_gate1_decision` /
   `verify_gate1_effective_approval` / `prepare_gate2_materials_request`，每个都写明**实读来源**。
2. **登记对象 `registry` 13 键封闭**：`registry_version`（常量 `TASK-025-runtime-registry-1.0`）、`batch_id`、
   `registered_at`、`scope_ref`、`batch_files`（恰 8 项 3 键）、`code_manifest`、`rules_manifest`、`config`、
   `input`、`contract`（`contract_file_sha256 = 174a021b…40ad`、`contract_effective = true` 逐字符等于冻结登记）、
   `run_binding`、`run_binding_sha256`、`note`（常量）。
3. **Gate1 请求封闭键**：新版本常量 `TASK-025-human-gate1-runtime-request-1.0` /
   `RUNTIME_GATE1_REQUEST_PREPARED`；`materials` 引用冻结 P1 七键 `MATERIALS_KEYS`、
   `expectations` 引用冻结 P1 八键 `EXPECTATIONS_KEYS`（避免重复整套规则）。
4. **Gate2 请求封闭键**：同构，`TASK-025-human-gate2-runtime-request-1.0` /
   `RUNTIME_GATE2_REQUEST_PREPARED`；`materials.files` 为 §8 白名单材料集，计数与摘要可与 Gate1 不同，
   `run_binding` 六项与 Gate1 **整体 canonical 相等**。
5. **有效 Gate1 核验返回 11 键封闭**：`verification_version`、`batch_id`、`event_relative`、
   `record_fingerprint`、`record_file_sha256`、`run_binding_sha256`、`materials_fingerprint`、`decision`、
   `actor_kind`（常量 `HUMAN_DECLARED`）、`effective`、`reasons`。

**唯一摘要正文**：`fingerprint(x) = sha256(canonical_json(x))`；`registry_sha256` 放**外层返回**，
**登记文件本身不写自身的文件 SHA-256**（因此不存在需排除的自指键）；文件 SHA-256 与对象规范指纹**两类分列**。

### 2.5 实读入口有据可取

每个候选 API 都写明**接收哪个路径/读取哪些固定文件**：
登记文件按 `data/runtime/<batch_id>/runtime_registry.json` 定位；
有效批准核验接收 `registry_path` + `scope_dir` + `event_relative`，**实读**该事件目录的快照与上下文/回执
（不只信调用方内存）；Gate2 准备接收登记路径、标准化产物相对路径、装载报告相对路径，
并**实读数据库文件本身**与报告核对（§8 实读要求）。

### 2.6 停止点与三类目录角色一致

- §1 明确区分：**本卡不产生任何产物**（不写登记/决定/数据库/profile）；**阶段一必须产生**运行登记与
  Gate1 决定记录；**禁止的是 Gate2 决定保存与筛查运行**。
- §6 分列三类角色：**角色一 运行输出目录** `data/runtime/<batch_id>/`（登记、标准化产物、装载报告、
  Gate2 请求、失败诊断）；**角色二 独立 Gate1 记录根** `data/human_gate_decision_records/gate1/<scope>/<event>/`
  （[已存在] 冻结布局，只增不改，新层只写新 scope/新事件）；**角色三 SQLite 独立子目录**
  `data/sqlite_tests/runtime_<batch_id>/`（仍在 [已存在] 核心允许根之内，不扩大权限）。
- 明确“普通业务 ID 不直接作为任意文件路径”，事件目录叶名与 `event_id` 字段解耦。

## 3. B2 关闭依据：正向基样改用已登记人类字段，并给完整可核对对象

- **人类字段改为已登记夹具**（案例集 §0.1）：

| 夹具 | 决定 | 路径 | 文件 SHA-256 | 字节 |
| --- | --- | --- | --- | --- |
| `FIXTURE-EV-G1-0001` | APPROVE | `docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`（§0.2 `record1` 块） | `bd1fc37dc2437454b87b5453d7df90a6dcd6f3f79e84c3e75a335381fcf2d2a6` | 43060 |
| `FIXTURE-EV-G1-0002` | HOLD | `data/human_gate1_decision_tests/task024_dev_01/fixtures/TASK024_G1_HOLD_0002.json` | `8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa` | 927 |
| `FIXTURE-EV-G1-0003` | REJECT | `data/reviews/task024_gpt_20261014_050915/registered_fixture_0003.json` | `6c69c75cde41014fd8740b95d58b9e8a805bd30003fb14ac6f8fb40c93cf23c3` | 709 |

  三份夹具的 `actor_kind` **逐字符为 `HUMAN_DECLARED`**（冻结 P1 `ACTOR_KIND_HUMAN`）；
  时间 `2026-10-13T18:00:00+08:00`、原因原文与 `actor` 对象均按其原文引用。
  **已删除**首轮的 `actor_kind = HUMAN`、自造时间 `2026-10-15T00:00:00+00:00` 与自造原因文本；
  外层 `PROTOCOL_TEST_FIXTURE_ONLY` 仍只放在测试证据层，**不写进 P1 封闭提交**。
- **完整正向书面基样**（案例集 §0.3）：① `run_binding` 六项 → ② Gate1 `materials`（冻结七键、`files` 恰 32 项）
  → ③ Gate1 人类提交片段（逐字符取自 0001）→ ④ Gate2 `materials`（白名单集，`run_binding` 与 ① 同一个对象）。
- **唯一摘要配方与推导顺序**（案例集 §0.4）：`fingerprint` / `sha256_file` / `code_manifest_fingerprint` /
  `rules_manifest_fingerprint` / `run_binding_sha256` / `materials_fingerprint` / `registry_sha256`，
  并按“①文件字节 → ②逐项 SHA 与列表 → ③清单 → ④run_binding → ⑤materials → ⑥材料指纹 → ⑦expectations
  → ⑧记录 → ⑨记录指纹”的顺序，任一步改动必须回到该步重算下游。
  由此 `normal` 与“**六项相等、材料摘要不同**”的对照可直接复算核对。
- **案例 3a 分层修正**：Gate/有效批准核验已阻断时，**标准化入口调用次数 = 0（未调用）**；
  冻结核心自身的 `NormalizationBlocked` 单列为**另一层级**的书面预期（3a′），不再同时声称“先阻断”又“已调用下游”。
- 十类案例数量与范围未增加；其余案例改为引用 §0.3 基样，不再以文字“均合法”代替；案例 6 增加
  `HUMAN` vs `HUMAN_DECLARED` 的唯一枚举拒绝维度（含首轮缺陷的登记说明）。

## 4. 针对性只读核验（36 项全部通过）

脚本：`data/human_gate_runtime_design_checks/task025r1_run_01/runtime_design_checks_r1.py`（只读；读文件 + AST/文本核对 + 书面夹具复算；
**未导入任何业务模块、未调用任何业务函数、未创建任何产物**）。
记录：同目录 `design_checks_r1.json`、`frozen_identity_r1.json`；`passed=true`、`failures=[]`。

覆盖：唯一接线与旧入口边界（5 项）、摘要正文唯一与无占位（含配方可复算，4 项）、字段闭合（登记 13 键 / 核验返回 11 键 / 请求引用冻结七键八键 / 计数声明，4 项）、冻结接口数量限制实读（`!= 14`/`!= 32`、旧保存自身重新准备、`CODE_FILES` 13 项，3 项）、三类目录角色与停止点表述（4 项）、合法已登记人类字段（夹具文件身份 3/3、路径与 SHA 写入正文、`HUMAN_DECLARED` 唯一、冻结常量实读、禁用措辞、时间/原因原文，6 项）、案例 3a 分层与完整基样（5 项）、阶段/目录一致与未执行声明（4 项）。

## 5. 分清五类陈述

- **设计建议（[候选]）**：`runtime_gate1`、`runtime_registry`、`gate1_effective_approval`、
  `gate2_materials_request`、`RT_*` 状态、运行登记与运行目录；全部标注**当前不存在**。
- **已冻结现状（[已存在]，本轮零改动）**：Gate1 旧适配器与冻结准备器、冻结 P1 纯内存核心与快照保存/store、
  正式契约、冻结配置与规则、标准化/SQLite/checker/接收器/跨核/筛查/事实底稿/初判核心、开发态流程控制与 `0001—0008`。
- **书面计算（仅夹具与配方）**：§0.2 的技术夹具常量、§0.4 的摘要配方与推导顺序，以及脚本内对
  一份示例 `code_manifest` 的配方复算（脚本与记录在证据根）。
- **真实执行（本轮实际发生）**：只读读取、AST/文本核对、SHA-256 实读复核（三份夹具、冻结身份）、
  36 项针对性核验，以及两份正文的定点修改与本回执/证据根写入。
- **未执行**：未调用 `normalize_workbook` / `load_normalized_to_sqlite` / `check_dev_action` /
  `prepare_human_gate1_decision_request` / 任何 P1 或 store 接口；未创建运行登记、批准凭证、接收批次、
  决定记录、数据库、运行 profile 或宿主检查点；未安装依赖、未初始化 Git、未运行历史入口或计算核心；
  未重跑首轮 25 项自检脚本（其默认会覆盖旧结果），只读引用其记录；未制定 TASK-026。

## 6. 交付物与最终哈希

**本次修改（恰两份允许正文）**：

| 路径 | 起点 | 最终 |
| --- | --- | --- |
| `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md` | `342d2d75…123d`（29236） | `284d0a5233ef8704c8b973598ea80bef8b7563fb7abdfe2646fe3e9352d357be`（45697） |
| `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md` | `ee394833…476a`（13454） | `b0b5da9448c1fabde5e9035bc7ae7028fbbcc1463b7b76510477bf95983ef3fd`（22755） |

**本次新增**：

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `data/human_gate_runtime_design_checks/task025r1_run_01/runtime_design_checks_r1.py` | 16546 | `a38396cc024bf568583e1a5b469a75681e62961522b8d2824d18095704d3246d` |
| 同目录 `design_checks_r1.json` | 7174 | `c3e1c2918dabd7a767f4c544d3bd3ffcb30eb4f3fe5347ab679bdb0c02b41750` |
| 同目录 `frozen_identity_r1.json` | 1976 | `17091001b3a364a543cfc2b90c83e46693af5ba3130beee8dbae41f3c4a99b15` |
| 同目录 `protection_scan_025r1.py` | 7288 | `f41ce39c2d7170915b787df98e0df8c69688cc603ed726274598e40b32c51272` |
| 同目录 `protection_scan_025r1.json` | 5079 | `dc056c99e939b0e1f957d0411df98747db0e05cb70573e1001cecf7e3a20f5fe` |
| `docs/EXEC_REPORT_025_R1.md`（本回执） | 15893 | 最终 SHA 见交接消息（避免自指） |

## 7. 保护与历史留证

- 最终一次全树扫描（`protection_scan_025r1.py` / `protection_scan_025r1.json`，`dc056c99…f5fe`）：基线为
  `data/reviews/task025_gpt_20261015_011124/source_hashes_after.json`（157255 项，实读 157258 项）；
  实读结果 `changed = 2`，恰为两份允许正文（`docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md`、
  `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md`）；`missing = 0`、`read_errors = 0`、
  `out_of_scope_changed = 0`、`out_of_scope_added = 0`；`added = 5` **全部为新增文件**，逐项落在本卡明示范围
  （`docs/EXEC_REPORT_025_R1.md` 与证据根 4 文件 `runtime_design_checks_r1.py`、`design_checks_r1.json`、
  `frozen_identity_r1.json`、`protection_scan_025r1.py`）；两份被修改正文只出现在 `changed` 中，未重复登记为新增；
  R5 越界 326 项逐项不变；`scope_compliant = true`。
- R5 越界 37 目录/326 文件继续固定留证、不追认、不动；`data/reviews/task025_gpt_20261015_011124/`
  下两个自指元数据按确切路径单列，未改写。
- 未回写旧回执、旧自检记录与旧扫描结果；首轮辅助身份差异（15626/`ec829861…` 与 15911/`f0280371…`）
  按评审结论**只在必要时于本回执说明**，不追溯改写旧文件。

## 8. 边界与待裁决

- 真实批准仍 `null`，宿主仍开发态 `0008`，`next_step_allowed=false`，AI 未开放；技术验收不批准任何批次。
- 待 GPT 裁决：① 新版本 `runtime_gate1` 唯一接线与旧入口零改动边界；② §3.2 封闭键表与
  `manifest_version` 常量化 + 旧 `null` 指纹仅作历史记录；③ B2 的已登记夹具引用与 §0.3/§0.4 完整基样。
- 若后续发现必须改变冻结 P1/契约/业务规则或需要人类新业务决定，将停止受影响设计并升级，
  不以扩大本卡范围继续实现。完成本卡后停止交 GPT，不自行制定或实施 TASK-026。
