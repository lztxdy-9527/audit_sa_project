# TASK-031：有效Gate2决定后的规则筛查接线

类型C：Architect明确单次动作前提和证据边界，GPT执行端实施，Architect独立验收。本卡适配器建设及合成夹具测试依据项目持续任务授权；D2仅是人工决定记录建设依据，不能当作计算动作或批次批准。每次实际调用仍须实读当批明确Gate2 APPROVE，不能从总体授权或聊天推断批次批准。测试只用既有合成夹具。

## 1. 起点与范围

先只读核对 `docs/reviews/REVIEW_TASK_030.md`、`data/reviews/task030_gpt_20261015_230844/review_result.json`及同根source_hashes_after.json，必须ACCEPTED；基线SHA/项数取接受登记。首轮锁目录偏差不追认，按评审具名保留，不移动或清理。

唯一允许修改的既有文件：`scripts/runtime_gate1.py`，185648 B / SHA `3940a625082d09da6df3f52801c1e9169adb680de29060e70c6f4be285f4759d`。实现版本升TASK-031-runtime-gate1-1.0；现有十公开API的签名/协议/固定集合/前提保持，可作必要小型内部helper复用，不新增框架、通用控制器或调用方绕过开关。

仅新增 `tests/test_runtime_approved_screen.py`、`docs/RUNTIME_APPROVED_SCREEN_GUIDE.md`、`docs/EXEC_REPORT_031.md`；本轮新根仅：

- `data/runtime_approved_screen_tests/task031_<轮次>/`。
- `data/runtime/task031_<轮次>/`。
- `data/human_gate_decision_records/gate1/task031_<轮次>/`。
- `data/human_gate_decision_records/gate2/task031_<轮次>/`。
- `data/sqlite_tests/task031_<轮次>/`。

只读复用已有小样批次；代码变更即新运行版本，建立新登记/Gate1/装载/Gate2夹具事件，不更新旧凭证。冻结全部既有测试/指南、P1/store/准备器、标准化/SQLite/规则/复算/事实/初判核心和SQL/schema、正式契约/登记/配置、开发宿主/控制器及旧证据。不安装、不重接收、不递归删除/移动或清理探针；需改冻结算法或扩大流程时停止升级。

## 2. 两个公开API，无CLI

```python
run_gate2_approved_screen(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
inspect_gate2_approved_screen(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
```

参数中scope_dir/event_relative仍指Gate1，gate2_event_relative指固定Gate2事件。成功恰六键：stage_version=`TASK-031-approved-screen-1.0`、status=`RT_RULE_SCREEN_RECORDED`、batch_id、run_binding_sha256、artifacts、boundaries。

boundaries恰八键且严格false：crosscheck_recorded、fact_packet_recorded、human_initial_judgment_saved、ai_enabled、audit_conclusion_formed、identity_authenticated、source_authenticity_proven、next_step_allowed。状态只登记本层筛查产物，不改变旧phase/0001—0008，不创建RT_G2_APPROVED或通用许可，不生成0009。

异常复用RuntimeGate1Blocked(field,reason)/RuntimeGate1Error(stage,reason)，保留原因链与原始reasons。inspect全程只读、不写failure、不调用screen_sqlite或任何计算/保存入口。

## 3. 必须实际成立的Gate2前提

真实调用现有 `verify_runtime_gate2_decision`，拒绝caller-supplied status/record/expected或APPROVE字符串。核验后明确要求record为同批次GATE2、decision=APPROVE、decision_source=HUMAN_GATE_DECISION、actor_kind=HUMAN_DECLARED；质量OK、三个阻断/失败计数为严格整数0，契约与共享六项绑定同当前登记，完整前序为本次有效Gate1。

HOLD/REJECT仍是合法可恢复记录，但本动作必须在筛查核心与输出目录创建之前拒绝；已有failure、锁、不完整封套或变化材料同样拒绝。不得修改P1的execution_allowed=false或persisted=false来制造许可。只允许本次显式API调用执行单次固定筛查动作，不向其他步骤颁发权限。

在核验调用前固定操作开始的来源八文件、登记二文件、Gate1八文件、Gate2八文件、装载四文件、DB及已绑定静态代码/四SQL读数；同缓冲取对象/长度/SHA。复用现有capture/集合/路径helper和真实核验，不复制Gate2验证算法；公共verify仍须被实际调用。必要的小型内部共享不改变旧API语义。

## 4. 真实核心与产物（单次，不重算算法）

冻结 `scripts/screen_demo_sqlite.py`：39840 B / SHA `1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe`，RULE_CORE_VERSION=TASK-006-rule-core-1.1。加载时使用独立预期SHA，纳入已有14项代码清单与操作读数；四SQL仍按既有规则清单绑定，不新增物理模块或改变14项计数。

只真实调用一次：

```python
screen_sqlite(str(database_path), load_report_object, cutoff_date="2026-09-30")
```

load_report取本次已核验的确切文件缓冲；核心前再确认Gate2/Gate1/来源/登记/装载/DB/静态绑定和固定集合。调用前、真实返回后核对保留的同一load_report引用指纹，核心返回完整保存观察，输入被改写即拒绝。数据库在核心前后与起始capture字节一致。不再调用normalize/loader，不导入答案册/生成器/场景标签，不重写R01—R04或金额勾稽。

可小改已有_call_frozen_entry支持kwargs及实际模块RuleScreenBlocked类型，旧分类默认不变；Blocked→本层Blocked，RuleScreenError/I-O→Error，原因列表完整。不要按同名类字符串识别，不预调用核心试探。

输出固定为登记叶同级 `<登记叶名>.screen/`，必须从未存在（含空目录/文件拒绝）。成功恰started.json、screening_report.json、artifacts.json三文件；只独占创建、UTF-8无BOM/canonical JSON+单LF，逐件读回与本次待写字节相等，artifacts最后写并读回。原登记叶二文件、load四文件、Gate1/Gate2事件八文件和DB不改。

started封闭八键：started_version、batch_id、source_batch_relative、runtime_relative、gate1_event_relative、gate2_event_relative、database_relative、bindings。版本TASK-031-approved-screen-start-1.0。bindings封闭五键：registry_file_sha256、gate2_record_file_sha256、gate2_record_fingerprint、load_report_file_sha256、run_binding；文件哈希来自操作开始实读，规范指纹分别登记。

artifacts封闭十一键：artifacts_version、batch_id、run_binding_sha256、registry_file_sha256、gate2_record_file_sha256、gate2_record_fingerprint、load_report_file_sha256、started_file_sha256、report_file_sha256、report_canonical_sha256、database。版本TASK-031-approved-screen-artifacts-1.0。database恰relative/file_sha256/byte_size，大小为严格非负整数。

完整真实核心报告原样保存，仍为DEVELOPMENT_TEST_ONLY/DEV_RULES_COMPUTED/next_step_allowed=false，不改报告标记、limits或人类提示。run和inspect最少核验以下关系，不复制整套规则：

- report顶层按冻结实际返回18键封闭；核心版本、固定截至日/期间、period.range_ok严格true、开发边界、database前后SHA和database_unchanged严格true、read_only的uri_mode=ro/query_only严格整数1。
- load_source七键与本次load_report、规范payload指纹及DB绑定闭合；run_metadata按冻结十键与已有DB/load核验读数一致，不能把字符串"false"与布尔false混同。
- rules恰R01—R04，SQL路径/SHA/版本与已核验四SQL清单一致；rule_hit_counts四项+total为严格非负整数，逐规则数量与findings实际rule_id一致、total等于总长，线索标识唯一。
- overall_reconciliation两成功旗标严格true，主表净额/已知/缺失关联净额及缺失分项与load_report对应精确整数一致；statistics.r02_overpayment_total_cents与报告R02线索超额整数分之和一致。规则金额不加总称损失。

所有计数和金额按冻结实际类型检查为严格整数，bool/同值float不能冒充；SHA全串64位小写hex，普通业务ID保留原文。报告JSON字节SHA与规范对象指纹分列。inspect复核已有报告和绑定，不重新运行SQL规则；底层本已验收的只读行数/元数据检查允许，不新增完整复算算法。

输出已建后失败只独占保存failure.json：封闭六键failure_version/kind/stage/field/reason/cause_chain，版本TASK-031-approved-screen-failure-1.0，kind严格BLOCKED/ERROR。无输出目录不为诊断造目录；失败诊断先核验再消费其他可能半写文件。半写/已写产物保留，不覆盖、不重试、不清理或声称回滚，主次错误都可追溯。

全部语义消费、异常/输出对象构造完成后，从操作开始或本次writer已绑定读数最终确认全部来源/事件/静态/DB/输出字节及固定集合/failure/锁/逐级reparse。之后不再读候选生成成功。新输出目录不必新增独立锁协议：其独占创建已阻止重复运行，沿用已有Gate1/Gate2锁不存在的前提。

## 5. 最小验收

四组即可，不追求检查项数量、不重跑历史大套件：

1. 一个当前版本C06b正常小样：新Gate1/装载/Gate2 APPROVE→真实screen恰一次→三文件与只读inspect；完整真实核心返回与报告canonical相等，报告缓冲确切字节相等、load_report三时点指纹一致、输入/DB/Gate1/Gate2/登记/load不变。固定小样`data/batches/task027r1_run_04/batch_normal`工作簿SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`，独立事实断言R01/R02/R03/R04=0/1/0/0、R02超额400000分（1000000已结算付款−100000有效退款−500000应付）；这是该小样的测试预期，不进入生产算法。inspect的规则核心次数0。
2. 一个有效HOLD对照及少量前提/路径反例：真实Gate2verify可恢复HOLD，但run在screen增量0、输出未建时拒绝；缺/错Gate2绑定、既有失败/锁、已有空输出目录/越界路径定位拒绝，旧现场不变。可在本轮已有干净场景上隔离改写并同步直接依赖摘要，坏候选具名保存、仅精确恢复本轮单文件。不要为REJECT重复矩阵再建第三条相同计算链。
3. 最小故障/晚变更：真实核验返回后、screen前给本轮DB或Gate2context加LF，本次即拒绝且screen0；真实报告writer返回后给报告加LF，本次与该次缓冲绑定拒绝；inspect最后必要消费后改报告或新增未知项，本次拒绝、撤销wrapper后保留变更仍拒绝、只恢复本轮原件后成功，inspect不写failure。另做artifacts真实xb句柄半写OSError，stage/原因链/失败现场准确。两真实核心异常类的受控映射可在同一私有调用helper做最小控制，不必为分类另建完整链；明确helper控制与真实全流程I/O故障分列，不把替身异常称为核心发现业务问题。
4. 复用既有短收尾和观察器，仅补实际screen入口代码对象/完整输入返回或异常/三时点引用；直接API、Gate1/Gate2/inspect/store/P1及SQLscreen分列，禁止计算/保存入口不混加。写盘前冻结独立内存预期、同缓冲审核内容/台账、最后原始字节确认支配返回码。四actual main新进程replay为normal0、返回替换1、末次消费后台账LF1、checksLF1，磁盘PASS/FAIL与failures一致；不重建期望或回填坏字节，replay不再建链。

测试不得改旧harness、移动锁目录或清理探针；各失败用独立新场景。新决定仍只取TASK-030已登记的APPROVE/HOLD人类字段，不生成人员/时间/原因/event_id。旧证据注明引用且未重跑，未执行null+原因；真实链接不强制另建，不将未装载下游入口报为守卫测得0。

## 6. 完整交付与保护

代码/指南/回执及局部核对定稿后一次最终全树保护。changed仅runtime_gate1.py；新增仅四交付文件和明示根展开的确切路径，无前缀兜底；范围外变化/新增、新missing/读取错误0。139历史损失、27恢复、326越界、19命名偏差和TASK-030具名锁目录偏差按接受基线保留，不追认、不重建、不清理。

交付完整SHA/长度、实际目标field与注入边界、真实调用数/CLI原文/源不变证明、失败现场和引用未重跑范围；最后有限登记扫描自身元数据。全部交付后停止实施交独立验收，不自行宣布通过或推进下一任务。

停止于本层SQL规则报告：无独立复算/事实底稿/真实独立初判/AI/终判，无开发宿主0009，无真实数据/网络/UI/ERP。真实批准仍null，开发宿主0008，next/AI=false。线索不是审计结论，模拟夹具APPROVE不批准任何真实批次。
