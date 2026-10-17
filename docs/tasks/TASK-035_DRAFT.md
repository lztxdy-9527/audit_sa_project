# TASK-035：人类独立初判纯内存核心（P3第一部分）

类型C：Architect固定协议和范围，GPT执行端实施，Architect独立验收。本卡只有 `data/reviews/task034_gpt_20261016_115103/review_result.json` 正式发布ACCEPTED后生效；不是批次批准，不启动执行会话。

## 1. 依据、前置输入和允许范围

先实读TASK-034评审/review_result，使用其最新source_hashes_after.json确切SHA/项数。再实读已接受两文档：

- `docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md`：29189 B / SHA `df5dace5f8ec2dfca820f9c74db6f5fa1d3a947005610ad72b8e8d59d1c38cfe`。
- `docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md`：24844 B / SHA `e02e1f49e16ebff6a3b683e4c76ece6dd81697569e4876d090a4cccb67d07d46`。

正式契约V1 SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`及D1/D2/D3持续有效；当前事实层停RT_FACT_PACKET_RECORDED。旧模拟初判核心/宿主0008及其记录冻结，不能换标签复用为本核心。

**首份人类夹具已登记**：`data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`，1627 B / SHA `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`。人类明确提供event_id="1"、actor_id="1"、declaration_note="1"、decided_at_raw="2026-10-16"、assessment="通过"、reason="无明显不一致且合规"；均作为原字符串保留。人类已选择只记录日期，不补时间/时区。先核对确切身份并将原字节/来源/允许用途保全到本轮证据根，标识PROTOCOL_TEST_FIXTURE_ONLY放schema之外。它不批准批次，不认证身份，文本中的“通过/合规”不是系统审计结论。不要把H_EVENT等符号名当值，不从Gate APPROVE/reason或旧SIMULATED记录改标签取值。

首份基样可用于正向/确定性/无别名及以其为基础的技术绑定变体。fixture_gap.json和human_fixture_followup_pending.json是前序过程，不再代表首份夹具缺失；原时间2026-10-16-12am不合法，不用于正向。若额外正向变体需要不同的人类时间精度/偏移、ID或“暂不能判断”的初判/原因原文，先取得并登记对应人类提供值；没有时相应项null+原因并明确缺口，不自行扩造、不声称已执行。可继续不依赖该缺口的实现/测试，最终验收由Architect评估剩余必需覆盖，不能用静态说明冒充动态PASS。技术绑定/错类型/无效值等隔离负例须记录从登记原件的单处受控变更，不作为新的人类决定。

仅允许新增：

- `scripts/build_demo_human_initial_judgment.py`。
- `tests/test_build_demo_human_initial_judgment.py`。
- `docs/HUMAN_INITIAL_JUDGMENT_GUIDE.md`。
- `docs/EXEC_REPORT_035.md`。
- `data/human_initial_judgment_tests/task035_<唯一轮次>/`：本轮输入夹具快照/源登记、完整调用/异常、台账/检查/保护/失败过程；必要辅助脚本只放该根。

所有既有文件冻结，包括协议/案例/本卡、全部其他scripts/tests、运行适配器、旧指南/回执/评审、配置/契约/生效登记、SQL/schema、批次/Gate/DB/facts/历史探针/锁/失败现场。不修改现有十四项运行代码清单；新核心此时尚未接入运行版本，由后卡另行明确绑定。无CLI/保存/恢复/运行接线/新业务链，无依赖安装、子Agent或跨会话指令，无递归删除/移动/清理。Python一律-B。

## 2. 唯一业务API与协议实施

```python
build_human_initial_judgment_record(
    submission: dict,
    materials: dict,
    expectations: dict,
    *, prior_history: dict | None = None,
) -> dict
```

外层恰record/record_fingerprint；核心实现版本 `TASK-035-human-initial-judgment-core-1.0`。协议中的submission/materials/expectations/record版本常量仍按已接受TASK-034设计，不擅自改版本字符串/字段集合。可有小型私有类型/关系/指纹helper；不新增通用框架/策略开关/其他业务入口。只有标准库，不导入旧模拟核心、宿主/控制器、运行适配器、上游、存储、测试、答案册、LLM或第三方库。

严格实施协议§1—§9及32组schema，不以本卡摘要替代正文：

- submission 9必需/2可选，输出副本11键；原身份、事件、时间、初判、原因及可选文本逐字符保留。去空白只判非空，不能改原文，不用审计结论枚举或关键词判断人类观点/作者；有原因暂不能判断、零条仍需人类输入。
- 自有对象键/type严格，canonical合法JSON；普通ID原字符串，SHA全串64小写hex，FILE与FP分列；bool/int/float不混同，不接受未知代签/phase/AI/终判/伪保存字段。上游不透明载荷只按协议消费范围核验形状/身份/ID/计数/来源指纹和完整packet FP，不重算事实算法或上下文。
- materials10键、唯一删除自身摘要后的9键正文；expectations12键独立预期不回退/刷新；8角色files名单排序/唯一/长度/SHA双向相等及内层关系闭合。来源、packet、finding_ids、inspect投影、run/contract/Gate投影关系按协议独立核验，不能只比外层M。
- 时间按协议两种格式、真实日历和±14:00范围，原串不变；不读时钟/补时区/推断人类时间顺序。
- prior_history语义必填，省略/None结构化Blocked，不默认完整空历史；显式三键历史、独立scope/FP/已核验索引、有界事件去重和同批首版不可覆盖。它是索引，不称完整历史恢复；核心不宣称验证未传入完整record或磁盘全局历史。
- 返回深拷贝无输入别名，record9键/binding10键/history_binding2键/八false边界、外置FP与固定note。VALIDATED不等RECORDED，不改persisted/next/AI，不产生初判文件或批准字段。

按协议§8最早核验顺序定位：可选备注ID重复、取证规范二元组重复在步骤1的语法检查首报（IJ-11/IJ-12）；步骤9再做当前finding归属等关系，不把先已可拒的重复延后。其他后步反例先满足此前步骤，缺键/错类型/未知键在消费前字段级Blocked，不靠捕获KeyError伪装。

异常为实际类HumanInitialJudgmentBlocked(field,reason)和HumanInitialJudgmentError(stage,reason)，均有reasons=[reason]。Blocked原样传播，意外Error(stage=internal) `raise ... from exc` 保留cause，无record。不吞主因，不把全部异常统称Blocked。core导入及调用均不得读写文件/DB/网络/时间随机环境、启动子进程或调用任何其他业务核心。

## 3. 测试输入、来源与最小验证

测试入口 `.venv\Scripts\python.exe -B tests\test_build_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_tests\task035_<新名>`，输出从未存在，旧失败过程保留。输入必须先独立定稿/登记，再造候选；人类字段遵守§1。测试侧可以构造明确标注的技术绑定/投影/独立预期/历史索引内存夹具，不称这些是当前实际Gate批准或当前运行恢复结果。

现有接受事实包可只读引用并登记确切文件SHA/对象FP作为基础载荷；不调用runtime/fact inspect或旧上游测试重建链，不读答案册。正常/零条载荷要分别来自相应已登记事实样例或明确标注的纯内存协议测试材料，不以删除C06b findings而残留旧计数/来源/FP凑正例。技术B/Q/FILE/FP/独立投影可按协议构造，所有关系先闭合；材料/投影测试仅证明内存协议，不声称实读了当前完整Gate/历史。

按IJ-01—IJ-34的问题族组织有限分组，不为了数量重复造业务链：

1. 登记人类字段上的合法批次/有原因暂不能判断、零条仍要求人类输入、可选省略/空列表、部分备注/null批次取证；完整返回与独立预期字节及FP一致，原文/原顺序不变。正常只真实调用一次即可观察；确定性/键插入序/无别名控制仅做必要额外调用，计数真实登记。
2. 必需/嵌套缺失、错类型/空白/未知字段、模拟/AI/SYSTEM来源、可选ID/重复/空文本和人类时间负例，精确field及实际Blocked类；零条自动状态/建设纪要/聊天对象不能代替提交。普通技术ID前导零/64hex与SHA格式边界分开。
3. 独立绑定族：批次/请求/三处M、FILE↔FP、外层M正确但来源/ID/inspect运行摘要/Gate前序矛盾、文件名单/整数类型、contract/run预期、历史None/不完整/scope/FP/重复事件/同批二次。测试阶段必要R-M隔离可更新外层M及其明确预期，但保持待测内层独立预期原值；记录哪些字段同步，不能运行检测后刷新。
4. 输入同引用进入前/返回后/所属调用收尾完整快照及FP；无别名深层修改返回不改输入；意外内部序列化接缝受控异常准确Error/cause；导入和调用的真实I/O/网络/子进程/时钟随机环境守卫，先受控探测证明守卫生效。测试自身读取输入/保存证据在守卫之外，核心代码实际入口profile计数与完整调用记录闭合。未观察/未运行项null+原因。

不复制新的通用测试框架；可只读复用已验收小型观察/短收尾helper，不能执行其旧业务run/main或修改旧测试。冻结独立内存预期 → 完整候选内容/台账实际读回审核 → 最后原始字节确认，必须真实支配main返回码、summary/failures；canonical比较类型敏感，不只看检查数量或自报状态。

对新定稿观察执行四个实际main新进程replay控制：normal0、candidate-return1、ledger-late1、checks-late1，源只读、坏字节保留、不回填候选/刷新预期；新增真实核心调用0，旧观察数不冒充新调用。记录argv/stdout/stderr/退出码、完整观察/父调用、实际代码对象profile及注入接缝。没有必要重跑历史大矩阵、建runtime/Gate/SQLite或测试保存层。

## 4. 定稿保护、交付与停止

代码/新测试/新指南/回执及局部检查定稿后，仅一次最终全树保护扫描，以本轮最新接受快照为基线：既有changed=[]、新missing/读取错误/范围外新增0；新增按四交付文件与本卡唯一新根展开为确切路径，无目录前缀豁免。接受快照自文件和review_result两条先前元数据单列，扫描后自身元数据有限登记。

139历史损失与本轮missing分开；27恢复、326越界、19命名偏差及TASK-030具名41 B锁目录偏差冻结不变，不追认/恢复/移动/清理/执行。旧模拟/拒绝/开发失败现场均保留。

完整交付四件长度/SHA、登记人类夹具来源与限制、完整正负输入/返回/异常/三时点、独立预期和同缓冲字节/台账、实际调用/CLI控制、保护结果及未执行原因。若必需夹具未提供，不填值凑最终PASS，不自行宣称完成全部验证；在可做工作完成后明确交代缺口。

本卡停止于HUMAN_INITIAL_JUDGMENT_VALIDATED的纯内存核心，不保存/恢复、不接运行层、不新建0009、不改变真实批准/初判/next/AI。后续独占保存/只读恢复及事实后初判接线分别另卡验收。看板由人类办理，执行端不自行ACCEPTED或继续下一任务。
