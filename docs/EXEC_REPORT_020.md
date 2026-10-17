# TASK-020 执行回执（真实 Gate 决策记录协议与案例，P0 文档准备）

任务：按唯一权威细则 `docs/tasks/TASK-020_DRAFT.md` 与补充通知 `docs/tasks/TASK-020_CONTRACT_INPUT_NOTICE.md` 只形成 **Gate 决策记录协议、案例与回执**三份文档。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：两份文档 + 本回执已交付；只读内容核验与**一次**完整保护扫描结果见 §5。

**硬边界重申**：本卡**只做文档，未写任何实现代码**；未实施 P1 纯核心、未运行宿主/控制器/导出/verify/纯核心/任何历史入口、未建业务链/审阅包/批次/SQLite、未生成真实 Gate 记录/真实初判/`0009`、未开放 AI 或终判；**未新增或修改 `scripts/`、`tests/` 下任何文件**；未创建 `AGENTS.md`/生效/批准/运行配置文件（`docs/AUDIT_CONTRACT.md` 由主理人建立，执行端只读）。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 说明 | SHA-256 |
| --- | --- | --- |
| `docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md` | Gate 决策记录协议（`PROTOCOL_DESIGN_DRAFT_NOT_IMPLEMENTED`） | `63e43bbb47d11ae00111bbfca55fb3c59d8e244b643da485238b938fd2ec6e05`（20330 字节） |
| `docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md` | 案例与最小验收设计（`PROTOCOL_CASE_DESIGN_NOT_EXECUTED`） | `f1f1cb58e3a6b443f83f330708648ee82bd80204aeb93e640c297a2edbcff668`（19012 字节） |
| `docs\EXEC_REPORT_020.md` | 本回执 | 自身 SHA 只在交接消息给出（不写回自身） |
| `data\decision_protocol_checks\task020_run_01\`（新证据根） | `selfcheck_020.py`、`checks.json`、`summary.json`、`protection_result.json` | 见 `summary.json` |

上表两份材料的 SHA 为**保护扫描之后**实读所得，未改动正文；回执自身 SHA 只在交接消息给出（不写回自身），证据根 summary.json 的 document_hashes 是本回执有限登记之前产生的快照。

**外部输入与冻结件实测**（只读核对，未修改）：正式契约 `docs/AUDIT_CONTRACT.md` = `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`（13289 字节，头部"版本：V1 / 状态：已生效"）与补充通知一致；已采纳候选 `171216c2…c15c`、接入方案 `62c5ab19…ee93`、决策包 `b914f1dd…93e1`、`REVIEW_TASK_019_R1.md` `4d24c54d…6c7d`、宿主 `38869681…a307`、控制器 `a6b7b8e1…3a8c`、初判纯核心 `0b514733…4d8c`、导出工具 `0b2f7b28…2577` 全部未变。

---

## 2. 协议要点（`HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`）

- **标识/范围**：`PROTOCOL_DESIGN_DRAFT_NOT_IMPLEMENTED`；范围为**独立纯内存**的 Gate 决定记录校验与构建，持久化/恢复/控制器/宿主接线**留后卡**；不设计真实初判（D3 只登记为 P3 约束：批次初判与原因必填、逐条备注可选）、不设计 AI 或终判。
- **拟定接口**：`build_human_gate_decision_record(submission, materials, expectations, *, prior_decisions=())`，返回 `{"record", "record_fingerprint"}`；异常拟定 `HumanGateDecisionBlocked(field, reason)` / `HumanGateDecisionError(stage, reason)`（保留 `__cause__`）；**无 CLI、无持久化、无恢复入口**。
- **字段集合**：`submission`（`submission_version`/`event_id`/`batch_id`/`gate`/`request_binding`/`decision`/`actor`/`decided_at_raw`/`reason`/`prior_decision_binding`/`finding_notes`）、`materials`（`gate`/`batch_id`/`run_binding`/`contract_binding`/`files[]`/`materials_fingerprint`/`quality`/`gate1_binding`）、`expectations`（8 项独立预期）；**未知字段一律拒绝**；布尔/数字不得冒充字符串；不 `strip`/不改大小写/不转数字。
- **五项义务**（明确决定／批次标识／守门材料指纹／时间／说明）缺一不可；时间只做最小语法判定（真实日历日期、带时间写法必须显式时区、拒绝非法偏移），**原文保留、不规范化、不补当前时间/时区**，并写入 `decided_at_source="HUMAN_PROVIDED_RAW"`。
- **材料与契约**：正式契约**版本 + 确切文件 SHA**独立绑定（拒绝候选/草案冒充正式、`contract_effective` 必须为 `true`）；材料集**内部文件字节 SHA 与整体规范对象指纹分别命名、分别核对**，不得以外层指纹掩盖内层不符。
- **能力边界**：写明纯内存核心**能**验证的对象关系（一致性、可复算指纹、前序结构、输入不变、确定性）与**不能**验证的事实（磁盘实读、契约生效、来源真实性、人类身份、全局重复事件），后者属未来适配层职责；核心**不认证身份、不证明业务真实性**。
- **Gate 顺序/放行分离**：Gate2 必须绑定同批次已核验的**真实 Gate1 APPROVE**（前序绑定形状给出）；明确拒绝仅凭 `APPROVE` 字符串、开发态 `phase`、模拟凭证或 **D2 总体许可**放行；`HOLD`/`REJECT` 可形成记录但 `execution_allowed=false`；结构/质量阻断下 `APPROVE` **必须拒绝**。
- **历史/身份/确定性/停止点**：决定不可覆盖、变化即新批次、重复事件与不完整历史须显式传入快照并写清能力边界；真实人类输入用 `HUMAN_DECLARED` 且**拒绝** `SIMULATED_HUMAN`/`AI`/`SYSTEM`/开发态凭证冒充；规范 JSON 沿用既有口径、输出不内嵌自身指纹、返回深拷贝不改输入、同输入同结果、不读写文件/库/网络；纯核心只返回内存校验结果，**不设** `gate1_approval`/`gate2_approval`/`next`/AI 字段，VALIDATED ≠ RECORDED ≠ APPROVED。
- **哈希规则**：必须完整 64 位小写十六进制（尾 LF/CRLF/空格、大写、截断拒绝）；**普通 ID 即使形状恰为 64 位十六进制或含前导零仍是合法字符串**，不套用"不是哈希"的排除。
- **未决项**（协议 §14）：U1 持久化/恢复、U2 控制器与批准字段、U3 真实初判结构、U4 材料集来源、U5 时间格式最终取舍、U6 AI/终判。

---

## 3. 案例要点（`HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`）

- **标识/性质**：`PROTOCOL_CASE_DESIGN_NOT_EXECUTED`；全部夹具标注 `PROTOCOL_TEST_FIXTURE_ONLY`，**无审批效力**，不向人类表单预填；**不运行任何函数、不含任何执行结果**，不写成"测试 PASS"。
- **结构**：78 个编号案例（C-01…C-78），每例给出「所属字段/关系 / 隔离构造 / 预期结果与定位字段 / 为何不被更早错误遮蔽」，并对应协议章节。
- **覆盖维度**：正向（合法 APPROVE、合法 HOLD/REJECT、Gate2 合法前序、时间原文保留、前导零与 64 位十六进制普通 ID、可选备注、两类哈希分列、输入不变、嵌入指令只作字符串）；五项义务与字段级负向（缺失/空白/布尔与数字冒充/非法枚举/未知与越界字段/身份缺失/模拟身份与 AI-SYSTEM 代签/开发态凭证冒充）；时间（非法日历日期、无时区、非法偏移、非字符串、禁止补时间、整理时间冒充）；绑定与契约（错批次/错 Gate/错请求/错材料指纹/错文件 SHA/错契约版本与 SHA/候选冒充正式/错运行绑定/材料变更传旧预期/**更新外层指纹但内层矛盾**/**只改外层指纹**分别列例）；Gate2 前序（缺失/前序 HOLD/前序 REJECT/错批次/模拟 Gate1/仅凭 APPROVE 字符串/开发态 phase 冒充/D2 纪要当批准）；质量与放行（阻断下 APPROVE 拒绝、**HOLD 记录与放行 false 分列**、材料失败、空材料集、只算残余子集、记录不等于放行）；哈希与尾随字符（尾 LF/CRLF/空格、大写、截断、**两类哈希互换**、普通 ID 正向对照）；历史与重复事件（重复 event_id、同批次同 Gate 已有 APPROVE、快照不完整、变化后不复用）；确定性与异常分列（同输入同结果、深拷贝与输入不变、嵌入指令、协议错误与内部错误分型、无副作用；后两者只列**未来验证方法**，不声称已运行守卫或调用计数为 0）。

---

## 4. 协议关键设计与未决项（供审查）

| 项 | 设计取舍 | 备注 |
| --- | --- | --- |
| 指纹分列 | `files[].file_sha256`（字节）与 `materials_fingerprint`（对象）分别命名与核对 | 直接对应上一轮 B2 的口径要求 |
| 独立预期 | `expectations` 8 项由调用方核验后传入 | 避免"自报指纹与自身比较" |
| 契约绑定 | 版本 + 确切文件 SHA + `contract_effective` | 候选/草案不得冒充正式 |
| 决定 vs 放行 | 记录内仅 `execution_allowed=false`；不放行字段 | VALIDATED ≠ RECORDED/APPROVED |
| 时间 | 原文保留 + 最小语法判定 + `decided_at_source` | 不规范化、不补当前时间 |
| 身份 | `HUMAN_DECLARED` 显式声明 | 拒绝模拟/AI/SYSTEM；声明非强认证 |
| 未决 | U1—U6（协议 §14） | 留 P2/P3 与另行范围 |

---

## 5. 只读核验与保护

本轮**未运行**宿主、控制器、导出/verify 工具、任何纯核心、旧自检或任何业务测试；未生成/验证审阅包；未新建 batches/SQLite；未重跑 TASK-018/019 及任何历史入口；未新增或修改 `scripts/`、`tests/` 下任何文件。

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| `protocol_identifier_and_anchors` | PASS | 标识 `PROTOCOL_DESIGN_DRAFT_NOT_IMPLEMENTED` + 23 项要点锚点（函数签名、五要素、指纹分列、独立预期、前序绑定、放行分离、canonical 口径、异常分型等）齐备 |
| `case_identifier_and_dimensions` | PASS | 标识 `PROTOCOL_CASE_DESIGN_NOT_EXECUTED`、夹具标注 `PROTOCOL_TEST_FIXTURE_ONLY`、40 项维度锚点齐备（覆盖原卡 §5 全部要求） |
| `no_affirmative_completion_claims` | PASS | "已实现/已通过验收/测试 PASS/已获批准/P1 可启动"等仅出现在否定语境，无肯定式完成声明 |
| `external_contract_input` | PASS | 正式契约 `docs/AUDIT_CONTRACT.md` 实读 SHA = `174a021b…40ad`、13289 字节、头部"版本：V1 / 状态：已生效"，与登记一致 |
| `effective_registration_consistency` | PASS | 生效登记中 `formal_file_sha256` 与文件实读一致；`effective_time_normalized` 为 `null`（时间原文保留） |
| `references_and_links` | PASS | 18 项引用分层登记（含人类新输入、架构端登记、上一轮交付、历史快照、评审层级、只读源码、基线文件）；文档相对链接全部可解析 |
| `frozen_and_forbidden` | PASS | 8 项重点冻结身份一致；未出现 `AGENTS.md`/`approval.json`/`real_gate.json`/`config.yaml` |
| `protection_scan_once` | PASS | 见下 |

**保护比较**（基线 `data/reviews/task020_handoff_20261013_164109/source_hashes_before.json`，SHA `dd12d188b4a49bb7faf378a93a2d3402d8a36f946e0f20a6b2831b1afb02d24c`，**133294** 项；该基线是任务交接快照，不是批准或版本恢复点）：

- **一次**完整扫描（三份文档齐备后执行）：`changed=[]`、`missing=[]`、读取错误 **0**；
- 新增产物分类：**本轮允许新增**（协议、案例、回执、证据根内文件）；**先前交接元数据**单列（`source_hashes_before.json`、`handoff.json`，按原卡自排除约定不计允许/范围外新增）；**人类新输入/架构端登记**单列（`docs/AUDIT_CONTRACT.md`、生效登记、补充通知、`contract_v1_registered_20261013_171458/` 三个文件，逐项实读身份记录在 `protection_result.json` 的 `external_inputs_verified`）；**范围外新增 0**。
- 未使用 reviews 目录前缀豁免未知文件：分类按**确切路径**判定。
- 扫描后只做**有限身份登记**（把三份文档 SHA 与本节数值补入本回执），**未再次全树扫描**。

---

## 6. 过程问题与未解决项

**过程问题**

1. 本卡沿用了上一轮（TASK-019-R1）的纪律：**内容核验与全树扫描分离**——先完成文档与内容锚点核对，三份文档齐备后才做那一次完整扫描；未因内容检查触发多次扫描。
2. 分类逻辑按原卡要求修正了上一轮出现过的"目录前缀豁免"风险：本轮分类使用**确切路径集合**（本轮允许新增前缀、两个确切交接元数据路径、六个人类/架构端输入路径），未知路径一律计入范围外新增（本轮为 0）。
3. 扫描后对回执做有限身份登记（补入文档 SHA 与扫描数值），属卡内允许的"扫描后仅有限登记本轮新增产物"，未改动协议/案例正文。

**未解决项**：无（本卡范围内）。协议未决项 U1—U6 已在协议 §14 列明，分别归属 P2/P3/另行范围。

**未执行动作（not_executed，不填通过或默认零调用）**：未运行宿主、控制器、导出/verify 工具、任何纯核心或历史入口；未运行任何拟定协议函数或案例（案例仅为设计稿，无执行结果）；未生成真实 Gate 记录、真实人类初判或 `0009`；未新建 batches/SQLite、未重建业务链、未生成或验证审阅包；未新增或修改 `scripts/`、`tests/` 下任何文件；未调用任何 AI/模型，未开放终判；未执行任何保存/恢复/放行操作（均属后卡）。

---

## 7. 绝对路径

- `D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`
- `D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_020.md`
- `D:\harness work\audit_sa_project\data\decision_protocol_checks\task020_run_01\`（`selfcheck_020.py`、`checks.json`、`summary.json`、`protection_result.json`）
- 只读外部输入：`D:\harness work\audit_sa_project\docs\AUDIT_CONTRACT.md`（人类正式契约 V1，执行端未修改）

---

## 8. 停止点

本卡只形成 Gate 记录协议、案例与回执：**不写实现、不运行核心、不生成真实 Gate/初判或 `0009`、不开放 AI/终判**。文档验收通过后，P1 纯核心实施须**另卡**，且先核验主理人正式 V1 文件与明确生效确认；正式契约、协议与实际代码**各自独立绑定**，本卡与 D2 纪要**均不构成任何批次的 Gate 批准**。人类继续作出每一批次的决定与初判；DSH 由人类操作。
