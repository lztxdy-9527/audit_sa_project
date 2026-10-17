# TASK-029：只读准备 Gate2 候审请求

类型 B：按已验收 TASK-025 设计补齐一个请求适配器，由 GPT 执行端实施、Architect 独立验收。TASK-028/R1/R2 已通过；人类负责看板 done 和任何真实业务决定。本卡不保存 Gate2 决定，不运行规则筛查。

## 1. 起点与范围

先只读核对 `docs/reviews/REVIEW_TASK_028_R2.md` 及 `data/reviews/task028_r2_gpt_20261015_211252/review_result.json`、同根 `source_hashes_after.json`（必须 ACCEPTED，哈希以 review_result 登记为准）。

唯一允许修改的既有文件：`scripts/runtime_gate1.py`，155899 B / SHA-256 `cf7f526ae3b6c222b3c0663a8473e9231e3ebcd7091e025d27ebcb238ec7346a`。实现版本升 `TASK-029-runtime-gate1-1.0`；保留已有七公开 API、协议、固定集合及前提。

仅新增：

- `tests/test_runtime_gate2_request.py`。
- `docs/RUNTIME_GATE2_REQUEST_GUIDE.md`。
- `docs/EXEC_REPORT_029.md`。
- 本轮新根 `data/runtime_gate2_request_tests/task029_<轮次>/`、`data/runtime/task029_<轮次>/`、`data/human_gate_decision_records/gate1/task029_<轮次>/`、`data/sqlite_tests/task029_<轮次>/`；技术 scope、load 和控制副本须落在这些根内。运行登记叶可在根内设 registry 子目录，其 load 同级。

只读复用已存在小样批次及已登记人类字段夹具。因代码绑定变化，正常验证须用当前版本建立新登记、Gate1 夹具事件和装载；不修改旧凭证迎合新版本，不重接收批次，不新增决定夹具。已有批次来源保持只读。

冻结所有既有测试/指南、TASK-025 设计/基样、准备器/P1/store、标准化/SQLite/schema、筛查/复算/事实/初判核心、契约/生效登记/决策登记、配置、开发宿主/控制器及全部旧证据。TASK-028 测试 SHA `48794abb496035732c8af8e96c153d80eaa832c9394a70dddf49cf46daa7a120`、指南 SHA `5941017f45b7d99640471032616220f7ffd47434e035d67537b583da02317357` 不变。

禁止递归删除/移动、清理现场或扩建审计框架。需改冻结件、改变证据链或批准语义时立即停止并升级 C 类，不扩大本卡范围。

## 2. 唯一新 API 与停止点

```python
prepare_runtime_gate2_request(
    batch_dir, runtime_dir, request_id, *,
    scope_dir, event_relative, database_path
) -> {"request": ..., "request_sha256": ...}
```

无 CLI、无 caller-supplied status/expected/request、无 submission 或人类字段输入。错误复用 `RuntimeGate1Blocked(field, reason)` / `RuntimeGate1Error(stage, reason)`，保留 cause，先判类型再消费。

API **只读**，不创建目录或文件、不写 failure、不调用保存 API。真实调用现有 `inspect_gate1_approved_load` 核验当批有效 Gate1、登记、四件产物与数据库，不信任调用方状态或自行拼一个 READY。准备窗口内 inspect 一次即可；其内部既有 Gate1/store.verify/P1 核验允许且须如实分列，不宣称 P1 零调用。禁止直接调用 P1 构造新决定、store.save、normalizer/loader 及所有下游业务核心。

本卡只返回内存中的候审请求：`request_persisted=false`。不发布 gate2_request.json，不修改登记叶恰两文件规则，不建立持久 RT_G2_PENDING 状态。TASK-025 中拟定的请求发布属于后续保存接线范围，原设计保留；本卡只是其前置只读组件。PREPARED 不等于决定、批准、放行或真实审计结论。

## 3. 固定请求与绑定

外层恰两键；request 恰六键：request_version、status、materials、expectations、evidence、boundaries。

- request_version=`TASK-025-human-gate2-runtime-request-1.0`，status=`RUNTIME_GATE2_REQUEST_PREPARED`。
- materials 沿用冻结 P1 七键：gate=`GATE2`、batch_id、run_binding、contract_binding、files、quality、materials_fingerprint。
- expectations 沿用冻结八键：expected_batch_id、expected_gate=`GATE2`、expected_request_id（非空字符串原样）、expected_materials_fingerprint、expected_files、expected_contract、expected_run_binding、expected_prior_gate1。
- evidence 沿用现有七键：source_manifest_version、source_batch_status、source_receive_exit_code、source_description、source_scope、code_manifest、rules_manifest。五项来源说明取本次已核验的 Gate1 context.request.evidence，并与现有 inspect 的实读链闭合；两清单取本次登记。不得使用未核验 context 或回调要求 scope 不存在的旧公开 prepare。
- boundaries 沿用现有七键对象，严格 false：request_persisted、decision_recorded、execution_allowed、workflow_connected、ai_enabled、identity_authenticated、source_authenticity_proven。

`expected_prior_gate1` **恰五键** gate、batch_id、event_id、record_fingerprint、run_binding，来自本次核验的完整 Gate1 记录/真实核验结果；必须 GATE1/APPROVE/HUMAN_DECLARED、同批次、六项运行绑定 canonical 相等。不得把一个 APPROVE 字符串或摘要当完整记录核验；未来提交所需完整 wrapper 不在本卡生成或保存。

共享 run_binding 从登记实读，与有效 Gate1 和装载三方 canonical 相等；代码清单仍14项、Gate1材料仍32项。不为 Gate2 另造代码/规则/配置/输入预期。正式契约版本与确切文件 SHA 分列按既有绑定核验。quality 只有在 inspect 实际成功且既有质量核验通过时才为 OK、三列表空，不允许调用方指定或把阻断改成 OK。

Gate2 的 files **恰十项**，relative 是下列逻辑映射（不是可任意 resolve 的路径），每项恰 relative/file_sha256/byte_size；按 relative 的 UTF-8 字节序严格升序且唯一：

1. `registry/runtime_registry.json` → 登记叶同名文件。
2. `registry/runtime_registry_readback.json` → 登记叶同名文件。
3. `gate1/decision_result.json` → 本次事件 snapshots/decision_result.json。
4. `source/batch_manifest.json` → 原批次 batch_manifest.json。
5. `source/quality_report.json` → 原批次 checks/quality_report.json。
6. `load/started.json` → 本次 load_dir/started.json。
7. `normalized/normalized.json` → 本次 load_dir/normalized.json。
8. `load/load_report.json` → 本次 load_dir/load_report.json。
9. `load/artifacts.json` → 本次 load_dir/artifacts.json。
10. `sqlite/runtime.sqlite3` → 本次显式且已核验的 database_path。

构造时排序；恢复/消费不静默排序非法输入。每项长度严格非负整数、SHA 为确切文件字节的完整64位小写十六进制；expected_files 与这十项双向相等。其他已消费事件/来源/静态文件虽不全列为 Gate2 材料，仍在操作起始读数与末端确认范围内。

materials_body 唯一为顶层删除 materials_fingerprint 的其余对象；指纹=sha256(canonical JSON UTF-8)。request_sha256 取完整 request 的 canonical 字节。沿用 ensure_ascii=False/sort_keys=True/separators=(",",":")/allow_nan=False；文件 SHA 与对象指纹不互替。Gate2 材料摘要与 Gate1 不同；两 Gate 的六项 run_binding 相同。返回深拷贝，无输入/结果别名；不生成 event_id/actor/决定时间/原因或预填判断。

## 4. 操作与末端确认

复用当前路径、capture、封闭 schema 和有界集合 helper；不要复制整套 inspect 或新增 I/O/观察框架。参数/路径检查后，在调用 inspect 前固定本次将消费的来源、登记、事件八文件、四件装载产物、数据库及静态绑定读数；同一次缓冲绑定对象/长度/SHA。inspect 的核验对象不得取自另一未绑定缓存。

全部必要消费、对象构造、摘要复算完成后，再与起始读数有界确认确切字节、既有批次/登记/scope/事件/快照/load/数据库固定集合、failure/锁不存在及逐级 reparse。不要以“刚读的新 capture 与自身比较”替代起始预期，不重复加载业务核心。最后只做原始字节/集合/路径确认，之后不再读取候选来生成成功返回。失败保持全程只读。

不重新计算规则或数据库金额算法；复用已验收 inspect 的只读行数、来源指纹和成功勾稽旗标核验。普通 ID 原文保留，不套“不是哈希”、isprintable 或目录名语义黑名单。

## 5. 最小验收

四组即可；不追求检查项数量，不为每个嵌套字段穷举，也不重跑历史大套件。

1. 正常：一个新运行版本的 C06b 小样完成既有登记/夹具 Gate1/装载，准备两次 canonical 相等；外层2/request6/materials7/expectations8/evidence7/boundaries7，十材料与独立固定映射实读长度/SHA 相等，prior5与真实 Gate1 记录闭合，共享六项相同、两材料摘要不同。准备调用 normalizer/loader/store.save 为0，嵌套 inspect/verify/P1 实际计数分列；返回后改副本不影响源，源与目录哈希不变。
2. 前提与类型：无装载、有效 failure、Gate1非APPROVE/错误绑定、错数据库路径、空/非字符串 request_id 的最小隔离反例定位拒绝；禁止入口0、无新文件。无需反复建立相同业务链，可使用本轮自建干净副本；同步依赖摘要时要说明目标错误未被更早问题遮蔽。
3. 晚变更：先观察真实 inspect 返回边界；其返回原值后分别给本轮自己的 DB 和事件/装载材料之一加 LF，另一个控制新增 load 未知文件。三例本次拒绝并指出目标；撤销 wrapper 保留变更仍拒绝，精确恢复仅本轮原件后正常；准备未写 failure。正常来源不改写。路径规则复用已有逐级检查，真实链接不能建立时如实 not_executed，不为本卡重复搭建链接设施。
4. 证据收尾：完整公开/嵌套实际观察、同引用必要输入前后、独立计数、真实返回/异常链、独立 canonical/文件哈希；在候选读取前冻结内存预期，磁盘内容和台账确切字节支配失败。复用 TASK-028 已验证的简短收尾逻辑，禁止新增通用审计框架。一个正常 CLI 收尾和三个 replay 负向（返回替换、台账末次消费后漂移、checks末次消费后漂移）为0/1/1/1，磁盘PASS/FAIL与failures一致；replay不再建链、不得刷新期望或回填坏字节。

不要求重跑 TASK-026/027/028 大套件；可做静态接口/旧固定集合核对与上述正常建立的连带检查。额外实跑如实计数，未执行 null+原因，不把 replay 条目称本轮核心调用。测试不得清理探针、改旧 harness 或旧证据。

## 6. 交付与保护

代码/指南/回执定稿、局部检查通过后一次最终完整保护扫描。changed 仅 runtime_gate1.py；其余新文件逐条按确切路径登记，禁止目录前缀兜底；范围外变化/新增、新 missing/读取错误为0。139历史损失、27恢复、326越界与R1命名偏差按接受基线单列，不重建、不追认。有限登记扫描后自身元数据，避免循环改写或反复扫全树。

回执写出起点/最终SHA与长度、各验收目标及实际field、实际调用范围、旧证据引用且未重跑、当前只读停止点。流程清单补齐证据引用，不为勾选重建业务链。全部交付后 in_review，执行端停止本卡；不自行宣布验收通过或推进下一任务。

真实批准仍 null，开发宿主仍0008、next/AI=false；不改真实流程授权、不接Gate2保存/筛查/复算/事实/真实初判/AI/终判，不生成0009。
