# 真实人工 Gate 决策记录协议 V1（拟定设计稿，R1 修正版）

标识：**PROTOCOL_DESIGN_DRAFT_NOT_IMPLEMENTED**
版本：V1-DRAFT-R1 / TASK-020-R1；日期：2026-10-13。
状态：**拟定设计，尚未实现、尚未验收、未获批准。** 本文不含任何可运行实现，也不表示 P1 已启动。

> 阅读须知
> - 函数名、字段名、状态名、异常名均为**拟定设计、当前不存在**；不得表述为已实现、已通过或已获批准。
> - 范围**仅为独立纯内存的 Gate 决定记录校验与构建**；持久化/恢复、控制器、宿主接线、运行放行、真实初判、AI 与终判**全部留后卡**。
> - 前置事实（只读）：D1 内容已采纳且主理人已建立正式契约 V1（`docs/AUDIT_CONTRACT.md`，SHA-256 `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`，13289 字节，状态原文"已生效"）；D2 允许限合成数据的真实决策保存/校验；D3 批次初判及原因必填、逐条备注可选（**仅作为 P3 约束登记，不在本协议内设计**）。**契约生效与 D2 许可均不批准任何批次。**
> - 本版按 `docs/reviews/REVIEW_TASK_020.md` 与 `docs/tasks/TASK-020-R1.md` 修正四组问题：材料正文与可推导夹具、严格 schema/历史完整性/前序闭合、质量与决定矩阵、来源能力边界。
> - 当前运行态仍为开发态 `0008`：真实批准 `null`、真实人类初判未保存、`next=false`、AI 未开放。

---

## 1. 范围、非目标与名词

### 1.1 范围

| 项 | 内容 |
| --- | --- |
| 目标 | 定义"真实人工 Gate 决定记录"的**校验与构建**：输入人类明确提供的提交、材料封装与**已独立核验的预期值**，输出内存中的规范记录（或可定位的拒绝） |
| Gate1 | 接收、范围与结构核验的人工决定 |
| Gate2 | 标准化、入库与勾稽的人工决定（依赖同批次已核验的**完整真实 Gate1 记录**） |
| 载体 | **纯内存**：不读写文件/数据库/网络，不导入宿主/控制器/上游/测试/答案册，不产生状态迁移 |

### 1.2 非目标

不持久化/不恢复/不做独占写/不写失败诊断；不接控制器/宿主；不设置 `gate1_approval`/`gate2_approval`/`next_step_allowed`/AI 许可；不产生 `0009`；**不设计真实人类初判记录结构**（D3 仅为 P3 约束）；不设计 AI 或终判；不做重要性阈值/缺陷分级；不认证人类身份、不证明来源业务真实性、不提供防篡改或独立审计保证。

### 1.3 名词

| 名词 | 含义 |
| --- | --- |
| 提交（submission） | 调用方提供的、人类**明确**给出的决定内容对象 |
| 预期值（expectations） | 调用方**已独立核验**的绑定值 |
| 材料集（materials） | 本次守门点展示材料的封装（含内部各文件字节 SHA 与**派生**整体指纹） |
| 材料正文（materials_body） | 材料集**顶层剥离**派生字段后的对象（§4.1） |
| 规范指纹（fingerprint） | `sha256(canonical_json(obj))`，64 位小写十六进制 |
| 文件字节 SHA | 对**确切原始字节**计算的 SHA-256 |
| 前序记录包装（wrapper） | `{wrapper_version, record_fingerprint, record}`，用于传递**完整**前序记录 |
| 决定记录（record） | 校验通过后构建的内存记录（不内嵌自身指纹） |

---

## 2. 拟定公开接口

### 2.1 函数签名（拟定）

```python
def build_human_gate_decision_record(
    submission: dict,
    materials: dict,
    expectations: dict,
    *,
    prior_history: dict | None = None,   # 语义必填；缺省或显式 None 均在 history 检查步拒绝
) -> dict:
    """校验并构建真实人工 Gate 决定记录（纯内存；拟定设计，尚未实现）。

    返回（成功）：{"record": <record>, "record_fingerprint": <64位小写十六进制>}
    失败：抛 HumanGateDecisionBlocked（协议/绑定问题，带 field）
         或 HumanGateDecisionError（意外内部错误，保留 __cause__）。
    不写文件/库/网络；不修改入参；返回深拷贝。
    """
```

- 拟定异常（当前不存在）：`HumanGateDecisionBlocked(field=..., reason=...)`、`HumanGateDecisionError(stage=..., reason=...)`。
- **无 CLI、无持久化、无恢复入口**。
- **`prior_history` 的必填约定（R2 定稿）**：形参带默认值 `None`，但**语义上必填**——**缺省省略**与**显式传 `None`** 两种情形都在**第 4 步（history 检查步）**以 `HumanGateDecisionBlocked(field="prior_history", reason="历史完整性声明缺失")` 拒绝；**不默认空历史、不默认 `declared_complete=true`**。如此可避免 Python 在进入函数体前抛原生 `TypeError` 与"可定位的协议拒绝"相互矛盾。合法值仍须满足 §3.4 的封闭对象协议。
- 拟定常量（当前不存在）：`RECORD_VERSION = "TASK-020-human-gate-decision-record-1.1"`、
  `SUBMISSION_VERSION = "TASK-020-human-gate-decision-submission-1.1"`、
  `WRAPPER_VERSION = "TASK-020-human-gate-decision-record-wrapper-1.1"`、
  `RECORD_STATUS_MEMORY_VALIDATED = "HUMAN_GATE_DECISION_MEMORY_VALIDATED"`、
  `DECISION_SOURCE_HUMAN = "HUMAN_GATE_DECISION"`、`ACTOR_KIND_HUMAN = "HUMAN_DECLARED"`、
  `QUALITY_OK/BLOCKED/FAILED = "OK"/"BLOCKED"/"FAILED"`。

### 2.2 返回值与状态语义

| 概念 | 拟定取值 | 说明 |
| --- | --- | --- |
| 记录状态 | `HUMAN_GATE_DECISION_MEMORY_VALIDATED` | **仅**表示内存校验通过 |
| `execution_allowed` | 恒为 `false`（严格布尔） | **固定的"不放行"边界字段**：本协议不提供任何实际放行接口；即使未来宿主持久保存/控制器接线后，此字段也不得被读取为"已获准执行" |
| 是否已保存 | 无字段（不在本协议） | 不得把 VALIDATED 读作 RECORDED |
| 是否已产生人类判断 | 无字段 | 记录只是人类决定的载体，不等于审计结论 |

> **停止点**：纯核心只返回内存校验结果；拟定后续"宿主持久保存"与"运行放行"必须**独立验收**。VALIDATED ≠ RECORDED ≠ APPROVED。

---

## 3. 严格字段集合

> 通用规则（§3.5）适用于本节**所有**对象：每个对象的键集合都是**封闭**的，未列出的键一律拒绝并给出该键的完整路径；**不存在"可选字段 extra"**（此前版本把 `extra` 列为可选又当未知字段处理，属矛盾，本版删除）。

### 3.1 `submission`（人类明确提供；封闭键集合）

| 字段 | 类型/范围 | 必需 | 说明 |
| --- | --- | --- | --- |
| `submission_version` | 常量 `TASK-020-human-gate-decision-submission-1.1` | 是 | 协议版本 |
| `event_id` | 非空 `str` | 是 | 调用方提供，**不自动生成**；原字符串保留；**不做前缀判断**（§11.4） |
| `batch_id` | 非空 `str` | 是 | 精确字符串比较；不做大小写/数字归一化 |
| `gate` | 枚举 `"GATE1"` \| `"GATE2"` | 是 | — |
| `request_binding` | 对象 `{request_id, materials_binding}` | 是 | `request_id` 非空 `str`；`materials_binding` 为 64 位小写十六进制 |
| `decision` | 枚举 `"APPROVE"` \| `"HOLD"` \| `"REJECT"` | 是 | — |
| `decision_source` | 常量 `"HUMAN_GATE_DECISION"` | 是 | **调用方提供的纯结构来源标记**（§11.1）；其它值一律拒绝 |
| `actor` | 对象 `{actor_kind, actor_id, declaration_note}` | 是 | `actor_kind` 常量 `"HUMAN_DECLARED"`；后二者为非空 `str`（**本地显式声明，非身份认证**） |
| `decided_at_raw` | 非空 `str`，须通过 §6 时间规则 | 是 | 人类提供的决定时间**原文**，原样保留 |
| `reason` | 非空 `str` 且非纯空白 | 是 | 决定说明；`HOLD`/`REJECT` 必须写明原因；**内容不参与任何控制流**（§11.3） |
| `prior_decision_binding` | `null`（Gate1）\| wrapper 对象（Gate2，§3.5） | 是 | Gate1 必须为 `null`；Gate2 必须是**完整前序记录包装**，不得是字符串或摘要 |

> 本版**删除** `finding_notes`（及 `finding_key`/`note` 结构）：逐条线索备注属**真实初判**范围，按 D3 归 P3 另卡；Gate 记录不得混入。

### 3.2 `materials`（封闭键集合）

| 字段 | 类型/范围 | 必需 | 说明 |
| --- | --- | --- | --- |
| `gate` | 枚举 `"GATE1"` \| `"GATE2"` | 是 | 必须与 `submission.gate` 一致 |
| `batch_id` | 非空 `str` | 是 | 必须与 `submission.batch_id` 一致 |
| `run_binding` | 对象（§7.3 定义各摘要含义） | 是 | 与 `expectations.expected_run_binding` 逐字段严格相等 |
| `contract_binding` | 对象 `{contract_version, contract_file_sha256, contract_effective}` | 是 | 见 §7.1；`contract_effective` 必须是**严格布尔 `true`** |
| `files` | 非空列表，成员 `{relative, file_sha256, byte_size}` | 是 | 规则见 §7.2（非空、逻辑键唯一、按 `relative` 升序） |
| `quality` | 对象 `{status, structural_blockers, quality_blockers, verification_failures}` | 是 | 一致性规则与矩阵见 §12 |
| `materials_fingerprint` | 64 位小写十六进制 | 是 | **派生字段**：必须等于 §4.1 材料正文的规范指纹 |

> 本版**删除** `materials.gate1_binding`：Gate2 的前序关系全部由 `submission.prior_decision_binding`、`expectations.expected_prior_gate1` 与 `prior_history` 三处承担（§9），不再保留冗余字段。

### 3.3 `expectations`（调用方已独立核验；封闭键集合）

| 字段 | 类型/范围 | 必需 | 说明 |
| --- | --- | --- | --- |
| `expected_batch_id` | 非空 `str` | 是 | 与本批次精确一致 |
| `expected_gate` | 枚举 | 是 | 与提交一致 |
| `expected_request_id` | 非空 `str` | 是 | 与 `submission.request_binding.request_id` 一致 |
| `expected_materials_fingerprint` | 64 位小写十六进制 | 是 | 见 §4.2 唯一相等关系 |
| `expected_files` | 非空对象 `{relative: file_sha256}` | 是 | 独立文件名单；与 `materials.files` 双向完整比较（§7.2） |
| `expected_contract` | 对象 `{contract_version, contract_file_sha256}` | 是 | 必须是**正式生效契约**的版本与确切文件 SHA（§7.1） |
| `expected_run_binding` | 对象，形状同 `materials.run_binding` | 是 | 逐字段严格相等 |
| `expected_prior_gate1` | `null`（Gate1）\| 对象 `{gate, batch_id, event_id, record_fingerprint, run_binding}`（Gate2） | 是 | Gate1 必须为 `null`；Gate2 必须为对象（形状不符在第 3 步拒绝）；`run_binding` 是前序记录运行绑定的**独立预期**，与 §9.3 的 11f 比对 |

### 3.4 `prior_history`（历史完整性载体；封闭键集合）

| 字段 | 类型/范围 | 必需 | 说明 |
| --- | --- | --- | --- |
| `declared_complete` | **严格布尔**（`bool`，非 `0/1`、非 `"true"`） | 是 | 调用方声明：所提供的记录是否覆盖其所声明范围的全部历史 |
| `declared_scope` | 非空 `str` 且非纯空白 | 是 | 调用方**声明**的范围文本（纯结构，不认证其真实性） |
| `records` | 列表，成员为 wrapper（§3.6）；按 `event_id` 升序且唯一 | 是 | 可为空列表（表示该范围内无历史） |

**缺失/非法处理**（缺一不可，见 §10）：参数**缺省省略或显式 `None`** → 第 4 步拒绝 `prior_history`（理由：历史完整性声明缺失；**不得**默认空历史或 `declared_complete=true`）；`declared_complete` 缺失 → 拒绝 `prior_history.declared_complete`；非布尔 → 同字段拒绝（类型）；`false` → 拒绝 `prior_history.declared_complete`（理由：调用方声明历史不完整，无法排除全局重复事件）；`declared_scope` 空白 → 拒绝；`records` 非列表/成员非法/`event_id` 非升序或重复 → 拒绝（**唯一性与顺序属第 4 步的名单规则**）。

### 3.5 通用规则：类型、范围与未知字段

- **封闭键集合**：任何对象出现未列出的键 → 拒绝，`field` 为该键的完整路径（如 `submission.actor.role`）。
- **非空字符串**：不 `strip`、不改大小写、不转数字、不补前导零；整串为空或仅空白视为缺失。
- **严格类型**：布尔、整数**不得**冒充字符串（`True != "true"`、`7 != "7"`）；反之亦然。常量字段（如 `decision_source`、`actor_kind`、`decided_at_source`、`contract_effective`、`execution_allowed`）必须是**常量值且类型正确**（`is True` 而非 `== 1`）。
- **严格整数**：计数字段（`byte_size`、各 `*_count`）必须是 `int` 且非 `bool`；`byte_size` 范围为 `>= 0`（对象自身的整数范围；不含"文件必须存在"这类磁盘事实）。
- **哈希字段**：必须**完整 64 位小写十六进制**（`fullmatch`）；尾随 `\n`/`\r\n`/空格、大写、截断一律拒绝。
- **普通 ID 例外**：`event_id`/`batch_id`/`request_id`/`actor_id` 等身份字符串**不套用"不是哈希"或"必须是哈希"的排除**——即使形状恰为 64 位十六进制（或含前导零）仍是合法字符串，身份只做**精确字符串比较**。
- **列表**：除另有说明外，成员必须唯一且按**UTF-8 字节序升序**（`files` 按 `relative`、阻塞/失败项按原文、`records` 按 `event_id`）；顺序不符或重复 → 拒绝。

### 3.6 wrapper（前序记录包装）与 record（输出记录）

- wrapper 封闭键集合：`{wrapper_version, record_fingerprint, record}`；`wrapper_version` 必须为 `WRAPPER_VERSION`；`record_fingerprint` 为 64 位小写十六进制且必须等于 `fingerprint(record)`；`record` 必须是 §14 定义的**完整记录对象**（封闭键集合）。
- 输出 record 的封闭键集合与派生来源见 §14。

---

## 4. 材料正文与指纹（唯一计算正文）

### 4.1 材料正文定义（唯一、无自指）

```text
materials_body := materials 对象中，仅删除【顶层】键 materials_fingerprint 之后的其余内容
                   （其余顶层键、所有嵌套对象与所有列表的成员与顺序原样保留）
materials.materials_fingerprint == fingerprint(materials_body)
fingerprint(x) := sha256(canonical_json(x)).hexdigest()        # canonical 参数见 §13
```

- **参与字段**：`materials` 的**全部其它顶层键**——`gate`、`batch_id`、`run_binding`（含 `code`/`rules`/`config`/`input` 全部嵌套）、`contract_binding`、`files`（含每个成员的 `relative`/`file_sha256`/`byte_size`）、`quality`（含 `status` 与三个列表及其顺序）。
- **列表顺序**：`files` 必须先按 `relative` 升序（严格递增、唯一）才可参与正文；三个阻塞/失败列表按原文升序且唯一。**正文不做任何其他规范化**（不改键名、不排序对象键——对象键由 canonical JSON 的 `sort_keys=True` 决定、不置空、不删除其它字段）。
- **禁止**：对包含 `materials_fingerprint` 自身的整对象求摘要；把"置空/删除/任选排序"等算法选择留给实施端。本定义是**唯一**允许的算法。

### 4.2 唯一相等关系

校验必须同时成立（§5 第 9 步）：

```text
fingerprint(materials_body)
  == materials.materials_fingerprint
  == submission.request_binding.materials_binding
  == expectations.expected_materials_fingerprint
```

四者**必须完全相同**（字符串精确相等）。**不得互相替代**的另有：`materials.files[i].file_sha256`（内部文件字节 SHA）与 `expected_files[relative]` 必须**逐项**相等（§7.2）——文件字节 SHA 与整体规范对象指纹是两类值，任何一方缺失都不能由另一方补齐。

---

## 5. 校验顺序（固定；最早违反项即 `field`）

> **两个范围**：第 **1—4 步**只做**形状/类型/常量/键集合/列表规则**（对象自身是否合法，含 Gate 与字段的对应关系如"Gate2 必须有前序绑定对象"）；第 **5—12 步**做**值/关系**（跨对象一致性与语义比较）；第 **13 步**为质量/决定矩阵；第 **14 步**构建记录。每个案例只给**唯一最早字段与步骤**。

| 步 | 检查 | 范围 | 定位字段示例 |
| --- | --- | --- | --- |
| 1 | `submission` 结构/类型/枚举/常量/未知键（含 `decision_source`、时间字段类型、按 Gate 规定的 `prior_decision_binding` 形状：Gate1 必须 `null`、Gate2 必须是 wrapper 对象） | 形状/类型 | `submission.*` |
| 2 | `materials` 结构/类型/常量（含 `contract_effective` 必须为严格布尔 `true`）/未知键 + `files` 名单规则（非空、唯一、升序、成员形式）+ `quality` **状态与列表一致性** | 形状/类型 | `materials.files`、`materials.contract_binding.contract_effective`、`materials.quality.status` |
| 3 | `expectations` 结构/类型/未知键（含按 Gate 规定的 `expected_prior_gate1` 形状：Gate1 必须 `null`、Gate2 必须是对象） | 形状/类型 | `expectations.*` |
| 4 | `prior_history` 结构与完整性声明 + `records` 名单规则（`event_id` 唯一、升序） | 形状/类型/列表 | `prior_history`、`prior_history.declared_complete`、`prior_history.records` |
| 5 | 身份一致性（`batch`/`gate`/`request`） | 值/关系 | `materials.batch_id`、`expectations.expected_gate` … |
| 6 | 时间语义（§6，含真实日期/分量/偏移） | 值/关系 | `submission.decided_at_raw` |
| 7 | 契约绑定（§7.1，与独立预期比较） | 值/关系 | `expectations.expected_contract.*` |
| 8 | 运行绑定（§7.3，与独立预期逐字段比较） | 值/关系 | `expectations.expected_run_binding.*` |
| 9 | 材料正文派生复算（§4.2） | 值/关系 | `materials.materials_fingerprint` |
| 10 | `files` ↔ `expected_files` 双向完整比较（§7.2） | 值/关系 | `expectations.expected_files[...]` |
| 11 | 前序闭合（§9.3；含**前序运行绑定逐字段比较**） | 值/关系 | `submission.prior_decision_binding.*` |
| 12 | 历史与重复事件（§10：与提交/既有批准记录的关系） | 值/关系 | `prior_history.records`、`submission.event_id` |
| 13 | 质量/决定矩阵（§12） | 语义决定 | `submission.decision` 或 `materials.quality.status` |
| 14 | 构建记录 + 派生计数 + 外层指纹 | 输出 | — |

> 顺序意义：**时间字段的类型错误在第 1 步**（不进入第 6 步的值判定）；**材料内常量（如 `contract_effective` 的类型与 `true`）在第 2 步**，与独立契约预期的**值比较**在第 7 步；`records` 的**唯一/升序**在第 4 步，与**提交或既有批准**的语义重复在第 12 步；**内层文件关系（第 10 步）晚于外层摘要复算（第 9 步）**；**质量与决定矩阵（第 13 步）晚于全部材料与绑定检查**，因此以质量为由的拒绝必须先满足书面配方（否则会先在第 2/9/10 步失败）。**前序记录内部的常量、枚举、`note`、质量与运行绑定**一律在**第 11 步**校验（不因它是内嵌对象而跳步），其中 `note` 必须逐字符等于 §14 的程序输出常量。

---

## 6. 五项义务与时间语义（规则唯一，不留 U5）

**五项义务缺一不可**：主理人的明确决定（`decision`）、批次标识（`batch_id` 三处一致）、守门材料指纹（`request_binding.materials_binding` + `materials_fingerprint` + 独立预期）、时间（`decided_at_raw`）、说明（`reason`）。

**时间接受写法（恰好两种，全串匹配）**：

```text
A) YYYY-MM-DD
B) YYYY-MM-DDThh:mm:ss±hh:mm
```

- **全串匹配**：必须锚定整串；**不允许**首尾空白、`Z` 形式、小数秒、缺秒（如 `T18:00`）、其他分隔符或额外字段。
- **真实日历日期**：年 4 位、月 01–12、日必须在该月实际存在（闰年规则适用：`2028-02-29` 合法，`2026-02-29`、`2026-09-31` 非法）。
- **时间分量范围**：`hh` 00–23、`mm` 00–59、`ss` 00–59（不接受闰秒 `60`）。
- **偏移范围**：`±hh:mm`，`hh` 00–14、`mm` 00–59；当 `hh == 14` 时 `mm` 必须为 `00`（即最大 ±14:00）；`+25:00`、`+08:60`、`+08` 一律非法。
- **失败定位**：一律 `submission.decided_at_raw`，理由须写明失败元素（形式/日期/时间分量/偏移）。
- **原文保留**：记录中 `decided_at_raw` 与输入**逐字符相等**；同时写入 `decided_at_source = "HUMAN_PROVIDED_RAW"`。
- **禁止**：补当前时间/时区、把整理时间或保存时间当人类决定时间、缺失时填默认值、生成 `decided_at_normalized` 一类机器时间值。
- `docs/AUDIT_CONTRACT.md` 头部的人工生效时间原文**不**作为本协议的正向 Gate 输入（用途不同，且不得反向否定该契约的生效确认）。

---

## 7. 材料与契约绑定

### 7.1 正式契约绑定

`materials.contract_binding.contract_version` 与 `contract_file_sha256` 必须与 `expectations.expected_contract` **逐项相等**；`contract_effective` 必须是严格布尔 `true`。**候选/草案状态不得冒充正式契约**（前置事实：`docs/AUDIT_CONTRACT.md`，`174a021b…40ad`）。协议本身不读文件，因此"该 SHA 是否仍为正式文件当前字节"由未来适配层实读核对（§8.3）。

### 7.2 `files` 名单与独立预期（双向完整比较）

- **`relative` 含义与允许形式**：批次相对 **POSIX 路径**——以 `/` 分隔、**不以 `/` 开头**、**不含空段**、**不含 `..` 段**、**不含 `\`**；按**字节精确比较**（区分大小写、不做路径归一化、不做 Unicode 归一化）。
- **名单规则**：`files` **非空**；`relative` **逻辑键唯一**（重复即拒绝 `materials.files`）；必须按 `relative` 升序；每个成员必须恰有 `{relative, file_sha256, byte_size}`，`file_sha256` 为完整 64 位小写十六进制，`byte_size` 为非负严格整数。
- **双向完整比较**：`expected_files` 必须**非空**；`set(materials.files[].relative) == set(expected_files.keys())`（**缺项、额外项、重复项一律拒绝**）；并对每个 `relative` 要求 `file_sha256` 精确相等。哪一侧多/少都在第 10 步拒绝，`field` 指向缺失或多余的 `relative`。
- **完备性责任**：独立名单 `expected_files` 的**完备性由调用方（未来适配层）负责**；纯内存核心只比较**双方提供的**两份名单，**不能**发现调用方在两处同时少报的文件。这一限制必须随能力声明一起表述，不得宣称"全量材料已核验"。
- **两处 Gate 的纯对象完整性（B5 修正：不得依赖批准后产物）**：Gate1 至少包含输入快照与接收核验结果（夹具示例：`receive/quality_report.json`、`receive/snapshot.xlsx`）；Gate2 至少包含**批准前即可取得**的标准化产物、入库数据库与**装载/质量/勾稽核验报告**（夹具示例：`load/load_report.json`、`normalized/normalized.json`、`sqlite/audit.sqlite3`）。**规则筛查报告不是 Gate2 的必需材料**：按正式契约 §3.2 与冻结流程，Gate2 位于标准化/入库完成之后、规则筛查之前——若要求先有筛查报告才能批准 Gate2，会形成"未批准不能筛查、未筛查不能批准"的依赖环。逻辑 `relative` 与示例仅表示材料**角色**；实际磁盘路径与读取仍留 P2，本协议不新增替代门禁、不提前运行筛查、不改变两处 Gate 的业务顺序（先后依赖核对见 TASK-020-R2 证据根）。

### 7.3 运行绑定各摘要的计算对象与含义

```text
run_binding = {
  "code":   {"file_sha256": <宿主/核心代码【单文件】确切字节 SHA>,
             "manifest_fingerprint": <代码清单对象的规范指纹>},
  "rules":  {"version": <非空 str>, "manifest_fingerprint": <规则清单对象的规范指纹>},
  "config": {"file_sha256": <配置【单文件】确切字节 SHA>},
  "input":  {"file_sha256": <本次输入工作簿【单文件】确切字节 SHA>}
}
代码清单对象 := {"entries": [{"relative": <str>, "file_sha256": <64hex>}, ...]}
                 （按 relative 升序、唯一、非空；其规范指纹即 manifest_fingerprint）
```

- `*_file_sha256` 一律表示**该单文件的确切原始字节哈希**；`*_manifest_fingerprint` 一律表示**上述清单对象的规范 JSON 指纹**。两者含义不同、不可互换。
- `materials.run_binding` 与 `expectations.expected_run_binding` 必须**逐字段严格相等**（含嵌套键集合与类型）。

---

## 8. 能验证什么、不能验证什么

### 8.1 纯内存核心**能**验证

字段存在/类型/枚举/未知键；批次-Gate-请求一致；契约版本与 SHA 一致；运行绑定逐字段一致；材料正文（§4.1）可复算且与三处摘要闭合；内部文件名单与独立名单双向一致；前序 wrapper 的记录正文可复算且与三处指纹/字段闭合；历史声明的完整性与范围内重复事件；质量与决定矩阵；输入不被修改；输出确定性。

### 8.2 **不能**验证

磁盘实读（文件/契约"当前字节"是否仍等于所报 SHA）；契约是否真的被人类确认生效（只接受调用方给的结构字段）；来源业务真实性；人类身份真实性或文本是否真由人类独立完成；**调用方同时少报的材料文件**；其声明范围之外的隐藏历史。

### 8.3 未来适配层职责（P2）

实读文件字节并计算文件 SHA、实读正式契约并核对生效登记、枚举材料文件并保证独立名单完备、把历史记录装入 `prior_history`、独占保存与恢复、以及在任何放行动作前重做上述核对。

---

## 9. Gate 顺序与前序闭合

### 9.1 两处守门点

| Gate | 关注 | 纯对象完整性要点（**均为批准前可得**） |
| --- | --- | --- |
| Gate1 | 接收、范围、结构 | 输入快照与接收核验结果（示例逻辑 relative：`receive/quality_report.json`、`receive/snapshot.xlsx`） |
| Gate2 | 标准化、入库、勾稽 | 标准化产物、入库数据库、装载/质量/勾稽核验报告（示例逻辑 relative：`load/load_report.json`、`normalized/normalized.json`、`sqlite/audit.sqlite3`）。**不含规则筛查报告**——筛查在 Gate2 决定之后进行（B5） |

### 9.2 Gate1：前序字段必须为 `null`

`submission.prior_decision_binding` 与 `expectations.expected_prior_gate1` **必须为 `null`**（出现任何非 null 值 → 第 1/3 步拒绝）；`prior_history` 仍为必需参数（可为空 `records`）。

### 9.3 Gate2：必须闭合到**完整 Gate1 记录**

必需输入（三处必须同时给出且互相一致）：

1. `submission.prior_decision_binding` = wrapper（**完整记录** + 外层指纹）。
2. `expectations.expected_prior_gate1` = `{gate, batch_id, event_id, record_fingerprint, run_binding}`（**独立预期**，不得由提交自报推导；`run_binding` 为前序记录的运行绑定对象，形状同 §7.3）。
3. `prior_history.records` 必须包含与 (1) **规范相等**的同一 wrapper。

校验（**第 11 步**，按下列顺序给唯一最早字段；前序记录内部的常量、枚举、`note`、质量与运行绑定都在本步校验）：

| 序 | 检查 | 说明 |
| --- | --- | --- |
| 11a | wrapper 形状 | 封闭键集合、`wrapper_version` 常量、`record_fingerprint` 64 位小写 |
| 11b | 记录键集合/常量/枚举/`note` | `record` 键集合与 §14 完全一致；`record_version`、`record_status`、`decided_at_source`、`note` 为常量（`note` 逐字符等于 §14 常量）；`gate`/`decision`/`actor_kind` 命中枚举 |
| 11c | **记录正文复算** | `record_fingerprint == fingerprint(wrapper.record)`（对**记录对象**按 canonical JSON 复算；摘要相等或一个 `"APPROVE"` 字符串**不能替代**实际记录） |
| 11d | 记录身份 | `record.gate == "GATE1"`、`record.batch_id == submission.batch_id`、`record.decision == "APPROVE"`、`record.actor.actor_kind == "HUMAN_DECLARED"` |
| 11e | 契约一致 | `record.binding.contract_binding` 的版本与文件 SHA 必须等于**本次** `expectations.expected_contract`（契约变化 ⇒ 新批次，不得用旧契约记录放行） |
| 11f | **前序运行绑定逐字段严格相等**（R2 新增） | `record.binding.run_binding` 必须与**本次** `materials.run_binding` **及** `expectations.expected_run_binding` **逐字段严格相等**：`code.file_sha256`、`code.manifest_fingerprint`、`rules.version`、`rules.manifest_fingerprint`、`config.file_sha256`、`input.file_sha256` 六项全等，且嵌套键集合一致。任一不同 → 拒绝 `submission.prior_decision_binding.record.binding.run_binding.<字段路径>`。亦可与独立预期 `expectations.expected_prior_gate1.run_binding` 对齐为同一对象（它是 11f 的独立预期来源） |
| 11g | 质量与边界 | `record.quality_summary.status == "OK"` 且三个计数为 `0`；`record.execution_allowed is False`；`record.boundaries` 六项严格 `false` |
| 11h | 三处指纹闭合 | `expectations.expected_prior_gate1.record_fingerprint == submission.prior_decision_binding.record_fingerprint == fingerprint(record)`；`expected_prior_gate1.{gate,batch_id,event_id}` 与记录一致 |
| 11i | 历史一致 | `prior_history.records` 中必须存在与 (1) 规范相等的 wrapper |

**11f 的意义**：运行绑定指**本批代码/规则/配置/输入版本**；若前序 Gate1 记录是在**另一套**绑定下作出的，则它对本批不再有效——必须新批次重新守门，不能只因为契约版本相同就复用。**Gate1 与 Gate2 的材料集不同，因此两者的 `materials_fingerprint` 不要求相等**（本协议不作此要求）；要求相等的是**运行绑定**。

**不得**：仅凭 `"APPROVE"` 字符串、开发态 `phase`（如 `DEV_GATE2_APPROVED`）、模拟凭证（`SIMULATED_*`）、`0001—0008` 记录、或本次 D2 总体建设许可放行 Gate2。前序记录的**自身材料指纹**指 Gate1 材料，仅用于记录内部一致性校验（11c），**不与当前 Gate2 材料比较**。

---

## 10. 历史完整性与重复事件

- **唯一载体**：`prior_history`（§3.4）为 API 参数（形参默认 `None`，**语义必填**，见 §2.1）；**缺省省略或显式 `None` 均在函数体的第 4 步拒绝** `prior_history`（`HumanGateDecisionBlocked`），**不默认空历史、不默认 `declared_complete=true`**；不存在其他完整性字段。`declared_complete` 非布尔 → 类型拒绝；`declared_complete == false` → 拒绝并说明"调用方声明历史不完整，无法排除全局重复事件"。
- **快照范围**：`prior_history.records` 仅为调用方所声明范围（`declared_scope`）内的记录；纯核心**仅在该快照范围内**判定重复，**不声称**能发现磁盘或全局的隐藏历史。真实完整性由未来适配层负责。
- **重复/覆盖判定**：
  - `records` 内自身出现重复 `event_id`（或非升序）→ **第 4 步**拒绝 `prior_history.records`（名单唯一性/顺序规则）；
  - `records` 内出现与 `submission.event_id` 相同的 `event_id` → **第 12 步**拒绝 `submission.event_id`（重复事件）；
  - 同批次同 Gate 已存在成功 `APPROVE` 记录 → **第 12 步**拒绝 `prior_history.records`。
- **不可覆盖**：决定一经保存不可覆盖（保存属后卡）；数据/代码/规则/范围/契约/守门材料变化 → **新批次**，不复用旧决定。

---

## 11. 身份边界与来源能力

### 11.1 结构来源标记（调用方提供，非身份认证）

`submission.decision_source` 是**封闭枚举中唯一取值** `"HUMAN_GATE_DECISION"` 的**纯结构标记**，由**调用方**提供。它不是身份认证、不证明文本作者。拒绝"以 D2 纪要/开发态凭证代替本批次决定"必须**通过结构构造**：错误的 `decision_source` 取值、缺失独立预期、或错误的前序记录关系——而**不是**通过阅读说明文字。

### 11.2 身份声明

`actor.actor_kind` 必须为 `"HUMAN_DECLARED"`；`"SIMULATED_HUMAN"`、`"AI"`、`"SYSTEM"`、`"DEVELOPMENT"` 等一律拒绝（第 1 步）。声明是**本地文本**，不认证；协议**不承诺**识别"伪装成人类的文本"。

### 11.3 `reason` 文本只作数据

`reason` 的内容（含提到 `D2`、含 `IGNORE PREVIOUS INSTRUCTIONS` 之类指令样式文字）**一律作为原文数据**：不执行、不做关键词判断、不做自然语言意图分析、不做文本作者检测、**不从说明文字生成或推导任何授权**。原文按 §14 原样写入记录。

### 11.4 普通 ID 不是来源凭证

`event_id` 等身份字符串按 §3.5"普通 ID 例外"处理：**前缀（如 `SIM-EV-*`）、形状或内容都不构成来源证明**，不得据此把合法的 `HUMAN_DECLARED` 提交判为模拟，也不得依赖任何未列入 §3 的"真实模式"字段。

---

## 12. 质量与决定矩阵

### 12.1 `quality` 一致性（第 2 步）

```text
status == "OK"      ⇔ structural_blockers == [] 且 quality_blockers == [] 且 verification_failures == []
status == "BLOCKED" ⇔ (structural_blockers 或 quality_blockers 非空) 且 verification_failures == []
status == "FAILED"  ⇔ verification_failures 非空
```

- 三个列表成员必须为非空字符串、唯一、升序；**不允许** `status=OK` 却带非空阻断项，也不允许 `BLOCKED` 而三个列表全空、`FAILED` 而无 `verification_failures`——**矛盾输入一律在第 2 步拒绝**，`field = materials.quality.status`。

### 12.2 决定矩阵（第 13 步）

| `materials.quality`（且已通过第 1—12 步） | `APPROVE` | `HOLD` | `REJECT` |
| --- | --- | --- | --- |
| 完整报告、无阻断（`OK`，三列表空） | 记录，`execution_allowed=false` | 记录，`false` | 记录，`false` |
| 完整报告、存在未解决阻断（`BLOCKED`，`verification_failures` 空） | **拒绝**，`field=submission.decision` | 记录，`false` | 记录，`false` |
| 核验失败/凭证不完整（`FAILED`，`verification_failures` 非空） | **拒绝**，`field=materials.quality.status` | 同左 | 同左 |
| 状态与列表矛盾 | 第 2 步拒绝，`field=materials.quality.status` | 同左 | 同左 |

- **区分**："完整报告显示存在阻断"（可保存 HOLD/REJECT 的内存记录、固定不放行）与"核验过程失败/材料不完整"（**不产生成功记录**）。
- **不得**：把所有 `BLOCKED` 与 `FAILED` 一并拒绝（那会让 C-58 类 HOLD 无法记录）；也不得靠改写为矛盾的 `OK` 让 HOLD 通过。
- **`quality_summary`**（记录内派生）：`{status, structural_blockers_count, quality_blockers_count, verification_failures_count}`；计数为对应列表长度的**严格整数**，来源即 `materials.quality` 的三个列表，不重新计算、不推断。

---

## 13. 规范 JSON、确定性与异常

- canonical JSON：UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、`allow_nan=False`；规范指纹 = 该字节串的 SHA-256。
- **输出记录不内嵌自身指纹**：`record_fingerprint` 在返回值外层（与 §4.1 材料正文同一思路）。
- 返回**深拷贝**、无别名；**不修改**任何入参（含 `prior_history`）。
- 同输入同结果；不依赖时间、随机数、环境或全局状态；不读写文件/库/网络；不导入宿主、控制器、上游核心、测试或答案册；不产生状态迁移。
- 异常：协议/绑定问题 → `HumanGateDecisionBlocked(field, reason)`；意外内部错误 → `HumanGateDecisionError(stage, reason)` 并**保留 `__cause__`**；不得把内部错误包装成成功或伪装为协议拒绝。

---

## 14. 拟定记录形状（封闭键集合；不含真实内容）

```json
{
  "record_version": "TASK-020-human-gate-decision-record-1.1",
  "record_status": "HUMAN_GATE_DECISION_MEMORY_VALIDATED",
  "gate": "GATE1",
  "batch_id": "<原文>",
  "event_id": "<原文>",
  "decision": "APPROVE",
  "decision_source": "HUMAN_GATE_DECISION",
  "reason": "<人类原文，逐字符保留>",
  "decided_at_raw": "<人类原文，逐字符保留>",
  "decided_at_source": "HUMAN_PROVIDED_RAW",
  "actor": {"actor_kind": "HUMAN_DECLARED", "actor_id": "<原文>", "declaration_note": "<原文>"},
  "binding": {
    "request_id": "<原文>",
    "materials_fingerprint": "<64位小写十六进制>",
    "materials_files": [{"relative": "<批次相对POSIX路径>", "file_sha256": "<64hex>", "byte_size": 0}],
    "contract_binding": {"contract_version": "<原文>", "contract_file_sha256": "<64hex>", "contract_effective": true},
    "run_binding": {"code": {"file_sha256": "<64hex>", "manifest_fingerprint": "<64hex>"},
                    "rules": {"version": "<原文>", "manifest_fingerprint": "<64hex>"},
                    "config": {"file_sha256": "<64hex>"}, "input": {"file_sha256": "<64hex>"}}
  },
  "prior_gate1": null,
  "quality_summary": {"status": "OK", "structural_blockers_count": 0,
                      "quality_blockers_count": 0, "verification_failures_count": 0},
  "execution_allowed": false,
  "boundaries": {"persisted": false, "approved_for_execution": false,
                 "human_initial_judgment_saved": false, "ai_enabled": false,
                 "identity_authentication": false, "source_authenticity_proven": false},
  "note": "内存校验通过；不表示已保存、已放行或已产生真实人类判断。"
}
```

- `prior_gate1`（Gate2 时）为**记录内的前序摘要**：`{record_fingerprint, event_id, batch_id, gate, decision, actor_kind}`（Gate1 时必须为 `null`）。它是**校验通过后**从 wrapper 派生的摘要；校验本身仍使用 §9 的**完整记录**（含 11f 的运行绑定比较）。
- 记录**不含** `finding_notes` 或任何初判备注字段。
- **记录键集合固定为 17 个键**（本节列出的全部键）；未列出的键不得出现；`note` 为**常量字符串**（保证确定性），**夹具标识不得追加到 `note`**——夹具说明只能放在证据外层、人类提供的 `reason`/`declaration_note` 等字段中，否则记录的规范指纹将不对应协议常量。

---

## 15. 未决项（不再包含本协议已定事项）

| 编号 | 未决项 | 归属 |
| --- | --- | --- |
| U1 | 持久化/恢复/独占写与失败诊断 | P2 后卡 |
| U2 | 控制器与宿主接线、`gate1_approval`/`gate2_approval`/`next` 字段与放行语义；材料文件的实际枚举与磁盘读取（含独立名单完备性） | P2 后卡（Gate1/Gate2 分开验收） |
| U3 | 真实人类独立初判记录结构（D3：批次必填 + 可选逐条备注） | P3 另卡 |
| U4 | AI 建议与终判 | 另行明确范围，当前未开放 |

> 此前版本的 `U5（时间格式取舍）` 已在本版 §6 **定稿**（接受写法、全串匹配、真实日期、分量与偏移范围、失败定位），**不再留给实施端**。

---

## 16. 停止点

本文件为 **TASK-020-R1 的文档修正交付**：不含实现、不创建生效文件、不修改任何既有实现或绑定。**P1 纯核心实施须另卡**，且先核验主理人正式 V1 文件与明确生效确认；正式契约、协议与代码**各自独立绑定**，本协议与 D2 纪要**均不构成任何批次的 Gate 批准**。
