# TASK-020-R2 执行回执（合法夹具与派生摘要、缺参数约定与前序 run_binding、Gate2 材料时序）

任务：按唯一权威细则 `docs/tasks/TASK-020-R2.md` 修正剩余三组问题（B1 剩余/B2 剩余/B5）。依据 `docs/reviews/REVIEW_TASK_020_R1.md`。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：两份正文已修正；独立书面核验与**一次**最终完整保护扫描结果见 §6。

**硬边界重申**：本卡**仅修文档**——未实现或调用任何拟定 API、未定义 validator/公开入口、未运行本卡任何案例或注入、未运行 R1 旧夹具或旧自检、未导入或运行宿主/控制器/上游核心/业务链（控制器仅以**文本方式只读**）、**未新增或修改 `scripts/`、`tests/` 下任何文件**、未生成真实提交/Gate 记录/真实初判/`0009` 或审阅包、**未提前运行规则筛查、未修改冻结控制器/宿主、未改变两处 Gate 业务顺序**。B3/B4 保持关闭、未重做。正式契约 V1 与 D1/D2/D3 继续有效，未重新征求、未修改人类决定或正式文件。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 说明 | SHA-256 |
| --- | --- | --- |
| `docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md` | 协议（R2 修正版） | `68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`（39298 字节） |
| `docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md` | 案例（R2 修正版） | `fec74c9148c69ee8d4066c82eee167a93963412ad099a5b1b6982cea67da3c64`（39118 字节） |
| `docs\EXEC_REPORT_020_R2.md` | 本回执 | 自身 SHA 只在交接消息给出（不写回自身） |
| `data\decision_protocol_checks\task020r2_run_01\`（新证据根） | `fixtures_r2.py`、`fixture_values.json`、`verify_r2.py`、`checks.json`、`summary.json`、`protection_result.json`、`case_index.json`、`fixture_doc_audit.json`、`dependency_order.json` | 见 `summary.json` |

上表两份正文的 SHA 在**最终完整保护扫描前后实读一致**（扫描本身不修改文件；登记动作只修改本回执、未再改动两份正文）；证据根 `summary.json` 的 `document_hashes` 是登记之前产生的快照。保护数值见 §6。

**只读外部输入核对（未修改）**：正式契约 `docs/AUDIT_CONTRACT.md` = `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`、13289 字节；其头部生效时间原文未改、未规范化，也未作为本协议正向时间输入。**R1 旧夹具与其 JSON/自检记录未修改、未重跑**（本轮仅读取 `task020r1_run_01/fixture_values.json` 作对照）。

---

## 2. B5（先修）：Gate2 材料只能依赖批准前产物

- **协议 §7.2**：两处 Gate 的纯对象完整性改为——Gate1＝输入快照与接收核验结果（`receive/quality_report.json`、`receive/snapshot.xlsx`）；**Gate2＝批准前即可取得的标准化产物、入库数据库与装载/质量/勾稽核验报告**（`load/load_report.json`、`normalized/normalized.json`、`sqlite/audit.sqlite3`）。并写入："**规则筛查报告不是 Gate2 的必需材料**：按正式契约 §3.2 与冻结流程，Gate2 位于标准化/入库完成之后、规则筛查之前——若要求先有筛查报告才能批准 Gate2，会形成'未批准不能筛查、未筛查不能批准'的依赖环"。
- **协议 §9.1**：Gate2 行同步（并注明"**不含规则筛查报告**——筛查在 Gate2 决定之后进行"）。
- **BASE2 夹具**：`files` 改为 `load/load_report.json`＋`normalized/normalized.json`＋`sqlite/audit.sqlite3`（升序），筛查产物已移除；材料正文与派生摘要**重新推导**：`materials_fingerprint = ce95ec25578e026b61a269871575a049b432443786ec5280bcafa725e7bcc45e`（既非旧 `74e6f14e…`，也非仅排序后的过渡值）。
- **先后依赖核对**（新证据根 `dependency_order.json`，**只读来源、未运行链**）：顺序为 **Gate1 决定 → 标准化/入库 → Gate2 决定 → 规则筛查**；只读证据：冻结 `control_demo_workflow.py` 第 879 行 `ACTION_NORMALIZE` 需 `PHASE_G1_APPROVED`、第 883 行 `ACTION_SCREEN` 需 `PHASE_G2_APPROVED`；正式契约 §3.2 的标准化/入库后暂停口径；结论：**Gate2 每种必需材料均在其决定之前可得**。
- 未新增替代门禁、未提前筛查、未改冻结控制器/宿主、未调整两处 Gate 业务顺序。

---

## 3. B1 剩余：先构造协议合法对象，再算摘要

- **构造顺序**：夹具在**构造阶段**即把 `files` 写成按 `relative` 的 UTF-8 字节序**严格升序、唯一**的列表，然后计算摘要；**拟定核心仍拒绝无序输入、不为调用方静默排序**（协议 §3.5/§4.1 未放松）。
- **BASE1**：`files` 顺序为 `receive/quality_report.json` → `receive/snapshot.xlsx`（`files[0]`＝quality_report，`files[1]`＝snapshot）。展开后正文复算值 **`5f0299e17f46f90f2893884d52eb2c2dd6131b7fe6c33350ae9dc38af8e3f739`**——与验收端独立展开所得一致，**取代**旧稿 `5d92459c…`（旧值对应未排序正文）。
- **record1**：`note` **逐字符等于**协议 §14 常量"内存校验通过；不表示已保存、已放行或已产生真实人类判断。"，**未追加**"设计夹具，无审批效力。"；夹具标识只放在本文档与证据根、以及人类提供的 `reason`/`declaration_note` 字段。`materials_files` 采用合法升序、`materials_fingerprint` 用 **BASE1 新值**；复算后 `record1` 外层指纹＝`15bebb4834702ce970d54a1ce5b5545065480ece13b4b5c64de48c5c1a148c19`（**记录键数 17**，与协议 §14 一致）。
- **BASE2 前序同步**：提交 wrapper、历史 wrapper、独立 `expected_prior_gate1`（含新增字段 `run_binding`）全部采用**新的完整 record1 与指纹**（`15bebb48…8c19`）。
- **C-08 与单点错批次分离**：C-08 保持**正向**（三处批次标识同步为 `"a"×64`，摘要重算为 `65e583582f5abc0838dcf0cd6fb040aa687bd1c61b5b1a90aaa91de26a449f45`，预期成功）；原与 C-08 混用的"单点错批次"改为**独立编号 C-117**（仅 `materials.batch_id` → `FIXTURE-BATCH-B`，摘要同步为 `8a6ee4e1004760c8ca147c7074d99af054a8539c19f1461c4198b98abaeaab60`，提交/预期仍 `FIXTURE-BATCH-A`，第 5 步拒绝）。
- **`files[0]` 标注修正**：全文按逻辑 `relative` 定位变更目标；涉及索引处一律写明"按合法升序列表＝`files[1]` 为 `receive/snapshot.xlsx`"（C-52/C-53/C-54/C-98），不再把 `files[0]` 标成 snapshot。
- **其他同步值**：C-50 `a`×64（故意不符）；C-52/C-53 `ced6a9b31cadd276826763e00fce6b2e1875afa59de6550eb1e7f931bbaafe62`；C-57 `86a39a3e732c533059ea37a199106bbe2a0902a0808ee2fa4393efc4793514d0`；C-58 `6331516b888a0039dc0efd63e7ce292ed1d21026ae2227d3f889842edec03cc2`；C-89 `d70fb4e5442d9f225592b45ccf3640b8a836e1d40c5634b6055ced70c7c7d7f0`；C-90/C-91 `10a234aff694d92dc0d8dc53d3ff5b332e6b0c215dce8da0d74f4b6ccc0b2d0b`；C-93 `f83d319095b60a0521b47896109e23db5300d8c10fdd6b48782d66626a9bb61d`。
- **独立书面核验**（新根 `verify_r2.py`，**不依赖夹具构造器**）：直接从案例正文抽取 3 个 JSON 块 → 按正文声明的缩写规则（`"x…x"` ＝ 该字符×64）展开 → 检查 `files` 升序/唯一/成员键/哈希格式/`byte_size` 类型范围 → 用标准库按唯一公式**重算** BASE1/BASE2 材料摘要与 record1 记录摘要并与正文标称值比对 → 再把 `fixture_values.json` 作为**第二来源**交叉比对（`fixture_doc_audit.json` 记录被计算对象来源、列表顺序、常量比较与摘要关系）。三处复算值与标称值全部一致。

---

## 4. B2 剩余：缺参数约定与前序运行绑定

### 4.1 缺参数的统一方案

签名固定为 `..., *, prior_history: dict | None = None`，并在 §2.1、§3.4、§10 统一声明：**语义上必填**——**缺省省略**与**显式传 `None`** 两种情形都在**第 4 步（history 检查步）**以 `HumanGateDecisionBlocked(field="prior_history", reason="历史完整性声明缺失")` 拒绝；**不默认空历史、不默认 `declared_complete=true`**。这样避免了 Python 在进入函数体前抛原生 `TypeError` 与"可定位的结构化拒绝"相互矛盾。案例 **C-36** 同步改写（同时覆盖"省略"与"显式 None"），回执不再出现"无默认值必需关键字"的表述。本次只改文档，未定义或调用函数。

### 4.2 前序 Gate1 运行绑定逐字段严格相等（新 §9.3 第 11f 项）

`prior.record.binding.run_binding` 必须与**本次** `materials.run_binding` **及** `expectations.expected_run_binding` **逐字段严格相等**：`code.file_sha256`、`code.manifest_fingerprint`、`rules.version`、`rules.manifest_fingerprint`、`config.file_sha256`、`input.file_sha256` 六项全等且嵌套键集合一致；任一不同即在前序检查拒绝（`field = submission.prior_decision_binding.record.binding.run_binding.<字段路径>`）。`expectations.expected_prior_gate1` 增加 `run_binding` 字段作为**独立预期**来源。协议同时明确：运行绑定指本批代码/规则/配置/输入版本；**Gate1 与 Gate2 的材料集不同，故两者 `materials_fingerprint` 不要求相等**——要求相等的是运行绑定。

**最小隔离反例（新增 C-112—C-116）**：分别**仅**变更前序记录的代码/规则/配置/输入绑定；该前序记录及其祖先摘要（记录正文、wrapper 外层指纹、提交 wrapper、历史、独立前序预期）**全部正确复算并同步**；**当前材料与当前独立 `run_binding` 保持不变的**同时在前序运行绑定处拒绝，唯一字段/步骤如下：

| 新例 | 仅变前序 | 复算后前序记录指纹 | 唯一字段（步） |
| --- | --- | --- | --- |
| C-112 | `code.file_sha256` → `"7"×64` | `c64fbba003f9c2f82f6b640d1d9d1edfa808460062683e6cda730560e6c18657` | `…run_binding.code.file_sha256`（11f） |
| C-113 | `rules.manifest_fingerprint` → `"8"×64` | `66ac12a5baa85356abc5c302849c9c197618f2fa6493a7610594099691426cbb` | `…run_binding.rules.manifest_fingerprint`（11f） |
| C-114 | `config.file_sha256` → `"9"×64` | `35a9697cd20a5cbf45dbc710d5c5877a6195880f4fb9b59e497e3a66f9e2f4c5` | `…run_binding.config.file_sha256`（11f） |
| C-115 | `input.file_sha256` → `"0"×64` | `9c5e799b6216b4836192f0b5663aeb3d83b347a3a963f3055dcf4ae438d690e8` | `…run_binding.input.file_sha256`（11f） |
| C-116 | 无（同版本对照） | 前序即 `record1`：`15bebb48…8c19` | **成功**（11f 通过） |

由于指纹与所有祖先关系都已同步，11a—11e 与 11g—11i 全部通过，**拒绝只能来自 11f**，不能用"未同步摘要提前拒绝"冒充该检查。

---

## 5. 定点步骤口径与案例迁移

- **两个范围写清**（协议 §5）：第 **1—4 步**只做**形状/类型/常量/键集合/列表规则**（含按 Gate 判定的前序字段形状）；第 **5—12 步**做**值/关系**；第 13 步质量/决定矩阵；第 14 步构建。并在 §5 顺序说明中写清：**时间字段类型错误在第 1 步**；**`contract_effective` 的类型与 `true` 常量在第 2 步**、与独立契约预期的**值比较在第 7 步**；`records` 的**唯一/升序在第 4 步**、与提交或既有批准的语义重复在第 12 步；前序记录内部常量/枚举/`note`/质量/运行绑定**一律在第 11 步**（11a—11i 子序）。
- **定点修正的案例**：C-48 → **第 1 步**（类型）；C-63 → **第 2 步**（常量类型/值）；C-84 → **第 4 步**（名单唯一性）；C-69 → **第 3 步**（按 Gate 的形状规则，去掉 3/11 双口径）；C-79 → **第 11i 步**（去掉 11/12 双口径）；C-67/C-68 → **第 1 步**（按 Gate 形状规则）。
- **案例编号与迁移**：本版 **117 个唯一连续编号 C-01—C-117**（无字母后缀）；新增 C-112—C-116（前序运行绑定四反例＋同版本对照）、C-117（材料侧单点错批次）；§10 给出与 TASK-020／R1 版的逐段对应与迁移理由。脚本核对：唯一性、连续性（1..117 无缺口）、无后缀、与正文声明计数一致（`case_index.json`）。未受影响的 B3/B4 案例未重做。

---

## 6. 只读核验与保护

本轮核验＝人工逐条对照 + 只读链接/引用/计数 + **标准库 JSON/摘要书面核算**；未实现或调用拟定 API，未运行旧夹具/旧自检/上游/控制器/宿主/业务链。

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| `doc_objects_recomputed_independently` | PASS | 从**正文**抽块并展开后复算：BASE1 `5f0299e1…f739`、BASE2 `ce95ec25…c45e`、record1 `15bebb48…8c19`，与标称值一致 |
| `record1_constants_and_keys` | PASS | 键数 17；`note` 逐字符等于协议常量；`boundaries` 六项严格 `false`；`execution_allowed is False`；计数严格整数 0；`materials_files` 升序；材料指纹＝BASE1 新值 |
| `b5_gate2_materials_pre_approval` | PASS | BASE2 材料无筛查产物；控制器 `ACTION_SCREEN` 需 `PHASE_G2_APPROVED`；协议写明筛查报告不是 Gate2 必需材料与依赖环理由 |
| `b2_signature_and_prior_run_binding` | PASS | 签名 `prior_history: dict \| None = None`；"语义上必填"与第 4 步结构化拒绝；§9.3 含 11f；`expected_prior_gate1` 含 `run_binding`；C-112—C-117 齐备 |
| `step_scope_fixes` | PASS | C-48/C-63/C-84/C-69/C-79/C-67 的唯一最早步骤与两个范围一致 |
| `case_numbering_unique_sequential` | PASS | 117 个唯一连续编号、无后缀、与声明一致 |
| `constructor_vs_document_cross_check` | PASS | 构造器产物与正文展开复算三者一致（非同源自比） |
| `no_affirmative_completion_claims` | PASS | "已实现/测试 PASS/已获批准/P1 可以启动/已验证通过"仅在否定语境 |
| `references_and_links` | PASS | 11 项引用分层登记（含本轮评审、旧夹具作"读取的旧证据"）；正文链接全部可解析 |
| `external_contract_input` | PASS | 正式契约实读 SHA 与 13289 字节匹配登记 |
| `frozen_and_forbidden` | PASS | 宿主/控制器/初判核心与 R1 旧夹具、R1 回执身份一致；无禁止文件 |
| `protection_scan_once` | PASS | 见下 |

**保护比较**（基线 `data/reviews/task020_r1_gpt_20261013_183029/source_hashes_after.json`，身份见同目录 `review_result.json`）：

- 局部内容与夹具核对（含上述失败修正）**全部通过后**，才执行**一次最终完整扫描**（两份正文与本回执齐备）：基线 `source_hashes_after.json`（SHA `4392a678372c179cef52b0ce817fec6901519d79152371a984a9dce89af2153a`、**133344** 项，同目录 `review_result.json` 记 `verdict=NOT_ACCEPTED`）→ 实扫 **133355** 文件；`changed` **恰为两份允许文档**（协议 `68c931b3…3e76`、案例 `fec74c91…3c64`）、`missing=[]`、读取错误 **0**、**范围外新增 0**。
- 新增产物分列：**本轮允许新增 9 项**（本回执 + 证据根 8 个文件）；**旧评审元数据**按**两个确切路径**单列（`source_hashes_after.json`、`review_result.json`）；**外部输入**按确切路径核对（正式契约 `174a021b…40ad`、生效登记 `042086cb…`、D1/D2/D3 纪要 `bface683…`、本卡 `5ace4389…`、R1 评审 `f73914fe…`，逐项身份记于 `protection_result.json` 的 `external_inputs_verified`）。**未用整个 reviews 前缀豁免未知文件**（按确切路径分类）。
- 扫描后只做**有限身份登记**（把两份正文写后 SHA 与本节数值补入本回执），未再全树扫描。

---

## 7. 过程问题、未解决项与未执行动作

**过程问题（如实记录）**

1. **R1 的两次扫描偏差**（定稿前一次 + 最终一次）已在 R1 回执披露并被验收端登记为**非阻断过程偏差**；本卡改为"**先局部核对、最后一次全树扫描**"：夹具与正文对象的复算、案例编号、定点步骤口径全部在**本地**完成并修正后，才做最终扫描。本卡不重做历史回归、不清理旧现场。
2. R1 的根因是"**先算摘要、后写对象**"：正文与证据的 `files` 顺序不同，且 `note` 被追加了夹具说明。本卡改为"**先构造合法对象、再算摘要**"，并让核验脚本**从正文抽块复算**（不依赖构造器），避免"同一错误构造器两次得到同一值即填 PASS"。
3. **辅助计数更正**：R1 回执称 record 键数 15，实际协议 §14 为 **17 键**；本回执按 17 统一（只在新回执更正，未回写旧文件）。
4. 上一轮"40 项维度与 summary 实计不一致"的同类问题已不再出现：本轮计数以 `case_index.json` 落盘为准。
5. **局部核对阶段发现并定点修正的两处问题（均未触发全树扫描）**：① 案例 §0.1 原先把缩写规则写成"`x…x`（单字符）"，与正文实际使用的 `aaa…a`（左侧三次重复）**不一致**——已把规则改为"省略号两侧为同一小写十六进制字符、左侧重复 1—3 次"，并同步核验脚本的展开判定；② 核验脚本自身的 B5 控制器取证与 §3.3 行匹配原先依赖过窄的字符串假设，已改为按 `elif action == ACTION_SCREEN:` 后三行窗口取证、按表格行前缀匹配。两处都在**局部**核对（`--no-scan`）中修正并复算通过后，才执行那一次最终全树扫描。

**未解决项**：无（本卡范围内）。协议未决项仍为 U1—U4（持久化/恢复；控制器与宿主接线及批准字段、材料实际枚举与磁盘读取；真实初判结构 P3；AI/终判另行范围）。

**未执行动作（not_executed，不填 PASS 或默认零调用）**：未实现或调用任何拟定 API、未定义 validator/公开入口；未运行本卡任何案例、未实施注入、未运行 R1 旧夹具或旧自检；未导入或运行宿主/控制器/上游核心/业务链（控制器仅文本只读）；未新增或修改 `scripts/`、`tests/` 下任何文件；未生成真实提交/Gate 记录/真实初判/`0009` 或审阅包；未提前运行规则筛查、未修改冻结控制器/宿主、未改变两处 Gate 业务顺序；未执行持久化/恢复/放行；未开放 AI/终判。

---

## 8. 绝对路径

- `D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`
- `D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_020_R2.md`
- `D:\harness work\audit_sa_project\data\decision_protocol_checks\task020r2_run_01\`
- 只读外部输入：`D:\harness work\audit_sa_project\docs\AUDIT_CONTRACT.md`（人类正式契约 V1，未修改）

---

## 9. 停止点

本卡只做文档修正：不实现、不运行核心、不生成真实 Gate/初判或 `0009`、不开放 AI/终判。修正版通过后再制定 P1 纯核心实施卡（先核验主理人正式 V1 文件与明确生效确认）；正式契约、协议与实际代码**各自独立绑定**，本卡与 D2 纪要**均不构成任何批次的 Gate 批准**。人类继续作出每一批次的决定与初判；DSH 由人类操作。
