# TASK-033-R1：事实上下文来源闭合与必需结构定点修正

类型C，由GPT执行端实施、Architect独立验收。依据 `docs/reviews/REVIEW_TASK_033.md` 及 `data/reviews/task033_gpt_20261016_034829/review_result.json` 的NOT_ACCEPTED结论。只消除B1/B2，不推进初判、AI或TASK-034。本卡不启动执行会话，不批准任何批次。

## 1. 起点和范围

正式接受基线仍为TASK-032：`data/reviews/task032_gpt_20261016_030543/source_hashes_after.json`，165366项，SHA `002f0477e7a6d98273c8591c9f4537d8770e26c595f94398094d4e4814eba9c7`。同时实读本轮review_result登记的source_hashes_observed.json及SHA/项数，作为未接受交付与评审现场的保护参考，不能写成TASK-033已经接受。不回滚、覆盖或修改TASK-033原交付及本轮评审证据。

唯一可修改既有文件：`scripts/runtime_gate1.py`，258365 B / SHA `1218244728192d8d0d8ef85f4850b66e656e6891d3708e455f78c1691967a10e`。实现版本升 `TASK-033-R1-runtime-gate1-1.0`；原十六公开API、成功协议、固定集合及前提保持。仅允许 `_validate_fact_context_033`、`_validate_fact_packet_033` 和必要小型上下文核对helper的定点修改及版本常量更新，不重构其他阶段、不新增公开API/CLI/跳过核验开关。

只新增 `tests/test_runtime_fact_packet_r1.py`、`docs/RUNTIME_FACT_PACKET_R1_GUIDE.md`、`docs/EXEC_REPORT_033_R1.md`。新根仅：

- `data/runtime_fact_packet_tests/task033_r1_<轮次>/`。
- `data/runtime/task033_r1_<轮次>/`。
- `data/human_gate_decision_records/gate1/task033_r1_<轮次>/`。
- `data/human_gate_decision_records/gate2/task033_r1_<轮次>/`。
- `data/sqlite_tests/task033_r1_<轮次>/`。

冻结所有其他既有文件：TASK-033测试/指南/回执、所有核心/模板、旧记录/运行/DB/锁/探针、正式契约/生效登记/配置、SQL/schema、开发宿主/控制器及评审现场。不改冻结build_demo_fact_packet.py，不增加新的事实算法、不重算规则、不修改人类字段，不调用子Agent或其他会话，不安装依赖。Python一律-B。

只读复用C06b批次 `data/batches/task027r1_run_04/batch_normal`，工作簿SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`。代码变化必须全新登记和夹具事件/装载/Gate2/screen/crosscheck/facts链，不修改旧凭证适配新代码。人类身份/时间/事件ID/原因仍只用已登记合成夹具原文。

## 2. 修正要求

B1的自建反例见本轮api_016及三件context.false_missing.*.bad.bin：R02/AP01在normalized确实存在，错误not_found候选却通过恢复并生成“未找到/不参加R01、R02”的矛盾正文。

上下文必须按**已知角色**核验，不能只在递归对象偶然含status时检查任意记录三元组：

- 先核对context所需对象/列表及具体entry的必需键、类型和封闭形状；status缺失、未知或错误类型均在renderer前字段级Blocked。label、record_id、data/source/cells及角色需要的嵌套对象不得因缺status跳过。
- payable绑定当前finding.related_ids的payable_id及normalized.payables；payments/allocations按当前finding.related_ids原ID及顺序/集合协议绑定各自对应表；refund/refund_allocation按当前finding.evidence.related_refunds绑定对应payments/allocations；payable_supplier和每笔payment.payee_supplier绑定其实际normalized记录的supplier_id/payee_supplier_id及suppliers表。保留原字符串ID，不把任意表中的三元组存在当成当前角色成立。
- 对应ID在对应表存在时必须found，完整data/source/cells与那一条实际记录严格canonical相等；not_found必须由对应ID为空或确实不在对应表支持。没有依据的not_found、found对应不存在对象、角色/关联ID串换、缺失/多余必需展示上下文均拒绝。
- 合法R03缺失应付关联仍须保留为not_found，missing_kind字段与该finding的原缺失事实一致；不能把缺失关联过滤掉、改为found或全面禁止not_found。只核对输入已有关系，不重新实现R01—R04或重建冻结事实包。
- 不重新组装事实卡、不重新调用build验证输出、不改Markdown模板或BANNER/LIMITS。正常run仍真实build恰1次（内部render1次），inspect只真实render恰1次，不调用build/SQL/复算/标准化/装载/决定保存。所有必要结构/来源核对完成后才能render。

B2的自建反例见api_017：删除payable.status后，当前renderer真实进入并发生KeyError→Error。修正后必须 `RuntimeGate1Blocked(field="facts.packet.findings[0].context.payable.status", reason=明确缺失)`，renderer增量0、无inspect failure。其他同一消费路径的必需结构应一次闭合，不只加本例status特判后让下一个必需键晚至renderer失败。

真实外部I/O/冻结核心运行错误仍按原Error保留原因链；不要把全部异常都改成Blocked或吞掉KeyError。若发现需要更改冻结核心或其他阶段，停止升级，不能扩大范围继续。

## 3. 最小验证

只新建一条当前版本正常C06b链。正常事实build/inspect、真实返回JSON/Markdown确切字节、原模板/runtime_context、三输入/renderer引用三时点、上游/DB不变、只读守卫和原始函数代码计数闭合；事实预期0/1/0/0、R02=400000分只在测试侧使用。

在该本轮新facts场景中保全原件并最小隔离：

1. 重现B1：实际存在的AP01改为not_found，测试侧用真实冻结renderer生成对应Markdown并同步外层摘要；实际公开inspect须在上下文来源核验处Blocked，不能恢复成功，renderer增量0。测试侧生成候选的renderer另列，不能冒称inspect调用。
2. 重现B2：仅删payable.status并同步packet外层摘要；字段级Blocked且renderer0，不出现renderer KeyError/Error。
3. 同一结构边界再删一个renderer必需context成员（例如payable），及一个角色/ID串换反例；均在renderer前拒绝，证明按已知结构/角色核验而不是递归偶遇status。无需穷举所有排列。
4. 最小合法not_found正例：只读引用冻结核心已验收C07b的packet/normalized/screening，在测试内存直接调用本次小型上下文核对helper，不建旧凭证运行、不重跑上游；应保留R03的EMPTY_AP_ID/not_found。具体三文件为：`data/fact_packet_tests/task008_gpt_20261011_083855/cases/C07b/fact_packet.json`、`data/sqlite_tests/task007_r2_gpt_20261011_081630/cases/C07b/normalized.json`、同目录screening_report.json。先按本轮评审reference_fixture_identities.json及最后接受基线核对确切SHA，完整保留实际载荷，不把它称当前运行批准或新业务链。若确切来源不可用，停止报告，不伪造恢复历史文件。

坏候选具名保全，注入仅本轮自建单文件或内存对象，不递归删除/移动，不清理现场；精确恢复本轮packet/Markdown/artifacts后正常inspect成功，无failure，上游不变。原TASK-033半写、前置/末端晚变更、分类映射和CLI证据只读引用并明确未重跑；本轮无需重复两条半写链、20项套件或历史大矩阵。

沿用已验收短收尾及完整观察：独立内存预期不刷新，候选内容/台账真实读回与末次字节确认支配main返回码和summary/failures。对新定稿观察只做四个actual main新进程replay，normal0/candidate-return1/ledger-late1/checks-late1，源只读、实测新增业务入口0。公开直接调用、嵌套核验/P1/store、SQL/复算/build/render/helper分列，代码对象计数与完整观察、ID及父调用闭合。未执行项null+原因，不把旧观察数当新调用。

## 4. 定稿保护、交付与停止

局部代码/新测试/新指南/新回执核对定稿后只做一次最终全树扫描。对TASK-032接受基线报告累计允许改动；对本轮source_hashes_observed.json报告修正轮次净改动。两套口径分别列示，不把未接受现场快照称接受基线。修正轮次既有改动仅runtime_gate1.py，新增按本卡交付文件及新根展开为确切路径登记；原TASK-033和本轮评审元数据另按确切路径保护，不用前缀豁免未知文件。扫描后的自身元数据有限登记。

范围外变化/新增、新missing/读取错误均0；139历史损失继续单列，27恢复、326越界、19命名偏差、TASK-030锁目录偏差原样保留，不追认/恢复/移动/清理/运行。完整登记四件身份、实际反例字段/类型/阶段/cause、候选与原件SHA、真实调用和未重跑范围、CLI原文及保护结果。

实施完停止交Architect重新独立验收，不自行ACCEPTED，不创建执行会话或TASK-034。真实批准仍null，开发宿主0008，真实独立初判未保存，next/AI=false；技术修正/计算一致不批准批次或形成审计结论。
