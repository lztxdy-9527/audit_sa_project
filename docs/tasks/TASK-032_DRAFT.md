# TASK-032：运行层独立复算接线与只读恢复

类型 C：Architect 固定计算动作与证据边界，GPT 执行端实施，Architect 独立验收。本卡为持续授权下的适配器建设和合成夹具测试，不批准真实批次。每次动作仍须实读当批 Gate2 APPROVE 及已完成筛查，不能从总授权、状态名或模拟字段推断批准。

## 1. 起点与允许范围

先只读核对 `docs/reviews/REVIEW_TASK_031.md` 和 `data/reviews/task031_gpt_20261016_021424/review_result.json`，结论必须 ACCEPTED；使用其登记的 source_hashes_after.json/SHA/项数，不自行猜测基线。

唯一允许修改既有文件 `scripts/runtime_gate1.py`，起点 213659 B / SHA `540cb273f2b57aa9da1cf57438c9765a0b4346e66db1a46cdd4193f24a9fd609`。实现版本升 `TASK-032-runtime-gate1-1.0`；原十二公开 API 签名、协议、固定集合和前提保持。只允许必要小型内部复用；不拆物理模块、不新增框架或通用许可、不向调用方开放跳过核验开关。

仅新增 `tests/test_runtime_rule_crosscheck.py`、`docs/RUNTIME_RULE_CROSSCHECK_GUIDE.md`、`docs/EXEC_REPORT_032.md`。本轮新根仅：

- `data/runtime_rule_crosscheck_tests/task032_<轮次>/`。
- `data/runtime/task032_<轮次>/`。
- `data/human_gate_decision_records/gate1/task032_<轮次>/`。
- `data/human_gate_decision_records/gate2/task032_<轮次>/`。
- `data/sqlite_tests/task032_<轮次>/`。

代码变更即新运行版本，新登记/Gate1/装载/Gate2/筛查夹具链；只读复用已有 C06b batch，不重接收、不更新旧凭证。冻结既有测试/指南、P1/store/准备器、所有计算核心/SQL/schema、契约/登记/配置、开发宿主/控制器和旧证据。不要安装依赖、递归删除/移动、清理失败现场或旧锁。需要改冻结算法或扩大范围即停止升级。

## 2. 两个 API，无 CLI

```python
run_gate2_rule_crosscheck(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
inspect_gate2_rule_crosscheck(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
```

成功外层恰六键：stage_version=`TASK-032-rule-crosscheck-1.0`、status=`RT_RULE_CROSSCHECK_RECORDED`、batch_id、run_binding_sha256、artifacts、boundaries。成功必须完整 MATCHED；不新增可放行的 phase、许可对象或宿主检查点。

boundaries 恰七键，严格 false：fact_packet_recorded、human_initial_judgment_saved、ai_enabled、audit_conclusion_formed、identity_authenticated、source_authenticity_proven、next_step_allowed。

异常复用 RuntimeGate1Blocked(field,reason)/RuntimeGate1Error(stage,reason)，完整原因链与核心 reasons 保留。inspect 全程只读，不调用任何计算核心或保存接口，不写 failure。

## 3. 前提与唯一计算

真实调用当前 `inspect_gate2_approved_screen`，确认 RT_RULE_SCREEN_RECORDED；其内部真实 Gate2 核验必须保留。拒绝调用方提供报告/status/expected 代替来源。核心前固定本窗口起始读数：来源八文件、登记二文件、Gate1/Gate2 八文件、load 四文件、DB、筛查三文件和已绑定静态文件/四 SQL。可复用 `_screen_inputs_031`、已有 capture/集合/路径 helper；必要小型内部共享只减少复制，不改变旧公开入口。

normalized、screening_report 均从本次起始 capture 的同一缓冲解析；length/文件 SHA/对象规范指纹同源。筛查 artifacts 与公共 inspect 的返回严格 canonical 相同，且其 report_file_sha256/report_canonical_sha256、DB 与本次实际缓冲闭合。不能在后续重读候选后覆盖起始预期。

冻结核心 `scripts/crosscheck_demo_rules.py`：59934 B / SHA `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`，版本 TASK-007-crosscheck-1.2。它已在十四项代码清单内，按独立冻结 SHA 加载，不新增清单条目。唯一真实调用：

```python
verify_rule_facts(normalized_object, screening_report_object)
```

只传两个内存对象，不传数据库路径。保留真实引用，调用前、返回后及所属 API 收尾核对指纹，不能用两个调用后值替代前后。完整真实返回留观察，与保存报告严格 canonical/确切字节比较。不要预调用核心或重新实现 R01—R04；不调用 SQL 筛查、normalizer、loader 或答案册。DB 仍由适配器按起始 capture 实读复测。实际模块 CrossCheckBlocked → 本层 Blocked，CrossCheckError/I-O → Error；允许在已有 `_call_frozen_entry` 增实际类识别，旧映射不变。

## 4. 输出及协议

输出固定登记叶同级 `<登记叶名>.crosscheck/`，必须从未存在（含空目录拒绝）。独占创建、canonical JSON UTF-8 无 BOM+单 LF，一次写定并逐件读回与本次缓冲比较。正常恰 started.json/crosscheck_report.json/artifacts.json，artifacts 最后写。

started 恰八键：started_version、batch_id、source_batch_relative、runtime_relative、gate1_event_relative、gate2_event_relative、database_relative、bindings；版本 TASK-032-rule-crosscheck-start-1.0。bindings 恰九键：registry_file_sha256、gate2_record_file_sha256、gate2_record_fingerprint、normalized_file_sha256、normalized_payload_sha256、screening_report_file_sha256、screening_report_canonical_sha256、screening_artifacts_file_sha256、run_binding。前者文件 SHA 来自起始字节，对象指纹明确分列。

artifacts 恰十五键：artifacts_version、batch_id、run_binding_sha256、registry_file_sha256、gate2_record_file_sha256、gate2_record_fingerprint、normalized_file_sha256、normalized_payload_sha256、screening_report_file_sha256、screening_report_canonical_sha256、screening_artifacts_file_sha256、started_file_sha256、report_file_sha256、report_canonical_sha256、database。版本 TASK-032-rule-crosscheck-artifacts-1.0；database 恰 relative/file_sha256/byte_size（严格非负整数）。上述绑定与 started、实际文件/对象、登记、Gate2、筛查、DB 逐项闭合。

完整核心报告原样保存，不改 DEVELOPMENT_TEST_ONLY、method 或 limits，不添加人类判断。run/inspect 只核验接口协议及绑定，不重新独立复算算法：

- 顶层恰冻结实际十八键：crosscheck_version、batch_status、matched、mode、next_step_allowed、period、cutoff_date、input_source_sha256、normalized_payload_sha256、screening_report_sha256、rule_core_version_checked、rule_recomputed_counts、recomputed_facts、observed_summary、comparison、differences、method、limits。
- 版本/固定期间/截至日/开发边界与核心固定值一致；来源工作簿 SHA、normalized 规范指纹、筛查规范指纹等于本次实际输入。SHA 全串64位小写hex；普通 ID 原文保留。
- comparison 恰 dimensions/difference_count/matched_dimensions/unmatched_dimensions。dimensions 恰 hit_keys、amounts_cents、related_ids、refund_facts、rule_identity、source_entities、source_rows、counts、statistics、overall_reconciliation 十维度；每项恰 executed/matched/difference_count，executed 严格 true、matched 严格 bool、计数严格非负 int。总体差异数等于 differences 长度和各维差异数之和；两维度名单是按名称排序、唯一、与十维实际真假双向相等。
- MATCHED 要求 matched 严格 true、batch_status=DEV_CROSSCHECK_MATCHED、differences 空、十维全 matched/零差异、无 unmatched。MISMATCH 必须 matched 严格 false、对应状态、非空实际差异和未匹配维度；不允许只改 matched 旗标制造通过。
- rule_recomputed_counts 恰 R01—R04/total，严格整数且与 recomputed_facts.findings 的 rule_id/实际长度闭合。recomputed_facts 恰 findings/reconciliation/statistics；observed_summary 与本次 screening_report 对应三字段 canonical 相等。method/limits 与冻结常量相等；不把两种计算一致解释为真实性或审计结论。

MISMATCH 是真实核心的正常比较返回，不冒称运行 Error：先独占保存完整报告并读回，核验比较协议，随后抛 `RuntimeGate1Blocked(field="crosscheck.report.matched", reason=包含差异数/维度)`，不写成功 artifacts；失败诊断 kind=BLOCKED。保留 started、完整 report/differences 和 failure；inspect 优先传播失败，不宣称 MATCHED、不修正原筛查/DB、不继续事实底稿。此行为沿用已验收开发宿主的阻断语义，不另设 MISMATCH 成功状态。

failure 恰六键 failure_version/kind/stage/field/reason/cause_chain，版本 TASK-032-rule-crosscheck-failure-1.0，kind 严格 BLOCKED/ERROR。只在本次输出已建后独占写；半写/坏文件原样保留，不覆盖/重试/清理；主次失败原因可见。inspect 先核验 failure 再消费可能半写报告/artifacts。

全部必要语义、返回对象构造完成后，以起始或本次 writer 缓冲绑定值最终确认全部来源/静态/Gate1/Gate2/登记/load/DB/screen/本层文件字节、固定集合、failure/锁及逐级 reparse。此后不读候选产生成功，不以重新 capture 后自比代替确认。独占新输出目录已防重复，不新增锁协议。

## 5. 最小验收（四组，不追求数量）

1. 一个新版本 C06b 链至已批准筛查，真实复算恰一次且正常保存/只读恢复；两输入三时点不变、完整真实返回与报告确切字节相等。独立事实仍 R01/R02/R03/R04=0/1/0/0、R02=400000 分，十维 MATCHED；上游/DB 字节不变，inspect 的复算/SQL/保存增量0。重复、缺筛查/错误 Gate2 绑定及已有输出拒绝，用已有场景隔离，避免再建 HOLD/REJECT 重复业务链。
2. 一个真实 MISMATCH：独立新场景，仅改本轮筛查报告中一处被复算器比较、但不违反筛查接口前提的来源事实（优先 source_rows 的一个严格整数行号），同步该筛查 report 的文件 SHA/规范指纹及 artifacts，不改 normalized/DB/Gate 决定。先实测公共筛查 inspect 仍成功，再真实调用复算，必须实际返回非空差异、适配器 Blocked，完整报告与原差异保存，无成功 artifacts；撤销 wrapper 后只读 inspect 仍拒绝且现场不变。若所选字段在更早层被拒，只纠正隔离构造，不放宽前提或改冻结核心，不把提前拒绝称为 MISMATCH。
3. 最小持久化/晚变更：真实核心前最后核验返回后给本轮输入报告或 DB 加 LF，本次拒绝、复算0、输出未建；正常 writer 返回后或 inspect 最后语义消费后改本层报告，本次定位拒绝。inspect 撤销注入后保留坏字节仍拒绝、仅恢复本轮原件后成功，不写 failure。artifacts 真实 xb 句柄半写 OSError 一例、失败优先与原因链准确；两真实异常类映射用同一 helper 最小控制，不为映射另建完整链。
4. 复用已验收短证据收尾与观察器，仅补真实复算函数代码身份、完整输入返回/异常和三时点引用；直接 API、嵌套核验/P1/store、SQL/复算分列，计数来自实际观察。定稿独立内存预期 → 候选同缓冲内容/台账审核 → 最后原始字节确认支配 CLI/磁盘。四个 actual main 新进程 replay：normal0、返回替换1、末次消费后台账LF1、checksLF1；源只读，不回填、不刷新预期、不在 replay 建链。

人类字段只用既有登记夹具原文，不生成姓名/决定时间/事件 ID/原因。只按确切路径保全/恢复本轮单文件；不移动锁目录、不删除目录。未执行项 null+原因，未加载下游不要声称测得守卫0。没有要求重跑 MAIN/零条、冻结核心大套件或历史入口；旧证据明确引用且未重跑。

## 6. 完整交付与停止点

代码、指南、回执和局部核对定稿后一次最终全树扫描；changed 仅 runtime_gate1.py，新增按四交付文件和明示根展开的确切路径登记，无前缀兜底；范围外变化/新增、新 missing/读取错误均0。139历史损失、27恢复、326越界、19命名偏差和 TASK-030 锁目录按接受基线保留，不追认/重建/清理。扫描自身元数据最后有限登记。

交付完整 SHA/长度、调用/注入真实来源、CLI 原文与退出码、MISMATCH 完整差异、只读/源不变证据及未重跑范围。全部交付后停止实施交独立验收；不自行宣布通过或继续下一任务。

停止于独立复算成功记录；不接事实底稿、真实独立初判、AI/终判、真实数据、网络/UI/ERP，不新增开发宿主0009。真实批准仍 null、开发宿主0008、next/AI=false；一致性不是身份认证、业务真实性或审计结论。
