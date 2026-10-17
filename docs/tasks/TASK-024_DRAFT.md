# TASK-024：Gate1决定保存与限定历史核验适配器

日期：2026-10-14。**C类：GPT设计 + DSH执行**。前提为 `docs/reviews/REVIEW_TASK_023_R2.md` 的ACCEPTED与最终保护登记。人类转交/操作看板，实施前建卡；完成本卡后停止实施交验收，不能自行推进下一阶段。

## 1. 目标和停止点

把已验收的实际材料准备与快照存储连接起来：人类先取得当前材料请求，再明确提交Gate1决定；系统从当前文件重新生成独立预期、实读限定范围的既有记录，保存并核验这一次提交。

本卡**止于独立Gate1记录已保存/可核验**。不改宿主/控制器，不执行标准化/DB/筛查，不接Gate2，不产生0009、真实初判、AI/终判，不将APPROVE解释为执行许可。所有新接口execution_allowed/workflow_connected/ai_enabled保持严格false。

D1/D2/D3和正式V1生效已由人类明确决定，不重问。人类的姓名/身份声明/事件ID/时间/决定/原因只能来自submission；程序不生成或补造。测试全部标为PROTOCOL_TEST_FIXTURE_ONLY（标在测试证据外层，不加进P1封闭submission），不是主理人真实提交。

## 2. 文件范围与起点

仅新增：

- `scripts/record_demo_human_gate1.py`
- `tests/test_record_demo_human_gate1.py`
- `docs/HUMAN_GATE1_DECISION_GUIDE.md`
- `docs/EXEC_REPORT_024.md`
- 新 `data/human_gate1_decision_tests/task024_<唯一轮次>/`
- 新 `data/batches/task024_<同轮次>/`，仅最少接收样本。
- 新 `data/human_gate_decision_records/gate1/task024_<同轮次>/`，本卡测试管理范围；允许必要父目录。不得触碰该namespace外的旧存储记录。若gate1下已有非本轮内容，先只读登记，不覆盖/清理。

**所有既有文件冻结**。准备器SHA `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4`；存储 `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7`；P1 `5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79`；配置 `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c`；宿主 `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`。契约/登记及其他冻结身份从验收基线取，不改或重命名旧协议。

基线 `data/reviews/task023_r2_gpt_20261014_034254/source_hashes_after.json`；完整SHA/项数及两个确切自指排除见同目录ACCEPTED review_result。先读P1协议/指南的历史规则与矩阵、存储公开API、准备指南、正式契约及本卡。仅标准库和既有依赖；不安装、不初始化Git、不删除旧现场。

## 3. 三个公开API，无CLI

1. `prepare_human_gate1_decision_request(batch_dir, request_id)`：只读，返回新的32项材料请求。
2. `save_human_gate1_decision(batch_dir, request_id, submission, event_dir, *, scope_dir=None)`：显式限定历史范围并保存。scope_dir缺省/None结构化Blocked，不默认空历史。
3. `verify_human_gate1_decision(event_dir, batch_dir, *, scope_dir=None)`：只读核验已保存记录及当前来源，不能重新批准。

异常 `HumanGate1DecisionBlocked(field, reason)` / `HumanGate1DecisionError(stage, reason)`；保留下游原field/reason和cause/context链，不泄漏原生类型/I/O异常，不包装成成功。字段/路径拒绝与运行/I/O失败分开，无本模块CLI退出码。

prepare返回六键形状沿用准备器，但request_version=`TASK-024-human-gate1-decision-request-1.0`、status=`HUMAN_GATE1_DECISION_REQUEST_PREPARED`。materials七键、expectations八键、evidence七键、原七项false边界均保留，不生成submission。

save/verify成功返回**恰九键**：adapter_version=`TASK-024-human-gate1-adapter-1.0`；status分别为HUMAN_GATE1_DECISION_RECORDED/VERIFIED；scope=`LOCAL_GATE1_DECISION_RECORDS_ONLY`；identity恰{batch_id,event_id,decision}；record_fingerprint；event_dir和scope_dir（核验后的项目相对路径）；store_result（冻结存储完整八键返回）；boundaries（见§6六项false）。没有approved_for_execution=true或next=true。

## 4. 新层代码绑定：明确32项，不改旧31项

本新组件必须绑定自身代码，不能只存旧准备器31项而漏掉实际保存者。

每次真实调用冻结prepare_human_gate1_request(batch_dir, request_id)，只消费其经核验的完整返回，不接受调用方status/materials/expected/历史对象。实读本新adapter文件，扩展副本：

- 在code_manifest.entries中加入 `scripts/record_demo_human_gate1.py` 与其文件SHA，UTF-8升序唯一，共14项。
- materials.files加 `project/scripts/record_demo_human_gate1.py` 的实际长度/SHA，共32项；其他31项不删改。
- run_binding.code.file_sha256指向新adapter实际字节，manifest_fingerprint取新14项清单规范指纹；rules/config/input/contract保持真实原绑定。
- 按冻结P1唯一正文算法重新计算materials_fingerprint及八键独立expectations；evidence.code_manifest对应14项。所有预期来自本次实际读数，不从submission取。

这是**新层新请求版本**，旧准备器API/31项协议冻结不动。旧31项请求指纹不能拿来保存新层决定；人类需审阅新32项请求。准备和保存都在最后必要消费后实读32份白名单字节与初始预期比较、复查路径和集合；新adapter文件也参与。保存时重新真实准备，材料变更即拒绝旧submission。

代码/规则/配置/范围变更按契约新批次/新请求，测试全部新接收批次；本层不声称发现所有过去未持久化的内存请求，也不静默迁移旧开发批准。普通ID与人类字符串原文保真，技术文件路径另按Windows文件规则处理，不能要求event_id等于目录名。

## 5. 明确历史范围与并发边界

scope_dir必须由调用方**显式先建立**，是 `data/human_gate_decision_records/gate1/` 严格后代；首次可为空。event_dir必须是scope_dir的**直接子目录**且从未存在（含空目录拒绝）。原始绝对路径逐级无link/junction/reparse，再resolve复核，文件须正常文件；不能跟随JSON中的任意绝对路径。scope根/越界/互为不合法祖先均拒绝。

scope只含本层事件目录，保存时另有一个独占 `.gate1.lock`。保存以O_CREAT|O_EXCL取得该锁；已占用立即Blocked，不自动回收、不等候重试、不把失败当新scope自动重跑。锁内容固定{lock_version,operation}，版本TASK-024-gate1-scope-lock-1.0、operation=SAVE，不造人类时间/事件ID。只清理本次确实独占创建、路径/字节仍匹配的自己的锁；不能删旧锁或其他数据。崩溃遗留锁如实阻断，清理由人类另行决定。verify全程不创建/删除锁，存在锁即拒绝，结束复查。

实读枚举本scope全部事件目录；未知文件/失败/半写/缺receipt/版本不符均阻断，不跳过。每个历史事件只用本层封套与冻结store.verify核验保存快照，**不读取历史业务源文件**，不把历史APPROVE当当前材料仍有效。完整事件按技术revision严格为1…N连续唯一；每条prior_scope必须准确引用全部更早revision的实际封套/六快照文件及完整P1记录，不得漏掉较早HOLD/REJECT。revision只是存储序号，不是人类事件ID、时间或批准。

从实际核验的完整record构造冻结wrapper，按原event_id UTF-8排序唯一，生成P1 prior_history：declared_complete=true仅表示**本次实际枚举该scope**，declared_scope=`GATE1_LOCAL_SCOPE:<项目相对scope路径>`，records为全部历史wrapper。空根经实际检查才可records=[]，不是缺参默认。不要把当前批次/运行条件套给其他合法历史批次。

P1既定规则保持：相同event_id拒绝；同批次Gate1已有APPROVE拒绝后续提交；合法HOLD/REJECT历史不能一律禁掉。保存新提交由冻结store.save内部P1恰一次决定；历史核验每个store.verify的P1复算另计。不得先直接调用P1校验一次，再store.save调用第二次。

此范围不是全局历史发现/身份认证，不能证明其他scope没有记录或抵御同权限完整删尾/重写。程序不得自动换scope规避失败；版本不一致如实阻断，旧记录保留，迁移/跨范围引用另行定界。

## 6. 封套与冻结存储，避免修改六文件协议

每个成功event_dir恰为：`context.json`、`receipt.json`及`snapshots/`。snapshots内仍是冻结存储恰六文件，不添加字段/文件、不把P1 record.persisted=false改true。

context.json**恰九键**：context_version=`TASK-024-gate1-context-1.0`；revision（严格整数N+1）；event_relative（本scope下叶名）；source_batch_relative（实际批次项目相对路径）；request（§4完整六键新请求）；prior_scope；snapshot_files；store_result；boundaries。

prior_scope**恰四键**：scope_relative、declared_scope、prior_events、prior_history_fingerprint。prior_events按revision升序，每项恰{revision,event_relative,context_file_sha256,receipt_file_sha256,snapshot_files}；snapshot_files恰六项，按文件名UTF-8升序，成员{relative,byte_size,file_sha256}且relative只能为冻结六文件名。prior_history_fingerprint为完整P1历史对象的canonical指纹，须与snapshots/prior_history.json闭合。

receipt.json**恰十键**：receipt_version=`TASK-024-gate1-receipt-1.0`；status=`HUMAN_GATE1_EVENT_COMPLETE`；revision；context_file_sha256；snapshot_manifest_file_sha256；record_fingerprint；batch_id；event_id；decision；boundaries。最后独占写receipt，不内嵌自身SHA。

封套及API的boundaries**恰六项严格false**：execution_allowed、workflow_connected、human_initial_judgment_saved、ai_enabled、identity_authenticated、source_authenticity_proven。字符串ID非空不归一化；版本/枚举/键集合封闭，整数非bool，SHA完整64位小写hex。P1及store对象保持原协议。

context.store_result须为冻结STORED状态；公开verify得到的store_result须为VERIFIED状态。各按自身常量检查，**其余七键严格一致**，不能直接要求两个不同状态完整相等或任意忽略其他字段。identity/决定/record_fingerprint/manifest SHA与实际snapshots/decision_result、manifest、context、receipt完整闭合。

## 7. 保存、恢复与失败固定顺序

save：轻量参数/路径核验 → 独占scope锁 → 同缓冲读取并核验历史/保留全文件初始读数 → 真实准备32项当前请求 → 调用冻结store.save到event_dir/snapshots → 核验完整返回与六文件真实读数 → 独占写context并读回 → 最后独占写receipt并读回 → 全部必要消费后的最终确认 → 释放自己的锁 → 返回。

store.save在P1通过前不建目标/父目录；借此保持错提交/质量APPROVE等P1拒绝不建event_dir，不能为提前写封套再额外调用P1。进入store创建阶段以后发生错误必须保留现场；新event_dir已创建时只在本事件写独占failure.json。不能覆盖旧event；不得预建既有目标让store拒绝。

最终确认覆盖32个当前来源、全部旧事件八文件字节与初始读数、scope成员集合（只允许本次新增事件和本次锁）、本次八文件与实际待写/读回预期、代码/路径/失败存在性。不能最后又读一个新的摘要/业务对象而不确认。受锁保护的完成封套及最终字节确认是本次提交点；释放锁是协调收尾，不声称解锁之后scope不会追加别的合法事件。

新事件失败诊断恰{failure_version,status,stage,field,reason,exception_chain,boundaries}，版本TASK-024-gate1-failure-1.0，status=BLOCKED/ERROR；field无适用值为null，链包括实际异常及cause/context。failure优先于解析任何半写封套/receipt；写诊断失败保留原错误链并如实报告，不吞掉失败。晚变更即使已有完整store/receipt仍必须失败，本层failure使恢复拒绝；恢复原业务字节不能抹掉已保存失败事实。

verify：只读核验完整scope封套/前缀历史及目标store快照 → 用显式batch_dir及已核验请求ID重新实读当前32材料，精确比较目标record/request/期望 → 末次确认全部消费对象/路径/集合/无failure/无锁 → 返回。当前源改变时，冻结store的快照核验可能仍通过，但本层verify必须拒绝；不得称旧材料APPROVE仍可执行。源路径从显式参数核验，不能跟随封套任意路径读文件。verify不写failure、不修复/迁移历史。

独占字节写采用UTF-8无BOM、canonical JSON+单LF，读回精确长度/SHA/对象；文件字节SHA与规范对象指纹分列。异常映射先绑定cause再写failure。无网络、Excel业务计算、下游核心调用；仅真实冻结prepare和store公开API，核心调用不能用替身成功冒充。

## 8. 最小验收

入口 `.venv\Scripts\python.exe -B tests\test_record_demo_human_gate1.py --out-dir data\human_gate1_decision_tests\task024_<新名>`；先小样/必要负向，局部错误定点修正，最后一次完整本卡入口。不要复制72/117组旧套件，不为每个字段反例重建上游链。

1. 最少新接收样本：正常A、正常B及仅一个币种USD的BLOCKED样本；复用最少独立scope做各场景，不创建DB或宿主链。测试独立复算14代码/32文件/材料与封套指纹，完整返回/原文字段与store/P1真实返回一致；相同纯prepare输入确定性、不预填决定。
2. 真save+verify：正常APPROVE；另scope中BLOCKED HOLD成功、BLOCKED APPROVE由真实P1拒绝；其他批次合法历史存在时可正常追加。测试拟人字段只来自明确登记夹具，框架不代生成人类内容。
3. 重复event、已有APPROVE同批Gate1、错批次/错材料、模拟actor、已有event_dir含空目录、未显式scope、越界及真实junction、占用锁各必要反例；早拒绝的store/P1调用0，P1拒绝前不建事件；旧文件/锁不变。合法HOLD/REJECT前序不能一律拒绝。
4. 历史真实枚举：缺receipt/失败优先/缺六快照之一/未知项/封套identity矛盾、revision缺口或前缀名单漏记录均拒绝；不跳过坏目录、不默认空历史。使用新场景副本，不修改旧证据。scope枚举及每次store.verify/新store.save/P1入口分别计数，不能把所有P1复算称新提交一次。
5. 一个真实源晚变更：先观察最后消费接缝，在真实store.save返回后、封套最终确认前仅给本轮源quality_report追加LF，不更新哈希 → 本次save即拒绝；有效本层failure保存，撤销/恢复源后verify仍拒绝失败事件。另正常记录的当前源改变时只读verify拒绝且不写failure。
6. 新封套真实writer两例：context半写OSError、receipt完整写后sentinel；包装真实独占句柄，不替换整个writer。Error+完整原因链、failure有效、半写/完整现场保留、旧事件字节不变；不重跑冻结store六文件writer历史故障。
7. 接收CLI/内部checker、prepare、store.save/verify、真实P1、本层API/审核helper分列真实观察，完整输入或文件现场/返回/异常+traceback/cause单份保存；守卫下游业务/网络0，生产源及历史只读。程序生成的revision/路径摘要不得冒充人类时间或事件ID。
8. 证据在终审前从真实观察定稿，完整canonical比较、ID/实际入口/完整载荷/磁盘读数闭合，最终台账实际读回；删一条权威登记由同一audit失败。至少一次分离的终审证据缺条目故障应套件非零/FAIL，不覆盖候选/重建期望；不要再设计一套无关通用审核框架。未执行项null/not_executed。

## 9. 保护与升级

实现/测试/指南/回执定稿、局部和完整入口完成后一次最终保护：changed=[]，missing/读取错误/范围外新增0。所有新增按本卡确切文件及实际本轮根逐项登记，不以reviews或gate1目录前缀豁免未知变化。最后仅有限登记身份；错误扫描/过程失败如实计次，旧现场和junction不清理。

新回执给出真实接口/调用次数/历史范围和prefix核对、核心新提交与历史复算分列、32项与14代码新绑定、失败与恢复停点、起点/写后SHA、保护/过程/未执行；自身最终SHA只在交接给出。

若需要改冻结prepare/store/P1/契约/配置/宿主，改变本卡32项/封套/历史/锁/执行边界，或发现任务分类不适用，立即停止受影响处理、保留现场、报告重新定界升级，不扩大本卡自行实施。完成后交GPT；真实业务决定和看板由人类负责。
