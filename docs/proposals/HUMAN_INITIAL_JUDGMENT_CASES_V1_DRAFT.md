# 人类独立初判 V1 最小案例设计（未执行）

标识：**HUMAN_INITIAL_JUDGMENT_CASE_DESIGN_NOT_EXECUTED**

设计依据：[协议](HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md)，版本 `TASK-034-human-initial-judgment-design-1.0`。本文件34个编号案例仅为未来实施的设计输入，**未执行拟定函数，不记核心PASS/Blocked次数/守卫命中0**。没有新增人类初判，所有人类字段为外部值的符号引用，不是表单预填或真实事件。

## 1. 公共符号基样与隔离方法

**BASE** 是满足协议§2—§7全部关系的一组符号输入 `(S,M,E,H)`，不是当前可提交JSON或已核验运行凭证：

- `B`：同一已完成事实运行的原batch_id；`Q`：技术请求原ID；`V`：未来调用方实读登记的当前runtime_version；`R`：六项共享run_binding；`K`：正式V1/当前契约文件SHA/严格true。
- `P`：真实fact inspect通过后，由同次packet缓冲取得的完整原JSON对象；`PFP=FP(P)`；`FIDS`=P.findings的原finding_id序列；`SRC`=四项原来源指纹。
- `G1/G2`：未来实际Gate核验所得绑定投影，皆HUMAN_DECLARED/APPROVE，同B/K/R，G2.prior_gate1_fingerprint=G1.record_fingerprint；两Gate守门材料指纹允许不同。
- `FILES`：8个固定角色的确切原文件SHA/长度/路径，按relative UTF-8序严格升序，角色/路径各唯一。packet文件FILE与PFP分列，不假定二者相同。
- `H`：调用方在声明范围`D`真实枚举核验后的三键历史索引；首版空例是严格true、D、显式空records。`HFP=FP(H)`。
- `M`：协议10键材料；填全9键正文后最后求MFP并放materials_fingerprint。`E`：协议12键独立预期，由调用方自己的核验源固定，包含B/Q/V/K/R、PFP/FIDS/SRC/inspect投影、G1/G2、FILES、D/HFP及MFP。
- `S`：协议9必需键；event_id=`H_EVENT`，actor_id=`H_ACTOR_ID`，declaration_note=`H_DECLARATION`，decided_at_raw=`H_TIME`，assessment=`H_ASSESSMENT`，reason=`H_REASON`，技术绑定B/Q/MFP正确，结构来源HUMAN_INITIAL_JUDGMENT、actor_kind=HUMAN_DECLARED；可选两列表先省略。

**人类字段来源缺口**：H_EVENT/H_ACTOR_ID/H_DECLARATION/H_TIME/H_ASSESSMENT/H_REASON/H_NOTE/H_REQUEST均表示未来**人类明确提供并另行登记**的值，不是字面可提交字符串。本轮没有这些初判夹具。现有Gate字段不改标签充当初判；旧模拟字段不转换。H_UNCERTAIN表示人类实际提交“暂不能判断”的语义，仍是符号；未填写任何实际初判或原因。未来实施需要具体调用前先登记来源，不以本案例替人类造值。

每例独立深拷贝BASE，只改指定项。只读引用历史资料不等于重跑或迁移批准。共同构造步骤：先固定B/K/R/文件读数和G1/G2 → P/FP/FIDS/SRC → fact_snapshot → FILES排序 → M正文FP → S绑定/E独立预期 → H与其独立FP → 未来调用。禁止先计算摘要再改材料。

`R-M`表示**构造阶段**按唯一正文配方独立复算变更材料的MFP，同步M自报、S请求绑定和E.expected_materials_fingerprint；E其他值保持BASE。它只用于把“外层M失配”排除在待测内层矛盾之外，不是在运行检测中刷新预期，更不改变生产适配层的独立来源要求。每个使用R-M的案例显式说明哪一项独立预期仍保持原值；需要改变其他外层投影的案例另外列出，不作默认全同步。

除案例指定的末步外，所有更早步骤必须满足协议；field写相对于公开入口的完整路径。列表用`[i]`表示该隔离例中实际位置，未来实测应保存确切整数下标。类型/格式族按单字段逐个构造，不将多个错误混在同一输入掩盖最早拒绝。预期VALIDATED只指未来内存关系，不表示已保存、获批或AI开放。

## 2. 正向与人类输入

### IJ-01 合法批次初判
- **字段/关系**：协议§3/§5—§9，BASE全部绑定。
- **隔离构造**：使用BASE，9项人类提交来自未来已登记输入，两个可选键省略。
- **预期/定位**：未来返回恰两键；record恰9键，提交副本恰11键，两可选键为[]；record_fingerprint=FP(record)，八边界false。
- **排除遮蔽**：BASE的正式V1、最新事实/两Gate、独立预期、真实枚举空历史均先满足；符号未实例化前不得执行或称成功。

### IJ-02 有原因的暂不能判断
- **字段/关系**：submission.assessment/reason；协议§3。
- **隔离构造**：BASE中assessment引用H_UNCERTAIN，reason引用非空H_REASON；不新增结论枚举或AI字段。
- **预期/定位**：未来VALIDATED并原文保留；无确定结论要求，无AI许可。
- **排除遮蔽**：技术绑定不变；H_UNCERTAIN/H_REASON必须来自同次已登记人类提交，不是程序预填。

### IJ-03 零条线索仍有批次输入
- **字段/关系**：fact_snapshot.finding_ids/packet.findings/summary与submission；协议§3/§5.1。
- **隔离构造**：独立零线索事实基样P0，空finding_ids、四规则数0、total_findings=0；独立文件/事实预期正确重绑，R-M；S仍含H_ASSESSMENT/H_REASON。
- **预期/定位**：未来VALIDATED；不生成“无问题”，备注空；允许null finding_id的批次取证需求。
- **排除遮蔽**：不是只删findings而保留旧FP/计数；P0须来自未来已核验零线索材料，不能冒用当前C06b包。

### IJ-04 可选省略与空列表
- **字段/关系**：finding_notes/evidence_requests；协议§3/§9。
- **隔离构造**：两份BASE仅可选键省略与显式[]不同。
- **预期/定位**：未来C(record)及record_fingerprint相等；各自原submission保留原形不回写补键。
- **排除遮蔽**：其他输入完全相同；未将null当作空列表。

### IJ-05 当前线索备注
- **字段/关系**：submission.finding_notes[].finding_id/note；协议§3/§8步骤9。
- **隔离构造**：非零BASE中选一个原FIDS项及H_NOTE，仅部分线索有备注；原列表顺序保留。
- **预期/定位**：未来VALIDATED，ID/文本原文保存；未备注的线索不被自动判断。
- **排除遮蔽**：所选ID直接取当前P原ID，不凭rule_id或另一批次编号替代。

### IJ-06 明确取证需求
- **字段/关系**：submission.evidence_requests；协议§3。
- **隔离构造**：两成员分别指当前原finding_id及null，request各引用人类H_REQUEST，二元组不重复。
- **预期/定位**：未来VALIDATED、原顺序/原文保留；不替人类生成证据清单。
- **排除遮蔽**：成员恰两键，null只允许作为批次需求的finding_id，不能用空字符串替代。

### IJ-07 必需字段缺失、空白和错类型
- **字段/关系**：submission的9项及request_binding/actor必需成员；协议§2/§3。
- **隔离构造**：逐例仅删除一个必需键；或把assessment/reason/ID/declaration_note改为空白；或以7/true/[]替代str。另用显式null替代可选列表。
- **预期/定位**：步骤1 Blocked，field精确为被改路径，例如submission.reason、submission.actor.actor_id或submission.finding_notes。
- **排除遮蔽**：其余schema/技术绑定干净；无原因的H_UNCERTAIN只清空reason，不同时删actor或改指纹。

### IJ-08 越界键与伪保存状态
- **字段/关系**：submission自有schema；协议§3/§9。
- **隔离构造**：独立添加ai_suggestion/final_judgment/phase/human_initial_judgment_saved/approved等一个字段；嵌套actor也单独加入未知role。
- **预期/定位**：步骤1未知键Blocked，field指向新增键；自报bool或phase不生成已保存状态。
- **排除遮蔽**：全部必需键与常量保持正确；false、0、0.0都不能因Python相等绕过键集合检查。

### IJ-09 结构来源不能代签
- **字段/关系**：submission_source/actor.actor_kind/submission_version；协议§3。
- **隔离构造**：分别改为AI、SYSTEM、SIMULATED_HUMAN或旧模拟version；另把D2纪要对象或先前聊天倾向对象直接作submission。
- **预期/定位**：步骤1对应字段Blocked；D2纪要/聊天倾向对象缺submission_version先于其内容语义；没有批准或独立思考识别声明。
- **排除遮蔽**：常量反例只改该一项；纪要对象例仅声明“不是本schema”，不声称关键词识别纪要。

### IJ-10 零线索自动结论不可代替人类输入
- **字段/关系**：零线索不省略人类提交；协议§3/§11。
- **隔离构造**：用IJ-03技术材料；分别省略assessment/reason或使用SYSTEM结构来源企图自动填结论。
- **预期/定位**：步骤1对应人类字段/来源Blocked；正常H_ASSESSMENT/H_REASON仍按IJ-03接受，不因人类文本可能含“无问题”而关键词封禁。
- **排除遮蔽**：P0/文件/独立预期完整；拒绝依据是缺明确提交结构，不是零线索数量或文本审计观点。

## 3. 可选字段、绑定与类型

### IJ-11 备注错误ID、重复及空文本
- **字段/关系**：finding_notes成员；协议§3/§8。
- **隔离构造**：分别用不在FIDS的原字符串ID、重复第二个成员ID、note空白；每例只一个问题。
- **预期/定位**：未知ID步骤9定位submission.finding_notes[i].finding_id；重复/空文本按步骤1语法检查定位第二个finding_id或note。
- **排除遮蔽**：ID格式本身非空合法，技术绑定不变；不以空ID掩盖“不在当前包”。

### IJ-12 取证成员关系与重复
- **字段/关系**：evidence_requests；协议§3/§8。
- **隔离构造**：分别缺request、多未知键、request空白、非法非null/非str的finding_id、未知但非空ID、重复同一规范二元组。
- **预期/定位**：形状/类型/空白/重复语法在步骤1；成员归属在步骤9，field对应finding_id或request。不同request的同线索正向允许。
- **排除遮蔽**：一次只改一个成员属性；重复例两条完整且当前ID合法，null批次需求本身不判非法。

### IJ-13 错批次或请求
- **字段/关系**：submission.batch_id/request_binding.request_id；协议§6/§8步骤5。
- **隔离构造**：只改S的原ID为另一个非空字符串，M/E维持BASE。
- **预期/定位**：步骤5 Blocked submission.batch_id或submission.request_binding.request_id。
- **排除遮蔽**：不修改材料，MFP不需重算；不把错ID写成7触发步骤1。

### IJ-14 材料摘要三处闭合
- **字段/关系**：materials_body及三处声明；协议§5.4/§8步骤6。
- **隔离构造**：分别只改M自报、S材料绑定、E材料预期为另一合法64hex；另错误对带自身摘要整个M求FP后放自报。
- **预期/定位**：步骤6按协议顺序定位materials.materials_fingerprint、submission.request_binding.materials_fingerprint、expectations.expected_materials_fingerprint。
- **排除遮蔽**：64hex格式合法、全部内部材料保持BASE；自身摘要错误配方不被当作“允许任选算法”。

### IJ-15 事实变化与旧独立预期
- **字段/关系**：fact_snapshot.packet_canonical_sha256；协议§5.1/§8步骤8。
- **隔离构造**：改P中一个原事实字段，复算自报packet FP和R-M；E.expected_fact_binding.packet_canonical_sha256仍旧PFP。
- **预期/定位**：步骤8 Blocked expectations.expected_fact_binding.packet_canonical_sha256（独立预期不等）。
- **排除遮蔽**：packet仍为合法JSON、schema/ID/类型；自报packet摘要真实对应候选，排除更早自报不符。不是声称改后事实已获真实inspect核验。

### IJ-16 外层M更新仍不能遮蔽内部矛盾
- **字段/关系**：source_fingerprints、finding_ids、inspect运行摘要；协议§5.1/§8步骤8。
- **隔离构造**：三个独立变体：仅改source_fingerprints.normalized_payload_sha256但packet.bindings不变；仅改finding_ids一个ID但P不变；仅改inspect_binding.run_binding_sha256而R不变。各做R-M，E的原fact_binding保持BASE。
- **预期/定位**：步骤8定位materials.fact_snapshot.source_fingerprints.normalized_payload_sha256、materials.fact_snapshot.finding_ids、materials.fact_snapshot.inspect_binding.run_binding_sha256。
- **排除遮蔽**：P/PFP完全不变、M三处闭合；每例只改变该内部关系，证明不只校验外层摘要。

### IJ-17 文件字节SHA、对象FP不可交换
- **字段/关系**：files/expected_files；协议§5.3/§8步骤7。
- **隔离构造**：选择FILE(P原JSON)与PFP本就不同的基样，把facts.packet成员file_sha256改成PFP；R-M，E.expected_files保留原FILE。反向把packet_canonical_sha256改成FILE时R-M，E.expected_fact_binding保持原PFP。
- **预期/定位**：前例步骤7定位materials.files[i].file_sha256；后例步骤8定位materials.fact_snapshot.packet_canonical_sha256（与实际对象FP不符）。
- **排除遮蔽**：两值均完整64hex；使用确切原字节，不能用规范化重写JSON假装原FILE；不假定两个哈希必然不同。

### IJ-18 名单、封闭结构与严格整数
- **字段/关系**：files及相应expectations自有schema；协议§2/§5.3。
- **隔离构造**：分别缺/多role、重复relative/role、无序、越界relative、成员缺键；把byte_size从0改0.0或false；把packet.summary.total_findings从合法整数改float/bool。
- **预期/定位**：步骤2材料schema/名单规则Blocked；expectations对应变体步骤3；field精确到受影响成员/数字。对于8角色仍完整但路径或合法整数大小变化，R-M后步骤7与原expected_files比较拒绝。
- **排除遮蔽**：float不是删除键的替代例；名单结构例不声称走到摘要步骤，关系例先正确重算M。

### IJ-19 哈希完整匹配与普通ID正例
- **字段/关系**：所有SHA叶、普通ID；协议§2。
- **隔离构造**：逐个SHA族追加LF/CRLF/空格、改大写或截短；另把技术B/Q替换为保持前导零或64hex形状的原字符串并同步所有B/Q依赖后再算摘要。人类ID若需此形状，必须引用另行登记的对应人类字段，不现场派生事件/身份。
- **预期/定位**：SHA格式在所属步骤1/2/3/4定位原叶拒绝，不strip；普通ID形状合法且全部关系正确时未来VALIDATED。
- **排除遮蔽**：SHA反例仅改一个叶并先遇格式检查；ID正例不把ID当哈希，不使用现有Gate事件改标签为初判。

### IJ-20 正式契约与独立预期
- **字段/关系**：contract_binding；协议§5/§6。
- **隔离构造**：contract_effective=false/1或候选版本在材料步骤2拒绝；另只替换正式文件SHA为候选稿合法SHA，R-M，E.expected_contract保留正式值。
- **预期/定位**：常量/严格类型定位materials.contract_binding相应叶；合法SHA关系例步骤5定位materials.contract_binding.contract_file_sha256。
- **排除遮蔽**：关系例不能仍用旧M或非法SHA；本例不把核心比较成功称“已实读契约”。

### IJ-21 运行六项及版本
- **字段/关系**：runtime_version/run_binding；协议§5/§6。
- **隔离构造**：依次只改R中一个合法值或runtime_version；R-M，E.expected_run_binding/expected_runtime_version及原Gate投影保持原值。
- **预期/定位**：步骤5定位materials.run_binding的实际叶或materials.runtime_version；拒旧初判复用不同代码/规则/配置/输入。
- **排除遮蔽**：所有SHA仍完整、键集合正确；不一次同时改多个运行值，不以不存在版本文件代替内存关系例。

### IJ-22 两Gate不能被状态或错前序替代
- **字段/关系**：gate_links；协议§5.2/§8步骤8。
- **隔离构造**：分别把gate1/gate2替成APPROVE字符串、加effective bool、actor改模拟/decision改HOLD（步骤2）；关系例只改gate2.prior_gate1_fingerprint为另一合法摘要，R-M，原expected_gate_links保持BASE。
- **预期/定位**：结构/常量在步骤2对应字段；前序关系例步骤8定位materials.gate_links.gate2.prior_gate1_fingerprint。
- **排除遮蔽**：前序例不改变Gate文件SHA/其他绑定或M关系；拒绝先来自G2→G1实际投影关系，不靠effective真假假设。G1/G2守门材料FP不同但共同R相同为正向控制。

## 4. 时间、历史及未来性质验证

### IJ-23 原始时间合法精度与偏移
- **字段/关系**：decided_at_raw；协议§4。
- **隔离构造**：引用人类已登记的有效日期精度原串或带偏移秒精度原串；±14:00、有效闰日仅以满足规则的符号T_VALID_BOUNDARY描述，未来具体值须登记，不预填本轮人类时间。
- **预期/定位**：未来VALIDATED，原文逐字符相等，不产生normalized/current时间；日期精度不自动补时区。
- **排除遮蔽**：全部技术绑定不变，不引用正式契约头部不规则生效时间充当本协议正例。

### IJ-24 非法日期、datetime无时区和偏移
- **字段/关系**：submission.decided_at_raw；协议§4/§8步骤5。
- **隔离构造**：字符串形式反例包括不存在日期/非闰年闰日、时间分量溢出、含时间却无偏移、Z/小数秒、±14:01/超14小时、+0800、尾空白；每例只改该字段，均为技术反例而非真实决定时间。
- **预期/定位**：步骤5 Blocked submission.decided_at_raw，原因说明具体形式/日期/分量/偏移；非str例按IJ-07在步骤1。
- **排除遮蔽**：不要把允许的纯日期误称“无时区datetime”；不同时改actor或材料摘要。

### IJ-25 必需历史与声明范围
- **字段/关系**：prior_history；协议§7/§8步骤4、10。
- **隔离构造**：分别省略关键字/显式None/declared_complete=false或1/空白scope/非list records；关系例只改为另一非空scope并使自有历史FP正确，E.expected_history_scope保持原D。
- **预期/定位**：结构例步骤4精确字段Blocked；非空错scope步骤10定位prior_history.declared_scope。合法显式空索引正例按IJ-01。
- **排除遮蔽**：默认None允许进入函数体，不以Python签名TypeError为预期成功；错scope不写为空以遮蔽关系。

### IJ-26 历史索引不能自行替代核验源
- **字段/关系**：prior_history.records与expected_prior_history_fingerprint；协议§7。
- **隔离构造**：分别给坏成员/缺摘要/未知record键/重复event_id/无序；另在一个结构合法历史索引中改record_fingerprint而E历史FP保持原值。
- **预期/定位**：结构/名单步骤4；摘要关系步骤10定位expectations.expected_prior_history_fingerprint。纯核心不声称发现了未传入完整历史正文的缺陷。
- **排除遮蔽**：关系例索引字段仍完整合法；未来适配层应有单独“原完整历史record损坏不能生成核验索引”的恢复测试，本卡不实现/冒称已执行该测试。

### IJ-27 重复事件及同批第二初判
- **字段/关系**：首版不可覆盖；协议§7/§8步骤10。
- **隔离构造**：提供已由调用方核验的索引，分别event_id等于S事件、或另一event_id但batch_id等于B；H/E历史FP在构造前独立一致。
- **预期/定位**：前例Blocked submission.event_id；后例Blocked prior_history.records，即使当前材料未变也不接修订；没有覆盖/自动追加入口。
- **排除遮蔽**：索引内自身不重复/无序，先满足声明/历史FP，区别“名单重复”与“当前提交重复”。

### IJ-28 变化材料不得复用旧初判
- **字段/关系**：当前独立绑定与历史；协议§5—§7。
- **隔离构造**：把一份旧S对准变化后的当前材料但仍带旧请求MFP，其他当前M/E正确；另同步S新MFP却保留同B已有初判索引。
- **预期/定位**：前例步骤6拒submission.request_binding.materials_fingerprint；后例步骤10拒prior_history.records。正确新批次须新的守门/材料/人类提交，不设计“旧record迁移通过”。
- **排除遮蔽**：变更后M/E为独立当前基样；不能把旧审批标记换真或只改batch文字冒充已执行新链。

### IJ-29 其他批次合法历史的有界正例
- **字段/关系**：declared_scope与索引边界；协议§7。
- **隔离构造**：范围D内有另一批次已核验初判索引，其事件与S不同；该历史使用当时运行/契约，当前M/E保持当前正确版本，历史FP独立固定。
- **预期/定位**：未来VALIDATED；不把当前运行六项强套给一般历史，不宣称全局无隐藏历史。
- **排除遮蔽**：四字段只是已核验索引，不称完整record；其核验来源须未来适配层保证，不能拿随机摘要凑合法历史。

### IJ-30 自由文本不执行且不授权
- **字段/关系**：assessment/reason/note/request/declaration_note；协议§2/§3。
- **隔离构造**：引用人类明确输入的指令样式原文或提及D2的原文；结构来源/actor仍正确，技术绑定不变。
- **预期/定位**：未来作为数据原文返回，无执行/批准/AI/终判副作用；不是通过关键词证明独立思考。
- **排除遮蔽**：本轮只用H_TEXT符号，不创造实际人类意见；来源改成SYSTEM应按IJ-09拒绝而不是在本例豁免。

### IJ-31 确定性与规范字节严格性
- **字段/关系**：C/FP与输出；协议§2/§9。
- **隔离构造**：未来同输入调用两次；只调整dict键插入序再调用；另对比较候选仅把边界false改0或整数计数改0.0（输出候选审核方法设计，不是给核心合法新submission）。
- **预期/定位**：同值/键序不同C(record)及FP相同；类型替换C不同，未来证据审核必须拒绝；可选省略等值见IJ-04。
- **排除遮蔽**：不以Python==判定False/0或0/0.0；输出候选篡改测试须走未来实际审核，不写影子判定器。本卡不运行它。

### IJ-32 输入不变与无别名
- **字段/关系**：submission/materials/expectations/prior_history及返回；协议§1/§9。
- **隔离构造**：未来在真实核心进入前记录同一消费引用指纹，返回后/API收尾复测；改返回的深层actor/备注/绑定，观察原输入不变。
- **预期/定位**：未来输入三时点一致，返回修改不影响输入；验证使用真实保留引用而非两次事后deepcopy。
- **排除遮蔽**：不重新调用核心制造对照结果，不预先把返回与输入共享对象替换掉。仅列未来验证方法，当前未执行。

### IJ-33 Blocked与意外Error原因链
- **字段/关系**：拟定异常；协议§1/§8。
- **隔离构造**：正常schema负例验证Blocked field/reason/reasons；未来在真实内部确定性序列化接缝受控注入运行异常，保留真正cause并明确测试注入。
- **预期/定位**：Blocked不被包装成成功/Error；意外错误HumanInitialJudgmentError(stage=internal)保留__cause__/traceback；无record。
- **排除遮蔽**：缺必需键须先Block，不能把renderer/后消费KeyError当正向Error控制。本卡未导入拟定核心、未捕获实际异常。

### IJ-34 纯内存与保存/AI边界
- **字段/关系**：协议§1/§9—§11。
- **隔离构造**：未来在open/os.open/socket/subprocess/时间随机环境读入口安装真实守卫，导入及合法调用；核对输出八false、没有RECORDED/AI_READY、没有存储副作用；另给旧模拟submission按IJ-09拒绝。
- **预期/定位**：未来守卫若无命中且合法调用成功才可报告；本轮执行计数null+原因。VALIDATED不改变任何现有批次状态，未保存就不存在已保存初判。
- **排除遮蔽**：守卫必须装真实入口/模块，不仅搜禁用字符串；不把纯核心成功当未来独占写/恢复已验证，不开放AI或终判。

## 5. 覆盖、未执行与后续缺口

34个唯一连续编号按问题族合并，**不是34项函数PASS或变体执行数**。IJ-01—10覆盖人类输入/D3/零条/来源；IJ-11—22覆盖可选字段/独立绑定/类型/两类SHA/Gate；IJ-23—29覆盖时间/声明历史/不可覆盖；IJ-30—34为自由文本、确定性、无别名、异常及未来守卫设计。

protocol_cases_executed=null，business_core_calls=null，guard_hits=null，persistence_checks=null；原因均为TASK-034仅文档，拟定函数未实现且禁止业务执行。当前静态核验只报告文档结构/字段/引用/链接/一致性，不把其PASS叫业务验收。

未来纯核心实施前需另卡和另行登记合成人类初判字段；本卡不生成/签署夹具，不把Gate决定或旧SIMULATED记录转为人类初判。协议/案例/技术验收不批准批次、不认证身份，不选择模型/框架/缺陷等级，不定义AI许可或终判保存。实施端交文档后停止；真实批准null、宿主0008、真实初判未保存、next/AI=false。
