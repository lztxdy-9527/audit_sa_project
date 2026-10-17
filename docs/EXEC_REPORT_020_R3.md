# TASK-020-R3 执行回执（四个前序变更夹具的材料→记录摘要完整闭合）

任务：按唯一权威细则 `docs/tasks/TASK-020-R3.md` 定点修正唯一阻断 **E1**——C-112—C-115 变更前序运行绑定后，记录仍绑定 BASE1 旧材料指纹，与"祖先摘要全部同步"的声明不符。依据 `docs/reviews/REVIEW_TASK_020_R2.md`。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：四例配方与派生值已重做并独立核验；最终保护扫描结果见 §6。

**硬边界重申**：**仅修案例正文**（`docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`）与新增回执/证据根。**协议冻结未动**（`docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md` = `68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`、39298 字节，与 R2 评审冻结值一致，未改算法/schema/API/Gate 顺序/时间规则/输出常量/检查顺序）。未实现或调用任何拟定 API、未运行任何案例或异常捕获、未导入/运行宿主、控制器、上游核心、旧自检或 **R2 旧夹具**、未新增或修改 `scripts/`、`tests/`、未生成真实提交/Gate 记录/真实初判/`0009` 或审阅包、未提前运行规则筛查、未执行持久化/恢复/放行、未开放 AI/终判。正式契约 `174a021b…40ad`、D1/D2/D3 与全部旧产物未改，未填任何实际人类姓名/决定/时间/事件 ID。

---

## 1. 交付与身份

| 文件 | 说明 | 写后实测 SHA-256 |
| --- | --- | --- |
| `docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md` | 案例正文（本轮唯一修改的既有文件） | `bd1fc37dc2437454b87b5453d7df90a6dcd6f3f79e84c3e75a335381fcf2d2a6`（43060 字节；起点 `fec74c9148c69ee8d4066c82eee167a93963412ad099a5b1b6982cea67da3c64`） |
| `docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md` | 协议（**只读冻结**） | `68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`（39298 字节，未改） |
| `docs\EXEC_REPORT_020_R3.md` | 本回执 | 自身最终哈希**只在交接消息提供**，不写回自身 |
| `data\decision_protocol_checks\task020r3_run_01\`（新证据根） | `fixtures_r3.py`、`prior_variants.json`、`verify_r3.py`、`independent_rebuild.json`、`checks.json`、`summary.json`、`protection_result.json` | 见 `summary.json` |

**回执身份说明（非阻断项，如实登记）**：R2 回执的**交接声明**为 `7139f82a429a5980fb3446843e1d41ca3b5d4917bb57657ed3e964183e048881`、18697 字节；**实际读取** `docs/EXEC_REPORT_020_R2.md` 为 `90235e44c0e0a20fe0de29bad8c3307ae1f7a7436f612513a53124a3bd9feb09`、19198 字节（与 R2 评审一致）。该差异由 R2 扫描后的有限身份登记造成，**旧回执按实际字节冻结、未改写或追造旧交接记录**；本回执只记录本轮实读值。

---

## 2. E1 关闭：四例改为"先材料、后记录"的完整闭合

### 2.1 构造顺序（案例 §0.4 已写明六步）

```text
① 仅改前序材料 run_binding 的一项（7/8/9/0×64）
② 由变化后的前序材料正文复算前序材料指纹
③ 前序 Gate1 提交 request_binding.materials_binding / 前序独立材料预期 / 前序独立运行预期 → 同步到该值
④ 构造前序记录：binding.materials_fingerprint 取【新值】（note/文件表/边界等常量不变）
⑤ 复算前序记录外层指纹
⑥ 本次 Gate2 的提交 wrapper / 历史 wrapper / 独立 expected_prior_gate1（含 run_binding）→ 同步采用该记录
```

**根因与修正**：R2 构造器在构建记录时显式传了 `materials_fp=MATERIALS1["materials_fingerprint"]`，把新算出的前序材料指纹覆盖成 BASE1 旧值；R3 的构造器**取消了该覆盖参数**（`build_record` 只从传入的 `materials` 正文取指纹），并加断言 `record.binding.materials_fingerprint == 材料正文复算值`。当前 Gate2 的材料、材料指纹/文件名单与独立 `run_binding` **保持 BASE2 原值**（断言 `gate2_materials == MATERIALS2`）。

### 2.2 四例派生值（本轮写后实读，独立重建与保存对象两路一致）

| 例 | 仅改前序材料 | 前序**材料**指纹（新） | 前序**记录**指纹（新） | R2 旧交付值（= 旧材料指纹所致） |
| --- | --- | --- | --- | --- |
| C-112 | `code.file_sha256` → `"7"×64` | `5d3e9e03236189dce4854ec87958785fde86b80939cede463393d5017da893c0` | `935fdc685f0de790981ea4e9c82c6a1f34605c6e35d13bc763255475b596a9f7` | `c64fbba0…8657`（已复现） |
| C-113 | `rules.manifest_fingerprint` → `"8"×64` | `08ec9f7005cc1a4f04ff26eafab0232a1863eda6e74f4ea849d05f1eca49ea93` | `9c35154f97f21ed48a490b25353ec95ef975deedae4a870c1fc6ed633c37a6d5` | `66ac12a5…6cbb`（已复现） |
| C-114 | `config.file_sha256` → `"9"×64` | `3eabe63cf9d2a95dfcef2cfe68b78d1541747e0d9e462eee09508e179edc33aa` | `9c2fea02138d4c2640b70b9dc33760ac6813725721e79c79271a7050e32b3721` | `35a9697c…f4c5`（已复现） |
| C-115 | `input.file_sha256` → `"0"×64` | `9fe5b9ab8c8d47b7fa624f84c9f743142c4b8cdf61441c7af87e85cc6e320b43` | `ba3f59cb2650cb8981b830387c62a02916d8aecd700c6c34f4dba1758efe760d` | `9c5e799b…90e8`（已复现） |

- 四例的**材料**指纹与**记录**指纹均与评审独立重建值**逐字符一致**（`independent_rebuild.json` 的 `matches_review_reference = true`），并**同时**与案例正文 §0.4／§5 声明值一致（`matches_declared = true`）。
- **旧值诊断已被复现**：把记录退回"新 run_binding + 旧材料指纹"的混合写法，得到 R2 交付的四个值（`diagnosis_reproduced = true`）——证明阻断确由该覆盖造成，而非其他原因。
- **基准未漂移**：BASE1 `5f0299e1…f739`、BASE2 `ce95ec25…c45e`、record1 `15bebb48…8c19` 与 R2 评审冻结值一致；C-116 同版本对照的 `prior_run_binding == current_run_binding` 仍为 `true`。

### 2.3 完整对象与两处同步

新证据根为每例保存**完整集合**（`prior_variants.json`）：变化后的前序材料、前序 Gate1 提交、前序独立预期、前序记录、前序 wrapper，以及采用该 wrapper 的**当前 Gate2** submission／materials／expectations／prior_history。闭合检查（`verify_r3.py`，四例各 15 项，全部 `true`）包括：材料指纹=派生值、记录采用新材料指纹、记录 run_binding 与材料一致、`note` 逐字符等于协议常量、wrapper 指纹=记录复算值、提交 wrapper=该 wrapper、历史含该 wrapper、独立 `expected_prior_gate1.record_fingerprint` 与 `run_binding` 闭合、前序提交绑定与前序独立预期同步、**当前 Gate2 材料/材料预期/运行预期/文件名单不变**、保存对象与独立重建一致。夹具标识只在证据外层与文档中，**未写进 `note`、未扩展协议输入键**。

---

## 3. 独立核验（不导入构造器）

`verify_r3.py` **不 import 构造器**：从**案例正文**抽取 §0.2 的 BASE1 材料块与 record1 块，按 §0.1 声明的缩写规则展开，按 §0.4 解析每例"仅改字段 + 取值"，然后**独立重建**：深拷贝 BASE1 材料 → 只改指定 `run_binding` 字段 → 复算材料指纹 → 以 record1 为基替换材料指纹与 run_binding（`note`/文件表/边界不变）→ 复算记录指纹。结果与 ① 正文声明值、② 评审参考值、③ 保存的完整对象 三路一致；评审参考值**仅作交叉核对**，未硬编码跳过计算。另有 15 项逐步闭合检查针对保存对象重算（对象来源、旧值/新值、比较结果均记入 `independent_rebuild.json`）。

---

## 4. 非阻断文案修正

1. **C-117 补入主表**：§4 标题改为"C-50—C-66 与 C-117"，并在该表内加入 C-117 行（只改 `materials.batch_id`、摘要 `8a6ee4e1…ab60`、第 5 步拒绝）。**主表 §1—§9 现为 117 行**、编号 C-01—C-117 **唯一连续无后缀**（脚本逐行核对：`main_unique == 1..117`、行数 117）；不再宣称"主表 116/117 行不符"。未新增业务案例。
2. **C-75**：最早子步统一为 **11b**（字段不变、身份规则不变），去掉此前的重复子步写法。
3. **回执身份**：见 §1 的交接声明 vs 实际读取差异说明（旧回执按实际字节冻结，不回写）。
4. **协议标题残留 R1**：已登记且冻结，**未为此修改协议**。

---

## 5. 案例正文可展开配方

案例 §0.4 的 C-112—C-115 行给出**六步配方 + 两个新摘要**（前序材料指纹、前序记录指纹）；§5 主表对应行同步给出同一对摘要与 11f 定位字段；§0.4 表后说明"先算材料、后算记录、不存在用 BASE1 旧材料指纹覆盖新值的写法"，并指出完整对象集合另存于 TASK-020-R3 证据根。§11 未执行声明补充：这四例的期望只是**书面反例满足构造关系**，**未运行**不存在的核心、**未实际捕获**任何异常。

---

## 6. 只读核验与保护

本轮只运行**新证据根内的文档算术工具**；未导入/运行宿主、控制器、业务核心、旧自检、R2 旧夹具或历史入口。核验＝人工逐条对照 + 标准库 JSON/摘要书面核算。

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| `independent_rebuild_from_document` | PASS | 四例由正文独立重建；材料/记录指纹与声明值、评审参考值一致；旧值可复现（诊断成立） |
| `saved_objects_closure` | PASS | 四例各 15 项闭合检查（材料→记录→wrapper→历史→独立预期→当前 BASE2 不变）全部为真 |
| `baselines_not_drifted` | PASS | BASE1/BASE2/record1 与冻结值一致；C-116 同版本对照仍成立 |
| `main_table_and_copy_fixes` | PASS | 主表 117 行、编号 1..117 连续唯一无后缀；C-75=11b；正文给出前序材料指纹 |
| `no_affirmative_completion_claims` | PASS | "已实现/测试 PASS/已获批准/P1 可以启动/已验证通过/已运行核心"仅在否定语境 |
| `references_and_links` | PASS | 5 项引用分层登记（含 R2 旧夹具产物作"读取的旧证据"）；链接全部可解析 |
| `external_contract_input` | PASS | 正式契约实读 SHA 与 13289 字节匹配 |
| `receipt_identity_disclosed` | PASS | 交接声明与实际读取的差异已如实登记（不回写旧文件） |
| `frozen_and_forbidden` | PASS | 协议冻结值一致；R2 旧夹具/核验器存在且未改；宿主/控制器未变；无禁止文件 |
| `protection_scan_once` | PASS | 见下 |

**保护比较**（基线 `data/reviews/task020_r2_gpt_20261013_190817/source_hashes_after.json`；**执行前已核验该文件与同目录 `review_result.json` 两个确切文件，未用 R1 基线冒充**）：

- **一次**最终完整扫描（局部核对全部完成、案例与本回执齐备后执行）：基线 `source_hashes_after.json`（SHA `f67eb5a9b10d7cebd81676e1108f0372fd152f049af1bf90938d13dc7ea4bcaf`、**133371** 项，同目录 `review_result.json` 记 `verdict=NOT_ACCEPTED`）→ 实扫 **133380** 文件；`changed` **恰为案例正文**（`bd1fc37d…d2a6`）、`missing=[]`、读取错误 **0**、**范围外新增 0**。
- 新增产物分列：**本轮允许新增 7 项**（本回执 + 证据根 6 个文件）；**旧评审元数据**按**两个确切路径**单列（`source_hashes_after.json`、`review_result.json`）；**外部输入**按确切路径核对（正式契约 `174a021b…40ad`、本卡 `97b8916c…`、R2 评审 `dc49f446…`、R2 回执 `90235e44…`），逐项身份记于 `protection_result.json` 的 `external_inputs_verified`。**未豁免整个 reviews 目录**（按确切路径分类）。
- 扫描后仅做**有限登记**（把本回执与最终产物身份补入回执；对案例正文只实读核对、未改动，其 SHA 在扫描前后一致），不再全树扫描。证据根 `summary.json` 的 `document_hashes` 是登记之前产生的快照。

---

## 7. 过程问题、未解决项与未执行动作

**过程问题（如实记录）**

1. **局部核对阶段的失败尝试已保留登记**：第一版核验器把配方字段正则写成 `[a-z_.]+`（不匹配 `file_sha256` 中的数字）、摘要正则未容忍 `**…**` 包裹、C-75 检查与正文措辞冲突、以及旧证据引用指向 R2 根下不存在的文件名（实际为 `fixture_values.json`）；这些均在 `--no-scan` 的**局部**核对中暴露并定点修正，**未触发任何全树扫描**。
2. R3 的构造器取消了 R2 的 `materials_fp` 覆盖参数，并加入两条断言（记录材料指纹=材料正文复算值、当前 Gate2 材料未被改动），使同类错误在构造阶段即失败。
3. 主表行数与编号统计以脚本逐行核对（`main_unique == 1..117`），不再依赖"全文去重"。
4. 设计说明中区分了"独立算术结果"（本轮实际执行）与"未执行的 API 案例期望"（仅书面），未填任何未测运行调用数为 0。

**未解决项**：无（本卡范围内）。协议未决项仍为 U1—U4（持久化/恢复；控制器与宿主接线及批准字段、材料实际枚举与磁盘读取；真实初判结构 P3；AI/终判另行范围）。

**未执行动作（not_executed）**：未实现或调用任何拟定 API、未定义 validator/公开入口；未运行本卡任何案例、未实际捕获任何异常；核验器未导入构造器；未导入/运行宿主、控制器、上游核心、旧自检、R2 旧夹具；未新增或修改 `scripts/`、`tests/`；未生成真实提交/Gate 记录/真实初判/`0009` 或审阅包；未提前运行规则筛查；未执行持久化/恢复/放行；未开放 AI/终判。

---

## 8. 绝对路径

- `D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_020_R3.md`
- `D:\harness work\audit_sa_project\data\decision_protocol_checks\task020r3_run_01\`
- 只读冻结：`D:\harness work\audit_sa_project\docs\proposals\HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`、`D:\harness work\audit_sa_project\docs\AUDIT_CONTRACT.md`

---

## 9. 停止点

本卡只做案例与证据定点修正：不实现、不运行核心、不生成真实 Gate/初判或 `0009`、不开放 AI/终判。完成后交 GPT 整体验收并停止本轮实施；通过后由 GPT 按持续授权制定 P1 纯核心实施卡。本卡**不批准任一批次**，真实人类判断与 Gate 批准仍由主理人作出；协议/案例仍标拟定未实现。
