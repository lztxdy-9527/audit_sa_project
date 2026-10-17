# EXEC_REPORT_034：人类独立初判协议与案例文档

状态：文档交付，待Architect独立验收；不自行ACCEPTED，不批准任何真实批次。

## 1. 授权、当前基线及范围

TASK-034_DRAFT.md 已由 TASK-033-R1 ACCEPTED 正式发布激活，当前接受基线为 `data/reviews/task033r1_gpt_20261016_110401/source_hashes_after.json`，166017项，SHA `1cd0cdbe8d752e9f5e5945504a417185b571a5cfdb4a50dfae8ebf49813e9d72`。review_result.json、评审和本卡身份实读一致；TASK-033原拒绝及修正过程原样保留。

只新增三份授权文档与 data/initial_judgment_protocol_checks/task034_run_01/。未修改任何既有文件；未新增/修改scripts/tests/config/sql、AGENTS或批准配置；没有子Agent/跨会话指令/看板操作、联网、新依赖或Git初始化。所有脚本仅有限文件读取、SHA、AST、文档结构/链接核对及保护扫描，Python一律-B。

正式契约V1及D1/D2/D3持续有效，不重新征求、不修改。旧方案/纪要的待建立状态仅属历史。本卡不实施P3全部组件，不生成或提交初判，不把建设许可、协议或技术核验当批次批准。

## 2. 交付与封闭字段

协议标识 HUMAN_INITIAL_JUDGMENT_PROTOCOL_DESIGN_NOT_IMPLEMENTED，案例标识 HUMAN_INITIAL_JUDGMENT_CASE_DESIGN_NOT_EXECUTED；所有新函数/类型/状态明确拟定/未实现。拟定唯一纯内存API build_human_initial_judgment_record(submission, materials, expectations, *, prior_history=None)，前三必填；prior_history省略/None在函数体结构化Blocked，不默认空历史。

- submission：9必需+2可选，原人类身份/事件/时间/初判/原因；可选finding_notes和evidence_requests，省略按输出空列表，显式null拒绝；输出副本11键。
- materials：10键，fact_snapshot5键、Gate1/Gate2核验投影、8角色文件清单；材料唯一正文为删除materials_fingerprint后的9键，不置null/任选排序。
- expectations：12键独立预期；契约/运行/事实/两Gate/文件/历史来自未来调用方自己的当前实读核验，不从submission自报或候选重新采集。
- prior_history：3键，完整性/范围/已核验历史索引；成员4键，首版拒绝重复事件或同批第二初判，不覆盖、不自动修订。
- 返回：外层2键、record9键、binding10键、history_binding2键、八边界严格false；record外置FP，无自指，常量note不加人类/夹具内容。

完整机读键集合见协议§9.1和 final_02_schema.json；案例逐项字段/关系、隔离构造、预期/定位、排除早期遮蔽见案例正文，final_02_case_index.json为同正文静态摘录。

## 3. 主要关系与能力边界

固定实体澄明商贸有限公司/CNY/2026年9月/截至2026-09-30；金额整数分、原ID、主表与分摊分列。普通ID允许64hex形状，不用前缀辨身份；SHA完整fullmatch。所有自有类型/常量/键集合严格；规范相等用canonical UTF-8字节，不能以Python False==0/0==0.0代替。

D3为批次初判及原因必填、逐条备注可选。有原因暂不能判断成立，零线索仍要人类输入；程序不预填“无问题”，也不以关键词禁止人类实际原文观点。自由文本不执行，不声称检测作者/独立思考。人类时间沿人工Gate两写法（日期或带±hh:mm的秒精度），真实日历及±14:00范围，原文保留，不补时钟/时区、不以技术登记时间代替。

packet FP、packet/Markdown/started/artifacts的FILE分别命名绑定。材料外层摘要不能替代内部独立名单、原packet FP、来源、当前运行或两Gate关系。相同六项运行绑定不等于各阶段守门材料摘要相同。未来适配必须实读最新fact inspect及两Gate核验；Gate2现有verify返回完整record，不臆造effective许可。

两个明确的受限投影：Gate成员是已核验完整Gate记录的绑定投影；历史成员是已核验完整初判记录的索引。本纯内存协议不把投影/索引称完整record，也不声称从未传入的历史正文中发现schema错误。未来保存/恢复层必须先实读核验完整正文再提取索引并独立固定历史FP，不能用四字段空壳代替恢复；纯核心仅判断当前提供快照范围内的关系，不证明磁盘、全局隐藏历史、身份或业务来源。

packet保留已验收冻结模板及其历史说明，不迁移SIMULATED记录、不改“尚未保存判断”。未来记录另说明当前状态；内存VALIDATED与未来RECORDED、Gate批准、人类审计结论分开。未来技术保存时间分离，submission对象快照只保证字符串与对象，不承诺原JSON文件BOM/排版/换行；原字节需求另卡。没有新存储框架/锁/运行端点/模型/重要性/缺陷等级/外部框架/AI建议/AI许可/终判保存设计。

## 4. 34项符号案例与人类初判夹具缺口

34个唯一连续编号IJ-01—IJ-34，按问题族合并，不把类型/哈希每个变体机械扩展为历史矩阵。IJ-01—10为合法批次/暂不能判断/零条/省略空列表/备注取证/必需输入/未知键/结构来源；IJ-11—22为可选字段关系、错批次请求、材料正文、事实变更、外层更新内层矛盾、FILE与FP交换、严格类型/ID、契约/运行/Gate；IJ-23—29为时间/历史完整范围/重复与同批不可覆盖/变化材料/其他批次历史；IJ-30—34为自由文本/确定性/无别名/异常原因链/未来纯内存守卫方法。

所有人类字段是H_EVENT/H_ACTOR_ID/H_TIME/H_ASSESSMENT/H_REASON等符号引用，不是字面表单值。本轮未编造姓名、实际事件、决定时间、assessment/reason或新夹具。当前人类初判夹具缺口已登记：未来需要实际调用的合成人类初判字段须另行明确提供并先登记；不把现有Gate的APPROVE/reason或旧SIMULATED值改标签挪用。这一缺口不阻塞当前文档与符号案例完成，执行端本轮不提前请求或生成决定。

## 5. 实际静态核验与未执行

局部静态命令 `.venv\Scripts\python.exe -B data\initial_judgment_protocol_checks\task034_run_01\check_documents.py --label local_02`：退出0，21项静态检查/0失败。final模式在三件齐备后额外核对回执与身份；最终结果在final_02_checks.json，不把静态PASS当拟定函数PASS。

静态范围包括：最新ACCEPTED/快照SHA与166017项；16份权威引用身份；设计未实现标识；32组schema键数/唯一及投影；canonical/两类SHA/材料正文；D3/原时间口径；独立预期来源；Gate/历史投影边界；未知类型/不可覆盖/保真/不开放AI；34案例唯一连续/每例四栏；符号非预填；构造先依赖后摘要；本地Markdown链接；AST实际接口/事实常量参考。检查器不实现拟定业务校验函数、不对符号S/M/E/H运行判断逻辑。

业务核心/旧main/宿主/控制器/适配器**未导入且未调用**；未建批次/运行/Gate/DB/facts/初判/配置。protocol_cases_executed/core_calls/guard_hits/persistence_checks均null+原因：TASK-034仅文档，拟定函数未实现且禁止业务执行。当前只报告静态文档检查，不填“未运行故障=0”或声称守卫命中0。

## 6. 权威引用身份与支持断言

- `docs/tasks/TASK-034_DRAFT.md`：11354 B / `5c289eca7b3fb6e0291b9c3400bd5ca56bfc91573c8705d5ebee9ffc73f497a3`；支持：current document-only authority, paths, minimum cases and stop point。
- `docs/reviews/REVIEW_TASK_033_R1.md`：6937 B / `547ee9605334ac66646f6dc9183f83ce669b6917e1d64154855be2507ba6797e`；支持：accepted fact layer, R03 memory boundary and current stop point。
- `docs/AUDIT_CONTRACT.md`：13289 B / `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`；支持：effective V1, scope, independent human judgment sequence and limits。
- `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md`：3195 B / `042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`；支持：human effective confirmation and exact contract file SHA。
- `docs/decisions/REAL_FLOW_DECISIONS_20261013.md`：4100 B / `bface683b1a9eb41250e20822f471621b289f4b8237944a851d3d0554a0635e4`；支持：D1/D2/D3 human decisions; earlier pending-contract statement is historical。
- `docs/proposals/REAL_FLOW_INTEGRATION_PLAN_DRAFT.md`：13568 B / `62c5ab197d2dba0a66132254693569bb3b172096551d86cd600fca81f661ee93`；支持：P3/P4 staged scope and immutability; original pending statements are historical。
- `docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`：39298 B / `68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`；支持：raw human time, independent expectations, canonical bytes and declared-history limits。
- `scripts/build_demo_human_gate_decision.py`：53584 B / `5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79`；支持：frozen P1 names/constants only; AST/text, not imported or executed。
- `scripts/store_demo_human_gate_decision.py`：41353 B / `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7`；支持：frozen save/verify snapshots boundary only; AST/text, not imported or executed。
- `docs/HUMAN_GATE_DECISION_GUIDE.md`：20780 B / `9345baf16297dd53a7bfeb83d5392697c08b86f11d34504f78f068546fffd980`；支持：accepted P1 memory validation is not approval or storage。
- `docs/HUMAN_GATE_DECISION_STORE_GUIDE.md`：20165 B / `3d3805f42444f3e6f06b3a77e55744dcf9c3849252e105c9f67078067ae2582f`；支持：snapshot persistence and restore boundary。
- `scripts/runtime_gate1.py`：264105 B / `65946ffd740771c3917297d5d566c147c641004547fbbbb71873d5b53898e78a`；支持：fact inspect and Gate verification signatures, fixed packet/status constants; AST/text only。
- `docs/RUNTIME_FACT_PACKET_GUIDE.md`：8201 B / `bee4949f5291dbde4aaf9423dcd6098a3d535dac68ce075d4b660b34cb5e04f4`；支持：fact files and frozen template/current runtime context。
- `docs/RUNTIME_FACT_PACKET_R1_GUIDE.md`：6124 B / `a08dd8491b1e38a0d7ddf47dd67783870f627767e2b6362035d248380f252f13`；支持：accepted context source closure and historical R03 scope。
- `scripts/build_demo_initial_judgment.py`：20510 B / `0b5147333a280001591aa5b80ab19c81a7776d3f0d58d00b8769a6ba549c4d8c`；支持：old simulated API/constants, frozen, no migration or relabeling。
- `docs/INITIAL_JUDGMENT_GUIDE.md`：10714 B / `2bbaa876ae7a76175f3462d9395b7bbc8e4bec5b1631030ff3fe32142d0286f5`；支持：old simulation boundary and human-string/object fidelity distinction。

引用登记还保存当前review_result的FILE及AST签名，逐项与最新接受快照相等。正式契约FILE与其生效确认用途独立，旧草案/纪要的未生效文字只引用为历史，不回写。旧业务测试/证据没有重新执行。

## 7. 三件身份与最终一次保护附件

- `docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md`：29189 B / `df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe`。
- `docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md`：24844 B / `e02e1f49e16ebff6a3b683e4c76ece6dd81697569e4876d090a4cccb67d07d46`。

本回执自身最终SHA/长度由delivery_identity_before_scan.json和delivery.json有限登记，不内嵌自身SHA。

文档/引用/局部核验与本回执定稿后仅执行一次完整保护扫描，结果附件 `data/initial_judgment_protocol_checks/task034_run_01/protection_result.json`；同根delivery.json登记其确切SHA、实际计数和三件最终身份。本回执扫描前定稿，不预填扫描成功/项数；发布程序仅在scope_compliant=true、静态最终核对通过、全部交付身份未漂移后创建delivery.json。

接受基线为本轮最新166017项；既有changed必须[]，本轮新missing/读取错误/范围外新增0。新增按三份文档及唯一明示根展开为确切文件名单；旧接受快照自文件与review_result两条元数据单列，不用reviews/目录前缀豁免。扫描后只登记本轮自身元数据，不再改正文、不重扫。

历史139项损失继续单列，不补造/静默清零；27恢复、326越界、19命名偏差与TASK-030具名41 B锁目录偏差按确切身份冻结，不追认/恢复/移动/清理/执行。TASK-033拒绝现场、R1失败迭代、全部旧文件同样保护。

## 8. 过程记录与停止

一次局部检查器错误：local_01对FACT_FILES引用型AST元组调用literal_eval而产生ValueError，未输出文档验收结论、未扫全树。改为只看成员AST名和数量，不执行/导入runtime；同时修正一个纯文字锚点“无文件缓冲”为正文“没有文件缓冲”。两份正文未为该脚本问题修改，local_02通过；static_attempt_01.json原样登记。之后仅在IJ-09明确补入聊天倾向对象反例，定稿静态核对使用final_02；先前final结果及回执草稿保留，不作为最终字节依据。

交付证据根为data/initial_judgment_protocol_checks/task034_run_01/，含引用登记、局部及最终静态结果/schema/case_index、具名脚本和最终保护/交接附件；没有递归删除/移动/清理，没有看板操作。

本卡交付后停止，待Architect独立验收，不制定/实施下一张纯核心卡，不自行done。当前RT_FACT_PACKET_RECORDED，真实批准null，开发宿主0008，真实初判未保存，next/AI=false。正式契约、协议文档、静态核验与技术验收均不批准真实批次、认证身份或形成审计结论。
