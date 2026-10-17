# TASK-039 执行回执：运行层初判保存/恢复协议与符号案例

日期：2026-10-17。交付状态：文档及有限静态核对交Architect独立验收，**未宣布架构验收通过**。未操作看板，未制定或实施下一卡。

## 1. 授权与起点

唯一实施依据为docs/tasks/TASK-039_DRAFT.md，SHA c8c82be1b63652abacc2993f95504f261de866d19247a02da333bc57f39c2625。范围C：只新增两份协议/案例、一份有限静态checker及本回执，在task039_run_03新证据根保存定稿静态/交付/保护产物，task039_run_01/02仅保留本轮过程静态证据。所有既有文件冻结。

已实读REVIEW_TASK_038及其review_result（ACCEPTED）、接受快照、TASK-034协议§5—10、TASK-038任务与额外最终链的人类授权补充、现行适配器相关准备/绑定分支、冻结core/store/history相关接口。未加载全部旧会话，未执行旧run/main。

接受基线：data/reviews/task038_gpt_20261017_003401/source_hashes_after.json，168728项，SHA e841d1caa03c0445246db76148551175cfa7ea2522fe21d1c5dd954d4d40dcb9。它是本卡保护起点，不是本卡的新接受声明。快照自身与同根review_result两项在快照外，最终扫描按确切路径单列。

九份关键身份经实际文件读取与该基线逐项交叉一致：runtime_gate1.py、初判core/store/history、正式契约、生效记录、TASK-034协议、event1/event2夹具登记。适配器仍290568 B / ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a / TASK-038-runtime-gate1-1.0。实际SHA来源与长度详见reference_registry.json，不从本轮候选文档建立冻结预期。

## 2. 新增交付

四个文件均为本卡新增，未修改任何现有实现、测试、指南或证据：

- docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md：32071 B，SHA 5091060d774eda05efd429010543220d9e7d25dd2777e0fb92f00ad68ed0634e。
- docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_CASES_V1_DRAFT.md：21907 B，SHA 1c69957c8476711819e8a290a6ad0b9d5936b3479ab6bf959c5dbba15b28f8f5。
- tests/check_runtime_initial_judgment_recording_protocol.py：22135 B，SHA 500c520932c0efa9939e4d55142c7fb2fbe6e42f232a3f2d6d8dbd115257cab3。
- docs/EXEC_REPORT_039.md：本回执不内嵌自身SHA；定稿后的长度/SHA与其他三件一同写入delivery_identities.json及delivery.json。

只使用标准库。checker读文本/JSON/AST/确切文件字节，不导入、加载或调用业务模块。其输出目录限定在本卡静态证据根内；不覆盖非空旧目录，无递归清理。保护脚本为本卡证据文件，不属于新的生产组件或测试框架。

## 3. 协议定稿要点（未实施）

两个拟定未来入口完全沿任务卡参数名及关键字边界：save_runtime_initial_judgment / verify_runtime_initial_judgment。当前runtime中这两个函数不存在。成功返回固定十二键；三份运行封装started/context/receipt分别七/十/八键；失败十一键；锁五键；运行权限九项全false。原核心九键record和八项false边界、原store十一键完整返回及六件叶、原history十二键返回保持不变。固定版本/状态/NOTE及机器键集合见协议§9。

输出分两处：冻结store的历史直接叶恰六件；运行封装位于登记同级<登记叶名>.initial，不能把context/receipt加入历史叶。声明域共用一把同级技术锁，按真实独占句柄/文件身份/本次缓冲核对，保持至末次确认；只允许成功时释放确证自锁，不按路径或相同内容盲删。失败保留已出现现场，不承诺两个输出根原子。

保存先在锁内真实取得本次独立当前请求及完整旧历史H0/P0，再只调冻结store.save一次（内部核心构建一次），不预调核心。store返回必须绑定该次manifest FILE、六缓冲/FP及完整对象。保存后独立E1仅取旧名单加该次目标manifest FILE，真实history核验n+1叶；新增自身不回写旧P0/expectations。候选结果先构造和审核，再以本次开始/本次writer缓冲进行末端原字节、路径、集合、failure、输入引用及锁身份确认，随后仅释放自锁并直接return。

恢复先完整核验当前域（含自身），从真实history的完整store返回选择目标，避免重复验证目标核心。当前域可增加其他批次合法记录；旧引用四字段及旧叶字节仍须精确闭合。不得以“当前域减自身”回造旧快照。窄私有共享分支核当前Gate/fact/registry/材料，不能直接公开prepare误拒自身，也不公开skip/force等开关。当前材料和运行代码身份仍须一致，不能迁移旧凭证。

正常未来调用公式：保存前n叶，初判store.verify=2n+1、初判core=2n+2（构建1+核验2n+1）；恢复当前m叶，初判verify/core各m。两种正常路径沿TASK-038既有Gate/fact嵌套图，不增额外Gate复核。checker只静态计算n=0/2、m=1/3并交叉读取旧图，**不是新核心调用计数**。提前失败不能套正常公式。

FILE只指确切文件字节；FP只指约定canonical对象；两者名称/用途及本次缓冲来源明确。False/0、0/0.0必须不等。受控候选/台账/末次字节FAIL支配最外层成功结论；已有主异常不被诊断时钟/写诊断故障顶替。运行层failure不新增技术时间字段，冻结store的既有技术时间次故障原链保留。

## 4. 符号案例与人类字段

43个唯一连续RC-01—RC-43，每例八栏：编号、问题族、先前已满足条件、独立预期来源/时点、变更、结果字段或阶段、写入限制、未来调用预期。覆盖正常/零线索/暂不能判断/可选列表、形状和严格类型、当前Gate/事实/来源漂移、域/scope/名单/重复关系、同域并发/不同运行共域、坏锁/替代件/原链、真实句柄半写、failure优先、部分成功、诊断故障、保存后自身、末次变化、恢复自身/后来其他批次/旧引用、只读边界以及外层失败支配。

只引用H_EVENT/H_ACTOR/H_DECLARATION/H_TIME/H_ASSESSMENT/H_REASON；TECH_*为技术符号。没有可提交的预填人类payload，不生成姓名、事件、时间、assessment/reason或批准值。event1/event2登记只核文件来源SHA，未拿它们运行业务。本卡未建立新profile、运行登记、Gate事件、初判记录、业务批次或SQLite。

## 5. 有限静态实际核对

局部命令：

```text
.venv\Scripts\python.exe -B tests\check_runtime_initial_judgment_recording_protocol.py --check-only
```

首轮91/91 PASS，补入与已接受TASK-038旧调用图文件的实际SHA/字段交叉后92/92 PASS，均退出0。随后澄清冻结入口简称、将静态AST/JSON解析改为复用取摘要的同一缓冲，机器键集合未变；第一次落盘的run_01保留为过程证据，不回写。定稿完整静态命令：

```text
.venv\Scripts\python.exe -B tests\check_runtime_initial_judgment_recording_protocol.py --out-dir data\runtime_initial_judgment_recording_protocol_checks\task039_run_03
```

定稿实测结果以同根summary.json/checks.json为准；每条明确scope=STATIC_ONLY。校验包括：接受基线与任务身份、冻结SHA、25组新schema计数/唯一/顺序、TASK-034机器块与真实核心AST、store/history真实完整返回/六文件/四字段索引、拟定签名及当前不存在、固定S/V顺序、调用公式、43例完整/连续、人类符号及未执行标识、关键设计条款锚点、checker标准库导入限定。

定稿证据均在data/runtime_initial_judgment_recording_protocol_checks/task039_run_03：checks.json、summary.json、schema_comparison.json、reference_registry.json、delivery_identities.json。此核对证明有限文本/结构/摘要一致；条款锚点检查不代替Architect语义评审，也不证明未来物理句柄、并发或实现行为。无默认业务PASS/调用0填充。

## 6. 最终保护安排与判据

本回执/正文/checker/静态证据定稿后，仅执行一次新的finalize_task039.py全树扫描；不把有限读文件或局部check-only计作树扫描。扫描根层排除与接受快照相同的.venv/.git/__pycache__，其余逐文件实读。全树raw结果保存在protection_result.json；全部新增由本卡四文件、本轮明确根中逐项展开的确切清单及两项接受元数据组成，prefix_exemption_used=false。先固定新增清单与交付SHA，不从未知候选扩大允许根。

成功判据：既有changed=[]，新missing/read_errors/unknown_added/identity_drift=[]；139项历史损失仍缺失且单列，27恢复件/326越界件/19命名偏差/TASK-030具名41 B锁与基线或独立已登记SHA相同，TASK-038旧开发/最终/失败现场通过整体基线保持。任何偏差保留结果并停止，不重跑全树或追认。

本回执在扫描前定稿，**不预填尚未取得的扫描结果**。扫描后仅有限登记本轮protection_result/delivery等自身元数据；最终扫描数字与四件最终身份在delivery.json，不回写本回执迎合结果、不改旧证据。

## 7. 未执行与过程记录

动态保存、恢复、并发、真实句柄/junction、history/store/core/Gate业务、标准化/SQL/复算/事实build、真实数据、认证、AI/终判全部count=null，原因是本卡仅文档/静态且未来接口未实施。旧TASK-038图/评审/授权及TASK-034/036夹具只是只读引用，未重跑。

有限只读侦察两处命令错误如实记录：一次按不存在的旧脚本名查找；一次读取事故登记时对整数remaining_missing尝试len，进程报TypeError。均只读、未更改文件；改为读取实际存在的有限文件及正确列表字段后继续。checker局部两轮均通过。run_01落盘后有限复核发现源码二次读取，已小修checker；run_02先放保护脚本再运行checker，被非空输出目录规则拒绝（1，无静态文件落盘），该脚本原样保留不执行。最终改为先在全新run_03生成静态证据，再放保护脚本。所有过程根保留；没有执行动态探针或提前全树扫描。未做递归删除/移动、清理旧证据/锁/探针，未操作Git/安装依赖。

## 8. 停止与状态

本卡交付后停止实施，交Architect独立验收；未来运行层保存/恢复须另卡，新增代码身份须用新登记及新合成Gate前提链，不复用旧凭证适配新代码。看板done与真实业务判断仍由人类作出。

正式契约/D1/D2/D3及技术材料不批准批次。真实批准null，真实初判未保存，开发宿主0008，next/AI=false；线索不是损失/舞弊/审计结论。本卡不改变上述状态。
