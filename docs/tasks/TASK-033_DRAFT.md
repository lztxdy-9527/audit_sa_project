# TASK-033：运行层冻结事实底稿接线与只读恢复

类型 C：Architect 固定范围及协议，GPT 执行端实施，Architect 独立验收。本卡只有 TASK-032 的 review_result.json 正式发布 ACCEPTED 后才生效；这是持续建设授权，不批准任何真实批次。本卡不启动执行会话。

## 1. 起点、允许路径和停止条件

先实读 `docs/reviews/REVIEW_TASK_032.md`、`data/reviews/task032_gpt_20261016_030543/review_result.json`，使用其中 source_hashes_after.json 的确切 SHA/项数。不要猜测接受快照或使用执行端 delivery 替代架构验收。

唯一允许修改既有文件 `scripts/runtime_gate1.py`：234725 B / SHA `5ad8b95a196213105ec7e1dc1058d22e7790ac0292b5a77e8d641d29a82902d0`，版本升为 `TASK-033-runtime-gate1-1.0`。保持原十四个公开 API 签名、行为、前提及固定集合；仅必要小型内部复用和实际异常类型映射扩展，不拆模块、不新增框架/CLI/通用许可或跳过核验开关。

只新增 `tests/test_runtime_fact_packet.py`、`docs/RUNTIME_FACT_PACKET_GUIDE.md`、`docs/EXEC_REPORT_033.md`。本轮新根仅：

- `data/runtime_fact_packet_tests/task033_<轮次>/`。
- `data/runtime/task033_<轮次>/`。
- `data/human_gate_decision_records/gate1/task033_<轮次>/`。
- `data/human_gate_decision_records/gate2/task033_<轮次>/`。
- `data/sqlite_tests/task033_<轮次>/`。

代码变化即建立新登记/夹具事件/装载/Gate2/筛查/复算前提链，不修改旧凭证。只读复用 C06b `data/batches/task027r1_run_04/batch_normal`，工作簿 SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`，不重新接收。固定代码清单仍十四项、Gate1 材料仍三十二项，六项共享 run_binding 精确一致，阶段材料摘要可不同。

冻结所有其他既有文件，包括计算/展示核心、P1/store/准备器、SQL/schema、正式契约及生效登记、配置、旧测试/指南、开发宿主/控制器和历史证据。正式契约 V1 SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`。人类字段只沿用已登记夹具原文；不生成姓名、决定时间、事件 ID 或原因。Python 一律 -B。不安装依赖，不递归删除/移动、清理探针/锁/失败产物。

如果发现需要修改冻结展示核心/算法/旧指南、扩大范围或改变业务口径，停止该级别实施并升级，不自行修补。

## 2. 两个公开 API

```python
run_gate2_fact_packet(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
inspect_gate2_fact_packet(
    batch_dir, runtime_dir, *, scope_dir, event_relative,
    database_path, gate2_event_relative
)
```

成功外层恰六键：stage_version=`TASK-033-fact-packet-1.0`、status=`RT_FACT_PACKET_RECORDED`、batch_id、run_binding_sha256、artifacts、boundaries。boundaries 恰六键且严格 false：human_initial_judgment_saved、ai_enabled、audit_conclusion_formed、identity_authenticated、source_authenticity_proven、next_step_allowed。状态仅登记本层事实底稿，不产生通用放行凭证，不连接初判或 AI。

复用 RuntimeGate1Blocked(field,reason)/RuntimeGate1Error(stage,reason)。按冻结模块实际 FactPacketBlocked/FactPacketError 分类，保留原 reasons/cause 链；不按同名异常字符串分类。inspect 不保存、不写 failure、不调用 build_fact_packet、复算、SQL、标准化、装载或决定保存。

## 3. 真实前提、单次构建与只读展示核对

必须真实调用已验收 `inspect_gate2_rule_crosscheck`，确认 RT_RULE_CROSSCHECK_RECORDED 和完整十维 MATCHED，保留其真实筛查/Gate2 核验；MISMATCH/failure/错误绑定/缺失上游均拒绝。不得接受调用方提供的报告、状态或 expected 代替来源。

在本次操作开始捕获来源八文件、登记二文件、Gate1/Gate2 八文件、load 四文件、DB、筛查三文件、复算三文件及全部已绑定静态文件/四 SQL。normalized、screening_report、crosscheck_report 分别只从这些本次缓冲解析；对象/长度/文件 SHA 同源，规范 JSON 指纹另列。上游公共 inspect 返回 artifacts 与本次捕获严格 canonical 相等，所有报告文件 SHA/对象指纹、DB、登记/Gate 决定逐项闭合。可复用 TASK-032 的 capture/confirm helper，不重新采集后覆盖起始预期。

冻结展示核心 `scripts/build_demo_fact_packet.py`：54548 B / SHA `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`，版本 `TASK-008-fact-packet-1.1`，已在固定十四项清单内，不新增代码条目。run 仅真实调用一次：

```python
build_fact_packet(normalized_object, screening_report_object, crosscheck_report_object)
```

只传三个内存对象，不传路径/数据库/答案册；不预调用核心，不重写事实组装、Markdown 模板或 R01—R04。保留真实引用，调用前、返回后、所属 API 收尾三时点核对完整快照和规范指纹。完整真实返回留观察，原 packet 及 markdown 与保存字节精确相等。

inspect 为核对已存 JSON 与 Markdown 的关系，**允许且只允许一次**真实冻结 `render_markdown(packet_object)`；它是纯展示核对，不是重新 build。run 不再额外调用 renderer（build 内部已有一次）。真实 renderer 原代码对象计数、完整输入/返回和引用三时点另列；inspect 的 build/复算/SQL/保存增量仍须零。只读 render 返回的 UTF-8 字节必须等于本次起始 Markdown 缓冲，不能用后来重读内容刷新预期；不得调用任何其他展示核心业务入口。加载冻结模块不等于调用构建入口。

## 4. 输出和完整性协议

输出固定登记叶同级 `<登记叶名>.facts/`，必须从未存在（含空目录拒绝），独占创建。正常恰四文件：started.json、fact_packet.json、fact_packet.md、artifacts.json；artifacts 最后写。JSON 为 canonical UTF-8 无 BOM+单 LF；Markdown 为核心返回字符串的 UTF-8 **原字节**，不额外加 LF、改转义或改历史提示。一次写定、逐件读回与本次 writer 缓冲比较。

started 恰九键：started_version、batch_id、source_batch_relative、runtime_relative、gate1_event_relative、gate2_event_relative、database_relative、bindings、runtime_context；版本 `TASK-033-fact-packet-start-1.0`。

bindings 恰十三键：registry_file_sha256、gate2_record_file_sha256、gate2_record_fingerprint、normalized_file_sha256、normalized_payload_sha256、screening_report_file_sha256、screening_report_canonical_sha256、screening_artifacts_file_sha256、crosscheck_started_file_sha256、crosscheck_report_file_sha256、crosscheck_report_canonical_sha256、crosscheck_artifacts_file_sha256、run_binding。SHA 均完整小写 hex，文件 SHA 与对象指纹分列，run_binding 与实际登记精确相同。

runtime_context 恰四键，固定值：

- contract_version=`V1`。
- contract_file_sha256=`174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`，并核对实际绑定正式契约。
- core_notice_scope=`FROZEN_DEVELOPMENT_TEMPLATE`。
- notice=`冻结事实核心中的契约/批准未实施提示是该开发模板原文；本运行层另行核验已绑定正式V1契约及当批本地Gate记录。原文不代表本层未核验，也不表示已获真实批次批准、强身份认证或审计结论。人类初判未保存，AI未开放。`。

冻结 BANNER/LIMITS 包含历史开发提示，不得删除、改写或用当前契约事实静默替换。指南必须把 runtime_context 与原提示一起说明，不把模板历史描述当作当前正式契约无效，也不把夹具批准说成真实批准。此项只增加运行层来源说明，不改冻结核心或原 packet/Markdown。

核心返回恰 packet/packet_sha256/markdown 三键；packet_sha256 必须是 packet 的规范指纹，markdown 为严格 str。packet 顶层恰十二键：packet_version、batch_status、mode、next_step_allowed、entity、banner、bindings、summary、reconciliation、findings、amount_labels、limits。固定版本/DEV_FACT_PACKET_READY/DEVELOPMENT_TEST_ONLY/严格 false、澄明商贸有限公司/CNY/2026年9月/截至日2026-09-30、banner/limits/amount_labels 与冻结常量及当前实际输入关系一致。

packet.bindings 的工作簿/normalized/筛查/复算指纹、上游版本、声明 DB 哈希须与本次实读输入精确闭合；其“展示层未读取 DB”说明指纯核心，本适配层实际复测 DB，二者分别表述。summary/counts、R01—R04/total 与实际 findings 数量闭合；金额严格整数分、业务 ID 保持字符串、主表与分摊分别列示，不相加称损失。校验接口形状、来源和展示关系，不在适配器重写规则或事实算法。

artifacts 恰十键：artifacts_version、batch_id、run_binding_sha256、bindings、started_file_sha256、packet_file_sha256、packet_canonical_sha256、markdown_file_sha256、markdown_byte_size、database；版本 `TASK-033-fact-packet-artifacts-1.0`。bindings 等于 started.bindings；database 恰 relative/file_sha256/byte_size，长度为严格非负整数，等于本次 DB 起始捕获。packet_canonical_sha256 等于真实返回 packet_sha256；Markdown 文件 SHA/长度来自同一返回字符串缓冲。文件 SHA/对象指纹/完整内容与登记及上游逐项闭合。

必要语义核对、渲染核对及成功返回对象构造全部完成后，以操作起始或本次 writer 缓冲最终确认来源/静态/登记/Gate1/Gate2/load/DB/screen/crosscheck/本层文件字节、固定集合、failure/锁及逐级 reparse。最后确认后不继续读取候选构造成功，不以重采集后自比代替确认。无需新增锁协议。

失败沿用六键 failure_version/kind/stage/field/reason/cause_chain，版本 `TASK-033-fact-packet-failure-1.0`，kind 严格 BLOCKED/ERROR。仅本次已建立输出后独占写，半写/坏文件保留、不覆盖/重试/清理；主次异常均可见。inspect 优先校验/传播有效 failure，再消费可能半写 JSON/Markdown，不写诊断、不修复现场。

## 5. 最小验证与实际进程收尾

只建立一个新版本正常 C06b 链；独立事实预期仍 0/1/0/0、R02=400000 分，预期只用于测试，不进入生产算法。完整正常构建一次、正常 inspect；完整核心返回绑定 JSON/Markdown 字节，三输入同引用三时点不变，上游/DB 不变。原始代码对象 profile 与完整观察闭合，renderer/build 分列，inspect 在写盘/网络/子进程守卫下成功。重复/已有空输出、错误 Gate2/缺失复算可用同一场景隔离，避免重复建链。

最小反例：

1. 真实上游 crosscheck inspect 返回后、本次构建核心前给本轮 DB 或输入报告加 LF：本次拒绝，build 增量0，facts 输出未建；保全坏字节、只恢复本轮原件。
2. 本层 inspect 最后必要语义/渲染消费后改 fact_packet.json 或 Markdown：当次拒绝；撤销包装保留坏字节仍拒绝（允许在更早绑定字段拒绝），只恢复本轮原件后成功，不写 failure。
3. 保存后的 Markdown 正文改一处并同步其 artifacts 文件 SHA/长度：inspect 必须由真实 renderer 与 packet 的完整内容关系拒绝。另以一个 false→0 或 0→0.0 反例证明 canonical 类型敏感。只改本轮文件、具名保全、精确恢复。
4. 最小真实 xb 半写 OSError 一例，可在正常 run 的 artifacts writer 内注入；须额外新场景时只增加一条明确必要链。failure 分类、阶段、field/cause 链及有效失败优先准确。两实际冻结异常类以 helper 控制即可，不为分类另建业务链。记录 renderer 运行异常的来源，不把受控替身称业务失败。

复用已验收短收尾，不新增测试框架或重跑历史大套件。写盘前固定独立内存预期 → 候选同缓冲全内容及台账实际读回审核 → 最后原始字节确认；三者必须真实支配 CLI 退出码、磁盘 summary/failures。四个 actual main 新进程 replay：normal0、candidate-return1、ledger-late1、checks-late1；源只读，不刷新预期/回填候选，不建立业务链。新调用与重放旧观察分开，直接公开 API、嵌套核验/P1/store、SQL、复算、build、renderer 原始代码计数单列，ID/父调用闭合。

新执行、只读引用、受控映射及未执行 null+原因分别登记。不测试/加载初判、AI、终判、真实数据、网络/UI/ERP、0009；不把未加载下游写成守卫实测0。无需重跑 MAIN/零条或冻结核心历史大矩阵。

## 6. 定稿保护和交付停止点

代码/新测试/新指南/回执及局部核对定稿后，仅一次最终全树保护扫描。changed 仅 runtime_gate1.py；新增按本卡确切交付文件及明示根展开为确切文件名单，不使用目录前缀豁免未知项。范围外变化/新增、新基线 missing、读取错误均0；扫描后自身元数据有限确切登记。

139 项历史损失与本轮 missing 分开；27 恢复、R5越界326、R1命名19、TASK-030 锁目录偏差按接受基线保留，不追认/造证/运行/恢复/移动/清理。锁文件 `data/runtime/task030_run_01/normal.gate2.lock.preserved_probe/lock.json` 41 B / SHA `c78006d55489a9ad1b10cc98a081c3bc8135858c5b9040b7d7d5079409cf0e47`。

完整回执登记最终四件长度/SHA、最终轮次、真实调用与注入来源、完整返回/输入观察、CLI 原文/退出码、只读/源不变、确切保护结果和未重跑范围。过程轮次保留，不能混作最终交付。实施完停止交 Architect 独立验收，不自行宣称 ACCEPTED 或继续初判。

本层仅停在 RT_FACT_PACKET_RECORDED。真实批准仍 null、开发宿主仍0008、真实独立初判未保存、next/AI=false。正式契约、事实保存、计算一致和技术验收均不认证身份、不批准批次、不形成审计结论；人类独立初判及其保存接线另卡，后置 AI/终判继续另行授权。
