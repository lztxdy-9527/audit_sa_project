# TASK-036 执行回执

状态：独立快照存储实现与本轮验证交付，待 Architect 独立验收，不自行 ACCEPTED/操作看板。scope=STORED_SNAPSHOTS_ONLY；不接运行层、不发布完整历史索引、不改变真实初判业务状态或AI许可。

## 1. 前置与接续

先核对TASK-036、本卡依据的TASK-035-R1 ACCEPTED评审与review_result，再读取已接受协议/案例、冻结核心及现有Gate存储的有限相关模式。接受基线166390项，SHA `63ba73224065bdcdf53538b58a23d966ab6469aed8cdf7330445846828005948`；TASK-036卡SHA `27ab718fcd318728b8a40cbe3dc6d27a694fac8b724e10d37e222501be45bc79`。

前一准备阶段在人类允许的8%额度条件下停工，保留 `task036_prepare_01` 的13份冻结身份、四份源原字节及十键failure schema。接续时有限实读核对13份冻结源和10份准备载荷均不变；五小时额度工具读数已重置为usedPercent=0，因此本轮继续实施。准备checkpoint保留其历史“尚未实施”状态，未回写冒充当前交付。

仅新增四交付件及授权task036_*测试/记录根；没有修改任何既有组件、指南/回执、配置、契约、任务卡或评审。当前实现身份：

- `scripts/store_demo_human_initial_judgment.py`：25318 B / `ff25a5b5d82b76ca17d2edd745f287b9b816ba684d44ece83023109b5e6c194c`。
- `tests/test_store_demo_human_initial_judgment.py`：32446 B / `77182f1f509a4a0ab9e62b3840ab568589a0a16fbb93d825d996c8a8f6f2974f`。
- `docs/HUMAN_INITIAL_JUDGMENT_STORE_GUIDE.md`：7305 B / `d6e98f8116b0d5df2b3a646490ea8f65490836f7162dfd4bbb407b33d594c450`。
- 本新回执 `docs/EXEC_REPORT_036.md` 的完整长度/SHA外置登记于同轮delivery.json，不自嵌摘要。

## 2. 组件与保存/核验语义

实现 `TASK-036-human-initial-judgment-store-1.0`，公开业务API仅save_human_initial_judgment_snapshots与verify_human_initial_judgment_snapshots。out_dir为必需关键字参数；生产无CLI、新依赖、UI、DB或业务接线。AST核对仅十项标准库导入。

成功六文件：expectations/judgment_result/materials/prior_history/submission/manifest.json，无子目录或其他成员；每份canonical UTF-8加单LF、无BOM。manifest九键，component_bindings六项，fingerprints七项，payloads五项四键条目；长度为严格int，FILE与对象FP分列，自身manifest文件摘要不自嵌。技术时间为程序生成UTC秒精度，与人类decided_at_raw分开。返回十一键，含独立深拷贝四snapshots、完整两键judgment_result、六项实际files及九项严格false存储边界。

save在路径/组件前提后深拷贝四输入，不先canonical非法输入；从本次绑定核心源缓冲compile/exec加载真实冻结1.1核心，核心前复核组件字节，恰调用一次。核心拒绝保留精确field/reason和cause且不建叶；核心Error保留internal等原stage/说明/cause。合法输入与独立契约声明再闭合后建立从未存在叶目录、用真实xb句柄独占写、逐件按writer缓冲读回，manifest最后写。

verify先原始路径链/正常文件检查及failure优先，再固定六文件同缓冲解析、长度/SHA/对象FP；封闭schema/身份/组件/全部内层指纹闭合后恰一次真实核心复算，比较完整返回，不能仅比自报摘要。verify不调用save/上游、不读时钟造新值、不写任何文件。材料清单路径仅为快照数据，不实读业务材料；prior_history是传入有界声明，不声称本组件已完整枚举历史或认证身份。

完整成功返回在末次确认前构建，随后消费输入复测，最后有界实读六组件、六文件、目录集合/无failure，比较本次起始capture或writer原缓冲，结束后直接返回已构造对象；不在最后确认后解析/重读候选或刷新预期。

冻结核心28927 B / `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`；协议/案例/正式契约/生效登记五外部身份与卡一致。自身存储源SHA按操作实读，不缓存跨调用读数。十四项运行代码清单、16个运行API与宿主均未改；本组件未纳入当前运行凭证。原核心record八false、VALIDATED、note和协议版本原样保留，persisted不改true。

## 3. failure schema及真实故障

实施前静态登记见 `task036_prepare_01/failure_schema.json`，新指南同步封闭十键：failure_version/scope/identity/stage/classification/field/reason/exception_type/cause_chain/technical_registration。版本TASK-036-human-initial-judgment-store-failure-1.0，分类仅BLOCKED/ERROR；BLOCKED精确field、ERROR null。identity为本次已验证三原ID；cause_chain保留实际根异常及cause优先/context顺序，技术失败时间单列。

实际独占句柄半写反例：只包装真实Path.open产生的xb句柄，真实写入expectations缓冲一半后flush并抛OSError，生产writer except映射HumanInitialJudgmentStoreError(stage=write.expectations.json)，原因链含真实OSError，半字节保留；有效failure恰十键。verify在半写/缺manifest并存下先拒绝failure，核心0、目录字节不变。writer命中/模式/实际长度见writer_control.json，未替换整个writer。

另一个新叶实际半写主错误后，failure真实独占句柄创建并在写入前抛第二个OSError：主stage/原cause仍可见，secondary_errors及传播说明包含诊断写失败，failure保留0字节，不重试、不覆盖；verify在此坏failure优先拒绝，核心0。额外failure=[]也先字段级拒绝，未消费成功manifest或调用核心。

## 4. 人类夹具与实际业务验证

源原字节/身份保全在定稿测试根，完整来源：

- `data/human_initial_judgment_tests/task035_r1_run_02/technical_base.json`：45094 B / `4757b9cc7a4096ce8ef96fba40c08b001713861ba339fc9da56396c3e4093730`。
- `data/human_initial_judgment_tests/task035_setup_01/human_fixture_supplement_02.json`：926 B / `36dcbeb2ff2ebf0ded07608df63008052ce67cf53e6991950a7f9f3a6e0ac2d7`。
- `data/human_initial_judgment_tests/task035_setup_01/human_fixture_supplement_03.json`：895 B / `3ff0a6cc844643a92ca5b2438d6df2bc6d1be260f19eb6ad8e21a162eccb8424`。
- `data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`：1627 B / `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`。

四输入技术基样从已接受TASK-035-R1材料只读复用，首份人类六项原字段、补充“暂不能判断/原始凭证缺失”、人类明确秒精度+08:00时间和指令样式原文均来自既有独立登记。技术材料/Gate/历史投影明确为PROTOCOL_TEST_FIXTURE_ONLY，不冒充实际Gate批准或当前完整历史。指令文字只被保存为数据，未生成新的人类身份/事件/时间/判断、未执行指令。

定稿实际命令：

```powershell
.venv\Scripts\python.exe -B tests\test_store_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_store_tests\task036_run_03
```

结果：68项检查/0失败，真实顶层0/PASS/空failures，audit_ok/bytes_ok=true，problems/drift=[]。正常save与verify各核心1；完整十一键返回及六份确切字节由测试依据事先固定四输入、独立核心记录构造、实际技术时间函数返回观察和独立实读源字节构造核对，不调用生产摘要helper建预期。

有限问题族均留完整实际输入/返回或异常证据：

- 核心B1 bytes、错请求、history=None三例各核心1、精确Blocked/cause，叶未建；受控真实核心内部序列化ValueError映射StoreError/internal，核心1且叶未建。
- 两个独立临时组件副本：真实load返回后、核心前末次组件复核之前追加LF，分别core/contract身份本次拒绝、核心0、叶未建；生产源字节未改。precore_controls.json分列实际测试注入。
- 根自身/越界/既有空/成功/失败目录均拒绝且原件不变。真实junction创建命令实际退出1、stderr为Access is denied，未产生reparse路径，物理链接反例count=null+限制，不声称动态通过。
- 六件缺/多/子目录、长度同值float、false→0、哈希尾LF、FILE↔FP、身份/组件矛盾均可定位拒绝，verify候选逐字节不变。
- 候选judgment_result改reason并同步record FP、manifest内部FP及payload字节SHA/长度/对象FP，真实核心仍恰1并按完整两键结果拒绝，非摘要自比。
- 最后真实构造返回之后改judgment_result LF，verify本次精确拒绝；保留坏字节再次verify仍拒绝、无failure；坏原文具名保全，仅本轮自建单文件精确恢复后verify成功。保存同接缝改submission LF，本次拒绝并留十键failure，未返回成功。

## 5. 观察、守卫及来源范围

定稿公开API34=save17+verify17，按真实原函数代码对象独立计数；嵌套核心14与完整条目/唯一ID/所属父调用/实际增量闭合，两层不强求相等。API返回5/Blocked26/Error3；核心返回10/Blocked3/Error1。十份成功核心返回再由局部核验端按协议独立重建，完整规范相等。

每次公开参数完整登记；save的原四输入和核心实际消费四引用分别在进入前、立即返回/异常后、所属API收尾重新取完整快照/FP/id。verify路径有界场景也三时点登记，core的真实解析输入三时点闭合。save的out_dir标为输出角色，不冒称已有输入文件；verify记录目录为输入角色。原始native返回深层修改不影响那次实际调用输入或保存字节，不以调用框架的返回副本证明无别名。异常完整保留field/stage/reasons/traceback/cause/context及次错误。

实际I/O观察按父call_id归属，生产读取397次、写入29次；所有verify调用写事件0。网络/子进程/verify时钟三个真实探测先被拒，生产守卫命中0，其他业务入口命中0。测试自身夹具读取/证据写入不在生产guard窗口。组件/晚变更故意写入通过保留的真实io.open作用于本轮明确目标，单列TEST_CONTROL_INJECTION，避免把测试动作误判为生产写权限；没有放宽生产I/O根或verify只读守卫。

读取现有小型观察/短收尾helper时没有执行其旧run/main或纯核心156项。主要七项载荷实际同缓冲台账审核，完整内容预期在所有观察定稿后、写候选前独立冻结；附加来源/探针原文/IO观察/独立正常预期另纳入本轮有限字节身份清单，不把这些外围文件冒称由主要台账自身覆盖。

## 6. 四个实际main与停止结论

`task036_finalization_03/verify_local.py`局部核验定稿AST/完整观察/阶段来源/输入三时点/父调用/七项台账，并执行四个新进程的当前交付main（cli_profile.py → runpy）：normal/candidate-return/ledger-late/checks-late实际退出0/1/1/1，对应磁盘PASS/FAIL/FAIL/FAIL及空/非空failures。

台账/checks两个晚漂移在语义审核后、末次原始字节循环中各真实命中1、只加1个LF；完整候选返回替换由独立定稿观察检出。源task036_run_03全部文件前后SHA不变。逐进程原项目scripts公共函数代码帧profile，新增save/verify/核心及其他业务调用全部实测0，旧观察数不冒充本轮新调用。argv/stdout/stderr/profile/字节变化见closure_controls.json；坏字节在新根保留，不回填候选、不重建独立预期，不依靠注入标志硬判退出。

## 7. 保护与最终登记

代码/测试/指南/本文及局部证据定稿后，由同根finalize.py prepare固定四交付和全部自有证据身份，再执行唯一一次全树scan。以166390新接受基线核查既有changed=[]、新missing/读取错误/未知新增/交付漂移0；新增先将四路径与22个本轮具名根展开确切文件，不用目录前缀兜底。接受快照自身及review_result两条旧元数据确切单列。

本文不预填尚未得到的全树扫描数字；实测protection_result.json为权威，仅其scope_compliant=true且有限身份复核通过后发布delivery.json，其中登记完整四件长度/SHA、实际保护数量和调用统计。扫描后不改实现/本文，不重扫项目，仅有限发布自身元数据。

139历史损失独立于本轮missing；27恢复、326越界、19偏差、TASK-030具名41B锁及全部旧失败现场保持，不追认、恢复、重建、移动或清理。未递归删除/移动/清理任何探针树。

## 8. 过程与未执行项

过程根均具名保留、未覆盖旧输出：dev_01为60项/5失败（组件测试注入被生产写guard拦截），并发现“缺文件”场景同时产生未知文件；仅在该新场景单文件rename过，旧证据未动，后改为从新目录仅复制五件以隔离缺失，不以未知项遮蔽。dev_02为66项/0失败；随后补强真实public立即返回点、实际输入无别名和完整十一键独立预期，run_01为68项/0失败；再补严格verify写守卫/父调用I/O归属后，run_02为68项/4失败，是新的只读guard正确拦截测试晚变更写入，使该故意控制未执行。最终将测试注入与生产I/O明确分列，run_03为68项/0失败。

早期辅助脚本生成出现PowerShell引用错误，Python未成功执行；改为本轮文件脚本。finalization_02局部核验因run_02实际FAIL而拒绝继续，未生成四CLI结果；finalization_01的四控制只作过程证据，最终四控制为finalization_03。回执初稿的局部时序措辞在首次全树扫描前已更正，初稿及先前两份交付前身份清单原字节具名保留，不改业务观察或台账。上述不是生产实现返修；生产源定稿后未因这些测试问题改变。测试源和新指南修改仅限本卡允许的新文件。

五个业务测试轮次真实API合计167、嵌套核心合计69，按每轮分列，不混成定稿34/14。准备阶段没有业务调用；最终四replay只实测0新调用。无需重跑纯核心156项、旧Gate/运行/SQL/事实大套件或重建接收/SQLite。

物理reparse反例、额外合法闰日/±14人类正例继续null+真实原因；保存全局历史发现、运行Gate/fact实调用、真实初判业务保存、AI/终判、0009均null+范围外原因，不能由replay的0推断其正确性。正式V1仍有效；本卡仅技术物理快照，真实批准null、真实初判未保存、开发宿主0008、next/AI=false。交Architect独立验收后停止，不自行推进下一任务或看板done。
