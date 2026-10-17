# 真实人工 Gate 决策记录：拟定案例与最小验收设计（R2 修正版）

标识：**PROTOCOL_CASE_DESIGN_NOT_EXECUTED**
版本：V1-DRAFT-R2 / TASK-020-R2；日期：2026-10-13。
状态：**案例设计稿，尚未执行。** 本文不运行任何函数、不含测试结果，不得被读作"测试 PASS"。

> 阅读须知
> - 全部夹具标注 `PROTOCOL_TEST_FIXTURE_ONLY`：**无审批效力**、不向人类表单预填、不代表任何真实批次。该标识**只出现在本文与证据根**，**不写入程序输出记录**（协议 §14 的 `note` 是常量，夹具说明只能放在证据外层或人类提供的 `reason`/`declaration_note`）。
> - 案例**不从**任何现有真实/模拟批次生成提交，不含真实人类决定或初判文本。
> - 对应协议：`docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`（`PROTOCOL_DESIGN_DRAFT_NOT_IMPLEMENTED`，R2 修正版）；文中节号指该协议。
> - 每例给出：编号 / 所属字段或关系 / 隔离构造方式 / 预期结果与定位字段 / 为何不被更早错误遮蔽。
> - **R2 修正要点**：① 夹具**先构造协议合法对象再算摘要**（`files` 在构造期即写成合法升序唯一列表；拟定核心**仍拒绝**无序输入，不为调用方静默排序）；② `record1` 的 `note` 逐字符等于协议常量；③ Gate2 材料改为**批准前可得**（去掉筛查报告，B5）；④ 每例给**唯一最早字段与步骤**（协议 §5 的两个范围）。
> - **编号唯一且连续**：本版共 **117 个唯一编号 C-01—C-117**，不重号、不用字母后缀；与 TASK-020／R1 版的对应关系见 §10。

---

## 0. 夹具与书面配方

### 0.1 材料正文配方（与协议 §4.1 一致）

```text
materials_body := materials 顶层删除 materials_fingerprint 后的其余内容（嵌套与列表顺序原样）
materials.materials_fingerprint := sha256(canonical_json(materials_body)).hexdigest()
canonical_json := UTF-8 / ensure_ascii=False / sort_keys=True / separators=(",",":") / allow_nan=False
```

派生步骤（书面、可复算，无需运行拟定 API）：

1. **先把 `files` 写成合法列表**：按 `relative` 的 UTF-8 字节序**严格升序**、`relative` 唯一、每项恰有 `{relative, file_sha256, byte_size}`；`quality` 三列表亦唯一升序并与 `status` 自洽。
2. 写出完整 `materials` 对象（除派生字段外的全部字段），按上式计算 `materials_fingerprint`（**对象一旦写成，顺序不再变动**）。
3. 把该值同步写入三处：`materials.materials_fingerprint`、`submission.request_binding.materials_binding`、`expectations.expected_materials_fingerprint`。

**缩写展开规则**（本文 JSON 与证据 JSON 通用）：形如 **`ccc…c`** 的字符串（省略号**两侧均为同一个**小写十六进制字符，左侧重复 1—3 次）表示**该字符 ×64**：`"a…a"`、`"aa…a"`、`"aaa…a"` 三种写法**都**展开为 `"a"×64`（本文一律写成左侧重复三次的形式，如 `aaa…a`、`111…1`）。省略号两侧字符不同、含非十六进制字符或左右侧不是同一字符的字符串**不适用**该规则，按原样处理。其余字符串一律逐字符原样。文件字节 SHA 的夹具常量（如 `bbb…b`）表示"该文件确切原始字节的 SHA"：协议只要求它们与独立名单 `expected_files` 逐项相等，**不要求核心重新计算字节**。

### 0.2 BASE1（Gate1 合法）

```json
{"gate":"GATE1","batch_id":"FIXTURE-BATCH-A",
 "run_binding":{"code":{"file_sha256":"ccc…c","manifest_fingerprint":"ddd…d"},
                "rules":{"version":"FIXTURE-RULES-1","manifest_fingerprint":"eee…e"},
                "config":{"file_sha256":"fff…f"},
                "input":{"file_sha256":"111…1"}},
 "contract_binding":{"contract_version":"V1",
                     "contract_file_sha256":"174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad",
                     "contract_effective":true},
 "files":[{"relative":"receive/quality_report.json","file_sha256":"bbb…b","byte_size":2048},
          {"relative":"receive/snapshot.xlsx","file_sha256":"aaa…a","byte_size":40960}],
 "quality":{"status":"OK","structural_blockers":[],"quality_blockers":[],"verification_failures":[]},
 "materials_fingerprint":"5f0299e17f46f90f2893884d52eb2c2dd6131b7fe6c33350ae9dc38af8e3f739"}
```

- **列表顺序**：`receive/quality_report.json` 在 `receive/snapshot.xlsx` 之前（`q` < `s`，UTF-8 字节序升序）；`files[0]` 是 **quality_report**，`files[1]` 是 **snapshot**（后文按此索引）。
- **派生值**：`materials_fingerprint = 5f0299e17f46f90f2893884d52eb2c2dd6131b7fe6c33350ae9dc38af8e3f739`（＝上述对象去掉派生字段后的规范指纹；与旧 R1 稿的 `5d92459c…` 不同，旧值对应**未排序**正文，已被取代）。

**BASE1 提交与预期（关键字段）**

```text
submission.request_binding = {"request_id":"FIXTURE-REQ-G1-0001",
                              "materials_binding":"5f0299e17f46f90f2893884d52eb2c2dd6131b7fe6c33350ae9dc38af8e3f739"}
expectations.expected_materials_fingerprint = "5f0299e1…f739"（同值）
expectations.expected_files = {"receive/quality_report.json":"bbb…b","receive/snapshot.xlsx":"aaa…a"}
prior_history = {"declared_complete":true,"declared_scope":"FIXTURE-SCOPE-2026-10-13","records":[]}
```

**BASE1 记录（`record1`，拟定输出；`note` 逐字符等于协议 §14 常量）**

```json
{"record_version":"TASK-020-human-gate-decision-record-1.1",
 "record_status":"HUMAN_GATE_DECISION_MEMORY_VALIDATED",
 "gate":"GATE1","batch_id":"FIXTURE-BATCH-A","event_id":"FIXTURE-EV-G1-0001",
 "decision":"APPROVE","decision_source":"HUMAN_GATE_DECISION",
 "reason":"FIXTURE：结构核验通过，同意进入标准化（设计夹具，无审批效力）",
 "decided_at_raw":"2026-10-13T18:00:00+08:00",
 "decided_at_source":"HUMAN_PROVIDED_RAW",
 "actor":{"actor_kind":"HUMAN_DECLARED","actor_id":"FIXTURE-HUMAN-01",
          "declaration_note":"设计夹具：本地显式身份声明，非真实人员、非强认证"},
 "binding":{"request_id":"FIXTURE-REQ-G1-0001",
            "materials_fingerprint":"5f0299e17f46f90f2893884d52eb2c2dd6131b7fe6c33350ae9dc38af8e3f739",
            "materials_files":[{"relative":"receive/quality_report.json","file_sha256":"bbb…b","byte_size":2048},
                               {"relative":"receive/snapshot.xlsx","file_sha256":"aaa…a","byte_size":40960}],
            "contract_binding":{"contract_version":"V1",
                                "contract_file_sha256":"174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad",
                                "contract_effective":true},
            "run_binding":{"code":{"file_sha256":"ccc…c","manifest_fingerprint":"ddd…d"},
                           "rules":{"version":"FIXTURE-RULES-1","manifest_fingerprint":"eee…e"},
                           "config":{"file_sha256":"fff…f"},
                           "input":{"file_sha256":"111…1"}}},
 "prior_gate1":null,
 "quality_summary":{"status":"OK","structural_blockers_count":0,
                    "quality_blockers_count":0,"verification_failures_count":0},
 "execution_allowed":false,
 "boundaries":{"persisted":false,"approved_for_execution":false,
               "human_initial_judgment_saved":false,"ai_enabled":false,
               "identity_authentication":false,"source_authenticity_proven":false},
 "note":"内存校验通过；不表示已保存、已放行或已产生真实人类判断。"}
```

- **记录键数 17**（与协议 §14 一一对应）；`note` **不含**任何夹具后缀。
- 其**外层指纹**（对上述记录对象按 §0.1 canonical 规则复算）＝`15bebb4834702ce970d54a1ce5b5545065480ece13b4b5c64de48c5c1a148c19`。
- **wrapper1** ＝ `{"wrapper_version":"TASK-020-human-gate-decision-record-wrapper-1.1","record_fingerprint":"15bebb48…8c19","record":<上述记录>}`。

### 0.3 BASE2（Gate2 合法；材料为**批准前可得**，B5）

```json
{"gate":"GATE2","batch_id":"FIXTURE-BATCH-A",
 "run_binding":{"code":{"file_sha256":"ccc…c","manifest_fingerprint":"ddd…d"},
                "rules":{"version":"FIXTURE-RULES-1","manifest_fingerprint":"eee…e"},
                "config":{"file_sha256":"fff…f"},
                "input":{"file_sha256":"111…1"}},
 "contract_binding":{"contract_version":"V1",
                     "contract_file_sha256":"174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad",
                     "contract_effective":true},
 "files":[{"relative":"load/load_report.json","file_sha256":"444…4","byte_size":8192},
          {"relative":"normalized/normalized.json","file_sha256":"222…2","byte_size":65536},
          {"relative":"sqlite/audit.sqlite3","file_sha256":"333…3","byte_size":131072}],
 "quality":{"status":"OK","structural_blockers":[],"quality_blockers":[],"verification_failures":[]},
 "materials_fingerprint":"ce95ec25578e026b61a269871575a049b432443786ec5280bcafa725e7bcc45e"}
```

- **列表顺序**：`load/load_report.json` → `normalized/normalized.json` → `sqlite/audit.sqlite3`（升序）；`files[0]` = load_report，`files[1]` = normalized，`files[2]` = sqlite。
- **派生值**：`materials_fingerprint = ce95ec25578e026b61a269871575a049b432443786ec5280bcafa725e7bcc45e`（**先完成 B5 材料变更再重算**；既不是旧 `74e6f14e…`，也不是仅排序后的过渡值）。
- **材料角色与先后依赖**：标准化产物（`normalized/*`）、入库数据库（`sqlite/*`）、装载/质量/勾稽核验报告（`load/load_report.json`）**都在 Gate2 决定之前可得**；**规则筛查报告不在 Gate2 材料内**——筛查按冻结流程在 Gate2 批准之后进行（协议 §7.2/§9.1）。先后依赖核对：Gate1 决定 → 标准化/入库 → **Gate2 决定** → 规则筛查。

**BASE2 提交与预期（关键字段）**：`prior_decision_binding = wrapper1`；
`expected_prior_gate1 = {"gate":"GATE1","batch_id":"FIXTURE-BATCH-A","event_id":"FIXTURE-EV-G1-0001","record_fingerprint":"15bebb48…8c19","run_binding":<与 record1.binding.run_binding 相同的对象>}`；
`prior_history = {"declared_complete":true,"declared_scope":"FIXTURE-SCOPE-2026-10-13","records":[wrapper1]}`。

### 0.4 变更例的同步规则（四要素）

每个变更例写明：**① 只改哪个语义目标；② 需同步的派生值**；**③ 故意保持不一致的旧值**；**④ 预期最早拒绝字段（协议 §5 步号）**。下表"旧引用"指 TASK-020／R1 版案例号。

| 变更例（本版） | 旧引用 | 只改 | 需同步 | 故意不一致 | 最早字段（步） |
| --- | --- | --- | --- | --- | --- |
| C-08 | C-08 | 三处批次标识同步为 `"a"×64` | 材料正文含 `batch_id` → 摘要重算为 `65e583582f5abc0838dcf0cd6fb040aa687bd1c61b5b1a90aaa91de26a449f45`（三处同步） | 无 | 成功（5 通过；正向） |
| C-117 | 原 §0.4 的"单点错批次"（新编号） | **仅** `materials.batch_id` → `FIXTURE-BATCH-B` | 材料摘要 → `8a6ee4e1004760c8ca147c7074d99af054a8539c19f1461c4198b98abaeaab60`（三处同步） | `submission.batch_id`／`expectations.expected_batch_id` 仍为 `FIXTURE-BATCH-A` | `materials.batch_id`（5） |
| C-89 | C-54 | `quality` → `BLOCKED` + `structural_blockers=["FIXTURE-STRUCT-1"]`，`decision=APPROVE` | 材料摘要 → `d70fb4e5442d9f225592b45ccf3640b8a836e1d40c5634b6055ced70c7c7d7f0` | 无 | `submission.decision`（13） |
| C-90 | C-55 | `quality` → `BLOCKED` + `quality_blockers=["FIXTURE-QUALITY-1"]`，`decision=APPROVE` | 材料摘要 → `10a234aff694d92dc0d8dc53d3ff5b332e6b0c215dce8da0d74f4b6ccc0b2d0b` | 无 | `submission.decision`（13） |
| C-91 | C-58 | 同 C-90 但 `decision=HOLD` | 同上 | 无 | 成功记录（`execution_allowed=false`） |
| C-93 | C-57 | `quality` → `FAILED` + `verification_failures=["FIXTURE-VERIFY-1"]` | 材料摘要 → `f83d319095b60a0521b47896109e23db5300d8c10fdd6b48782d66626a9bb61d` | 无 | `materials.quality.status`（13） |
| C-50 | C-45 | 仅 `materials.materials_fingerprint` → `"a"×64`（正文未变） | 无 | 派生字段 ≠ 正文实际值 `5f0299e1…f739` | `materials.materials_fingerprint`（9） |
| C-52 | C-43 | `files[1]`（按合法列表＝`receive/snapshot.xlsx`）字节 SHA → `"9"×64` | 材料摘要 → `ced6a9b31cadd276826763e00fce6b2e1875afa59de6550eb1e7f931bbaafe62`（三处） | `expected_files["receive/snapshot.xlsx"]` 仍为 `aaa…a` | `expectations.expected_files[receive/snapshot.xlsx]`（10） |
| C-53 | C-44 | 同 C-52 构造 | 同上 | 同上 | 同上（10） |
| C-54 | C-66 | 互换两类值：`materials_fingerprint` ↔ `files[1].file_sha256` | 无 | 派生字段被写成文件字节 SHA `aaa…a` | `materials.materials_fingerprint`（9） |
| C-57 | — | `files` 删除 `receive/quality_report.json` | 材料摘要 → `86a39a3e732c533059ea37a199106bbe2a0902a0808ee2fa4393efc4793514d0` | `expected_files` 仍含该文件 | `expectations.expected_files[receive/quality_report.json]`（10，缺项） |
| C-58 | — | `files` 增加 `extra/x.json` | 材料摘要 → `6331516b888a0039dc0efd63e7ce292ed1d21026ae2227d3f889842edec03cc2` | `expected_files` 未含该文件 | `materials.files[extra/x.json]`（10，额外项） |
| C-112 | 新增 | **仅前序材料** `run_binding.code.file_sha256` → `"7"×64`（其余前序字段与材料正文不动） | 由**变化后的前序材料正文**复算材料指纹 → 前序材料指纹 = 5d3e9e03236189dce4854ec87958785fde86b80939cede463393d5017da893c0；前序提交 `materials_binding`／前序独立材料预期／前序独立运行预期同步到该值；再构造前序记录（材料指纹取新值）并复算 → 前序记录指纹 = 935fdc685f0de790981ea4e9c82c6a1f34605c6e35d13bc763255475b596a9f7；本次 Gate2 提交 wrapper／历史 wrapper／独立前序预期同步采用该记录 | **当前** Gate2 材料、材料指纹/文件名单与独立 `run_binding` 保持 BASE2 原值 | `submission.prior_decision_binding.record.binding.run_binding.code.file_sha256`（11f） |
| C-113 | 新增 | **仅前序材料** `run_binding.rules.manifest_fingerprint` → `"8"×64` | 前序材料指纹 = 08ec9f7005cc1a4f04ff26eafab0232a1863eda6e74f4ea849d05f1eca49ea93；前序记录指纹 = 9c35154f97f21ed48a490b25353ec95ef975deedae4a870c1fc6ed633c37a6d5；三处前序关系与本次 Gate2 三处前序绑定同步 | 同上 | `…run_binding.rules.manifest_fingerprint`（11f） |
| C-114 | 新增 | **仅前序材料** `run_binding.config.file_sha256` → `"9"×64` | 前序材料指纹 = 3eabe63cf9d2a95dfcef2cfe68b78d1541747e0d9e462eee09508e179edc33aa；前序记录指纹 = 9c2fea02138d4c2640b70b9dc33760ac6813725721e79c79271a7050e32b3721；同上 | 同上 | `…run_binding.config.file_sha256`（11f） |
| C-115 | 新增 | **仅前序材料** `run_binding.input.file_sha256` → `"0"×64` | 前序材料指纹 = 9fe5b9ab8c8d47b7fa624f84c9f743142c4b8cdf61441c7af87e85cc6e320b43；前序记录指纹 = ba3f59cb2650cb8981b830387c62a02916d8aecd700c6c34f4dba1758efe760d；同上 | 同上 | `…run_binding.input.file_sha256`（11f） |
| C-116 | 新增 | 无（同版本对照） | 前序记录即 `record1`（指纹 `15bebb48…8c19`） | 无 | 成功（11f 通过；Gate1/Gate2 材料摘要**不要求相等**） |

> C-52 与 C-53 使用**同一构造**：C-52 说明"材料变更但独立名单仍旧值"，C-53 说明"外层摘要已同步仍不能掩盖内层不符"，两者都必须在**第 10 步**暴露。
> C-112—C-115 的构造顺序为 **① 只改前序材料 run_binding 的一项 → ② 由变化后的前序材料正文复算前序材料指纹 → ③ 前序提交 `materials_binding`、前序独立材料预期、前序独立运行预期同步到该值 → ④ 构造前序记录（材料指纹取新值，`note` 等常量不变）→ ⑤ 复算前序记录指纹 → ⑥ 本次 Gate2 的提交 wrapper／历史 wrapper／独立前序预期同步采用该记录**。**先算材料、后算记录**，不存在"用 BASE1 旧材料指纹覆盖新值"的写法；当前 Gate2 材料与当前独立 `run_binding` **刻意保持不变**——因此 11a—11e 与 11g—11i 全部通过，拒绝只能来自 11f 的前序运行绑定比较，**不能**由未同步摘要提前拒绝冒充。每例的完整对象集合（变化后前序材料、前序 Gate1 提交/独立预期、前序记录/wrapper、采用该 wrapper 的当前 Gate2 submission/materials/expectations/prior_history）另存于 TASK-020-R3 证据根，供独立复核。

---

## 1. 正向案例（C-01—C-13）

| 编号 | 字段/关系 | 隔离构造 | 预期结果 | 为何不被更早错误遮蔽 |
| --- | --- | --- | --- | --- |
| C-01 | Gate1 全量合法 | BASE1 原样（`files` 已合法升序，摘要按 §0.1 推导） | 返回记录 + 外层指纹；状态 `HUMAN_GATE_DECISION_MEMORY_VALIDATED`；`execution_allowed=false` | 无更早错误 |
| C-02 | Gate1 合法 `HOLD` | BASE1，`decision="HOLD"`，`reason` 写明原因 | 成功构建记录；`execution_allowed=false` | 决定值不在材料正文内，材料摘要不变 |
| C-03 | Gate1 合法 `REJECT` | 同 C-02，`decision="REJECT"` | 成功构建记录；`false` | 同上 |
| C-04 | Gate2 合法（批准前材料） | BASE2（`prior_decision_binding=wrapper1`、`expected_prior_gate1` 含同一 `run_binding`、`prior_history` 含 wrapper1） | 成功构建记录；`prior_gate1` 摘要指向 `15bebb48…8c19`；`false` | 第 10、11 步全部有效（材料为批准前产物，无依赖环） |
| C-05 | 时间原文保留 | BASE1，`decided_at_raw="2026-10-13T18:00:00+08:00"` | 记录中 `decided_at_raw` **逐字符等于**输入；无 `decided_at_normalized` | 类型在第 1 步通过，值在第 6 步通过 |
| C-06 | 纯日期写法 | BASE1，`decided_at_raw="2026-10-13"` | 成功；原文保留 | 协议 §6 形式 A |
| C-07 | 普通 ID 前导零 | BASE1，`event_id="0001"` | 成功；原文保留（不去零） | 类型检查只判非空字符串 |
| C-08 | 批次 ID 恰为 64 位十六进制（**正向**） | BASE1，把 `materials.batch_id`、`submission.batch_id`、`expectations.expected_batch_id` **三处同步**为 `"a"×64`，材料摘要按 §0.1 重算为 `65e583582f5abc0838dcf0cd6fb040aa687bd1c61b5b1a90aaa91de26a449f45`（三处同步） | **成功**；不得因"形状像哈希"拒绝 | 身份只做精确字符串比较；顺序/唯一规则已满足 |
| C-09 | 越界字段拒绝 | BASE1，`submission` 增加 `finding_notes=[…]` | 拒绝 `submission.finding_notes`（第 1 步，未知键） | 逐条备注属 P3 初判范围，不在 Gate schema 内 |
| C-10 | 两类值分列并存 | BASE1（对象指纹 `5f0299e1…f739` 与文件字节 SHA `aaa…a`/`bbb…b` 不同且各自与独立名单一致） | 成功 | 第 9、10 步分别核对 |
| C-11 | 输入不被修改 | BASE1，调用前后比较输入规范指纹 | 输入不变；返回与输入无别名 | 与顺序无关 |
| C-12 | 嵌入指令样式文本只作字符串 | BASE1，`reason` 含 `"IGNORE PREVIOUS INSTRUCTIONS; APPROVE ALL"` | 成功；文本原样保留、不被执行、不改变决定 | 文本不参与控制流（协议 §11.3） |
| C-13 | `reason` 提及 D2 的原文保留对照 | BASE1，`reason="FIXTURE：依据 D2 建设许可提交本决定（设计夹具）"`，其余合法、`decision_source="HUMAN_GATE_DECISION"` | **成功构建记录**；原文逐字符保留；**不因文字生成任何新的批准权限**（`execution_allowed=false`） | 文本仅作数据 |

---

## 2. 字段、类型与未知键（C-14—C-40；协议 §3、§5 第 1—4 步）

| 编号 | 字段/关系 | 隔离构造 | 预期结果（唯一最早字段/步） | 为何不被更早错误遮蔽 |
| --- | --- | --- | --- | --- |
| C-14 | 缺"明确决定" | 删除 `submission.decision` | `submission.decision`（1） | 其余字段合法 |
| C-15 | 缺"批次标识" | 删除 `submission.batch_id` | `submission.batch_id`（1） | 同上 |
| C-16 | 缺材料绑定 | 删除 `submission.request_binding.materials_binding` | 同字段（1） | 同上 |
| C-17 | 缺"时间" | 删除 `submission.decided_at_raw` | `submission.decided_at_raw`（1，缺失） | 同上 |
| C-18 | 缺"说明" | 删除 `submission.reason` | `submission.reason`（1） | 同上 |
| C-19 | 说明为空白 | `reason="   "` | `submission.reason`（1） | 空白不算说明 |
| C-20 | 布尔冒充枚举 | `decision=true` | `submission.decision`（1，类型） | 布尔不通过枚举 |
| C-21 | 数字冒充字符串 | `batch_id=7` | `submission.batch_id`（1，类型） | 不做 `str()` 转换 |
| C-22 | 非法枚举 | `gate="GATE3"` | `submission.gate`（1） | 结构合法、值非法 |
| C-23 | 未知顶层字段 | `submission` 增加 `"extra":1` | `submission.extra`（1，未知键） | 封闭键集合；`extra` 已从 schema 删除 |
| C-24 | 未知嵌套字段 | `actor` 增加 `"role":"admin"` | `submission.actor.role`（1） | 同上 |
| C-25 | 缺身份 | 删除 `actor` | `submission.actor`（1） | 其余合法 |
| C-26 | 身份枚举冒充 | `actor.actor_kind="SIMULATED_HUMAN"` | `submission.actor.actor_kind`（1） | 协议 §11.2 |
| C-27 | AI/SYSTEM 代签 | `actor.actor_kind="AI"`（另例 `"SYSTEM"`） | 同字段（1） | 同上 |
| C-28 | 来源标记非法 | `decision_source="D2_AUTHORIZATION_SUMMARY"`（另例 `DEVELOPMENT_APPROVAL`／`AI_SUGGESTION`／`SYSTEM_DERIVED`） | `submission.decision_source`（1，非法取值） | 纯结构来源标记，不是靠文字或 ID 前缀 |
| C-29 | `submission_version` 非常量 | `submission_version="x"` | `submission.submission_version`（1） | 常量检查 |
| C-30 | `byte_size` 为布尔 | `files[0].byte_size=true` | `materials.files[0].byte_size`（2，严格整数） | 布尔不冒充整数 |
| C-31 | `byte_size` 为负 | `files[0].byte_size=-1` | 同字段（2，范围） | 范围检查 |
| C-32 | `contract_effective` **类型**非法 | `contract_effective=1`（整数） | `materials.contract_binding.contract_effective`（**2**，常量类型） | 类型/常量判定在材料结构步 |
| C-33 | 未知材料字段 | `materials` 增加 `gate1_binding={…}` | `materials.gate1_binding`（2，未知键） | 该冗余字段已删除（协议 §3.2） |
| C-34 | 未知提交字段（能力限定） | `submission` 增加 `decided_at_source="HUMAN_PROVIDED_RAW"` | `submission.decided_at_source`（1，未知键） | **只证明未知字段被拒**；不得宣称识别"整理时间的真实来源" |
| C-35 | `expectations` 未知字段 | `expectations` 增加 `"mode":"REAL"` | `expectations.mode`（3，未知键） | 不存在未定义的"真实模式"字段 |
| C-36 | `prior_history` 缺省/显式 `None` | 调用时省略该参数，或显式传 `None` | `prior_history`（**4**，`HumanGateDecisionBlocked`：历史完整性声明缺失） | 形参默认 `None` 使函数体能执行第 4 步；**不默认空历史、不默认 `declared_complete=true`**（协议 §2.1/§10） |
| C-37 | `declared_complete` 非布尔 | `declared_complete="true"` | `prior_history.declared_complete`（4，类型） | 字符串不冒充布尔 |
| C-38 | `declared_complete=false` | `declared_complete=false` | `prior_history.declared_complete`（4，拒绝） | 声明不完整 ⇒ 无法排除全局重复 |
| C-39 | `declared_scope` 空白 | `declared_scope="   "` | `prior_history.declared_scope`（4） | 空白不算范围 |
| C-40 | `records` 非升序 | 两条记录 `event_id` 逆序 | `prior_history.records`（4，顺序规则） | 名单规则在第 4 步 |

---

## 3. 时间语义（C-41—C-49；协议 §6）

| 编号 | 字段/关系 | 隔离构造 | 预期结果（唯一最早字段/步） | 为何不被更早错误遮蔽 |
| --- | --- | --- | --- | --- |
| C-41 | 非法日历日期 | `decided_at_raw="2026-09-31"` | `submission.decided_at_raw`（6，日期） | 类型与形状在第 1 步通过 |
| C-42 | 非闰年 2 月 29 日 | `"2026-02-29"`（对照 `"2028-02-29"` 合法） | 同上（6，日期） | 闰年规则 |
| C-43 | 无时区 | `"2026-10-13T18:00:00"` | 同上（6，偏移缺失） | 形式 B 要求显式偏移 |
| C-44 | 非法偏移 | `"2026-10-13T18:00:00+25:00"`（另例 `+08:60`、`+08`、`Z`） | 同上（6，偏移） | 偏移范围与全串匹配 |
| C-45 | 时间分量越界 | `"2026-10-13T24:00:00+08:00"`（另例 `…:60:00`、秒 `60`） | 同上（6，时间分量） | 分量范围 |
| C-46 | 缺秒/小数秒 | `"2026-10-13T18:00+08:00"`、`"2026-10-13T18:00:00.5+08:00"` | 同上（6，形式） | 全串匹配 |
| C-47 | 首尾空白 | `" 2026-10-13 "` | 同上（6，形式） | 不 strip |
| C-48 | 时间非字符串 | `decided_at_raw=1750000000` | `submission.decided_at_raw`（**1**，类型） | **类型错误在第 1 步即被捕获**，不进入第 6 步的值判定（R2 定点修正） |
| C-49 | 禁止补时间 | 删除 `decided_at_raw`，而 `expectations` 含"当前时间" | `submission.decided_at_raw`（1，缺失） | 期望值不供给该字段；程序不得补齐 |

---

## 4. 材料正文、名单与契约（C-50—C-66 与 C-117；协议 §4、§7）

| 编号 | 字段/关系 | 隔离构造 | 预期结果（唯一最早字段/步） | 为何不被更早错误遮蔽 |
| --- | --- | --- | --- | --- |
| C-50 | 只改外层派生字段 | `materials_fingerprint="a"×64`，正文未变 | `materials.materials_fingerprint`（9） | 第 9 步复算正文即暴露；内层名单仍一致 |
| C-51 | 只改独立材料预期 | BASE1，`expected_materials_fingerprint="d"×64` | `expectations.expected_materials_fingerprint`（9） | 派生字段与正文仍一致 |
| C-52 | 材料变更但独立名单仍旧值 | `files[1]`（=`receive/snapshot.xlsx`）SHA → `"9"×64`，摘要三处同步，`expected_files` 未更新 | `expectations.expected_files[receive/snapshot.xlsx]`（10） | 第 9 步已通过（摘要同步正确），第 10 步暴露内层不符 |
| C-53 | 外层摘要同步但内层矛盾（同构） | 同 C-52 | 同上（10） | **不得**以外层摘要通过掩盖内层关系 |
| C-54 | 两类值互换 | `materials_fingerprint` 写成文件字节 SHA `aaa…a`，`files[1].file_sha256` 写成对象指纹 | `materials.materials_fingerprint`（9） | 第 9 步先于第 10 步 |
| C-55 | `files` 为空 | `files=[]`、`expected_files={}` | `materials.files`（2，非空） | 空表不等价"无要求" |
| C-56 | `files` 重复 `relative` | 两条 `receive/snapshot.xlsx` | `materials.files`（2，唯一） | 逻辑键唯一 |
| C-57 | `files` 缺项（对独立名单） | `files` 删除 `receive/quality_report.json`，摘要按配方重算并同步 | `expectations.expected_files[receive/quality_report.json]`（10，缺项） | 第 9 步通过、第 10 步双向比较暴露 |
| C-58 | `files` 额外项 | `files` 增加 `extra/x.json`（摘要同步） | `materials.files[extra/x.json]`（10，额外项） | 双向比较两个方向都检查 |
| C-59 | `relative` 形式非法 | `relative="/abs.json"`、`"a\\b.json"`、`"a/../b.json"` | `materials.files[i].relative`（2，形式） | 形式规则独立于名单比较 |
| C-60 | 错批次（独立预期） | `expectations.expected_batch_id="FIXTURE-BATCH-B"` | `expectations.expected_batch_id`（5） | 前 1—4 步合法；与 C-117 分列（彼为材料侧单点） |
| C-61 | 错 Gate | `expectations.expected_gate="GATE2"`（提交 GATE1） | `expectations.expected_gate`（5） | 同上 |
| C-62 | 错请求 | `expected_request_id` 不一致 | `expectations.expected_request_id`（5） | 同上 |
| C-63 | 候选/草案冒充正式契约 | `contract_effective=false`（**类型正确但常量值错**） | `materials.contract_binding.contract_effective`（**2**，常量值必须为 `true`） | 类型与常量判定都在第 2 步（R2 定点统一）；与第 7 步的"与独立预期比较"分开 |
| C-64 | 错正式契约 SHA | `expected_contract.contract_file_sha256="e"×64` | `expectations.expected_contract.contract_file_sha256`（7，值/关系） | 第 7 步独立 |
| C-65 | 错运行绑定（本次） | `expected_run_binding.code.file_sha256="e"×64` | `expectations.expected_run_binding.code.file_sha256`（8） | 第 8 步独立于材料名单 |
| C-66 | 运行绑定含义混淆 | `code.file_sha256` 填"代码清单规范指纹"值 | `expectations.expected_run_binding.code.file_sha256`（8） | 两类含义不同（协议 §7.3） |
| C-117 | 单点错批次（材料侧） | **仅** `materials.batch_id` → `FIXTURE-BATCH-B`，材料摘要按配方重算为 `8a6ee4e1004760c8ca147c7074d99af054a8539c19f1461c4198b98abaeaab60`（三处同步）；`submission.batch_id`／`expectations.expected_batch_id` 仍为 `FIXTURE-BATCH-A` | `materials.batch_id`（5） | 前 1—4 步合法（名单升序/唯一、摘要复算一致）；与 C-08（三处同步为 64 位十六进制、正向成功）和 C-60（只改独立预期）分列 |

---

## 5. Gate2 前序闭合（C-67—C-81 与 C-112—C-116；协议 §9）

| 编号 | 字段/关系 | 隔离构造 | 预期结果（唯一最早字段/步） | 为何不被更早错误遮蔽 |
| --- | --- | --- | --- | --- |
| C-67 | Gate2 缺前序绑定 | BASE2 删除 `submission.prior_decision_binding` | `submission.prior_decision_binding`（**1**，按 Gate 的形状规则） | 第 1 步按 `gate` 判定形状 |
| C-68 | 前序只给字符串 | `prior_decision_binding="APPROVE"` | `submission.prior_decision_binding`（**1**，形状） | **字符串/摘要不能替代实际记录** |
| C-69 | 前序缺独立预期 | `expectations.expected_prior_gate1=None`（提交为 GATE2） | `expectations.expected_prior_gate1`（**3**，按 Gate 的形状规则） | 单一口径：Gate2 必须为对象（R2 定点去掉 3/11 双口径） |
| C-70 | 前序记录指纹被改 | wrapper 的 `record_fingerprint` 改为 `"d"×64` | `submission.prior_decision_binding.record_fingerprint`（11c，复算不符） | 记录正文复算 |
| C-71 | 前序记录正文字段被改 | 改动 `record.decision` 为 `"HOLD"` **但不同步指纹** | 同上（11c，复算不符） | 先复算曝光，不进入语义检查 |
| C-72 | 前序决定为 HOLD | 用**合法复算**的 HOLD 前序记录（指纹同步） | `…record.decision`（11d） | 复算通过后按语义拒绝 |
| C-73 | 前序决定为 REJECT | 同 C-72，`decision="REJECT"` | 同字段（11d） | 同上 |
| C-74 | 前序错批次 | 前序记录 `batch_id="FIXTURE-BATCH-B"`（指纹同步） | `…record.batch_id`（11d） | 同上 |
| C-75 | 前序为模拟身份 | 前序记录 `actor.actor_kind="SIMULATED_HUMAN"`（指纹同步） | `…record.actor.actor_kind`（**11b**，协议枚举检查；字段不变） | 记录内枚举固定在 11b（R3 定点统一，去掉重复子步写法） |
| C-76 | 前序记录带质量阻断 | 前序 `quality_summary.status="BLOCKED"`（计数一致，指纹同步） | `…record.quality_summary.status`（11g） | 有效 Gate1 APPROVE 记录只能是 OK |
| C-77 | 前序契约不同 | 前序记录 `contract_binding.contract_version="V0"`（指纹同步） | `…record.binding.contract_binding.contract_version`（11e） | 契约变化 ⇒ 新批次 |
| C-78 | 三处指纹不一致 | `expected_prior_gate1.record_fingerprint` 与 wrapper 不等（各自合法 64 位） | `expectations.expected_prior_gate1.record_fingerprint`（11h） | 三处闭合检查 |
| C-79 | 历史未含前序记录 | `prior_history.records=[]`（提交与预期仍有 wrapper1） | `prior_history.records`（**11i**，单一口径） | 历史一致性属前序闭合（R2 定点去掉 11/12 双口径） |
| C-80 | 开发态 phase 冒充前序 | 用含 `DEV_GATE2_APPROVED` 字样的**无记录结构**对象代替 wrapper | `submission.prior_decision_binding`（1，形状） | 开发态状态不是决定记录 |
| C-81 | D2 纪要冒充批次决定 | `decision_source="D2_AUTHORIZATION_SUMMARY"`（结构来源标记非法） | `submission.decision_source`（1） | 结构构造，不做文本分析 |
| C-112 | **前序代码绑定不同**（隔离反例） | 仅前序材料 `run_binding.code.file_sha256` → `"7"×64`；**先复算前序材料指纹**（前序材料指纹 = 5d3e9e03236189dce4854ec87958785fde86b80939cede463393d5017da893c0）并同步前序提交/独立预期，**再构造前序记录**（材料指纹取新值）并复算（前序记录指纹 = 935fdc685f0de790981ea4e9c82c6a1f34605c6e35d13bc763255475b596a9f7），最后同步本次 Gate2 的 wrapper/历史/独立前序预期；当前 Gate2 材料、材料指纹/文件名单与独立 `run_binding` **不变** | `submission.prior_decision_binding.record.binding.run_binding.code.file_sha256`（**11f**） | 11a—11e 与 11g—11i 均已通过（前序记录按要求复算、契约/身份/质量不变），因此唯一暴露点是 11f |
| C-113 | 前序规则绑定不同 | 同上，仅前序材料 `run_binding.rules.manifest_fingerprint` → `"8"×64`；前序材料指纹 = 08ec9f7005cc1a4f04ff26eafab0232a1863eda6e74f4ea849d05f1eca49ea93；前序记录指纹 = 9c35154f97f21ed48a490b25353ec95ef975deedae4a870c1fc6ed633c37a6d5 | `…run_binding.rules.manifest_fingerprint`（11f） | 同上 |
| C-114 | 前序配置绑定不同 | 同上，仅前序材料 `run_binding.config.file_sha256` → `"9"×64`；前序材料指纹 = 3eabe63cf9d2a95dfcef2cfe68b78d1541747e0d9e462eee09508e179edc33aa；前序记录指纹 = 9c2fea02138d4c2640b70b9dc33760ac6813725721e79c79271a7050e32b3721 | `…run_binding.config.file_sha256`（11f） | 同上 |
| C-115 | 前序输入绑定不同 | 同上，仅前序材料 `run_binding.input.file_sha256` → `"0"×64`；前序材料指纹 = 9fe5b9ab8c8d47b7fa624f84c9f743142c4b8cdf61441c7af87e85cc6e320b43；前序记录指纹 = ba3f59cb2650cb8981b830387c62a02916d8aecd700c6c34f4dba1758efe760d | `…run_binding.input.file_sha256`（11f） | 同上 |
| C-116 | **同版本对照（正向）** | 前序记录即 `record1`（`15bebb48…8c19`） | **成功**；11f 通过（前序与本次运行绑定逐字段相等） | 与 C-112—C-115 对照：同版本可放行到记录构建；Gate1/Gate2 材料摘要**不要求相等** |

---

## 6. 历史与重复事件（C-82—C-85；协议 §10）

| 编号 | 字段/关系 | 隔离构造 | 预期结果（唯一最早字段/步） | 为何不被更早错误遮蔽 |
| --- | --- | --- | --- | --- |
| C-82 | 重复事件（与提交） | `records` 中一条 wrapper 的 `event_id` 与 `submission.event_id` 相同（合法复算） | `submission.event_id`（12） | 前 1—11 步合法 |
| C-83 | 同批次同 Gate 已有 APPROVE | `records` 含同批次 Gate1 成功 APPROVE（**另一 event_id**，合法复算） | `prior_history.records`（12） | 与 C-82 分列 |
| C-84 | 历史内重复 `event_id` | `records` 内两条同 `event_id`（各自合法复算） | `prior_history.records`（**4**，名单唯一性规则） | 与第 4 步唯一性一致，不再放到第 12 步（R2 定点修正） |
| C-85 | 变化后不复用旧决定 | 材料变更（C-52 构造）**且** `records` 含旧材料指纹的成功决定 | `expectations.expected_files[...]`（10，先暴露） | 两处独立；另设一例仅历史命中 |

---

## 7. 质量与决定矩阵（C-86—C-97；协议 §12）

| 编号 | `materials.quality` | `decision` | 预期结果（唯一最早字段/步） | 说明 |
| --- | --- | --- | --- | --- |
| C-86 | `OK`，三列表空 | `APPROVE` | 记录，`execution_allowed=false`，`quality_summary` 三计数 0 | 正向 |
| C-87 | `OK`，三列表空 | `HOLD` | 记录，`false` | 正向 |
| C-88 | `OK`，三列表空 | `REJECT` | 记录，`false` | 正向 |
| C-89 | `BLOCKED` + `structural_blockers=[…]` | `APPROVE` | `submission.decision`（13） | 有未解决阻断不得 APPROVE |
| C-90 | `BLOCKED` + `quality_blockers=[…]` | `APPROVE` | 同字段（13） | 同上 |
| C-91 | `BLOCKED` + `quality_blockers=[…]` | `HOLD` | **记录**，`false`；`quality_summary.quality_blockers_count=1` | 与 C-90 对比（同材料、不同决定） |
| C-92 | `BLOCKED` + `quality_blockers=[…]` | `REJECT` | **记录**，`false` | 同上 |
| C-93 | `FAILED` + `verification_failures=[…]` | 三种决定 | 均拒绝，`materials.quality.status`（13）；**不产生成功记录** | 与"有阻断但材料完整"分开 |
| C-94 | `status="OK"` 但 `quality_blockers` 非空（矛盾） | `HOLD` | `materials.quality.status`（2，矛盾） | **不得**靠矛盾状态让 HOLD 通过 |
| C-95 | `status="BLOCKED"` 但三列表全空（矛盾） | `APPROVE` | 同字段（2） | 一致性规则 |
| C-96 | `status="FAILED"` 但 `verification_failures` 空（矛盾） | `REJECT` | 同字段（2） | 同上 |
| C-97 | `execution_allowed` 边界 | C-91 记录 | 记录中 `execution_allowed is False`；记录**无** `gate1_approval`/`gate2_approval`/`next_step_allowed`/AI 字段 | 固定"不放行"边界，非放行接口 |

---

## 8. 哈希格式与普通 ID（C-98—C-105；协议 §3.5）

| 编号 | 字段/关系 | 隔离构造 | 预期结果（唯一最早字段/步） | 为何不被更早错误遮蔽 |
| --- | --- | --- | --- | --- |
| C-98 | 文件 SHA 尾 LF | `files[0].file_sha256="bbb…b\n"` | `materials.files[0].file_sha256`（2，格式） | fullmatch |
| C-99 | 派生字段尾 CRLF | `materials_fingerprint="…\r\n"` | `materials.materials_fingerprint`（2，格式） | 同上 |
| C-100 | 预期材料指纹尾空格 | `expected_materials_fingerprint="…"+" "` | `expectations.expected_materials_fingerprint`（3，格式） | 同上 |
| C-101 | 大写十六进制 | 任一哈希字段改为大写 | 对应字段（2/3，格式） | 仅小写 |
| C-102 | 截断哈希 | 任一哈希字段前 63 位 | 对应字段（2/3，格式） | 长度检查 |
| C-103 | 普通 ID 恰为 64 位十六进制（正向） | 同 C-08 | **成功** | 格式规则**只**约束哈希字段 |
| C-104 | 普通 ID 前导零（正向） | 同 C-07 | **成功** | 同上 |
| C-105 | 普通 ID 含 `SIM-EV-` 前缀（正向） | BASE1，`event_id="SIM-EV-0001"`，`actor_kind="HUMAN_DECLARED"`，其余合法 | **成功**；**不因前缀判为模拟** | 前缀不是来源凭证；协议不做 ID 前缀判断 |

---

## 9. 确定性与异常分列（C-106—C-111；协议 §13）

| 编号 | 字段/关系 | 隔离构造 | 预期结果（如何验证） | 说明 |
| --- | --- | --- | --- | --- |
| C-106 | 同输入同结果 | BASE1 连续两次调用 | 两次 `record_fingerprint` 相同 | 确定性 |
| C-107 | 返回深拷贝、无别名 | BASE1；修改返回对象内部字段 | 入参与第二次返回不受影响 | 单独验证 |
| C-108 | 输入不被修改 | BASE1；调用前后比较全部入参（含 `prior_history`）的规范指纹 | 均不变 | 单独验证 |
| C-109 | 嵌入指令只作字符串 | 同 C-12 | 文本原样保留、不触发控制流 | 单独验证 |
| C-110 | 协议错误与内部错误分列 | (a) 协议违规；(b) 设计注入使内部实现抛意外异常（**仅设计，不实施**） | (a) `HumanGateDecisionBlocked(field=…)`；(b) `HumanGateDecisionError` 且保留 `__cause__` | 两者异常类型不同 |
| C-111 | 不产生状态迁移 | BASE1；检查调用未产生文件/库/网络副作用 | 无副作用（未来验证方法；**本卡不运行**） | 单独验证 |

> C-110/C-111 只列**未来验证方法**；本卡不实施注入、不运行任何调用，也不提供"守卫命中 0""调用计数 0"之类运行结论。

---

## 10. 编号迁移与计数

| 旧编号（TASK-020 / R1 版） | 本版编号 | 处理 |
| --- | --- | --- |
| C-01—C-08 | C-01—C-08 | 保留；C-08 保持**正向**（三处同步为 64 位十六进制字符串），摘要改为按合法顺序推导 |
| （原 §0.3 的"单点错批次"，曾与 C-08 混用） | **C-117** | **新编号**：只改 `materials.batch_id`，提交/预期保持 `FIXTURE-BATCH-A`，第 5 步拒绝（与 C-08 的正向用途分开） |
| C-09—C-13 | C-09—C-13 | 保留（C-09 负向、C-13 提及 D2 的原文保留对照） |
| C-14—C-47 | C-14—C-47 | 保留；步骤口径按 §5 统一（C-32 常量类型在第 2 步） |
| C-48（时间非字符串） | C-48 | 定位改为**第 1 步**（类型） |
| C-49—C-62 | C-49—C-62 | 保留 |
| C-63（`contract_effective=false`） | C-63 | 定位统一为**第 2 步**（常量类型/值） |
| C-64—C-66 | C-64—C-66 | 保留 |
| C-67—C-68 | C-67—C-68 | 定位改为**第 1 步**（按 Gate 形状规则） |
| C-69 | C-69 | 去掉 3/11 双口径 → **第 3 步** |
| C-70—C-78 | C-70—C-78 | 保留（步骤细化为 11a—11i） |
| C-79 | C-79 | 去掉 11/12 双口径 → **第 11i 步** |
| C-80—C-81 | C-80—C-81 | 保留 |
| C-82—C-83 | C-82—C-83 | 保留（第 12 步） |
| C-84（历史内重复 ID） | C-84 | 定位改为**第 4 步**（名单唯一性） |
| C-85—C-111 | C-85—C-111 | 保留 |
| —（新增，R2 B2） | **C-112—C-116** | 新增：前序运行绑定四个隔离反例（代码/规则/配置/输入）+ 同版本正向对照 |
| —（R3 E1 修正） | C-112—C-115 | **配方与派生值重做**：改为"先复算变化后的前序**材料**指纹、再构造并复算前序**记录**指纹"，并同步前序提交/独立预期与本次 Gate2 三处前序绑定；R2 旧值（对应旧材料指纹）作废 |
| —（R3 非阻断） | C-117 | 由 §0.4 定义**补入主表 §4**（不新增业务案例）；C-75 最早子步统一为 11b |

- **案例计数**：本版共 **117 个唯一编号**（C-01—C-117），**连续、不重号、无字母后缀**；**主表即本文件 §1—§9，共 117 行**（R3 已把 C-117 补入 §4 主表），未借助"全文去重"掩盖主表重号。§0.4 与 §5 中对同一编号的重复提及是**引用**，不计入新增统计。

---

## 11. 未执行声明

- 全部案例均为**设计期望**，本卡**未运行**任何拟定函数、未实施任何注入、未验证任何"预期成功/拒绝"；无测试结果、无 PASS 计数。
- 夹具按 §0.1 **先构造合法对象再算摘要**；C-112—C-115 按 R3 卡 §3.1 的顺序**先复算前序材料指纹、再构造并复算前序记录指纹**，完整对象集合另存于 TASK-020-R3 证据根。摘要核算脚本仅在本轮证据根、使用标准库，**不构成**对拟定 API 的实现或调用；独立核验另由**不导入构造器**的书面对象核验器完成（TASK-020-R2 证据根为基准夹具，TASK-020-R3 证据根为这四个前序变更例与首次独立重建）。
- 本节案例期望均为**书面反例满足构造关系**的设计说明：**未运行**不存在的核心、**未实际捕获**任何异常；第 11f 步只是按协议文字预期的唯一最早定位点。
- 未生成真实 Gate 记录、真实人类初判或 `0009`；不涉及持久化/宿主/AI/终判；未提前运行规则筛查、未修改冻结控制器。
