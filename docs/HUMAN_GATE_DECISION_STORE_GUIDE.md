# Gate 决定快照：保存与只读恢复核验指南（P2-S1 / TASK-022）

版本：TASK-022 / TASK-022-R1 / TASK-022-R2 / TASK-022-R3（P2-S1）；日期：2026-10-13。R1 定点修正见 §2（原始路径链接拒绝）、§3（生产仅绑四项组件）、§4（失败诊断先绑定原因链）、§5（先类型检查再消费、完整 I/O 映射、末次消费接缝）与 §8（三类调用登记与真实读取观察）；R2 追加 §4（首次加载 P1 的错误边界与缓存清理）与 §10（完整核心载荷审核、同缓冲磁盘读回、漂移绑定、verify 输入现场与三时点）；R3 追加 §10.2（**终审与本次真实观察的完整对象比较**，生产存储实现自 R3 起冻结）。
组件：`scripts/store_demo_human_gate_decision.py`；测试/证据入口：`tests/test_store_demo_human_gate_decision.py`。
依据：已验收的 P1 纯内存核心（`scripts/build_demo_human_gate_decision.py`，SHA
`5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79`）与冻结协议
`68c931b3…3e76`。

> **范围声明（先读）**：本组件范围是 **`STORED_SNAPSHOTS_ONLY`**。它只验证**已提供快照**的内部关系
> 与实际存储字节，**不做**全局历史发现、**不实读**业务材料/工作簿/DB、**不证明**材料清单完备或
> 来源真实。保存事实由外层 `status`/manifest 表达；**它不是批次批准、不是运行放行、不是身份认证**。
> 真实 Gate 批准仍为 `null`、真实初判未保存、`next=false`、AI 未开放；宿主/控制器接线、Gate1/Gate2
> 适配器（本批材料实读、完整历史枚举）**均不在本卡范围**。

---

## 1. 公开接口

```python
from scripts.store_demo_human_gate_decision import (
    save_human_gate_decision_snapshots, verify_human_gate_decision_snapshots,
    HumanGateDecisionStoreBlocked, HumanGateDecisionStoreError,
)

saved = save_human_gate_decision_snapshots(out_dir, submission, materials, expectations,
                                           prior_history=prior_history)
verified = verify_human_gate_decision_snapshots(record_dir)
```

| 项 | 内容 |
| --- | --- |
| 成功返回 | **恰好八键**：`status`／`scope`／`identity{batch_id, gate, event_id}`／`record_fingerprint`／`manifest_file_sha256`／`execution_allowed`／`workflow_connected`／`ai_enabled` |
| `status` | 保存 = `HUMAN_GATE_DECISION_SNAPSHOTS_STORED`；核验 = `HUMAN_GATE_DECISION_SNAPSHOTS_VERIFIED` |
| `scope` | 恒为 `STORED_SNAPSHOTS_ONLY` |
| 三个 `false` | `execution_allowed`／`workflow_connected`／`ai_enabled` **严格布尔 `false`** |
| 拒绝 | `HumanGateDecisionStoreBlocked(field, reason)`：协议/路径/前提/不一致；P1 的 Blocked 映射后**保留实际 field/reason** |
| 运行错误 | `HumanGateDecisionStoreError(stage, reason)`：I/O 与意外内部错误，`raise ... from exc` **保留 cause 链**；P1 的 Error 映射后保留 cause |
| 无 | 无 CLI（测试脚本自身可有 CLI）；无 submission-file 接口；不宣称保存原始 JSON 的排版/BOM/换行 |

`prior_history` 默认 `None` 只让缺省调用进入函数体：**缺省省略与显式 `None` 都由真实 P1 拒绝**
（`field=prior_history`），组件**不**擅自默认空历史，也**不**拒绝后建立叶目录。

---

## 2. 目录规则与六份固定文件

- 只接受**解析后**的项目根 `data/human_gate_decision_records/` 的**严格后代目录**：不得等于该根、不得越界；
  由调用方**显式传路径**，不从 batch/event/actor ID 拼目录。
- **链接拒绝（R1）**：先按调用方**原始路径**（含允许根自身）逐级检查符号链接/Windows junction/reparse
  （`lstat` + `FILE_ATTRIBUTE_REPARSE_POINT`），随后才 `resolve()` 并核对解析后的严格后代关系；
  保存与核验**都**适用。经 junction 别名调用会在**写入前**被拒绝（真实 P1 = 0，target 下不建记录）。
- 拒绝已有目标（**含空目录**）、符号链接/Windows reparse 路径；逐级检查已存在祖先；
  **独占建立**叶目录（`mkdir` 语义，不覆盖）；只创建必要父目录；不删除、移动或覆盖任何现有对象。
- 成功叶目录文件集合**恰为六份**（不含子目录、未知文件或 failure）；**六份载荷必须是正常文件**
  （未知项/目录/链接不得被当作合法载荷读取）。

```text
submission.json   materials.json   expectations.json   prior_history.json
decision_result.json   manifest.json
```

- 前四份是**本次消费的独立快照**；`decision_result.json` 是真实 P1 的**完整两键返回**
  （`{"record", "record_fingerprint"}`），不只存 record 或摘要。
- 所有文件采用 P1 canonical JSON 字节（UTF-8、`ensure_ascii=False`、`sort_keys=True`、
  `separators=(",", ":")`、`allow_nan=False`），末尾统一加**一个 LF**、无 BOM；
  字节先明确构造，再以真实**独占 `xb`**（`O_CREAT|O_EXCL`）写入，按确切待写缓冲逐文件读回验证
  长度、SHA 与对象相等。
- **规范对象指纹不含末尾 LF**，与文件 SHA 分列。
- `manifest.json` **最后写入**，不内嵌自身文件哈希。
- P1 record **原样保存**：17 键、`note` 与六项 `boundaries` 均不改，含 `boundaries.persisted=false`；
  它表达 P1 内存记录语义，**不改写成批准或放行标志**。

---

## 3. manifest 封闭协议

版本常量 `TASK-022-human-gate-decision-store-manifest-1.0`；顶层**恰八键**：

| 键 | 内容 |
| --- | --- |
| `manifest_version` | 上述常量 |
| `store_status` | `HUMAN_GATE_DECISION_SNAPSHOTS_STORED` |
| `scope` | `STORED_SNAPSHOTS_ONLY` |
| `identity` | 恰 `{batch_id, gate, event_id}`，分别与 submission、materials、expectations（其对应字段 `expected_batch_id`/`expected_gate`）与 `decision_result.record` 精确闭合；没有对应 event 的对象不补造 |
| `component_bindings` | 恰四项文件 SHA：`core_file_sha256`／`store_file_sha256`／`contract_file_sha256`／`contract_effective_record_file_sha256`（固定项目路径**真实文件实读**，不得用测试答案册或调用方声明值冒充） |
| `fingerprints` | 恰六项：`submission_fingerprint`／`materials_snapshot_fingerprint`／`materials_body_fingerprint`／`expectations_fingerprint`／`prior_history_fingerprint`／`record_fingerprint` |
| `payloads` | 五份 payload 按 `relative` 的 UTF-8 字节序**严格升序**，每项恰 `{relative, byte_size, file_sha256}` |
| `boundaries` | 恰 `{workflow_connected, execution_allowed, identity_authenticated, source_authenticity_proven, ai_enabled}`，全部**严格 `false`** |

所有层级拒绝未知/缺失键，常量与类型严格；`byte_size` 是非负整数（bool 不冒充）；所有 SHA/指纹使用
**全串匹配**的 64 位小写十六进制（不 strip、不截断、不改大小写）；payload `relative` 只能是五个固定
字面文件名，重复、遗漏、绝对路径、分隔符、`..` 一律拒绝（不先 normalize 再宽容接收）。

指纹算法**沿用 P1**：`materials_snapshot_fingerprint` 对完整 `materials` 计算；
`materials_body_fingerprint` 仅移除顶层 `materials_fingerprint` 后计算（沿用 P1 的 `materials_body`），
并与 P1 已验证的派生字段、`submission.request_binding.materials_binding`、
`expectations.expected_materials_fingerprint` 闭合。文件 SHA 对**保存的确切字节**计算，不能互相替代。

`component_bindings` 来自固定项目路径的真实文件实读，**恰四项**：P1 模块、本存储模块、正式 V1、
已登记生效确认文件（R1 起不再在生产运行中核对协议/案例/宿主/控制器等额外冻结身份，避免后续宿主
接线改变代码后阻断所有新快照；这些身份改由**测试/保护层**独立核对）。指令与 P1 输入中的
`run_binding` **分别命名**：后者是调用方提供的业务运行快照，本组件只由 P1 核验其内部关系，
**不声称**已实读其业务代码/规则/配置/输入文件；因此合成夹具的 `run_binding.code.file_sha256`
不必等于存储模块 SHA。manifest **不保存**绝对机器路径、不生成时间/随机值或 ID：同输入 + 相同组件
字节在两个新目录产生**逐文件相同字节**。

---

## 4. 保存顺序与失败现场

1. 检查目标路径/不存在与本次组件绑定；取得四个输入的独立快照，保留对真实消费对象的引用；**不修改**调用者输入。
2. **恰一次**调用真实冻结的 `build_human_gate_decision_record(submission, materials, expectations, prior_history=...)`，只传四个内存快照；不在 store 重写 P1 schema/决定矩阵/历史算法。P1 拒绝时**不建立叶目录**、不生成成功记录。
3. 核对真实消费引用调用前后规范指纹不变；完整返回与输入关系符合已验收接口；生成确定的五份 payload 待写缓冲与 manifest 待写缓冲。
4. 独占创建叶目录，独占保存五份 payload 并读回精确核对，最后独占写 manifest 并读回。
5. 在全部必要数据消费与**组件绑定复测**之后、返回成功之前，**实读六文件字节**与本次待写缓冲逐项核对；manifest 期望只来自本次待写/真实 writer 读回，**不在发生变化后重新采集为新期望**。确认无 failure、无未知项后才返回成功。

**失败现场**：叶目录建立后的任何失败，只尝试在**该新目录**独占写 `failure.json`（版本
`TASK-022-human-gate-decision-store-failure-1.0`、失败阶段、Blocked/Error 分类、`field`（无则 `null`）、
`reason`、完整 cause/context 链）。**先绑定 `raise ... from exc` 的原因链，再写诊断**（R1 修正），
保证 `failure.json.cause_chain` 与实际传播链一致，不把 sentinel 只放进 `reason` 文本。不覆盖已有诊断、
不删除半写文件、不重试覆盖来凑成功；诊断写入失败时保留原异常并报告诊断错误。叶目录建立前的拒绝
**不写**任何失败文件（含**首次加载 P1 失败**）。

**首次加载错误边界（R2）**：`load_frozen_p1_core` 把 spec 建立与 `exec_module` 的**运行/I-O 错误**
统一映射为 `HumanGateDecisionStoreError("p1_load", reason)` 并保留 cause；**未完整加载的模块不作为
正常缓存复用**（从 `sys.modules` 清理、`_CORE` 不写入），撤销原因后下一次调用可正常重载。协议 Blocked
仍为 Blocked；不捕获 `AttributeError` 等程序错误掩盖缺陷。`save` 与 `verify` 都在错误边界内先加载冻结核心。

多进程争用只保证独占创建/不覆盖，不实现锁服务、事务数据库或全局事件索引。

---

## 5. 只读恢复核验

`verify` 不接收调用方 status/期望作为替代证据：

1. 检查路径（原始路径与解析后链路的链接拒绝、存在、目录）、无 `failure.json`、固定六文件集合；
   六份载荷必须是正常文件。
2. **先做封闭类型/形状检查再消费（R1）**：六份顶层必须是 JSON 对象；`decision_result.json` 必须是
   **完整两键对象**且 `record` 是对象；随后才做 `.get`/`.items`/摘要派生/嵌套消费。错类型以
   `StoreBlocked(field)` 定位到具体文件/字段，**不泄漏**原生 `AttributeError`/`TypeError`/`KeyError`，
   也不以“捕获全部原生异常”代替检查。完整 P1 schema/矩阵/历史校验仍交给冻结 P1，不复制算法。
3. **同一缓冲**绑定每份文件的长度/SHA 与解析对象（不先 hash 一次再另读 JSON）。
4. 核验 manifest 全部封闭 schema、实际文件字节与 `payloads`、六项对象指纹与身份闭合；`component_bindings`
   与**当前真实**组件/契约文件匹配。
5. 从四份已绑定快照**恰一次**调用同一冻结 P1 核心，严格比较 `decision_result.json` 的两键对象、记录指纹
   与输入未变。恢复允许这一次纯核心复算；**不调用**宿主、控制器或业务核心。
6. 全部必要消费完成后、返回成功前**再次实读**六文件字节并与本次初始缓冲比较，确认固定集合、无 failure。
   拒绝只读：**不写** `failure.json` 或其他文件；错误消息保留可定位的文件/字段。

**I/O 错误边界（R1）**：目录枚举、初始读取、末次读取、组件绑定实读等**所有实际 I/O** 都统一映射为
`HumanGateDecisionStoreError(stage, reason)` 并保留 `cause`（原生 `OSError` 不泄漏）；协议/路径/类型
错误仍为 `StoreBlocked`，不因统一映射而把协议拒绝降级为运行错误。

**版本不兼容策略**：只有当前组件字节与固定正式契约一致的记录可按本版本恢复；版本/文件身份变化则**如实阻断**，
**不迁移、不补签、不重写**旧记录。这个本地核验**不提供**防同权限攻击者伪造的签名保证，也不替代将来适配器
对当前材料和完整历史的实际核查。

---

## 6. 保存/核验的保真与确定性

- 保存的是**内存对象快照**（canonical JSON 字节 + 一个 LF）：人类字符串原文保留；
  **不生成**身份、时间、事件、原因或决定。
- 四个输入在调用前后指纹不变；组件调用的是**独立快照**，调用者对象不被修改。
- 同一输入与相同组件字节在两个新目录产生**逐文件相同字节**（manifest 不含绝对路径/时间/随机值）。
- 返回与 manifest/文件闭合：`manifest_file_sha256` 是本次实读 manifest 的确切字节 SHA；
  `record_fingerprint` 是 P1 完整返回中的规范记录指纹；`identity` 三项来自已核验的 P1 record。

---

## 7. 能力限制（明确不做）

| 不做 | 归属 |
| --- | --- |
| 全局历史发现、跨目录唯一性保证 | 后续 Gate 适配器（P2 分卡） |
| 业务材料/工作簿/DB 的实际枚举与磁盘读取、材料清单完备性 | 后续 Gate1/Gate2 适配器 |
| 来源真实性、强身份认证、防同权限伪造的签名保证 | 不在当前范围 |
| 宿主/控制器接线、放行字段、真实批准/初判/`0009`、AI/终判 | 另卡/另行明确范围 |

---

## 8. 验证方式

```text
.venv\Scripts\python.exe -B tests\test_store_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_store_tests\task022_<唯一名>
```

- 证据容器与**记录轮次根**（`data/human_gate_decision_records/<同名>/`）必须全新；同一入口复用准备对象，
  不为每个轻量反例重建业务链。
- 覆盖 **G1** 正常与确定性、**G2** 前提与路径、**G3** 恢复负向与只读、**G4** 真实 writer 与晚变更、
  **G5** 边界与真实调用观察、**G6** 证据收尾与保护。
- 证据容器包含：`summary.json`、`checks.json`、`failures.json`、`counts.json`、`call_registry.json`
  （公开存储 API 次数）、**`core_call_registry.json`（真实核心调用登记：存储 API **嵌套**的 P1 与
  测试**直接**调用的 P1 分列，并与核心入口代码帧观察数闭合）**、`api_records.json`（每次存储 API 的
  **完整输入快照**/完整返回或异常与真实 traceback/cause 链）、**`read_observation.json`（真实
  `io.open`/`Path.read_bytes` 读取通道与写入事件的**分列观察**）**、`io_observations.json`、
  `store_inventory.json`（本轮全部记录文件与 junction 现场）、`test_frozen_identities.json`
  （P1/契约/生效登记/协议/案例/宿主/控制器的独立冻结核对，属测试层）、
  `fixture_registration.json`（`PROTOCOL_TEST_FIXTURE_ONLY` 声明）、`isolation_self_tests.json`、
  `evidence_ledger.json`。
- **末次消费接缝**：保存的注入接缝位于**末次组件绑定读取之后**、最终六文件字节确认之前；核验的接缝
  位于唯一一次纯核心复算之后、末次实读之前。测试会先**无注入地观察真实读/写次序**，再注入。

### 10.1 完整核心载荷与终审绑定（R2）

- **审核完整 entries，而非只比 ID 字符串**：`core_call_registry.json` 的 `entries`、`core_call_ids`、
  声明 `total_core_entries`、实际**入口代码帧观察数**与 API 记录的嵌套清单必须**五者一致**；每个真实
  核心调用**恰有一条**完整输入（四个对象）与完整返回/异常（含真实 traceback/cause 链）载荷；重复
  entry、缺 entry（ID 存在而载荷缺失）、空壳 entry、额外/缺失 ID 一律拒绝。
- **真实磁盘读回 + 同缓冲绑定**：终审用**同一次读取**取得对象与文件 SHA（`_core_audit_from_disk`），
  不再把内存比较命名为“磁盘审核”。
- **期望绑定终审读数**：最终台账的期望来自通过**字节漂移确认**的那次终审读数（或本次 writer 待写缓冲）；
  终审后若磁盘字节相对该读数发生变化（漂移）即判失败，**不得**重新采集为新期望后继续通过。收尾为
  **有界两轮**（首轮登记审核结论、次轮确认漂移并落台账），不无限“改文件→重建台账”。
- 故障实测：终审前从磁盘删除**一条完整 entry**（保留 ID 名单/声明 total/入口计数）→ 真实审核检出
  `ids_without_entry`、套件**返回 1 / FAIL / failures 非空**；终审读数后对 `checks.json` 追加 LF →
  漂移确认检出并使套件非零。两者现场均保留。
- **verify 输入现场**：每次 verify 调用在 API 开始前登记 `record_dir`、目录文件集合与各文件确切
  大小/SHA；不存在/不可读时记录 `not_available` 与原因，不填未观察的空白成功值。
- **三时点指纹**：观察器保留进入核心的四个**真实消费引用**，在调用前、返回后、**API 收尾**三时点
  复算指纹并登记（不改对象、不再调用核心、不在 I/O 守卫内落盘）。

### 10.2 终审与本次真实观察的完整对象比较（R3）

- **定稿真实观察预期**：全部 API 与真实核心观察（含三时点）定稿后、任何终审读取之前，从**该次实际观察
  结果**建立**独立深拷贝**预期，至少覆盖完整 `core_call_registry`、完整 `api_records` 与权威调用登记；
  预期不来自候选磁盘文件、不来自重新调用 P1，并在有界两轮审核中**不因候选文件变化而刷新**。
- **同缓冲内容审核**：终审一次读取最终载荷缓冲，从同缓冲取对象与 SHA；先做**完整解析对象的规范比较**
  （任何输入/返回/异常/关联/时点内容差异都被发现，并按 `core_call_id`/`call_id` 定位到字段路径），
  再应用已有效的 ID/entry/total/入口/API 关联审核与字节漂移确认。**数量与形状完整不等于内容与真实观察
  一致**；合法形状的自洽改写（含同步内部指纹）同样被拒绝。
- **`returned` 载荷最低形状**：必须是冻结 P1 的完整两键外层（`record` + `record_fingerprint`）——`{}`
  等不可能的成功外层不再被视为完整；异常与输入记录受同一完整比较约束。
- 故障实测：终审首读前把一条真实成功返回替换为 `{}`（ID/entry 数/total/入口/API 关联不变）→ 套件
  **返回 1 / FAIL / failures 非空**并定位该载荷差异；合法形状的 reason 自洽改写同样失败；终审读数后
  对 `checks.json` 追加 LF 仍由漂移确认判失败。
- 全部合成审批输入明确登记为 **`PROTOCOL_TEST_FIXTURE_ONLY`**：不是主理人真实提交，不产生批次批准效力；
  该标识**不进入** P1 封闭 schema 的任何键。

---

## 9. 停止点

本组件止于**快照已保存 / 只读核验通过**的本地事实：

- 不接宿主/控制器/网络/UI/ERP；不产生 `0009` 或真实初判；不开放 AI/终判；
- 不填写或修改真实批准、初判、`next` 字段；
- 真实人类判断与每一批次的 Gate 批准仍由主理人作出；
- 若后续需要修改冻结 P1、正式契约或宿主，或改变决定矩阵/身份/材料时序、扩大历史发现范围，
  必须**停止受影响实施、保留现场并报告新设计范围**。
