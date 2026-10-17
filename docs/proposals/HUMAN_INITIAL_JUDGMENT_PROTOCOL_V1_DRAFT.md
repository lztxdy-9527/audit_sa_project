# 人类独立初判协议 V1（拟定，未实现）

标识：**HUMAN_INITIAL_JUDGMENT_PROTOCOL_DESIGN_NOT_IMPLEMENTED**

设计版本：`TASK-034-human-initial-judgment-design-1.0`。本文件是 TASK-034 文档交付；下列函数、类型、状态、记录和新材料封装均为**拟定/未实现**。不创建运行配置、批准或初判。本轮最新接受基线是 TASK-033-R1 的 166017 项快照，不再以 TASK-032 或 TASK-033 拒绝现场代表当前接受状态。

依据：[正式契约 V1](../AUDIT_CONTRACT.md) §3、§5、§7—§9、[生效登记](../decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md)、[D1/D2/D3](../decisions/REAL_FLOW_DECISIONS_20261013.md)、[分阶段方案](REAL_FLOW_INTEGRATION_PLAN_DRAFT.md)、[事实层接受评审](../reviews/REVIEW_TASK_033_R1.md)。确切源文件 SHA/长度及支持断言见 `data/initial_judgment_protocol_checks/task034_run_01/reference_registry.json`。

正式 V1 已由人类建立并确认生效，确切文件 SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`。D2/D3 持续有效，不再征求；旧方案/纪要中的“契约尚未建立”是历史时点，不回写。范围仅合成数据的人类初判校验与未来保存，建设许可不批准批次。

## 1. 拟定唯一纯内存接口

```python
build_human_initial_judgment_record(
    submission: dict,
    materials: dict,
    expectations: dict,
    *, prior_history: dict | None = None,
) -> dict  # 恰 {"record", "record_fingerprint"}；当前尚未实现
```

`prior_history` 语义必填；默认 None 仅为使省略/显式 None 进入函数体，均在步骤4结构化拒绝，不先抛参数缺失 TypeError，不默认空历史或完整性 true。前三位置参数按正常 Python 调用约定必填；本协议不承诺捕捉函数体之外的错误调用签名。

未来核心只校验收到的内存对象和调用方独立预期。**不读文件/DB/工作簿/网络/时间/随机/环境，不导入宿主、上游、现有模拟核心、测试、答案册或 LLM；不生成身份、事件ID、决定时间、初判、原因、取证要求。** 不重新计算金额、规则、复算或事实卡，不渲染/改写事实模板。

拟定异常：

- `HumanInitialJudgmentBlocked(field: str, reason: str)`：协议/类型/关系拒绝；属性 field 为完整路径，reason 为非空说明，reasons 固定为 `[reason]`（保留原说明，不以默认成功替代）。不返回 record。
- `HumanInitialJudgmentError(stage: str, reason: str)`：意外内部运行错误；属性 stage、reason、reasons=`[reason]`；使用 `raise ... from exc` 保留 `__cause__`。Blocked 原样传播；不以捕获 KeyError/TypeError 冒充前置字段检查。
- 没有 CLI/退出码/保存接口。异常文本不是身份判断或审计结论。

## 2. 通用类型、文本和摘要

所有自有对象封闭键集合，缺失字段先验存在再消费；未知键拒绝。字典键必须为 str；列表、对象、字符串、bool、int 使用严格实际类型。本协议 integer 字段只接受 `type(x) is int`，不接受 bool/float；常量布尔用 `is True/False`。JSON 必须可用下列 canonical 序列化，禁止 NaN/Infinity、bytes、set、非字符串键等非JSON值。

```text
C(x) = json.dumps(x, ensure_ascii=False, sort_keys=True,
                  separators=(",", ":"), allow_nan=False).encode("utf-8")
FP(x) = sha256(C(x)).hexdigest()
FILE(raw_bytes) = sha256(raw_bytes).hexdigest()
```

`FP` 仅规范对象指纹；`FILE` 仅确切原始文件字节 SHA，二者不互换。所有 SHA 字段使用 `[0-9a-f]{64}` **fullmatch**，恰64位，不 strip/截断/转小写；尾 LF/CRLF/空格及大写拒绝。两个摘要偶然数值相等不使其角色可互换。

普通 batch_id/request_id/event_id/actor_id/finding_id/declared_scope 只要求 str 且 `.strip()` 判非空，**保存原串**；不排除64hex形状、不按前缀认定模拟或AI、不作为磁盘路径使用、不做Unicode/大小写/数字规范化。自由文本 assessment/reason/note/request/declaration_note 同样去空白判非空但逐字符保存，允许换行、首尾空格、指令样式文字；只作数据，不执行，不靠关键词推断作者或独立性。

## 3. 提交对象（人类明确输入）

`submission` 必需**9键**，仅有**2个可选键**：

- submission_version：常量 `TASK-034-human-initial-judgment-submission-1.0`。
- event_id、batch_id：原字符串ID；不由核心生成。
- request_binding：恰 `{request_id, materials_fingerprint}`；原请求ID、材料规范指纹。
- submission_source：常量 `HUMAN_INITIAL_JUDGMENT`，是结构来源声明，不是认证凭证。
- actor：恰 `{actor_kind, actor_id, declaration_note}`；actor_kind 唯一 `HUMAN_DECLARED`，其余非空原文。
- decided_at_raw：人类提供的原决定时间，规则见§4。
- assessment、reason：批次初判及原因均必填非空原文，**不是审计结论枚举**；有原因的暂不能判断有效，无须先给确定结论。不检索/填入聊天倾向或AI候选。
- 可选 finding_notes：list，成员恰 `{finding_id, note}`，均非空原文。ID只可来自当前包，成员ID唯一；允许只注释部分线索，未注释不等于已判断。
- 可选 evidence_requests：list，成员恰 `{finding_id, request}`。finding_id 为当前包原ID或 null（批次通用需求）；request 非空原文。相同 `(finding_id, request)` 规范字节二元组不可重复；同一线索可有不同需求，不使用臆造的证据类型枚举。

两个可选键省略时仅在**输出副本**补 `[]`，显式空列表同义；显式 null/错类型拒绝。保留两列表的输入顺序，不排序、合并或改写；原 submission 不变。规范化后的提交固定**11键**。零条 finding_ids 时 finding_notes 只能空；evidence_requests 仍可有 finding_id=null 的批次需求。**零线索仍须9项人类提交，不自动生成“无问题”。**

来源为 AI/SYSTEM/SIMULATED_HUMAN、模拟协议/version、D2纪要对象、旧phase/approval bool 或任何越界代签字段时，按结构拒绝。核心不能从一段合法自由文本辨别人类是否独立完成；一个人在 reason 中提及 D2 或写入指令样式文字不因此非法，也不因此得到新权限。

## 4. 原始人类时间（沿用人工Gate口径）

恰两种**全串匹配**写法：`YYYY-MM-DD` 或 `YYYY-MM-DDThh:mm:ss±hh:mm`。

- 年0001—9999，真实公历日期，含闰年；月01—12及该月实际日数。
- 时间 hh00—23、mm/ss00—59，无闰秒；偏移时00—14、分00—59，14时只能00分，含±14:00。
- 日期单独写法是允许的日精度，不补时间/时区；有时间则必须有偏移。拒绝无偏移datetime、Z、小数秒、缺秒、空格分隔、尾空白、`+0800`、超界偏移。
- 失败 field 固定 `submission.decided_at_raw`；输出原串不变、`decided_at_source="HUMAN_PROVIDED_RAW"`，不生成 normalized 时间，不与系统当前时间/Gate时间比较先后，不编造时区或精度。
- 正式契约头部的生效时间是另一种已登记用途，不套本规则反向否定生效；技术保存/登记时间也不是决定时间。

## 5. 已核验事实材料封装（新设计，不是现有API返回）

`materials` 恰**10键**：materials_version、batch_id、runtime_version、entity、contract_binding、run_binding、fact_snapshot、gate_links、files、materials_fingerprint。

materials_version 常量 `TASK-034-human-initial-judgment-materials-1.0`；batch_id、runtime_version 非空原串。entity 恰 `{company,currency,period,cutoff_date}`，period 恰 `{period_start,period_end}`，固定值与现行packet一致：澄明商贸有限公司、`人民币（CNY）`、2026-09-01—2026-09-30、截至2026-09-30。金额整数分，四表 suppliers/payables/payments/allocations，原ID保留；主表/分摊分别计量，缺失应付关联不丢弃，线索不是损失、舞弊或正式审计结论。

contract_binding 恰 `{contract_version,contract_file_sha256,contract_effective}`，本版 V1/正式文件确切 FILE/严格 true；与独立 expected_contract **整对象规范相等**。纯核心不把自报true当作已实读生效；未来适配层须实读正式文件及生效登记，不用候选或旧draft SHA代替。

run_binding 恰四键，六项值：

```text
code   = {file_sha256, manifest_fingerprint}
rules  = {version, manifest_fingerprint}
config = {file_sha256}
input  = {file_sha256}
```

所有嵌套键集合封闭；rules.version 非空原串，其他为SHA。单文件 FILE 与代码/规则清单 FP 分列，沿已验收运行登记的实际含义，不另造清单正文。与独立 expected_run_binding 整对象严格规范相等；Gate1/Gate2 的共同运行六项也相等，**各阶段 materials_fingerprint 不要求相同**。runtime_version 与独立预期精确相等，不凭版本前缀猜合法；后续代码/初判组件加入运行绑定由后卡规定，新代码不能复用旧运行凭证。

### 5.1 fact_snapshot（恰5键）

- inspect_binding：恰 `{stage_version,status,batch_id,run_binding_sha256}`。前两常量分别 `TASK-033-fact-packet-1.0` / `RT_FACT_PACKET_RECORDED`；batch_id 与本批相同；最后一项为 FP(materials.run_binding)。这些是从实读事实核验返回及登记产生的投影，不是调用方可用phase/bool替代的证据。
- packet：完整已核验事实包JSON对象；对象 FP 与下述及独立预期比较。上游显示模式仍是冻结模板 `DEVELOPMENT_TEST_ONLY`，**不改标签**。
- packet_canonical_sha256：FP(packet)。不是 fact_packet.json 的 FILE，也不是Markdown FILE。
- finding_ids：packet.findings 中 finding_id 的**原顺序**列表；严格非空字符串、唯一，允许空列表。
- source_fingerprints：恰 `{workbook_sha256, normalized_payload_sha256, screening_report_sha256, crosscheck_report_sha256}`；分别等于 packet.bindings 同名字段。workbook为FILE并等于run_binding.input.file_sha256；其余三个为对应已消费对象FP，不把它们当JSON文件FILE。

packet 的顶层恰现行12键 packet_version/batch_status/mode/next_step_allowed/entity/banner/bindings/summary/reconciliation/findings/amount_labels/limits；常量分别 `TASK-008-fact-packet-1.1`/`DEV_FACT_PACKET_READY`/`DEVELOPMENT_TEST_ONLY`/严格false，entity同本批。bindings恰现行6键：四项source_fingerprints加upstream_versions、upstream_declared_database（均JSON对象）；findings每项恰现行12键 finding_id/rule_id/rule_name/rule_template/hit_key/amounts_cents/amounts_display_cny/related_ids/source_rows/evidence/context/refund_summary，R03额外且必须 missing_kind。rule_id属于R01—R04；finding_id唯一；summary恰 rule_counts/total_findings/involved_payments/r02_overpayment_total_cents/r02_overpayment_basis，rule_counts恰四规则严格非负整数，和实际规则个数一致，total_findings为严格非负整数且等于list长；r02_overpayment_total_cents为严格整数。

初判核心只消费上述身份/常量/ID/计数/来源指纹，并核对整个packet FP；不重新实现已验收事实上下文、金额、退款算法或模板。上述其余既有上游字段是**原样不透明JSON载荷**，不是本协议的新扩展点：其业务完整结构/语义必须由未来适配层真实 `inspect_gate2_fact_packet` 先核验；本纯核心不声称独立复验了上下文、DB或Markdown。自有schema未知键拒绝不等于在新核心重做所有上游数据schema。

expected_fact_binding 恰 `{inspect_binding,packet_canonical_sha256,finding_ids,source_fingerprints}`，等于 fact_snapshot 去掉 packet 后的投影；其预期必须从未来调用方独立核验取得，不能由待验candidate重建。

### 5.2 gate_links（恰gate1/gate2）

两成员各含共同**10键** `{gate,batch_id,event_id,record_fingerprint,record_file_sha256,materials_fingerprint,contract_binding,run_binding,decision,actor_kind}`；gate2 额外且必须 `prior_gate1_fingerprint`。gate为对应GATE1/GATE2，decision严格APPROVE，actor_kind严格HUMAN_DECLARED；batch同本批、event_id非空原串；所有摘要完整64hex。

contract_binding、run_binding与本批整对象规范相等；gate2.prior_gate1_fingerprint=gate1.record_fingerprint；两gate的事件ID不要求彼此不同（Gate命名空间不同）。两阶段守门材料摘要允许不同，不能以初判材料摘要替换它们。gate_links 全对象还须与独立 expected_gate_links 规范相等。

这些成员是**未来适配层对已核验完整Gate记录的绑定投影**，不是完整P1记录，不代替其真实性/历史/质量核验。本核心不接受APPROVE字符串、effective=true、开发phase或“已保存”bool替代投影和独立预期。未来适配层必须真实调用 `verify_gate1_effective_approval`（effective严格true、APPROVE/HUMAN_DECLARED、reasons空）及 `verify_runtime_gate2_decision`，对后者的完整record核对APPROVE/人类声明/同批/前序/契约/运行；**现有Gate2 verify没有新设计effective许可，不凭空读该键**。再由真实fact inspect通过、当前文件实读及末次复确认共同形成本材料和独立预期。仅给核心两份相同伪造对象不能证明磁盘或真实人类批准。

### 5.3 files（恰8角色，与独立名单双向相等）

每成员恰 `{role,relative,file_sha256,byte_size}`。role恰且各一次：`facts.started`、`facts.packet`、`facts.markdown`、`facts.artifacts`、`runtime.registry`、`contract`、`gate1.record`、`gate2.record`。分别表示本运行四件事实文件、runtime_registry.json、正式AUDIT_CONTRACT.md、两事件snapshots/decision_result.json；**不是完整批次备份名单**。

relative为未来调用方实读的项目相对POSIX路径，非空，不以/开头，不含反斜杠、冒号、空段、`.`/`..`段，不作路径归一化。按relative的UTF-8字节序严格升序且唯一，role唯一；byte_size严格非负int，file_sha256=对应确切文件FILE。expected_files形状相同的8项list，完整比较角色/路径/大小/SHA和顺序，缺/多/重复均拒绝；核心不读取这些路径。

contract角色SHA=contract_binding.contract_file_sha256；gate1.record/gate2.record角色SHA=对应record_file_sha256。packet四文件SHA分列，facts.packet FILE不得冒充packet_canonical_sha256。实际packet FILE与对象FP怎样由同缓冲读数闭合、artifacts/start内部绑定和Markdown原字节怎样验证，是未来适配层及现有inspect职责；本内存对象没有文件缓冲，不能凭packet对象重造原文件FILE或宣称逐字节验证。

本协议固定8个直接绑定角色，只代表这份初判材料封装。代码/规则/原始工作簿/DB/接收范围/装载/筛查/复算等的完备性由运行登记、实读Gate核验和fact inspect沿现行链核对，**不能因这8项而略过依赖链或声明“全项目材料完整”**。

### 5.4 唯一材料摘要正文

`materials_body = materials 顶层恰删除 materials_fingerprint 后的其余9键`；嵌套、字符串和所有列表原序不动，不置null、不任选排序。

```text
M = FP(materials_body)
M == materials.materials_fingerprint
  == submission.request_binding.materials_fingerprint
  == expectations.expected_materials_fingerprint
```

名单先满足既定顺序再求摘要；核心拒绝无序输入，不排序修复它。不得对带自身摘要的完整materials求FP。file字节SHA继续逐项与expected_files比较，不能被这个外层M替代。

## 6. 独立 expectations（恰12键）

expectations_version 常量 `TASK-034-human-initial-judgment-expectations-1.0`；其余恰：expected_batch_id、expected_request_id、expected_materials_fingerprint、expected_contract、expected_runtime_version、expected_run_binding、expected_fact_binding、expected_gate_links、expected_files、expected_history_scope、expected_prior_history_fingerprint。

ID/版本非空原串、摘要64hex；contract/run/fact/gate/files结构见§5。expected_contract包含严格true及正式V1，不以候选替代。expected_history_scope非空原串，等于prior_history.declared_scope；expected_prior_history_fingerprint=FP(已由调用方核验后固定的prior_history完整三键对象)，不内嵌于该对象。

来源要求：未来保存/适配层自己实读本次运行/事实/契约/Gate/历史，在接收人类提交之前固定独立预期；保存时重新核验当前材料并比较，不能接收旧request直接保存，不从submission推导预期，也不能在发现candidate变化后刷新预期凑相等。核心只判断关系，不验证调用方的独立性或完整性。

## 7. 声明历史、首版不可覆盖

prior_history恰 `{declared_complete,declared_scope,records}`。declared_complete必须严格true，否则Blocked；declared_scope须与独立expected_history_scope相等。records是本次调用方**已核验记录索引快照**，不是原始完整record，不接受随便拿部分历史record充当索引。

每个索引成员恰 `{event_id,batch_id,record_fingerprint,binding_fingerprint}`，前两非空原ID，后两64hex。排序按event_id UTF-8字节升序、唯一。record_fingerprint表示历史完整record的FP，binding_fingerprint表示该record.binding的FP。未来保存/恢复层必须先实读历史完整提交/材料/预期/历史/核心返回，核验完整record形状、正文FP与绑定，才提取索引；不得仅看这四字段声称历史已核验。**本纯核心仅比较索引schema、独立历史FP与当前去重，不声称验证了未传入的完整历史正文。** 这一设计避免重复实现完整恢复框架，也避免把索引当完整record。

缺省/None、完整性false/非bool、空scope、坏成员/重复/乱序均拒绝；显式三键true+正确scope+空records是合法空历史，完整性来自调用方真实枚举，不来自默认值。FP(prior_history)与独立expected_prior_history_fingerprint相等才可用。

本版仅首个初判：若提供范围内存在同event_id，拒绝 `submission.event_id`；若任何已核验索引batch_id等于当前batch_id，即使不同事件/材料也拒绝 `prior_history.records`，不得覆盖或冒称修订。其他批次合法索引可保留，不强求它们采用当前运行/契约版本；当前提交仍必须匹配本批独立预期。只在declared_scope内去重，不发现范围外隐藏历史。

数据/规则/代码/配置/契约/范围/事实变化后，必须新运行/新批次并重新取得守门及人类提交；本版没有“同批换材料继续沿用”或旧记录迁移路径。人类以后如需更正判断，须另卡设计**追加新事件及原件关系**，不得在本首版临时引入覆盖、自动迁移或补签。

## 8. 固定核验顺序与定位

同一步多错按下方schema键顺序/列表原序，先报最早缺失/类型/未知键；未知键按UTF-8序。每个字段缺失指向 `对象.字段`，未知键指向 `对象.未知键`。后步反例须先满足此前所有步骤。

1. submission：9必需/2可选键，嵌套schema、类型、非空、source/actor常量；可选成员形状/原文/重复语法；时间这里只验str非空。版本及未知AI/终判/phase/bool字段在此拒绝。
2. materials：封闭10键与全部自有嵌套schema/常量/严格类型/SHA格式；packet只校验§5.1指明的结构/身份字段，不重算业务。文件角色/名单排序唯一，finding_id唯一、计数类型在此。
3. expectations：封闭12键及相应嵌套schema/常量/类型/SHA/名单规则；缺失/null不回退到materials。
4. prior_history：必需三键、完整性、索引形状/类型/排序唯一；省略/None在此Blocked。
5. 人类时间真实日历/偏移校验；随后 batch三处、请求两处、runtime_version、contract/run本批与独立预期整对象相等。field分别指submission.decided_at_raw、submission.batch_id、submission.request_binding.request_id或materials对应字段。
6. 复算§5.4正文M，按 `materials.materials_fingerprint` → `submission.request_binding.materials_fingerprint` → `expectations.expected_materials_fingerprint` 顺序闭合。
7. files与独立expected_files双向完整比较；按materials.files的原下标定位缺/多/不等字段，列表缺额角色定位materials.files；再核对contract/Gate角色SHA与内层声明。
8. fact_snapshot：先packet FP与自报packet_canonical_sha256、独立expected_fact_binding.packet_canonical_sha256闭合；再finding_ids/summary个数、四项来源、inspect_binding本批/运行；最后整个fact_binding与独立投影规范相等。gate_links的同批、契约/运行、APPROVE/HUMAN_DECLARED、Gate2前序FP关系及全对象与独立expected_gate_links在此核对。定位实际矛盾成员，不以更新外层M掩盖。
9. 可选备注/取证ID属于本包、重复二元组、零条备注规则；未知ID定位对应finding_id，重复定位第二次成员的finding_id（备注）或request（取证）。
10. 历史scope/独立FP；按schema顺序先scope、再FP、再当前event重复、再同批已有记录。只根据当前有界快照判断。
11. 按§9构建深拷贝record，复核消费输入未改；FP(record)返回外层。不得在失败时生成成功record或默认字段补救。

所有结构/关系检查在实际消费前执行，不把缺字段交给后续代码报KeyError。协议异常保留field/reason；意外错误Error(stage="internal", reason=原错误说明)保留cause链，不生成成功记录。未实现阶段不能声称这些拒绝已实测。

## 9. 返回（封闭9键record，无自指）

外层恰 `{record,record_fingerprint}`，record_fingerprint=FP(record)，record不内嵌自己的FP。record恰：

- record_version：`TASK-034-human-initial-judgment-record-1.0`。
- record_status：`HUMAN_INITIAL_JUDGMENT_VALIDATED`。
- mode：`LOCAL_DECLARED_SYNTHETIC`，不是旧模拟身份/状态换标签。
- binding：恰10键 `{batch_id,request_id,materials_fingerprint,runtime_version,entity,contract_binding,run_binding,fact_binding,gate_links,files}`；来自已核验本次输入深拷贝，fact_binding为§5.1投影，不重复整包。
- human_initial_judgment：§3的11键提交副本（只补省略可选键为空列表，原文不改）。
- decided_at_source：常量 `HUMAN_PROVIDED_RAW`。
- history_binding：恰 `{declared_scope,prior_history_fingerprint}`，后者FP(本次三键prior_history)，对应独立预期。
- boundaries：恰8键 persisted/execution_allowed/next_step_allowed/ai_enabled/final_judgment_recorded/identity_authenticated/source_authenticity_proven/audit_conclusion_formed，**全严格false**。
- note固定原文：`仅在内存校验人类明确提交及其绑定；未保存，不批准执行，不认证身份，不形成审计结论，不开放AI或终判。` 不追加夹具说明或时间。

同样输入产生相同C(record)/FP；字典键顺序不影响，列表顺序与人类文本变化可影响。返回深拷贝无输入别名；更改返回不影响输入。VALIDATED只说明内存输入关系成立，**不等于RECORDED、不等于获批/已保存初判**。本核心不会写出RECORDED状态；未来存储须另定义存储结果，不把内存record.boundaries.persisted改true冒称本函数已保存。

### 9.1 机器可读schema登记（描述键集合，不是可提交样例）

<!-- TASK034_SCHEMA_BEGIN -->
```json
{
  "submission_required": ["submission_version", "event_id", "batch_id", "request_binding", "submission_source", "actor", "decided_at_raw", "assessment", "reason"],
  "submission_optional": ["finding_notes", "evidence_requests"],
  "request_binding": ["request_id", "materials_fingerprint"],
  "actor": ["actor_kind", "actor_id", "declaration_note"],
  "finding_note": ["finding_id", "note"],
  "evidence_request": ["finding_id", "request"],
  "materials": ["materials_version", "batch_id", "runtime_version", "entity", "contract_binding", "run_binding", "fact_snapshot", "gate_links", "files", "materials_fingerprint"],
  "entity": ["company", "currency", "period", "cutoff_date"],
  "period": ["period_start", "period_end"],
  "contract_binding": ["contract_version", "contract_file_sha256", "contract_effective"],
  "run_binding": ["code", "rules", "config", "input"],
  "code": ["file_sha256", "manifest_fingerprint"],
  "rules": ["version", "manifest_fingerprint"],
  "config": ["file_sha256"],
  "input": ["file_sha256"],
  "fact_snapshot": ["inspect_binding", "packet", "packet_canonical_sha256", "finding_ids", "source_fingerprints"],
  "inspect_binding": ["stage_version", "status", "batch_id", "run_binding_sha256"],
  "source_fingerprints": ["workbook_sha256", "normalized_payload_sha256", "screening_report_sha256", "crosscheck_report_sha256"],
  "fact_binding": ["inspect_binding", "packet_canonical_sha256", "finding_ids", "source_fingerprints"],
  "gate_common": ["gate", "batch_id", "event_id", "record_fingerprint", "record_file_sha256", "materials_fingerprint", "contract_binding", "run_binding", "decision", "actor_kind"],
  "gate2_extra": ["prior_gate1_fingerprint"],
  "gate_links": ["gate1", "gate2"],
  "file_entry": ["role", "relative", "file_sha256", "byte_size"],
  "file_roles": ["facts.started", "facts.packet", "facts.markdown", "facts.artifacts", "runtime.registry", "contract", "gate1.record", "gate2.record"],
  "expectations": ["expectations_version", "expected_batch_id", "expected_request_id", "expected_materials_fingerprint", "expected_contract", "expected_runtime_version", "expected_run_binding", "expected_fact_binding", "expected_gate_links", "expected_files", "expected_history_scope", "expected_prior_history_fingerprint"],
  "prior_history": ["declared_complete", "declared_scope", "records"],
  "history_entry": ["event_id", "batch_id", "record_fingerprint", "binding_fingerprint"],
  "record": ["record_version", "record_status", "mode", "binding", "human_initial_judgment", "decided_at_source", "history_binding", "boundaries", "note"],
  "record_binding": ["batch_id", "request_id", "materials_fingerprint", "runtime_version", "entity", "contract_binding", "run_binding", "fact_binding", "gate_links", "files"],
  "history_binding": ["declared_scope", "prior_history_fingerprint"],
  "boundaries": ["persisted", "execution_allowed", "next_step_allowed", "ai_enabled", "final_judgment_recorded", "identity_authenticated", "source_authenticity_proven", "audit_conclusion_formed"],
  "outer": ["record", "record_fingerprint"]
}
```
<!-- TASK034_SCHEMA_END -->

## 10. 未来保存/恢复与实施分卡边界

后续纯核心、独占保存/只读恢复、运行适配分别验收。本卡不命名实现文件、不设计目录框架/锁/详细端点/新运行profile。未来至少保存接收到的submission对象快照、materials、expectations、prior_history、完整核心返回；技术保存登记时间单列，来自保存程序，绝不写回decided_at_raw或由其冒充人类时间。

内存入口只承诺人类字符串原文及对象快照，不承诺原JSON文件排版/换行/BOM保真；未来文件输入需要原字节时另存确切字节/FILE并独立绑定对象FP，须另卡。未来独占写、读回、失败优先、末次原字节确认、审核失败支配返回沿现行原则；本协议没有实现这些能力。

未来适配层须自己真实核验当前 Gate1/Gate2/fact inspect、全依赖/目录集合/无failure/版本/契约及完整历史，再建立本材料与独立预期；保存前再次实读比对，不能信任旧请求或自报phase。材料变化停、新运行/新批次。初判记录另说明当前状态，冻结packet/Markdown中的“尚未保存判断”开发模板历史原文不回写；保留两者来源时点说明。

## 11. 来源、夹具缺口及停止

本轮没有新的人类初判提交。案例只用符号引用H_EVENT/H_ACTOR/H_TIME/H_ASSESSMENT/H_REASON等外部人类值，**不是可填写的默认字符串**，不得把符号名填入表单称为人类决定。现有Gate夹具仅能说明Gate原字段，不把其APPROVE/reason改标签当初判。旧 `build_demo_initial_judgment.py` 的 SIMULATED_HUMAN/SIMULATED_TEST_ONLY/DRAFT_NOT_IN_FORCE及全部旧记录冻结，不复用/转换/迁移/补签。

未来实施若需真实调用测试的合成人类初判字段，必须先有独立登记的新夹具来源；当前缺口如实登记，**不阻塞本卡符号协议与案例完成**，也不提前编造姓名、事件、决定时间或assessment/reason。自由文本意义、人类独立性、身份认证和来源业务真实性不能由程序证明。

不选模型、重要性/缺陷等级、外部框架，不生成AI建议或终判，不定义AI解锁许可。D2/D3、内存VALIDATED及未来保存成功均不自动开放AI。当前仍RT_FACT_PACKET_RECORDED，真实批准null、开发宿主0008、真实初判未保存、next/AI=false。文档完成后交Architect独立验收，执行端不自行ACCEPTED或推进下一张纯核心卡。
