# TASK-022：P2-S1 独立 Gate 决定快照保存与恢复核验

执行分类：**C 类，GPT 设计 + DSH 执行**。本卡授权新存储凭证布局，不授权真实 Gate 放行或宿主接线。GPT 为 Architect / Reviewer；人类保留全部业务判断和真实批准。

## 1. 前置与目标

TASK-021/R1/R2 已通过 P1 整体验收，依据 `docs/reviews/REVIEW_TASK_021_R2.md`。D1/D2/D3 和正式 V1 生效确认已完成，不重新征求；契约生效和 D2 建设许可都不是任何批次的 APPROVE。

本卡只新增一个独立组件：接收四个内存对象，真实调用已验收 P1 核心，独占保存收到的对象快照及完整返回；随后可从六份固定文件只读恢复、复算和核验。**范围为 STORED_SNAPSHOTS_ONLY**：验证已提供快照内部关系及实际存储字节，不发现全局历史，不实读业务材料/工作簿/DB，也不证明材料清单完备或来源真实。

这只是 P2 第一部分。后续 Gate1 适配器、Gate2 适配器分别承担本批材料实读、完整历史枚举和宿主接线，分卡验收；本卡不得顺便实现这些内容。没有真实初判、0009、AI、终判、网络、UI、ERP、强身份认证或新依赖。

## 2. 允许文件与冻结范围

仅新增：

- `scripts/store_demo_human_gate_decision.py`。
- `tests/test_store_demo_human_gate_decision.py`。
- `docs/HUMAN_GATE_DECISION_STORE_GUIDE.md`。
- `docs/EXEC_REPORT_022.md`。
- 本轮新 `data/human_gate_decision_store_tests/task022_<唯一名>/` 证据容器，以及新 `data/human_gate_decision_records/task022_<同轮唯一名>/` 下的测试记录目录。必要过程容器留存、不回写；不新增其他业务数据根。

**不修改任何既有文件**，包括 P1 核心/测试/指南、正式契约、生效登记、协议/案例、宿主/控制器、全部上游、旧任务/评审/回执/样本。不得在 scripts/tests 中另加通用框架或复制一份 P1 算法，不创建 Git、不安装依赖、不建 batches/SQLite/审阅包。

先核验 `data/reviews/task021_r2_gpt_20261013_214052/review_result.json` 为 ACCEPTED，并核对其中 `source_hashes_after` 的完整 SHA/项数后，以该清单为保护基线。只按该清单声明的两个确切元数据路径单列自指排除，不按 reviews 目录前缀豁免未知文件。

重点冻结身份：

- P1 核心：`5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79`。
- P1 测试：`472586942f9822bd249385a88607a90c5dbcf9db54730b1ea5c18296be9885a8`。
- P1 指南：`9345baf16297dd53a7bfeb83d5392697c08b86f11d34504f78f068546fffd980`。
- 正式契约 `docs/AUDIT_CONTRACT.md`：`174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`。
- 生效登记 `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md`：`042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`。
- 协议：`68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`；案例：`bd1fc37dc2437454b87b5453d7df90a6dcd6f3f79e84c3e75a335381fcf2d2a6`。
- 宿主：`3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`；控制器：`a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c`。

正式契约生效时间按原文登记；不要用 Gate 决定的时间语法重新否定契约生效，也不要生成新确认或修改人类文件。

## 3. 固定接口和错误语义

独立公开 API，**本组件不加 CLI**：

```python
save_human_gate_decision_snapshots(
    out_dir, submission, materials, expectations, *, prior_history=None
) -> dict
verify_human_gate_decision_snapshots(record_dir) -> dict
```

保存的是内存对象快照；没有 submission-file 接口，不宣称保存原始 JSON 文件的排版/BOM/换行。所有人类字符串原文保留，不生成身份、时间、事件、原因或决定。

新增 `HumanGateDecisionStoreBlocked(field, reason)` 和 `HumanGateDecisionStoreError(stage, reason)`：协议/路径/前提/不一致用 Blocked；运行/I-O 用 Error，均保留 `raise ... from exc` 原因链。P1 Blocked 映射后保留实际 field/reason，P1 Error 映射后保留 cause。不要将原生 JSON/Unicode/I-O 异常包装为成功。API 没有退出码，不虚构“API exit 1/2”；测试入口成功 0、断言/审核失败非零。

两个 API 成功返回都**恰八键**：

```text
status: 保存为 HUMAN_GATE_DECISION_SNAPSHOTS_STORED，核验为 HUMAN_GATE_DECISION_SNAPSHOTS_VERIFIED
scope: STORED_SNAPSHOTS_ONLY
identity: {batch_id, gate, event_id}
record_fingerprint: P1 完整返回中的规范记录指纹
manifest_file_sha256: 本次实读 manifest 确切字节 SHA
execution_allowed: false
workflow_connected: false
ai_enabled: false
```

三个 false 必须是严格布尔值。identity 三项分别来自本次已核验 P1 record；普通 ID 只按 P1 字符串规则精确保留，64 位十六进制样式、前导零或 SIM 前缀本身不是来源证明，也不能因此拒绝。

## 4. 目录与六份固定文件

生产 API 只接受解析后的项目 `data/human_gate_decision_records/` 的严格后代目录；不能等于该根，且本轮测试只在 §2 指定的新轮次根内。由调用方显式传路径，不从 batch/event/actor ID 拼目录。拒绝越界、已有目标（含空目录）、符号链接/Windows reparse 路径；检查已存在祖先，随后独占建立叶目录。只创建必要父目录，不删除、移动或覆盖任何现有对象。verify 同样检查允许根和路径。

成功叶目录文件集合**恰为六份**，不含子目录、未知文件或 failure：

```text
submission.json
materials.json
expectations.json
prior_history.json
decision_result.json
manifest.json
```

前四份为本次消费的独立快照；第五份为真实 P1 完整两键返回，不只存 record 或一个摘要。所有快照与返回采用 P1 canonical JSON 字节，末尾统一加**一个 LF**，UTF-8 无 BOM；字节先明确构造，再以真实 `xb` 独占写入，不能依赖文本换行转换。按确切待写缓冲逐文件读回验证长度、SHA、对象相等。规范对象指纹不含末尾 LF，与文件 SHA 分列。

manifest **最后写入**，不内嵌自身文件哈希。保存 P1 record 原样：17 键、note 和六项 boundaries 均不改，包括 `boundaries.persisted=false`。它表达 P1 内存记录语义；物理保存事实由外层 store status 表达，不把它改成批准或放行标志。

## 5. manifest 的封闭协议

版本常量 `TASK-022-human-gate-decision-store-manifest-1.0`。顶层**恰八键**：

- `manifest_version`：上述常量。
- `store_status`：`HUMAN_GATE_DECISION_SNAPSHOTS_STORED`。
- `scope`：`STORED_SNAPSHOTS_ONLY`。
- `identity`：恰 `{batch_id, gate, event_id}`，分别与 submission、materials、expectations（其对应字段）及 decision_result.record 精确闭合；没有对应 event 的对象不补造 event 字段。
- `component_bindings`：恰四项文件 SHA：`core_file_sha256`、`store_file_sha256`、`contract_file_sha256`、`contract_effective_record_file_sha256`。
- `fingerprints`：恰六项：`submission_fingerprint`、`materials_snapshot_fingerprint`、`materials_body_fingerprint`、`expectations_fingerprint`、`prior_history_fingerprint`、`record_fingerprint`。
- `payloads`：上述五份 payload 按 relative 的 UTF-8 字节序严格升序列出，恰五项；每项恰 `{relative, byte_size, file_sha256}`。
- `boundaries`：恰 `{workflow_connected:false, execution_allowed:false, identity_authenticated:false, source_authenticity_proven:false, ai_enabled:false}`。

所有层级拒绝未知/缺失键，常量/类型严格；byte_size 是非负整数，bool 不冒充；所有 SHA/指纹使用**全串匹配**的 64 位小写十六进制，不 strip/截断/改大小写。payload relative 只能是五个固定字面文件名，重复、遗漏、绝对路径、分隔符、`..` 均拒绝，不先 normalize 再宽容接收。

指纹算法沿用 P1。`materials_snapshot_fingerprint` 对收到的完整 materials 对象计算；`materials_body_fingerprint` 仅移除顶层 materials_fingerprint 后计算，并与 P1 已验证的派生字段、submission 绑定、expectations 独立预期闭合。其余快照指纹分别对对应完整对象计算；record 指纹对 record 正文计算。文件 SHA 对保存的确切字节计算，不能互相替代。

component_bindings 来自固定项目路径的真实文件实读：已冻结 P1 模块、本存储模块、正式 V1、已登记生效确认文件。正式契约/P1/登记须先匹配 §2 冻结值；输入材料及独立契约预期必须指向同一正式 V1 SHA。store_file_sha256 为本次运行模块实读值。不能用测试答案册或调用方声明值冒充实际组件文件哈希。

这些组件绑定与 P1 输入中的 run_binding **分别命名**：后者是调用方提供的业务运行快照，本卡只由 P1 核验内部关系，不声称已实读其业务代码/规则/配置/输入文件。不能要求合成夹具的 run_binding.code.file_sha256 等于存储模块 SHA。

manifest 不保存绝对机器路径、不生成时间/随机值或 ID。同样输入与相同组件字节在两个新目录应产生逐文件相同字节。

## 6. 保存顺序与失败现场

固定主序：

1. 检查目标路径/不存在和本次组件绑定。取得四个输入的独立快照，保留对真实消费对象的引用；不修改调用者输入。
2. **恰一次**调用真实冻结 `build_human_gate_decision_record(submission, materials, expectations, prior_history=...)`，只传四个内存快照。不得在 store 重写 P1 schema/决定矩阵/历史算法；`None` 由真实 P1 拒绝，不擅自默认空历史。P1 拒绝时不建立叶目录，不生成成功记录。
3. 核对真实消费引用调用前后规范指纹不变；完整返回及输入关系符合已验收接口，生成确定的五份待写缓冲和 manifest 待写缓冲。
4. 独占创建叶目录，独占保存五份 payload 并读回精确核对，最后独占写 manifest 并读回。
5. 在全部必要数据消费、组件绑定复测、文件集合检查之后、返回成功之前，**实读六文件字节**与本次待写缓冲/写后读回哈希逐项核对。manifest 预期只能来自本次待写/真实 writer 读回；不能在发生变化后重新采集为“新期望”。确认无 failure、无未知项，再返回成功。

不要在保存内额外调用公开 verify 而无意调用 P1 第二次；共享轻量字节/形状核对可以，但不得新造通用 I/O 框架。只要求函数成功返回前最后必要消费后的字节确认，不承诺抵御返回后的外部修改。

独占叶目录建立后的任何失败，只尝试在**该新目录**独占写 `failure.json`，保存本层版本 `TASK-022-human-gate-decision-store-failure-1.0`、失败阶段、Blocked/Error 分类、field（无则 null）、reason 和完整 cause/context 异常链。不能覆盖已有诊断、删除半写文件或重试覆盖来凑成功。诊断写入失败时保留原异常并报告诊断错误，不能吞掉主因；不要求强行写成成功凭证。verify 只要发现 failure 就拒绝，即使诊断本身损坏。

叶目录建立前拒绝不写任何失败文件。多进程争用仅保证独占创建/不覆盖，不实现锁服务、事务数据库或全局事件索引。重复事件以 P1 的已提供 prior_history 为准；不能宣称本组件发现了未提供的历史或保证跨目录全局唯一。

## 7. 只读恢复核验

verify 不接收调用方 status/期望作为替代证据：

1. 检查路径、无 failure、固定六文件集合。**同一缓冲**绑定每份文件的长度/SHA 与解析对象；不先 hash 一次再另读 JSON。
2. 核验 manifest 全部封闭 schema、实际文件字节与 payloads、六项对象指纹和身份闭合；组件绑定与当前真实组件/契约文件匹配。版本/文件身份变化则如实阻断，不迁移、补签或重写旧记录。
3. 从四份已绑定快照**恰一次**调用同一冻结 P1 核心，按真实完整返回严格比较 decision_result 的两键对象、record 指纹和输入未变。恢复允许这一次纯核心复算；不能调用宿主、控制器或业务核心。
4. 全部必要 JSON/核心/组件消费完成后，返回成功前再次实读六文件字节，与本次初始缓冲比较，并确认固定集合/无 failure。拒绝只读，不写 failure 或其他文件。保留可定位文件/字段消息。

只有当前组件字节和固定正式契约一致的记录可按本版本恢复。这个本地核验不提供防同权限攻击者伪造的签名保证，也不替代将来适配器对当前材料和完整历史的实际核查。

## 8. 最小验证：先小样与必要负向，最后一次回归

测试入口：`.venv\Scripts\python.exe -B tests\test_store_demo_human_gate_decision.py --out-dir data\human_gate_decision_store_tests\task022_<新名>`。证据根须新/空且在指定根内；记录叶目录必须从未存在。全部合成审批输入明确登记为 **PROTOCOL_TEST_FIXTURE_ONLY**，不是主理人真实提交，不产生批次批准效力；不要把此标识塞入 P1 封闭 schema 的未知键。

按以下六组完成，可在一个入口复用准备对象，不为每个轻量反例重建业务链：

**G1 正常与确定性**：Gate1 OK 的 APPROVE/HOLD/REJECT、BLOCKED HOLD，Gate2 合法 APPROVE 各有控制；至少一组双目录字节确定性。真实 P1 返回单份保存、与 decision_result 完整对象严格相等；输入实际引用前/后/收尾指纹一致、人类字符串原文不变、返回与 manifest/文件闭合。采用正文夹具配方在新测试内构造；不运行旧工具，不复用旧模拟批准作为真实凭证。测试通过期待来自独立规范序列化和关系核对，不能只调用被测 helper 生成期望。

**G2 前提与路径**：已有叶目录/已有空目录/越界/根自身均拒绝且旧文件不变；空白 reason、模拟 actor、BLOCKED APPROVE、缺历史由真实 P1 拒绝且不建叶目录。先存一次再同路径提交被拒，不能覆盖。不要以 ID 看起来像哈希或 SIM 前缀当作负向依据。

**G3 恢复负向与只读**：独立副本分别改 payload 字节、manifest SHA 加 LF、byte_size=true、未知项、遗漏/重复/越界名单、failure、跨文件 batch 矛盾，均可定位拒绝且核验前后目录不变。至少一例同步外层 payload SHA/对象指纹但使内层提交/材料绑定矛盾，必须由真实 P1 或关系核验拒绝；不能只靠旧外层哈希提前拒绝冒充内层覆盖。

**G4 真实 writer 与晚变更**：一例在真实 xb 句柄 write 中写前半段后抛 OSError（不替换整个 writer），一例真实 manifest 完整写入并读回后抛 sentinel；保存 Error、完整链、失败现场、verify 拒绝，旧文件不变。另各一例保存/核验最后必要消费返回原值后追加一个 LF，必须**本次** Blocked 且指出对应文件；记录实际读/写次序和命中1，不能靠“第几次调用”未观察就猜。verify 反例不写 failure；保存失败只写自己的新目录诊断。

**G5 边界与真实调用观察**：save 正常真实 P1=1、verify 正常真实 P1=1、提前路径拒绝 P1=0，公开存储 API 次数与嵌套 P1 次数分列，不要求总数相等。观察真正核心入口或宿主实际模块对象上的函数，不包装 store API 伪称纯核心计数。业务核心/宿主/控制器调用为0；组件不导入它们，也不读取业务材料文件。未观察子进程内部次数写 null。核心返回 boundaries 不改，外层不放行，无0009/真实初判/AI。

**G6 证据收尾与保护**：全部公开 API/真实核心调用有完整输入快照、完整返回或异常、真实 traceback/cause/context、权威登记。稳定最终 summary/checks/counts 后，台账逐项实读 exists/长度/SHA，调用登记与记录双向一致；隔离审核副本仅删一条登记须由真实 audit 失败、原件通过。最终审核非空必须影响 failures/summary/进程返回，不能检测到错误却 PASS；复用已明确的有界失败收尾模式，不反复“改文件再重建台账”。正常容器与一项终审字节故障现场分开，失败现场不恢复凑成功。

本卡不重跑 P1 的195次完整入口、协议117例全套、宿主/业务历史入口。P1冻结，只做保存/恢复所需控制与新 I/O 反例。局部错误先定点修正，不重复完整建链；新增失败或代码变化才扩大有关验证。

## 9. 交付、保护与停止

正文/测试/指南/回执定稿、局部及正常入口通过、必要故障实测完成后，**一次**完整保护扫描：基线已有文件 changed=[]、missing=[]、读取错误0；新增仅按本卡明确文件/轮次根的确切路径集合登记，范围外新增必须列出，不做目录前缀豁免。扫描后只有限登记本轮证据与最终文件身份，不再改实现再声称同一次扫描有效。

回执区分：执行端实测、读取旧证据、未执行；列出保存/核验 API、真实 P1、进程/守卫各自 scope、正常与预期故障结论、冻结件、全部交付最终字节 SHA、保护基线和实际次数、过程失败/偏差。自身最终哈希只在交接消息给出，不写回自身。指南明确六文件协议、快照保真范围、只读核验可调用一次纯核心、版本不兼容策略以及尚未完成的 Gate 适配器职责。

执行端完成本卡后停止实施并交 GPT 验收；这不取消 GPT 验收通过后制定下一卡的持续授权。人类操作看板，技术验收不能代替真实批准。若发现需要修改冻结 P1/正式契约/宿主、改变决定矩阵/身份/材料时序或扩大历史发现范围，**立即停止受影响实施、保留现场并向 GPT 报告新设计范围**；不得因本卡已属 C 类就自行扩大授权。新业务问题交人类明确决定。
