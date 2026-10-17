# TASK-039-R1 执行回执：按字段来源固定摘要角色

2026-10-17。文档/有限静态修正完成后交Architect独立验收；不宣布技术验收通过，不实施保存/恢复或TASK-040，不操作看板。

## 1. 起点及范围

依据docs/tasks/TASK-039-R1_DRAFT.md（SHA 38acd35bb1b5836a1be065fe676d69310b64c757797232e797af9c389d4b7b52），实读REVIEW_TASK_039、semantic_counterexamples.json、independent_result.json和正式review_result。结论NOT_ACCEPTED，唯一阻断B1，C1为准确字段路径澄清。

NOT_ACCEPTED现场快照：data/reviews/task039_gpt_20261017_015556/source_hashes_observed.json，168771项，SHA b0d9c2f41129266033f84abb83dd4803efdf8e8e43b0ebace9f230ae5f0f3f81；不是接受基线。最后接受基线仍TASK-038，168728项，SHA e841d1caa03c0445246db76148551175cfa7ea2522fe21d1c5dd954d4d40dcb9。

修改前协议32071 B/5091060d…634e、案例21907 B/1c69957c…f8f5、checker22135 B/500c5209…cab3均实读匹配任务卡和观察快照。三件确切原字节及完整SHA保全在task039_r1_prepare_01/source_1_before.bin至source_3_before.bin、starting_identities.json；不是恢复其他旧证据的授权。

仅修改上述三份交付，新增本回执和task039_r1_*静态证据。所有生产、原EXEC_REPORT_039、旧任务卡/评审/静态输出、契约/生效登记等冻结。适配器仍290568 B/ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a。

## 2. B1/C1修正

根因是协议将后缀当作摘要语义，原92项检查只核通用定义/形状，没有核具体字段角色。**旧92静态PASS不能消除B1；原交付未获接受。** 本回执不回写任何旧结论。

删除通配后缀分类，明确每字段按指定来源取FILE或FP。新增27项有限digest_roles设计元数据，覆盖本层新摘要、直接继承的registry/request/packet及来源对象例外、record/binding/P0/历史/清单对象FP、三封装/六快照/manifest的确切FILE及同缓冲对象FP。它不是业务字段扩展；完整继承对象继续沿TASK-034/036/037/038原契约，算法/schema/常量不变。

明确run_binding_sha256=FP(registry.run_binding)、request_sha256=FP(prepared_request.request)、packet_canonical_sha256=FP(packet)。normalized/screening/crosscheck对象摘要仍是FP；工作簿及JSON原文件FILE分列。不能以包含文件SHA或C(对象)+LF的SHA替代这些FP，也不能用对象FP替代writer FILE。

design_version统一1.1；原业务stage/status/版本、两个未来签名、S1—S9/V1—V8、八/九false及调用公式不变。新增静态检查将修改前机器块与本版去除新设计元数据、还原design_version后的完整canonical比较；结果一致。

原43例完整canonical前缀保持（只还原允许的RC-02一处字段澄清后比较）。C1改为materials.fact_snapshot.finding_ids与packet.findings的空列表关系。仅追加RC-44：在更早形状/来源/名单成立后，三个隔离变体分别把两个FP误换FILE、把receipt.context_file_sha256误换对象FP，规定S4/S8/V3对应字段拒绝、不刷新预期。本卡不运行业务符号例，不提供人类提交值。

## 3. 独立来源与静态实际结果

checker从已接受文件的**同一次实际缓冲**取得解析对象和FILE，独立canonical复算FP；先以TASK-038基线核源文件FILE，再比较实际字段。只读旧样本，不调用业务：

- data/runtime/task038_review_003401/normal/runtime_registry.json：run_binding FP=8e71944a8c465c9d8532afa958f2e210b18ff80031ebb3eca654fea44b997528；包含文件FILE=27dae6c237a1862c38d759ccec7016bc2434e52a574f4b16204123b4d428661a；两者不同，且该字段也不等于C(run_binding)+LF的SHA。
- data/reviews/task038_gpt_20261017_003401/fixed_empty_request.json：request FP=0d7f6240d58f68f0431f8224895b334fc99d03c151e4a99d8d27fef77e97cb06；包含文件FILE=3feae9333f5a4e4bf6cb4466964e1543be0c2c836a6b75890b69cb3c2dbb558f；同样与含LF的SHA不同。

冻结AST同时确认build_runtime_registry中的fingerprint(binding)、prepare中的fingerprint(request)/fingerprint(packet)、事实验证中的normalized/screen/cross三个fingerprint调用，不执行AST或业务模块。角色审核的独立预期来自这些冻结字段契约及来源关系，不能从候选或字段后缀反推。

纯内存控制只改候选角色表的run_binding_sha256.role为FILE；不改协议/案例磁盘、不改独立预期、不改实际字段值。正常和控制都调用同一audit_digest_roles；实际main只依据checks失败数返回，不按控制标志直接返回1。

局部检查：正常109/109 PASS、错标109项中1项FAIL且退出1；补入原业务形状/43例前缀保持检查后正常111/111 PASS、退出0。定稿两个新进程命令由prepare根run_cli_static.py真实启动，stdout/stderr及返回码原样保存：

```text
.venv\Scripts\python.exe -B tests\check_runtime_initial_judgment_recording_protocol.py --out-dir data\runtime_initial_judgment_recording_protocol_checks\task039_r1_run_01
.venv\Scripts\python.exe -B tests\check_runtime_initial_judgment_recording_protocol.py --out-dir data\runtime_initial_judgment_recording_protocol_checks\task039_r1_role_fault_01 --role-control
```

定稿结果以prepare根cli_results.json及各根summary/checks为准。正常目标0/PASS/空failures；错标目标1/FAIL/非空failures并定位digest_roles.source_binding.registry_binding.run_binding_sha256；这是本次真实静态审核结果，不冒称未来保存的Blocked实测。

main在静态窗口实际安装sys.setprofile，记录scripts路径下原代码帧call及新加载模块；结果保存在static_execution_observation.json，脚本业务入口和业务导入实测均0。checker仅标准库，未新增网络或业务执行能力。未来保存/恢复/并发/真实句柄/物理junction/AI等仍null+未实施，不把这些0填为动态业务结果。启动的两个checker子进程属于静态验证，单列在cli_results。

## 4. 交付身份和保护

- 协议：36779 B / 0b92e8629a9d8306a8fc9b383a835f393db028a4acdda6d91bde901de7a6b2db。
- 案例：23542 B / 177d58018071b7f87c74be04ce2f1a0d8a7600598e168e9396b8010cb735729b。
- checker：35004 B / 89e66549cdd11cb441c631c60c7a32d064b8c262573e2888eb3d325baa31a2f5。
- 本回执不内嵌自身SHA；四件最终身份均在正常根delivery_identities.json及delivery.json。

所有静态与回执定稿后，唯一一次全树扫描同次产生双口径：相对NOT_ACCEPTED观察快照仅三件允许变化；相对TASK-038接受基线原既有变化为0。两者新missing/范围外新增/读取错误/身份漂移应为0；旧已观察新增及观察快照自身/review_result按确切路径单列，不能用目录前缀豁免。

本回执在扫描前定稿，不预填尚未得到的扫描数字。真实结果写protection_result.json和delivery.json，扫描后仅有限自身元数据。139历史损失、27恢复、326越界、19命名偏差、TASK-03041 B锁及TASK-038/039旧现场保持；不追认、不重建/恢复/删移/清理，不重复全树扫描。

## 5. 过程与停止

首次小补丁因整行上下文不完整而未匹配，apply_patch拒绝，未改变文件；补足上下文后修正。其余局部检查如上，未运行历史矩阵或业务main replay，没有新建业务前提链、决定记录、锁或数据库。旧NOT_ACCEPTED现场与原92项PASS输出原样保留。

本轮交付后停止待Architect独立验收；不推进TASK-040。真实批准null、真实初判未保存、开发宿主0008、next/AI=false。文档、静态结果及技术验收均不批准真实批次。
