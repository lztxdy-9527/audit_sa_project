# TASK-027：运行层 Gate1 单事件保存与当前有效性核验

日期：2026-10-15。**C类：GPT在本卡确定接线与边界，DSH执行。** 前置为TASK-026当前实现经GPT修正复验通过；其历史证据删除事故与139项未恢复损失必须继续登记，不视为原执行合规。

本卡实现已有TASK-025设计中的Gate1保存及有效性核验，停在Gate1记录。**不接标准化/SQLite/Gate2/宿主/初判/AI/终判，不增加CLI。** 人类D1/D2/D3不重新征求，测试夹具不构成真实批准。

## 1. 明确缩小的版本范围

每份运行登记只保存**一个**Gate1事件，一次写定；不做追加、修改、撤销、修订链或跨scope发现。HOLD/REJECT保存后停止，改变决定走后续明确授权的新批次，不能覆盖旧记录。旧TASK-024多事件实现继续冻结。本卡仍实读确认scope初始不存在并形成显式空历史，不能以默认None或猜测代替。

这一定界避免将旧多事件管理器整体复制到新运行层。当前三个公开登记/请求API的“计划scope尚不存在”前提保持。保存后使用本卡新增核验API；**不**让公开read/prepare普遍接受已有scope，也不增加调用方可传的skip/allow-existing开关。

## 2. 文件与产物范围

只修改 `scripts/runtime_gate1.py`，起点 `b7dd3bcafb12b96d944bcedaa27b840de8c4d7e6b99ce69c4a72585f8f4b87ea` /61205 B。新增：

- `tests/test_runtime_gate1_decision.py`
- `docs/RUNTIME_GATE1_DECISION_GUIDE.md`
- `docs/EXEC_REPORT_027.md`

不修改TASK-026测试/指南、P1/store/冻结准备器/旧Gate1组件/宿主/控制器/契约/生效登记/配置/历史设计与证据。物理运行脚本仍只有这一个；代码清单14项、来源材料32项的构成不变，自身SHA实读；改代码即新运行版本、新批次/登记，旧登记不迁移。

仅在新根创建产物：
`data/runtime_gate1_decision_tests/task027_<round>/`、`data/batches/task027_<round>/`、`data/runtime/task027_<round>/`、`data/human_gate_decision_records/gate1/task027_<round>/`。每个登记绑定的scope必须为该记录根下从未存在的新叶路径；所有场景路径实施前列出，不从人类event_id生成目录。

基线与起点核对：`data/reviews/task026_r3_gpt_20261015_043939/review_result.json` 及同根 `source_hashes_after.json`、`remaining_loss.json`、`restoration_journal.json`。后两项是永久历史记录，不删除、不改写，不把139项缺失当成新任务允许删除，也不引用它们为现存阳性证据。27项已精确恢复文件亦冻结。

## 3. 新增两个公开API

沿用TASK-025签名：

```python
save_runtime_gate1_decision(
    batch_dir, runtime_dir, request_id, submission, event_dir, *, scope_dir
) -> {"record": ..., "record_fingerprint": ..., "event_relative": ...}

verify_gate1_effective_approval(
    batch_dir, runtime_dir, *, scope_dir, event_relative
) -> {...}  # TASK-025 §3.2(5) 的11键
```

save外层恰三键，record为真实冻结P1返回的17键正文。verify恰十一键：
`verification_version, batch_id, event_relative, record_fingerprint, record_file_sha256, run_binding_sha256, materials_fingerprint, decision, actor_kind, effective, reasons`。
版本 `TASK-025-gate1-effective-approval-1.0`，actor_kind唯一 `HUMAN_DECLARED`；指纹和文件SHA分列，严格整数/bool/hash规则复用既有口径。

只有**完整合法记录、APPROVE、质量OK、当前材料与所有绑定一致、无锁/失败/未知项**时effective严格true、reasons空。合法HOLD/REJECT返回effective=false及非空原因；结构损坏/错绑定/缺件/失败现场用可定位Blocked，I/O用Error并保留cause，不能为凑11键伪造未知摘要。这是对TASK-025“拒绝时false”笼统措辞的明确细化。冻结P1/store异常可原样传播并保留field/stage/reason/cause，不将其包装为成功返回。

effective只描述该记录在本次材料下是否满足Gate1前提。**本卡没有执行动作或执行许可**，不得调用标准化等下游；host真实批准仍null、0008、next/AI false。

## 4. 保存顺序与独占边界

采用**运行登记叶的同级技术锁**，不放进固定两文件登记叶；同一runtime_dir映射唯一锁路径，位置与命名在指南写明。锁由本层独占创建，其他锁存在即拒绝。只释放本次实际创建且身份/内容未变化的锁；释放失败保留完整错误。不得清理他人锁。

1. 实读核验登记、scope_ref与调用方scope严格相符，事件路径是scope严格后代且从未存在；scope初始必须不存在。检查原始路径逐级reparse及解析后关系。
2. 获取上述锁。**真实调用一次现有公开 `prepare_runtime_gate1_request`**，自己得到当前请求与独立预期，不接受调用方request/status，不从submission取预期。
3. 在锁内实读确认计划scope仍不存在，形成三键历史：`declared_complete=true, declared_scope=<scope项目相对路径>, records=[]`。同批次已有事件/已有scope即拒绝，不能另换scope绕过登记绑定。
4. 比较submission的batch/request/materials/prior绑定与当前独立预期。错绑定不建事件；保留人类字符串原文，不代填actor/时间/原因/event_id，不从D2许可推断批准。Gate1 prior必须null。
5. 来源/登记读数与初始绑定仍一致后，**只调用一次冻结store.save**：

```python
store.save_human_gate_decision_snapshots(
    event_dir / "snapshots", submission,
    current_request["materials"], current_request["expectations"],
    prior_history=verified_history,
)
```

store内部自己调用P1一次，不另做直接P1预调用。冻结store在P1验证后才创建快照及父目录；不要提前建事件空目录。真实核心拒绝不得形成成功事件。

6. 本层独占写context，再写receipt，均canonical UTF-8+单LF、无BOM、确切字节读回。store只负责六快照。全部必要消费后，实读确认本次来源32项、登记两文件、事件八文件、scope/事件/快照固定集合与无failure、静态绑定/自脚本路径字节；预期只来自初始同缓冲或本次writer缓冲。释放自锁后返回；成功时锁不得残留。

保存前的路径/绑定/人类协议拒绝不制造假成功目录。写入后失败保留半写与诊断，不覆盖、不重试、不删除凑成功。事件内failure五键：`failure_version, stage, field, reason, cause_chain`，版本 `TASK-027-runtime-gate1-failure-1.0`。没有事件可落盘时正常传播错误，不为写诊断新造事件。诊断再失败保留主/次原因。

## 5. 最小封套及只读核验

成功scope恰含本次一个事件目录；事件恰 `context.json/receipt.json/snapshots/`，snapshots恰冻结六文件。锁位于运行登记叶同级，不计入成功scope。未知项/failure/半写/锁均阻断。

context封闭十键：
`context_version, source_batch_relative, runtime_relative, scope_relative, event_relative, registry_file_sha256, request, prior_history, store_result, boundaries`。
版本 `TASK-027-runtime-gate1-context-1.0`；request是本次完整六键请求；history显式三键；store_result是那次真实保存完整返回。路径为项目相对规范路径且逐项与显式参数相符，非调用方自报来源。boundaries封闭五键：`execution_allowed, workflow_connected, ai_enabled, identity_authenticated, source_authenticity_proven`，全部严格false。

receipt封闭九键：
`receipt_version, batch_id, event_relative, scope_relative, context_file_sha256, snapshots_manifest_file_sha256, record_fingerprint, registry_file_sha256, boundaries`。
版本 `TASK-027-runtime-gate1-receipt-1.0`，同五键false边界。receipt最后保存，不内嵌自身SHA。完整关系绑定context实际字节、快照manifest实际字节、P1正文指纹、登记实际字节及批次；不改P1记录内persisted=false等冻结语义。

verify只读：先实读事件固定集合、封套及冻结store.verify（该次内部P1次数分列），核验所有形状/指纹/来源关系。随后基于**本次已核验事件**，从显式runtime_dir核验登记与当前批次材料；不得因为计划scope现在存在而直接跳过scope检查。

允许为共享材料构造提取一个内部helper，给verify传入**它自己已核验的scope/事件证据**；此私有分支只容许scope恰等于registry.scope_ref、事件恰是其唯一合法事件、context登记文件SHA匹配本次实读登记、record六项绑定/契约/批次闭合。不能暴露一个调用方bool绕过检查；原三个公开API仍按计划scope前提执行。不要复制整套材料构造或放宽所有已有scope。

完整保存材料/预期、当前重建材料/预期与登记六项均须canonical一致；store恢复的STORED/VERIFIED状态各自按冻结常量核验，其余稳定字段精确闭合。所有消费结束后一次有界原始字节/集合/路径确认；不写failure、不回签、不修复旧文件。

## 6. 最少验收，不堆回归

两次真实接收正常/BLOCKED小样可供全部定点场景复用；每场景只建自己的新登记/scope。人类字段仅来自TASK-025案例§0.1三份登记夹具0001/0002/0003，原文与SHA先核对，标记仅在测试证据外层。它们不是本批真实人类批准。

- 正常APPROVE保存及新进程/新模块只读核验：真实store.save一次/P1一次，完整P1返回与落盘正文相等；verify十一键/effective=true，来源与共享绑定准确；重复保存拒绝且旧字节不变。
- HOLD及一个BLOCKED对照：合法HOLD可保存但effective=false；BLOCKED+APPROVE真实P1拒绝，无成功事件；HOLD/REJECT不启动下游。REJECT可做轻量对照，不重跑冻结质量矩阵。
- 错批次/旧材料绑定、错scope或已有事件、锁/failure、一个未知项、一个同步外层摘要仍内层矛盾：定位拒绝，不覆盖、不写入核验现场。
- 一个来源晚变更：真实必要消费返回后改本轮来源字节，本次拒绝；保存失败留诊断，verify只读失败不写诊断。无需遍历32个路径逐一注入。
- 新context writer真实句柄半写OSError、receipt完整写后sentinel：主因/映射/坏字节保留；不重跑冻结store半写入口。
- 准备器/store/P1实际使用模块上轻量完整观察，单一profile计数闭合，直接/嵌套/重放分列。保存人类输入/完整返回或异常，前后指纹真实取得，不改返回；禁止下游入口命中0。不要双通道观察器或大证据框架。
- 测试收尾按已验收TASK-026原则：写盘前独立完整预期，真实同缓冲比较、双向ID/计数、待写缓冲台账、末次字节确认；正常0/PASS/空failures；一个写后内容或缺记录控制实际1/FAIL/非空failures。复用同一次观察的新副本，不重复建业务链，不只按flag return1。

所有测试输出从未存在；**禁止递归删除、移动或清理任何探针目标**。根自身/越界反例只验证拒绝与未创建，不准备清理列表。唯一允许删除动作是经身份核对释放本次自建技术锁。旧损失139项不重建，旧326项越界产物不动。

## 7. 交付

先局部通过，再一次最终全树比较。expected known historical loss139单列，不能再写missing=0；当前基线内现存文件不得新增missing。仅改本脚本，新增四类明示根与三交付文件按确切路径登记；旧恢复27项/损失登记/冻结件均不变，无前缀豁免。源/记录/技术锁动作和文件哈希分别记录。

运行版本标记升 `TASK-027-runtime-gate1-1.0`，保留TASK-025/026既有协议名；新批次绑定实际新字节。回执列实现、真实测试/注入/读取旧证据/未执行范围及最终哈希。必须全部完成才移in_review；不自行done，不实施下一任务。发现需追加事件/改契约/扩大执行权限，停止并升级C类设计，不自行扩面。
