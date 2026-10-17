# TASK-023：Gate1真实文件材料与只读候审请求适配器

日期：2026-10-14。分类：**C类，GPT设计 + DSH执行**。本卡为P2下一阶段的材料来源接入，前提是 `docs/reviews/REVIEW_TASK_022_R4.md` 的ACCEPTED及其最终保护登记。人类操作看板；实施开始前建卡并记录范围。

## 1. 目标、授权及停止点

TASK-021的P1能验证内存声明，TASK-022能保存/恢复这些快照，但二者均不证明业务材料已从磁盘实读。本卡补上**Gate1实际文件 → 已核验材料 → 候审请求与独立预期**，使后续保存不必相信提交方自报的哈希。

本卡止于只读准备：不提交/保存任何Gate决定，不枚举历史记录、不默认完整空历史，不调用存储save/verify，不接开发宿主/控制器，不执行标准化/装载/筛查，不构造真实流程检查点或0009，不处理Gate2、真实初判、AI/终判。下一卡才设计决定保存及限定历史范围，之后再分别接线；不得以本卡输出的PREPARED或质量OK当作批准。

人类已允许合成数据、本地显式身份声明及可追溯记录的真实人工决策建设，D1/D2/D3不重问。正式V1已由人类建立并明确确认生效；这不批准任何批次。本卡不生成姓名、身份、事件ID、时间、决定或原因，不产出预填submission。

## 2. 文件范围与冻结依据

只允许新增：

- `scripts/prepare_demo_human_gate1.py`
- `tests/test_prepare_demo_human_gate1.py`
- `config/human_flow_v1.json`（仅固定合成业务范围，内容见§6；不是批准或放行配置）
- `docs/HUMAN_GATE1_REQUEST_GUIDE.md`
- `docs/EXEC_REPORT_023.md`
- 全新 `data/human_gate1_request_tests/task023_<唯一轮次>/`（测试输入副本、记录、隔离故障均限本轮）。
- 全新 `data/batches/task023_<同轮次>/`，仅用于真实接收器造最少接收/质量样本；不建workflow或SQLite。

**所有既有文件冻结，包括旧测试、回执、评审和数据。** 不初始化Git、不安装依赖、不清理旧现场。P1/存储/接收器/checker/宿主/控制器/规则/规范/契约均不得修改。

起点基线：`data/reviews/task022_r4_gpt_20261014_004745/source_hashes_after.json`；完整SHA/项数及两个确切自指元数据排除见同目录 `review_result.json`（须ACCEPTED）。先核验二者，不用旧NOT_ACCEPTED清单替代。

重点冻结身份：存储 `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7`；P1 `5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79`；宿主 `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`；控制器 `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`。其他冻结文件从上述已验收清单取独立预期，不从候选提交生成。

优先读正式契约、生效登记、P1协议§3/4/7/12、P1指南、存储指南、本卡；接收器的实际manifest/report及 `validate_report`，不得凭交接摘要猜字段。

## 3. 唯一公开入口与输出

`prepare_human_gate1_request(batch_dir, request_id) -> dict`。无CLI，无生产写文件接口；只用标准库及冻结接收器的只读 `validate_report(report)` helper。

异常 `HumanGate1RequestBlocked(field, reason)` 表示前提/协议/绑定/路径拒绝；`HumanGate1RequestError(stage, reason)` 表示I/O/加载等运行失败，`raise ... from exc` 保留cause。无原生AttributeError/TypeError/KeyError泄漏，不用捕获一切或默认值替代结构检查。无CLI退出码；测试套件自己的0/1/2另列。

`request_id`由调用方明确传入非空非纯空白字符串，原样保存；无自动UUID/时间。普通ID允许前导零、64位十六进制形状、指令样式文本，不strip/改大小写/转数字；batch_id取已核验manifest并与叶目录名精确一致。

成功外层**恰六键**：

- `request_version = "TASK-023-human-gate1-request-1.0"`
- `status = "HUMAN_GATE1_REQUEST_PREPARED"`
- `materials`：冻结P1协议的七键对象，gate=GATE1。
- `expectations`：冻结P1协议的八键对象，expected_gate=GATE1、expected_prior_gate1=null、expected_request_id为原输入。
- `evidence`：恰七键 `source_manifest_version, source_batch_status, source_receive_exit_code, source_description, source_scope, code_manifest, rules_manifest`；前五项来自同缓冲已核验manifest，来源说明原文保留且不作已验证业务事实。
- `boundaries`：恰七项严格false：`request_persisted, decision_recorded, execution_allowed, workflow_connected, ai_enabled, identity_authenticated, source_authenticity_proven`。

成功可返回质量OK或BLOCKED的候审材料；FAILED/不完整/读数矛盾不返回PREPARED。返回深拷贝无别名，调用方改返回不影响任何保留输入/后续调用。没有prior_history、submission或决定字段，不默认任何历史声明。

## 4. 接收材料来源与路径

接收来源必须为 `data/batches/` 严格后代中的**仅接收阶段目录**。原始绝对路径逐级（含允许根）检查link/junction/reparse，再resolve并复查，正常文件要求同样适用；拒越界/根自身/任何链接。拒含开发workflow、旧模拟决定、标准化、DB或下游产物的目录。本卡不从已到0008的旧批次/导出包回收材料，不迁移旧凭证。

合法接收目录固定恰八文件，子目录集合仅由这些路径推导：

`batch_manifest.json`、`gate1_packet.md`、`source/input.xlsx`、`checks/quality_report.json`、`logs/checker.stdout.txt`、`logs/checker.stderr.txt`、`code_snapshot/receive_demo_batch.py`、`code_snapshot/check_demo_data.py`。

这八份全部只读。生产API**不启动接收器/checker、不打开Excel重算、不导入生成器/答案册/宿主/控制器/任何下游核心**。测试准备阶段可用冻结接收器CLI建立新接收样本，内部checker真实运行须分列登记。

接收器仍是 `TASK-003-R2-batch-manifest-1.2`、mode=DEVELOPMENT_ONLY、contract_status=DRAFT_NOT_IN_FORCE。以上是接收工具的原始历史标签，不改写、不解释为正式流程批准。适配器复用的是原始快照及质量核验事实，正式契约另从§6实读绑定；不能把旧draft SHA当正式契约SHA。两项approval须null、next_step_allowed须严格false。

## 5. 接收证据核验与质量映射

八文件各第一次读缓冲同时取得字节长度、文件SHA与必要JSON对象。先类型检查再消费。冻结 `validate_report` 只调用报告结构验证，不执行其CLI；helper拒绝、加载错误均保留实际定位/原因，不复制Excel校验算法。

必须核对：manifest版本/批次/状态/严格退出整数；failure.stage=null、exceptions/material_write_failures/failure_reasons均空；report_validation attempted/valid/report_readable严格true、problems=[]；snapshot_written/snapshot_matches_source严格true；source_before/after_copy/after_check、snapshot_after_copy/after_check与实际input字节SHA全等；size与实际input长度一致。

checker attempted/started严格true；report/stdout/stderr/packet/code_snapshot各路径为上述固定路径，exists严格true、read_error=null、声明SHA与初始实际字节全等；代码快照与项目冻结接收器/checker字节SHA一致，before/end/stable/matches均闭合。report.workbook.sha256/size及report.checker.sha256必须与同次input/冻结checker一致，report.workbook.path须精确指向本次快照；manifest中的report_result、两项report哈希和matches标志亦闭合。读取只走本卡白名单，不能跟随manifest中的任意original_path/argv去读外部文件。不得用两个null相等代表已核验。

来源范围与固定配置逐项一致（manifest.expected_scope.as_of_date对应配置cutoff_date）；主体与完整性只能是项目合成设定，不推断业务真实性。

质量映射固定如下：

- READY必须receive/checker exit=0、report.result=pass、issues=[]、issue_counts_by_code={}，四表structural_block严格false且blocked_rows严格整数0；映射P1质量OK、三列表全空。
- BLOCKED_QUALITY必须receive/checker exit=1、report.result=issues_found、issues非空；映射P1质量BLOCKED。`MISSING_SHEET / REQUIRED_COLUMN_MISSING / DUPLICATE_COLUMN_NAME`进入structural_blockers，其余实际issue进入quality_blockers；verification_failures保持[]。
- 每条issue保留原对象canonical JSON；列表项唯一编码为 `issues[<8位十进制原索引>]:<该issue的canonical JSON>`，按UTF-8排序。保留全部原issue（含重复内容），不去重丢记录；issue索引为事实位置，不是人类事件ID。issue_counts_by_code须与实际issues按code统计严格相等、严格非负整数。四表行数/structural_block的类型及行数勾稽核对；缺失/矛盾不补零。
- FAILED_RUNTIME、exit=2、未知状态、报告不完整、路径/哈希/布尔/计数矛盾均拒绝，不伪造FAILED质量对象供APPROVE。合法质量问题仍能准备供未来HOLD/REJECT，不能一律把BLOCKED当运行错误。

R03缺失应付关联不是质量外键错误；本适配器只映射checker实际issues，不另加规则、筛除记录或算R01—R04。

## 6. 正式契约、运行与文件绑定

正式契约文件SHA固定 `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`、版本V1；生效登记 `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md` SHA `042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`。两份均实读并与独立冻结预期比较。formal contract_effective=true的依据为人类明确确认及登记，不从接收器旧标签、D2纪要或submission推断。正式契约原始生效时间不做Gate决定时间语法校验、不规范化。

新增固定配置恰七键，值为：config_version=`TASK-023-synthetic-human-flow-config-1.0`，company=`澄明商贸有限公司`，period_start=`2026-09-01`，period_end=`2026-09-30`，cutoff_date=`2026-09-30`，currency=`CNY`，synthetic_data=true。保存canonical JSON+单LF；API实读并严格核对对象与既定值，config.file_sha256取确切文件字节。禁止增加approval/执行开关/可覆写路径；生产API不接受调用方配置或expected哈希。

`code_manifest`恰 `{entries}`，成员恰 `{relative,file_sha256}`，实际项目相对路径如下13项，按UTF-8严格升序唯一：

`scripts/build_demo_fact_packet.py`、`scripts/build_demo_human_gate_decision.py`、`scripts/build_demo_initial_judgment.py`、`scripts/check_demo_data.py`、`scripts/control_demo_workflow.py`、`scripts/crosscheck_demo_rules.py`、`scripts/normalize_demo_data.py`、`scripts/prepare_demo_human_gate1.py`、`scripts/receive_demo_batch.py`、`scripts/run_demo_workflow.py`、`scripts/screen_demo_sqlite.py`、`scripts/store_demo_human_gate_decision.py`、`scripts/store_demo_sqlite.py`。

只实读这些文件，不导入/执行其中业务函数。既有项与验收基线冻结SHA核对；新adapter取本次初始实读并在结束复测。`run_binding.code.file_sha256`为本adapter单文件字节SHA；manifest_fingerprint为此code_manifest的规范指纹，两个值不可互换。

`rules_manifest`恰 `{version,entries}`，version=`TASK-006-rule-core-1.1`，entries为R01—R04升序，成员恰 `{rule_id,rule_version,relative,file_sha256}`；rule_version分别为 `TASK-006-R01-1.0`…`TASK-006-R04-1.0`，relative分别为 `sql/rules/r01.sql`…`r04.sql`。四份SQL实读、核对冻结SHA，不执行；run_binding.rules的version与此一致、manifest_fingerprint取此对象规范指纹。不得导入screening获取结果。

run_binding.input.file_sha256取同次input确切字节。另实读并冻结核对 `docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md`（接收器原依赖）、`sql/demo_schema.sql`。

`materials.files`固定**31项**：batch/前缀的八份接收文件，加project/前缀的13份代码、SPEC、旧draft、正式契约、生效登记、新配置、schema及四份SQL。relative只用上述逻辑名，不存绝对路径；成员三键为relative/file_sha256/byte_size，严格整数非bool、可为0（如空stderr）。按UTF-8升序唯一。

materials七键按P1协议组装；materials_fingerprint仅对删除顶层自身字段的正文canonical JSON计算。expectations八键从**本次实际读数及固定请求ID/契约/运行绑定**独立构造，expected_files为31项双向完整名单；不从submission/调用方材料/status或候选记录取预期。

此运行绑定描述TASK-023已实现的准备范围，不声称未来组件已存在。未来代码/清单/规则/配置/范围变化必须新批次、新请求；本卡不保证未来宿主兼容、不静默更新旧请求。

## 7. 固定消费与最终确认

路径及文件集合 → 全部31份初始同缓冲读数 → 结构与来源关系/helper验证 → 质量映射/契约/运行核验 → 组装完整输出及独立预期 → **全部必要消费后、返回成功前**再实读31文件并逐项与初始长度/字节SHA比较，重新确认路径集合和无链接。预期不得刷新为晚读值。无成功落盘、无failure写入、无源目录修改；任何变化本次即Blocked并指向文件。

读取/枚举/stat/加载helper失败各明确stage并保留cause，区别协议拒绝。最后一次确认的OSError也须Error，不泄漏原生异常。实现不需要泛化I/O框架、插件或异步系统。

## 8. 最小验收与证据

入口：`.venv\Scripts\python.exe -B tests\test_prepare_demo_human_gate1.py --out-dir data\human_gate1_request_tests\task023_<新名>`。先小样及必要负向，局部错误定点修正，最后一次完整本卡入口和一次最终保护扫描。不得为每个轻量反例重新造整条业务链。

1. 用冻结接收器在同轮新batch根构造**三个**仅接收样本：C06b正常；C06b新副本仅把一个币种改USD（质量阻断）；另一新副本仅删allocations工作表（结构阻断）。不改原fixture，真实记录receiver/checker命令、日志、返回和材料；没有标准化/DB/宿主链。
2. 公开prepare的正常/两类BLOCKED输出符合六/七/八键协议、31项实读字节、材料正文/运行清单指纹及全部关系。测试自行标准库canonical/哈希复算，不用生产helper当期望。相同输入重复调用完整规范相等，无别名；普通ID原文对照（含64hex形状）通过，无决定/身份/时间预填。
3. 兼容性只在测试直接调用冻结P1：正常材料+显式PROTOCOL_TEST_FIXTURE_ONLY测试submission及显式历史夹具可VALIDATED；BLOCKED材料HOLD可VALIDATED、APPROVE被真实P1拒绝。至少各一次并完整登记；不写任何决定叶目录，不把夹具说成人类提交。生产prepare的P1/存储调用必须0。P1历史完整性不由prepare声明。
4. 路径/类型负向：越界、根自身、带workflow的旧样本、真实junction/reparse、缺必需文件、非对象JSON、request_id空白/非字符串；同缓冲哈希/身份/严格bool/计数/报告状态/代码快照不一致各必要反例定位拒绝。禁止用一个提前错误遮蔽多个目标。固定项目文件保持原件；需要反例时包装真实reader并标为受控输入映射，不声称改了冻结磁盘。
5. 一个**真实源晚变更**：先无注入观察末次材料消费，再在最后必要消费返回原值后仅给新批次quality_report追加LF、不更新哈希；本次prepare即拒绝并指向文件。撤销wrapper保留变更仍拒绝；恢复仅本轮原件后成功。只读全程不写failure。一个末次实读OSError注入须Error+cause，不称真实磁盘故障。
6. prepare守卫：写文件/网络/子进程/六下游业务函数不得被调用；计数0且源/项目文件字节前后相等。不得禁止生产必要读取或用未覆盖io.open的守卫称完整读写观察。被调用helper/prepare/API/直接P1、receiver CLI及内部checker分列，子进程未知内部函数次数null。
7. 每次公开API/实际P1/helper与CLI保留完整输入或输入文件现场、完整返回/异常+traceback/cause链、实际计数和scope。真实观察预期在终审前定稿，终审同缓冲读回按canonical字节严格比较并最终实读确认；台账不内嵌自身SHA。至少一个删权威登记的隔离自测由真实audit拒绝；不为此再建业务链。审核失败必须支配suite返回非零/FAIL，未执行项null/not_executed，不默认零。

本卡不要求再建设复杂通用审核框架；可以在新测试内复用已证明有效的**模式**，不能修改旧测试或复制旧整套证据称新观察。正常与预期拒绝分列，使用清晰、有界的最终证据收尾。

## 9. 保护、回执与升级

全部文件定稿、定点与正常入口完成后一次最终全树比较：所有原有文件changed=[]，missing/读取错误/范围外新增0；新增按本卡确切文件和实际本轮根逐项登记，禁止目录前缀兜底豁免未知文件。新config是授权新增业务范围文件，其他批准/生效/运行配置不得创建。扫描后仅有限登记评审/回执身份，不改实现后仍称原扫描有效；错误尝试如实计次。

回执写起点/写后SHA、实际API/receiver/checker/P1/helper次数与来源、各组真实结果、31项来源及两类指纹、晚变更接缝、保护身份/次数、过程失败、未执行项和停止点。最终自身SHA只在交接消息给出，不反复写回自指。

如发现需要修改冻结接收器/P1/存储/宿主/契约、改变Gate时序/材料/历史范围/执行边界，或分类不适用，**立即停止受影响实施，保留现场、报告并重新定界/升级**；不得扩大范围继续。完成本卡后交GPT验收并停止实施。持续制定下一卡的授权属于架构端，不授权执行端自行接线。
