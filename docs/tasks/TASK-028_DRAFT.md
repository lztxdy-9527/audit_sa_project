# TASK-028：Gate1 核验后的标准化与 SQLite 装载接入

类型C：GPT制定接线与边界，DSH实施。本卡只完成计算阶段，停在RT_NORMALIZED；Gate2材料请求与决定下一卡。先建看板再实施，完成全部交付才in_review，done由人类操作。执行端完成本卡停止实施，下一卡由GPT验收后继续制定。

## 1. 前提与允许范围

以 `docs/reviews/REVIEW_TASK_027_R2.md` 与 `data/reviews/task027_r2_gpt_20261015_173156/review_result.json` 的当前GPT修复版ACCEPTED为前提，先核对同根source_hashes_after.json及最终身份。原DSH提交不是直接通过。正式契约V1及D1/D2/D3既有授权继续有效，不重新征求，不代表批准任何批次。

只允许修改scripts/runtime_gate1.py（起点111301 B / `336cf30e791a2f325f50fdef3a63dde94c70baf5f7546f0035ec0d6759dac79f`）。本卡使用下列专属指南，不改任何冻结旧指南。

新增tests/test_runtime_approved_load.py、docs/RUNTIME_APPROVED_LOAD_GUIDE.md、docs/EXEC_REPORT_028.md。本卡严格最终只修改runtime_gate1.py一个既有文件；不修改任何旧测试/指南/回执。测试根：data/runtime_approved_load_tests/task028_<轮次>/；运行根data/runtime/task028_<轮次>/；新Gate1测试记录根data/human_gate_decision_records/gate1/task028_<轮次>/；数据库根data/sqlite_tests/task028_<轮次>/。只有确有必要重新接收时才允许data/batches/task028_<轮次>/，默认只读复用已核验小样，实际次数如实登记。

冻结初判/Gate1准备器/P1/store/控制器/宿主/业务核心/契约/配置/全部旧证据；特别冻结：

- normalizer `a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310`；SQLite核心 `1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446`；schema `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205`。
- TASK-027当前测试 `66b82df9888efa499eee44f3af071aa75955680f8573f4386e5973e714afc4d4`、指南 `b6759e6f5a7de4c625a09cb43f8173d522a6dc5585ad940a8e0321437283e88b`，以及TASK-026已验收测试/指南。

139历史损失、27恢复、R5越界326项及R1偏差19文件不重建、不追认、不清理。身份不符或须扩大权限/修改冻结核心，停止并升级，不自行扩域。

## 2. 物理接线与公开 API

仍只在runtime_gate1.py扩展，代码清单保持14项、共享运行绑定仍六项，不新增生产模块。实现版本升TASK-028-runtime-gate1-1.0；旧协议与五个API不改名、不改输出、不放宽前提。代码改动即新运行版本，测试创建新登记和Gate1事件，不迁移旧登记。

设计§6.1目录归属在本卡明确为：runtime_dir仍是**不可扩充的二文件登记叶**；计算输出位于其同级固定目录 `runtime_dir.with_name(runtime_dir.name + ".load")`，以下称load_dir。技术名来自已核验调用方runtime路径，不从业务ID拼路径。这样计算产物不会使已有Gate1核验因登记叶未知项而失效。

新增且仅新增两个公开API，无CLI：

```python
run_gate1_approved_load(batch_dir, runtime_dir, *, scope_dir, event_relative, database_path)
inspect_gate1_approved_load(batch_dir, runtime_dir, *, scope_dir, event_relative, database_path)
```

二者成功均恰六键：stage_version/status/batch_id/run_binding_sha256/artifacts/boundaries。stage_version=`TASK-028-approved-load-1.0`，status=`RT_NORMALIZED`。boundaries封闭八键且严格false：gate2_approved、screening_allowed、ai_enabled、initial_judgment_recorded、audit_conclusion_formed、identity_authenticated、source_authenticity_proven、next_step_allowed。不能把normalizer/SQLite通过改称审计结论或Gate2批准。

run真正调用两冻结核心各一次；inspect只读，不调用normalizer/loader，不写failure，不修复现场。两者都必须自己真实调用现有verify_gate1_effective_approval，严格要求effective is True、decision=APPROVE、actor_kind=HUMAN_DECLARED、reasons为空；不接受调用方status/approved，也不调用开发控制器伪造放行。合法HOLD/REJECT、缺记录、错绑定、失败/锁或材料变化时，计算核心增量0。

## 3. 路径、对象和保存顺序

load_dir须从未存在（含空目录拒绝），用独占mkdir作为单次计算的唯一写入点；同runtime登记不能换输出目录重复计算。数据库database_path显式提供，只允许data/sqlite_tests严格后代的固定文件名runtime.sqlite3，所在叶目录必须从未存在，由本层在批准前提核验通过后独占创建；上级本轮根可预建。拒绝与来源、登记、事件、load_dir相等或互为祖先，逐级查reparse再核对解析路径。已存在库、staging、未知项拒绝；不扩大冻结SQLite核心允许根。

执行顺序固定：

1. 实读核验参数/登记/当前来源/Gate1事件，保存同缓冲字节与对象读数；真实Gate1核验通过后再准备计算输出。前提/路径拒绝不建load_dir/数据库目录。
2. 独占建load_dir，写started.json并精确读回。不得生成新的actor/人类时间/原因/决定/event_id。
3. 每次调用计算核心之前复确认已消费的来源/Gate1/登记字节仍等于起始读数，再真实调用 `normalize_workbook(batch_dir / "source/input.xlsx", quality_report)` 一次。quality_report来自本次同缓冲读取且与Gate1材料绑定一致；完整返回保持不改，调用前后验证其消费输入未变。
4. 按确切canonical UTF-8+单LF独占写normalized.json并读回；真实调用 `load_normalized_to_sqlite(normalized, database_path)` 一次。只传本次真实标准化对象和显式新路径，不传答案册/规则筛查/开发批准。
5. 保存并读回该次完整load_report。要求DEV_SQLITE_VERIFIED、冻结版本/模式、next_step_allowed严格false、输入及normalized_payload_sha256闭合；实读数据库字节与报告database_sha256相等。四表行数用只读SQL与标准化records/报告交叉核对；不复制核心整套勾稽算法。
6. 复核当前Gate1仍有效、共享运行绑定未变；最后独占写artifacts.json并读回。全部必要语义消费结束后，按起始读数/本次writer缓冲/核心返回绑定复确认来源、登记、事件、静态代码与本阶段文件、数据库字节/固定集合；通过才返回RT_NORMALIZED。末次确认后不再读取候选构造成功输出。

冻结normalizer返回NORMALIZATION_VERSION=TASK-004-normalized-1.1，SQLite STORE_VERSION=TASK-005-sqlite-load-1.2；保留其DEVELOPMENT_TEST_ONLY/next=false等原标记，不为了“真实流程”改冻结产物。运行层只说明当前合成计算已由具体Gate1前提约束。

## 4. 固定产物和只读恢复

load_dir成功恰四文件：started.json、normalized.json、load_report.json、artifacts.json，无failure/未知项。数据库单独位于上述既有允许根，成功目录只含runtime.sqlite3；冻结loader既有暂存发布动作按原实现执行，适配器/测试不得自行清理失败库或staging。

started封闭八键：started_version、batch_id、source_batch_relative、runtime_relative、scope_relative、event_relative、database_relative、bindings。版本TASK-028-approved-load-start-1.0；bindings封闭四键registry_file_sha256/gate1_record_file_sha256/gate1_record_fingerprint/run_binding（完整六项对象），都来自本次实读，不采信调用方摘要。

artifacts封闭十一键：artifacts_version、batch_id、run_binding_sha256、started_file_sha256、registry_file_sha256、gate1_record_file_sha256、gate1_record_fingerprint、normalized_file_sha256、normalized_payload_sha256、load_report_file_sha256、database。版本TASK-028-approved-load-artifacts-1.0；database恰relative/file_sha256/byte_size，路径与显式参数一致。规范对象指纹与文件字节SHA分列，不内嵌artifacts自身SHA。

失败时，仅在本次已建load_dir独占写failure.json，六键failure_version/kind/stage/field/reason/cause_chain；版本TASK-028-approved-load-failure-1.0，kind严格BLOCKED或ERROR。保留核心异常reasons和cause/context；诊断再失败保留主次原因。不要声称提交后数据库错误已回滚，不删除半写/旧文件/失败事实，不重试覆盖。尚未建目录时正常传播，不为诊断新造目录。

inspect先检查有效failure再解析其余文件（半写artifacts不得遮蔽诊断），按kind如实阻断。成功路径严格核对键集/类型/常量、相对路径/身份/摘要/来源关系、两个完整核心结果与数据库实读，并真实核验当前Gate1；已知产物存在不能放宽登记叶或scope模型。只读路径在全部语义消费之后做一次有界字节/集合/路径确认。

## 5. 最少验收与交付

默认只读复用C06b正常/自洽BLOCKED接收小样，按新运行代码创建本轮新登记及Gate1夹具事件。人类字段仅取原登记0001/0002/0003原文，测试标签在证据外层；不替人类生成批准。不要重跑TASK-027全套或冻结核心历史大组。

最低六组即可，不遍历全路径：

- 正常APPROVE→两核心各1次→四文件与数据库→只读inspect成功；本次完整返回与落盘规范相等、输入前后指纹真实取得；四表行数/整数分/缺失应付关联保留。没有规则命中或R02计算要求。
- HOLD及一个缺/错Gate1绑定对照：normalize/loader均0，目录/库未建；BLOCKED+APPROVE仍由既有Gate1规则拒绝，不制造放行。
- 重复/既有空load_dir/既有数据库父叶/越界三类代表路径拒绝且现场不变，不执行清理列表。链接无法实际建立就如实not_executed，不影响普通路径验证。
- 一次标准化Error映射及一次数据库已发布后Error映射（实际核心返回后受控抛异常，明确标注宿主注入）：分别loader0或已发布库保留；有效failure、恢复拒绝，不冒称测试了冻结核心自身所有失败分支。
- 新artifacts真实独占句柄半写，以及一个数据库/源材料晚变更：本次拒绝，坏字节/诊断保留，inspect只读拒绝。无需重跑冻结store writer故障组。
- 调用/返回/异常完整登记，单一profile按原函数code身份计数并分列Gate1核验内部P1/store与新两计算核心；inspect的normalize/loader计数0。小收尾复用已验收的独立内存预期、同缓冲、待写字节台账、末次确认；正常0/PASS，台账替换或晚字节漂移真实顶层1/FAIL。复用同次观察的新副本，不重建业务链。

代码/专属指南/新回执定稿后一次最终全树扫描，范围外变化/未知新增/新missing/读取错误0；旧139损失单列，27/326及已知偏差保持。新增按明确新根展开为确切路径，禁止前缀兜底与递归删除/移动。扫描后仅有限自有元数据登记。回执必须区分真实执行/映射注入/旧证据读取/未执行null与原因，实际新接收或额外回归不可写成0/未执行。

本卡不生成Gate2请求/决定、筛查/事实/初判/AI/终判、不接LLM/网络/UI/ERP、不修改开发宿主0001—0008、不新增0009。真实业务判断及批准仍由人类作出；本轮测试夹具不构成任何批次真实批准。
