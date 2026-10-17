# TASK-032 执行回执：冻结独立复算接线与只读恢复

日期2026-10-16，北京时间。状态为完成本卡实施与交付，待独立架构验收；不宣称ACCEPTED、不批准真实批次。未操作看板、未标done、未制定下一任务。

## 1. 依据、起点和范围

本卡 `docs/tasks/TASK-032_DRAFT.md` SHA `31eccc17bbafd36bf624290ee13a9f1ca08035c198d26ff1ada2b3d419456a11`。先实读TASK-031评审和ACCEPTED review_result，再核对接受基线 `data/reviews/task031_gpt_20261016_021424/source_hashes_after.json`，164880项，SHA `82af8fef8839c0788692a330dd12f3bd08d01a5431adc2de5df96ad0ab710a7e`。

起点runtime为213659B / `540cb273f2b57aa9da1cf57438c9765a0b4346e66db1a46cdd4193f24a9fd609`，原字节保全于 `data/runtime_rule_crosscheck_tests/task032_setup_01/runtime_gate1_before.py`；starting_identity.json登记任务卡/核心/旧测试/基线。未找到适用AGENTS.md，未加载全历史回执。

仅修改scripts/runtime_gate1.py；新增本卡测试、指南、回执及授权task032新根。冻结全部旧测试/指南、P1/store/准备器/计算核心/SQL/schema、契约/登记/配置、开发宿主/控制器和旧证据。不安装、不重接收、不联网、不初始化Git、不调用子Agent。

## 2. 定稿身份与接口

- `scripts/runtime_gate1.py`：234725B，SHA `5ad8b95a196213105ec7e1dc1058d22e7790ac0292b5a77e8d641d29a82902d0`，版本TASK-032-runtime-gate1-1.0。
- `tests/test_runtime_rule_crosscheck.py`：21969B，SHA `de00cd4da824bbf82fc35ce84db8ebbbb52bd0cbddf9fde963a86ce81099f7b3`。
- 新指南 `docs/RUNTIME_RULE_CROSSCHECK_GUIDE.md` 与本回执的写后完整SHA/长度，登记于task032_finalization_02/delivery_identity_final_before_scan.json与扫描后有限发布delivery.json；回执不内嵌自身摘要。

新增run_gate2_rule_crosscheck/inspect_gate2_rule_crosscheck，无CLI。成功六键、status=RT_RULE_CROSSCHECK_RECORDED、七边界严格false；started八键/bindings九键、artifacts十五键/数据库三键、failure六键。AST对照接受原字节：十二旧公开接口签名不变；既有函数定义仅_call_frozen_entry增加实际模块CrossCheckBlocked识别，旧分类不变；没有重复定义、物理拆分、通用许可或跳过核验开关。

## 3. 实现绑定和失败语义

共享_screen_inputs_031固定操作开始来源/登记/Gate1/Gate2/load/DB/静态与四SQL读数，筛查三文件逐项同缓冲捕获；实际调用公开inspect_gate2_approved_screen，保留其真实Gate2核验，screen artifacts/报告文件SHA与规范指纹/DB和本窗口闭合。normalized与screening_report仅从起始缓冲解析，不以后续重读覆盖预期。

冻结核心crosscheck_demo_rules.py为59934B / `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`，独立SHA加载且沿用十四清单。每次仅调用一次verify_rule_facts(two_objects)，不传DB、不调用SQL或normalizer/loader。生产保留两实际引用，调用前、返回后及成功API收尾比较指纹；观察器独立保存三时点及完整真实返回。DB由适配器核对起始字节。

独占新.crosscheck叶；started/report/artifacts canonical UTF-8+单LF，逐件读回绑定该次缓冲，artifacts最后写。接口只核验固定十八键/来源/开发边界、十维/名单/严格计数/实际findings/observed_summary/method/limits；不复制算法。语义与返回对象构造后，最终只确认起始/writer字节、集合、failure/锁和reparse，再直接返回。

MISMATCH正常返回先完整写report并读回、核验比较协议，随后Blocked(crosscheck.report.matched)且不写成功artifacts，reason包含差异数/维度；保存六键BLOCKED诊断，不修复上游，不继续事实。运行/I-O为Error、真实模块类映射，reasons和cause链完整。inspect先传播有效failure、不解析半写artifacts、不写诊断。

## 4. 定稿目标验证

实际命令：

```text
.venv\Scripts\python.exe -B tests\test_runtime_rule_crosscheck.py --out-dir data\runtime_rule_crosscheck_tests\task032_run_02
```

定稿目标21项检查、0失败、退出0/PASS，完整结果见同根summary/checks/failures/api_records/core_records/expected_observations/file_ledger/audit_failure。独立内存预期在写盘前定稿，同缓冲内容和台账审核、末次字节确认支配真实返回；没有按注入标志直接判失败。

G1正常：新C06b链至筛查，复算真实恰1次，十维MATCHED；R01/R02/R03/R04=0/1/0/0，R02=400000分。真实核心完整返回canonical+LF等于报告确切字节；两输入同引用三时点相同。run/inspect返回canonical相同、三正常文件、六键外层/十五键artifacts/七false边界；上游/DB字节不变。inspect在真实写盘/网络/子进程守卫下成功，复算/SQL/标准化/装载/保存增量0。

同场景反例：缺筛查screen_dir、错Gate2事件、重复/已有空输出crosscheck_dir，均在复算增量0处拒绝。空输出只测路径前提，不称完整链。三个内层协议反例同步外层report文件SHA与对象指纹后仍定位拒绝：source_rows维executed=整数1、R02计数=浮点1.0、matched_dimensions删一项；不靠外层旧哈希提前遮蔽，键顺序未规范化成新的业务事实。

G2真实MISMATCH：独立新场景，仅把本轮筛查findings[0].source_rows.payables.AP01从严格整数2改3，同步筛查artifacts的文件SHA/规范指纹；normalized/DB/Gate不改。先公开screen inspect成功，再真实复算返回一项SOURCE_ROW_MISMATCH，field_path=source_rows.payables.AP01，expected=2/actual=3且两类型int；未匹配维度source_rows。完整真实差异报告与保存字节相同，适配器Blocked(crosscheck.report.matched)，无artifacts，failure.kind=BLOCKED。撤销包装后inspect仍拒绝、目录/上游字节不变。完整差异见mismatch.crosscheck/crosscheck_report.json及checks中的G2.true_mismatch。

G3故障/晚变更：

- 包装真实公开筛查inspect返回原对象后、本次核心前给DB加LF，命中1。本次Blocked(runtime.sqlite3)，复算0、输出未建；具名保存坏字节，仅恢复本轮原DB。
- 无注入先观察inspect最后语义字段crosscheck.artifacts；真实helper返回后给本层报告加LF，命中1。本次Blocked(crosscheck.crosscheck_report.json)，撤销wrapper留坏字节仍拒绝；保全后只恢复本轮原报告即成功，不写failure。
- artifacts真实open(xb)句柄写半段后抛OSError，生产writer异常分支映射RuntimeGate1Error(write.crosscheck.artifacts.json)；六键ERROR诊断、真实原因链、半写字节保留。后续只读inspect优先报告crosscheck.failure，不被半写JSON遮蔽。
- 两个实际模块异常类用同一私有调用helper各做一次受控映射，reasons两项完整/cause类正确；真实复算函数入口0。这是替身分类控制，不称复算发现业务缺陷，不另建完整链。

本卡选择inspect末次语义后报告晚变更，未另重跑报告writer返回后变更场景（任务卡为二选一）；未重跑HOLD/REJECT矩阵、MAIN/零条、冻结核心大套件或历史入口。

## 5. 观察、计数和实际CLI

定稿直接记录42条=公开API40+helper2；registry4、Gate1 prepare/save各3、load3、Gate2 prepare/save各3、SQLscreen3、crosscheck8、crosscheck inspect9、screen inspect直连1、mapping2。profile公开计数含内部调用，不能混加为直接次数。

289条嵌套完整观察与原始code profile逐层闭合：冻结prepare49、Gate1 verify39、旧load inspect33、normalizer3、loader3、P1 72、SQLscreen3、screen inspect12、store.save6、store.verify66、crosscheck3。三次复算分别正常/MISMATCH/半写场景，正常那一次恰1；三次SQL/normalizer/loader仅用于三个新版本前提小样。17个crosscheck/inspect直接窗口无SQL/normalizer/loader/store.save，9次inspect的复算增量0。新接收0，子进程内部业务计数null+原因。

定稿四个实际main新进程replay由task032_finalization_02/verify_local.py启动；原文argv/stdout/stderr/大小/SHA与注入读数见closure_controls.json：normal0/PASS/空failures、candidate-return1/FAIL、ledger-late1/FAIL、checks-late1/FAIL。末两例在真实末次语义消费后的原始字节循环中读取返回后追加LF，均命中1；坏字节保留，无候选回填、无预期刷新。replay源全文件SHA前后不变，新增业务调用0；42/289只是被重放观察数。

测试复用TASK-031/030/029/028已验收观察/短收尾helper，仅增加真实复算代码身份、完整输入返回/异常、三时点引用与SQL窗口守卫；没有修改旧harness或新增框架。未加载事实/初判/AI等下游，按null+原因登记，不声称测得守卫0。

## 6. 过程、路径和历史保留

首轮task032_run_01的21项及四CLI均通过。随后局部源码检查发现生产成功API收尾尚缺显式输入引用再确认（测试观察器已有第三时点），定点补上收尾条件检查；代码字节变化后按卡新建task032_run_02全新登记/Gate1/load/Gate2/筛查链。首轮原件及四CLI留作过程证据，不更新旧凭证、不冒充定稿复验；没有提前全树扫描。

交付辅助脚本首轮身份登记沿用EXEC_REPORT_031.md，漏入本卡新回执；在最终扫描之前修正本轮publish脚本引用。首轮delivery_identity_before_scan.json原样保留，仅作过程记录；最终采用新文件delivery_identity_final_before_scan.json，扫描/交付均绑定最终四件。未修改旧回执，未因此重跑业务或全树扫描。

只读复用data/batches/task027r1_run_04/batch_normal，工作簿SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`。人类字段沿用已登记BASE2与APPROVE片段，BASE2文件SHA `6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337`；只更新技术request/batch/material/prior绑定，不生成姓名/事件ID/时间/原因。

根：测试task032_setup_01、run_01/run_02、finalization_01/finalization_02、两组task032_cli_*/task032_cli2_*；运行/G1/G2/SQLite各task032_run_01与02。每轮三个完整场景normal/mismatch/half_artifacts，另有仅登记/空输出路径反例。没有新接收批次，不递归删除/移动/清理目录或探针；只按具名文件保全/精确恢复本轮DB/报告/artifacts，MISMATCH和半写现场保留。

未执行事实底稿、真实独立初判、AI/终判、真实数据/网络/UI/ERP、新junction、0009、历史大套件；均null+原因。旧证据与helper为只读引用，旧入口未重跑。Task031旧SQL报告writer晚变更与分类场景不称本轮新实测。

## 7. 最终保护与停止

代码/测试/指南/本回执及局部核对定稿后，一次最终全树扫描使用接受基线164880项；脚本/结果为task032_finalization_02/scan_protection.py与protection_result.json。实测扫描数、确切新增名单和完整交付SHA见最终delivery.json，不预填扫描结果。仅允许runtime_gate1.py既有变化，新增根展开确切文件，无前缀兜底；基线自身/review_result以两条确切路径列为先前元数据。最后只有限登记扫描与本轮交接元数据。

139历史损失继续单列、不造证；27恢复、326越界、19命名偏差及TASK-030锁目录逐项不变。具名锁data/runtime/task030_run_01/normal.gate2.lock.preserved_probe/lock.json为41B / `c78006d55489a9ad1b10cc98a081c3bc8135858c5b9040b7d7d5079409cf0e47`，不追认、不恢复、不移动或运行。

真实批准null，开发宿主0008、next/AI=false。RT_RULE_CROSSCHECK_RECORDED不构成审计结论或执行许可；不接事实底稿、真实初判或AI，不生成0009。全部交付后停止实施交独立验收，不自行推进下一任务。
