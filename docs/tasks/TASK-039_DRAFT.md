# TASK-039：运行层初判保存与只读恢复协议、符号案例

分类C，Architect规定设计边界，执行端交付文档和有限静态核对，Architect独立验收。本卡以前置 `data/reviews/task038_gpt_20261017_003401/review_result.json` 发布ACCEPTED为生效条件。只做协议，不实施或运行业务入口，不保存人类初判，不接AI/终判，不启动下一实施卡或改看板。

## 1. 起点和交付范围

先读REVIEW_TASK_038、同根review_result与新接受快照（SHA/项数从结果实读），TASK-034协议§5—10、TASK-038及其人类链数量授权补充，再有限阅读当前适配器和冻结初判三件。禁止执行旧run/main、全套历史测试或创建新业务链。

当前适配器 `scripts/runtime_gate1.py` 290568 B / SHA `ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a`，TASK-038-runtime-gate1-1.0；十七业务API、新registry十四键/代码十七项/Gate1材料三十八项。本卡全冻结。

冻结初判core 28927 B / `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`；store 25787 B / `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`；history 15064 B / `7276ddb704d27cec031ca3c2af4122a3c2c890d613bd4cfa90e6454d72000b22`。正式契约/生效登记、协议/案例、准备器、所有计算/展示核心/P1/store、SQL/schema/config、宿主0008、旧测试/指南/记录均冻结。其余身份从新接受基线读，不复制历史全部SHA。

仅新增：

- `docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md`。
- `docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_CASES_V1_DRAFT.md`。
- `tests/check_runtime_initial_judgment_recording_protocol.py`，有限静态核对，不导入或调用业务组件。
- `docs/EXEC_REPORT_039.md`。
- `data/runtime_initial_judgment_recording_protocol_checks/task039_<轮次>/`，只保存文本/静态核对/交付与保护证据，不建运行、Gate、SQLite或历史记录根。

所有既有文件零修改。新增逐确切路径登记，根不是目录前缀豁免。Windows/PowerShell、`.venv\Scripts\python.exe -B`；不装依赖、不造通用框架，不递归删除/移动，不清理任何锁/探针/失败现场。需要改上述范围、正式契约或业务政策时停止该级处理并报告Architect。

## 2. 本卡要解决的实际接口问题

TASK-038已能从当前Gate1/Gate2/fact/history真实核验准备材料，尚不能保存运行层决定。TASK-036独立store保存的是六文件快照，未连接运行层；TASK-037会把声明域直接子目录当记录叶，叶必须恰六件且无failure。TASK-038的prepare又会在域中已有本批记录时拒绝首版准备。

因此不能直接把运行context/receipt塞进历史叶，也不能让恢复入口直接再调用prepare而误拒绝自身记录，更不能把旧请求或旧历史FP当当前许可。协议须先固定跨域锁、两处输出、保存前与保存后历史含义、恢复时当前材料和旧历史快照的区别，以及半成功保留语义。不得通过改冻结history/store放宽六件约束、公开skip参数或修改旧凭证解决。

## 3. 拟定唯一两个未来入口（本卡不实现）

```python
save_runtime_initial_judgment(
    batch_dir, runtime_dir, request_id, submission, record_relative, *,
    scope_dir, event_relative, database_path, gate2_event_relative,
    history_expectations
)
verify_runtime_initial_judgment(
    batch_dir, runtime_dir, *, scope_dir, event_relative, database_path,
    gate2_event_relative, record_relative, history_expectations
)
```

明确标“拟定，尚未实现”；不能写成可运行命令或现有API。协议正文把各参数的严格类型/来源/相对路径/固定顺序、成功完整键集合、固定状态/版本/说明、异常映射、FILE/FP角色与末次确认时点静态定稿，并给机器可读键集合块供静态核对；不得只列待办。

submission沿冻结TASK-034九必需/两可选键。事件、身份声明、决定时间、assessment/reason全由人类明确原文提供；request_id为技术请求原串，不能转成event。save不接受外部完整request作为可信来源，不从submission构造独立预期，不预填判断/原因。零线索仍需人类完整提交；允许有原因的暂不能判断。日期不补时间/时区，不比较人类时间与Gate/系统时间推断独立性。

record_relative为调用方显式技术路径，须为已绑定namespace的安全直接记录叶，原路径链先于规范化、无链接/reparse；不从event_id/actor_id拼目录。save目标必须从未存在，verify目标必须已存在。scope/namespace必须来自当前已Gate1绑定的registry，不由参数换到其他空域。

history_expectations仍TASK-037四键、调用前独立固定。save为保存前完整现存名单；verify为当前完整现存名单且必须包含目标叶，双方不能默认空名单。当前范围完整性仅声明域现存成员及已声明引用，不证明无引用删失/域外/全时间历史。

## 4. 两处文件与有界独占设计

未来历史记录叶保持冻结store六文件原样，不新增运行字段、不改纯核心record.boundaries.persisted或record_status。运行封装放登记同级 `<登记叶名>.initial/`；协议自行定稿最少必要的started/context/receipt及失败诊断键集合，不引入数据库/多版本目录/通用恢复框架。

运行封装至少绑定：本批/运行/目标叶/声明域、实际Gate事件/事实四件/正式契约/六项run_binding、接收的人类submission快照、保存前完整请求材料与独立预期/已核验旧历史、冻结store完整返回与六FILE/FP、保存后完整域核验。说明完整对象如何与本次开始缓冲、store已核验writer读回及自己的writer缓冲闭合；避免摘要自指，FILE与对象FP不互换。不要把八直接角色名单冒称全依赖备份。

声明域共用一把技术锁，放namespace之外（建议固定同级 `<namespace名>.initial_judgment.lock`），不能破坏history直接叶枚举。保存取得真实独占创建/句柄并保持到末次确认；持锁后重核当前Gate/材料/完整历史，防止两个遵守本适配器锁的保存同时看见空域。不同运行但共用同域也必须串行。已有锁（含坏型/半写/陌生者）拒绝，不能接管、重写或清理。

只允许对本次成功、确证仍由本次持有的技术锁作必要释放；逐项规定身份/字节/句柄核对，禁止删除外来/旧锁或失败现场。失败保留本次锁及具名现场，不自动重试/回滚/补签；后续恢复或人工处置另卡。verify严格只读；锁存在即拒绝，不生成技术时间、随机/owner或写失败。

锁只协调遵守接口的本地写入；外部绕过锁的篡改仍靠原字节/目录集合末次确认发现，不能据此声称强认证、不可删历史或全局事务。不得夸大两个输出根的原子性。

## 5. 保存的冻结核心调用与历史时点

持锁后真实核验当前Gate1有效批准、Gate2完整APPROVE、fact inspect与完整保存前history；材料/独立预期在接收内容校验前从真实来源固定，必须与submission已明确给出的request_binding闭合。沿当前TASK-038事实/依赖检查和模板说明，不重跑SQL、标准化、装载、复算、事实build或旧模拟初判。

只真实调用冻结store.save一次；初判核心由store内部恰一次，不先直呼核心再保存重复调用。人类内容缺/错/重复event/同批首版拒绝由冻结核心/当前域关系准确处理；不修改其首报顺序。原始输入/完整实际返回及引用三时点要有可观察定义。

store成功后，新增目标叶使当前history与保存前不同。保存前prior_history是人类决定绑定的旧历史快照，必须原样保存；**不能把新增自身后的索引写回旧prior_history或expectations**。保存后独立名单只能由原保存前名单加本次实际store已核验目标manifest FILE形成，不能重枚举并默许并发新增。真实调用history.inspect进行完整保存后核验；它内部对全部n+1叶真实store.verify/core，不重复直呼当前叶verify。明确每个直接/嵌套调用数、父关系及允许的额外只读Gate检查，不把它们混成一次核心。

在构造成功封装/返回后，对全部开始依赖、提交对象、本次六快照、封装writer缓冲、原路径/集合/failure和锁身份作末次确认；只认可本次预先规定的新增目标叶，不刷新独立预期迎合其他变化。成功至多表示这个合成运行的完整技术保存状态，任何next/AI/身份/业务真实性/结论/终判许可均false；纯核心记录的原false边界保持。

## 6. 恢复如何核验自身及后来历史

verify先拒绝运行封装/历史叶failure、锁和不完整布局，再固定本次原字节。真实核验当前完整域（包含目标叶）；从实际完整history/store返回绑定当前叶六文件、四快照和完整两键结果，不能只看索引或路径存在，也不再次直呼store.verify重复当前叶核心。

本批只能有一份已核验记录；不能略过自身叶而隐藏域中第二份或重复事件。先完整域核验通过，再将目标快照与运行封装、当前真实Gate/fact/registry/契约及所有依赖闭合。当前同批记录是恢复对象，不是授权新保存。

**恢复不能直接调用会拒绝自身的公开prepare，也不能把“当前域减自身”当保存时旧历史。** 提案规定一个有限私有共享材料核验分支，只在目标完整快照已核验、固定目标及来源之后用于恢复；不暴露skip/ignore/force或caller-supplied true，不降低公开prepare的同批拒绝规则，不重写冻结算法。

目标存储的prior_history/其FP是保存时旧快照。当前域可以后来增加其他批次合法记录；当前完整域须验证所有现存叶及已声明引用，旧快照中的每个引用四字段仍须在当前实际完整索引精确找到。后来无矛盾的新记录不回写旧快照、不抹掉旧时点，也不据此宣称保存时全球历史完整。当前材料九键正文/八角色/Gate/契约/运行身份则必须仍精确匹配目标绑定；数据、代码、规则、配置、范围、契约或事实漂移拒绝，不迁移旧凭证。

协议分别给出历史增加允许/旧引用丢失或变更拒绝/当前材料漂移拒绝的符号案例，避免用更新外层摘要掩盖晚层矛盾。所有成功完整返回在最后必要消费之前构建；末次比较本次开始/本次writer缓冲后直接return，不写失败或重采预期。

## 7. 部分成功、分类和最小符号案例

在固定协议中明确：store已写完而封装receipt/读回/末次确认失败时，六快照可能存在，但运行层**不得返回成功**；保留原件、主异常、准确stage/field/reason/reasons/cause及次错误，不删除成功叶或重写为新版本，不把独立store成功冒称运行层保存完成。该域随后存在同批记录/失败/锁会拒绝自动重试，未来人工处置另卡。两根没有跨文件事务，不承诺自动恢复到“从未发生”。

受控候选或内部审计FAIL必须支配最外层返回/未来CLI/summary/failures；实际独占句柄半写、有效/坏failure优先、最后消费后的变更、异常诊断故障不盖主异常均要有可复现符号时序。只画符号，不运行这些入口。

案例至少覆盖以下互异问题族，标明前提、独立预期来源/固定时点、先前步骤已满足、触发字段/阶段、是否可写及预期调用增量：

- 正常首版（零线索亦需完整提交）、有原因的暂不能判断、可选备注/取证需求。
- 缺/null/错型/未知字段、非法原时间、陈旧M、False/0和int/float、字典反序首报一致。
- 当前Gate/事实不通过或材料漂移；声明域/名单/scope错；同event/同batch重复。
- 两个并发保存同域；不同运行同域；既有/坏锁/外来锁；原路径reparse/alias/..。
- 真实独占半写、坏/有效failure优先、store成功而运行封装失败、诊断时间/写诊断故障。
- 保存后新增自身、未声明新叶、最后必要消费后的文件/集合变更，保留坏现场/精确恢复本轮原件的区别。
- 正常只读恢复自身、后来不同批记录、已声明旧引用缺/错、当前同批第二份或重复event；旧请求不能重存/覆盖。
- 只读恢复无save/算法/时钟/随机/网络/子进程；完整返回及台账/末次字节支配外层结果。

符号只引用H_EVENT/H_ACTOR/H_DECLARATION/H_TIME/H_ASSESSMENT/H_REASON，不把符号名填成默认人类值，不预填“通过”。夹具只列已登记文件来源：event1 SHA `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`、event2 SHA `e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a`；八权限false，不新增人类字段。新技术路径/请求/锁标识若用于说明，标TECHNICAL_SYMBOL，不是实际批次批准。

## 8. 静态核对、保护与停止

静态核对仅文本/JSON schema块/AST和确切文件SHA：协议与符号案例键集合、状态/FILE/FP角色、参数、顺序、直接/嵌套计数、保存前后历史分离、恢复自身规则、不可覆盖、失败优先与最外层失败支配、无预填人类判断/AI许可相互一致。不得把静态PASS叫业务实测。动态并发/真实句柄/运行保存/恢复/真实数据/身份/AI/终判均null+尚未实施，不伪造调用计数0充动态结果。

局部文档/静态检查/回执定稿后一次全树保护扫描，既有changed=[]；新missing/读取错误/范围外新增0。接受快照自身/review_result两条有限元数据单列，新文件逐确切路径登记；扫描后仅有限自身元数据，不重扫全树。不追认历史偏差。139损失、27恢复、326越界、19命名偏差、TASK-03041 B锁、TASK-038开发/最终失败现场全部保持，不重建/删移/清理。

回执与delivery登记完整四件身份、静态实际观察/未执行、保护及本轮源身份；停止交Architect独立验收。未来实施必须另卡，并因适配器代码变化建立新运行登记/新Gate夹具前提链，不复用TASK-038旧凭证适配新代码；本卡不批准额外业务链或写人类记录。

固定澄明商贸有限公司、人民币（CNY）、2026年9月/截至2026-09-30；金额整数分、原ID、主表与分摊分列、规则线索非舞弊/损失/结论。人类是业务决定及真实Gate批准唯一决策者。D1/D2/D3不授权真实批次、强认证、真实数据、AI或终判。真实批准null、真实初判未保存、开发宿主0008、next/AI=false；文档及技术验收不改变这些状态。
