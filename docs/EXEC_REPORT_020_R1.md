# TASK-020-R1 执行回执（闭合 Gate 协议与案例，四组文档阻断）

任务：按唯一权威细则 `docs/tasks/TASK-020-R1.md` 修正两份拟定正文的四组问题（B1—B4）。依据 `docs/reviews/REVIEW_TASK_020.md`。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：两份正文已修正；只读核验与**一次**完整保护扫描结果见 §6。

**硬边界重申**：本卡**只修文档，未写任何实现代码**；未实现或调用任何拟定 API、未运行本卡任何案例或注入、未导入运行宿主/控制器/上游核心/旧核心/旧自检/业务链、**未新增或修改 `scripts/`、`tests/` 下任何文件**、未生成真实 Gate 记录/真实初判/`0009`、未新建批次或 SQLite。修正后两份正文仍为 `PROTOCOL_DESIGN_DRAFT_NOT_IMPLEMENTED` 与 `PROTOCOL_CASE_DESIGN_NOT_EXECUTED`。正式契约 V1、D1/D2/D3 继续有效，本卡未重新征求、未修改任何人类决定或正式文件。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 说明 | SHA-256 |
| --- | --- | --- |
| `docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md` | 协议（R1 修正版） | `cdc9dbf608843816ed38b81c4bdfab06262d30927e30c980fecf9c532e8b0bcc`（33805 字节） |
| `docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md` | 案例（R1 修正版） | `a520219fc45a1b8e96d7a58a287bd8d2c34df616390c8870cb89c357579728b1`（30916 字节） |
| `docs\EXEC_REPORT_020_R1.md` | 本回执 | 自身 SHA 只在交接消息给出（不写回自身） |
| `data\decision_protocol_checks\task020r1_run_01\`（新证据根） | `fixtures.py`、`fixture_values.json`、`selfcheck_020r1.py`、`checks.json`、`summary.json`、`protection_result.json`、`case_index.json` | 见 `summary.json` |

上表两份正文的 SHA 为**保护扫描之后**实读所得（有限身份登记），未改动正文；证据根内 `summary.json` 的 `document_hashes` 是登记之前产生的快照。

**外部输入只读核对（未修改）**：正式契约 `docs/AUDIT_CONTRACT.md` = `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`、13289 字节（与生效登记一致）；正式契约头部生效时间原文**未被修改、未规范化**，也**未**被当作本协议的正向时间输入。旧自检 `task020_run_01/selfcheck_020.py` 与其输出**冻结未重跑**（本轮仅读取其 `summary.json` 作为旧证据）。

---

## 2. B1：唯一材料计算正文与可推导夹具

### 2.1 唯一材料正文（协议 §4.1）

```text
materials_body := materials 对象中，仅删除【顶层】键 materials_fingerprint 之后的其余内容
                   （其余顶层键、所有嵌套对象与所有列表的成员与顺序原样保留）
materials.materials_fingerprint == fingerprint(materials_body)
fingerprint(x) := sha256(canonical_json(x)).hexdigest()
canonical_json := UTF-8 / ensure_ascii=False / sort_keys=True / separators=(",",":") / allow_nan=False
```

- **参与字段**逐项列出：`gate`、`batch_id`、`run_binding`（含四组嵌套）、`contract_binding`、`files`（每成员三字段）、`quality`（含状态与三个列表及顺序）。
- **列表顺序**：`files` 必须按 `relative` 升序（严格递增、唯一）方可参与正文；三个阻塞/失败列表按原文升序且唯一；**不做其他规范化**（不置空、不删除其它字段、不改键名）。
- **禁止**：对包含 `materials_fingerprint` 自身的整对象求摘要；把"置空/删除/任选排序"等选择留给实施端。§4.1 明确标注这是**唯一**允许的算法。

### 2.2 唯一相等关系（协议 §4.2）

```text
fingerprint(materials_body) == materials.materials_fingerprint
                            == submission.request_binding.materials_binding
                            == expectations.expected_materials_fingerprint
```

四者字符串精确相等；**内部文件字节 SHA 仍逐项**与独立名单 `expected_files` 比较（协议 §7.2），两类值**不互相替代**。

### 2.3 可推导夹具（协议 §0 与案例 §0）

- BASE1 材料正文复算值：`materials_fingerprint = 5d92459cfe7bd257e21cc2937180da8de508eeb6a2ee6d9bae3e98186c7bdbc3`；BASE2：`74e6f14ee68db56a99834ce1e37376a5f2f18d0190400a78d9387f12f770e0e2`；BASE1 记录外层指纹：`be7221df8f3eabcaa7b3663a5b0440b379badb430c535373093c6c5b4e4d22a9`。
- 三处摘要同步写入（`materials.materials_fingerprint`、`submission.request_binding.materials_binding`、`expectations.expected_materials_fingerprint`）；`a`×64 等**只作夹具字节哈希常量**（表示文件确切字节的 SHA，供逐项比较），**不再**用于表示"已满足摘要关系"的正向实值。
- 核算方式：本轮证据根内 `fixtures.py`（**仅标准库**）按 §4.1 复算，未实现决定算法、未提供公开入口、未生成真实提交或批准文件；`selfcheck_020r1.py` 导入该模块**重新核算并与正文值比对**（见 §6 的 `fixture_fingerprints_recomputable`）。

### 2.4 每个变更例的同步规则（案例 §0.3 新增四栏）

逐例给出：**① 只改哪个语义目标 ② 需同步的派生值 ③ 故意保持不一致的旧值 ④ 预期最早拒绝字段（协议 §5 步号）**。重点复核项与其派生值：

| 变更例（本版编号） | R1 卡旧引用 | 同步后的材料摘要 | 故意不一致 | 最早字段（步） |
| --- | --- | --- | --- | --- |
| C-08 | C-08（`materials.batch_id`） | `f6c2e867194d077c2303de8eea8d063b47bbd6dcc9b567317119a0c6e73cb341` | 无 | `materials.batch_id`（5） |
| C-89 | C-54（结构阻断 + APPROVE） | `a7beae9513a9acdd50d28b74d7dc83e3f1b10945aa06814957a5d6bdaa1b6fff` | 无 | `submission.decision`（13） |
| C-90 / C-91 | C-55 / C-58（质量阻断 APPROVE/HOLD） | `cde7f4e2417bea02d0e2e3c76955ca5010c20f91249ca41465775fe48f208450` | 无 | 13（前者拒绝、后者记录） |
| C-93 | C-57（核验失败） | `2fc567ee87a5325cc4b7f5eb8bff6900d08a285678da20f99b66d88cc9b1b92d` | 无 | `materials.quality.status`（13） |
| C-52 / C-53 | C-43 / C-44（文件字节 SHA 变更） | `937628b8fb9310fe38ef71e0dc40a24e0ed12aa2aa319f75fa11dcdbbc1cbad5` | `expected_files["receive/snapshot.xlsx"]` 仍旧值 | `expectations.expected_files[...]`（10） |
| C-50 | C-45（只改外层） | 正文实际值 `5d92459c…dbc3` | 派生字段写成 `a`×64 | `materials.materials_fingerprint`（9） |
| C-54 | C-66（两类互换） | —— | 派生字段写成文件字节 SHA | `materials.materials_fingerprint`（9） |

案例 §0.3 明确：**摘要不一致会先在第 2/9/10 步失败**，因此每个负向案例都先确认"非目标部分按书面配方有效"，再期待目标拒绝；未同步的外层摘要**不得**掩盖质量、来源或前序目标。

---

## 3. B2：严格 schema、历史完整性与前序闭合

1. **历史完整性载体唯一**：API 签名新增**必需关键字参数** `prior_history: dict`（无默认值），封闭键集合 `{declared_complete, declared_scope, records}`。缺失 → 拒绝 `prior_history`；`declared_complete` 非严格布尔 → 类型拒绝；`declared_complete == false` → 拒绝并说明"调用方声明历史不完整，无法排除全局重复事件"；`declared_scope` 空白 → 拒绝；**不存在其他完整性字段**（此前未定义的 `prior_decisions_complete` 已删除），**不把缺失默认成完整**。快照范围＝调用方所声明范围；真实完整性仍由未来适配层负责。
2. **前序闭合到完整记录**：Gate2 三处输入必须同时给出且互相一致——`submission.prior_decision_binding`（wrapper：`{wrapper_version, record_fingerprint, record}`，含**完整记录**）、`expectations.expected_prior_gate1`（`{gate, batch_id, event_id, record_fingerprint}`）、`prior_history.records`（须含规范相等的同一 wrapper）。校验：wrapper 形状与常量 → **按 canonical JSON 复算记录正文** `record_fingerprint == fingerprint(record)` → 记录身份（版本/状态/`gate=GATE1`/批次/`APPROVE`/`HUMAN_DECLARED`）→ 契约一致（等于**本次** `expected_contract`，并注明"不得用旧契约记录放行"）→ 质量与边界（`status=OK`、三计数 0、`execution_allowed is False`、六项边界 `false`）→ 三处指纹闭合 → 历史一致性。协议明示：**摘要相等或一个 `"APPROVE"` 字符串不能替代实际记录**。Gate1 侧 `prior_decision_binding` 与 `expected_prior_gate1` **必须为 `null`**（统一要求）。
3. **冗余字段删除**：本版**删除** `materials.gate1_binding`，前序关系全部由上述三处承担；全稿同步（协议 §3.2、案例 C-33 改为"未知材料字段拒绝"）。
4. **严格键集合与类型**：`submission`（11 键）、`materials`（7 键）、`expectations`（8 键）、`prior_history`（3 键）、wrapper（3 键）、record（15 键）全部为**封闭键集合**，未列出键一律拒绝并给出完整路径；计数字段（`byte_size`、三个 `*_count`）为**严格整数**（`bool` 不冒充 `int`），`byte_size >= 0`；常量字段要求类型正确（`is True` 而非 `== 1`）；**删除 `extra`**（不再同时作为可选字段与未知字段）。
5. **`files` 名单规则**：非空、逻辑键（`relative`）唯一、按升序；`relative` 定义为批次相对 POSIX 路径（`/` 分隔、不以 `/` 开头、无空段、无 `..`、无 `\`），字节精确比较、不做归一化；与 `expected_files` 做**双向完整比较**（缺项、额外项、重复一律拒绝）；并写明**独立名单完备性由调用方负责，纯核心不能发现调用方同时少报的文件**。两处 Gate 的纯对象完整性要点分别列出（磁盘路径与读取留 P2）。
6. **运行绑定含义明确**：`code.file_sha256`＝宿主/核心代码**单文件确切字节 SHA**；`code.manifest_fingerprint`、`rules.manifest_fingerprint`＝**有序清单对象**（`{"entries":[{relative,file_sha256}...]}`，按 `relative` 升序、唯一、非空）的**规范指纹**；`config.file_sha256`、`input.file_sha256`＝单文件字节 SHA。两类含义不同、不可互换。
7. **时间规则定稿**（协议 §6，**U5 已删除**）：恰好两种写法 `YYYY-MM-DD` 与 `YYYY-MM-DDThh:mm:ss±hh:mm`；**全串匹配**（不允许首尾空白、`Z`、小数秒、缺秒、其他分隔符）；真实日历日期（含闰年：`2028-02-29` 合法、`2026-02-29` 非法）；分量范围 `hh 00–23`、`mm/ss 00–59`；偏移 `±hh:mm` 且最大 ±14:00（`hh==14 ⇒ mm==00`）；失败一律定位 `submission.decided_at_raw`；原文逐字符保留 + `decided_at_source="HUMAN_PROVIDED_RAW"`；不补时间/时区、不生成 normalized。**未把该裁决留给实施端**（协议 §15 注明）。
8. **检查顺序固定**（协议 §5，14 步）并说明含义：内层文件关系（10）晚于外层摘要复算（9），质量/决定矩阵（13）晚于全部材料与绑定检查；输出 record 的字段集合、派生计数来源与外层指纹语义（§14、§13）均已定清。

---

## 4. B3：完整质量与决定矩阵

**一致性规则（第 2 步）**：`OK ⇔ 三列表全空`；`BLOCKED ⇔ (结构或质量列表非空) 且 verification_failures 空`；`FAILED ⇔ verification_failures 非空`。矛盾输入（`OK` 却带阻断、`BLOCKED` 却全空、`FAILED` 却无失败项）**一律在第 2 步拒绝**，`field = materials.quality.status`。

**决定矩阵（第 13 步）**

| `materials.quality` | `APPROVE` | `HOLD` | `REJECT` |
| --- | --- | --- | --- |
| 完整报告、无阻断（`OK`） | 记录，`execution_allowed=false` | 记录，`false` | 记录，`false` |
| 完整报告、有未解决阻断（`BLOCKED`） | **拒绝**，`field=submission.decision` | **记录**，`false` | **记录**，`false` |
| 核验失败/材料不完整（`FAILED`） | 均拒绝，`field=materials.quality.status`，**不产生成功记录** | 同左 | 同左 |
| 状态与列表矛盾 | 第 2 步拒绝 | 同左 | 同左 |

- 明确区分"完整报告显示存在阻断"（可保存 HOLD/REJECT 的内存记录、固定不放行）与"核验过程失败/材料不完整"（不产生成功记录）；**不再笼统把 BLOCKED 与 FAILED 一并拒绝**，也**不允许**靠改写为矛盾的 `OK` 让 HOLD 通过。
- `quality_summary`（记录内派生）＝`{status, structural_blockers_count, quality_blockers_count, verification_failures_count}`，计数为对应列表长度的**严格整数**、来源明确、不重新计算。
- §2.2 与 record 的表述统一：`execution_allowed` **恒为严格 `false`**，是**固定的"不放行"边界字段**，本协议不提供任何实际放行接口，也不得被读取为"已获准执行"。
- 案例 §7 给出矩阵全组合（C-86—C-97，含三种矛盾输入与 FAILED 分列），并同步原 C-54—C-58 对应关系（案例 §10 旧例对应表）。

---

## 5. B4：Gate 范围与来源能力边界

- **删除初判备注**：`submission` 字段表删除 `finding_notes`（及 `finding_key`/`note` 结构）；record 形状同步删除；协议 §3.1 注明逐条备注属**真实初判范围（D3→P3 另卡）**，Gate 记录不得混入。原成功案例 C-09 **改为负向**（`finding_notes` 为未知字段 → 拒绝）。
- **来源标记是结构字段，不是文本判断**：新增 `submission.decision_source`，封闭枚举中**唯一取值** `"HUMAN_GATE_DECISION"`，由**调用方**提供，协议明示**非身份认证**；其它取值（`D2_AUTHORIZATION_SUMMARY`、`DEVELOPMENT_APPROVAL`、`AI_SUGGESTION`、`SYSTEM_DERIVED`）在**第 1 步**按非法取值拒绝（案例 C-28、C-81）。"以 D2 纪要/开发态凭证代替本批次决定"的拒绝因此**全部由结构构造**：非法来源标记、缺失独立预期、或错误的前序记录关系。
- **`reason` 文本只作数据**：不做关键词、自然语言意图或文本作者检测，不从说明文字生成授权；新增**正向对照 C-13**（结构合法、人类明确提交、`reason` 提及 D2）→ 记录可形成、原文逐字符保留、`execution_allowed=false`、**不生成任何新的批准权限**。
- **ID 前缀不是来源凭证**：原 C-27（`SIM-EV-*` 前缀冒充）**改为正向对照 C-105**（`event_id="SIM-EV-0001"` + `actor_kind="HUMAN_DECLARED"` + 其余合法 → **成功**，不因前缀判为模拟）；协议 §11.4 明确前缀、形状、内容都不构成来源证明，也不依赖任何未列入 schema 的"真实模式"字段（原 C-35 改为"未知 `expectations` 字段拒绝"）。
- **能力陈述限定**：原 C-33 改为 C-34，明确其**只证明未知提交字段被拒**，**不得**据此宣称识别了"整理时间的真实来源"；类似表述已同步纠正。

---

## 6. 只读核验与保护

本轮**未运行**宿主、控制器、导出/verify、任何纯核心、旧自检或任何业务测试；未生成/验证审阅包；未新建批次/SQLite；未新增或修改 `scripts/`、`tests/`。核验＝人工逐条对照协议/案例/原卡/评审 + 必要链接引用统计 + **书面夹具摘要复算**（标准库）。

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| `protocol_anchors_B1` | PASS | 正文定义、复算公式、三处夹具摘要值、"不得互相替代"齐备 |
| `protocol_anchors_B2` | PASS | `prior_history` 参数、`declared_complete`/`declared_scope`、wrapper、历史不完整拒绝、不得用旧契约记录放行、双向完整比较、逻辑键唯一、清单指纹与文件 SHA 含义、全串匹配与 ±14:00、U5 已定稿、`extra` 处理齐备 |
| `protocol_anchors_B3` | PASS | 三条一致性等价式、`field=submission.decision`、不产生成功记录、`quality_summary` 齐备 |
| `protocol_anchors_B4` | PASS | `decision_source`/`HUMAN_GATE_DECISION`、ID 前缀不构成来源证明、不做关键词判断齐备 |
| `material_body_no_self_reference` | PASS | 禁止整对象求摘要 + 已删除 `gate1_binding` + 无 `extra` 字段 |
| `fixture_fingerprints_recomputable` | PASS | 由 `fixtures.py` **重新复算**：BASE1 `5d92459c…dbc3`、BASE2 `74e6f14e…e0e2`、record1 `be7221df…22a9`，与正文一致；正向基线**不再**以 `a`×64 充当已满足摘要 |
| `case_sync_rules_present` | PASS | 变更例四要素表（只改目标/需同步/故意不一致/最早字段）齐备 |
| `case_numbering_unique_sequential` | PASS | 唯一编号 **111**、连续 C-01—C-111、无字母后缀，与正文声明计数一致（`case_index.json`） |
| `b4_schema_and_source_boundary` | PASS | 字段表无 `finding_notes`；前缀非凭证；不做作者检测 |
| `no_affirmative_completion_claims` | PASS | "已实现/测试 PASS/已获批准/P1 可以启动/已验证通过"仅出现在否定语境 |
| `references_and_links` | PASS | 16 项引用分层登记（含本轮评审、旧回执自检作为**读取的旧证据**）；链接全部可解析 |
| `external_contract_input` | PASS | 正式契约实读 SHA 与 13289 字节匹配登记 |
| `frozen_and_forbidden` | PASS | 重点冻结身份一致（含上一轮回执与旧自检脚本存在且未改）；无禁止文件 |
| `protection_scan_once` | PASS | 见下（14 项检查 14 PASS / 0 FAIL） |

**保护比较**（基线 `data/reviews/task020_gpt_20261013_175701/source_hashes_after.json`，SHA `a753e0f1545c5bc5a157f3c358f60a3249c98e399bce369ce5cb34d882289ebc`，**133320** 项，同目录 `review_result.json` 记 `verdict=NOT_ACCEPTED`）：

- 对**最终字节**执行**一次**完整扫描（两份正文与本回执齐备后）：实扫 **133330** 文件；`changed` **恰为两份允许文档**（协议 `cdc9dbf6…b0bcc`、案例 `a520219f…728b1`）、`missing=[]`、读取错误 **0**、**范围外新增 0**。
- 新增产物分列：**本轮允许新增 8 项**（本回执 + 证据根内 7 个文件）；**旧评审元数据**按两个**确切路径**单列（`source_hashes_after.json`、`review_result.json`）；**外部输入**按确切路径单列核对（正式契约 `174a021b…40ad`、生效登记 `042086cb…`、D1/D2/D3 纪要 `bface683…`、补充通知 `f0c764cd…`、契约登记 `registration.json` `d547827b…`，逐项身份记于 `protection_result.json` 的 `external_inputs_verified`）。**未使用 reviews 目录前缀豁免未知文件**（按确切路径分类）。
- 扫描后只做**有限身份登记**（把两份正文写后 SHA 与本节数值补入本回执），**未再次全树扫描**。

---

## 7. 过程问题、未解决项与未执行动作

**过程问题（如实记录）**

1. 本版为重写而非逐点补丁：两份正文均按修正版 schema 与检查顺序整体重写，避免新旧条款并存导致的语义矛盾；案例编号随之重排并给出旧例对应表（案例 §10）。
2. 夹具摘要不再手填：先由 `fixtures.py` 按 §4.1 复算，再由 `selfcheck_020r1.py` **导入并复算核对**与正文一致；`a`×64 一类值在正值中只作**文件字节 SHA 常量**，不再充当已满足的摘要关系。
3. 案例计数：本版唯一编号数与正文声明一致，由脚本核对并落盘（`case_index.json`）；上一轮回执"40 项维度"与 summary 实计不一致的问题**只在本回执说明，未回写旧文件**。
4. 上一轮 §6 对"外层/内层篡改"的案例引用（原 C-17/C-18）在本版更正为对应 **C-50—C-54**（外层摘要、内层名单、两类互换；见案例 §4 与 §10 对应表）。
5. 案例编号在初稿中曾以字母后缀区分同类（如 `C-43T`/`C-54M`），与同一数字的其它案例**重号**；本版改为**唯一且连续**的 C-01—C-111（无后缀），由脚本核对唯一性、连续性与正文声明计数一致（`case_numbering_unique_sequential`，明细见 `case_index.json`）。
6. **过程偏差（如实披露）**：核验脚本在定稿前运行过一次，该次同时触发了全树扫描，结果为首轮 12 PASS / 2 FAIL——其中 1 项是**真实文档缺陷**（案例编号重号），1 项是**脚本自身锚点位置错误**（把夹具派生值锚定到协议，实际写在案例正文）。两处修正后对**最终字节**重新做了那一次完整扫描（即上表数值）。因此本轮的中间扫描数值不做交付依据、未被登记为两次通过；`protection_result.json` 只保留最终一次的结果。若验收端认为该中间扫描属于"为局部错误反复扫全树"，请按过程问题登记，本回执不作辩解。

**未解决项**：无（本卡范围内）。协议未决项仅剩 U1—U4（持久化/恢复；控制器与宿主接线及批准字段、材料实际枚举与磁盘读取；真实初判结构 P3；AI/终判另行范围），**U5 已在本版定稿**。

**未执行动作（not_executed，不填 PASS 或默认零调用）**：未实现或调用任何拟定 API；未运行本卡任何案例、未实施任何注入、无 PASS 计数；未导入或运行宿主/控制器/上游核心/旧核心/旧自检/任何业务链；未新增或修改 `scripts/`、`tests/` 下任何文件；未生成真实 Gate 记录、真实人类初判或 `0009`；未生成真实提交/批准文件；未新建批次/SQLite、未生成或验证审阅包；未执行任何持久化/恢复/放行操作；未开放 AI/终判。

---

## 8. 绝对路径

- `D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`
- `D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_020_R1.md`
- `D:\harness work\audit_sa_project\data\decision_protocol_checks\task020r1_run_01\`
- 只读外部输入：`D:\harness work\audit_sa_project\docs\AUDIT_CONTRACT.md`（人类正式契约 V1，未修改）

---

## 9. 停止点

本卡只做文档修正：不实现、不运行核心、不生成真实 Gate/初判或 `0009`、不开放 AI/终判。修正版通过后再制定 P1 实现卡（且先核验主理人正式 V1 文件与明确生效确认）；正式契约、协议与实际代码**各自独立绑定**，本卡与 D2 纪要**均不构成任何批次的 Gate 批准**。人类继续作出每一批次的决定与初判；DSH 由人类操作。
