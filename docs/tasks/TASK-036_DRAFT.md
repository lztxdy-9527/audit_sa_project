# TASK-036：独立人类初判快照保存与只读核验

状态：Architect制定；以前置 `data/reviews/task035r1_gpt_20261016_132048/review_result.json` 为ACCEPTED正式发布为准。分类C，由执行端实施、Architect独立验收。只建设独立存储组件，**STORED_SNAPSHOTS_ONLY**；不接运行层、不做完整历史发现或真实初判业务保存、不开放AI。看板由人类办理。

## 1. 依据、身份与唯一允许范围

先读本卡、`docs/reviews/REVIEW_TASK_035_R1.md`、同根review_result及其新接受快照，再读TASK-034初判协议/案例、冻结初判核心和现有Gate快照存储的相关小型模式。不得执行旧业务套件或旧评审脚本写旧根。

冻结核心 `scripts/build_demo_human_initial_judgment.py`：28927 B / SHA `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`，CORE_VERSION=`TASK-035-human-initial-judgment-core-1.1`。入口 `build_human_initial_judgment_record(submission, materials, expectations, *, prior_history=None)`。本卡不修改它；TASK-034协议对象版本保持。冻结当前测试43985 B / SHA `9b003d983251f4b50e5db1f5992fd6ca33e6d3b570430d9b57e9b94cb2e805dd`，不改既有指南/回执。

正式契约SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`；有效登记 `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md` SHA `042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`。协议SHA `df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe`、案例SHA `e02e1f49e16ebff6a3b683e4c76ece6dd81697569e4876d090a4cccb67d07d46`。运行适配器264105 B / SHA `65946ffd740771c3917297d5d566c147c641004547fbbbb71873d5b53898e78a`，十四项代码清单/16运行API冻结；本组件不进入当前运行登记，不改旧凭证适配新代码。

**仅允许新增**：

- `scripts/store_demo_human_initial_judgment.py`。
- `tests/test_store_demo_human_initial_judgment.py`。
- `docs/HUMAN_INITIAL_JUDGMENT_STORE_GUIDE.md`。
- `docs/EXEC_REPORT_036.md`。
- `data/human_initial_judgment_store_tests/task036_*` 本轮测试/交付根。
- `data/human_initial_judgment_records/task036_*` 本轮合成存储场景根及具名叶目录。

所有既有文件冻结，包括本卡、新接受快照、核心、Gate存储、运行层、历史失败/锁/证据。新增在授权根内逐个展开确切路径登记，不能用目录前缀兜底。不得复制通用框架、重构或添加生产CLI/UI/DB/新依赖。使用Windows/PowerShell及 `.venv\Scripts\python.exe -B`。若需越界或分类升级，停止该级处理并报告Architect。

## 2. 接口与范围语义

公开业务API仅两项：

```python
save_human_initial_judgment_snapshots(
    submission: dict, materials: dict, expectations: dict,
    *, prior_history: dict | None = None, out_dir,
) -> dict
verify_human_initial_judgment_snapshots(record_dir) -> dict
```

save接收四个内存对象，调用冻结核心**恰一次**，原样保存收到的对象快照及完整核心返回；不从提交刷新预期，不补历史，不生成任何人类字段。verify对一份既存快照真实只读恢复，调用同一冻结核心恰一次，完整比较两键返回；不能仅比较自报record_fingerprint或manifest摘要。verify可复算纯核心，不调用save、上游算法、运行层/Gate/fact入口、旧模拟初判或其他业务核心。

本组件验证的是**一份已存对象快照**及其与当前冻结组件的关系；不实读 materials.files 中业务路径，不认证身份或证明来源真实，不发现全局/当前完整历史。prior_history原样保存并由核心检验声明/独立FP，不能把declared_complete=true称为本组件已枚举完整历史。本卡不提取/发布“已核验历史索引”。未来适配层必须先用本verify核验历史完整四输入和返回，真实完整枚举后才可提取核心协议四字段索引；完整性、去重和同批首版政策不能靠本卡目录存在冒充。

原核心record及其八false边界逐字保留，record_status仍HUMAN_INITIAL_JUDGMENT_VALIDATED；物理保存事实仅由存储层status/manifest表达，绝不把record.boundaries.persisted改true。冻结事实packet/Markdown的“尚未保存判断”等历史模板不回写。当前真实初判仍未保存；本卡仅以登记的合成夹具开展技术存储测试。

## 3. 固定文件、封闭manifest与返回

成功叶目录恰六份文件，无子目录/其他成员：`expectations.json`、`judgment_result.json`、`materials.json`、`prior_history.json`、`submission.json`、`manifest.json`。前五份分别是收到的三输入、历史对象、完整 `{record,record_fingerprint}` 返回。各为规范JSON UTF-8字节加一个LF；规范规则与核心一致，类型敏感。只承诺对象快照和人类字符串原文，不宣称保留外部JSON文件排版/BOM/换行。

manifest恰九键，版本/状态固定：

- manifest_version=`TASK-036-human-initial-judgment-store-manifest-1.0`；store_status=`HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED`；scope=`STORED_SNAPSHOTS_ONLY`。
- identity恰 `{batch_id,event_id,request_id}`，来自已验证本次输入及record.binding/人类提交，精确原字符串闭合，不从目录名推断。
- component_bindings恰 `{core_file_sha256,store_file_sha256,protocol_file_sha256,cases_file_sha256,contract_file_sha256,contract_effective_record_file_sha256}`。五份外部冻结身份见§1，自身SHA实读本次源缓冲，不自嵌固定位。六件均与操作开始读数及本次结束确认闭合；代码变化拒绝旧快照，不改旧manifest迁移/补签。
- fingerprints恰 `{submission_fingerprint,materials_snapshot_fingerprint,materials_body_fingerprint,expectations_fingerprint,prior_history_fingerprint,record_fingerprint,binding_fingerprint}`。前几项分别FP(原输入对象)、FP(完整materials)、协议唯一九键正文M、FP(expectations)、FP(prior_history)、FP(record)、FP(record.binding)；不混同FILE或完整核心返回FP。
- payloads恰五项，按relative UTF-8升序，relative恰上述五个payload文件名，各成员恰 `{relative,byte_size,file_sha256,object_fingerprint}`。FILE/长度/对象解析来自同一实际缓冲，object_fingerprint=FP(该文件解析对象)。名单双向完整、唯一、整数类型严格；manifest不列自身，避免自指。
- technical_registration恰 `{registered_at_utc,source}`。source=`PROGRAM_GENERATED_TECHNICAL`，时间为保存程序生成的UTC秒精度 `YYYY-MM-DDThh:mm:ss+00:00`。只登记技术保存时点，与人类decided_at_raw分开；不写回人类时间、不推断先后。verify复用其已存原值，不读时钟生成新时间。
- boundaries恰九键 `workflow_connected/execution_allowed/next_step_allowed/ai_enabled/identity_authenticated/source_authenticity_proven/audit_conclusion_formed/final_judgment_recorded/complete_history_verified`，全严格false。

成功返回恰十一键 `{status,scope,identity,record_fingerprint,manifest_file_sha256,technical_registration,component_bindings,files,boundaries,snapshots,judgment_result}`。save的status=`HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED`，verify的status=`HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED`，其余与本次已核验内容精确闭合。snapshots恰 `{submission,materials,expectations,prior_history}`；judgment_result为完整两键核心返回，均为独立深拷贝。files恰六项，与payload项同四键格式、按relative升序，另含manifest实际FILE/长度/FP；manifest_file_sha256来自同一缓冲。scope/boundaries同manifest，所有成功载荷在末次确认前构建完，不在确认后重读刷新预期。

## 4. 保存、恢复、异常和末次确认

输出必须显式提供 `data/human_initial_judgment_records/` 的严格后代叶目录，不从人类ID拼接路径，不允许根本身、已有空目录/文件/成功或失败目录。Windows原始路径链和叶成员拒绝符号链接/reparse点；不要resolve后绕过原始链检查。只在本轮task036具名根建立测试场景，不触碰既有记录。

调用前实读并核对六件组件身份，冻结候选快照/独立预期；所有纯核心拒绝及路径前提失败在新叶建立前完成。非法输入应保持核心精确Blocked而非预先序列化变成内部Error。核心只一次，不靠先调用后再调用来修复快照。接收输入在进入前/返回后/本调用收尾不变、无输入别名。代码在核心前晚变更须本次拒绝、核心增量0、输出未建。

成功用独占mkdir建立从未存在叶目录、每文件独占二进制句柄写入；读回逐字节/长度/SHA/对象比较本次writer缓冲。禁止覆盖、原子替换既有文件、重试续写、删除或自动清理失败半文件。组件/文件/目录末次确认失败不能返回成功。

异常类为 `HumanInitialJudgmentStoreBlocked(field,reason)` 与 `HumanInitialJudgmentStoreError(stage,reason)`，均有reasons=[reason]。核心Blocked保留精确field/reason并 `raise ... from exc`；核心Error/真正I/O错误保留准确stage/原错误说明和cause，不一律Blocked。叶目录建立后失败仅在该新叶独占尝试写 `failure.json`，关闭实际写句柄后再处理失败；失败写诊断不能覆盖原主因。失败文件封闭schema在实现前静态定稿并写入新指南/证据：至少固定failure_version=`TASK-036-human-initial-judgment-store-failure-1.0`、scope、identity、stage、classification、field或null、reason、实际exception_type、cause_chain和单独技术登记时间；不得包含编造的人类字段或成功许可。

verify先查原始路径安全和failure；有效failure优先于成功manifest、半写或坏payload，核心调用0。failure坏格式也拒绝，不能忽略继续成功。verify全程不写failure/日志/补文件、不保存、不生成时间，不修复任何字节；仅允许其调用方在测试证据根记录观察。

verify操作开始一次读取六文件为固定缓冲，解析对象/长度/FILE/FP分列；核对封闭名单、manifest/身份/全部内层摘要与组件、核心完整返回。保存/核验最后必要消费后、成功返回前，重新实读组件/固定六文件及目录集合/无failure，分别比较**操作开始读数或本次writer原缓冲**；不得末次重采集并自比。保留最小可定点注入的消费后接缝，不新增通用钩子框架。构建完整返回后也要纳入末次确认，不在确认后执行保存/读取/刷新预期。

## 5. 有限测试与证据闭合

仅用已有登记人类字段，身份/事件/时间/assessment/reason不得生成。可只读复用TASK-035-R1技术材料及现有已核对夹具（首份SHA `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`、supplement_02 SHA `36dcbeb2ff2ebf0ded07608df63008052ce67cf53e6991950a7f9f3a6e0ac2d7`、supplement_03 SHA `3ff0a6cc844643a92ca5b2438d6df2bc6d1be260f19eb6ad8e21a162eccb8424`），先保全原字节/来源/用途，PROTOCOL_TEST_FIXTURE_ONLY标签放协议对象之外。合成技术绑定/投影不是实际Gate或历史核验；指令样式文本只作数据。额外合法闰日/±14正例继续null+原因，本卡不要求新造人类值。

按必要问题族分组，不追求数量、不重建业务链：

1. 正常save+独立verify：六件完整缓冲、完整返回与独立预期一致，每次核心恰1；原人类文本/时间、八false核心边界、九false存储边界、原输入三时点、深拷贝和独立技术时间闭合。明确verify复算核心属于本卡设计，不误用TASK-032禁止复算的inspect规则。
2. 核心协议负例（取B1与一个独立关系/历史None即可）精确类/field/cause、核心1、叶未建；代码/契约身份在核心前晚变更核心0、输出未建。注入仅本轮自建临时组件副本/明确接缝，不改冻结生产核心或契约字节。
3. 路径越界、原始链reparse、目标已有空/成功/失败目录拒绝且旧字节不变；不重复历史路径大矩阵。Windows若创建reparse确需外部权限且未获授权，写null+真实限制，不冒称测得通过。
4. 真实独占句柄半写后抛OSError，保留半文件/实际异常stage及cause，failure原主因优先；有效failure与坏manifest/半payload并存时verify核心0且失败优先，verify不写failure。
5. 六件缺/多/子目录、摘要/长度/类型错（False/0、0/0.0）、FILE与对象FP混用、身份或组件错；候选完整核心返回改正文并同步自报FP/manifest/文件SHA，真实核心复算仍拒绝，不能自比凑通过。
6. 最后必要消费后的报告/输入文件晚变更，本次verify拒绝；撤销wrapper保留坏字节仍拒绝，仅精确恢复**本轮自建单文件**原件后成功。坏字节具名保全，旧记录不修复。另保存收尾晚变更拒绝不返回成功，原writer缓冲约束真实生效。
7. 全部公开API实际原代码对象、嵌套纯核心原代码对象分列；完整参数/返回或异常、父调用、真实引用三时点。禁止以wrapper数、旧观察或登记条数冒充实际调用。未执行项null+原因。
8. 测试只读复用已验收短观察/收尾helper，不复制通用框架、不执行旧run/main。先冻结独立完整预期，再对候选完整内容、台账实际读回、末次原始字节核对；这些真实支配最外层main返回码/summary/failures。四个实际main新进程replay为0/1/1/1，新增save/verify/纯核心/其他业务调用均由原代码对象profile实测0；源只读，坏字节保留。

生产模块不加CLI。仅测试入口 `.venv\Scripts\python.exe -B tests\test_store_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_store_tests\task036_<新名>`；输出从未存在。保存场景同为从未存在具名目录，禁止覆盖旧输出。无需重跑纯核心全部156项或旧Gate/运行/SQL/复算/事实套件。

## 6. 定稿保护、交付与停止

先局部定稿实现/测试/新指南/回执/证据，再一次全树保护扫描，以本轮TASK-035-R1新接受快照为基线。既有changed=[]、新missing/读取错误/范围外新增/身份漂移均0；新增先展开确切路径，接受快照自身/review_result两条元数据单列，扫描后自身元数据有限确切登记，不能用目录前缀豁免未知文件。139历史损失单列；27恢复、326越界、19命名偏差、TASK-03041 B锁偏差及旧失败现场保持，不追认、恢复、移动、清理或递归删除。

回执与delivery登记四交付件长度/SHA、明确scope/不验证完整历史、核心冻结身份、完整观察/实际调用/四CLI、保护结果、原件与坏字节身份及未执行项。技术时间不是人类时间，物理快照不是业务初判状态。交付后停止，待Architect独立验收，不自行推进运行接线或下一任务。

固定业务样本/金额/原ID/主表与分摊边界、线索非结论保持。正式契约V1已生效；D2/D3授权建设合成初判保存校验，不授权批次批准/强认证/真实数据/AI/终判。开发宿主仍0008，真实批准null、真实初判未保存、next/AI=false。本卡未实施；技术验收和保存能力均不批准真实批次。
