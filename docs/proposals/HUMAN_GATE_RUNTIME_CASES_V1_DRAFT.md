# 真实运行共享绑定与 Gate1→Gate2 接线案例（V1 草案）

```
标识：DESIGN_CASES_NOT_EXECUTED
任务：TASK-025（C 类：GPT 架构约束 + DSH 文档落地）
日期：2026-10-15
状态：设计案例。以下全部为**书面构造**，**未执行**、**未捕获任何异常**、不调用任何业务函数。
配对设计：docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md
```

> 阅读须知
> - 每类的“预期定位”“为何未被更早错误遮蔽”均为**书面预期**，不表示已实测。
> - 涉及人类字段的文本只引用既有登记的 `PROTOCOL_TEST_FIXTURE_ONLY` 文本，不生成真实批准、新人员或新时间。
> - 抽象文件值一律标注为夹具常量；材料/记录派生摘要给出正文与独立可推导配方，先更新依赖再算摘要。

---

## 0.1 人类字段：**只引用已登记夹具**（本卡不造新人/新时间/新原因）

三份已登记夹具是**人类字段的唯一来源**；本文只取其中的人类字段（身份声明、时间原文、原因原文、事件 ID），
外层测试标记 `PROTOCOL_TEST_FIXTURE_ONLY` 只放在测试证据层，**不写进 P1 封闭提交**。

| 夹具 | 决定 | `event_id` | `actor_kind` | `decided_at_raw` | `reason`（原文） |
| --- | --- | --- | --- | --- | --- |
| `FIXTURE-EV-G1-0001`（项目权威夹具） | APPROVE | `FIXTURE-EV-G1-0001` | `HUMAN_DECLARED` | `2026-10-13T18:00:00+08:00` | `FIXTURE：结构核验通过，同意进入标准化（设计夹具，无审批效力）` |
| `FIXTURE-EV-G1-0002`（GPT 登记） | HOLD | `FIXTURE-EV-G1-0002` | `HUMAN_DECLARED` | `2026-10-13T18:00:00+08:00` | `设计夹具：暂缓，验证同一 scope 内追加事件及历史封套闭合；无审批效力。` |
| `FIXTURE-EV-G1-0003`（GPT 登记） | REJECT | `FIXTURE-EV-G1-0003` | `HUMAN_DECLARED` | `2026-10-13T18:00:00+08:00` | `设计夹具：拒绝，仅验证三事件历史排序与封套闭合；无审批效力。` |

三份夹具的 `actor` 对象**逐字符相同**：
`{"actor_kind": "HUMAN_DECLARED", "actor_id": "FIXTURE-HUMAN-01",
"declaration_note": "设计夹具：本地显式身份声明，非真实人员、非强认证"}`。

**只读引用路径与身份（本轮实读）**：

| 夹具 | 路径 | 文件 SHA-256 | 字节 |
| --- | --- | --- | --- |
| 0001 | `docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`（正文 §0.2 的 `record1` 块） | `bd1fc37dc2437454b87b5453d7df90a6dcd6f3f79e84c3e75a335381fcf2d2a6` | 43060 |
| 0002 | `data/human_gate1_decision_tests/task024_dev_01/fixtures/TASK024_G1_HOLD_0002.json` | `8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa` | 927 |
| 0003 | `data/reviews/task024_gpt_20261014_050915/registered_fixture_0003.json` | `6c69c75cde41014fd8740b95d58b9e8a805bd30003fb14ac6f8fb40c93cf23c3` | 709 |

- **禁止**：`actor_kind = "HUMAN"`（冻结 P1 只接受 `HUMAN_DECLARED`，见 `ACTOR_KIND_HUMAN`）、
  自造时间（如 `2026-10-15T00:00:00+00:00`）、自造原因文本或外层标记冒充人类字段。
- **引用方式**：书面案例展开时**逐字符复制**上表原文；不重新编号、不改大小写、不去除标点。

## 0.2 技术字段：书面夹具常量（可独立复算）

仅**技术绑定层**使用下列书面常量；它们**不是**任何真实文件的 SHA，也**不是**尚不存在组件的 SHA。

| 夹具常量 | 值 | 来源/说明 |
| --- | --- | --- |
| `FIX_BATCH_ID` | `FIXTURE-BATCH-A` | 与已登记夹具 0001 的 `batch_id` 一致 |
| `FIX_SCOPE` | `FIXTURE-SCOPE-2026-10-13` | 与 0001 的 `prior_history.declared_scope` 一致 |
| `FIX_COMPANY` | `澄明商贸有限公司` | [已存在] 项目固定配置口径 |
| `FIX_PERIOD_START` / `FIX_PERIOD_END` / `FIX_CUTOFF` | `2026-09-01` / `2026-09-30` / `2026-09-30` | [已存在] 固定口径 |
| `FIX_CURRENCY` | `CNY` | [已存在] 固定口径 |
| `FIX_ACTOR_KIND` | `HUMAN_DECLARED` | 冻结 P1 `ACTOR_KIND_HUMAN`；**唯一接受值** |
| `FIX_RULES_VERSION` | `TASK-006-rule-core-1.1` | [已存在] 规则清单版本 |
| `FIX_CONTRACT_SHA256` | `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad` | [已存在] 正式契约 V1 确切字节 SHA（实读值） |
| `FIX_BATCH_INPUT_SHA256` | `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341` | [已存在] 夹具工作簿 `C06b.xlsx` 确切字节 SHA（实读值） |
| `FIX_CODE_MANIFEST_VERSION` | `TASK-025-code-manifest-1.0` | 新层常量（旧实现为 `null`，见设计 §4.2） |
| `FIX_ABSTRACT`（抽象占位，书面） | `"a"×64` / `"b"×64` / … / `"0"×64` | **仅书面**表示“某文件的字节 SHA”；不得当作真实文件 SHA |

**规范指纹配方（全案例统一）**：
`fingerprint(x) = sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False).encode("utf-8"))`
— 与 [已存在] `scripts/build_demo_human_gate_decision.py::fingerprint` 同口径（只读引用）。
**文件 SHA-256** 与 **对象规范指纹** 是两类值，本文分别标注，不互相替代。

## 0.3 完整正向书面基样（normal 可核对；以基样文件为准）

`normal` 案例的**完整对象**不再在本正文内以省略号/占位写法重复维护，而是落在本轮证据根的
**一个可解析 JSON 文件**中，正文只引用其路径与文件 SHA：

```
data/reviews/task025_r2_gpt_20261015_020841/runtime_baseline_corrected.json
文件 SHA-256：84cdd60347ffccd8afbeccdce1372c572a1da7ab1a4a1ac97571fa1f71504a84
```

该文件逐项包含（键名与冻结常量一致）：

| 段 | 内容 | 冻结形状 |
| --- | --- | --- |
| `registry` | 登记对象 13 键（含 `run_binding`、`run_binding_sha256`） | 见设计 §3.2(2) |
| `gate1_request` / `gate2_request` | 恰六键请求（`request_version`/`status`/`materials`/`expectations`/`evidence`/`boundaries`）；其余内容由对应嵌套对象读取，不冗余放顶层 | `REQUEST_KEYS`、`BOUNDARY_KEYS`（**七项严格 false 的对象**）、`EVIDENCE_KEYS` |
| `gate1_request.materials` / `gate2_request.materials` | 七键 `MATERIALS_KEYS`；Gate1 `files` **恰 32 项**、Gate2 `files` **恰 3 项** | `FILE_ITEM_KEYS`（3 键） |
| `gate1_request.expectations` / `gate2_request.expectations` | 八键 `EXPECTATIONS_KEYS` | 同上 |
| `submission` | **11 键** `SUBMISSION_KEYS`（**不含** `decided_at_source`） | `SUBMISSION_KEYS` |
| `prior_history` | **三键** `PRIOR_HISTORY_KEYS`，`records` 为**显式空列表** | 同上 |
| `record` / `wrapper` | 17 键 `RECORD_KEYS`（**含** `decided_at_source`）与三键 wrapper | `RECORD_KEYS`/`WRAPPER_KEYS` |
| `source_real_values` | 13 项冻结文件实读 SHA、来源批次 ID、既有证据路径 | — |
| `written_fictitious_labels` | 书面虚构常量标签（`[候选]` 组件与 Gate2 抽象产物） | — |

**关键要点**：

- ① `run_binding` 六项是**同一个对象**（Gate1 与 Gate2 共用），故 `canonical` 逐字符相等；
  ② 两 Gate 的 `materials.files` 与 `materials_fingerprint` **不同**（材料集不同，摘要分别计算）；
  ③ `submission.binding` = `{"request_id", "materials_binding"}`；submission 的 11 键中**没有**
  `decided_at_source`——它是 **record 的字段**（`decided_at_source = "HUMAN_PROVIDED_RAW"`）；
  ④ 人类字段（`event_id` / `decided_at_raw` / `reason` / `actor`）逐字符取自
  `FIXTURE-EV-G1-0001`（§0.1），**未新造**；
  ⑤ 所有摘要字段都是完整 64hex：`[已存在]` 文件为实读真实值，
  `[候选]` 组件与 Gate2 抽象产物的值为**书面虚构常量**（标签见文件内
  `written_fictitious_labels`），**不声称**是真实组件文件哈希。

**复算入口**：同目录 `verify_baseline_r2.py`（只读）直接解析该文件并核对上表全部关系，
结果写入 `design_checks_r2.json`；服务端**不重跑**任何业务模块。

## 0.4 唯一摘要配方与推导顺序

```
fingerprint(x)            = sha256(canonical_json(x))                     # 对象规范指纹
sha256_file(path)         = sha256(path.read_bytes())                     # 文件字节 SHA
code_manifest_fingerprint = fingerprint({"entries": code_entries,          # 14 项，2 键，UTF-8 升序
                                         "manifest_version": "TASK-025-code-manifest-1.0"})
rules_manifest_fingerprint= fingerprint({"entries": rule_entries,          # 4 项，4 键，UTF-8 升序
                                         "version": "TASK-006-rule-core-1.1"})
run_binding_sha256        = fingerprint(run_binding)                       # 只作用内层对象
materials_fingerprint     = fingerprint(materials 去掉顶层 materials_fingerprint 后的对象)
registry_sha256           = fingerprint(registry)
```

**更新顺序（先依赖后摘要，避免“更早结构错误遮蔽目标”）**：
① 先确定/实读文件字节 → ② 逐项 SHA 与 `files` 列表（排序、去重、计数）→
③ `code_manifest` / `rules_manifest` → ④ `run_binding` 六项 → ⑤ `materials`（除 `materials_fingerprint`）→
⑥ `materials_fingerprint` → ⑦ `expectations`（八键，指向 ⑥ 与 ④）→ ⑧ 记录对象 → ⑨ 记录外层指纹。
**任何一步改动都必须回到该步重算下游全部值**，不得只改外层。

**normal 与“六项相等、材料摘要不同”的可核对性**：直接用上文 §0.3 的基样文件即可核对——
`gate1_request.materials.run_binding` 与 `gate2_request.materials.run_binding` **逐字符 canonical 相等**，
而两者 `materials_fingerprint`（`gate1_materials_fingerprint` / `gate2_materials_fingerprint`）
按 §0.4 配方各自复算后**必然不同**；`verify_baseline_r2.py` 已把这两条作为独立断言。

---

## 案例 1：同批次、同共享运行绑定、合法 Gate1 APPROVE 的正常先后依赖

- **构造**：**完全采用 §0.3 的完整正向书面基样**——登记本批六项（设计 §4.2）；
  Gate1 材料请求按 §0.3② 固定；人类字段**逐字符取自 `FIXTURE-EV-G1-0001`**
  （`actor_kind="HUMAN_DECLARED"`、`decided_at_raw="2026-10-13T18:00:00+08:00"`、原因原文见 §0.1）；
  `materials.run_binding` 与登记整体相等；质量报告 `result=pass`、`issues=[]`、`reconciliation.status=ASSESSED`。
- **预期结果**：`RT_G1_DECIDED → RT_G1_EFFECTIVE`；保存返回含 `record_fingerprint`；
  随后标准化 → 入库 → `RT_G2_PENDING`。
- **预期定位**：若失败应定位到具体字段路径（如 `materials.run_binding.code.file_sha256`）。
- **为何未被更早错误遮蔽**：这是**唯一正向**案例；其上游（S0 接收、S1 登记、S2 请求）全部为前置检查，
  任一失败会在到达 S4 之前以更早字段拒绝，因此正向通过本身即证明上游前置均已满足。

---

## 案例 2：HOLD/REJECT 已保存但不能进入标准化

- **构造**：同案例 1 的基样与绑定，但人类字段改为**已登记夹具**：
  `HOLD` 用 `FIXTURE-EV-G1-0002`（`TASK024_G1_HOLD_0002.json`），
  `REJECT` 用 `FIXTURE-EV-G1-0003`（`registered_fixture_0003.json`）；
  事件 ID、时间、原因均取各自夹具原文（§0.1），不新造。
- **预期结果**：决定**可以保存**并读回（保存不等于放行），阶段停在 `RT_G1_DECIDED`；
  `verify_gate1_effective_approval` 返回 `effective=false`，`reasons` 含“决定非 APPROVE”；
  标准化入口必须**未被执行**。
- **预期定位**：`decision` 字段与 `effective=false` 的原因列表。
- **为何未被更早错误遮蔽**：案例 1 已固定其余全部前提（绑定、材料、质量），
  故本案例唯一变量是 `decision`；拒绝原因不可能是绑定/材料/质量问题。

---

## 案例 3：阻断材料下 APPROVE 不得放行；FAILED 不得产生成功运行

- **构造（3a）**：质量报告 `result=fail`（或 `issues` 非空）但人类提交 APPROVE；其余同案例 1 基样。
- **预期结果（3a，Gate 前提层）**：有效批准核验 `effective=false`（质量阻断不被 APPROVE 掩盖），
  **标准化入口调用次数 = 0（未调用）**，不产生任何标准数据文件。
  **不得**同时声称“接线先阻断”又“真实调用了下游核心”。
- **单列（3a′，核心自身防御层）**：若把同一份 `result=fail` 报告**直接**交给冻结核心
  `normalize_workbook`（绕过接线），核心自身抛 `NormalizationBlocked`（“报告存在 N 条问题，未标准化”）。
  这是**另一层级**的书面预期，用于说明核心也有独立防御；它**不**表示正常接线会走到核心。
- **构造（3b）**：标准化运行期失败（例如转换后哈希变化 / 列位置不一致）→ `NormalizationError`；
  入库在提交前失败 → 数据事务已回滚；**不声称**已回滚的提交后失败另计。
- **预期结果（3b）**：**不产生**成功运行记录；失败只用**新运行输出目录**的失败诊断；保留半写现场。
- **预期定位**：3a 定位到 `quality_report.result` / `issues`；3b 定位到 `stage`（如 `read_input_hash`）。
- **为何未被更早错误遮蔽**：3a 与案例 2 的区别在于**质量**而非决定；
  3b 与 3a 的区别在于**运行期**而非前提，三类错误互不掩盖。

---

## 案例 4：共享运行六项任一不符 → 先前 Gate1 不可复用；材料摘要不同但六项相同的正向对照

- **构造（4a）**：把登记中的 `config.file_sha256` 换成另一个值（`FIX_ABSTRACT` 风格，或运行配置
  变更后的真实新值），其他不变；Gate1 决定记录仍引用旧六项。基样与其余前提见 §0.3。
- **预期结果（4a）**：整体 canonical 比较**不等** → 核验拒绝，`effective=false`，
  原因指向 `run_binding.config.file_sha256`；不得“就近匹配”。
- **构造（4b，正向对照）**：按 §0.3 取 Gate1 `materials`（②）与 Gate2 `materials`（④）——
  两者 `files` 集合与 `materials_fingerprint` **不同**，但 `run_binding` 是**同一个对象**（①）。
- **预期结果（4b）**：Gate2 请求**通过**绑定检查（六项相等），
  且**不要求** `materials_fingerprint` 相等。
- **预期定位**：4a 为 `run_binding.*` 的具体路径；4b 为“相等检查通过但材料摘要分列记录”。
- **为何未被更早错误遮蔽**：4a 只改一个字段，且该字段不是材料集内容；
  4b 的差异只在材料层，因此两次结果不会被绑定层或材料层的其它错误混淆。

---

## 案例 5：新阶段代码未纳入初始登记、或后来添加组件 → 拒绝沿用旧批次批准

- **构造（5a）**：在 §0.3① 的 14 项清单之外新增候选运行层组件文件（例如
  `scripts/runtime_registry.py`），**不**更新本批代码清单与 `manifest_fingerprint`，
  却试图用旧 Gate1 决定继续。
- **预期结果（5a）**：拒绝（`code.manifest_fingerprint` 与登记不符 / 实际清单多出未登记文件）；
  必须建立新运行版本与新批次。
- **构造（5b）**：在登记后修改 `scripts/screen_demo_sqlite.py` 字节，仍用旧登记。
- **预期结果（5b）**：`run_binding` 六项之一（清单内文件 SHA）不符 → 拒绝。
- **预期定位**：清单条目 `relative` 与其 `file_sha256`。
- **为何未被更早错误遮蔽**：5a/5b 的其它五项均与登记一致，
  因此拒绝只能来自“清单/组件集合”这一维度，不会被绑定整体失效掩盖。

---

## 案例 6：模拟批准／开发 phase／总体 D2 许可／聊天倾向／离线包冒充有效 Gate1

- **构造**：分别提交
  (6a) `actor_kind=SIMULATED_HUMAN` 且 `simulation=SIMULATED_TEST_ONLY`；
  (6b) 开发控制器产物 `phase=DEV_GATE1_APPROVED`（把 `simulation_allowed=true` 当作放行）；
  (6c) 以“总体 D2 许可/建设范围许可”为唯一凭证；
  (6d) 以聊天倾向性文字或离线审阅包（`COPIED_BYTES_ONLY`）为凭证。
- **预期结果**：四者**全部**被拒，`effective=false`；原因分别指向
  `actor_kind`/`simulation`、`phase` 与 `mode=DEVELOPMENT_TEST_ONLY`、
  “无当批有效批准记录”、以及“离线核验不构成真实批准”。
- **构造（6e，`HUMAN` vs `HUMAN_DECLARED`）**：其余完全合法，仅把
  `actor.actor_kind` 写成 `"HUMAN"`（或任何非 `HUMAN_DECLARED` 的值）。
- **预期结果**：被拒（冻结 P1 `ACTOR_KIND_HUMAN = "HUMAN_DECLARED"` 只接受该唯一值）；
  `effective=false`，原因指向 `submission.actor.actor_kind`。
  这一点是 TASK-025 首轮案例基样的实际缺陷，本卡改为 §0.1 的已登记夹具原文。
- **预期定位**：身份与来源字段（`actor.actor_kind`），而非绑定或质量字段。
- **为何未被更早错误遮蔽**：五例均使用**合法绑定与合法材料**，
  因此拒绝不可能来自绑定/材料/质量；只能在凭证身份维度暴露。
  6e 只改**一个枚举值**，其定位唯一。

---

## 案例 7：来源晚变更、失败诊断/锁/缺凭证、重复执行/既有输出 → 分别拒绝

- **构造（7a 来源晚变更）**：登记后修改批次 `source/input.xlsx` 字节（`input.file_sha256` 不再匹配）。
- **构造（7b 失败诊断/锁）**：批次内出现失败诊断文件或锁文件残留。
- **构造（7c 缺凭证）**：缺 Gate1 决定记录或记录不完整（缺 `decision_sha256`）。
- **构造（7d 重复执行/既有输出）**：目标数据库文件已存在（SQLite 核心 `resolve_database_path` 拒绝）；
  或运行登记文件已存在。
- **预期结果**：7a 绑定失配拒绝；7b 以“出现失败诊断/锁”优先阻断；7c 凭证不完整拒绝；
  7d `SqliteLoadBlocked`（已存在，拒绝覆盖）或登记独占写拒绝。四者**互不掩盖**。
- **预期定位**：7a `run_binding.input.file_sha256`；7b 诊断/锁文件路径；7c `decision_sha256`；
  7d 目标路径本身。
- **为何未被更早错误遮蔽**：四例分别只触发一个维度；其余维度按 §0.3 基样取**具体定义值**
  （不再以文字“均合法”代替），因此拒绝只可能来自被改的那一个维度。

---

## 案例 8：装载提交前失败与提交后失败不混称回滚；数据库/报告不一致阻断 Gate2 候审

- **构造（8a 提交前失败）**：在写入阶段触发文件/约束错误 → 数据事务已回滚，暂存库六表 0 行。
- **构造（8b 提交后失败）**：在 `COMMIT` 之后的严格关闭阶段失败 → **不声称已回滚**；
  如实说明暂存库已含提交数据与目标文件是否存在。
- **构造（8c 数据库/报告不一致）**：手工把 Gate2 材料引用的 `database_sha256` 改成另一夹具值，
  或报告字段与数据库实读行数/金额不符。
- **预期结果**：8a/8b 的失败描述必须**用词不同**且与真实状态一致；
  8c 实读核对失败 → **阻断** Gate2 候审，不进入 `RT_G2_PENDING`。
- **预期定位**：8a/8b 为 `stage` 与失败状态字段；8c 为 `database_sha256` / 报告字段名。
- **为何未被更早错误遮蔽**：8a/8b 的区别只在**提交时点**；
  8c 的前提是 8a/8b 均已成功，因此“不一致”只能由实读核对暴露。

---

## 案例 9：Gate2 准备不依赖筛查；零线索不是本阶段可自动判断的结论

- **构造**：Gate2 候审材料**只**包含登记、批准、质量报告、标准化产物、数据库与装载报告；
  筛查/复算/事实底稿/初判**均未运行**。另构造“筛查结果为空”的假想输入并尝试作为前置。
- **预期结果**：Gate2 材料请求**正常生成**（不依赖筛查）；
  以“筛查为空/零线索”为前置或结论的请求被拒（材料白名单之外，且本阶段无自动结论权）。
- **预期定位**：材料白名单字段；拒绝原因指向“不属于允许材料集/本阶段不作结论”。
- **为何未被更早错误遮蔽**：本案的绑定、批准、质量、标准化与入库**全部合法**，
  因此结果只反映“材料白名单与依赖方向”，不会被上游前提失败掩盖。

---

## 案例 10：只读恢复不执行下游；末次失败支配真实公开出口与磁盘失败事实；台账/载荷确认覆盖完整集合

- **构造（10a 只读恢复）**：对已完成的 Gate1 事件做只读读回/核验。
- **预期结果（10a）**：不调用标准化、不装载、不重新保存决定；无新产物。
- **构造（10b 末次失败）**：在**全部必要消费完成之后**、真实公开出口之前，
  把最终集合中的任一文件（例如 `checks.json` 类等价物：登记/材料/数据库/装载报告之一）
  追加一个 LF，**不同步任何哈希**。
- **预期结果（10b）**：真实公开出口必须**非零返回**、状态 `FAIL`、
  本批运行目录内**失败记录非空**（由失败支配出口的判据写入，见设计 §7.2 第 1、3、4 条）、
  坏字节**保留**且可定位；不得只在内存标记失败、不得只写诊断而让失败记录为空、
  不得重读候选来决定成功、不得重建台账消除漂移。
- **构造（10c 集合覆盖）**：一次完整有界确认必须覆盖**登记 + Gate1 材料 + 决定记录 + 标准化产物
  + 数据库 + 装载报告 + Gate2 请求 + 本轮台账**全部对象；缺任一项即视为确认不完整。
- **预期定位**：10b 为发生字节变化的文件名与期望/实际 SHA；10c 为缺失对象名。
- **为何未被更早错误遮蔽**：10b 的注入点位于所有语义消费之后，
  因此它专门检验“末端确认是否真正支配出口”，不会被任何更早检查拦截；
  10c 则专门检验确认集合是否完整，与 10b 的“单点变化”互补。

---

## 附：本案例集的未执行声明

- 以上十类**全部未执行**：未调用 `normalize_workbook`、`load_normalized_to_sqlite`、
  `check_dev_action`、`prepare_human_gate1_decision_request`、任何 P1 或 store 接口；
  未创建运行登记、批准凭证、接收批次、决定记录、数据库或宿主检查点。
- 案例中出现的 SHA/指纹中，标注“夹具常量”或来自本轮只读实读者的为真实值；
  凡属**候选组件自身**的 SHA 一律**未给出**（组件尚不存在），符合“不得编造占位 SHA”的要求。
- 复核见 `data/human_gate_runtime_design_checks/task025r1_run_01/design_checks_r1.json`
  （TASK-025-R1 针对性只读核验：字段闭合、摘要可推导、冻结接口数量限制、新保存路径、
  合法已登记人类字段、阶段/目录一致）。
  首轮 `data/human_gate_runtime_design_checks/task025_run_01/design_checks.json` 为**历史记录，
  只读引用不重跑**；按评审结论它不构成新协议合法性证明。


## GPT 定点校正登记（2026-10-15，A 类）

DSH R2 的原始基样、自检脚本/54 项结果与回执原样保留。GPT 只同步已定六键 schema、prepare 返回包装解包、
同一次登记清单/配置/技术 scope 的引用关系，重新计算受影响摘要；未改人类字段、冻结实现或业务范围。
本正文当前引用的修正版及实际独立复核见 `docs/reviews/REVIEW_TASK_025_R2.md`；旧54项自检没有覆盖这些残余，不能作修正版通过证据。
