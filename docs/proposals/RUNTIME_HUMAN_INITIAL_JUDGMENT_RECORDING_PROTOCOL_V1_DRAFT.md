# 运行层人类独立初判保存/恢复协议 V1（拟定，尚未实现）

标识：`RUNTIME_INITIAL_JUDGMENT_RECORDING_DESIGN_NOT_IMPLEMENTED`。设计版本 `TASK-039-recording-design-1.1`。只定义未来两个入口；本卡不实现、导入或调用业务入口，不建立业务链/锁/记录。本协议不批准批次。当前接受身份仍 TASK-038；未来增加适配器代码必须另卡建立新 profile、新登记和合成 Gate 前提链，不能把 TASK-038 凭证改签成新代码。

依据：TASK-039、REVIEW_TASK_038、正式 AUDIT_CONTRACT.md V1、TASK-034 §5—10、冻结 TASK-035/036/037 及 TASK-038。正式契约已经生效；采纳/建设许可不等于本批批准。固定澄明商贸有限公司、人民币（CNY）、2026年9月/截至2026-09-30，整数分、原ID、主表与分摊分列，规则线索不是损失/舞弊/审计结论。真实批准 null、真实初判未保存、开发宿主0008、next/AI=false。

## 1. 两个未来入口与参数

下面是拟定签名，不是现有函数、CLI或可运行命令。

```python
def save_runtime_initial_judgment(
    batch_dir, runtime_dir, request_id, submission, record_relative, *,
    scope_dir, event_relative, database_path, gate2_event_relative,
    history_expectations
): ...

def verify_runtime_initial_judgment(
    batch_dir, runtime_dir, *, scope_dir, event_relative, database_path,
    gate2_event_relative, record_relative, history_expectations
): ...
```

参数按签名顺序检查类型，再按以下固定顺序检查路径和关系。batch_dir/runtime_dir/scope_dir/database_path 仅接受 str 或 pathlib.Path，先保存原路径段、逐级查 link/junction/reparse，再 resolve，并沿现有运行层检查实际批次/登记/单 Gate1 scope/数据库。event_relative/gate2_event_relative 为非空合法UTF-8、安全项目相对POSIX原串；绑定实际当前 Gate 事件，不能由人类事件ID拼成路径。沿当前私有路径检查，不新增公用 bypass。

request_id 必须是非空合法UTF-8原字符串，技术用途，不作为人类event。record_relative 同样是安全项目相对POSIX原串，必须**恰为已绑定 namespace_relative 加一个安全直接叶段**：不以/开头，不含反斜杠、冒号、NUL、空段、`.`/`..`，不 strip/折叠/转大小写；原路径链先于任何消段。父域必须既存、正常且精确等于 registry.initial_judgment_history.namespace_relative，不接受其他空域；叶名与 event_id/actor_id 无推导关系。save 叶必须从未存在（空目录也拒绝），verify 叶必须存在。

history_expectations 是 TASK-037 封闭四键对象：expectations_version/expected_namespace_relative/expected_declared_scope/expected_entries。调用前由调用方独立固定，名单按叶名UTF-8严格升序、唯一，成员恰relative/manifest_file_sha256。域与scope须等于已Gate1绑定登记；save 是保存前现存完整名单，verify 是当前完整名单且含目标。不得默认空列表、从候选重采或跳过未知叶。

submission 沿 TASK-034 九必需/两可选键和全部固定检查顺序。不接收 caller request；不以submission建立独立预期。独立当前请求固定后，原对象直接交冻结store.save，使其内核心处理人类字段、时间、绑定及重复event；不在适配层复制核心首报顺序。初判、原因、事件、身份声明、时间只能人类原文；零线索亦必需完整提交；有原因的暂不能判断有效；原日期不补时间/时区，不据与Gate或系统时间的先后推断独立性。可选键只在核心输出副本补空列表，原提交快照不变。

## 2. 摘要、封闭schema与文件

C(x)=UTF-8 JSON，ensure_ascii=False/sort_keys=True/separators=(",",":")/allow_nan=False；FP(x)=SHA-256(C(x))；FILE(b)=SHA-256(确切原字节)。SHA严格64位小写fullmatch，尾LF/空白/大写不接受。整数用type(x) is int；布尔常量用is。普通ID不排除64hex形状。对象规范相等只比C字节，False/0及0/0.0不同。

新自有JSON独占写 C(object)+单LF、无BOM，逐文件读回与**本次待写缓冲**精确相等；长度/SHA/对象来自同一读回缓冲。名单先排序唯一再算FP，不排序修复输入。未知/缺失键先验检查，按机器块schema键序首报；未知键按UTF-8序；列表原序。所有嵌套对象也封闭，完整冻结对象引用其现有schema，不把“相同自报摘要”当验证。

历史叶保持冻结六文件：expectations.json、judgment_result.json、manifest.json、materials.json、prior_history.json、submission.json；核心record九键、record_status及八false边界原样，不能把persisted改true。历史叶不放context/receipt/锁/日志。运行封装固定在登记同级 `<登记叶名>.initial/`，成功恰started.json/context.json/receipt.json；失败时可能另有failure.json或半写，禁止假装成功布局。

**固定说明 NOTE**：`仅表示合成运行的人类声明初判快照及当前材料/声明历史的本地技术核验；不批准执行，不认证身份，不证明业务真实性，不形成审计结论，不开放AI或终判。`

所有新版本/状态/说明和键集合在§9定稿；版本是未来协议常量，不宣称当前代码已经实现。材料runtime_version来自未来真实新登记，必须与当次代码绑定精确相等，不在本卡编造新代码SHA。

## 3. 单域技术锁

锁路径固定为 namespace 同级 `<namespace叶名>.initial_judgment.lock`，**一个普通文件**，不在声明域内，不污染history直接叶枚举。锁正文五键：lock_version/namespace_relative/runtime_relative/record_relative/request_id；只含技术路径与请求原串，不生成owner身份、随机或人类时间。namespace父路径和锁路径原链也先验检查。已有任意锁（普通、目录、reparse、0字节、坏JSON、陌生正文）立即Blocked lock；不读它猜过期、不接管/补写/清理。

未来Windows实现固定为**真实CREATE_NEW独占句柄方案**：创建时请求读/写/删除权，仅共享读，不共享写/删除；持有该句柄直到全部材料/输出末次确认。记录父目录身份、句柄file ID、大小、属性和本次锁缓冲；写/读回失败则保留已出现的锁/半写，关闭本次句柄但不删除。句柄不能由request_id或相同文本代替。

成功释放前逐项核原路径链/父目录/锁路径file ID与最初句柄身份、句柄实际字节与本次缓冲、正常文件属性；任何不一致不删。**删除绑定该已持有句柄的文件对象**，不得关闭后仅凭路径unlink，也不得删除同内容替代锁。Windows按句柄设置删除标记并关闭；仅置pending不冒称释放完成，必须确认锁已解除。平台不能按已持有句柄执行时，Error release.lock，禁止静默退化成路径盲删。具体系统调用封装留实施卡，所要求的身份语义/失败结果在此固定；本卡不运行它、不声称已证明物理平台能力。

仅成功流程可释放本次确证自锁；失败不设置删除标记，保留现场并关闭资源句柄，不重试/回滚。若系统释放阶段已部分完成再失败，保存实际剩余状态，不伪造重建锁，不承诺“从未发生”。外来锁永不释放。锁只串行遵守本接口的本地保存者：不同runtime同域仍用这一把锁。不能证明非合作篡改、强认证、全历史不可删或跨两根原子事务。

verify 不取得锁：开始、必要边界及末端发现锁都拒绝；全程不写、不取时钟/随机、不生成owner或failure。它只返回有界读取窗口的事实，不能担保返回后数据永远不变。

## 4. 保存前到保存后（固定S1—S9）

**S1 参数/路径与失败先验**：检查绑定域、save叶和运行封装都从未存在；锁任意存在先拒绝。记录本次源原串/路径属性，不创建历史叶。原输入引用由调用方观察：进入、store返回后、所属save收尾三时点；非法类型指纹不可得要登记原因，不转换成虚假JSON。

**S2 取得自锁**：独占创建/读回，固定句柄与字节身份。其后重新实读当前登记、Gate/事实/历史和全部依赖，不能复用锁前旧成功或聊天倾向。

**S3 独立当前请求**：持锁真实调用现有公开prepare_runtime_initial_judgment_request **一次**，沿其当前四核验及完整开始捕获、静态绑定、目录/failure检查。它内部真实核验保存前n叶，已有本批记录即拒绝。本次完整两键返回、materials10/expectations12/七键evidence必须与本次开始同缓冲独立来源闭合，先固定预期，尚不读取人类assessment/reason去推导它。保存前H0就是该真实history十二键返回；P0=H0.prior_history，保持原三键和FP。

**S4 started独占写**：封装目录独占创建，写started并读回。started只含已核验技术batch/request/record路径、source_binding、pre_history_binding及false边界，**不填未知event/actor、不先序列化非法submission求FP**。source_binding七字段及pre_history_binding三字段见§9；完整Gate/事实/运行/契约及旧历史对象将在context保存。started不表示核心已校验或保存完成。

**S5 唯一存储构建调用**：store调用前复确认S3开始依赖、H0旧叶六字节/集合、原路径、锁句柄及started writer缓冲。仅调用冻结
`store.save_human_initial_judgment_snapshots(submission, request.materials, request.expectations, prior_history=P0, out_dir=目标叶)` 一次。
其中 `request = prepared["request"]`，`prepared`是S3的完整两键真实返回；不把外层当materials。该函数内部自己调用初判核心一次；不预调用核心，不重新校验一套人类字段。陈旧M、错误batch/request、非法时间/未知字段及重复event由这一真实核心定位。人类错误可以不建记录叶，但已取得的锁/started/failure现场按失败规则保留。

**S6 绑定本次实际S返回**：S为完整十一键STORED返回。立即同缓冲实读本次六文件；manifest FILE必须等于S.manifest_file_sha256，再按完整S.files核六份长度/FILE/对象FP。四快照与本次传入的原submission/current materials/独立expectations/P0精确相等；完整两键judgment_result与S及实际输入关系闭合；冻结组件核当前原件。不给另一轮新读数或另一份自报S相同比较凑通过。原提交原字符串/可选键省略样式原样存入快照，不把核心归一后的11键人类副本回写成输入。

**S7 独立保存后名单**：E1.expected_entries = UTF8排序(E0旧名单 + {目标叶名, S已核验manifest FILE})；域/scope/version与E0相同。不得从实际目录重枚举“顺便接受”别的叶。真实调用history.inspect一次，得到H1。它对n+1叶各真实verify/core一次，不另直呼当前叶verify。全H1必须与旧n叶开始缓冲、本次六缓冲及独立E1闭合；I1=排序(I0 + 本次完整record提取的四字段index)，H1.prior_history精确等于{true,原scope,I1}。**旧P0和旧expectations绝不改成H1**。

**S8 封装与返回构造**：context十键保存原两键prepared_request、原submission、完整H0/S/H1、六文件描述及独立E1、started绑定和边界。先独占写context/readback，再最后独占写receipt/readback。receipt FILE绑定started/context和本次目标manifest；post_history_fingerprint=FP(H1.prior_history)，无自身摘要。完整成功返回先深拷贝构造，storage_verification取H1中目标的完整VERIFIED返回，与S除status外全部精确相等。成功外层不缩减为record FP或bool。

从已核验源/H1目标/本次writer缓冲先固定独立十二键返回预期，再构造候选；先封闭schema/严格类型，后完整C字节比较。候选类型矛盾精确Blocked `result.字段`；内部内容审核产生非空问题时Error `audit.result`，问题及reasons保留，不能把false审核硬填true。任何失败都禁止成功返回。

**S9 末次确认/释放/返回**：全部JSON解析/FP/候选审核/返回构造已完成。只以S3开始依赖、旧叶缓冲、本次六缓冲、三份封装writer缓冲为预期，末次实读全依赖、原路径链/集合/failure、提交实际引用和自锁身份；域集合恰E1，唯一允许新增为目标。随后只作§3本次句柄技术释放，不再读业务JSON、调用核心/prepare或刷新预期；释放失败不返回成功。成功直接return。最后原始字节检查是有界窗口，不夸大为外部写入也不能绕开的跨根事务。

## 5. 封装关系及恢复（固定V1—V8）

started.source_binding：source_batch_relative/runtime_relative/gate1_event_relative/gate2_event_relative/database_relative来自显式已核验路径；registry_binding为TASK-038现有完整五键；contract_effective_record为其完整三键。六项run_binding、完整Gate/事实四件通过context.prepared_request及实际依赖固定，不能只信路径。pre_history_binding的namespace/scope/P0 FP与H0和registry精确相等。

context.started_binding为本次started的四字段FILE描述；prepared_request完整两键；submission_snapshot为本次原对象；prior_history_verification完整H0；store_save_result完整S；snapshot_files是六个项目相对文件描述（UTF8排序），对应S.files的local relative加已绑定叶前缀；post_history_expectations为独立E1；post_history_verification完整H1；boundaries全false。没有额外原JSON文件排版保真承诺。

receipt.identity等于S.identity且与实际核心人类event、批次、request原ID闭合；record_relative等于显式目标；started/context FILE取本次writer读回，snapshot_manifest_file_sha256等于S及实际六缓冲。receipt.post_history_fingerprint只绑定**保存当时H1**，不能拿恢复时新增后的当前H整体FP代替。三份封装都没有自指FILE/FP；返回的envelope_binding在三份写定后才列其FILE/长度/FP，自己不另落manifest。

**V1 固定原件/拒绝失败**：参数与registry域绑定先检查；运行封装或目标叶任何failure/锁优先阻断。有效failure分类映射，坏failure先类型/常量/键集合拒绝，不被context缺失遮蔽。成功封装恰三件、目标叶恰六件；同缓冲固定所有依赖、封装、声明域所有m叶（含目标）的开始读数。目标若不在caller完整名单，history_expectations.expected_entries拒绝。

运行failure使用本协议十一键；历史目标failure沿冻结store的十键及常量，用已接受校验逻辑只读检查，不借调用store.verify多走一次核心。valid BLOCKED保留原field并加runtime.failure.或store.failure.前缀，valid ERROR保留原stage；坏JSON/缺键/类型定位对应failure字段，读取OSError才按Error `read.failure`。锁检查优先于消费正文；锁、两处failure及布局都通过才继续。

**V2 完整当前域核验**：真实history.inspect一次，Hc完整十二键必须与开始名单/各叶六缓冲及完整store返回闭合。从verified_snapshots取目标完整VERIFIED十一键及四快照/完整两键结果，不再直呼store.verify。重复event/同batch、坏其他叶及所有声明引用均不得跳过。

**V3 目标/封装闭合**：先验三份schema再消费；目标S恢复结果与context.store_save_result除STORED/VERIFIED常量差外完整相等；所有六FILE/FP、原submission、identity和封装FILE关系闭合。目标snapshot.prior_history正是P0，expectations.expected_prior_history_fingerprint、record.history_binding和H0.prior_history精确闭合；P0不是Hc减自身。

**V4 私有共享材料分支**：只有V2目标完整核验和V3绑定通过后，内部固定目标来源及request_id，真实直接核Gate1/Gate2/fact各一次。共享一个有限私有“当前九键材料正文/八角色与独立预期物化”分支，复用TASK-038开始捕获/完整返回绑定/末次确认，不调用会拒绝自身的公开prepare。没有skip/ignore/force/allow_existing或caller-supplied true；公开prepare原同批拒绝规则不变。私有分支输入仅内部捕获源与已真实核验Gate/fact结果，不信目标存储材料作为当前预期，不重写冻结算法。

**V5 当前材料/旧历史分离**：从当前实际来源固定九键正文、M、八FILE角色、Gate/契约/运行/事实。目标完整materials必须精确相等；独立重建十二键expectations，前十项取当前来源及已核验目标request_id，最后两项取**已核验保存时P0**的scope/FP；与目标快照整对象比较。材料漂移、旧运行版本、正式契约/范围/代码/规则/配置/输入或事实变化拒绝，不迁移/补签。人类时间不参与“独立性”推断。

**V6 允许后来追加，不刷新旧决定**：P0中每个四字段引用仍须在Hc当前完整索引精确找到；context.H0记录的旧叶六文件、context.H1记录的当时n+1叶六文件仍须与当前对应原件相等。H1.prior_history仍是保存时I0加目标，不用Hc覆盖。其他批次后来合法新记录可多于H1，只要Hc全域/引用闭合、旧叶和目标不变。不是“当前域减自身”回造旧历史；也不声称无引用记录未曾删失或发现域外历史。

**V7 构造完整返回**：status为VERIFIED，history_verification为当前完整Hc，可与保存返回H1不同；storage_verification目标与原S稳定字段相同；envelope_binding来自本次开始的三份原文件。所有权限边界仍false。

**V8 最后确认直接返回**：全部必要消费/解析/FP/返回构造之后，对本次开始的全部当前依赖、m叶/三封装、原路径/集合/锁不存在/failure不存在做末次原字节确认。之后直接return；不写诊断/日志、不取时间/随机/网络/子进程，不靠重复H/core刷新当前来源。

## 6. 调用图与观察

文中history.inspect/H.inspect均是冻结`inspect_human_initial_judgment_history(namespace_dir, *, expectations)`的简称；store.save/verify分别是冻结`save_human_initial_judgment_snapshots`/`verify_human_initial_judgment_snapshots`，prepare是现有`prepare_runtime_initial_judgment_request`。这些简称不新增API，不表示存在名为inspect/save的替代实现。

固定不加额外只读Gate复核（必要静态/字节复确认不算业务调用）。保存直接：公开prepare1、store.save1、保存后history1；保存前history是prepare内部1。正常保存前n叶：history总2，初判store.verify=2n+1，初判核心=2n+2，其中构建1、核验2n+1；**不是整个保存只进核心一次**。

恢复当前m叶（m≥1）：直接history1/Gate1 verify1/Gate2 verify1/fact inspect1；公开prepare0、store.save0、初判store.verify/core各m，初判核心直接0。

两种正常路径的既有Gate/fact嵌套图各相同：Gate1 verify6、Gate2 verify5、load inspect5、screen inspect2、crosscheck inspect1、facts inspect/render各1、Gate store.verify/P1各11、冻结准备器6。SQL/标准化/装载/复算/事实build/旧模拟初判均0。提前失败按实际已到阶段计，不套成功公式。

未来观察按实际原代码对象、所属父调用、构建/核验、setup/正式窗口分列；输入同一真实引用三时点、完整返回/异常/traceback/reasons/cause/context/secondary保留。重放旧观察不算本进程新调用。完整候选与写前独立定稿内存观察canonical比较、台账自身同缓冲读回、末次原字节共同支配最外层API/未来CLI/summary/failures；任一FAIL不得被外层全局旧PASS或默认0覆盖。本卡这些动态数均null、未执行。

## 7. 异常、半成功及失败诊断

沿用RuntimeGate1Blocked(field,reason) / RuntimeGate1Error(stage,reason)。store/history按实际加载模块类对象分类，不按名字或有无field猜；Blocked分别加store./history.且保留原字段余部、reason/reasons和cause；Error保留原stage/reason/reasons/cause及secondary_errors。本层产生的错误给准确阶段（S1—S9/V1—V8及细阶段）。异常不是成功返回。

运行failure固定十一键见§9。仅在本次已经独占创建封装目录后独占写，既有目录/未知现场不写；仅一次，不覆盖半写或已有failure。identity在核心尚未成功前为null，成功后为已核验三键，不从缺失提交猜人类event。classification=BLOCKED时field非空；ERROR时field=null。reason原文；reasons若来源有则原列表深拷贝，无则本层明示派生[reason]；cause_chain非空，首项类型与exception_type相符；次错误分列，不顶替主异常、stage或field。

运行failure**不新增诊断时间字段**。冻结store已存在的诊断技术时钟故障由其原secondary_errors暴露，本层保留；运行诊断序列化/写入/链采集再失败，API仍传播原主异常及可得次错误，已写坏诊断不重写。读取坏failure先schema Blocked，有效ERROR failure按原stage Error，有效BLOCKED按原field Blocked；verify不再写failure。

store六件成功而context/receipt/读回/末次确认/释放失败，只能报告运行层失败：完整六快照可能保留，started/context/receipt可能部分存在，锁或其剩余部分保留。不得删除成功叶、回滚、补签、重写旧prior/expectations或将独立store成功当运行层完成。后续save因锁/旧叶/同批拒绝，verify因锁/failure/不完整拒绝；未来人工处置另卡。本协议没有自动恢复/清理端点，两个输出根不原子。

## 8. 符号、人类来源与停止

案例只用H_EVENT/H_ACTOR/H_DECLARATION/H_TIME/H_ASSESSMENT/H_REASON，不把符号填为默认提交。现有登记源仅列：data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json（SHA 81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560）；data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json（SHA e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a）。不抄进可提交人类样例，不新增人类字段。TECH_NAMESPACE/TECH_LEAF/TECH_REQUEST等只为TECHNICAL_SYMBOL。

本卡仅文本/JSON/AST/确切SHA静态核对；动态并发、真实句柄、保存、恢复、AI等均null+未实施，静态PASS不是业务实测。既有文件全冻结，一次最终保护扫描后交Architect；不操作看板、不实施保存或下一卡。

## 9. 机器可读键集合和设计常量

此块描述schema，不是提交、批准或运行配置。所有keys列表为固定schema首报顺序，未知键UTF8序；所有自有对象严格dict/list/str/int/bool。冻结完整对象分别引用TASK034_SCHEMA和冻结store/history形状。file_descriptor用于JSON文件，FILE/FP均由同一真实缓冲取得；不适用于把工作簿转对象。

<!-- TASK039_SCHEMA_BEGIN -->
```json
{
  "design_version": "TASK-039-recording-design-1.1",
  "stage_version": "TASK-039-runtime-human-initial-judgment-1.0",
  "save_status": "RT_HUMAN_INITIAL_JUDGMENT_RECORDED",
  "verify_status": "RT_HUMAN_INITIAL_JUDGMENT_VERIFIED",
  "scope": "RUNTIME_CURRENT_MATERIALS_AND_DECLARED_HISTORY_ONLY",
  "started_version": "TASK-039-initial-judgment-start-1.0",
  "context_version": "TASK-039-initial-judgment-context-1.0",
  "receipt_version": "TASK-039-initial-judgment-receipt-1.0",
  "failure_version": "TASK-039-initial-judgment-failure-1.0",
  "lock_version": "TASK-039-initial-judgment-lock-1.0",
  "note": "仅表示合成运行的人类声明初判快照及当前材料/声明历史的本地技术核验；不批准执行，不认证身份，不证明业务真实性，不形成审计结论，不开放AI或终判。",
  "save_positional": ["batch_dir", "runtime_dir", "request_id", "submission", "record_relative"],
  "save_keyword_only": ["scope_dir", "event_relative", "database_path", "gate2_event_relative", "history_expectations"],
  "verify_positional": ["batch_dir", "runtime_dir"],
  "verify_keyword_only": ["scope_dir", "event_relative", "database_path", "gate2_event_relative", "record_relative", "history_expectations"],
  "success": ["stage_version", "status", "scope", "identity", "record_relative", "record_fingerprint", "manifest_file_sha256", "storage_verification", "envelope_binding", "history_verification", "boundaries", "note"],
  "identity": ["batch_id", "event_id", "request_id"],
  "started": ["started_version", "batch_id", "request_id", "record_relative", "source_binding", "pre_history_binding", "boundaries"],
  "source_binding": ["source_batch_relative", "runtime_relative", "gate1_event_relative", "gate2_event_relative", "database_relative", "registry_binding", "contract_effective_record"],
  "registry_binding": ["registry_version", "registry_file_sha256", "registry_byte_size", "run_binding_sha256", "initial_judgment_history"],
  "initial_judgment_history": ["namespace_relative", "declared_scope"],
  "contract_effective_record": ["relative", "file_sha256", "byte_size"],
  "pre_history_binding": ["namespace_relative", "declared_scope", "prior_history_fingerprint"],
  "context": ["context_version", "started_binding", "prepared_request", "submission_snapshot", "prior_history_verification", "store_save_result", "snapshot_files", "post_history_expectations", "post_history_verification", "boundaries"],
  "receipt": ["receipt_version", "identity", "record_relative", "started_file_sha256", "context_file_sha256", "snapshot_manifest_file_sha256", "post_history_fingerprint", "boundaries"],
  "file_descriptor": ["relative", "byte_size", "file_sha256", "object_fingerprint"],
  "envelope_binding": ["relative", "files"],
  "lock": ["lock_version", "namespace_relative", "runtime_relative", "record_relative", "request_id"],
  "failure": ["failure_version", "scope", "identity", "stage", "classification", "field", "reason", "reasons", "exception_type", "cause_chain", "secondary_errors"],
  "chain_item": ["exception_type", "message"],
  "boundaries": ["workflow_connected", "execution_allowed", "next_step_allowed", "ai_enabled", "identity_authenticated", "source_authenticity_proven", "audit_conclusion_formed", "final_judgment_recorded", "global_history_completeness_proven"],
  "snapshot_files": ["expectations.json", "judgment_result.json", "manifest.json", "materials.json", "prior_history.json", "submission.json"],
  "envelope_files": ["context.json", "receipt.json", "started.json"],
  "submission_required": ["submission_version", "event_id", "batch_id", "request_binding", "submission_source", "actor", "decided_at_raw", "assessment", "reason"],
  "submission_optional": ["finding_notes", "evidence_requests"],
  "history_expectations": ["expectations_version", "expected_namespace_relative", "expected_declared_scope", "expected_entries"],
  "prior_history": ["declared_complete", "declared_scope", "records"],
  "history_index": ["event_id", "batch_id", "record_fingerprint", "binding_fingerprint"],
  "store_return": ["status", "scope", "identity", "record_fingerprint", "manifest_file_sha256", "technical_registration", "component_bindings", "files", "boundaries", "snapshots", "judgment_result"],
  "history_return": ["history_version", "status", "scope", "namespace_relative", "prior_history", "prior_history_fingerprint", "inventory", "inventory_fingerprint", "component_bindings", "verified_snapshots", "boundaries", "note"],
  "save_order": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"],
  "verify_order": ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"],
  "save_calls": {"public_prepare": "1", "history_total": "2", "initial_store_save": "1", "initial_store_verify": "2*n+1", "initial_core_construct": "1", "initial_core_verify": "2*n+1", "initial_core_total": "2*n+2", "direct_initial_core": "0"},
  "verify_calls": {"public_prepare": "0", "history_total": "1", "initial_store_save": "0", "initial_store_verify": "m", "initial_core_total": "m", "direct_initial_core": "0"},
  "gate_fact_calls": {"gate1_verify": 6, "gate2_verify": 5, "load_inspect": 5, "screen_inspect": 2, "crosscheck_inspect": 1, "fact_inspect": 1, "fact_render": 1, "gate_store_verify": 11, "gate_core": 11, "frozen_prepare": 6},
  "forbidden": ["normalize", "load", "SQL_screen", "crosscheck_build", "fact_build", "simulated_initial_judgment", "AI", "network", "subprocess"],
  "human_symbols": ["H_EVENT", "H_ACTOR", "H_DECLARATION", "H_TIME", "H_ASSESSMENT", "H_REASON"],
  "digest_role_contract": "EXPLICIT_FIELD_SOURCE_NOT_SUFFIX",
  "digest_roles": {
    "source_binding.registry_binding.registry_file_sha256": {"role":"FILE","basis":"runtime_registry.json exact bytes"},
    "source_binding.registry_binding.run_binding_sha256": {"role":"FP","basis":"registry.run_binding"},
    "context.prepared_request.request_sha256": {"role":"FP","basis":"context.prepared_request.request"},
    "materials.materials_fingerprint": {"role":"FP","basis":"materials minus top-level materials_fingerprint"},
    "materials.fact_snapshot.packet_canonical_sha256": {"role":"FP","basis":"materials.fact_snapshot.packet"},
    "materials.fact_snapshot.source_fingerprints.workbook_sha256": {"role":"FILE","basis":"bound source/input.xlsx exact bytes"},
    "materials.fact_snapshot.source_fingerprints.normalized_payload_sha256": {"role":"FP","basis":"bound normalized object"},
    "materials.fact_snapshot.source_fingerprints.screening_report_sha256": {"role":"FP","basis":"bound screening_report object"},
    "materials.fact_snapshot.source_fingerprints.crosscheck_report_sha256": {"role":"FP","basis":"bound crosscheck_report object"},
    "store.fingerprints.submission_fingerprint": {"role":"FP","basis":"received submission snapshot"},
    "store.fingerprints.materials_snapshot_fingerprint": {"role":"FP","basis":"complete materials snapshot"},
    "store.fingerprints.materials_body_fingerprint": {"role":"FP","basis":"materials minus top-level materials_fingerprint"},
    "store.fingerprints.expectations_fingerprint": {"role":"FP","basis":"independent expectations snapshot"},
    "store.fingerprints.prior_history_fingerprint": {"role":"FP","basis":"saved prior_history P0"},
    "store.fingerprints.record_fingerprint": {"role":"FP","basis":"judgment_result.record"},
    "store.fingerprints.binding_fingerprint": {"role":"FP","basis":"judgment_result.record.binding"},
    "pre_history_binding.prior_history_fingerprint": {"role":"FP","basis":"saved prior_history P0"},
    "history_verification.prior_history_fingerprint": {"role":"FP","basis":"that verification.prior_history"},
    "history_verification.inventory_fingerprint": {"role":"FP","basis":"that verification.inventory"},
    "receipt.post_history_fingerprint": {"role":"FP","basis":"saved H1.prior_history"},
    "success.record_fingerprint": {"role":"FP","basis":"target judgment_result.record"},
    "success.manifest_file_sha256": {"role":"FILE","basis":"target manifest.json exact bytes"},
    "receipt.snapshot_manifest_file_sha256": {"role":"FILE","basis":"target manifest.json exact bytes"},
    "receipt.started_file_sha256": {"role":"FILE","basis":"this started.json writer buffer"},
    "receipt.context_file_sha256": {"role":"FILE","basis":"this context.json writer buffer"},
    "file_descriptor.file_sha256": {"role":"FILE","basis":"the described JSON file exact bytes"},
    "file_descriptor.object_fingerprint": {"role":"FP","basis":"object parsed from the same described file buffer"}
  }
}
```
<!-- TASK039_SCHEMA_END -->

success.identity/record_fp/manifest_FILE等于选中目标完整storage_verification及实际六缓冲；history_verification恰完整当前H1/Hc；envelope_binding.files恰三描述。context.prepared_request恰TASK-038外层两键，内部六键及materials10/expectations12/evidence7/十false保持原样，不将历史时点的request_persisted改true。started/context/receipt/成功新权限边界恰九键全false；classification只为BLOCKED/ERROR，reasons是非空str列表，chain_item.message允许原空串但类型必须str，secondary_errors列表可空。failure.identity可null或identity三键；保存成功identity必三键。所有byte_size严格非负int、所有FILE/FP严格64hex；各版本/状态/scope/note均精确常量，无可选默认。

字段值规则同时固定如下，不只核对键数：

- success.stage_version/scope/note分别等于本块对应常量；status按入口分别为save_status/verify_status。failure.scope也等于本块scope。started/context/receipt/lock/failure的版本字段各等于本块同名常量。storage_verification.status精确为冻结store.VERIFIED，context.store_save_result.status精确为冻结store.STORED，二者分别为`HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED`/`HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED`；history完整对象的常量沿冻结history，不缩写成新的状态值。
- identity三项、started.batch_id/request_id及lock.request_id均为非空合法UTF-8原字符串，与已核验来源/目标原值精确相等；原ID可含换行/前导零，不以64hex形状排除。所有relative字段为已绑定的安全项目相对POSIX原串；namespace及目标直接叶关系按§1。摘要类型逐字段按已规定的语义及来源取FILE或FP，**不能根据后缀猜测角色**，也不能因都为64hex互换。直接继承的run_binding_sha256/request_sha256/packet_canonical_sha256以及normalized/screening/crosscheck对象摘要均为FP；工作簿、登记、三封装、六快照及manifest的文件描述取确切FILE。
- file_descriptor.relative在context.snapshot_files及envelope_binding.files中均为**项目相对完整文件路径**，不是本地basename；分别恰目标六件和封装三件，UTF8升序唯一、长度/FILE/对象FP全从同一缓冲取得。started_binding也是一份完整descriptor。receipt的三个FILE字段与这些descriptor对应；post_history_fingerprint只取保存当时H1的prior_history。
- source_binding/pre_history_binding/envelope_binding/registry_binding及其嵌套对象封闭键序见本块；registry_byte_size同样严格非负int。context各完整冻结对象先各自封闭schema，再作§4/§5指定关系比较。snapshots提交可选键省略样式保留，完整judgment_result只能是冻结两键外层，record只能是TASK034九键正文。
- failure.stage/reason/exception_type是非空str，field按classification规则；cause_chain是非空chain_item列表，exception_type非空、message为原str，首项类型等于failure.exception_type。secondary_errors原顺序保留，成员只允许非空str（现有运行层技术说明）或封闭chain_item（冻结store异常链）；本层新诊断次异常用chain_item，不把它拼成主stage或清空原链。reasons逐项为非空str，无原列表时才派生[reason]。
- 新本层阶段名固定为path、lock.acquire、lock.confirm、release.lock、write.started、write.context、write.receipt、read.envelope、read.failure、bind.store、history.post、audit.result、save.final、verify.final；真实冻结组件Error阶段按§7原值传播。独占创建/读回的OSError使用其所属阶段，协议/来源矛盾使用精确field的Blocked；receipt真实writer返回后sentinel在write.receipt边界映射，不另留任选阶段。

digest_roles是有限**设计元数据**，不是新增业务字段或提交键。materials表示context.prepared_request.request.materials（以及相同的目标快照）；store.fingerprints表示冻结manifest.fingerprints；history_verification表示H0/H1/Hc各自完整核验对象。同一继承字段在expectations/record/evidence中重复引用时，沿冻结TASK-034/036/037/038的同一字段契约，不能另选摘要算法。

file_descriptor行适用于context.started_binding、context.snapshot_files六件、success.envelope_binding.files三件及冻结store.files/manifest.payloads的相同描述字段：每个FILE是本次对应原缓冲，object_fingerprint是同缓冲解析对象的FP，两者分别核对。manifest不内嵌自身FILE，目标manifest FILE由实际store完整返回及外层receipt/success绑定。record/binding/P0/历史索引及清单对象FP不转换为它们所在JSON文件的FILE。

run_binding_sha256必须等于FP(registry.run_binding)，request_sha256必须等于FP(context.prepared_request.request)；两者既不取包含文件的FILE，也不取C(对象)+LF的SHA。packet_canonical_sha256与packet文件FILE、normalized/screening/crosscheck对象摘要与其JSON文件FILE同样分列。已有完整对象内其他字段继续沿冻结契约，角色登记不重设其常量、schema或算法。仅改变JSON排版可能改变FILE而不改变FP，故不能用形状合法或两份候选互相相等替代指定来源关系。
