# TASK-030：Gate2 决定快照保存与只读核验

类型 C：Architect明确接线与证据边界，GPT执行端实施，Architect独立验收。D2已允许建设合成数据Gate1/Gate2决定保存；本卡不批准任何批次，不运行筛查或接执行放行。

## 1. 起点、允许范围与停止点

先只读核对 `docs/reviews/REVIEW_TASK_029.md` 和 `data/reviews/task029_gpt_20261015_220323/review_result.json`/同根source_hashes_after.json，必须ACCEPTED；完整快照SHA/项数取review_result，不能把待审交付当通过。

唯一允许修改的既有文件：`scripts/runtime_gate1.py`，164079 B / SHA `38168b0eda7a3c4a2e2a2c8dc4ca7c287b03507970afc374fc6004c91a62b515`。实现版本升 `TASK-030-runtime-gate1-1.0`；已有八公开API/协议/前提/固定集合保持。可作必要的小型内部helper参数化以复用捕获/物化/锁/快照绑定，不复制整套Gate1适配器、不新增框架或公开绕过开关。

仅新增 `tests/test_runtime_gate2_decision.py`、`docs/RUNTIME_GATE2_DECISION_GUIDE.md`、`docs/EXEC_REPORT_030.md`；本轮新根为：

- `data/runtime_gate2_decision_tests/task030_<轮次>/`。
- `data/runtime/task030_<轮次>/`。
- `data/human_gate_decision_records/gate1/task030_<轮次>/`。
- `data/human_gate_decision_records/gate2/task030_<轮次>/`。
- `data/sqlite_tests/task030_<轮次>/`。

只读复用现有合成批次。改代码即新运行版本，测试用新登记/新Gate1夹具事件/新装载；不更新旧凭证迎合新代码。冻结全部既有测试/指南、协议/设计正文、P1/store/准备器、计算核心/schema、正式契约/登记/配置、开发宿主/控制器及旧证据；不安装依赖、不重接收、不初始化Git、不递归删除/移动或清理探针。

本卡固定**一个Gate2事件**；不做追加/撤销/替换/修订历史、不做全局发现、不引入RT_G2_APPROVED或执行许可。发现需改冻结核心、扩大历史范围或业务授权，停止并升级，不通过扩大修改继续。

## 2. 两个公开API，无CLI

```python
save_runtime_gate2_decision(
    batch_dir, runtime_dir, request_id, submission, event_dir, *,
    scope_dir, event_relative, database_path
) -> {"record": ..., "record_fingerprint": ..., "event_relative": ...}

verify_runtime_gate2_decision(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
) -> {"record": ..., "record_fingerprint": ..., "event_relative": ...}
```

scope_dir/event_relative始终指向**Gate1**来源；event_dir/gate2_event_relative指向新Gate2输出，命名不得混用。成功恰三键，record为真实冻结P1的17键正文，指纹为该正文规范指纹，返回的event_relative为Gate2事件项目相对路径。verify全程只读，不写failure、不重复保存或批准。

错误沿用RuntimeGate1Blocked(field,reason)/RuntimeGate1Error(stage,reason)，保留原field/reason及cause/context；先验封闭形状和严格类型再消费，I/O映射不泄漏原生消费异常。不得以APPROVE文本直接生成effective/allowed=true。

## 3. 唯一目录与历史规则（架构裁决）

Gate1仍位于 `data/human_gate_decision_records/gate1/<suffix>/`，其scope恰原单事件，零改动。Gate2 scope唯一映射为 `data/human_gate_decision_records/gate2/<相同suffix>/`；suffix从经核验Gate1 scope相对gate1根的严格后代路径取得，不能由submission或任意目录名推断。Gate2事件固定该scope下`event_0001`，不得接收其他事件路径。

保存时Gate2 scope必须从未存在（含空目录拒绝），父命名空间可独占建立；所有路径逐级reparse/链接拒绝后resolve复查，拒越界/与批次或DB重叠。verify仅接受该确定路径和既有固定集合。每个成功事件恰context.json、receipt.json、snapshots/；snapshots恰冻结store六文件。

技术锁固定为登记叶同级 `<登记叶名>.gate2.lock`，与Gate1锁分开；独占取得，记录文件身份/内容，仅释放本次自建且身份未变的锁。已有锁不动；取得半写保留，主/次错误都报告。Gate2写入期间不修改登记叶恰两文件或load_dir恰四文件规则。

P1前序唯一来自**本次真实核验的完整Gate1记录**，wrapper恰wrapper_version/record_fingerprint/record，版本 `TASK-020-human-gate-decision-record-wrapper-1.1`。submission.prior_decision_binding须与之canonical全等；错误提交不能被适配器悄悄替换成正确wrapper。Gate1必须同批次APPROVE/HUMAN_DECLARED、共享六项绑定相同，材料摘要不要求相等。

本次prior_history恰三键：declared_complete严格true，declared_scope固定字符串
`GATE2_SCOPE:<Gate2 scope项目相对路径>|BOUND_GATE1:<Gate1 event项目相对路径>`，records恰含上述一个完整Gate1 wrapper（按event_id排序，单条自然唯一）。完整性只覆盖“已实读证明尚不存在的本Gate2 scope＋已核验的绑定Gate1事件”，不声称发现其他scope或全局历史。不得传空历史、摘要假记录或caller-supplied历史。

## 4. 唯一保存/恢复顺序与封套

保存：参数/确定路径/既有现场检查 → 独占Gate2锁 → **本次自己真实准备Gate2请求**并保留开始消费的captures → 对照本次独立expectations核验submission绑定/完整Gate1 wrapper、实际枚举Gate2 scope不存在 → 核心前复确认来源/登记/Gate1/装载/DB/集合/锁 → 独占建立Gate2 scope/event → **冻结store.save恰一次**（内部P1恰一次）→ 绑定本次store返回、写context、最后写receipt → 全部语义消费及成功对象构造 → 按身份释放自锁 → **最后**有界原始字节/集合/路径确认（包括锁不存在）→ 成功。锁释放的身份/内容消费也必须位于最后确认之前；成功后不再解析锁或其他候选。释放后的终端拒绝仍按实际事件现场留诊断，不重复释放或删除后来出现的锁。

复用TASK-029物化逻辑，必要时抽内部helper供prepare/save/verify共享并传递同缓冲captures；公开prepare的签名/两键返回/只读语义不变。禁止独立P1预调用、信任调用方旧request/status/expected，或写后用较晚capture替换本次writer缓冲预期。

store返回后的manifest实读SHA必须等于**该次真实返回**manifest_file_sha256，五payload按该manifest核验字节/大小；submission/materials/expectations/prior_history与本次消费对象canonical全等，decision_result恰两键且与真实返回record指纹闭合。原始人类字符串原样保存，JSON对象快照不宣称保留原文件排版/BOM。

本层context封闭**14键**：context_version、batch_id、source_batch_relative、runtime_relative、gate1_scope_relative、gate1_event_relative、gate2_scope_relative、event_relative、database_relative、registry_file_sha256、request、prior_history、store_result、boundaries。

receipt封闭**9键**：receipt_version、batch_id、event_relative、gate2_scope_relative、context_file_sha256、snapshots_manifest_file_sha256、record_fingerprint、registry_file_sha256、boundaries。

版本常量分别 `TASK-030-runtime-gate2-context-1.0` / `TASK-030-runtime-gate2-receipt-1.0`。boundaries沿用现有决定封套五键execution_allowed/workflow_connected/ai_enabled/identity_authenticated/source_authenticity_proven，全部严格false；不改P1记录的六false边界或persisted=false。context.request保留真实准备时的六键请求原样快照（包括准备时request_persisted=false），不把快照字段当当前全局状态。

context中的不可变请求快照就是本次决定绑定的持久材料；**不另建gate2_request.json、不写登记叶**。这是本卡对TASK-025拟定文件发布位置的明确落地裁决，冻结设计正文作为历史提案保留，不静默回写或声称旧位置已实现。

失败仅在本次事件已实际建立后独占写五键failure_version/stage/field/reason/cause_chain，版本 `TASK-030-runtime-gate2-failure-1.0`。无事件不造事件；失败现场、半写与已建目录保留，不覆盖、不删除、不重试、不声称回滚。诊断在主次错误已知后一次写定，诊断本身失败也保留原错误与次错误。只读verify遇failure/未知项/锁立即拒绝。

verify：先验路径/失败现场和固定集合 → 同缓冲读取完整封套/六快照 → 真实重新准备当前Gate2请求、核验其绑定Gate1 → 冻结store.verify一次 → 封闭schema与所有身份/路径/共享运行绑定/完整request和history闭合 → store稳定字段除status外与保存时一致 → 构造三键返回 → 从操作开始读数作最后字节/集合/路径/failure/锁确认。最后不得再读候选生成成功。

保存和verify均不调用normalizer/loader/筛查等计算入口；当前Gate1核验及store.verify内部P1允许，实际次数分列。不把“保存了APPROVE”解释为筛查可以运行。

## 5. 最小验收与夹具

用既有夹具，先核对来源SHA；不能生成新人/时间/原因/事件ID：

- Gate2 APPROVE字段取 `data/decision_protocol_checks/task020r2_run_01/fixture_values.json` 的 `BASE2.submission`；文件35465 B / SHA `6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337`。取event_id/decision/actor/decided_at_raw/reason原文，其余技术批次/请求/前序绑定按本次实际材料构造；不得复用该旧夹具中的虚构材料SHA或旧Gate1wrapper。
- HOLD对照可取已登记0002的人类字段：`data/human_gate1_decision_tests/task024_dev_01/fixtures/TASK024_G1_HOLD_0002.json`，SHA `8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa`。本卡允许在测试提交中将技术gate字段设为GATE2，保留全部人类字段原文；event_id的G1前缀不证明Gate来源。外层标PROTOCOL_TEST_FIXTURE_ONLY，不新增核心字段。

只做以下四组，不按检查数量考核：

1. 一个正常新运行小样：Gate1/装载/只读Gate2准备 → APPROVE保存 → verify成功；独立十材料与完整前序/history核对，store.save内部新决定P1一次，实际完整返回与落盘decision_result规范相同；源/Gate1/登记/load/DB字节不变、Gate2事件八文件齐全、边界全false。一个独立HOLD保存/恢复对照，仍不放行；REJECT依冻结P1矩阵支持，不强制为重复矩阵另建第三条计算链。
2. 最小拒绝：错材料指纹、错/伪造完整前序、错确定路径、既有空scope/第二事件/锁、空白reason由真实P1拒绝；错绑定在store前拒绝、无成功事件；核心拒绝如外层event已建须有有效failure。核验反例要隔离、先干净可恢复，至少一个内层绑定矛盾同步直接外层摘要后仍被目标关系拒绝，无原生消费异常。键序不同canonical等值通过。
3. 保存/恢复晚变更：真实准备返回后、store前改本轮DB → 本次拒绝且新决定store.save增量0；真实store返回后改一份payload并同步其候选manifest → 本次与该次真实返回manifestSHA绑定拒绝；verify最后必要语义消费后改本层context或新增未知项 → 本次拒绝且只读不写failure。另做context真实独占句柄半写OSError与receipt真实writer写后sentinel两例，链/现场准确；锁身份沿用已验收helper并做既有锁不动小对照，不重跑历史锁大组。
4. 完整实际观察/独立profile/前后引用指纹/返回或异常链/文件台账闭合；候选读取前冻结内存预期，复用TASK-028短收尾，不新建框架。四个actual main新进程replay为normal0、返回替换1、末次消费后台账LF1、checksLF1；FAIL与非空failures落盘，期望不刷新、坏字节不回填，replay不再建业务链。

全过程直接API/嵌套Gate1/inspect/store/P1分列；准备和保存窗口内禁止计算入口实际命中0。未知或未执行计数null+原因；旧证据注明只读引用且未重跑。真实链接本卡不强制另建，沿用逐级规则并如实声明。不得改旧测试/harness或为探针清理目录；本轮原状恢复必须具名保全、仅单文件精确操作。

## 6. 完整交付与保护

全部代码/指南/回执定稿、局部核对通过后一次最终全树扫描。changed仅runtime_gate1.py，新增仅四交付文件与上述明示根展开的确切路径，禁止前缀兜底；范围外变化/新增、新missing/读取错误0。139历史损失、27恢复、326越界、19命名偏差分别保留；不能重建缺失证据冒充原件。

回执列出完整SHA/长度、各验收目标/实际field、真实调用范围、坏场景/控制证据与未执行项，最后有限登记扫描自身元数据。全部交付后in_review；执行端停止本卡，done与真实决定由人类操作。

本卡结束仍未连接筛查/复算/事实/真实独立初判/AI/终判；不变更开发宿主0008、不生成0009。测试合成APPROVE不构成真实批准，next/AI仍false。下一阶段实际Gate2放行另卡，不自动开放。
