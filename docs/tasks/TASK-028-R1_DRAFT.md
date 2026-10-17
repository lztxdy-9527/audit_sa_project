# TASK-028-R1：批准装载的绑定、恢复与测试收尾定点修正

类型 B，DSH 执行，GPT 验收。依据 docs/reviews/REVIEW_TASK_028.md。四组同类问题一次闭合；不设计新 Gate、不扩协议或新增框架。

## 1. 起点、允许修改与停止条件

先只读核对评审与 `data/reviews/task028_gpt_20261015_182926/review_result.json`、同根 source_hashes_after.json。当前是 NOT_ACCEPTED，禁止据此称原卡通过。只允许修改：

- scripts/runtime_gate1.py：143031 B / `067e24161d62fc2f3883d844e0dfe716e30f2fe7dcf2fd22fcfedb0ff69fc4e1`。
- tests/test_runtime_approved_load.py：43922 B / `0f9d44d93d9695fb652809502b996099bae8a6ca606ce3bd15657fa8fd39c05c`。
- docs/RUNTIME_APPROVED_LOAD_GUIDE.md（必要同步）：8918 B / `498cc568712d4ae6988e174dd960097091a911588e6ca7a3fa2a31956e4f6c1b`。

新增 docs/EXEC_REPORT_028_R1.md。仅允许本轮明示新根：data/runtime_approved_load_tests/task028r1_<轮次>/、data/runtime/task028r1_<轮次>/、data/human_gate_decision_records/gate1/task028r1_<轮次>/、data/sqlite_tests/task028r1_<轮次>/。scope 可在本轮记录根内设独立子目录。默认只读复用已核验 C06b 接收产物；本卡不授权新接收批次根。故障 harness 仅建在本轮新根，不改旧 harness/回执/证据。

生产补丁升 TASK-028-runtime-gate1-1.1，公开两个 API/六键成功外层/四件计算产物/六键 failure/八键 false 边界不改名、不新增字段、不改变单次计算模型。原五 API 的前提/协议不放宽；修复限定本卡新层与必要私有复用，不大重构老层。

冻结 TASK-026/027 测试及指南、准备器/P1/store、normalizer/SQLite/schema、契约/生效登记/配置、宿主/控制器和全部旧材料。冻结值按原 TASK-028 卡及本轮基线；任何身份不符或需改冻结件立即停止升级。139 历史损失、27 恢复、326 越界、旧命名偏差保留，不重建/不追认/不清理。禁止递归删除/移动。

先建任务卡再实施，完成全部交付再 in_review；done 由人类操作。完成本卡停止实施，不推进 TASK-029/Gate2/筛查/初判/AI/终判/0009。

## 2. B1：起始预期与最终字节/集合确认

保存与恢复各在操作开始固定已消费来源/登记/静态代码、Gate1 八文件（context/receipt/六快照）的同缓冲读数；Gate1 核验后与这些读数闭合。每次计算核心调用前复确认本次消费的来源/Gate1/登记仍相同。使用已有 capture/recheck/helper，不新造 I/O 框架。

数据库预期只能来自本次真实 load_report 绑定并已核验的数据库 capture；恢复取实际 capture 与报告/artifacts 闭合后保留至终端。输出预期来自本次待写缓冲及已核验读回。禁止 `_recheck_capture(_capture_file(...))` 式末端自比，禁止用较晚重新采集值覆盖初始预期。报告写后读回也须与该次 report_buffer 精确相等。

全部必要语义消费、Gate1 末次核验、结果对象构造结束后，只做有界原始字节/集合/路径确认：批次顶层与四子目录、登记叶恰二文件且无 failure、scope 恰单事件、事件 context/receipt/snapshots 恰固定集合、六快照无未知项/失败、锁不存在、load_dir 恰四文件/无 failure、数据库叶恰一文件、已消费路径逐级 reparse。之后不再读取候选/加载核心/复算业务来决定成功。

最低实测：一个新正常 APPROVE 小样；inspect 最后必要消费后 DB LF、context LF、decision_result LF 三个隔离反例各命中一次、本次 Blocked 且定位，撤销 wrapper 保留坏字节后仍拒绝（各自新副本或本轮自建场景，坏字节保存）。保存端真实 artifacts writer 返回后数据库 LF：本次拒绝、有本层 failure、坏库保留。一个晚新增 scope/快照未知项控制证明集合覆盖，其他集合可复用同 helper 的有限隔离核对，不遍历所有来源。

## 3. B2：完整字段闭合、严格类型与只读 SQL

先验对象/封闭键集/严格类型再消费，新层 started/artifacts/failure 每一字段都要校验或与本次独立预期精确比较：started.batch_id、所有路径/bindings；artifacts 的 registry/Gate1 两摘要、共享运行绑定、文件 SHA、规范对象 SHA、database 三键。所有 SHA 全串 64 小写 hex；byte_size/行数严格非负 int，bool/float 不能冒充。不能只检查“恰八/十一键”后忽略字段值。

normalized 的冻结版本/mode/next=false、source.input_sha256 与本次已绑定工作簿 SHA 闭合；load_report.source/run_metadata 中输入/标准化指纹与 normalized/本次材料闭合，版本/模式/next=false 及核心成功旗标（如 round_trip_exact/event_allocation_balanced/net_checks 等）按冻结返回语义严格验证。可调用冻结 `require_loadable` 等纯校验辅助（不调用 normalize/loader 进行恢复），不要重写完整勾稽算法。

必须用只读 SQLite 连接实际查询四业务表 count，与本次 normalized.records 长度及报告严格计数比较；结束关闭连接，再以已绑定库字节进行终端确认。无需复制核心全量金额/逐单元格复算，不扩成新数据库核验引擎。

最小反例复现评审九项中的相关字段：错 started.batch_id + 同步 started 文件 SHA；错 artifacts.registry_file_sha256；错 Gate1 指纹；同值 float byte_size；report.round_trip_exact=false + 同步文件 SHA；实际删一 allocations + 仅同步库/报告外层 SHA → 都须定位 Blocked。再加一项 normalized.source 错输入 SHA（同步直接派生指纹）拒绝、一个缺/未知嵌套键拒绝；正常键顺序不同的 canonical 等值对照通过。全部由本轮新场景隔离，不能改冻结来源。

## 4. B3：新层 I/O、真实异常类型与失败优先

目录创建、failure 读取等新 I/O 纳入明确阶段的错误边界，OSError → RuntimeGate1Error(stage)+cause；按本次实际目录创建事实决定能否独占写 failure，不删除失败目录/库，不为诊断新造目录。已建 load_dir 后数据库父叶创建失败也必须有可核验六键诊断；若诊断再失败，主/次错误均可见。不可把创建失败误报成成功或原生异常泄漏。

对实际加载模块上的 NormalizationBlocked/NormalizationError、SqliteLoadBlocked/SqliteLoadError 按真实类型明确映射；不能依赖这些类并不具备的 field/stage 属性来分类。Blocked → 本层 Blocked + kind=BLOCKED，Error/I/O → Error + kind=ERROR；原始 reasons 完整可追溯（保存在现有 reason/cause_chain 中即可，不新增 failure 字段），保留 cause/context。其他异常如实 Error，不吞错转成功。

inspect 先读取并核验 failure 的六键/常量/kind/类型再按有效诊断拒绝，不解析半写后续产物，不写诊断或修复；坏诊断本身定位 Blocked，读取 I/O 映射 Error。

最低控制：真实 mkdir 接缝 OSError（本次 load_dir 已建）→ Error、六键 failure、库叶未建、坏目录保留；用真实冻结异常类各注入一次 NormalizationBlocked / SqliteLoadBlocked（明确只测本层映射）→ Blocked，两个 reasons 均可查；一个非法 kind/非对象 failure 恢复拒绝。原真实 writer 半写/发布后 Error 路径只读引用旧证据，除代码触及该路径或发现退化不重跑整组。

## 5. E1：沿用已验收小收尾与实际输入观察

参照当前已验收 TASK-027 测试 finish 原则，限新测试收尾：独立内存真实观察在任何候选读取前冻结；同次读取绑定对象和字节；台账预期来自待写缓冲，台账自身确切字节也须实读核对并纳入末次确认；失败诊断先定稿后一次写定。末端后不再读候选 failures/summary 生成成功输出，使用已核验内存对象。任一失败支配真实 CLI 1 / 磁盘 FAIL / 非空 failures，坏候选不回填，不重建台账掩盖。

两个计算核心实际消费的 quality_report/normalized 引用，调用前和返回后及所属 API 收尾取得规范指纹；记录完整输入快照和真实返回/异常 traceback/cause/reasons。生产侧同样验证其内存输入未被核心改写。工作簿文件前后 SHA 另列，不能代替内存对象不变。单一 profile 按原代码身份计数/分列，新层完整观察与记录数闭合；只读 inspect 计算核心增量 0。不要扩展成全项目观察框架或大量复制旧测试。

用同一真实观察的新收尾副本、新进程 actual main/CLI 做 normal、真实审核返回后 ledger LF、原末次 failures 读取接缝后 checks LF（修复后该读取应不存在；在观察到的实际最后必要消费后等价注入）、返回载荷替换四个控制。normal0/PASS，三负向1/FAIL；不得按 mutate 标志直接判失败。输入不变辨识度用一项实际核心返回后同引用改写控制证明被真实正式审核拒绝，不把手填标志当证明。

## 6. 最终交付纪律

提供一个明确的小入口（可 --only r1）仅执行上述正向/反例与真实证据收尾，不重跑原 42 项或 TASK-026/027/核心历史整套。可在一个新正常场景上做已登记隔离副本，保留每个坏候选，减少重复建链；代码变化后用新登记/新事件，不复用旧运行版本。

先完成局部核对、代码/指南/回执定稿，最后一次完整保护扫描：changed 仅三个允许文件（指南非必改）、未知新增/新 missing/读取错误/范围外变化零；新增在明示根展开逐项路径，禁止前缀兜底。旧139/27/326/已知偏差单列；扫描后仅有限自有元数据登记。新回执区分真实核心执行/受控映射/旧证据读取/未执行 null，不回写旧回执。看板漏勾是记录事项，不能以重复业务链补偿。
