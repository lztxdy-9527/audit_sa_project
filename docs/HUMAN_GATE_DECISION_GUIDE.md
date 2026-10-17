# 真实人工 Gate 决定记录：纯内存核心使用与验证指南

版本：TASK-021 / TASK-021-R1 / TASK-021-R2（P1）；日期：2026-10-13。R1 变更见 §7（前序/历史 record 完整 schema 与 11a—11i 子序）与 §10（证据收尾与调用登记审核）；R2 变更见 §7（历史 record 的**跨字段关系**：质量×决定矩阵、Gate2 前序摘要派生关系）与 §10（终审失败传播、编号映射说明）。

> **子步编号映射说明（非阻断）**：冻结协议 §9.3 的 **11f 就是“前序运行绑定”**；本实现的 `_step11_prior` 把运行绑定比较放在**实现注释的第 11g 位**（因把记录顶层 schema 与 binding/文件成员拆成 11b/11c、把正文复算提前为 11d）。**两者指同一目标校验**，实际字段与顺序为：11a 形状 → 11b 顶层 schema → 11c binding/文件成员 → 11d 正文复算 → 11e 身份 → **11f 契约** → **11g 运行绑定（＝协议 11f）** → 11h 质量与边界 → 11i 指纹闭合与历史一致。编号仅为阅读标签，校验行为与协议目标一致，冻结协议不因此修改。
核心文件：`scripts/build_demo_human_gate_decision.py`
测试/证据入口：`tests/test_build_demo_human_gate_decision.py`
实现依据：`docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`（冻结 SHA-256
`68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`，39298 字节）§3—§14；
设计案例：`docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`（`bd1fc37d…d2a6`，117 个主表案例）。

> **能力边界（先读）**：本核心只做**纯内存**的校验与构建。它的成功结果
> `HUMAN_GATE_DECISION_MEMORY_VALIDATED` **不等于**已保存、不等于身份认证、不等于批次批准、
> 不等于运行放行。真实 Gate 批准仍为 `null`、真实人类初判仍未保存、`next=false`、AI 未开放。
> 正式契约 V1 已由主理人建立并确认生效，但**契约生效不批准任何批次**。

---

## 1. 接口

```python
from scripts.build_demo_human_gate_decision import (
    build_human_gate_decision_record, HumanGateDecisionBlocked, HumanGateDecisionError,
)

result = build_human_gate_decision_record(submission, materials, expectations,
                                          prior_history=prior_history)
```

| 项 | 内容 |
| --- | --- |
| 入参 | `submission`／`materials`／`expectations`（位置参数）与**语义必填**的关键字参数 `prior_history` |
| 成功返回 | **恰好两键**：`{"record": <17 键 record>, "record_fingerprint": <64 位小写十六进制>}`；`record` 不内嵌自身指纹 |
| 拒绝 | `HumanGateDecisionBlocked(field, reason)`：可定位字段与原因（协议/类型/绑定/前提） |
| 意外错误 | `HumanGateDecisionError(stage, reason)`：保留 `__cause__` 原因链；**不**伪装为协议拒绝、**不**包装成成功 |
| `prior_history=None` | 形参默认 `None` 只是让缺省调用进入函数体：**缺省省略与显式 `None` 都在第 4 步被拒绝**（`field="prior_history"`）。不默认空历史、不默认 `declared_complete=true` |
| 无 | 无 CLI、无文件保存、无恢复入口、无放行入口、不产生 `gate1_approval`/`gate2_approval`/`next`/AI 字段 |

`prior_history` 必须满足封闭对象协议：`{declared_complete: 严格布尔, declared_scope: 非空字符串, records: [wrapper, ...]}`；
`records` 按 `record.event_id` 升序且唯一，可为空列表（表示声明范围内无历史）。

---

## 2. 封闭 schema（协议 §3）

| 对象 | 键集合（缺一即拒绝；多一即按完整路径拒绝） |
| --- | --- |
| `submission` | `submission_version`(常量 1.1)／`event_id`／`batch_id`／`gate`(GATE1\|GATE2)／`request_binding{request_id, materials_binding}`／`decision`(APPROVE\|HOLD\|REJECT)／`decision_source`(常量 `HUMAN_GATE_DECISION`)／`actor{actor_kind(常量 `HUMAN_DECLARED`), actor_id, declaration_note}`／`decided_at_raw`／`reason`／`prior_decision_binding`(Gate1 必须 `null`；Gate2 必须是 wrapper) |
| `materials` | `gate`／`batch_id`／`run_binding{code{file_sha256, manifest_fingerprint}, rules{version, manifest_fingerprint}, config{file_sha256}, input{file_sha256}}`／`contract_binding{contract_version, contract_file_sha256, contract_effective(严格 `true`)}`／`files[{relative, file_sha256, byte_size}]`／`quality{status, structural_blockers, quality_blockers, verification_failures}`／`materials_fingerprint`（派生） |
| `expectations` | `expected_batch_id`／`expected_gate`／`expected_request_id`／`expected_materials_fingerprint`／`expected_files`／`expected_contract{contract_version, contract_file_sha256}`／`expected_run_binding`／`expected_prior_gate1`(Gate1 `null`；Gate2 `{gate, batch_id, event_id, record_fingerprint, run_binding}`) |
| `prior_history` | `declared_complete`／`declared_scope`／`records` |
| wrapper | `wrapper_version`(常量)／`record_fingerprint`／`record`(完整 17 键记录) |
| `record` | `record_version`／`record_status`／`gate`／`batch_id`／`event_id`／`decision`／`decision_source`／`reason`／`decided_at_raw`／`decided_at_source`／`actor`／`binding{request_id, materials_fingerprint, materials_files, contract_binding, run_binding}`／`prior_gate1`／`quality_summary`／`execution_allowed`／`boundaries`／`note` |

通用规则：

- **非空字符串**不裁剪、不改大小写、不转数字、不补前导零；整串为空或仅空白视为缺失。
- **严格类型**：布尔/整数不冒充字符串，反之亦然；常量字段必须取常量值**且类型正确**。
- **严格整数**：`byte_size`、各 `*_count` 必须是 `int` 且非 `bool`；`byte_size >= 0`。
- **哈希字段**：完整 64 位小写十六进制（拒绝尾 LF/CRLF/空格、大写、截断）。
- **普通 ID 例外**：`event_id`/`batch_id`/`request_id`/`actor_id` 即使形状恰为 64 位十六进制或含前导零仍是合法字符串，只做精确比较；**前缀（如 `SIM-EV-*`）不构成来源证明**。
- **列表**：`files` 按 `relative`、阻塞/失败列表按原文、历史 `records` 按 `event_id`，均须**唯一且按 UTF-8 字节序升序**；**无序输入被拒绝，核心不静默排序**。

---

## 3. 校验顺序（协议 §5，固定 14 步）

| 步 | 范围 | 检查 |
| --- | --- | --- |
| 1—4 | **形状/类型/常量/键集合/列表规则** | `submission`（含时间字段**类型**、按 Gate 的前序字段形状）→ `materials`（含 `contract_effective` 类型与 `true`、名单规则、质量状态一致性）→ `expectations`（含按 Gate 的独立前序预期形状）→ `prior_history`（完整性声明 + `records` 唯一/升序） |
| 5—12 | **值/关系** | 5 身份一致（batch/gate/request）→ 6 时间语义 → 7 契约与独立预期 → 8 运行绑定与独立预期 → 9 材料正文复算与三处摘要闭合 → 10 `files`↔`expected_files` 双向比较 → 11 前序闭合（11a—11i）→ 12 历史与重复事件 |
| 13 | 语义决定 | 质量/决定矩阵 |
| 14 | 输出 | 构建记录 + 派生计数 + 外层指纹 |

因此：时间**类型**错误在第 1 步、**格式/日历**错误在第 6 步；`contract_effective` 的**类型/常量**在第 2 步、与独立契约预期的**值比较**在第 7 步；`records` 的**唯一/升序**在第 4 步、与**提交或既有批准**的语义重复在第 12 步；内层文件关系（10）晚于外层摘要复算（9）；质量矩阵（13）晚于全部材料与绑定检查。每个反例只有**唯一最早**的 `field` 与步骤。

---

## 4. 材料正文、两类指纹与运行绑定

- **材料正文**（唯一算法）：`materials_body := materials` 顶层**仅删除** `materials_fingerprint`，其余内容与列表顺序原样保留。
- **唯一相等关系**：`fingerprint(materials_body) == materials.materials_fingerprint == submission.request_binding.materials_binding == expectations.expected_materials_fingerprint`。
- **两类值不互相替代**：`materials.files[i].file_sha256` 是**文件确切字节 SHA**（调用方报告），`materials_fingerprint` 是**材料集对象的规范指纹**；核心不重新读取文件。
- **canonical JSON**：UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、`allow_nan=False`；规范指纹 = 该字节串的 SHA-256。不得用文件排版哈希替代对象指纹。
- **`files` 双向比较**：与 `expected_files` 键集合必须完全相同（缺项/额外项/重复项一律拒绝），再逐项比较文件 SHA。
- **运行绑定**：`materials.run_binding` 与 `expectations.expected_run_binding` 六字段（`code.file_sha256`／`code.manifest_fingerprint`／`rules.version`／`rules.manifest_fingerprint`／`config.file_sha256`／`input.file_sha256`）必须逐字段严格相等；`*_file_sha256` 是单文件字节 SHA，`*_manifest_fingerprint` 是清单对象的规范指纹，两者含义不同。

---

## 5. 时间规则（协议 §6）

恰好两种写法，**全串匹配**：

```text
A) YYYY-MM-DD
B) YYYY-MM-DDThh:mm:ss±hh:mm
```

- 真实日历日期（闰年规则适用：`2028-02-29` 合法，`2026-02-29`、`2026-09-31` 非法）。
- 分量：`hh` 00–23、`mm`/`ss` 00–59（不接受闰秒）；偏移 `±hh:mm`，`hh` 00–14、`mm` 00–59，最大 ±14:00。
- 不接受首尾空白、`Z`、小数秒、缺秒、其他分隔符。
- **原文逐字符保存**为 `decided_at_raw`，并写入 `decided_at_source = "HUMAN_PROVIDED_RAW"`；不补当前时间/时区、不生成 normalized 值。失败一律定位 `submission.decided_at_raw`。
- `docs/AUDIT_CONTRACT.md` 头部的人工生效时间原文**不是**本协议的正向时间夹具。

---

## 6. 质量与决定矩阵（协议 §12）

一致性（第 2 步）：`OK ⇔ 三列表全空`；`BLOCKED ⇔ (结构或质量列表非空) 且 verification_failures 空`；`FAILED ⇔ verification_failures 非空`；矛盾输入一律在第 2 步拒绝。

| `materials.quality` | `APPROVE` | `HOLD` | `REJECT` |
| --- | --- | --- | --- |
| 完整报告、无阻断（`OK`） | 记录，`execution_allowed=false` | 记录，`false` | 记录，`false` |
| 完整报告、有未解决阻断（`BLOCKED`） | 拒绝（`field=submission.decision`） | 记录，`false` | 记录，`false` |
| 核验失败/材料不完整（`FAILED`） | 均拒绝（`field=materials.quality.status`），**不产生成功记录** | 同左 | 同左 |

`quality_summary` 的计数由 `materials.quality` 三个列表长度**直接派生**（严格整数）。所有成功记录（包括 APPROVE）的 `execution_allowed` 与 `boundaries` 六项**严格为 `false`**。

---

## 7. Gate 顺序与前序闭合

- **Gate1**：`submission.prior_decision_binding` 与 `expectations.expected_prior_gate1` **必须为 `null`**。
- **Gate2**：必须闭合到**完整 Gate1 记录**——提交 wrapper（完整记录 + 外层指纹）、独立 `expected_prior_gate1`、以及 `prior_history.records` 中的**同一** wrapper 三处一致。字符串 `"APPROVE"`、摘要、模拟凭证或开发态 `phase` 都不能替代记录。
- 第 11 步子序（唯一最早字段；R1 起对前序 record 执行**完整嵌套 schema**，摘要复算只是其中一项）：

| 序 | 检查 |
| --- | --- |
| 11a | wrapper 形状（封闭键、`wrapper_version` 常量、指纹格式） |
| 11b | 记录**顶层完整 schema**：封闭键集合、`record_version`/`record_status`/`decided_at_source`/`note` 常量、`gate`/`decision` 枚举、`decision_source` 常量、`batch_id`/`event_id`/`reason` 非空、`decided_at_raw` 合法时间、`actor` 完整键（`actor_kind` 常量 + `actor_id`/`declaration_note`）、Gate1 记录 `prior_gate1` 必须 `null` |
| 11c | `binding` 完整键、`request_id`、`materials_fingerprint` 全串格式、`materials_files` 非空/唯一/UTF-8 升序且逐项 `relative`/字节 SHA/严格非负 `byte_size` |
| 11d | **记录正文复算**：`record_fingerprint == fingerprint(record)` |
| 11e | 记录身份：`gate=GATE1`、批次一致、`decision=APPROVE`、`actor_kind=HUMAN_DECLARED` |
| 11f | 契约一致：`contract_binding` 完整键/版本/SHA/**`contract_effective` 严格 `true`** 且等于本次独立契约预期 |
| 11g | **前序运行绑定**逐层封闭键/严格类型/哈希 + 与本次 `materials.run_binding`、`expectations.expected_run_binding` **六字段全等**，且 `expected_prior_gate1.run_binding` 作为独立前序预期同步参与比较 |
| 11h | 质量与边界：`quality_summary` 完整键/合法状态/**派生计数自洽**、前序要求 `status=OK` 且三计数为 0、`execution_allowed` 严格 `False`、`boundaries` 六键严格 `false` |
| 11i | 三处指纹闭合（`expected_prior_gate1` / 提交 wrapper / 复算值）与 `gate/batch_id/event_id` 一致，且历史必须包含规范相等的同一记录 |

- **已提供历史的合法性（第 11 步之后、第 12 步语义判定之前）**：`prior_history.records` 的**每个** member 都必须满足 wrapper 版本/完整指纹（与记录正文复算一致）与**完整 record schema**（11b—11h 的自洽部分），并且满足**跨字段关系**（R2 起）：
  - **质量×决定矩阵**（与 §12 合法输出一致）：`OK`（三计数 0）→ 三种决定均可；`BLOCKED`（结构/质量计数≥1、失败计数 0）→ `HOLD`/`REJECT` 可接受、**`APPROVE` 拒绝**（`field=…record.decision`）；`FAILED`（失败计数≥1）→ **三种决定均拒绝**（`field=…record.quality_summary.status`，理由：核验失败/材料不完整不产生成功记录）。
  - **Gate2 记录的 `prior_gate1` 摘要派生关系**：`gate` 必须为 `GATE1`、`decision` 必须为 `APPROVE`、`batch_id` 必须等于**该历史记录自身**的批次、`actor_kind` 必须为 `HUMAN_DECLARED`，且摘要 `event_id` **不得等于该记录自身的 `event_id`**（事件不能自我充当前序）。只核现有字段自身关系，不查找全局祖先、不认证来源、不要求祖先 wrapper 出现在所给历史范围内。
- 这些校验是**自洽合法性**：一般历史允许合法 `HOLD`/`REJECT`、其他批次、以及**合法 Gate2 记录**，**不**要求 Gate1/APPROVE/同批次/同运行绑定等于当前批次；只有当前前序（第 11 步）才要求等于本批次。第 4 步仍只负责名单规则（形状、`event_id` 唯一与升序）。

**Gate1 与 Gate2 的材料集不同，两者 `materials_fingerprint` 不要求相等**；要求相等的是**运行绑定**。历史作用域仅按调用方声明（`declared_scope`/`declared_complete`）处理。

---

## 8. 身份与来源边界（协议 §11）

- `decision_source` 与 `actor.actor_kind` 是**调用方提供的纯结构标记**，不是身份认证；协议不承诺识别"伪装成人类的文本"。
- **`reason` 文本只作数据**：提到 D2、含指令样式文字等一律按原文保存；不做关键词/意图判断、不做作者检测、不从文字生成或推导任何授权。
- **普通 ID 不是来源凭证**：`SIM-EV-*` 之类前缀不构成模拟判定依据，核心不做前缀判断。
- 不得把候选契约、开发态状态、D2 纪要当作某批次的独立预期或批准。

---

## 9. 能验证什么、不能验证什么

**能**（纯内存对象层）：字段/类型/枚举/未知键；批次-Gate-请求一致；契约与运行绑定一致；材料正文可复算且与三处摘要闭合；内层文件名单与独立名单双向一致；**前序记录与每个已提供历史记录的完整嵌套 schema、常量、来源/身份声明、时间、契约生效声明、运行绑定格式与封闭键、质量派生计数、固定 `false` 边界**；**历史记录的跨字段关系（质量×决定矩阵、Gate2 `prior_gate1` 摘要的 Gate1/APPROVE/同批次/非自我事件派生关系）**；前序记录正文可复算并与三处指纹/字段闭合；历史声明的完整性与范围内重复；质量与决定矩阵；输入不被修改；输出确定性。

**不能**（须由未来适配层 P2 负责）：磁盘实读（文件/契约"当前字节"是否仍等于所报 SHA）；契约是否真的被人类确认生效（只接受调用方给的结构字段）；来源业务真实性；人类身份真实性或文本是否真由人类独立完成；**调用方在两侧同时少报的材料文件**（独立名单完备性由调用方负责）；其声明范围之外的隐藏历史；**前序/历史记录中所声明的材料是否真的存在或其摘要是否对应真实文件**（核心只校验这些对象自身的 schema、格式与自洽性）。因此本核心**不宣称"全量材料已核验"**。

---

## 10. 验证方式

```text
.venv\Scripts\python.exe -B tests\test_build_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_tests\task021_<新名>
```

- 证据容器必须为**全新空目录**；脚本拒绝写入非空目录。容器内包含：`summary.json`、
  `checks.json`、`failures.json`、`case_map.json`（117 个设计案例→实际调用，另有 R1 维度用例）、
  `api_records.json`（每次核心调用的完整输入快照与完整返回/异常/field/stage/reason/traceback/cause 链）、
  `call_registry.json`（权威调用登记 + 入口观察）、`counts.json`、
  `evidence_ledger.json`（逐文件 exists/字节/SHA，**登记后读回审核**）、
  `independent_expectations.json`、`guard_hits.json`、`injection.json`、`entry_observer.json`、
  `isolation_self_tests.json`、`protection_result.json`（后置保护，分层登记）。
- **独立性**：期望值由测试脚本自己的 canonical JSON/指纹实现与冻结案例正文推导，**不调用被测核心的同一 helper**；核心调用次数以核心入口登记为准（测试外层调用数不作数）。
- **真实入口观察**：`sys.setprofile` 在**真实公开入口函数代码帧的 `call` 事件**上独立计数，与测试 Registry 计数分列核对（两者必须相等）。
- **调用登记审核与隔离**：权威 `call_registry.json` 与 `api_records.json` 按调用 ID **双向审核**（重复/缺失/多余/无结果均进入正式 failures）；**隔离副本只删除权威登记的一条调用**，审核必须失败、原件仍通过。另有文件台账隔离（删副本一条文件登记，并**调用真实 audit helper** 判定），两者作用区分、不互相替代。
- **计数分列**：`case_map.json` 把**原 117 个设计编号**与 R1/R2 **新增维度编号**（RV/RS/HS/HP/HR）分列计数，不混为一个标签。
- **稳定载荷与台账**：先写全部最终载荷，再登记台账并**读回审核**；缺失/未登记/哈希不符进入正式 failures。台账不内嵌自身 SHA；后置保护脚本与保护结果按确切路径分层有限登记。
- **终审失败传播（R2 起）**：权威终审读取（`phase="final"`）之后若 `validated.missing`/`unregistered` 非空，**必须**形成正式 failure、`summary.status="FAIL"` 与**非零退出码**，并写 `final_audit_diagnostic.json` 记录该次真实读取的台账快照与检测结果；失败路径**不再重建台账**以保留故障现场。真实故障验证：包装真实 `_ledger_from_disk`，在终审读取返回原字典后仅对该容器 `checks.json` 追加一个 LF → 实测审计发现 `checks.json`、入口返回 **1**、`summary=FAIL`、failures 非空（正常控制容器与故障套件目录分开）。
- **纯内存守卫**：合法调用期间守卫 `builtins.open`/`os.open`/`socket.socket`/`subprocess.Popen`，命中必须为 0；守卫期间不写证据文件。
- **受控内部注入**：仅替换核心的私有实现函数以验证意外错误映射为 `HumanGateDecisionError`（保留 `__cause__`/`__context__` 链），公开边界不变；该调用明确标注为注入。
- 未执行项（receiver/checker 链、宿主/控制器、持久化/重放、AI/终判、历史业务链）在证据中记为 `not_executed`/`null`，不填默认零。

---

## 11. 停止点

本核心止于 **`HUMAN_GATE_DECISION_MEMORY_VALIDATED`** 的纯内存结果：

- 无持久化/恢复/独占保存/失败现场文件协议（U1，P2）；
- 无宿主/控制器接线、无放行字段、不新增 `0009`（U2，P2，Gate1/Gate2 分开验收）；
- 不设计真实人类独立初判结构（U3，P3，D3：批次初判及原因必填、逐条备注可选）；
- 不涉及 AI 建议与终判（U4，另行明确范围，当前未开放）；
- 不填写或修改真实批准、初判、`next`、AI 或终判字段，不接 UI/LLM/网络/ERP/真实数据。

真实人类判断与每一批次的 Gate 批准仍由主理人作出。
