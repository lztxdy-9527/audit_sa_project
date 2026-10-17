# TASK-019 执行回执（候选契约、人类决策包与分阶段接入方案）

任务：按唯一权威细则 `docs/tasks/TASK-019_DRAFT.md` 只形成**可审定材料与只读核验记录**。前置为 `docs/reviews/REVIEW_TASK_018_R2.md` 的整体验收通过。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：四份文档已交付；只读自检与保护核验通过（`changed=[]`、`missing=[]`、读取错误 0、范围外新增 0）。

**本卡不编写实现代码、不建立正式契约、不实施或批准真实 Gate、不保存真实初判、不开放 AI/终判**；无 `0009`/LLM/网络/UI/ERP。技术验收通过、卡片关闭、本回执中的任何"完成"表述，均**不表示**人类已采纳候选契约、已许可实施真实模式或已批准任一批次。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 说明 | SHA-256 |
| --- | --- | --- |
| `docs\proposals\AUDIT_CONTRACT_V1_CANDIDATE.md` | 候选契约（标识 `PROPOSAL_PENDING_HUMAN_REVIEW_NOT_IN_FORCE`） | `586409ae159d68c6458842de51a947e0a4f8e48db237b2bccd3c4327bb067d53`（15083 字节） |
| `docs\decisions\REAL_FLOW_DECISION_PACKET_DRAFT.md` | 人类决策包 D1/D2/D3（全部未作出） | `36b9f28d094e31125f92c50bfd95904634b3b568dac631586ded69c896b54e8e`（8411 字节） |
| `docs\proposals\REAL_FLOW_INTEGRATION_PLAN_DRAFT.md` | 分阶段接入方案 P0—P5（待采纳） | `2cbb32754bcb086a74f1686a90fe5f47014b1b7ec23252e9266d32cfa9785ca2`（10527 字节） |
| `docs\EXEC_REPORT_019.md` | 本回执 | 见交接消息（自身 SHA 不写回自身） |
| `data\decision_packet_checks\task019_run_01\`（新证据根） | `selfcheck.py`、`checks.json`、`summary.json`、`protection_result.json` | 见 `summary.json` 的 `document_hashes` |

上表三份材料的 SHA 为**保护扫描之后**对当前文件实读所得，未改动三份材料。回执自身 SHA 只在交接消息给出（不写回自身）：证据根 `summary.json` 的 `document_hashes` 与 `protection_result.json` 由那**一次**完整扫描产生，其中本回执一项是**有限登记之前**的身份，最终回执 SHA 以交接消息为准。本回执在扫描后仅做有限身份登记（补入上表 SHA 与本段数值），**未再次扫描全树**；回执自身不写回自身哈希。

**重点冻结身份实测未改**：宿主 `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`；独立导出工具 `0b2f7b288cc49327a124a6defad5b1d9ddd09856d6c907b6120536d932e32577`；导出工具测试 `042b20e33a37577a9c2c69050b4d34ca082dbfa862f9e061a54a3b0eeeb78fcf`；导出指南 `9a65bf991253f466b2130eebf776f936e2e9a767525bc0370da401c5a43df0c7`；控制器 `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`；初判纯核心 `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`。既有文件零改动；未创建 `AUDIT_CONTRACT.md`、`AGENTS.md`、运行配置或批准文件。

---

## 2. 三份材料的要点与边界

### 2.1 候选契约 `AUDIT_CONTRACT_V1_CANDIDATE.md`

- 首部标识 **候选稿、待主理人审定、尚未生效**，明示不构成任何批次批准或真实判断；不推断人类姓名/时间/事件 ID/批准值（未出现任何生效标记）。
- 内容：目标与业务范围（单公司、CNY、2026-09、截至 2026-09-30、四表、ID 原字符串、整数分、主表与分摊分别计量、缺失关联保留；范围外项列出并停止）；四类角色职责（架构验收不代替批次 Gate 与职业判断）；输入/批次/历史（原始快照、工作副本、变化后**不复用**旧批准、新批次策略）。
- **两处人工守门点**：Gate 1 / Gate 2 的触发、展示材料、停止条件与绑定要求（批次 + 当时材料指纹 + 决定说明）；明确**结构/质量阻断不得靠人工 APPROVE 掩盖**，不得从总体授权、聊天倾向、历史批准或模拟字段**推断**本批次批准。
- **人机顺序固定**：事实底稿 → 人类独立初判保存 → 后置 AI 对照建议 → 人类终判；初判前不展示 AI 候选结论/等级/预填判断；"暂不能判断 + 原因"是有效初判；**零条线索不得自动形成"无问题"**；缺框架/缺证据不给候选等级。
- **能力限度**：本地显式声明与可追溯记录，**不宣称**强身份认证、防同权限恶意篡改、不可篡改存储或独立审计保证；未设重要性阈值、不自动给缺陷等级/审计调整/正式结论；不引入外部审计准则、法律结论、真实 ERP 兼容性或新业务承诺。
- **§8 对应关系**：保留（K1—K7，与冻结草案逐条一致）／澄清（C1—C5，标为**建议**）／待人类决定（H1—H6）。**§9 现状声明**逐项给出取值与证据层级；并分列"纯核心内存校验 / 宿主持久保存 / 离线包核验 / 人类审计结论"四件不同的事。

### 2.2 人类决策包 `REAL_FLOW_DECISION_PACKET_DRAFT.md`

- §0 现状能力与缺口；三项决定**相互独立**（采纳契约 ≠ 许可实施 ≠ 批准批次）。
- **D1 候选契约是否采纳**：建议先审阅文本、再单独决定生效方式；实施范围限"文档层面 + 版本登记"；暂缓则维持"草案 + 候选稿"。
- **D2 是否允许建设真实人工决策保存模式**：建议允许，范围仅"本人对合成数据提交 Gate 决定与独立初判的保存/校验"，保留模拟模式，接受本地显式声明与可追溯记录的能力限制；强认证属**另一待定范围**，不承诺已解决；**此许可仅为实施范围授权，不是任何批次 APPROVE**。
- **D3 初判提交粒度**：方案 A（批次必填 + 可选逐条备注，建议）／方案 B（逐线索独立提交），并说明对零条线索与"暂不能判断"的影响；不作具体线索结论、不要求人类先作确定判断。
- **汇总表三项的"当前决定"均为 `null`（未作出）**；未默认勾选、未生成签名、未把沉默当同意；AI/模型/联网/隐私/成本/终判列为**后续另行明确范围**，未包装为已批准。

### 2.3 分阶段接入方案 `REAL_FLOW_INTEGRATION_PLAN_DRAFT.md`

- §0 现状与可复用边界：现有确定性计算核心可复用（以冻结指纹引用）；开发态 `0001—0008`、模拟守门与模拟初判**继续保留**，真实模式**不得复用**其批准/身份/凭证；变化即**新批次**，不静默迁移/补签/恢复旧批准。
- P0 前置确认（人类动作）→ P1 真实决策记录**纯核心**（候选名 `build_demo_decision_record.py`，**设计建议、当前不存在**；只校验并按原文记录、不生成批准）→ P2 独立保存/恢复 + **Gate 1 与 Gate 2 分开验收** → P3 真实独立初判（按 D3）→ P4 接入计算链 → **P5 后置 AI（不在本方案授权范围，需另行单独任务卡与授权）**。
- 每阶段均给前提、拟新增组件、输入/输出与绑定不变量、停止点、最小正负向验收；§2 统一拒绝清单（缺决定/错批次/错指纹/材料变化/重复事件/模拟身份冒充/未解决质量阻断/失败现场/不完整凭证/未生效契约版本/运行版本不一致）与失败现场策略；§4 说明 D1/D2/D3 未决时各阶段保持未启动。

---

## 3. 只读自检与保护核验（`data\decision_packet_checks\task019_run_01\selfcheck.py`）

本卡**未写生产测试、未运行宿主/工具/纯核心、未重新生成审阅包或业务链**；仅做实际文件阅读、引用 SHA 复核、文档标识/边界自检、正文链接可解析性与一次保护扫描。

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| `references_read` | PASS | 19 项引用（任务卡、规格、草案、四份评审、三份指南、三份只读源码、四份只读样本、基线与其身份登记）全部实际存在并实读 SHA |
| `doc_identifier_*` | PASS | 三份材料的标识与必需表述齐备（未生效/未作出/待采纳、D1—D3、P0—P5） |
| `doc_forbidden_claims_*` | PASS | 生效/批准类表述**仅出现在否定语境**（如"不是已建立、已签署或已批准""不默认勾选""不表示…允许执行"），无肯定式生效声明 |
| `decision_packet_structure` | PASS | D1/D2/D3 各含待决定问题/建议及理由/实施范围/暂缓停止点，汇总表三行"当前决定"均为 `null` |
| `integration_plan_structure` | PASS | 逐阶段前提/停止点/验收齐备，P5 明确需另行单独授权 |
| `no_prefilled_sample_judgment` | PASS | 决策材料中**未出现**只读样本的提交原文（`assessment`/`reason`/`event_id`） |
| `no_effective_files` | PASS | 未出现 `AUDIT_CONTRACT.md`、`AGENTS.md`、运行配置或批准文件 |
| `links_resolvable` | PASS | 四份文档中的相对链接全部可解析 |
| `protection_scan_once` | PASS | 见下 |

**保护比较**（基线 `data/reviews/task018_r2_gpt_20261013_151052/source_hashes_after.json`，身份经同目录 `review_result.json` 登记，`verdict=ACCEPTED`、`tasks_accepted=[TASK-018, TASK-018-R1, TASK-018-R2]`）：

- 基线 **133252** 项；**一次**完整扫描（结果见 `protection_result.json`）：
  **`changed=[]`**、**`missing=[]`**、读取错误 **0**；
  重点冻结身份（宿主/导出工具/工具测试/导出指南/控制器/初判纯核心）全部一致。
- 新增产物分类：允许新增 **8** 个文件（四份文档 + 证据根内 `selfcheck.py`/`checks.json`/`summary.json`/`protection_result.json`）；本轮之前由评审端创建的新增（`data/reviews/task018_r2_gpt_20261013_151052/`，2 个文件）单独归类；**范围外新增 0**（实扫 133262 文件）。
- 扫描后只做**有限登记**：本回执的写后身份与本节数值；**未再次扫描全树**。

`not_executed`（不填默认通过或零调用）：未运行宿主/控制器/任何纯核心；未运行导出工具或测试、未重新生成审阅包；未创建批次/SQLite、未重建业务链；未运行 R1/R2 定点入口或默认七组/六组；未执行任何真实 Gate、真实初判保存或 AI 调用（均未开放）。

---

## 4. 现状断言与证据层级（与材料一致）

| 断言 | 取值 | 证据层级 |
| --- | --- | --- |
| 宿主阶段 / 模式 / 契约状态 | `phase=DEV_GATE2_APPROVED`；`DEVELOPMENT_TEST_ONLY`；`DRAFT_NOT_IN_FORCE` | 只读样本 `host_status.json`（导出时冻结的公开 status） |
| 真实批准 | `null`（`real_approvals=0`） | 同上与样本 `manifest.json` 的 `boundaries` |
| 真实人类独立初判 | **未保存**（`human_initial_judgment=null`） | 样本 manifest 边界字段与记录边界 |
| 模拟初判 | **已保存**（`SIMULATED_INITIAL_JUDGMENT_RECORDED`；`SIMULATED_HUMAN`/`SIMULATED_TEST_ONLY`） | 同上 |
| 下一步 / AI | `next_step_allowed=false`；`ai_action_simulation_allowed=false`、`ai_suggestion=null`；无 `0009` | 同上 |
| 离线包核验范围 | `COPIED_BYTES_ONLY`：包内一致性，**不**证明来源真实性、不作身份认证、不重新批准批次 | `docs/DEV_REVIEW_BUNDLE_GUIDE.md` 与已验收记录 |

分列口径：**纯核心内存校验**（`DEV_INITIAL_JUDGMENT_VALIDATED`）、**宿主持久保存**（开发态 0008）、**离线包核验**（包内字节与清单）、**人类审计结论**（尚未形成）为四件不同的事，材料中未相互替代。

---

## 5. 过程问题与未解决项

**过程问题（如实记录）**

1. 自检脚本首轮把"禁止性表述"做成**朴素子串匹配**，把否定语境（"不是已建立、已签署或已批准的契约""不默认勾选""不表示…允许执行"）误报为失败 → 改为**否定窗口**判断（命中词前 16 字符内出现否定词即不计为肯定声明），复跑通过。该修正只影响自检脚本，未改任何交付文档内容。
2. 首轮自检在回执尚未写入时运行，仅报"文档缺失"一项 → 在四份文档齐备后按卡要求重跑**一次**完整扫描，并以该次结果为准（`protection_result.json`）。两次运行的 `changed/missing/读取错误` 均为 `[]/[]/0`，未据首轮误报重建任何业务链或改动既有文件。

**未解决项**：无（本卡范围内）。**所有真实事项仍待人类决定**：候选契约是否采纳（D1）、是否允许建设真实人工决策保存模式（D2）、初判提交粒度（D3），以及后续另行明确范围的 AI/模型/联网/隐私/成本/终判与真实数据接入。

---

## 6. 停止点与边界

- 本卡只做文档与只读核验：**未实施任何真实控制**、未创建生效文件、未改实现/绑定/草案/规格/测试/SQL/历史现场；未安装依赖、未初始化 Git、未清理或迁移历史；小检查脚本仅存在于本轮证据根内。
- 待材料可审后由人类决定 D1/D2/D3；**未决期间不得进入真实流程实现，也不得代签任何批准**。
- 宿主仍停开发态 `0008`：真实人类初判未保存、真实 Gate 未批准、`next_step_allowed=false`、AI 未开放；正式契约未建立。
- 四份文档与证据根绝对路径：
  - `D:\harness work\audit_sa_project\docs\proposals\AUDIT_CONTRACT_V1_CANDIDATE.md`
  - `D:\harness work\audit_sa_project\docs\decisions\REAL_FLOW_DECISION_PACKET_DRAFT.md`
  - `D:\harness work\audit_sa_project\docs\proposals\REAL_FLOW_INTEGRATION_PLAN_DRAFT.md`
  - `D:\harness work\audit_sa_project\docs\EXEC_REPORT_019.md`
  - `D:\harness work\audit_sa_project\data\decision_packet_checks\task019_run_01\`（`selfcheck.py`、`checks.json`、`summary.json`、`protection_result.json`）
