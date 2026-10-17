# TASK-033 独立验收：不通过

日期：2026-10-16。技术结论 **NOT_ACCEPTED**。最终交付四件身份及执行端20项检查真实一致，但本轮独立复验确认事实上下文恢复存在两项阻断。执行端PASS、保护范围合规和本轮正常场景通过均不能替代完整验收。没有修改生产代码、交付测试或既有指南，没有子Agent、执行会话、跨会话指令或看板操作。

证据根：`data/reviews/task033_gpt_20261016_034829/`。交付入口为 `data/runtime_fact_packet_tests/task033_finalization_01/delivery.json`，最终业务证据为 task033_run_02；run_01只是保留过程现场。

## 1. 两项可复现阻断

### B1 / P1：实际存在的应付单可被恢复成“未找到”

位置：`scripts/runtime_gate1.py` 的 `_validate_fact_context_033`，4096行起，尤其4102—4117行；`_validate_fact_packet_033` 将上下文交给该通用递归校验。

本轮自建正常C06b链真实生成事实包，R02命中AP01，normalized中AP01存在，实际应付500000分、净付款900000分、超额400000分。只在本轮facts输出中把 `findings[0].context.payable` 从完整found对象替换为 `{label:"相关应付单",record_id:"AP01",status:"not_found"}`；筛查、复算、normalized、DB、Gate记录及金额事实完全不变。

测试侧真实调用冻结render_markdown生成该候选对应Markdown，同步候选packet文件SHA/规范指纹和Markdown文件SHA/长度。实际公开inspect在写盘/网络/子进程守卫内仍返回 **RT_FACT_PACKET_RECORDED**，六项边界false，renderer真实调用一次，build/复算/SQL/保存增量0。正文却写“相关应付单：未找到……所填标识AP01……不参加R01、R02”，与同包R02事实及起始normalized相矛盾。

实际调用 `api_016 / inspect_false_missing_context`，完整返回及计数见api_records.json，真实renderer完整输入/返回见nested_observations.json；坏候选为context.false_missing.packet.bad.bin、context.false_missing.markdown.bad.bin、context.false_missing.artifacts.bad.bin。注入结束后只精确恢复本轮三件原文件，最终正常inspect成功，上游未变。

原因：当前仅对status=found验证任意normalized记录三元组存在；not_found没有按角色、关联ID及对应表核验实际不存在。JSON与Markdown一致不能替代它们与来源事实一致。该项属于来源/展示关系核验缺口，不涉及强认证或不可篡改承诺。

### B2 / P2：缺少必需status被分类成renderer运行错误

在同一本轮原件的内存副本中，仅删除 `findings[0].context.payable.status`，同步packet文件SHA/规范指纹，Markdown保持原字节。实际公开inspect未在字段校验处阻断，而进入真实renderer并返回 `RuntimeGate1Error(stage="render_markdown")`，cause为 `KeyError('status')`。

实际调用 `api_017 / inspect_missing_context_status`；完整异常/原因链及原始代码计数见api_records.json、findings.json，候选见context.missing_status.packet.bad.bin/context.missing_status.artifacts.bad.bin。应在renderer前以字段级 RuntimeGate1Blocked 拒绝必需结构缺失，renderer增量应为0。当前 `if "status" in value` 对缺键直接跳过校验，执行端只补record_id不足以闭合此路径。

两项均已具名保全、精确恢复本轮原件；inspect未写failure。发现分类错误后停止推进后续业务层，改交定点修正卡，不直接修实现。

## 2. 已核对和实际通过的部分

四件实际长度/SHA与delivery一致，适配器为258365 B / `1218244728192d8d0d8ef85f4850b66e656e6891d3708e455f78c1691967a10e`；冻结事实核心54548 B/SHA及TASK-033卡身份保持。AST比较已知起点字节：原十四个公开API签名不变，旧定义仅_call_frozen_entry必要增加实际FactPacketBlocked识别，没有重复函数定义。历史模板BANNER/LIMITS保持，runtime_context正式V1说明与任务卡精确一致。

独立实读定稿34条直接/控制登记、437条嵌套完整观察、20项检查，与写盘前expected_observations的canonical全内容一致；ID唯一/父直接调用闭合，台账实际长度/SHA一致，三时点完整引用及snapshot指纹一致，嵌套计数与原始代码profile一致。32公开API与2个分类helper分列；两次build与七次renderer不能混称单次正常构建。15个facts/inspect窗口无复算/SQL/标准化/装载/决定保存，8次inspect无build。属于本轮审核交付证据，没有重跑执行端整个20项套件。

本轮只新建一条正常前提链：SQL一次、复算一次、build一次、内部renderer一次。完整真实packet返回canonical+LF与保存JSON逐字节一致，Markdown与真实字符串UTF-8原字节一致；三输入真实引用三时点不变。正常inspect只读、renderer一次、build0，完整返回与run规范相等，外层六键/artifacts十键/六false边界，四正常文件。独立事实0/1/0/0、R02=400000分，模板提示原文及runtime_context保持。

真实crosscheck inspect返回后给本轮DB加LF：本次Blocked(runtime.sqlite3)、build0、facts输出未建；保全后精确恢复本轮DB。正常inspect最后语义字段facts.artifacts消费后给Markdown加LF：本次在facts.fact_packet.md拒绝；撤销包装保留坏字节仍拒绝，仅恢复本轮原件后成功。全程上游不变，inspect不写failure。

半写发生过程引用并核对交付真实xb源码/完整观察/1224 B现场；本轮只读inspect实际优先传播facts.failure.write.facts.artifacts.json的ERROR，现场不变。两个实际冻结异常类控制和false→0反例引用已核对的交付完整观察，未另建分类/半写链，未冒称本轮重新执行。

本轮19条直接登记、379条嵌套观察的完整输入/返回/异常、ID/父调用、引用三时点及原函数代码计数闭合。renderer累计9次=正常build内部1+测试侧候选生成1+7次实际inspect渲染（含预期拒绝/错误）；失败优先inspect不render。直接API/内部核验/P1/store/SQL/复算/build/renderer分列，见verification_summary.json。

## 3. 四个新进程与保护

四个新Python -B进程经runpy执行交付测试真实__main__：normal/candidate-return/ledger-late/checks-late退出 **0/1/1/1**；stdout最终verdict、磁盘summary/failures同向，末两例真实末次字节确认窗口LF注入均命中1。profile覆盖scripts目录所有原函数代码，实测新增入口全0；重放源所有文件SHA前后不变，旧34/437观察不当作新调用。完整argv、stdout/stderr、注入和profile见closure_controls.json及具名文件。收尾控制通过不消除B1/B2。

局部定稿后一次最终全树扫描，以TASK-032接受快照165366项/SHA `002f0477e7a6d98273c8591c9f4537d8770e26c595f94398094d4e4814eba9c7`核对范围。结果以本轮protection_result.json/review_result.json为准；范围检查与技术验收分别报告。新增确切登记，扫描后自身元数据有限登记，无目录前缀豁免。

139项历史损失与本轮基线missing分开；27恢复、R5越界326、R1命名19及TASK-030具名41 B锁目录偏差继续原样保留，不追认/恢复/移动/清理/执行。最终保存source_hashes_observed.json仅供本次拒绝现场保护参考，**不是新接受基线**；最后接受基线仍TASK-032。

## 4. 定点修正与停止点

修正卡：`docs/tasks/TASK-033-R1.md`。只修运行适配器的事实上下文必需结构、角色/关联ID/对应来源表及存在性核对，新增有限回归证据，不改冻结事实核心/模板/算法/旧凭证。保留合法R03的not_found，不用全面拒绝缺失关联来获得通过。

不发布TASK-034，不创建执行会话、不自行实施修正。事实记录状态、契约、计算一致和技术检查均不批准真实批次。真实批准仍null，开发宿主0008、真实初判未保存、next/AI=false；看板由人类办理。
