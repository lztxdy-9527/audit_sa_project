# TASK-021：真实人工 Gate 决定记录的独立纯内存核心（P1）

状态：待 DeepSeek 执行。Architect / Reviewer：GPT；执行/测试/调试：DeepSeek；业务决定与批次批准：人类主理人。

## 1. 目标、依据与当前状态

将 TASK-020/R1/R2/R3 整体验收后的协议实现为**独立纯内存 Gate 决定记录校验与构建核心**。本卡只完成 P1；返回内存记录不等于持久保存、身份认证、批次批准或运行放行。

人类已明确采纳契约内容、允许限合成数据的真实人工决策保存/校验建设，选择“批次初判及原因必填、逐条备注可选”；并手动建立正式 V1 后确认生效。这些决定沿用，不重新征求。D3 归 P3，不把初判字段混入本卡 Gate schema。

任务开始必须实读核验下列输入，不运行旧辅助脚本：

- `docs/AUDIT_CONTRACT.md`：**`174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`**，13289 字节，V1/已生效。
- `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md`：**`042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`**；含人类明确生效确认。头部生效时间原文已登记且未规范化，不把它当本协议 Gate 时间的合法夹具，也不追溯否定契约生效。
- `docs/decisions/REAL_FLOW_DECISIONS_20261013.md`：**`bface683b1a9eb41250e20822f471621b289f4b8237944a851d3d0554a0635e4`**。其当时“正式文件尚待建立”属于历史快照，后续生效登记已补齐，不回写旧纪要。
- `docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md`：**`68c931b33ac51bdc5634247748d20463816e1a3a2105202fdd43942db26a3e76`**，39298 字节。算法、schema、常量、14 步与 11a—11i 以该确切正文为准。
- `docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md`：**`bd1fc37dc2437454b87b5453d7df90a6dcd6f3f79e84c3e75a335381fcf2d2a6`**，43060 字节，117 个主表设计案例。
- `docs/reviews/REVIEW_TASK_020_R3.md`：整体验收与本卡授权依据。协议的旧标题/“尚未验收”标记保留交付快照语义，不改冻结文件；本次技术验收状态看新评审。

开发宿主仍止于模拟 0008；真实批准 null、真实初判未保存、next=false、AI 未开放。P1 不改变这些运行字段。正式契约生效、D2 建设许可、本卡实施及技术验收均不批准任一批次。

## 2. 唯一允许的文件范围

仅新增以下四个文件与一个新证据容器：

1. `scripts/build_demo_human_gate_decision.py`——纯核心。
2. `tests/test_build_demo_human_gate_decision.py`——测试与证据入口。
3. `docs/HUMAN_GATE_DECISION_GUIDE.md`——实际接口、语义、能力限制与验证方式。
4. `docs/EXEC_REPORT_021.md`——执行回执。
5. `data/human_gate_decision_tests/task021_<唯一新名>/`——本卡夹具快照、完整返回/异常、台账、计数与保护结果。失败过程容器同属本卡命名范围，保留、不回写。

禁止修改任何既有文件，包括正式契约、协议/案例、TASK-020 全部回执/证据/评审、SPEC、控制器、宿主、上游所有核心/测试/指南、配置、输入工作簿和历史批次。不要创建 AGENTS.md、正式批准/生效/运行配置、持久化目录或迁移脚本，不新增依赖，不初始化 Git。

保护基线：`data/reviews/task020_r3_gpt_20261013_193016/source_hashes_after.json`；先核验同目录 `review_result.json` 中 **verdict=ACCEPTED**、清单 SHA/项数，再使用该基线。两个元数据自身未纳入清单，只允许按两个确切路径单列，不豁免整个 reviews 目录。本卡新增路径须逐项登记，范围外新增必须报告。

## 3. 公开入口、返回与异常

实现唯一业务入口（保留已验收参数名、关键字边界和语义）：

```python
build_human_gate_decision_record(
    submission: dict,
    materials: dict,
    expectations: dict,
    *,
    prior_history: dict | None = None,
) -> dict
```

成功外层**恰两键**：`{"record": <17键record>, "record_fingerprint": <64hex>}`。record 形状、嵌套封闭键集合和派生来源严格采用协议 §14；record 不内嵌自身指纹。协议常量仍为 TASK-020 的 1.1，不因实施卡编号改名。

异常：

- `HumanGateDecisionBlocked(field, reason)`：协议、类型、绑定或前提拒绝；有可读取 field/reason，消息能定位，不把异常包装成成功记录。
- `HumanGateDecisionError(stage, reason)`：意外内部错误，使用 `raise ... from exc` 保留实际原因链；不得吞掉、误报成功或统称协议阻断。

`prior_history` 的默认 None 只让缺省调用进入函数体；缺省/显式 None 对合法前三个对象均在第 4 步 Blocked，field=`prior_history`。不得默认空历史或默认完整，不改为 Python 调用前抛 TypeError 的必需关键字。

**无 CLI、无文件保存、无恢复或放行入口**；测试脚本自身可有 CLI。私有辅助函数/实现组织由执行端决定，不增加业务入口或输入字段。

## 4. 必须保持的核心不变量

### 4.1 纯内存、输入保真和确定性

仅用标准库，不读写文件/数据库/工作簿/网络，不调用子进程，不依赖当前时间、随机数、环境或可变全局状态。不导入宿主、控制器、上游核心、测试、答案册或旧夹具模块。核心不从磁盘核验契约生效；其能力仅是比较调用方提供的对象/预期，实读与生效核验属于后卡适配层。

四个输入（含 prior_history）的调用前后内容不变；保留人类字符串原文，不 trim/大小写转换/转数字/补零/改写 reason。返回与输入之间、独立调用返回之间无共享可变别名。同输入同输出。

canonical JSON 固定 UTF-8、ensure_ascii=False、sort_keys=True、separators=(",", ":")、allow_nan=False；不要用文件排版哈希替代对象指纹。文件 SHA 字段是调用方报告的确切字节 SHA，核心不声称重新读取文件验证它。

### 4.2 封闭 schema 与固定顺序

完整实现协议 §3 的各层封闭键集合/类型/常量/枚举/列表规则，未知字段给完整 field；严格区分 bool/int/str，计数严格整数、byte_size≥0，普通 ID 仅非空字符串且原样保留。所有哈希字段全串匹配 64 位小写十六进制，不允许尾 LF/CRLF/空格、大写或截断。

files/阻塞列表/历史列表遵守已定唯一与 UTF-8 字节升序，**拒绝无序输入，不静默排序输入**。relative 按协议形式与精确字符串比较，不做文件系统解析或归一化。

按协议 §5 的 14 步检查；第1—4步为形状/类型/常量/列表，第5—12步为值/关系，第13步矩阵、第14步构建。前序内部常量、质量、边界和运行绑定按11a—11i。测试每个反例应先使非目标部分合法，确认唯一最早违反项；不能倒换检查顺序或改核心规则来保住旧期望步号。书面缩略构造展开中的细节需在新测试/回执交代，冻结案例不回写。

### 4.3 材料、运行、契约与独立预期

materials_body 唯一算法为**仅删除顶层 materials_fingerprint**，保留其他内容与列表顺序。正文复算值＝materials派生字段＝submission.request_binding.materials_binding＝expectations.expected_materials_fingerprint；不对含自身指纹的整对象求摘要、不置空替代删除。

files 与 expected_files 双向完整比较，再逐项比较文件 SHA；文件字节 SHA 与整体材料指纹不能替代。调用方两侧同时少报的文件、所声明范围之外的历史、磁盘当前状态与来源真实性均不在核心发现能力内，指南必须说明。

当前运行绑定六字段与独立预期严格相等；契约版本/文件 SHA 与独立预期相等、contract_effective 严格 true。不得把候选契约、开发态状态、D2 纪要当某批次独立预期或批准。协议定义的 Gate2 材料是批准前可得角色，不新增筛查报告前置条件。

### 4.4 完整前序记录与历史

Gate1 前序提交/前序预期均为 null。Gate2 必须有完整 Gate1 wrapper、独立 expected_prior_gate1、历史同一 wrapper；字符串 APPROVE、摘要、模拟凭证或开发态 phase 不能替代记录。

按11a—11i核验封闭形状、常量/note、record指纹复算、Gate1/同批次/APPROVE/HUMAN_DECLARED、契约一致、**前序与当前材料及当前独立预期六字段运行绑定一致**、质量 OK/严格零计数、固定false边界、三处指纹身份与历史闭合。expected_prior_gate1.run_binding 作为独立前序预期也须参与对应比较，不可接收后忽略。Gate1/Gate2 材料集不同，材料指纹不要求相等。

记录自身完整验证不变；本卡不为修正旧夹具而向 API 加 prior_materials 参数或新验证算法。历史作用域仅按 declared_scope/declared_complete 的调用方声明处理；拒绝缺失/非布尔/false、逆序/重复名单、当前重复 event_id、同批次同Gate既有成功APPROVE，不覆盖记录。

### 4.5 时间、质量和能力边界

时间恰两种写法（日期；带秒与±hh:mm的完整日期时间），全串匹配、真实日历/闰年、分量与偏移至±14:00；原文保存，不补时间/时区或生成normalized值。按协议统一 field=submission.decided_at_raw，类型错误先于语义检查。

质量状态与三个列表自洽；完整 BLOCKED 允许 HOLD/REJECT 内存记录，APPROVE拒绝；FAILED 对三种决定均拒绝；矛盾状态在早期拒绝。计数由真实列表长度派生。

所有成功记录（包括 APPROVE）固定 execution_allowed严格false、boundaries六项严格false；不产生 gate1_approval/gate2_approval/next/AI 字段，不写运行状态。decision_source/actor_kind 是结构声明，不能认证作者。reason 中 D2 或指令样式文字、SIM-EV 前缀、恰64位hex普通ID均不能变成权限或被猜测为来源证明；只按合法字段原文保存。

## 5. 验收设计与实际运行

先小样正向和必要负向，局部失败定点修复；最终在**一个全新容器**运行一次完整本卡入口。无需重跑 TASK-002—020 历史入口/业务链、宿主测试或旧文档核验脚本。

建议入口：

```text
.venv\Scripts\python.exe -B tests\test_build_demo_human_gate_decision.py --out-dir data\human_gate_decision_tests\task021_<新名>
```

容器须位于限定根下且为新/空目录；不能覆盖旧现场。可提供小样/定点子集，但未执行的证据审核或保护项写 null/not_executed，不填默认零。

下列维度必须真实覆盖。按已验收117个设计案例给**案例→实际调用记录→断言/结果**映射；可合并重复构造或把一行的多个边界拆成多调用，说明范围，不强求117恰等于调用次数。仅检查文本锚点不算运行案例。

全部测试对象使用明确虚构的 `PROTOCOL_TEST_FIXTURE_ONLY` 语境，无审批效力、不复用实际人类提交、不预填真实表单。夹具说明放证据外层或合法测试字符串，不新增协议输入键，也不追加到固定note。

- **正常与完整返回**：BASE1 Gate1三种决定、BASE2合法Gate2、C-116同版本；返回恰两键/record17键/全部固定常量和边界/来源原文均符合协议。BASE1实际完整record及其指纹与正文展开得到的record1独立比对；Gate2也须独立推导完整期望对象，不只检查状态/摘要。哈希计算期望不得调用待测核心的同一个helper自比。
- **材料与独立绑定**：错批次/Gate/request、两类哈希互换、改材料仍用旧预期、更新外层但文件名单不符、只改外层、缺/多/重复/无序文件，契约与运行逐字段错绑，非法relative。变更反例遵循先合法构造再复算，不能靠另一处未同步摘要提前拒绝冒充目标断言。
- **前序与历史**：Gate2缺/字符串/摘要/模拟/错误Gate/批次/决定/契约/常量/note/质量/边界，复算前序记录而非只信外层指纹；三处记录身份与expected_prior_gate1.run_binding矛盾；缺省/None/声明不完整/空白scope、重复与逆序历史、重复当前event、既有成功批准。C-112—C-115 使用R3正确的完整前序材料→记录→wrapper同步构造，实际拒绝field为各自11f目标；对照C-116成功。只读旧JSON可作交叉来源，不运行/导入旧构造器；测试自行构造快照，期望值不能只硬编码评审摘要。
- **schema/类型/哈希/时间**：各层未知键与缺五项义务、空白、bool冒充、严格整数，所有SHA位置用代表性分组覆盖LF/CRLF/空格/大写/截断；日期/月日/闰年、无时区、±14:00边界、越界时间偏移、额外后缀、缺秒/小数秒。非法输入应是可定位Blocked，不泄漏原生KeyError/TypeError/AttributeError冒充预期拒绝。
- **质量完整矩阵**：OK三决定；结构或质量BLOCKED下APPROVE拒绝、HOLD/REJECT成功；FAILED三决定拒绝；矛盾状态早期拒绝；实际派生计数严格整数。失败无成功记录。
- **确定性/保真/无别名**：四入参保留同一真实引用，在调用前与调用后取指纹；反例拒绝也不改输入。改变返回的深层对象不影响入参或另一次返回；前导零/64hex/SIM-EV ID原文保留，reason含D2与指令样式文字正向保存且无新增权限。
- **纯内存与异常**：导入完成后在真实核心调用期间守卫 open/os.open/socket/子进程等，合法调用成功且命中0；守卫调用的原始返回在解除守卫后落盘登记，不重调核心凑记录。意外异常采用受控内部注入明确标为注入，真实进入核心公开边界，验证HumanGateDecisionError及cause链，与协议Blocked分列；不把宿主映射替身当真实算法观察。

## 6. 证据、计数与保护

每次进入**真实公开核心**的调用（包括正常、预期拒绝、注入、守卫、为Gate2准备前序的核心调用）均登记并保存完整输入快照/完整返回或异常类型、field/stage/reason、traceback、完整cause/context链。在真实核心入口观察调用数，与登记覆盖数核对；不能用测试外层调用次数冒充核心次数。守卫中禁止证据文件写入，解除后保存那次已观察结果。

证据至少含：summary/checks/failures、case映射、api_records、权威call_registry、evidence_ledger、counts、独立期望/夹具及保护结果。台账逐文件实读exists/字节SHA，与调用登记双向核对；missing/unregistered进入正式failures。隔离自测只删审核副本一条登记即必须失败，原件仍通过，不为此再建业务样本。

调用总数、返回/Blocked/Error/意外、守卫命中按真实现场导出；测试运行器进程与核心API分列。无 receiver/checker/业务链执行就标not_executed，不沿用历史模板填0；所有组总数与子集scope明确。

局部测试完成、核心/测试/指南/回执定稿且最终完整入口通过后，仅做**一次全树保护扫描**：对新验收基线 changed=[]、missing=[]、读取错误0、范围外新增0。扫描排除项沿用基线，不扩大范围。扫描后只对本轮有限新增产物/回执做最终身份登记，不再修改核心/测试/指南；如之后确需改这些文件，披露并按受影响范围重测，不把早先测试说成最终字节验证。

回执给四个交付文件写后实读大小/哈希（自身最终SHA只在交接消息给出，不回写自身）、真实运行命令/退出码/组数/调用scope、独立比对、保护基线与结果、失败过程及未执行事项。区分执行端自测与GPT复验，不宣称纯内存VALIDATED已保存真实决定。

## 7. 停止点与下一阶段

本卡成功止于 **HUMAN_GATE_DECISION_MEMORY_VALIDATED** 的纯内存核心。无持久化/恢复/独占保存/失败现场文件协议，无宿主/控制器接线，不新增0009，不填写或修改真实批准、初判、next、AI或终判，不接UI/LLM/网络/ERP/真实数据。

完成本卡后执行端停止本轮实施并移交GPT验收。通过后GPT按持续授权制定P2有界任务；Gate1/Gate2保存和接线仍分阶段验收，不因P1通过自动放行。人类继续保留每批Gate决定与审计判断权。
