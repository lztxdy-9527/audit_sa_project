# 运行层事实底稿构建与只读恢复

实现版本 `TASK-033-runtime-gate1-1.0`。本层只接冻结展示核心，将当批已核验筛查与十维 MATCHED 整理为事实 JSON/Markdown。技术验收由独立架构会话作出，真实批次批准与审计判断由人类作出。

## 1. 接口与前提

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

无 CLI。scope_dir/event_relative 仍指 Gate1，gate2_event_relative 指固定 Gate2 事件。原十四个公开接口的签名、行为、前提与固定集合保持，不开放跳过核验开关。

真实调用 `inspect_gate2_rule_crosscheck`，确认 `RT_RULE_CROSSCHECK_RECORDED` 与完整十维 MATCHED，保留真实筛查/Gate2/Gate1/装载核验。不得由调用方 status、报告、expected 或 APPROVE 字符串替代。当批 MISMATCH/failure、错误绑定、缺失上游或变化材料拒绝，不新造事实输出作诊断。

操作开始固定来源八文件、登记二文件、Gate1/Gate2各八文件、load四文件、DB、screen三文件、crosscheck三文件及全部静态/SQL。三个核心输入只从本次同缓冲读数解析，文件SHA/长度与对象同源，规范指纹分列。公共inspect的artifacts与本窗口严格canonical相等；登记、Gate2、normalized、各报告、DB与本次捕获逐项闭合。

## 2. 构建与只读渲染

冻结 `scripts/build_demo_fact_packet.py` 为54548 B，独立SHA `f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`，版本 `TASK-008-fact-packet-1.1`，仍在十四项清单内。run只调用一次：

```python
build_fact_packet(normalized_object, screening_report_object, crosscheck_report_object)
```

不传路径/数据库，不重写事实组装、规则或Markdown模板。保留三实际引用，调用前、返回后、成功API收尾核对规范指纹；测试保存三时点完整快照。完整返回恰packet/packet_sha256/markdown，packet指纹须正确，Markdown为严格str。run不额外调用renderer，build内部原有一次。

inspect为核对JSON和Markdown，允许且仅调用一次真实 `render_markdown(packet_object)`。这是纯展示关系核验，不重新build；它的原代码计数、输入返回与三时点独立登记。UTF-8返回字节必须等于操作起始Markdown缓冲，renderer不得修改packet。inspect不调用build、复算、SQL、标准化、装载或决定保存；既有P1/store的只读前序核验仍由真实Gate核验执行，不混称新决定保存。

## 3. 固定输出与字节

登记叶同级 `<登记叶名>.facts/` 必须从未存在，含已有空目录也拒绝。正常恰四文件，顺序为started.json、fact_packet.json、fact_packet.md、artifacts.json。独占创建/写入，各件读回精确等于该次待写缓冲；artifacts最后写。

JSON为canonical UTF-8无BOM+单LF；canonical固定ensure_ascii=False/sort_keys=True/separators=(",",":")/allow_nan=False。fact_packet.json保存原packet对象。Markdown保存真实返回字符串的UTF-8原字节，不额外加LF、改转义或改提示。文件SHA与对象规范指纹分列。

started九键，版本 `TASK-033-fact-packet-start-1.0`，包括批次/来源/登记/Gate1/Gate2/DB路径、bindings、runtime_context。bindings十三键：registry_file_sha256、gate2_record_file_sha256、gate2_record_fingerprint、normalized_file_sha256、normalized_payload_sha256、screening_report_file_sha256、screening_report_canonical_sha256、screening_artifacts_file_sha256、crosscheck_started_file_sha256、crosscheck_report_file_sha256、crosscheck_report_canonical_sha256、crosscheck_artifacts_file_sha256、run_binding。

artifacts十键，版本 `TASK-033-fact-packet-artifacts-1.0`：artifacts_version/batch_id/run_binding_sha256/bindings/started_file_sha256/packet_file_sha256/packet_canonical_sha256/markdown_file_sha256/markdown_byte_size/database。bindings等于started.bindings，packet规范指纹等于真实核心返回指纹；Markdown摘要/长度来自同一字符串缓冲。database恰relative/file_sha256/byte_size，长度严格非负int，绑定起始DB。

成功外层六键：stage_version=`TASK-033-fact-packet-1.0`、status=`RT_FACT_PACKET_RECORDED`、batch_id、run_binding_sha256、artifacts、boundaries。六项boundary严格false：human_initial_judgment_saved、ai_enabled、audit_conclusion_formed、identity_authenticated、source_authenticity_proven、next_step_allowed。

## 4. 原模板提示与当前运行上下文

冻结BANNER/LIMITS仍含“未实施正式契约与批准控制”等历史开发模板提示，packet与Markdown均原样保留。它不表示当前正式V1契约无效，也不表示夹具决定批准了真实批次。

运行层started.runtime_context另列四个固定字段：contract_version=V1；contract_file_sha256=`174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`；core_notice_scope=FROZEN_DEVELOPMENT_TEMPLATE；notice原文为：

> 冻结事实核心中的契约/批准未实施提示是该开发模板原文；本运行层另行核验已绑定正式V1契约及当批本地Gate记录。原文不代表本层未核验，也不表示已获真实批次批准、强身份认证或审计结论。人类初判未保存，AI未开放。

正式契约确切文件SHA与当批本地Gate记录由运行层实读核验。核心的“展示层未读取DB”说明指纯核心；本适配层另行实读复测DB。两层分别表述，不静默改核心提示、不宣称身份认证或业务真实性。

## 5. 协议核验和末端确认

packet顶层封闭十二键；固定版本/DEV_FACT_PACKET_READY/DEVELOPMENT_TEST_ONLY/next=false、公司/人民币CNY/2026年9月/截至日、banner/limits/amount_labels核对冻结常量。四项来源指纹、上游版本、声明DB与本窗口输入闭合；summary/counts与实际findings及已核验筛查相等，金额严格整数分，业务ID保留原文。事实卡的hit_key/amounts/related/source_rows/evidence与来源报告canonical相等，展示上下文完整记录与normalized行/原ID闭合。仅校验接口、来源和展示关系，不重算规则或复制组装算法。

全部必要语义、展示核对、引用收尾与返回对象构造完成后，最终按起始/writer缓冲确认来源/静态/登记/两Gate/load/DB/screen/crosscheck/本层字节、固定集合、failure/锁和逐级reparse。随后直接返回，不继续读取候选决定成功，不重采集后自比。

异常复用RuntimeGate1Blocked/RuntimeGate1Error；实际模块FactPacketBlocked映射Blocked，FactPacketError/I-O映射Error，完整reasons/cause保留。仅本次输出已建立时独占保存failure六键，版本 `TASK-033-fact-packet-failure-1.0`，kind为BLOCKED/ERROR。半写/坏字节保留，不覆盖、重试、清理或声称回滚；诊断写失败主次原因可见。inspect优先校验有效failure，不解析半写artifacts、不写诊断。

## 6. 本轮定点入口

```text
.venv\Scripts\python.exe -B tests\test_runtime_fact_packet.py --out-dir data\runtime_fact_packet_tests\task033_<新名>
```

定稿 `task033_run_02`：20项检查、0失败。正常C06b为0/1/0/0、R02=400000分；JSON/Markdown与真实完整返回一致，三输入和renderer引用三时点一致，上游/DB不变。缺复算、错Gate2、重复/空输出、核心前晚变更、inspect末次语义后Markdown变更、同步摘要后的正文篡改、false→0和缺展示ID均有定位证据。第二条明确必要前提链仅用于artifacts真实xb半写OSError。

四个actual __main__新进程replay退出0/1/1/1，按原始业务代码文件与函数名独立profile测得新增业务入口全0，源证据不变；原文见task033_finalization_01/closure_controls.json。首轮task033_run_01为过程证据，保留不改。

真实批准null、开发宿主0008、真实初判未保存、next/AI=false。不接初判/AI/终判、真实数据/网络/UI/ERP或0009；事实保存与两算法一致均不形成审计结论或批次批准。
