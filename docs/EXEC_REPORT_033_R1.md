# EXEC_REPORT_033_R1：事实上下文定点修正交付

状态：执行端完成，待 Architect 独立验收；不是 ACCEPTED，不批准任何批次。

## 1. 依据、起点与授权范围

任务卡 `docs/tasks/TASK-033-R1.md`，SHA b23d4a52221ca58772bca179be205b7b98e8b3b372ba0a5251e2b75bd564c200；评审 `docs/reviews/REVIEW_TASK_033.md` 与 task033_gpt_20261016_034829/review_result.json 的 NOT_ACCEPTED。

实读起点 runtime_gate1.py：258365 B / 1218244728192d8d0d8ef85f4850b66e656e6891d3708e455f78c1691967a10e。原字节具名保全于 task033_r1_setup_01/runtime_gate1_before.py，起点核对见 starting_identity.json。

正式接受基线仅 TASK-032：165366 项，source_hashes_after.json SHA 002f0477e7a6d98273c8591c9f4537d8770e26c595f94398094d4e4814eba9c7。TASK-033 未接受现场保护参考：165717 项，source_hashes_observed.json SHA 0171d9d6925c1bd64c2c27def03bd70da31189953c12293230eb89e28120fb4c；后者不作为接受基线。

唯一修改既有文件 scripts/runtime_gate1.py；只变两个指定 validator、四个小型私有关系 helper 与版本常量。十六公开函数参数 AST 完全保持；没有新公开 API/CLI/绕过开关，没有重复函数定义、子Agent、联网、新依赖或 Gate2 之后的新阶段。

只新增本轮新测试、新指南、本回执及授权 task033_r1_* 根。TASK-033 原测试/指南/回执、所有冻结核心/模板、旧证据/记录/DB、契约/生效登记/配置/SQL/schema/开发宿主/控制器冻结。精确身份由 delivery_identity_before_scan.json 与最终扫描共同核对。

## 2. 修正内容

实现版本 TASK-033-R1-runtime-gate1-1.0。原递归仅在碰巧含 status 时验任意三元组，改为已知角色先验必需键/类型/封闭形状，再按当前 finding 的原关联 ID 和对应 normalized 表核对存在性与完整 data/source/cells。所有比较使用 canonical JSON 字节，ID 不转换。

- payable→related_ids.payable_id→payables；payments/allocations 的长度、原顺序、原 ID→各自表。
- refund/refund_allocation→本条 evidence.related_refunds→payments/allocations；refund wrapper 恰两键。
- payable_supplier→实际应付 supplier_id→suppliers；payment.payee_supplier→该笔实际付款 payee_supplier_id→suppliers。
- 实际存在必须 found；确实空/缺失才允许 not_found。应付缺失种类代码与原 finding 绑定，标签与冻结展示映射一致；R03 卡 missing_kind 同时核对。
- entry 缺 status/label/record_id/data/source/cells 或角色必需嵌套成员，renderer 前字段级 Blocked；未知字段和错误类型拒绝。

四个新 helper：_fact_context_keys_033、_fact_context_index_033、_fact_context_entry_033、_validate_fact_payable_033。仅索引与核对已有输入，不拼装事实卡、不重算规则、不重新调用 build 验证候选、不改模板。真实 I/O/核心运行异常沿原 Error 边界保留原因链，未增加“捕获 KeyError 后统称 Blocked”分支。

## 3. 最终定点实测

命令：`.venv\Scripts\python.exe -B tests\test_runtime_fact_packet_r1.py --out-dir data\runtime_fact_packet_tests\task033_r1_run_02`。

实际退出 0 / summary PASS / 17 项检查 / 0 失败 / failures=[]；内容审核 audit_ok=true、bytes_ok=true、problems=[]、drift=[]、ledger_source_same_buffer=true。

当前版本最终正常 C06b 链：真实事实 build 一次、内部 renderer 一次、正常 inspect renderer 一次；最终恢复 inspect 再渲染一次。三输入及 renderer 实际消费引用的前/后/API 收尾三时点均一致。真实完整 build 返回 packet 与落盘 canonical+单 LF 精确相等；Markdown 等于真实返回 UTF-8 确切字节；BANNER/LIMITS/runtime_context 保留；四条规则数 0/1/0/0，R02=400000 分仅在测试侧核对。

反例由本轮原件独立深拷贝，具名保全坏 JSON/Markdown/artifacts；然后仅精确恢复本轮三份原件，不删目录。

- call_012：RuntimeGate1Blocked，field=`facts.packet.findings[0].context.payable.status`，reason=facts.packet.findings[0].context.payable.status: 必须与对应表中本条关联ID的实际存在状态一致。
  实际 inspect build/render 增量均 0，未写 failure；完整 traceback/cause_chain 在 api_records.json 与嵌套观察内。

- call_013：RuntimeGate1Blocked，field=`facts.packet.findings[0].context.payable.status`，reason=facts.packet.findings[0].context.payable.status: 缺少必需展示字段。
  实际 inspect build/render 增量均 0，未写 failure；完整 traceback/cause_chain 在 api_records.json 与嵌套观察内。

- call_014：RuntimeGate1Blocked，field=`facts.packet.findings[0].context.payable`，reason=facts.packet.findings[0].context.payable: 缺少必需展示字段。
  实际 inspect build/render 增量均 0，未写 failure；完整 traceback/cause_chain 在 api_records.json 与嵌套观察内。

- call_015：RuntimeGate1Blocked，field=`facts.packet.findings[0].context.payments[0].record_id`，reason=facts.packet.findings[0].context.payments[0].record_id: 与本次独立实读预期不一致。
  实际 inspect build/render 增量均 0，未写 failure；完整 traceback/cause_chain 在 api_records.json 与嵌套观察内。

call_012 是 B1：AP01 确实存在，候选改为 not_found；测试侧真实冻结 renderer call_011 生成矛盾 Markdown，同步 packet 文件 SHA/规范指纹、Markdown 文件 SHA/长度后公开 inspect 仍在 payable.status 拒绝。候选 renderer 单列 test_candidate_generation，未称 inspect 渲染。

call_013 是 B2：仅删 payable.status 并同步 packet 摘要；field 完整为 `facts.packet.findings[0].context.payable.status`，reason=缺少必需展示字段，无 renderer KeyError。call_014 删必需 payable；call_015 串换两个真实存在的付款上下文，定位 payments[0].record_id。

call_017 恢复后正常只读 inspect 成功；fact_packet.json/fact_packet.md/artifacts.json 与具名原件逐字节相同，无 failure；当前上游/DB 与操作前快照相同，接收源始终不变。全部 inspect 在真实只读守卫内，命中 0。

## 4. 合法 R03 内存对照及一次开发失败

指定 C07b 三份原文件与 reference_fixture_identities.json 及 TASK-032 接受基线逐项双重核对，完整原字节保存在本轮 C07b.*.source.bin；没有重跑旧核心/上游、没有新旧凭证迁移。

- data/fact_packet_tests/task008_gpt_20261011_083855/cases/C07b/fact_packet.json：21740 B / 40a19b3a035b27fbda5e94aa8bfdee450c9ed09ccc0131b3e2f6177f26279371。
- data/sqlite_tests/task007_r2_gpt_20261011_081630/cases/C07b/normalized.json：12660 B / b1e7d489d8b49b487b74dc68ca26cfc9995841f44a1b6547a24a5423026bcddf。
- data/sqlite_tests/task007_r2_gpt_20261011_081630/cases/C07b/screening_report.json：12862 B / 36ae19f0905b7922a8a824395276971903219071e105a9ba9483678b870bf4bc。

历史 C07b packet 带旧版顶层 payee_supplier，与现行冻结核心逐笔 payee_supplier 布局不同。首个开发轮 task033_r1_run_01 直接把整个历史 context 送入当前整包 context validator，正确因旧键拒绝，造成其 R03 对照检查失败：实际 17 项 / 1 失败 / 退出 1（其他四反例均按预期拒绝）。现场/观察/FAIL 保留，未回写。

修正测试选取：从生产路径抽出共用应付角色 helper，最终 call_016 仅把历史原 payable entry、原 normalized 的表/原 ID 索引和该原 finding.related_ids 传给 _validate_fact_payable_033。它核对真实空关联/null/EMPTY_AP_ID/not_found/原标签，成功且输入三时点不变；没有放宽当前整包封闭形状，没有改写历史源。此正例仅声明应付角色内存核验，不声明旧整包可恢复。

因此本轮实际保留两条不同迭代代码的开发/最终链；代码提取改变文件 SHA 后建立新登记与夹具事件，未改旧凭证迁就新代码。最终版本仅一条 C06b 正常链 task033_r1_run_02；没有重复半写链或历史大套件。

## 5. 完整观察、计数与收尾

最终直接记录 17：公开 API 15、测试侧候选 renderer 1、历史应付角色 helper 1。公开成功/拒绝均完整记录入参、完整返回或异常、traceback、cause/context 链、field/stage/reasons。嵌套实际消费引用保留到所属 API 收尾，287 条完整观察，ID/父调用与独立原函数 code 对象 profile 闭合。没有把嵌套次数冒称公开 API 次数。

- context_helper：完整条目 7 = 原代码入口观察 7。
- crosscheck：完整条目 1 = 原代码入口观察 1。
- crosscheck_inspect：完整条目 7 = 原代码入口观察 7。
- facts_build：完整条目 1 = 原代码入口观察 1。
- facts_render：完整条目 4 = 原代码入口观察 4。
- frozen_prepare：完整条目 38 = 原代码入口观察 38。
- gate1_verify：完整条目 35 = 原代码入口观察 35。
- inspect：完整条目 33 = 原代码入口观察 33。
- loader：完整条目 1 = 原代码入口观察 1。
- normalizer：完整条目 1 = 原代码入口观察 1。
- p1：完整条目 68 = 原代码入口观察 68。
- payable_context_helper：完整条目 7 = 原代码入口观察 7。
- screen：完整条目 1 = 原代码入口观察 1。
- screen_inspect：完整条目 15 = 原代码入口观察 15。
- store_save：完整条目 2 = 原代码入口观察 2。
- store_verify：完整条目 66 = 原代码入口观察 66。

renderer 总计 4：build_internal 1、inspect_display 2（正常+恢复）、test_candidate_generation 1。四个坏候选 inspect renderer 0。整个新链 SQL/独立复算/事实 build 各 1；7 个 facts run/inspect 窗口内 normalizer/loader/store.save/SQL/独立复算增量全部 0；inspect 的 build 增量全部 0。

复用原已验收短收尾，未复制新审核框架：写前定稿独立内存预期不刷新；一次写定候选；同缓冲内容比较、登记/计数关系、台账真实读回和末次原始字节确认支配真实 main 返回码、磁盘 FAIL、非空 failures。

对最终观察只执行四个真实 __main__ 新 Python 进程 replay（命令/stdout/stderr/哈希和实际代码 profile 完整保存在 finalization_01）：
- none：退出 0 / PASS / failures 0 / 实测新增业务入口 0。
- candidate-return：退出 1 / FAIL / failures 1 / 实测新增业务入口 0。
- ledger-late：退出 1 / FAIL / failures 1 / 实测新增业务入口 0。
- checks-late：退出 1 / FAIL / failures 1 / 实测新增业务入口 0。

candidate-return 是候选返回内容替换；ledger-late/checks-late 是真实终末读取后目标加一个 LF，命中各 1；均依实际审核或漂移拒绝，不按注入标志直接给失败。坏候选保留，源观察目录全部字节不变。replay 记录属于同次原观察重放，不是新的 P1/store/业务核心调用。

## 6. 文件身份与证据路径

- scripts/runtime_gate1.py：264105 B / 65946ffd740771c3917297d5d566c147c641004547fbbbb71873d5b53898e78a。
- tests/test_runtime_fact_packet_r1.py：19910 B / 57e61c71d979da0db9d80a6abae662fe1f64f37439abed25f946fee314204cff。
- docs/RUNTIME_FACT_PACKET_R1_GUIDE.md：6124 B / a08dd8491b1e38a0d7ddf47dd67783870f627767e2b6362035d248380f252f13。

本回执自身最终身份只放 delivery_identity_before_scan.json、delivery.json 和交接消息，不内嵌自身哈希。

- 定稿实际观察：data/runtime_fact_packet_tests/task033_r1_run_02/（summary/checks/failures/api_records/core_records/expected_observations/file_ledger/audit_failure，原件/坏候选/C07b 原字节）。
- 起点与保全：data/runtime_fact_packet_tests/task033_r1_setup_01/。
- 局部验证、四个 CLI 原文/profile、身份、最终双口径扫描与交接：data/runtime_fact_packet_tests/task033_r1_finalization_01/。
- 四个 CLI 新根：task033_r1_cli_none / task033_r1_cli_candidate_return / task033_r1_cli_ledger_late / task033_r1_cli_checks_late。
- 最终运行根：data/runtime/task033_r1_run_02/；两 Gate 记录根 gate1|gate2/task033_r1_run_02/；DB 根 data/sqlite_tests/task033_r1_run_02/。
- 开发 FAIL 根及相应运行/记录/DB：task033_r1_run_01，原样保留。

## 7. 最终保护附件与历史损失

局部 AST/编译/实际反例/CLI 全通过、本指南和本回执定稿后，才执行一次全树扫描；扫描同一读数复用于两套比较，不会为了局部错误反复扫树。实际最终保护结果作为本回执附件 `data/runtime_fact_packet_tests/task033_r1_finalization_01/protection_result.json`，其确切 SHA、项数和两口径结果由同根 `delivery.json` 有限登记；发布程序仅在 scope_compliant=true 且所有交付身份及定稿证据未漂移时创建 delivery.json。本回执在扫描前定稿，不虚填扫描文件数或预先宣布扫描通过。

accepted_cumulative 对 TASK-032 报告累计允许改动；observed_repair 对 NOT_ACCEPTED 现场快照报告本轮净改动。两者允许既有变化仅 runtime_gate1.py；本轮新增按本卡三文件/明确根展开确切清单。原 TASK-033/评审文件逐项受保护，观察快照自文件与 review_result 两条元数据按确切路径登记，不用 reviews/目录前缀兜底，不把未接受旧交付追认为接受。

交付条件：两口径均无范围外变化/未知新增/新缺失/读取错误，交付及旧现场身份无漂移。139 历史损失继续单列不重建；27 恢复项、R5 越界326、R1 命名偏差19、TASK-030 锁目录当前位置均逐项核对不变，不追认、不恢复、不运行、不移动、不删除。

## 8. 未重跑范围与其他过程记录

TASK-033 原20项、半写、前置/末端晚变更、分类映射、旧CLI只引用原数据 task033_run_02 与 task033_finalization_01，以及 Architect task033_gpt_20261016_034829 的报告；其正常链/保护通过不等于 TASK-033 接受。上述故障路径、历史大套件、新 junction、真实初判、AI 本轮未执行，summary.results.not_executed 为 null+原因。本轮接收器新调用0，来源只读复用；子进程内部业务计数仅四个 CLI replay 外部实测0，未测项不填默认0。

过程还包括一次只读 CIM 进程列表侦察因环境拒绝访问失败；没有执行终止或修改进程，没有影响实施。没有递归删除/移动/清理；唯一字节恢复为本轮具名保全的 packet/Markdown/artifacts 三文件。没有看板写操作，不能声称已移 in_review 或勾选清单；本地完整交付可转交 Architect 独立验收。

## 9. 停止声明

本卡实施后停止，不自行 ACCEPTED、done 或制定/实施 TASK-034。真实批准仍 null，开发宿主0008，真实独立初判未保存，next/AI=false。事实一致与技术交付不批准批次，不形成审计结论。
