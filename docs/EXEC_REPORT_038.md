# TASK-038 执行回执

状态：交付待 Architect 独立验收，不自行 ACCEPTED、不操作看板、不启动下一卡。只准备初判请求；本回执和测试人类文本不批准真实批次。真实批准 null、真实人类独立初判未保存、开发宿主 0008、next/AI=false。

## 1. 依据、冻结与范围

实施依据为 TASK-038_DRAFT.md（SHA 1beefdf889ff3f550290a890df01bdfcf0081bf325f5de379aa437e3dad44002）和 TASK-037 的 ACCEPTED。接受基线为 data/reviews/task037_gpt_20261016_203440/source_hashes_after.json，168367 项，SHA 155f0247e7a62f033c46f919c22925017bc3683d9913cfd1f8875c7c9cbcc75c。实施前核对十四份输入身份，并在 task038_prepare_01 保全允许修改的适配器原字节、Gate 夹具源和两个初判人类字段源。

唯一修改既有文件 scripts/runtime_gate1.py；仅新增本卡测试、指南、本回执及明示 task038_* 自有根。准备器、Gate P1/store、初判 core/store/history、协议/案例、normalizer/SQLite/SQL/事实核心、契约/生效登记/配置、旧测试/指南、宿主/控制器和历史现场均冻结。只读复用 data/batches/task027r1_run_04/batch_normal，未接收新批次。

正式 V1 契约 SHA 174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad；工作簿 SHA 8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341。全部输入身份详见 task038_prepare_01/starting_identity.json；其余旧文件以接受快照核对。

## 2. 实现

新 CODE_MANIFEST_VERSION / REGISTRY_VERSION / RUNTIME_VERSION_028 分别为 TASK-038-code-manifest-1.0 / TASK-038-runtime-registry-1.0 / TASK-038-runtime-gate1-1.0。代码清单恰17项；registry 恰14键，新增两键 initial_judgment_history。域必须既存、正常、位于初判记录根严格后代，安全原相对 POSIX 串与 UTF-8 scope，原路径链先验 reparse 检查，不绑定可增长成员。

Gate1 共享材料物化为38份：原32 + 三份初判代码 + 协议/案例 + 真实已保存 registry 文件。FILE/长度用开始原缓冲，清单与完整材料 FP 闭合；更换域并同步合法 readback 不能保留原 Gate1。旧版本明确拒绝、不迁移。AST 比对确认：仅 build_runtime_registry 新增必填关键字，其余十五个原业务 API 签名不变；新增一个业务 API，总计17个。

唯一新入口 prepare_runtime_initial_judgment_request 的成功外层恰 request/request_sha256。request 六键；materials 十键、expectations 十二键、evidence 七键、boundaries 十键严格 false，保持 TASK-034 协议。事实、登记、契约和两 Gate 的八文件角色取同一开始缓冲的 FILE/长度；record/packet/正文 FP 分列。先固定独立 expectations，再组装候选并完整 canonical 比较；末次确认原字节、路径、集合、failure/锁、历史成员/六文件与静态身份后直接 return。

直接 Gate1 verify/Gate2 verify/facts inspect/history 各一次，完整返回分别与开始对象/FILE 闭合。保留既有只读嵌套核验；不直接调初判核心或任何 save/算法。历史正常成功后，本批已有记录即拒绝 prior_history.records。history 原类型映射，Blocked 加 history. 前缀并保留 reason/reasons/cause；Error 保留 stage/reason/reasons/cause/secondary_errors。失败不写诊断。

## 3. 运行组织、授权例外与接续

最初 task038_run_01 完整开发链及62项检查实际运行，2项失败，退出1；内容审核/字节审核通过。两项是测试预期首报字段不一致：空绑定对象实际定位 initial_judgment_history，保留事实漂移实际定位 facts.artifacts。另在只读自检发现生产映射没有显式保留 history.reasons。

因为修正生产代码会改变运行身份，已明确请求任务卡“只建一条链”的例外，人类原文答复为“允许小修并另建最终链，当前现场保留”。登记在 task038_finalization_01/scope_exception.json。只补 reasons 深拷贝后建立 task038_run_02 这一条最终身份链；run_01 全部保留，不作最终正常证据。两条链各自实际执行五个计算核心一次；不把全卡说成只执行一次。

run_02 的正常业务链、空历史请求及前半组反例完成后，测试把局部缓冲采集函数名 capture 重用成 reader，进入非空历史组前在测试侧抛 TypeError。生产 API 未出错，未再改适配器、未重建链。process_exception.json 完整保留33条 API/690条嵌套观察及当时原代码帧计数；不包含未落盘的旧 checks 或 IO 队列，不声称恢复它们。

修正测试命名并抽取同一剩余历史组，由标准 main 的 --resume-prefix 在新证据容器 task038_run_03 接续同一运行身份。前段观察作为只读来源保全为 prior_segment.source.bin（17361068 B，SHA 013e172e5dc19dd12d5aec8554c98412b4183a2a8243e20ab683ce69d189a952）；新增只读验证检查其完整返回/异常/字段、三时点、独立空请求、38份文件及帧计数闭合，不冒充旧 checks 恢复。旧段与本进程新调用分列。

实际接续命令：

```text
.venv\Scripts\python.exe -B tests\test_runtime_initial_judgment_request.py --out-dir data\runtime_initial_judgment_request_tests\task038_run_03 --resume-prefix data\runtime_initial_judgment_request_tests\task038_run_02
```

结果：92项检查，0失败，退出0；audit_ok/bytes_ok=true，problems=[]、drift=[]、failures=[]。前段33 API/690观察 + 本进程7 API/222观察 = 完整证据40 API/912观察。summary 的 new_process_code_entries 与 prior_segment 分列；aggregate 用于载荷登记闭合，不能解释为接续进程新执行912次。常规完整入口同样使用已修正的共享历史组，但本轮没有再建链重跑常规完整模式。

## 4. 有限验证结果

- 正常空域请求：完整返回与调用前固定的独立空请求相等，八角色 FILE/长度/FP、十false和只读场景闭合。非空域请求同样与独立完整预期相等，并对实际返回/消费引用做无别名与三时点校验。独立验证文件不调用运行层组装或 FP helper。
- 新 profile：17项代码独立复算；registry14、Gate1材料38及真实 registry FILE 绑定闭合。仅改历史域的副本先在 Gate1 前通过真实公开 read；Gate1 保存后，真实 reader 返回副本读数的具名接缝拒绝 context.registry_file_sha256。旧版本按 registry.registry_version 拒绝。None/缺键/unsafe、合成 reparse 元数据控制均拒绝且不建目标。
- 真实返回映射控制：Gate1 non-effective、Gate2 HOLD、facts 完整返回错误分别在对应关系处拒绝；原真实观察与映射替身分列。完整 assembler 候选 False→0、int→float、事实上下文矛盾均在 initial.request 拒绝，没有用 Python 相等代替 canonical。
- 真实最后消费后 fact_packet.json 加 LF：本次 facts.fact_packet.json 拒绝；撤销 wrapper 保留坏字节后 facts.artifacts 仍拒绝；原件/坏字节具名保全后，仅精确恢复该本轮单文件，随后请求成功。未写生产 failure。
- 代码晚变更用本轮源码物理副本的实读缓冲在开始捕获后替换 reader 视图，registry.run_binding.code.file_sha256 拒绝，Gate 核心增量0，原生产源码未改。此项为副本接缝，非物理篡改冻结源码。
- history 的 Blocked/Error 映射分别保留精确字段/阶段、reasons、traceback和完整原因链；Error 的 OSError 是明确受控注入，不称原生业务故障。
- history 成功后追加完整 event2 叶，本次与撤销 wrapper 后都拒绝原空名单；保留新增叶。新的调用先独立固定新名单，再真实逐叶 verify/core 成功后提取。旧源六快照保持原字节，不宣称其旧重复批次反例域整体有效。
- setup 单独调用初判 store.save 一次，使用已登记 event1 与正常请求材料建立合成本批记录。随后 history 两叶真实成功后，本入口拒绝 prior_history.records。前序 FP 矛盾、已声明引用缺失均同步所有直接派生摘要，先经两个真实 core 成功，再由 history 分别定位 record_fingerprint/event_id。坏叶和 failure 优先现场全部保留。

本轮保存的是协议合成测试快照，不是人类本批真实初判。本入口自身未调用 save；它不能复用历史请求覆盖当前域的新状态。

## 5. 计数与观察范围

正常空域单次直接四调用各1。总 Gate1 verify6、Gate2 verify5、load inspect5、screen inspect2、crosscheck inspect1、facts inspect1/render1、Gate store.verify/P1各11、冻结准备器6、history1；初判 verify/core为0。指南在测试前固定该图，实际父关系/原代码帧一致。

最终身份两段完整证据累计：新入口24、history13、初判 store.verify7/core8（含 setup save 的 core1）、初判 setup store.save1；Gate store.save2/verify187/core189；冻结准备器107；normalizer/loader/SQL/crosscheck/facts build各1，仅最终链 setup 执行。完整各层计数以 summary.json 和 local_validation.json 为准，业务 API、嵌套核验与纯核心不混称。

所有912条业务观察的完整参数、真实引用ID、调用前/返回后/API收尾快照及 FP、完整返回或异常链均闭合。前段观察的来源是保留检查点，不算本进程新增调用。I/O 事件 io_events.json 仅覆盖接续进程；前段未落盘 IO 队列不补造、不填计数0。接续真实写/网络/子进程/时钟守卫先经拒绝证明，再在生产窗口执行；其命中为空。隔离源码副本/晚变更的写入由具名测试 wrapper 执行，非生产写入。

独立只读 verify_local.py 校验两份完整正常请求、40 API/912观察、全部引用三时点、197个成功纯核心返回的正文 FP、7项文件台账与当前文件字节；自身新增业务调用0。

## 6. 四个实际 main 控制与收尾

task038_finalization_01/finalize.py controls 启动四个独立新进程，cli_profile.py 执行当前交付测试的真实 main --replay；不执行旧 run/main。结果按 none / candidate-return / ledger-late / checks-late 顺序为0/1/1/1；磁盘 PASS/FAIL/FAIL/FAIL、failures为0/非空/非空/非空；四进程新增业务调用均0，源证据逐文件不变。

candidate-return 只替换候选完整 API 返回，独立定稿预期不刷新。ledger-late 和 checks-late 在真实收尾终端读数边界追加一个 LF，分别命中1；真实末次字节比较支配非零，坏字节保留，不依据注入标志直接判失败、不重建台账掩盖漂移。

正式内容/台账收尾复用已接受短 helper：定稿内存预期→一次写定七载荷→同缓冲磁盘内容审核→台账对象与自身字节→末次八文件原始字节确认→实际退出码。成功后不再读候选构造成功输出。辅助源副本/正常独立预期/控制资料由最终 evidence_identity_before_scan.json 按确切文件分层登记。

## 7. 交付身份与根

scripts/runtime_gate1.py：290568 B，SHA ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a。

tests/test_runtime_initial_judgment_request.py：62539 B，SHA 3b0732b138a31fadba7ec61505ad3216a4828c803da30ef5bb789e7560287f13。

指南与本回执自身写后 SHA/长度在 task038_finalization_01/delivery_identity_before_scan.json 和 delivery.json 登记；不把自身摘要写回自身。

最终证据 data/runtime_initial_judgment_request_tests/task038_run_03；最终前提链 data/runtime/task038_run_02；Gate1/Gate2 分别为 data/human_gate_decision_records/gate1|gate2/task038_run_02；SQLite data/sqlite_tests/task038_run_02；测试历史域 data/human_initial_judgment_records/task038_run_02/bound。完整路径、文件 SHA 与控制结果见 task038_finalization_01 的有限登记。run_01、run_02及预检全部保留，不覆盖旧输出。

## 8. 最终保护与历史事故

内容、代码、测试、指南、回执、控制资料全部定稿后才执行唯一一次全树扫描 finalize.py scan。最终事实以 task038_finalization_01/protection_result.json 为准，本回执不提前填入尚未执行的扫描数字。接受基线168367项；允许既有 changed 仅 runtime_gate1.py。新增先展开为 allowed_new_paths.json 的确切文件集合；仅两条接受快照自身/review_result元数据单列，不用前缀豁免未知文件。扫描后只有限发布本轮 delivery.json，不再次遍历全树。

历史139损失、27恢复、326越界、19命名偏差及TASK-030具名41 B锁逐项核对、单列。未恢复/重建/删除/移动/清理任何历史或探针证据，没有追认越界。

## 9. 过程问题与未执行

准备预检01的测试读守卫只列21个冻结项目件，真实准备器需读23项，导致测试阻断；补充确切名单后预检02通过，未跑业务链。开发run_01两项测试定位预期已更正，另有真实 reasons 漏保留按人类授权修复。最终run_02测试变量重名导致中断，已按上述两段接续披露。一次只读映射探针的命令换行编码错误在写入独立 mapping_check.py 后核对；脚本输出真实 reasons 差异，未调用业务核心。没有在内容未定稿时执行全树扫描。

物理junction为null＋既有权限限制，未重试绕过；本轮合成元数据控制不能替代物理建立。接收器子进程内部核心次数null（本轮未接收）；直接checker CLI为0＋只读复用原接收产物。旧TASK-021—037大套件、额外人类时间正例、真实Gate/真实初判保存、运行层初判save、AI/终判/UI/网络/跨域全局发现均未执行，不填默认0。

任务完成后停止实施，交 Architect 独立验收。测试不批准任何批次，也不表示身份认证、原始业务真实性或审计结论；不实施下一卡。
