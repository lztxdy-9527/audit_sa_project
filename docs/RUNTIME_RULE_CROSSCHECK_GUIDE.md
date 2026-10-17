# 运行层独立复算与只读恢复

实现版本 `TASK-032-runtime-gate1-1.0`。本层只对已经核验 Gate2 APPROVE 和 SQL 筛查的同批材料执行一次冻结内存复算；交付测试不代替独立架构验收，不批准任何真实批次。

## 1. 两个公开接口

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

无 CLI。scope_dir/event_relative 仍指 Gate1，gate2_event_relative 指固定 Gate2 事件。调用方不能提交 status、报告或 expected 代替来源核验。已有十二公开接口的签名、协议、前提与固定集合保持原值。

两接口真实调用当前 `inspect_gate2_approved_screen`，要求 `RT_RULE_SCREEN_RECORDED`，保留其真实 Gate2/Gate1/装载核验。共享起始 capture 同时固定来源八文件、登记二文件、Gate1/Gate2 各八文件、load 四文件、DB、screen 三文件和静态/SQL字节。筛查 artifacts 与真实 inspect 返回 canonical 相等，报告文件 SHA/规范指纹及数据库与本窗口读数闭合。已有 failure、锁、未知项、不完整凭证或变化材料均阻断。

## 2. 一次真实内存复算

冻结核心 `scripts/crosscheck_demo_rules.py` 为 59934 B，独立 SHA-256 `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`，版本 `TASK-007-crosscheck-1.2`；它已在十四项代码清单内，不添加清单条目。

只调用一次 `verify_rule_facts(normalized_object, screening_report_object)`。两个对象从本窗口起始实读缓冲解析；字节、长度、文件SHA与对象指纹同源。核心不收数据库路径；适配器仍独立复测 DB 起始字节。保留两实际引用，在调用前、返回后、成功 API 收尾复核规范指纹，测试观察器也在这三时点记录完整输入。核心前再次确认全部材料/事件/DB/静态字节与集合，不预调用核心探路。

不运行 SQL 筛查、标准化或装载，不重写规则或访问答案册。只读恢复核验已有报告与绑定，不重新复算；既有 P1/store 的只读前序验证仍由真实 Gate 核验调用，不混称新决定保存。

## 3. 文件与返回

输出是登记叶同级 `<登记叶名>.crosscheck/`，必须从未存在，空目录也拒绝。独占建立，canonical JSON UTF-8 无 BOM + 单 LF；每件一次写定，读回与该次缓冲精确相等，artifacts 最后写。文件SHA与对象规范指纹分列。成功目录恰三件：

- started.json：八键，版本 `TASK-032-rule-crosscheck-start-1.0`；批次/来源/登记/Gate1/Gate2/DB路径与九键 bindings。bindings 为 registry_file_sha256、gate2_record_file_sha256、gate2_record_fingerprint、normalized_file_sha256、normalized_payload_sha256、screening_report_file_sha256、screening_report_canonical_sha256、screening_artifacts_file_sha256、run_binding。
- crosscheck_report.json：冻结核心完整十八键报告，保留 method/limits/开发标记与全部真实差异，不添加人类判断。
- artifacts.json：十五键，版本 `TASK-032-rule-crosscheck-artifacts-1.0`；批次/运行绑定、上述八项摘要、started/报告文件SHA与报告规范指纹、database。database 恰 relative/file_sha256/byte_size，大小是严格非负整数。

成功恰六键：stage_version=`TASK-032-rule-crosscheck-1.0`、status=`RT_RULE_CROSSCHECK_RECORDED`、batch_id、run_binding_sha256、artifacts、boundaries。boundaries 恰七键且严格 false：fact_packet_recorded、human_initial_judgment_saved、ai_enabled、audit_conclusion_formed、identity_authenticated、source_authenticity_proven、next_step_allowed。

## 4. MATCHED 与 MISMATCH

报告协议核验包括固定版本/期间/截至日/开发边界和三输入来源摘要；comparison 封闭四键，dimensions 恰十维，各维 executed 严格 true、matched 严格 bool、difference_count 严格非负整数。差异总数等于 differences 长度与十维计数和；两维度名单排序唯一且与十维真假双向相等。MATCHED 要求十维全执行、全匹配、零差异且无未匹配维度；MISMATCH 要求实际非空差异和未匹配维度，不能只改旗标制造通过。

rule_recomputed_counts 恰 R01—R04/total，严格整数，与 recomputed_facts.findings 实际规则数量/长度相等；recomputed_facts 恰 findings/reconciliation/statistics。observed_summary 与本次筛查的计数、R02超额、总体勾稽 canonical 相等；method/limits 与冻结常量相等。本层核验协议和来源，不再次独立计算规则。

真实 MISMATCH 是核心正常比较返回。适配器保存完整 report 并精确读回，核验协议后抛 `RuntimeGate1Blocked(field="crosscheck.report.matched")`，reason 含差异数/维度；不写成功 artifacts，不修正上游。现场保留 started/report/failure，failure.kind=BLOCKED；只读恢复优先传播失败。

## 5. 故障和末端确认

异常复用 RuntimeGate1Blocked/RuntimeGate1Error。实际加载模块的 CrossCheckBlocked 映射 Blocked，CrossCheckError/I-O 映射 Error；完整 reasons 和 cause 链保留。只有本次输出已建立才独占写 failure.json，恰六键 failure_version/kind/stage/field/reason/cause_chain，版本 `TASK-032-rule-crosscheck-failure-1.0`，kind 为 BLOCKED/ERROR。诊断写失败时保留主次错误；不重试覆盖、不清理半写、不声称回滚。

inspect 先校验 failure 再消费可能半写文件，不写诊断。全部语义、输入引用收尾及返回对象构造之后，以起始/本次 writer 绑定读数最终确认来源、事件、load、DB、screen、本层文件字节，固定集合、failure、锁与逐级 reparse；随后直接返回，不再读候选生成成功。

## 6. 定点验证与边界

```text
.venv\Scripts\python.exe -B tests\test_runtime_rule_crosscheck.py --out-dir data\runtime_rule_crosscheck_tests\task032_<新名>
```

定稿证据 `data/runtime_rule_crosscheck_tests/task032_run_02/`。三个新运行场景：正常十维 MATCHED；筛查 source_rows.payables.AP01 从2改3、同步外层摘要后真实 MISMATCH；artifacts真实xb半写OSError。缺筛查/错绑定/重复和空输出、严格类型/维度名单、核心前DB晚变更、inspect最后语义消费后报告LF及恢复均留证。

四个实际 main 新进程只重放定稿观察，normal/candidate-return/ledger-late/checks-late 退出0/1/1/1；完整原文见 task032_finalization_02/closure_controls.json。replay不新建业务链、不调用计算核心。run_01及其CLI是补齐生产API收尾输入检查前的过程证据，保留、不替代定稿证据。

真实批准仍null、开发宿主0008、next/AI=false。两种实现一致只说明输入计算一致，不证明身份、业务真实性或审计结论；本层不接事实底稿、真实初判、AI/终判或真实数据/网络流程。
