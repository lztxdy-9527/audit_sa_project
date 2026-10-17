# TASK-021-R1：前序/历史record完整校验与最终证据审核

状态：待DeepSeek执行。依据`docs/reviews/REVIEW_TASK_021.md`；本卡为定点修正，不进入P2。业务与真实批准仍由人类决定，DSH由人类操作。

## 1. 两项阻断与保留范围

B1：已同步摘要/历史/独立预期的非法前序record仍被Gate2接受；已提供历史wrapper/record损坏也可成功。B2：最终checks哈希与台账不符、summary未登记；实际核心入口计数和权威调用登记隔离审核缺失。

保留现有API签名、常量/输出17键、14步与11a—11i、材料算法、当前输入绑定/质量矩阵、纯内存/深拷贝/固定false边界。不得修改冻结协议或案例，不新增输入参数、输出字段或业务入口，不以修改协议来保留当前成功行为。

## 2. 允许文件与基线

允许修改：

- `scripts/build_demo_human_gate_decision.py`，起点 `1355dce0b22a90dbe1d1d08bb05c49a6d5e76c2c6b21d15a8ae6b512463d6a68`。
- `tests/test_build_demo_human_gate_decision.py`，起点 `f7a6c8c8a073a891c2505c69a09409e2e1f5739eebc1156d34d2ee55ac67b02b`。
- `docs/HUMAN_GATE_DECISION_GUIDE.md`，起点 `5a753b15c0ca378cb07b4e2fb7e782fed7b2944dc7f2cad599c8bd5f6ce50caa`，仅同步实际校验/证据能力与说明，非必改。

仅新增 `docs/EXEC_REPORT_021_R1.md` 和全新 `data/human_gate_decision_tests/task021r1_<唯一名>/`（含必要过程容器、局部/完整入口结果）。旧TASK-021回执、原/过程证据、评审脚本与输入全部冻结，不运行或覆盖旧容器中的脚本。

保护基线：`data/reviews/task021_gpt_20261013_195927/source_hashes_after.json`，身份/项数/verdict见同目录`review_result.json`（NOT_ACCEPTED）。清单自身与该result按两个确切路径单列，不豁免reviews整个目录。不得拿原TASK-020基线代替本次基线。

正式契约 `174a021b…40ad`、协议 `68c931b3…3e76`、案例 `bd1fc37d…d2a6`、D1/D2/D3、宿主/控制器/全部上游和历史产物冻结。不新增依赖或Git，不建batches/SQLite/审阅包/批准文件。

## 3. B1定点实现

### 3.1 当前Gate2前序完整record

补齐全部record字段与嵌套对象的封闭schema/严格类型/常量/格式/语义校验，不能只校验顶层17键或取选定字段相等。至少覆盖：

- decision_source常量；event/batch/reason/时间/身份声明字符串；合法决定时间；actor完整键/actor_id/declaration_note。
- binding完整键、request_id、materials_fingerprint的fullmatch、非空升序唯一materials_files及每项relative/字节SHA/严格非负byte_size。
- contract_binding完整键、版本/SHA、contract_effective严格true；run_binding及每层封闭键/严格类型/哈希，含已有六字段与三组独立运行预期比较。
- quality_summary完整键/合法状态/严格派生计数语义、execution_allowed严格false、boundaries六键严格false。
- Gate1记录的prior_gate1为null；record其余常量、未知键与缺键均按协议拒绝。

保持前序内部验证在第11步相应子序；未知/缺失字段给完整路径。直接复算record SHA只是完整性的一项，不能替代schema和合法来源/契约声明校验。不从reason内容或ID前缀猜身份/授权。

### 3.2 已提供历史的合法性

已提供的每个wrapper必须符合版本/完整指纹/完整record约定；不可让invalid-wrapper、not-a-sha、只有少数键的record或SYSTEM来源进入成功结果。历史完整性仍仅是调用方声明范围，不新增全局历史发现或磁盘读取。

保持第4步历史名单/基本形状与第11步当前前序内部核验的分工；**不能把当前前序内部常量/质量/运行语义提前到第4步，掩盖11b/11f/11g的目标定位**。其他历史在第12步被用于事件/既有批准语义判定之前，应完成其完整record与wrapper合法性/指纹核验；当前前序本身按第11步完整验证。可以复用私有校验辅助，但不要把“当前前序必须Gate1/APPROVE/同批次/同运行”套到全部历史记录上：一般历史允许合法HOLD/REJECT、其他批次或Gate2记录，不要求其运行绑定等于当前批次；它们仍须自身协议合法。保持合法历史的重复规则。

不新增prior_materials参数、不从record中的摘要反推原始材料真实性、不新增跨全局祖先图算法；本卡核验现有字段所能表达的schema、语义与记录摘要。

## 4. B2最终证据收尾

1. 在**真实公开核心函数入口**观察实际调用数，包含前序准备/正常/拒绝/确定性/无别名/注入/守卫；测试外层Registry计数与真实入口观察分列并核对，不用自增封装次数冒充实际次数。守卫中的观察只写内存，解除后登记那次完整返回/异常，不补调核心。
2. 权威call_registry与API记录按调用ID双向审核，重复/缺失/多余/观察次数不符进入正式failures。隔离副本只删除权威registry的一条调用，真实audit必须失败；原件仍通过。可保留现有文件台账隔离，但不能用它替代调用登记隔离。
3. 全部成功/Blocked/Error/意外记录保存完整输入、完整返回或真实traceback及cause/context链；调用前/后保留同一真实引用的指纹证据。计数来自现场，未执行项写null/not_executed，真实API计数与测试运行器标签不混淆。
4. checks/failures/counts/summary等最终载荷稳定后再登记最终长度/字节SHA并读回审核。不要先建ledger、再追加checks、仍保留旧SHA/validated零值。可用小型明确的finalize，但不引入通用I/O框架。
5. 台账/summary/保护元数据分层说明：台账不内嵌自身SHA，不制造自指；后置保护脚本/结果按确切路径有限登记。最终审核必须包含最终summary与checks，并把实际missing/unregistered/changed等纳入正式failures。审核完成后不得再次改载荷而不刷新/复核对应条目。

## 5. 最小实际验收

先定点小样，修正后再在一个新容器运行一次完整本卡纯核心入口。不给局部失败附带全树扫描，不重跑业务/历史入口。

- 两项正常控制BASE1/BASE2完整返回正确，原record1独立规范比对仍相等，C-116正常。
- 至少复现评审12个反例：11个前序字段单点变化及1个坏历史wrapper/部分record。每例独立对象；先重算record摘要、同步提交wrapper/独立前序预期/历史，再调用公开核心，必须Blocked且指出对应字段，不以摘要不一致/缺历史提前拒绝冒充目标校验，输入不变。
- 补充代表性未知/缺失嵌套键、hash尾LF/CRLF/空格、大写/截断、bool冒充、前序不合法日期/身份、材料files格式/顺序、契约effective类型等；使新加schema覆盖全层，不只拦评审给的12个值。新增用例按维度分组即可，避免机械笛卡尔膨胀。
- 历史正向控制包括合法HOLD/REJECT及其他批次记录；历史Gate2合法记录不得一律当成Gate1前序拒绝。历史错wrapper版本/格式正确但摘要不符/不完整record应分别拒绝；当前前序11b/11f/11g定位仍保持。
- 连带确认原117设计案例的实际调用映射、质量矩阵、时间/ID保真、无别名、纯内存守卫、内部Error cause链。原C-112—C-115/R3正确派生构造仍在11f拒绝，不能被新历史校验提前遮蔽；无需运行旧文档自检。
- 最终证据audit真实执行：入口观察=登记覆盖，权威调用登记↔API记录双向一致；最终文件SHA实读一致；两种隔离自测区分作用，删一条调用登记必失败；missing/unregistered/changed等为真实审核结果并进入failures。

只修改授权文件；候选核心仍无CLI/持久化/恢复/放行/网络，输出固定false不变。测试自身可用--only定点模式，但定点与完整入口都必须明确执行了哪些审核，不填未执行的默认零。

## 6. 回执、保护与停止点

核心/测试/指南/回执定稿、定点与完整入口真实通过后，执行一次全树保护扫描，对本次新基线changed仅允许上述本轮实际修改文件、missing/读取错误/范围外新增0。之后只有限登记本轮最终产物/回执身份；不要在扫描后继续改核心/测试/指南或重复全树扫描。

新回执列B1/B2逐项关闭证据、实际调用与作用域、完整入口命令/退出码/检查数、核心/测试/指南写后SHA、最终证据审核与保护基线/结果、过程失败与未执行声明。自身最终SHA只在交接消息给出，不写回自身；不回写旧回执/证据。

完成本卡后停止本轮实施交GPT验收。通过后才制定P2；不接宿主/控制器，不生成真实Gate/初判/0009，不开放AI或终判。人类业务决定与契约生效确认不重开，不以本卡内存结果放行任何批次。
