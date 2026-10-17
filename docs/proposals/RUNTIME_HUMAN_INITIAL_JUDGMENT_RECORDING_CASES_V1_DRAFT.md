# 运行层初判保存/恢复符号案例 V1（尚未执行）

标识：`RUNTIME_INITIAL_JUDGMENT_RECORDING_CASES_NOT_EXECUTED`。仅书面隔离案例，不是已运行测试/人类提交/批准文件。与同目录 RECORDING_PROTOCOL_V1_DRAFT 对照；状态/键集合由下方机器块显式引用，不自造省略的成功payload。

## 符号及共同前提

H_EVENT/H_ACTOR/H_DECLARATION/H_TIME/H_ASSESSMENT/H_REASON仅引用未来人类明确提供的原文；不是默认值，不把符号名填进submission，不预填判断或时间。若描述暂不能判断，前提是人类H_ASSESSMENT表达该意思且H_REASON非空，执行端不提供替代原文。fixture仅引用TASK-034 event1和TASK-036-R1 event2登记文件，其SHA见协议；本卡不消费这些字段运行业务。

TECH_NAMESPACE/TECH_LEAF/TECH_REQUEST/TECH_RUNTIME均为TECHNICAL_SYMBOL，不是实际路径/event/批准。P0/H0/E0为持锁后真实保存前历史及完整核验/独立名单；S为本次真实store.save十一键；H1/E1为保存后独立新增自身的核验/名单；Hc为恢复时当前完整域。M为九键材料正文FP，F为确切原文件FILE；两者不替换。n=保存前合法叶数，m=恢复时合法当前叶数（包括目标）。

正常save：S1—S9全部；直接prepare1/store.save1/后H1，嵌套总history2、初判verify2n+1/core2n+2。正常verify：V1—V8全部；直接history/Gate1/Gate2/facts各1，公开prepare0/save0，初判verify/core各m。两者Gate/fact既有嵌套图相同，算法/直接初判core均0。提前失败只计算已进入代码帧，不套正常公式。

每例 `prior_satisfied` 保证错误不被更早无关条件遮蔽。`basis`说明独立预期在何时从哪些真实缓冲固定；`change`是唯一触发或明确关联变更；`expected`给字段/阶段及结果；`writes`区分只读与保存保留；`calls`是设计预期而非实测数字。实际动态调用、并发、句柄和恢复全部null，未来实施另卡。

下方为完整44例单一权威索引；JSON可解析，所有文本均符号关系/条件描述，没有可提交的人类值。case中的常量1/0只是未来调用图设计；不得统计成执行次数。设计版本TASK-039-recording-design-1.1只增加摘要角色说明/RC-44并澄清RC-02字段路径，原业务形状/状态/顺序/边界不变。

<!-- TASK039_CASES_BEGIN -->
```json
{
  "label": "DESIGN_SYMBOLS_NOT_EXECUTED",
  "design_version": "TASK-039-recording-design-1.1",
  "human_symbols": ["H_EVENT", "H_ACTOR", "H_DECLARATION", "H_TIME", "H_ASSESSMENT", "H_REASON"],
  "schema_uses": ["success", "identity", "started", "source_binding", "registry_binding", "initial_judgment_history", "contract_effective_record", "pre_history_binding", "context", "receipt", "file_descriptor", "envelope_binding", "lock", "failure", "chain_item", "boundaries", "snapshot_files", "envelope_files", "submission_required", "submission_optional", "history_expectations", "prior_history", "history_index", "store_return", "history_return"],
  "constants": {"stage_version":"TASK-039-runtime-human-initial-judgment-1.0","save_status":"RT_HUMAN_INITIAL_JUDGMENT_RECORDED","verify_status":"RT_HUMAN_INITIAL_JUDGMENT_VERIFIED","scope":"RUNTIME_CURRENT_MATERIALS_AND_DECLARED_HISTORY_ONLY"},
  "dynamic_execution": {"count":null,"reason":"文档范围；未来保存/恢复尚未实施，未运行任何符号案例"},
  "digest_role_case": {"case_id":"RC-44","role_contract":"EXPLICIT_FIELD_SOURCE_NOT_SUFFIX","fields":["source_binding.registry_binding.run_binding_sha256","context.prepared_request.request_sha256","receipt.context_file_sha256"]},
  "cases": [
    {"id":"RC-01","family":"正常首版","prior_satisfied":"S1—S8正常，n=0；人类六符号有已登记原文","basis":"S3持锁来源及E0真实空域；S6本次S缓冲；S7独立E1","change":"无变更","expected":"S9返回完整12键RECORDED，九权限false；核心persisted仍false","writes":"六快照+三封装；仅成功释放自锁","calls":"prepare1，store.save1，history2，初判verify1/core2；算法0"},
    {"id":"RC-02","family":"零线索","prior_satisfied":"RC-01来源关系成立，materials.fact_snapshot.finding_ids与packet.findings均为空列表","basis":"当前真实facts而非空命中推断","change":"人类仍明确提供完整六符号及技术绑定；未生成无问题","expected":"完整提交可保存；缺assessment/reason交核心Blocked store.submission对应字段","writes":"合法成功同RC-01；非法仅保存已出现诊断/锁","calls":"合法save公式；非法pre核验+n个verify，store.save/core构建各1，postH0"},
    {"id":"RC-03","family":"暂不能判断","prior_satisfied":"S3真实材料正常；H_ASSESSMENT由人类表达暂不能判断且H_REASON非空","basis":"独立M不来自assessment意义","change":"只改变人类明确原文符号所指，不预设实际值","expected":"真实核心接受原文并完整保存；不变成HOLD/AI许可","writes":"正常save","calls":"save公式2*n+2核心，无额外核心"},
    {"id":"RC-04","family":"可选逐条备注及取证需求","prior_satisfied":"S3全部通过，finding_id来自真实packet","basis":"已固定finding_ids；两列表保持人类原序","change":"省略/显式空列表等值；合法note/request按原文，批次需求ID=null","expected":"可保存；核心输出副本补空列表不回写原submission","writes":"原收到对象快照保留","calls":"save公式"},
    {"id":"RC-05","family":"提交封闭schema","prior_satisfied":"S1—S4正常，M/域/时间其他字段有效","basis":"冻结TASK034九必需/两可选顺序","change":"四隔离变体：缺必需键、actor=null、reason错型、未知字段","expected":"真实核心精确Blocked store.submission对应字段，未知键UTF8序；无原生KeyError","writes":"不建目标叶；已有started/失败/锁保留","calls":"preH+nverify；store.save1/core构建1；postH0"},
    {"id":"RC-06","family":"非法原始时间","prior_satisfied":"提交schema及其他值先满足","basis":"冻结真实日历和两种格式口径","change":"仅H_TIME不满足协议；不补时区或秒","expected":"Blocked store.submission.decided_at_raw；原文不改","writes":"不建目标叶，保留已出现现场","calls":"同RC-05"},
    {"id":"RC-07","family":"陈旧M","prior_satisfied":"S3本次真实M固定，提交其余合法","basis":"M来自当前开始缓冲，不刷新","change":"仅提交request_binding.materials_fingerprint为旧有效64hex","expected":"核心绑定检查Blocked store.submission.request_binding.materials_fingerprint","writes":"不建目标叶，不改预期","calls":"store.save1/core构建1，postH0"},
    {"id":"RC-08","family":"严格类型与规范相等","prior_satisfied":"合法完整候选先独立形成，所有直接摘要同步使更早SHA合法","basis":"同缓冲独立schema+canonical预期","change":"两隔离变体：权限false→整数0；byte_size整数→同值float","expected":"对应result.boundaries或file_descriptor.byte_size Blocked；不能用Python相等通过","writes":"保存端失败保留；恢复端不写","calls":"不重调用核心替换坏候选"},
    {"id":"RC-09","family":"字典反序首报稳定","prior_satisfied":"同一步有两个相同矛盾，其他前置均正常","basis":"固定schema顺序/列表原序/未知键UTF8序","change":"仅反转字典插入顺序，不改变键值","expected":"两构造首报同一字段；纯键序不同的合法对象规范等值通过","writes":"非法不成功；合法正常","calls":"每个调用独立计，不声称本卡运行"},
    {"id":"RC-10","family":"Gate或事实前提失败","prior_satisfied":"S1—S2及历史schema正常；每次隔离一个前提","basis":"真实Gate1/Gate2/fact完整返回和开始缓冲","change":"Gate1非effective、Gate2非APPROVE、fact有效failure三变体","expected":"当前层对应gate1.effective/gate2关系/facts.failure拒绝；不得靠提交掩盖","writes":"历史目标不创建；已有自锁及封装现场保留","calls":"store.save0；按已到只读节点实际计"},
    {"id":"RC-11","family":"保存前材料漂移","prior_satisfied":"S3已成功；S5复确认前所有绑定一致","basis":"S3开始源原字节","change":"真实reader返回后只给一个本轮源文件加LF","expected":"S5指向该来源文件Blocked，store.save/core构建增量0","writes":"不建目标；坏源及失败/锁保留","calls":"仅S3只读调用，S5无业务重算"},
    {"id":"RC-12","family":"错声明域","prior_satisfied":"路径语法合法，候选域确实存在且空","basis":"当前已Gate1绑定registry域","change":"只将expected_namespace_relative换另一个合法域","expected":"S1 history_expectations.expected_namespace_relative Blocked；不允许空域逃逸","writes":"无本次锁/叶/封装","calls":"业务0，只有参数/登记字节读取"},
    {"id":"RC-13","family":"错scope","prior_satisfied":"域和名单形状合法","basis":"registry.initial_judgment_history.declared_scope","change":"仅expected_declared_scope不同","expected":"S1 history_expectations.expected_declared_scope Blocked","writes":"无本次输出","calls":"业务0"},
    {"id":"RC-14","family":"不完整名单","prior_satisfied":"域/scope/schema合法；实际成员不变","basis":"caller调用前固定E0，禁止重采","change":"E0遗漏一叶或manifest FILE错","expected":"S3 prepare的history集合/manifest字段Blocked；不默认空历史","writes":"已取自锁保留；不建目标","calls":"prepare1；更早捕获拒绝时H公开/store/core0，按实际顺序记录"},
    {"id":"RC-15","family":"同event重复","prior_satisfied":"H0合法且旧batch不同；人类H_EVENT恰与旧event相同，其他提交合法","basis":"完整H0索引，不从它预填H_EVENT","change":"仅事件关系重复","expected":"store.submission.event_id Blocked，先前材料/时间均通过","writes":"不建目标叶","calls":"preH+nverify；store.save/core构建1，postH0"},
    {"id":"RC-16","family":"同batch重复首版","prior_satisfied":"H0全域核验成功，旧记录为本batch","basis":"本次真实H0而非存在bool","change":"当前batch已出现，不关event字符串","expected":"S3 prepare Blocked prior_history.records；不覆盖/选最新","writes":"不建目标；自锁保留","calls":"prepare1、preH1/nverify；store.save0"},
    {"id":"RC-17","family":"同域两个并发保存","prior_satisfied":"两个调用锁前都拿过同一E0；其他来源有效","basis":"锁内重新核验，不复用锁前成功","change":"A取得真实独占句柄，B随后CREATE_NEW","expected":"B在lock拒绝；A成功后B旧E0不能刷新凑成功","writes":"B不写/不清A；A仅可释放自己的成功锁","calls":"B store.save0；A正常公式"},
    {"id":"RC-18","family":"不同运行共用域","prior_satisfied":"TECH_RUNTIME_A/B合法且registry同namespace","basis":"锁名由namespace唯一确定，不由runtime或人类event决定","change":"A持锁时B以另一运行调用","expected":"B同一lock拒绝；不同运行不能各建私锁绕过","writes":"B无本次输出","calls":"B业务0"},
    {"id":"RC-19","family":"既有坏锁/半锁","prior_satisfied":"S1参数正确，锁路径已有现场","basis":"原路径存在事实","change":"普通陌生锁/目录/0B/坏JSON四隔离型","expected":"lock Blocked，不认过期或接管","writes":"旧锁逐字节不动","calls":"业务0"},
    {"id":"RC-20","family":"外来同内容替代锁","prior_satisfied":"原锁已取得且字节正常，S9前其他源不变","basis":"本次句柄/父目录/file ID，不仅文本","change":"隔离控制呈现同内容但不同文件身份","expected":"lock Blocked且不删除替代件；不把控制当物理成功替换","writes":"主/次错误和实际剩余现场保留","calls":"不加核心重试"},
    {"id":"RC-21","family":"原路径reparse/alias/..","prior_satisfied":"其余参数正常，原始链含具名链接段","basis":"规范化前的逐级原链","change":"alias指向另一目录或别名后带..；另有unsafe字面段","expected":"record_relative或相应原路径字段Blocked，在消段前拒绝","writes":"不建锁/目标；物理junction未执行不能当PASS","calls":"业务0"},
    {"id":"RC-22","family":"真实独占半写","prior_satisfied":"S5真实writer已打开独占句柄，先前来源/核心正常","basis":"该次writer原缓冲/真实句柄","change":"只包装句柄写半份后OSError，不替换整个writer","expected":"原StoreError stage保持映射，完整主cause；运行层不成功","writes":"六叶可能部分文件+store failure；锁/封装失败保留","calls":"store.save/core构建1；postH0"},
    {"id":"RC-23","family":"有效/坏failure优先","prior_satisfied":"V1目标/封装其余可缺，避免context早读遮蔽","basis":"failure同缓冲类型/常量/schema","change":"有效BLOCKED/ERROR或非法顶层/缺键/版本各隔离型","expected":"有效按原field/stage；坏failure精确Blocked字段；不进入renderer或原生异常","writes":"verify完全只读","calls":"当前域/core0，V1已拒绝"},
    {"id":"RC-24","family":"store完成但context半写","prior_satisfied":"S7全H1成功，六快照与S精确闭合","basis":"本次context writer缓冲","change":"context真实独占句柄半写OSError","expected":"Error write.context；独立store成功不等运行完成","writes":"六快照+半context+诊断/锁保留，不删叶","calls":"已完成save公式；不重复verify目标"},
    {"id":"RC-25","family":"receipt写后sentinel","prior_satisfied":"S8真实receipt完整写/读回后返回原值","basis":"本次receipt writer读回，不用候选新期望","change":"明确测试sentinel在真实writer返回后抛出","expected":"Error write.receipt，传播和诊断cause含sentinel","writes":"完整receipt也保留为失败现场，不回填","calls":"不重试核心"},
    {"id":"RC-26","family":"诊断故障不盖主异常","prior_satisfied":"已经有一个确定StoreError或本层主错误","basis":"原主class/stage/field/reason/reasons/cause","change":"冻结store诊断技术时钟抛OSError；或运行failure写入再失败","expected":"主异常顶部/stage不变，secondary分列；不是裸OSError","writes":"现存坏诊断保留，不重写；运行failure不新增时间字段","calls":"诊断不加核心"},
    {"id":"RC-27","family":"保存后只加自身","prior_satisfied":"S6六件与S已闭合；旧n叶不变","basis":"E1只由E0+本次S已核验manifest FILE构造","change":"合法目标加入使H1不同于H0","expected":"postH真实成功；P0/expectations仍旧快照；完整返回RECORDED","writes":"不回写prior_history/expectations","calls":"postH1、n+1 verify/core；总core2*n+2"},
    {"id":"RC-28","family":"未声明新增叶","prior_satisfied":"E1已独立固定，S7调用前后目标正常","basis":"E1固定名单而非目录新枚举","change":"外来另加一合法叶","expected":"history.expected_entries或末端域集合拒绝，不接受新candidate","writes":"保留新增现场，不能删叶凑成功","calls":"按已到阶段；不重采后再跑H"},
    {"id":"RC-29","family":"最后必要消费后变化","prior_satisfied":"S8或V7返回已构造，其余来源正确","basis":"本次开始/本次writer固定缓冲","change":"最后真实consumer返回后只改源/目标快照/封装一LF，或加unknown/failure/成员","expected":"S9/V8本次指向确切目标拒绝，不等下一调用","writes":"保存失败保留；verify不写诊断","calls":"确认只读原始字节，不再加H/core刷新"},
    {"id":"RC-30","family":"精确恢复与失败现场区别","prior_satisfied":"RC-29已检出，原件和坏字节具名保全","basis":"同一轮单文件原缓冲，不从摘要重建","change":"只恢复该本轮原文件；不清理锁/failure/新增叶","expected":"无sticky失败的纯只读探针可恢复；真实保存失败锁/failure存在则仍拒绝","writes":"不递归删移；不冒称回滚成功","calls":"若后续调用另记，旧调用结果不回写"},
    {"id":"RC-31","family":"恢复自身","prior_satisfied":"V1—V3目标六件及完整当前Hc真实通过，m=1","basis":"存储P0、独立当前Gate/fact来源，不是公开prepare","change":"当前域含自身是恢复对象","expected":"V8完整12键VERIFIED；公共prepare仍会拒绝同batch","writes":"全程只读","calls":"H1，初判verify/core1；公开prepare/save0；Gate/fact正常图"},
    {"id":"RC-32","family":"后来不同batch合法记录","prior_satisfied":"V1—V5正常，旧叶/目标完全不变","basis":"当前完整Hc名单独立固定；旧P0/H0/H1保持","change":"后来增加其他batch合法叶及合法引用","expected":"当前Hc可比H1大，旧引用四字段全匹配则恢复成功","writes":"不改旧P0/receipt.post_history_fingerprint","calls":"初判verify/core=m，不另verify目标"},
    {"id":"RC-33","family":"旧引用缺失","prior_satisfied":"目标旧P0声明该event，所有外层摘要合法","basis":"旧P0原四字段+当前Hc真实索引","change":"仅引用目标不在当前完整域，caller也如实固定当前名单","expected":"history references.event_id拒绝；不隐藏自身或默认完整","writes":"只读；不伪造重建缺失叶","calls":"H按实际现存叶核验后引用检查，不刷新旧历史"},
    {"id":"RC-34","family":"旧引用FP矛盾","prior_satisfied":"当前叶各自store/core自洽，形状/FILE已同步以排除早错","basis":"旧索引四字段与真实当前索引","change":"已声明引用record_fingerprint或binding_fingerprint不匹配","expected":"history对应引用FP拒绝；不把摘要同步当正确业务绑定","writes":"只读保留坏现场","calls":"先逐叶真实verify/core，再关系拒绝"},
    {"id":"RC-35","family":"当前域第二份同batch","prior_satisfied":"两个叶各自合法且不同event","basis":"Hc完整名单，不能排除自身","change":"同batch两个索引","expected":"history record.binding.batch_id拒绝，不选最新","writes":"只读，不删第二叶","calls":"按实际核验前缀计"},
    {"id":"RC-36","family":"当前域重复event","prior_satisfied":"两个叶各自合法且不同batch","basis":"Hc完整索引","change":"两个记录同event","expected":"history record.human_initial_judgment.event_id拒绝","writes":"只读","calls":"不进入新的save"},
    {"id":"RC-37","family":"旧请求不可重存覆盖","prior_satisfied":"已有成功目标及运行封装","basis":"S1存在事实及S3当前历史","change":"拿旧request/旧M再存同叶或新叶","expected":"同叶record_relative/封装存在拒绝；新叶同batch仍拒绝；无caller request参数","writes":"旧文件全部不变","calls":"早拒绝0或S3只读，store.save0"},
    {"id":"RC-38","family":"当前材料或代码版本漂移","prior_satisfied":"旧目标及历史完整，自身校验成立","basis":"V4真实当前来源固定九键正文/八FILE/六运行","change":"只改数据/规则/代码/配置/范围/契约/事实之一，外层摘要同步","expected":"当前Gate绑定或V5 materials对应关系拒绝，不迁移旧凭证","writes":"只读","calls":"不重算SQL/事实，不更新旧expectations"},
    {"id":"RC-39","family":"恢复禁止副作用","prior_satisfied":"正常m叶和当前材料可恢复","basis":"真实入口代码对象与实际open/clock/network/subprocess守卫","change":"先证明守卫会拒绝，再在V1—V8运行","expected":"成功恢复，无save/算法/时钟/随机/网络/子进程和失败写入","writes":"0为未来实测目标，本卡不是实测0","calls":"verify公式；额外禁止项本卡null"},
    {"id":"RC-40","family":"完整返回/内部审核失败","prior_satisfied":"真实源、输出缓冲和独立完整返回预期固定","basis":"写前独立观察而非候选回采","change":"候选合法形状替换内容，或真实审核返回FAIL","expected":"完整canonical差异Blocked result；内部FAIL Error audit.result并支配外层","writes":"坏候选保留，未回填期望","calls":"不重调用核心凑成功"},
    {"id":"RC-41","family":"台账自身被替换","prior_satisfied":"未来测试正式载荷一次写定，真实末次审核前","basis":"台账本次writer缓冲","change":"磁盘仅替换台账内容，payload不变","expected":"真实main非零、磁盘FAIL、failures非空，不依据注入标志","writes":"坏台账保留不重建","calls":"重放观察不算新业务调用"},
    {"id":"RC-42","family":"审核后最后字节漂移","prior_satisfied":"内容/台账审核真实通过且成功输出预先构造","basis":"本次审核同缓冲和writer期望","change":"最后必要读返回后checks/ledger只加LF","expected":"末次原字节检出并支配最外层；确认后不再读候选构造PASS","writes":"坏字节保留，不清理失败","calls":"未来新进程0/1控制；本卡动态null"},
    {"id":"RC-43","family":"技术释放失败","prior_satisfied":"S9所有材料/输出确认成功，句柄仍持有","basis":"最初句柄/file ID/锁缓冲及当前同一文件","change":"按句柄删除/close/解除确认真实失败或遇替代锁","expected":"Error release.lock或Blocked lock，绝不返回RECORDED；不退化路径盲删","writes":"保留实际剩余锁和输出，主/次错误可见，无回滚承诺","calls":"无新core/算法/重试"},
    {"id":"RC-44","family":"64hex形状正确但摘要角色错","prior_satisfied":"三变体各自隔离；正常来源/形状/名单/材料/先前关系已成立；不篡改真实登记或旧请求制造更早Gate错误","basis":"S3同缓冲固定registry.run_binding及prepared_request.request的对象FP和包含文件FILE；S8本次context writer固定FILE；预期不刷新","change":"变体A仅候选source_binding.registry_binding.run_binding_sha256以登记文件FILE替FP；B仅context.prepared_request.request_sha256以包含文件FILE替FP；C仅receipt.context_file_sha256以context对象FP替writer FILE；三值仍完整64hex","expected":"A在S4来源关系或V3封装关系Blocked source_binding.registry_binding.run_binding_sha256；B在S8/V3完整请求关系Blocked context.prepared_request.request_sha256；C在S8/V3文件绑定关系Blocked receipt.context_file_sha256；不能以格式检查代替角色检查","writes":"仅纯内存角色表控制在本卡执行，不改落盘候选文档；未来保存失败保留已出现现场，verify只读","calls":"本卡仅静态审核真实非零控制，不运行业务；未来只计已到阶段，不重新采预期或重调核心凑成功"}
  ]
}
```
<!-- TASK039_CASES_END -->

## 实施时的证据要求（本轮未执行）

每个未来动态例先证明正常对照、再在真实消费后只变指定字段/字节，保留原返回和命中次数；真实半写仅包装真实独占句柄。协议型错与OSError映射分列，不能把改参数前的错误叫晚变更、不能用假writer声称生产except分支运行。实际完整观察、原引用三时点、父关系、最终磁盘与独立预期、文件台账及末次字节都必须支配最终结论。

并发、Windows持有句柄删除、真实物理junction、部分成功、保存与恢复、CLI及AI/终判均未运行；本卡静态核对只能证明文本/键集合/公式/来源相互一致。未来代码改变后须另卡新身份链，旧失败/锁/记录不自动清理。当前状态不因符号设计而变化。
