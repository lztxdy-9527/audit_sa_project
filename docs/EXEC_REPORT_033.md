# TASK-033 执行回执：冻结事实底稿接线与只读恢复

日期2026-10-16，北京时间。完成实施与本卡交付，待Architect独立验收；不自行宣称ACCEPTED或批准任何批次。未操作看板、未标done、未制定下一任务。

## 1. 实施依据与起点

任务卡docs/tasks/TASK-033_DRAFT.md SHA `7549975195f77ac4a4259d40713f040b03530dca5e1e562176bf5e0c081cee21`。实读TASK-032评审/ACCEPTED review_result，接受基线为data/reviews/task032_gpt_20261016_030543/source_hashes_after.json，165366项，SHA `002f0477e7a6d98273c8591c9f4537d8770e26c595f94398094d4e4814eba9c7`。

原runtime为234725 B / `5ad8b95a196213105ec7e1dc1058d22e7790ac0292b5a77e8d641d29a82902d0`，修改前确切原字节保全到data/runtime_fact_packet_tests/task033_setup_01/runtime_gate1_before.py，starting_identity.json同时核对任务卡/冻结展示核心/旧测试/基线。未找到适用AGENTS.md，未加载全历史回执。

仅修改scripts/runtime_gate1.py，新增本卡测试/指南/回执与授权task033新根；旧测试/指南/全部核心/P1/store/准备器/SQL/schema/契约/登记/配置/开发宿主/控制器/旧证据冻结。不安装、不重接收、不联网、不初始化Git、不调用子Agent。

## 2. 最终身份和接口兼容

- scripts/runtime_gate1.py：258365 B，SHA `1218244728192d8d0d8ef85f4850b66e656e6891d3708e455f78c1691967a10e`，版本TASK-033-runtime-gate1-1.0。
- tests/test_runtime_fact_packet.py：21685 B，SHA `af647a42f1ec655fe974a313498557d28ed53a485645e1090a7308b5569de579`。
- docs/RUNTIME_FACT_PACKET_GUIDE.md与本回执写后长度/完整SHA登记在task033_finalization_01/delivery_identity_before_scan.json及扫描后有限发布delivery.json；不内嵌回执自身摘要。

AST对照原字节：原十四公开API签名均不变，唯一变动旧函数定义为_call_frozen_entry增加实际FactPacketBlocked识别，旧映射保持。新增run_gate2_fact_packet/inspect_gate2_fact_packet两个接口，无重复定义、模块拆分、CLI、新框架、通用许可或跳过核验开关。清单仍十四项、Gate1材料仍三十二项、共享run_binding完整不变。

## 3. 核心调用、来源及展示协议

实际调用已验收inspect_gate2_rule_crosscheck并要求RT_RULE_CROSSCHECK_RECORDED/完整MATCHED，保留真实筛查与两Gate核验。复用已有capture/confirm，固定起始来源八件/登记二件/两Gate各八件/load四件/DB/screen三件/crosscheck三件及静态/SQL；三个输入只由原缓冲解析，上游公共返回artifacts、文件SHA/规范指纹、DB、登记与Gate决定逐项闭合。

展示核心54548 B / `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`独立SHA加载；run仅一次build_fact_packet(三个内存对象)。调用前、返回后及成功API收尾检查同引用指纹；观察器另保存完整输入/ID/三时点。原三键返回与packet规范指纹/Markdown字节闭合，不额外render、不传DB/路径、不重新组装事实或模板。

inspect仅一次真实render_markdown(packet)，纯展示核对，完整UTF-8返回与起始Markdown字节相等，同引用返回后/API收尾不变；build/renderer原代码对象分列。inspect没有build/复算/SQL/标准化/装载/决定保存，P1/store只读前序验证仍由已有Gate核验执行。

独占新.facts叶，正常四件started/packet.json/packet.md/artifacts，artifacts最后写。JSON canonical UTF-8+单LF；Markdown原字符串UTF-8不追加LF。每件writer读回与本次缓冲精确比较。started九键/bindings十三键/runtime_context四键；artifacts十键/DB三键，SHA/对象指纹/长度分列；返回六键与六项严格false边界。封闭packet十二键、实体/版本/边界/来源/上游版本/DB/summary计数/金额/卡片来源/上下文记录/固定标签与提示均核验，不重算算法。

全部语义、渲染、真实引用收尾及返回对象构造后，仅以起始或writer读数有界复确认全部来源/静态/事件/load/DB/screen/crosscheck/本层字节、集合、failure/锁/reparse；之后直接返回，不读候选产生成功。

## 4. 冻结历史提示与正式V1

原BANNER/LIMITS及Markdown中的“未实施正式契约与批准控制”等开发模板原文保持不变。started.runtime_context另列contract_version=V1、正式契约文件SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`、core_notice_scope=FROZEN_DEVELOPMENT_TEMPLATE、卡上固定notice全文。实际契约文件与当批本地Gate记录由运行层核验；原提示不表示正式V1无效，夹具决定也不批准真实批次。

同理packet中“展示层未读取DB”说明指纯核心；适配器独立实读复测DB，分层表述，不静默替换原文。G1.original_notice_and_context实测原banner/limits/Markdown包含原提示，runtime_context四项精确一致。

## 5. 定稿目标验证

实际命令：

```text
.venv\Scripts\python.exe -B tests\test_runtime_fact_packet.py --out-dir data\runtime_fact_packet_tests\task033_run_02
```

20项检查全通过，0/PASS/failures=[]，audit_ok/bytes_ok=true、problems/drift为空、ledger_source_same_buffer=true。同根api_records/core_records/expected_observations/checks/failures/summary/file_ledger/audit_failure与具名原件/坏字节齐备。

正常C06b仅一条完整链：build恰1次、内部renderer恰1次；正常inspect另一次renderer，六键返回规范等值、四文件完整。packet33390 B与真实返回packet canonical+LF严格相等，Markdown6063 B与真实字符串UTF-8严格相等，packet指纹一致；三输入及renderer packet三时点ID/完整快照/规范指纹不变。R01/R02/R03/R04=0/1/0/0、R02=400000分；上游/DB前后不变，真实只读写盘/网络/子进程守卫无命中。

最小前提反例：未产生复算时facts拒绝crosscheck_dir，错Gate2事件拒绝；重复及已有空输出拒绝facts_dir，build0、未新建成功输出。空输出只测路径前提，未冒充完整业务链。

晚变更：包装真实上游crosscheck inspect，返回原对象后给本轮DB追加LF，命中1；本次Blocked(runtime.sqlite3)、build0、facts未建。坏DB保全后仅精确恢复本轮原件。无注入先观察本层inspect最后语义字段facts.artifacts，在真实helper返回后给Markdown加LF，命中1；当次Blocked(facts.fact_packet.md)。撤销wrapper留变更仍拒绝，保全后只恢复本轮原Markdown即成功；inspect不写failure，上游始终不变。

展示关系：Markdown“## 1. 总览”改单处为“## 1. 修改总览”，并同步artifacts的Markdown文件SHA/长度（6063→6069 B）；inspect实际调用renderer一次后拒绝facts.markdown.rendered_bytes，build0，证明不是只信外层摘要。bad Markdown/artifacts具名保全，原件精确恢复。

严格类型：packet.next_step_allowed=false改整数0，同步packet文件SHA/规范指纹及artifacts，仍拒绝facts.packet.next_step_allowed，renderer0；不被Python False==0放过。追加结构控制：只删展示payable.record_id、同步外层摘要，Blocked字段精确为facts.packet.findings[0].context.payable.record_id，renderer0，无原生KeyError泄漏。两个坏候选均保存后只恢复本轮原packet/artifacts。

真实半写：只为本项新建一条half_artifacts必要前提链；真实生产writer的open(xb)句柄写入1224/2448 B后抛OSError，命中1，映射RuntimeGate1Error(write.facts.artifacts.json)。六键ERROR诊断含原OSError原因链，半写及其他已写三件保留；后续inspect先报告facts.failure、不解析半写artifacts、build/render0、目录字节不变。

两实际冻结异常类为私有helper控制：FactPacketBlocked在build_fact_packet调用位、FactPacketError在render_markdown调用位各注入一次，映射/真实cause类/两项reasons完整。它们不是实际构建/renderer发现业务错误，原函数code增量0；renderer错误来源和traceback明确是测试controlled wrapper。不另为映射建链。

## 6. 计数、观察与四个实际main进程

34条直接/控制登记=32公开API+2映射helper：registry3、G1 prepare/save各2、load2、G2 prepare/save各2、screen2、crosscheck2、facts7、facts inspect8、mapping2。profile公开计数含内部调用，不冒充34次直接调用。

437条嵌套完整观察与原code profile逐项闭合：冻结prepare63、Gate1 verify56、load inspect52、normalizer2、loader2、P1 108、SQLscreen2、screen inspect23、store.save4、store.verify104、crosscheck2、crosscheck inspect10、facts build2、renderer7。两次build分别正常/半写，每次内部renderer1；其余五次renderer属于本轮inspect展示核对（含预期拒绝），不是重复build。新receiver0、主入口子进程内部计数null+原因。

15个facts/inspect窗口的复算/SQL/normalizer/loader/store.save增量均0；8次inspect的build增量0。failure/严格类型/缺ID等早期拒绝不执行renderer，进入完整展示核验的inspect恰1次renderer。未加载初判/AI/终判，按null+原因登记，不称守卫实测0。

复用已验收短收尾：写盘前固定独立完整内存预期，候选同缓冲全内容/登记/台账审核，最后原始字节确认实际支配返回和磁盘状态。四个新Python -B进程由cli_profile.py经runpy执行交付测试真实__main__，定稿退出0/1/1/1；none为PASS/空failures，其余三项FAIL/各1项failure。candidate-return真实内容审核拒绝；ledger-late在末次语义消费后的原始字节循环中追加台账LF，1760→1761 B；checks-late同边界3332→3333 B，均命中1、坏字节保留，无回填或刷新预期。

原始业务代码文件+函数名独立profile覆盖16运行API/P1/store/prepare/normalizer/loader/SQL/复算/build/renderer，四进程实测新增业务入口全0；重放源全部文件SHA前后不变。完整argv/stdout/stderr/退出码/命中/源和profile见task033_finalization_01/closure_controls.json、四原文及四profile.json。34/437仅为重放旧观察数量，不称新调用。

## 7. 过程、根与未执行

首轮task033_run_01为19项PASS、33条直接/控制与406条嵌套观察。之后源码复核发现found展示记录缺record_id会晚至字典消费，补非空字符串预检并加同步外层摘要的反例；按代码变化即新版本读数的要求，新建task033_run_02全新登记/夹具事件/装载/G2/screen/crosscheck链，不更新旧凭证。首轮原件保留，不混作定稿验证；没有提前全树扫描或重跑首轮CLI。

只读复用data/batches/task027r1_run_04/batch_normal，工作簿SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`。人类字段沿用已登记APPROVE/BASE2原文，BASE2夹具文件SHA `6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337`，仅更新技术batch/request/material/prior绑定，不生成人员/事件ID/决定时间/原因。

新根为测试task033_setup_01、run_01/run_02、finalization_01、四task033_cli_*；runtime/G1/G2/SQLite各task033_run_01与run_02。每轮正常链与唯一必要半写链，另有仅登记的空输出路径反例。只按具名文件保全/精确恢复本轮单文件，没有递归删除/移动/清理探针、锁或历史现场。

未执行MAIN/零条、冻结核心历史矩阵、历史入口、真实MISMATCH重建、初判/AI/终判、真实数据、网络/UI/ERP、新junction、0009，null+原因登记。TASK-032真实MISMATCH/失败语义为只读源码/已接受证据依据，本轮未重建；旧测试仅导入复用观察/收尾helper，没有调用其旧业务run/main。

## 8. 最终保护与停止

代码/测试/新指南/本回执及局部核对定稿后，仅一次最终全树扫描：task033_finalization_01/scan_protection.py，结果protection_result.json。实际扫描数、新增确切路径及最终四件SHA/长度以delivery.json为准，不预填数字。仅runtime_gate1.py为允许既有变化；明示新根先展开确切文件，旧基线自身/review_result仅两确切先前元数据路径，无前缀豁免。扫描后有限发布本轮自有交接元数据，脚本使用显式四文件/实际argv，不沿用旧回执名称。

139历史缺失继续单列、不造证；27恢复、326越界、19命名偏差和TASK-030具名锁目录逐项冻结不变。锁文件data/runtime/task030_run_01/normal.gate2.lock.preserved_probe/lock.json为41 B / `c78006d55489a9ad1b10cc98a081c3bc8135858c5b9040b7d7d5079409cf0e47`，不追认、不恢复/移动/清理/运行。

本层停止RT_FACT_PACKET_RECORDED；真实批准null、开发宿主0008、真实独立初判未保存、next/AI=false。事实保存、计算一致、契约生效和技术交付不认证身份、不形成审计结论或真实批准。全部交付后停止交独立验收，不实施初判或下一任务。
