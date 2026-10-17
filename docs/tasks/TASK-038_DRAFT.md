# TASK-038：新运行身份与有界历史绑定的只读初判请求

分类C，Architect设计、执行端实施、Architect独立验收。本卡以前置 `data/reviews/task037_gpt_20261016_203440/review_result.json` 正式发布ACCEPTED为生效条件。是合成数据上的建设授权，不批准真实批次。本卡不启动执行会话、不实施下一步保存或AI。

## 1. 前置、冻结身份和允许范围

先读REVIEW_TASK_037及同根review_result/source_hashes_after.json，以该新接受快照确切SHA/项数为基线，再读TASK-034协议§5—7/§10及三个已接受模块相关入口。不得执行旧测试run/main或写旧评审根。

唯一允许修改既有文件 `scripts/runtime_gate1.py`，实施前264105 B / SHA `65946ffd740771c3917297d5d566c147c641004547fbbbb71873d5b53898e78a`。本卡明确允许新运行profile所需的有限清单、登记和Gate1材料绑定变更，以及一个新只读公开入口。其他既有文件冻结，包括全部核心、P1/store、准备器、协议/案例、SQL/schema、契约/生效登记、配置、旧测试/指南、宿主和历史现场；不拆模块、不新增框架/依赖/生产CLI/UI/DB schema或通用许可开关。

冻结初判三件：

- `scripts/build_demo_human_initial_judgment.py`：28927 B / `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`，TASK-035-human-initial-judgment-core-1.1。
- `scripts/store_demo_human_initial_judgment.py`：25787 B / `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`，TASK-036-human-initial-judgment-store-1.1。
- `scripts/inspect_demo_human_initial_judgment_history.py`：15064 B / `7276ddb704d27cec031ca3c2af4122a3c2c890d613bd4cfa90e6454d72000b22`，TASK-037-human-initial-judgment-history-1.0。真实入口 `inspect_human_initial_judgment_history(namespace_dir, *, expectations)`，完整十二键返回。

协议29189 B / SHA `df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe`；案例24844 B / SHA `e02e1f49e16ebff6a3b683e4c76ece6dd81697569e4876d090a4cccb67d07d46`。正式契约V1 SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`；生效登记SHA `042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`。其余冻结身份从接受快照实读。

仅新增 `tests/test_runtime_initial_judgment_request.py`、`docs/RUNTIME_INITIAL_JUDGMENT_REQUEST_GUIDE.md`、`docs/EXEC_REPORT_038.md`；本轮新根限：

- `data/runtime_initial_judgment_request_tests/task038_<轮次>/`。
- `data/runtime/task038_<轮次>/`。
- `data/human_gate_decision_records/gate1/task038_<轮次>/`、gate2同名根。
- `data/sqlite_tests/task038_<轮次>/`。
- `data/human_initial_judgment_records/task038_<轮次>/`，用于本轮显式声明历史域及合成测试叶。

根只是可创建范围，交付必须展开全部确切文件路径，不以目录前缀豁免未知文件。只读复用 `data/batches/task027r1_run_04/batch_normal`，工作簿SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`，不重新接收或改批次。Python一律-B，Windows/PowerShell。不递归删除/移动，不清理锁、探针或失败产物。若需改冻结组件/协议、扩大范围或升级分类，停止该级处理并报告Architect。

## 2. 新运行profile，历史域在Gate1之前绑定

旧十四代码/三十二材料profile及旧凭证保持原件；本卡新运行profile的代码清单恰**十七项**：既有十三份冻结组件、上述三份已接受初判组件、适配器自身。唯一且按relative的UTF-8字节序。三新件必须按上列独立冻结身份实读核对，不能只对同次新读数自比。适配器自身SHA来自本次开始缓冲，不自嵌。

新 `CODE_MANIFEST_VERSION=TASK-038-code-manifest-1.0`、`REGISTRY_VERSION=TASK-038-runtime-registry-1.0`、`RUNTIME_VERSION_028=TASK-038-runtime-gate1-1.0`。其余阶段版本/schema无新增语义处保留。代码六项run_binding结构不变，Gate1/Gate2/事实/初判材料精确共用；各阶段材料摘要仍可不同。

`build_runtime_registry(batch_dir,runtime_dir,*,scope_dir,initial_judgment_history)` 明确新增必填关键字。initial_judgment_history恰 `{namespace_relative,declared_scope}`：安全项目相对POSIX原串、非空合法UTF-8原scope。namespace必须在data/human_initial_judgment_records严格后代，原始链检查先于消段规范化，无链接/reparse，既存正常目录；与运行/Gate/SQLite根无相等或祖先交叠。登记不创建该域、不给人类字段，不枚举全部项目历史。缺失/None按正常函数签名或函数内明确拒绝，不默认域或空历史。

新registry由原十三键加 `initial_judgment_history`，恰十四键；readback仍闭合整个登记对象FP和确切FILE/长度。绑定域路径/scope，不固定会增长的成员名单。登记时实读并核对三新代码和协议/案例，末次确认它们及域原路径/目录属性未变。登记只是技术动作。

**仅把域写进registry/readback不足以防止换域。** 新Gate1材料文件名单恰**三十八项**：原三十二项+三新代码+协议+案例+本运行runtime_registry.json。前三类project项使用 `project/<项目相对路径>`；登记项使用 `runtime/runtime_registry.json`，其FILE/长度取真实已保存登记开始缓冲。材料封闭七键不变，不向冻结Gate纯核心加字段。名单/完整预期双向相等，FP覆盖整个名单。prepare/verify的共享材料构造均据本次已捕获registry原件产生，不能重序列化对象冒充FILE。

这样Gate1记录中的材料名单/指纹与新的历史域绑定闭合；登记和readback同时被改、甚至重新计算它们自身摘要，也不能保留原Gate1批准。Gate2/上游继续核验这个真实Gate1并共享十七项run_binding。旧十三键/十四项登记明确版本拒绝，不自动迁移/补字段/重写凭证，不让旧Gate事件适配新代码。其余十五个原公开API签名不变；行为的必要变化仅是接受新profile、核对该新绑定和拒绝旧身份，不削弱其他前提/锁/失败优先/集合/只读规则。

## 3. 唯一新增公开API

```python
prepare_runtime_initial_judgment_request(
    batch_dir, runtime_dir, request_id, *, scope_dir, event_relative,
    database_path, gate2_event_relative, history_expectations
) -> dict  # 恰 {request, request_sha256}
```

公开API合计十七个。request_id是调用方明确的技术请求原字符串，非空合法UTF-8；不充当人类事件ID。history_expectations语义必需，为TASK-037封闭四键对象，调用前固定。expected_namespace_relative/expected_declared_scope必须与已绑定registry精确相等；不得从调用方另选域、从候选刷新名单、自动切到另一个空域或默认完整性true。

本入口只读，不接受人类submission/actor/event/assessment/reason/time，不生成预填判断或提交模板，不保存请求、初判、索引、failure或日志，不读时钟/随机/网络/子进程。不直接调用初判纯核心或任一save入口，不调用SQL筛查、标准化、装载、复算、事实build或旧模拟初判/宿主入口。已有只读fact inspect内部的一次真实render、Gate核验内部P1/store和history内store.verify/core为允许的既有嵌套核验，须分层计数，不能合并称直接初判调用。

实际直接调用各一次：

1. 当前适配器 `verify_gate1_effective_approval`；完整十一键返回，effective严格true，APPROVE/HUMAN_DECLARED且reasons为空；本批/本事件/契约/材料/六项运行精确闭合。
2. `verify_runtime_gate2_decision`；完整三键record/record_fingerprint/event_relative；完整record为APPROVE/HUMAN_GATE_DECISION、actor_kind=HUMAN_DECLARED，同批/前序Gate1 FP/契约/运行。现有接口没有effective新许可键，不凭空读取或生成它。
3. `inspect_gate2_fact_packet`；完整六键，RT_FACT_PACKET_RECORDED，保留真实Gate2、筛查、十维MATCHED复算及完整事实核验。inspect内部render恰1，不重build。
4. 按固定源码缓冲加载冻结history并真实调用其唯一公开API；namespace取绑定registry，完整十二键返回与本轮开始捕获的成员/各叶六文件/manifest FILE/完整store返回和索引闭合。

已有上游的嵌套公共核验按实际调用图保留，不用“为减少计数”删掉真实核验。实施前在新指南定稿直接与嵌套的预期调用数/父关系；每层原代码对象、完整输入/返回或异常分别观察。加载源码不算业务调用；测试setup与本入口分开。

当前有界历史存在本批任何记录时，拒绝 `prior_history.records`，不再准备首版请求、不选最新/覆盖。尚无人类event时不凭空做事件去重；提交时的event唯一和保存前重新核验留后卡。历史完整性仅TASK-037的声明域现存成员及已声明引用闭合，无法证明无引用记录从未删失，不能自称全历史不可删。

## 4. 固定开始缓冲、独立预期与封闭返回

操作开始捕获批次来源八件、登记二件、Gate1/Gate2事件及快照、load/DB、筛查/复算、事实四件、所有已绑定静态件/SQL，以及声明历史域成员及每叶六件。可有限复用当前capture/confirm/helper，不复制恢复算法。原始路径链和failure/布局优先；对象、长度、FILE来自同一缓冲，FP另列。八个直接绑定角色见协议§5.3，不表示可以略过其余依赖链。

真实Gate返回中的record、正文FP及文件SHA必须与开始decision_result.json完整两键对象闭合；投影不能只信APPROVE或两个相同自报对象。真实fact返回artifacts须与开始四缓冲及上游依赖精确闭合；packet从同一开始缓冲解析，FILE与FP分列。真实history返回须与开始域/叶缓冲闭合，不能末尾重读后改期望。

在组装candidate之前，从本次已核验的独立来源读数固定协议十二键expectations及prior_history；来源/固定时点在观察中登记，不从待验candidate、submission或保存后的新读数反推。候选的完整materials与固定独立预期严格canonical比较，False/0、0/0.0均不同。

成功request恰六键：

- request_version=`TASK-038-human-initial-judgment-request-1.0`。
- status=`RUNTIME_HUMAN_INITIAL_JUDGMENT_REQUEST_PREPARED`。
- materials：完整TASK-034协议十键，materials_version原常量；runtime_version为新TASK-038值；entity从已核验packet取固定业务对象；contract/run来自已核验登记；fact_snapshot完整五键；gate_links两个完整投影；files恰八角色，按项目相对路径UTF-8顺序。materials_fingerprint=FP(顶层删除该键的其余九键)，无自指。
- expectations：完整TASK-034十二键，expected_request_id取技术request_id，历史scope/FP取已核验有界prior_history；其余来自上述固定独立来源。
- evidence：恰七键 `gate1_verification,gate2_verification,fact_verification,history_verification,registry_binding,contract_effective_record,files`。前四保留本次真实完整返回的深拷贝；registry_binding恰 `{registry_version,registry_file_sha256,registry_byte_size,run_binding_sha256,initial_judgment_history}`，来自本次登记缓冲；contract_effective_record恰 `{relative,file_sha256,byte_size}`，核对冻结生效登记原件；files为同缓冲八角色完整list的独立副本。历史返回里的既有人类原文作为已核验旧记录保留，不用于预填当前人类判断。
- boundaries：恰十键 `request_persisted,human_initial_judgment_saved,execution_allowed,next_step_allowed,ai_enabled,workflow_connected,identity_authenticated,source_authenticity_proven,audit_conclusion_formed,final_judgment_recorded`，全严格false。

gate_links按实际Gate record提取：event_id/decision/actor.actor_kind来自record，materials_fingerprint/contract_binding/run_binding来自record.binding；record_fingerprint是完整record FP，record_file_sha256是完整decision_result.json确切FILE，Gate2.prior_gate1_fingerprint来自实际核验前序关系。不要用record FP替换record文件SHA。

先构建完整request及外层 `{request,request_sha256:FP(request)}` 深拷贝，再做最后必要消费后的末次确认：全部依赖原字节、原路径链、failure/锁、固定集合、声明域成员/各叶六件、适配器自身及十七代码/两协议文件，均对本次开始缓冲比较。history API成功后再来的新增/删失/坏字节也须本次拒绝；不重采预期或用新candidate自比，不再调用history/core来刷新来源。确认后直接return。

RuntimeGate1Blocked/RuntimeGate1Error沿用，真实冻结history异常按实际类型映射，Blocked field加 `history.` 前缀并保留reason/reasons/cause；Error保留原stage/reason/cause及次错误，不吞成Blocked或默认空历史。新指南在测试前定稿字段schema顺序/嵌套步骤顺序/失败优先定位；不按字典插入序首报，不用KeyError替代前置存在检查。失败不写任何诊断。

## 5. 有限必要验证与已登记人类夹具

只建立**一条**正常新profile业务前提链：新registry、新夹具Gate1、标准化/SQLite、Gate2、SQL/复算/事实各一次；只读复用上述小样。独立事实预期R01/R02/R03/R04=0/1/0/0，R02超额400000分，仅测试预期，不写算法。后续新入口分支复用本轮链/具名副本，不重复完整历史矩阵或重跑旧套件。代码变更后不得借旧TASK-033登记/凭证凑新成功。

Gate人类原文只读既有已登记合成APPROVE夹具，按接受基线/源登记核对原event/actor/declaration/time/reason，不从初判夹具反造Gate批准。初判合成夹具event1/2分别为 `data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`（1627 B / SHA `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`）及 `data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json`（1728 B / SHA `e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a`）。仅测试、八权限false。新技术批次/请求/路径/域scope可明确构造，不编造人类字段。物理junction继续null+原权限拒绝，不重试绕过。

必要问题族，不追求检查项数：

1. 新registry十四键/代码十七项/Gate1材料三十八项各有独立完整预期；全链共享run_binding。旧十四项登记以明确版本拒绝、旧根不变。只改变registry历史域并同步合法readback的自有反例，先证明登记本身可读，再证明原Gate1当前材料核验拒绝，不把更早坏SHA叫换域控制。注册缺/错历史绑定、unsafe/reparse原链拒绝，未建目标/未发业务调用。
2. 正常空历史请求：完整六键request/两键外层/全部materials、expectations及七键evidence与独立内存预期相等；八角色FILE/长度与同缓冲FP闭合，原输入三时点不变、返回无别名、全部字节/集合未变、所有false准确。新入口禁止算法/保存增量0；允许嵌套调用完整计数/父关系实测，金额/模板原文不改。
3. 非空历史用新自有域复制已接受合成快照，域声明/名单先固定；证明先真实逐叶verify/core成功再提取。错域/scope/名单、failure/已声明引用缺失或FP矛盾、完整候选返回False/0或int/float矛盾均拒绝，输入/文件不写。可在测试setup另行调用冻结store.save一次，以正常请求及登记event1建立**本轮合成同批记录**，明确与生产窗口分列；随后新入口须在history真实成功后拒绝本批第二份准备。不得修改旧记录或假称已保存真实初判。
4. Gate1未effective、Gate2非APPROVE/绑定错、fact failure/坏上下文/错完整返回、历史不闭合均拒绝；优先复用本轮小型自有接缝或反例，不重建许多业务链。至少一例完整候选与固定独立预期矛盾；不能只比摘要/状态。原异常分类/准确field或stage/reason/cause可复现。
5. 在新入口最后必要消费后晚改事实JSON/新增历史叶，本次拒绝；撤销wrapper保留坏现场仍拒绝，只精确恢复本轮单文件原件后成功。坏字节具名保全，不删/移新叶凑成功，不写failure。代码晚变更用本轮副本接缝，在业务核心前拒绝，冻结源码不注入。先证明写/网络/子进程/时钟守卫生效，生产窗口命中0，允许读取仅本链/声明域/冻结组件。
6. 真实公开入口原代码对象、Gate直接/嵌套/P1/store、history/store.verify/初判core、fact inspect/render、禁止SQL/复算/标准化/装载/build/save各分列；完整参数/返回或异常、引用三时点、登记与父调用闭合。setup链和setup初判save单独标注，不把旧观察/replay计成新调用。
7. 复用已验收短观察/收尾helper，只读导入相关定义，不执行旧run/main、不复制通用测试框架。候选完整内容与独立定稿内存预期闭合、台账真实读回、末次原字节确认共同支配CLI退出码/summary/failures。四个实际main新进程replay为0/1/1/1，原代码对象profile证明新增业务调用均0，源证据不变，坏字节保留。

测试入口 `.venv\Scripts\python.exe -B tests\test_runtime_initial_judgment_request.py --out-dir data\runtime_initial_judgment_request_tests\task038_<新名>`，所有输出从未存在。未执行填null+原因，引用旧证据与本轮实际重跑分列；不为补检查数生成新人类时间正例。

## 6. 交付、保护与停止

局部源码/新测试/新指南/回执/观察与四CLI定稿后一次最终全树保护扫描，以TASK-037新接受快照为基线。唯一既有changed为runtime_gate1.py；新missing/读取错误/范围外新增/身份漂移0。新增逐确切路径登记，前次快照自身/review_result两条元数据有限单列；扫描后仅有限确切自身元数据，不反复扫全树或用前缀豁免。

139历史损失、27恢复、326越界、19命名偏差和TASK-03041 B锁逐项保持、继续单列，不追认历史越界。不得恢复/伪造重建/移动/清理历史现场。交付登记适配器/测试/指南/回执的长度SHA、版本/十七代码/三十八材料、完整观察、四CLI/保护/未执行项，交Architect验收后停止。不得自行推进保存初判或下一卡，不操作看板。

固定澄明商贸有限公司、CNY、2026年9月/截至2026-09-30；整数分/原ID/主表与分摊分列、R01—R04仅待核查线索。冻结事实模板原提示及运行层来源说明保持。人类独立初判及原因仍待明确提交，本卡只准备材料，保存时须另卡重新核验当前材料和历史，旧请求不构成放行凭证。D1/D2/D3不授权强认证、真实数据、AI或终判。真实批准null、真实初判未保存、开发宿主0008、next/AI=false；技术验收不批准真实批次。
