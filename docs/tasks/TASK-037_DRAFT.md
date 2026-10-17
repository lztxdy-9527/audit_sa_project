# TASK-037：声明命名域的只读初判历史核验与索引

状态：Architect制定；以前置 `data/reviews/task036r1_gpt_20261016_193749/review_result.json` 为ACCEPTED正式发布为准。分类C，由执行端实施、Architect独立验收。只读层，scope=`DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY`。不保存初判/索引，不接运行层、不做迁移或AI。看板由人类办理。

## 1. 依据、冻结身份与允许范围

先读本卡、REVIEW_TASK_036_R1和同根review_result/新接受快照，再读TASK-034协议§7/§10、当前冻结初判核心和存储模块的相关接口。不得执行旧业务套件或旧评审脚本写旧根。

冻结store：`scripts/store_demo_human_initial_judgment.py`，25787 B / SHA `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`，版本TASK-036-human-initial-judgment-store-1.1。实际接口 `verify_human_initial_judgment_snapshots(record_dir)`，返回完整十一键，成功status=HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED，含四snapshots/完整两键judgment_result/六files/九false边界。新层不能用路径存在或四字段自报替代此真实调用。

冻结core：28927 B / SHA `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`。store当前测试38400 B / SHA `68c802e6ea1872acc67d4021bc1c3119039fa6298b248328a8576c5eefd3c66a`。其余正式契约/生效登记/初判协议/案例身份从新接受基线实读；运行适配器264105 B / SHA `65946ffd740771c3917297d5d566c147c641004547fbbbb71873d5b53898e78a`，十四项运行代码清单/16个运行API/开发宿主0008冻结。本新层不加入当前运行凭证，不改旧manifest适配新版本。

仅允许新增：`scripts/inspect_demo_human_initial_judgment_history.py`、`tests/test_inspect_demo_human_initial_judgment_history.py`、`docs/HUMAN_INITIAL_JUDGMENT_HISTORY_GUIDE.md`、`docs/EXEC_REPORT_037.md`，以及 `data/human_initial_judgment_history_tests/task037_*` 测试/交付根和 `data/human_initial_judgment_records/task037_*` 本轮合成命名域/叶场景根。所有既有文件冻结；新增逐个展开确切路径登记，无目录前缀豁免。不复制通用框架、重构或新依赖，不新增生产CLI/UI/DB。Windows/PowerShell，Python `.venv\Scripts\python.exe -B`。需扩大范围或升级分类时停止该级处理并报告Architect。

## 2. 唯一入口与有限完整性

```python
inspect_human_initial_judgment_history(namespace_dir, *, expectations: dict) -> dict
```

namespace必须显式指定为data/human_initial_judgment_records/严格后代的既存正常目录，代表调用方明确声明的一个历史域；原始路径链检查先于消段规范化，成员无链接/reparse。仅枚举该域的直接子目录作为记录叶，不递归搜索全项目、不按名字猜哪些失败可忽略、不自动切换域或创建缺失根。业务域归属/独立期望来源由未来调用方规定，本卡不把全部技术测试目录当真实业务历史。

expectations恰四键：

- expectations_version=`TASK-037-human-initial-judgment-history-expectations-1.0`。
- expected_namespace_relative：安全项目相对POSIX原字符串，精确等于本次已检查namespace的项目相对路径；不能从候选刷新或静默归一化。
- expected_declared_scope：非空原字符串，作为本域声明，不从叶目录/人类ID推断。
- expected_entries：严格list；每项恰 `{relative,manifest_file_sha256}`。relative为单一安全叶名（不含斜杠/反斜杠/冒号/空段、`.`、`..`、NUL），唯一且按UTF-8字节严格升序；SHA完整64位小写hex。空list仅在该域实际为空时成立。

期望必须在调用前独立固定，测试记录来源；调用发现变化不能重采集预期凑成功。实际域成员集合与expected_entries双向完整相等，根文件/子树层级/未知或缺失叶均拒绝。每个成功候选叶恰六文件、无failure；看到failure须先于六文件/manifest消费拒绝（坏failure也不忽略），不自动清理/补齐/跳过。保存原始坏现场，不声称失败目录是有效历史。

逐叶真正调用冻结store verify**恰一次**，成功后才可提取索引。该层不直接调用纯核心，不调用store save、运行层、Gate/fact/SQL/复算或旧模拟入口；每个成功叶由store内部核心恰1，前提拒绝可能为0，分别实际计数。可复用已冻结store的有限私有路径/组件/解析helper，明确列出名字和源身份，不修改它、不复制新通用恢复框架。

本次返回的declared_complete=true仅表示：当前明确域全部现存成员与固定期望名单闭合、逐份完整快照核验通过且已声明历史引用闭合，末次原件/集合未变。它不证明历史从未删失、不发现域外或未登记记录、不认证人类身份或来源，也不证明旧提交当时已枚举完整历史。禁止把本卡称为全项目/全时间不可删历史、强认证或真实批次批准。

## 3. 从完整快照提取与引用闭合

从每份实际成功verify的完整judgment_result.record提取，不能信任预置索引：

- event_id=record.human_initial_judgment.event_id；batch_id=record.binding.batch_id，保持原字符串。
- record_fingerprint=FP(record)，与完整两键返回和manifest已核验值闭合。
- binding_fingerprint=FP(record.binding)，与完整快照关系闭合。

当前namespace中event_id唯一、batch_id唯一；同批第二份和重复事件拒绝整次结果，不能去重、覆盖或只取最新。候选按叶名单UTF-8序核验；重复事件先于同批重复关系检查，定位第二个叶的对应record字段。输出索引按event_id UTF-8字节严格升序，不改变保存的人类文本、findings、原文件或叶遍历顺序。

每份成功快照的prior_history.declared_scope和record.history_binding.declared_scope必须等于expected_declared_scope。核验完整域后，逐份旧prior_history.records的每个四字段引用都要在本次完整实际索引中找到且四字段规范相等，原列表顺序定位缺失ID/错batch/错record或binding FP。仅比较已有字段，不递归重建历史或按人类/技术时间推断先后；此约束可发现已声明引用指向的缺失/不等旧记录，不证明从未存在无引用删失。index构建失败不返回部分成功。

所有自有schema封闭、严格类型/UTF-8/SHA/列表顺序，canonical规则沿冻结核心，False/0、0/0.0不等同。缺/错字段在消费前精确Blocked，不以KeyError统转拒绝。

## 4. 封闭返回与读数绑定

成功返回恰十二键：`history_version,status,scope,namespace_relative,prior_history,prior_history_fingerprint,inventory,inventory_fingerprint,component_bindings,verified_snapshots,boundaries,note`。

- history_version=`TASK-037-human-initial-judgment-history-1.0`；status=`HUMAN_INITIAL_JUDGMENT_NAMESPACE_INSPECTED`；scope常量如卡首。
- namespace_relative为已核验本次路径，与独立期望精确相等。
- prior_history恰核心协议三键 `{declared_complete:true,declared_scope,records}`；records为实际提取的完整四字段list，prior_history_fingerprint=FP(完整三键对象)，无自指。
- inventory恰 `{namespace_relative,declared_scope,entries}`；entries仍两键manifest FILE条目，由本次实际缓冲读数形成且与固定期望双向相等，inventory_fingerprint=FP(inventory)。不是record FP或当前业务材料FP。
- component_bindings恰store六项组件绑定加history_file_sha256。store六件从当前真实源缓冲核对，store自身须精确为§1的a1b4…；新history自身SHA实读开始缓冲，不自嵌固定位。空域也核对这些冻结身份，不凭空输入true。
- verified_snapshots按叶名单原序，每项恰 `{relative,verification}`；verification是该次实际store完整十一键成功返回的深拷贝，保留STORED_SNAPSHOTS_ONLY及九false，不改其record八false或业务状态。列表不是虚构的缩略四字段证明。
- boundaries恰九键 `workflow_connected/execution_allowed/next_step_allowed/ai_enabled/identity_authenticated/source_authenticity_proven/audit_conclusion_formed/final_judgment_recorded/global_history_completeness_proven`，全严格false。
- note固定：`仅核验本次声明命名域的现存成功快照及已声明历史引用；不证明历史从未删失，不批准执行，不认证身份，不开放AI或终判。`

按叶先排除显见failure/非法布局，再从实际六缓冲获取对象、长度、FILE/FP，固定开始读数；真实store verify完整返回与这些同缓冲对象/六文件元数据绑定，不能各自读两组新数据后自比。manifest FILE来自同一实际缓冲。完整返回深拷贝，在最后必要消费后的末次确认前构建完。

最后核对history自身、store六组件、namespace成员集合、每叶六文件/无failure/子目录，与本次开始字节或真实嵌套核验绑定读数逐项比较；不能重新采集后把新读数当预期。后续新增/删失/变更均本次拒绝，不保存失败、不返回成功。只读层不写文件/日志/失败/索引、不读时钟生成时间、不启网络/子进程；测试调用方在授权证据根保存观察。

异常 `HumanInitialJudgmentHistoryBlocked(field,reason)` 与 `HumanInitialJudgmentHistoryError(stage,reason)` 均reasons=[reason]。冻结store拒绝按实际叶下标前缀保留field/reason并raise from；技术Error保留准确阶段/主说明/cause，不统称Blocked、不吞次错误。全自有诊断field次序在实现前静态定稿于新指南，按schema/叶原序/旧引用原序，不依候选插入序。

## 5. 已登记夹具与必要验证

人类字段只用明确登记：首份event_id="1"夹具 `data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`，1627 B / SHA `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`；本轮人类新提供event_id="2"、其余五项沿首份，登记 `data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json`，1728 B / SHA `e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a`。先保全原字节/来源/允许用途，标签PROTOCOL_TEST_FIXTURE_ONLY放协议之外；不生成第三个人类event或身份/时间/判断。额外闰日/±14正例无需本卡补造。

合成技术batch/request/run/Gate投影/材料可在测试构造期独立定稿，所有本批和M关系闭合；不称实际Gate核验。声明域scope与期望历史FP在调用前固定。正向两记录用不同技术batch、event1/2；第二份历史引用可来自实际store verify第一份完整返回提取并固定的四字段，而不能从待测history候选刷新。用于同批拒绝的两份独立快照可保留明确技术空历史声明，不称保存时已真实完整枚举。所有源SHA与变更字段登记。

必要问题族，不追求数量：

1. 空域/一条/两条正常：完整十二键返回与独立预期、prior_history三键FP、全部真实核验返回及六文件读数一致。空域store verify/core各0；n条成功域verify/core各n，新history公开API每次1。用反序叶名证明索引按event1/2而非叶名排序；原输入三时点、返回无别名、只读字节不变。
2. 重复event（同一登记event1复用两份技术快照）、同batch不同登记event1/2均拒绝；不生成新人类值。完整快照历史scope错、引用event缺失、record/binding FP错均为晚层关系反例，必须先证明该叶实际store verify成功/核心1，不能以更早组件/文件拒绝冒称引用核验。用新场景和独立正确外层绑定隔离。
3. namespace错误/不存在、期望缺失/null/错键/名单乱序或SHA坏型、实际成员缺/多/根文件/嵌套目录、叶failure/半写/错组件/完整返回矛盾均拒绝且全程不写；failure优先于manifest消费，不能跳过失败凑空域。元数据reparse有限控制沿已修原链方法，物理junction继续null+既有权限限制，不重试绕过系统权限。
4. 源组件在store/core前晚变更、namespace新增成员或叶文件在最后消费后晚变更本次拒绝；撤销wrapper保留坏字节仍拒绝、具名保全后仅恢复本轮单文件原件成功。组件注入只用本轮副本/明确接缝，不修改冻结源；不删除/移动旧或新现场来造缺失，缺失场景新目录仅复制剩余文件。
5. 公开history原代码对象、嵌套store verify、再嵌套核心、测试setup store save分别真实计数/完整参数/返回或异常/父调用闭合，不把setup或私有helper混作history调用；同引用三时点。先证明写/网络/子进程/时钟守卫生效，生产窗口命中0。读取范围只本域/冻结组件；其他业务入口0由profile实测，未执行项null+原因。
6. 只读复用已验收短观察/收尾helper，不执行旧run/main或复制通用框架。定稿独立完整预期、候选内容/台账实际读回、末次原始字节确认真实支配main返回码/summary/failures。四个实际main新进程replay为0/1/1/1，新增history/store/core/其他业务调用均由原代码对象profile实测0；源不变、坏字节保留，不刷新预期。

测试入口 `.venv\Scripts\python.exe -B tests\test_inspect_demo_human_initial_judgment_history.py --out-dir data\human_initial_judgment_history_tests\task037_<新名>`；所有输出从未存在。store save仅用于本轮新合成场景准备，明确单独计数，不迁移/修改旧TASK-036记录。无需重跑84项存储或156项纯核心全套、旧Gate/SQL/事实/运行大套件或建立SQLite业务链。

## 6. 保护、交付与停止

局部实现/新测试/新指南/回执/证据定稿后一次最终全树扫描，以本轮TASK-036-R1新接受快照为基线。既有changed=[]、新missing/读取错误/范围外新增/身份漂移0；新增逐确切路径登记，接受快照自身/review_result两条旧元数据有限单列，无目录前缀豁免。扫描后只有限确切自身元数据，不重扫全树。139历史损失、27恢复、326越界、19命名偏差和TASK-03041 B锁及旧失败现场保持，不追认、恢复、重建、移动、清理或递归删除。

回执/delivery登记四件长度/SHA、源组件和人类夹具、全部正常/拒绝/三层观察/末次漂移、四CLI、保护及未执行项；明确当前域完整性和历史删失/真实性限制。交付后停止，交Architect独立验收，不自行继续运行接线或下一任务。

固定业务/金额整数分/原ID/主表与分摊分列/线索非结论保持。D2/D3仅合成建设授权，不批准批次/强认证/真实数据/AI/终判。当前真实批准null、真实初判未保存、开发宿主0008、next/AI=false；本卡未实施，技术历史核验不批准真实批次。
