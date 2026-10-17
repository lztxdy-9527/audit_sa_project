# TASK-031 执行回执：有效 Gate2 APPROVE 后的冻结 SQL 筛查

交付状态：实施与本卡局部测试完成，交独立架构验收；本回执不宣称技术 ACCEPTED 或批准任何真实批次。实现定稿跨 2026-10-15/16，北京时间。本轮未操作看板、未标 done、未制定下一任务。

## 1. 授权、起点和范围

唯一实施依据 `docs/tasks/TASK-031_DRAFT.md`，字节 SHA `cd3d1375a9fd942d7dd2ecbd8e8876d7c903dc845b517ef906b3c09ff39a9d6d`。只读核对 TASK-030 的 ACCEPTED review_result 与评审，接受基线为 `data/reviews/task030_gpt_20261015_230844/source_hashes_after.json`，164607 项，SHA `030f013f3b13104893e69e88666a7cf623419426995dda264c138494440d5c65`。

起点 runtime_gate1.py 为185648 B / `3940a625082d09da6df3f52801c1e9169adb680de29060e70c6f4be285f4759d`；修改前确切原字节保全至 `data/runtime_approved_screen_tests/task031_setup_01/runtime_gate1_before.py`，并记 starting_identity.json。未把哈希当作恢复材料。

仅修改 `scripts/runtime_gate1.py`；新增本卡测试、指南与回执，产物仅在 task031 明示新根。冻结 P1/store/准备器/计算核心/SQL/schema、旧测试/指南、契约/登记/配置、开发宿主/控制器及旧证据。不新接收，不调用子 Agent、不联网、不安装依赖或初始化 Git。

## 2. 交付身份

- `scripts/runtime_gate1.py`：213659 B，SHA `540cb273f2b57aa9da1cf57438c9765a0b4346e66db1a46cdd4193f24a9fd609`，实现版本 `TASK-031-runtime-gate1-1.0`。
- `tests/test_runtime_approved_screen.py`：23173 B，SHA `5e4f014477ac55cf16166a2eca95d14f79e2a168f6f9d62520ad24389be28440`。
- `docs/RUNTIME_APPROVED_SCREEN_GUIDE.md` 与本回执：写后长度/完整 SHA 登记于 `task031_finalization_01/delivery_identity_before_scan.json` 和扫描后有限发布的 `delivery.json`。本回执不内嵌自身摘要。

AST 对照原字节：原十个公开 API 签名全部不变；新增仅 run_gate2_approved_screen / inspect_gate2_approved_screen；既有函数定义仅 `_call_frozen_entry`（kwargs/真实类/reasons）与 `_prepare_runtime_gate2_captured`（提取起始 capture 小 helper）变动，没有同名重复定义。未改变旧协议/集合/前提，未增加绕过开关或通用控制器。见 local_validation.json。

## 3. 实现和本次绑定

两新 API 实际调用公开 verify_runtime_gate2_decision；从操作开始固定来源八件、登记二件、两 Gate 各八件、装载四件、DB和静态/SQL字节。只抽取共享 capture 前段，不复制 Gate2 算法。验证返回仍须与初始 Gate2 decision_result、当前登记和完整 Gate1 闭合，并明确要求 GATE2 APPROVE / HUMAN_GATE_DECISION / HUMAN_DECLARED / OK / 严格整数零阻断。HOLD 是合法记录，但动作拒绝。

冻结筛查核心实读独立预期 SHA `1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe`。每个真正运行一次调用 screen_sqlite，load_report 从已绑定原缓冲解析；保留实际消费引用核对前后指纹。DB前后字节与初始 capture 一致。不调用 normalize/loader 再计算，不保存新决定。

输出固定 `.screen` 同级新叶，独占创建，三件依次 started/report/artifacts；canonical UTF-8 + 单 LF，逐件读回精确等于本次 writer 缓冲，artifacts 最后写。返回六键、边界八键严格 false。报告保留完整18键、开发标记、limits与提示；文件 SHA 和规范指纹分列。报告最小协议/来源/元数据/四 SQL/计数/唯一线索/精确整数金额/勾稽/R02 总额全部核验，inspect 不重跑 SQL。

失败只在已建立本次输出叶时独占写六键诊断，真实半写保留。inspect 有效失败优先且只读。全部语义、输出对象构造后仅用初始/writer绑定读数作字节/集合/failure/锁/reparse末次确认，随后直接返回。

## 4. 实际命令与最小四组

定稿业务入口一次执行：

```text
.venv\Scripts\python.exe -B tests\test_runtime_approved_screen.py --out-dir data\runtime_approved_screen_tests\task031_run_01
```

结果退出0、PASS、21项检查全true、failures=[]；content/bytes/台账审核真实通过，problems=[]、drift=[]、ledger_source_same_buffer=true。checks.json、api_records.json、core_records.json、写盘前冻结 expected_observations.json、file_ledger.json、audit_failure.json、summary/failures 齐备。

G1：正常场景真实 SQL 恰一次，三输出与只读 inspect 返回相同，完整真实核心返回与报告 canonical 相同，报告字节恰其 canonical+LF。C06b R01/R02/R03/R04=0/1/0/0，R02=1000000−100000−500000=400000分，DB不变、load_report同引用三时点相同。正常运行前后批次、登记、G1/G2、load与DB字节未变；inspect只读守卫无命中。

G2：错 Gate2 事件、越界数据库、内层 Gate1 路径矛盾（同步 receipt 外层 SHA）、有效 Gate2 failure、重复输出均定位拒绝。合法 Gate2 HOLD 可由真实 verify 恢复，run 拒绝 field=gate2.record.decision，screen增量0/输出未建；独立本轮 HOLD 锁现场保持原目录未移动；既有空输出拒绝 field=screen_dir。空输出反例仅测路径前提，不冒充完整 HOLD/APPROVE 链。

G3：三个实际接缝和一项真实 writer 故障：

- 包装真实公开 Gate2 verify，返回原对象之后给本轮 DB 追加 LF，命中1；本次run在runtime.sqlite3拒绝，screen0且输出未建。坏字节保全后仅恢复本轮原DB。
- 包装真实报告 writer，读回返回之后给报告追加 LF，命中1；本次run以该次缓冲绑定拒绝 screen.screening_report.json，有效本层 failure保留。
- 无注入先观察 inspect 最后语义相等核对字段 `screen.artifacts`；真实helper返回后给报告追加LF，命中1。本次inspect拒绝screen.screening_report.json；撤销wrapper留变更仍拒绝，保全坏字节仅恢复本轮原件后成功，未写failure。
- 包装生产writer真实open的xb句柄，artifacts1008B缓冲写入504B后抛OSError，命中1；生产except映射RuntimeGate1Error(write.screen.artifacts.json)，六键failure含原OSError链，半写未删未覆盖。后续inspect先报告screen.failure而不解析半写artifacts，目录字节不变。

真实模块 RuleScreenBlocked/RuleScreenError 的分类各用同一私有调用helper一次受控异常，两项 reasons 完整、cause为实际模块类；它们是替身映射控制，不声称SQL发现业务错误，不另建业务链，真实SQL入口增量0。

G4：复用已验收短收尾/观察器，新增真实 SQL 入口代码身份与完整输入返回、DB前后、load_report三时点；screen/inspect窗口normalizer/loader/store.save命中0。未装载的复算/事实/初判/AI入口记null+原因，不报假守卫0。冻结独立内存预期在候选读取前取得，同缓冲内容审核、台账与末次原始字节实际支配返回。

## 5. 实际调用与四 CLI 控制

业务入口登记45条：43条直接公开API + 2条映射helper；registry5、Gate1 prepare/save各4、load4、Gate2 prepare/save各4、Gate2 verify直连1、screen12、inspect5、mapping2。profile含内部调用，不能把它们相加冒充45次直接调用。

187条嵌套完整观察逐层entry==原code profile：冻结prepare40、Gate1 verify27、旧load inspect19、normalizer4、loader4、P1 45、store.save8、store.verify37、screen3。三次SQL分别来自正常、报告writer晚变更、artifacts半写；四次normalize/loader仅建立这三个场景及HOLD前提。screen/inspect17次直接窗口内没有normalize/loader/store.save，5次inspect的SQL增量均0。新接收0；子进程内部核心次数null（本业务入口未启动子进程）。

局部核对 `task031_finalization_01/verify_local.py` 实际启动四个新Python进程，经测试 actual main replay：

- none：退出0/PASS/空failures。
- candidate-return：退出1/FAIL/1项failure，实际内容审核拒绝候选返回替换。
- ledger-late：末次语义消费后的原始字节循环中，真实读取返回后给台账追加LF，命中1，1786→1787B；退出1/FAIL/1项failure。
- checks-late：同边界给checks追加LF，命中1，2933→2934B；退出1/FAIL/1项failure。

末两项不是调用前改写；坏候选字节保留，不重建期望、不回填台账。完整argv/stdout/stderr/大小/SHA与注入读数见 closure_controls.json；replay源逐件SHA前后不变。四进程新增业务调用0，45/187是被重放的历史观察，不称本轮新调用。

## 6. 材料、路径与未执行

只读复用 `data/batches/task027r1_run_04/batch_normal`，工作簿SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`；没有新接收。人类字段取已登记TASK-030相同夹具：BASE2 submission 所在fixture_values.json SHA `6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337`、HOLD片段SHA `8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa`，不生成人员/时间/原因/event_id。只替换本次技术request/batch/material/prior绑定。

本轮根为测试 task031_setup_01、task031_run_01、task031_finalization_01 和四 task031_cli_*；运行/G1/G2/SQLite各 task031_run_01。四完整前提场景normal/hold/writer_late/half_artifacts，另有仅登记/空输出路径反例existing_empty。没有重跑旧大套件；旧测试仅作为只读复用helper导入，既有正常夹具/评审用于来源核对，不把引用称为新执行。

不递归删除、移动或清理任何探针/证据。仅在本轮允许场景内具名保全并精确恢复单文件；本轮自建注入failure单文件删去以恢复“原本不存在”，不删事件/目录，坏诊断原字节另存。锁目录原位保留；TASK-030具名偏差路径未动。

未执行复算/事实/真实初判/AI/终判/真实数据/网络/UI/ERP、0009、新链接、历史入口，按null+原因登记。受控映射、真实SQL执行、真实writer故障与旧材料读取分开，没有新增协议/CLI/物理生产模块。

## 7. 保护、历史事故与交接

代码、测试、指南、回执与局部核对定稿后执行一次最终全树扫描：`task031_finalization_01/scan_protection.py`，结果在 protection_result.json；最终实测数与完整SHA以该文件及delivery.json为准，不预填扫描数字。只允许既有runtime变化；新增根先展开确切文件名单，无目录前缀兜底，基线自身/review_result仅以两条确切路径列为先前评审元数据。扫描后仅有限发布本轮delivery元数据。

139历史缺失继续单列，不恢复、不造证；27精确恢复、R5越界326项、R1命名19项须逐项不变。TASK-030首轮移动不追认，其现位置 `data/runtime/task030_run_01/normal.gate2.lock.preserved_probe/lock.json` 为41B / `c78006d55489a9ad1b10cc98a081c3bc8135858c5b9040b7d7d5079409cf0e47`，本轮只读冻结检查，不授权恢复、不移动、不执行。

本轮正常业务入口首跑通过，没有为局部失败重跑业务链。最终扫描前局部核对脚本将canonical_json_bytes/fingerprint排除出“十个业务公开API”计数，执行前纠正，未影响实现或产生失败扫描。看板认证入口没有可用会话，本轮未操作看板，不把交付写成in_review已操作。

真实批次批准仍null，开发宿主0008、next/AI=false。RT_RULE_SCREEN_RECORDED仅登记本层规则报告；线索不是审计结论，夹具APPROVE不批准真实批次。全部交付后停止实施，待独立架构验收，不推进复算、事实或下一任务。
