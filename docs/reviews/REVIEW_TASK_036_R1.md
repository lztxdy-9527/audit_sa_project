# TASK-036-R1 独立验收：通过

日期：2026-10-16。技术结论 **ACCEPTED**，以本轮review_result.json最终保护确认发布为准。B1/B2关闭，接受TASK-036修正后的独立快照保存及只读核验，scope仍STORED_SNAPSHOTS_ONLY；不包含完整历史发现、运行接线或真实初判业务状态。未修改实现、交付测试、既有指南或看板，没有子Agent、执行会话、跨会话指令或清理。

评审根：`data/reviews/task036r1_gpt_20261016_193749/`。最终交付为 `data/human_initial_judgment_store_tests/task036_r1_finalization_01/delivery.json`，最终观察为task036_r1_run_02。setup_01/run_01保留失败过程，setup_02修前4/4、定稿42/17、本轮18/10和四replay新增0分列，旧TASK-036拒绝及观察快照不回写。

## 1. 身份与差异

三件同缓冲长度/SHA与delivery逐项一致：

- 存储模块25787 B / `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`。
- 测试38400 B / `68c802e6ea1872acc67d4021bc1c3119039fa6298b248328a8576c5eefd3c66a`。
- 新回执12573 B / `1c4d8fcf24be2f486709ba4edfab366b9f8bb1e0a2d1ac62b2db4a212c4e7afc`。

修前保全字节与TASK-036最终交付身份精确一致；逐定义AST差异仅 `_resolve_leaf`、`_write_failure`，唯一赋值变化为STORE_VERSION从1.0变1.1。API/异常类/其他函数、manifest/failure协议常量及成功返回构造不变。源差异保存在store_diff.patch，当前测试main AST未改变。冻结初判核心1.1、正式契约/登记/协议/案例、运行层及任务卡身份核对通过；旧指南/回执保留原1.0时点，新补丁不修改旧快照或凭证。

## 2. 完整旧证据与本轮真实复验

最终84项检查、42条公开存储调用（save21/verify21）、17条核心观察与定稿expected_observations完整内容规范一致，七项台账逐项实读长度/SHA；父调用、实际代码对象增量、公开输入与核心实际消费输入三时点同引用闭合。13份成功核心返回按协议由评审端另写构造完整比较，正常十一键返回与执行端独立预期一致。四个raw控制及diagnostic_clock的实际观测原文另外逐项读取。

本轮新脚本实际 **18次公开原代码对象调用（save8、verify10）、10次冻结核心原代码对象调用**，另1次私有raw-chain原代码对象控制，公开/核心增量0，分别记录。没有直接执行旧评审脚本或写旧根；参考定义在新根适配、编译后执行。完整输入/预期/返回或异常、直接cause/secondary、三时点和文件场景见independent_observations.json、verification_summary.json。

**B1关闭。** 原路径在构造绝对链时保留alias/..段，原始lstat检查先于resolve。独立绝对/相对save、绝对/相对verify四例均真实消费alias段一次，准确Blocked(out_dir/record_dir)、核心0、save目标未建；私有对照单独命中1，不混作公开调用。正常绝对和相对save/verify均成功、各核心1。源码对drive-relative仅取得盘当前目录作为基座，不规范化调用方的原始段。

**B2关闭。** 真实xb句柄半写并flush后抛主OSError；成功manifest登记真实返回，第二次失败诊断登记抛受控OSError。公开仍为原HumanInitialJudgmentStoreError(stage=write.expectations.json)，reason/reasons恰为原主错误，直接cause仍主OSError，secondary保留诊断时间故障；未编造failure或时间。撤销注入后不完整目录verify拒绝、核心0且只读。整个诊断构建、原因链、登记、编码/写入都在secondary保护内。链helper后备仅静态核对，动态数null，不冒称已测。

正常六文件及十一键返回另按定稿输入/独立核心记录/六件实际源字节重新构造，与存储字节完整一致；运行变值为已存程序技术时间，格式/来源核对，人类时间不生成。真实半写/有效failure优先、核心精确Blocked、完整返回构建后的晚变更本次拒绝→撤销wrapper保留坏字节仍拒绝→本轮单文件精确恢复后成功均保持。旧store绑定声明在新自建场景拒绝、核心0，不修改或执行旧记录迁移。core八false、store九false、FILE/FP、原人类字段及无输入别名保持。

## 3. main、缺口、过程与保护

四个当前交付main新进程只读replay定稿源，实际退出码 **0/1/1/1**。stdout末次结果、summary/failures与返回码一致；candidate-return内容审核拒绝，ledger/checks晚变更各命中1、加一个LF并触发末次bytes_ok=false。逐进程全部项目scripts函数profile，新增业务调用均实测0，源全部SHA不变。旧42/17只作回放载荷，坏字节保留；见closure_controls.json及新task036_r1_review_cli_*_193749根。

物理junction仍null+既有OS权限拒绝，无重试；合成元数据不称物理动态通过，按原卡允许保留，不阻断本次两项修复接受。额外合法闰日/±14人类正例、链helper后备动态故障、完整历史/运行层/真实业务/AI等未执行项均按范围和实际原因单列。

setup_01路径证据编码落盘失败、run_01 relpath消段控制失败保留，正式依据为新根完整setup_02/run_02。本轮一次只读元数据探针误取observed字段，实际为observed_baseline；metadata_probe.json记录，无业务调用或文件写入，随后有限按实际字段完成审核，没有重复业务链或全树扫描。

局部定稿后仅一次全树扫描，双口径核对：TASK-036观察快照167210项/SHA `d122a56245cb2800fbd76759ee748dbe85dc77304534d449bc84ec0f28c46494` 仅两份授权变化；TASK-035-R1接受基线166390项/SHA `63ba73224065bdcdf53538b58a23d966ab6469aed8cdf7330445846828005948` 既有冻结项changed=[]。新missing/范围外变化或新增/读取错误/身份漂移均须0才发布接受。确切新增逐路径登记、扫描后自身元数据有限登记，无目录前缀豁免。最终实测及新接受快照SHA/项数见protection_result.json/source_hashes_after.json/review_result.json。

139历史损失分列，27恢复、326越界、19命名偏差、TASK-030具名41 B锁及全部旧失败现场保持，不追认、恢复、重建、移动、清理或执行。

## 4. 下一卡、夹具登记与边界

下一卡 `docs/tasks/TASK-037_DRAFT.md` 仅建设显式声明命名域的只读完整快照核验/历史索引：真实调用当前冻结store verify，从完整核验返回提取协议四字段索引，核对名单与已声明历史引用闭合，不接运行层、不保存索引或新初判。现存快照的有界枚举不能证明历史从未删失，更不认证身份；该限制必须保留。

人类本轮明确回复“提供 event_id=\"2\"，其余五项沿首份夹具”。已登记human_history_fixture_supplement.json，1728 B / SHA `e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a`：event_id="2"，actor_id/declaration_note="1"，decided_at_raw="2026-10-16"、assessment="通过"、reason="无明显不一致且合规"。原问题/回复及首份来源SHA保留，只用于TASK-037合成多记录测试，八项权限全false，不是业务批准或真实初判，不补时间/时区。

当前真实批准null、真实独立初判未保存、开发宿主0008、next/AI=false。技术快照/VALIDATED/本次验收不批准真实批次、不认证身份、不形成审计结论。下一卡尚未实施，看板由人类办理。
