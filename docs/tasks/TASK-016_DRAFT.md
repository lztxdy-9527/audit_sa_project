# TASK-016：开发态独立初判记录纯核心

日期：2026-10-13。供人类转交 DeepSeek。GPT 负责架构与验收；DeepSeek 负责本卡实现、有限测试和如实交付；真实 Gate 批准、真实人类初判及终判仍由主理人作出。

## 1. 目的与停止点

TASK-015 已将冻结事实底稿核心接入宿主，验收范围到开发态0007。下一环节是“人类独立初判保存 → AI对照建议”，先建立一个可单独验收的**模拟初判记录校验与事实绑定核心**，随后另卡接入宿主持久化。

本卡只处理调用方明确提供的模拟初判文本，不推导、生成或预填判断，不读取聊天倾向，不计算候选等级、重要性或审计结论。允许“暂不能判断，需要补充证据”，必须有调用方提供的非空原因。无命中也不能自动填“无问题”。

**本卡不保存真实人类判断，不把内存校验称为已保存，不解锁AI。** 宿主、控制器、0001—0007及现有CLI全部冻结；不增加0008、不建正式契约/真实Gate，不接LLM、网络、UI、ERP。开发模拟身份不等于人类认证，不代表主理人已经作出初判。

## 2. 允许新增的文件

只新增以下四个文件：

- `scripts/build_demo_initial_judgment.py`
- `tests/test_build_demo_initial_judgment.py`
- `docs/INITIAL_JUDGMENT_GUIDE.md`
- `docs/EXEC_REPORT_016.md`

只新增本轮唯一证据容器 `data/initial_judgment_tests/task016_<唯一>/`。可保留过程容器，禁止覆盖、清理历史；不新建 batches、SQLite 或宿主测试链。

所有既有文件冻结，包括本任务卡、规格/契约草案、全部上游实现/SQL、既有测试、指南、回执、评审和数据现场。宿主冻结哈希：

`67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a`。

TASK-015最终宿主测试冻结哈希：

`90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e`。

保护基线为 `data/reviews/task015_r2_gpt_20261013_011825/source_hashes_after.json`，实际项数与哈希登记在同目录 `review_result.json`。本卡只新增，故相对该基线应 **changed=[]、missing=[]、读取错误0**。一次当前扫描即可；不安装依赖、不初始化Git、不改变目录结构或迁移旧凭证。

## 3. 固定纯API

仅提供一个业务入口：

`build_initial_judgment_record(batch_id, fact_packet, submission, *, expected_packet_sha256) -> {record, record_sha256}`

标准库、纯内存、确定性；不读取/写入文件、数据库或Excel，不导入/调用上游、控制器、宿主、测试、答案册、LLM、网络、子进程；不自动生成事件ID、身份、时间或判断。导入模块也不得触发这些操作。内部小型校验/helper可按需编写，不造通用协议框架。

不得修改任何入参或共享其可变对象；返回值后续被调用方修改也不能影响原输入。相同输入返回规范JSON等值且指纹相同。规范JSON统一为UTF-8、ensure_ascii=False、sort_keys=True、separators=(',',':')、allow_nan=False；指纹为该字节串SHA-256。record不内嵌自身指纹。

定义 `InitialJudgmentBlocked`（输入/协议/绑定不符，指出字段与原因）和 `InitialJudgmentError`（意外内部错误，保留cause链）；不能把异常包装成成功记录。无CLI、退出码或文件保存接口。

## 4. 事实包与批次绑定

batch_id为调用方提供的非空字符串，保留原值，不转数字、不自动strip后存储。expected_packet_sha256为64位小写十六进制字符串；必须与**本次fact_packet对象**的规范指纹一致。

事实包最少核验本核心实际消费的字段：

- dict、可按约定规范JSON编码；`packet_version=TASK-008-fact-packet-1.1`、`batch_status=DEV_FACT_PACKET_READY`、`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed`严格false。
- entity为现行主体/期间/截至日/币种：澄明商贸有限公司，2026-09-01—2026-09-30，截至2026-09-30；币种按冻结packet实际字段`人民币（CNY）`核验，不把展示字符串误当新版协议。
- bindings中的workbook_sha256、normalized_payload_sha256、screening_report_sha256、crosscheck_report_sha256为合法指纹。
- findings为list；各finding_id非空字符串且唯一，rule_id属于R01—R04。仅为引用及记录范围核验，不重新计算金额或复制冻结事实核心的全部校验逻辑。

事实包不含可独立认证的batch_id。本API的batch_id是调用方绑定声明，须与submission.batch_id相等；记录同时绑定完整packet指纹、四项来源指纹、entity和finding_id序列。不能声称纯核心实读了0007、数据库、packet文件字节或验证了身份。文件/凭证恢复、身份来源、旧事件去重及独占保存由后续宿主卡承担。

仅改packet中一个事实字段、仍传旧expected指纹时必须拒绝；submission传其他batch_id或其他packet指纹也必须拒绝。调用方同时重新声明所有指纹不是本纯内核能够阻止的同权限篡改，不宣称防伪。

## 5. 模拟提交协议

submission为dict。必填且仅允许以下必填键及两个可选键；未知键拒绝，不静默忽略ai_suggestion、final_judgment等越界字段。

必填键：

- `submission_version=TASK-016-initial-judgment-submission-1.0`
- `event_id`：调用方明确给出的非空字符串；本核心不生成、不作跨调用持久去重。
- `batch_id`、`fact_packet_sha256`：分别严格等于本次API批次及已验证规范指纹。
- `scope=BATCH_FACT_PACKET`：本卡采用整份事实包的初判记录，不强制每条线索作确定结论。
- `actor_kind=SIMULATED_HUMAN`、`actor_id`为非空字符串、`simulation=SIMULATED_TEST_ONLY`。
- `occurred_at`：调用方给出的含时区ISO8601日期时间；不读取系统时钟、不补造时间、不把字符串当身份凭证。
- `assessment`和`reason`：调用方给出的非空字符串；仅检查类型及去空白后非空，原文含空格、换行、ID、中文等按原字符串完整保留。不能自动补“通过”、确定结论或取证建议。

可选键：

- `needed_evidence`：调用方提供的非空字符串列表，可为空；不自动添加条目。
- `finding_notes`：列表，每项只含`finding_id`和非空`note`；ID必须存在于当前packet且不重复。允许只写部分线索备注或空列表；不把未写备注解释成已判断。

两个可选键省略时存为对应空列表并在指南说明规范化方式；其他文字不改写。拒绝bool冒充字符串/ID、空白assessment/reason、无时区/无效时间、重复/未知finding_id和真实HUMAN/AI身份混入。本卡只支持显式模拟身份；不得把测试记录标成主理人的真实判断。说明中不声称能够从文本识别人是否独立思考、是否用了AI。

测试中的assessment/reason必须醒目标注模拟测试用途，不能提供生产默认判断或让实现根据事实自动选文本。原始数据或文字中的指令只按字符串保存，不解释或执行。

## 6. 返回记录

外层严格为`record`与`record_sha256`。record包含：

- `record_version=TASK-016-initial-judgment-record-1.0`、`batch_status=DEV_INITIAL_JUDGMENT_VALIDATED`、`mode=DEVELOPMENT_TEST_ONLY`。
- `contract_status=DRAFT_NOT_IN_FORCE`、`next_step_allowed=false`、`ai_suggestion_allowed=false`。
- `gate1_approval=null`、`gate2_approval=null`、`human_initial_judgment=null`、`ai_suggestion=null`、`final_judgment=null`。
- `source`：batch_id、fact_packet_sha256、packet_version、entity深拷贝、四项来源指纹、finding_ids（packet原序）。字段名和嵌套在指南固定，不增加文件已验证/数据库已实读之类声明。
- `simulated_initial_judgment`：已核验submission的深拷贝及上述两个可选字段的确定性规范化，不改变assessment/reason原文。
- `boundaries`：固定说明开发模拟、内存校验尚未持久化、身份未认证、人类判断先于AI、真实判断与批准由人类作出；只写边界，不生成具体业务意见。

返回状态只叫VALIDATED，不能叫SAVED、HUMAN_APPROVED或AI_READY。它也不改变事实包中“尚未保存人类判断”的冻结banner。

## 7. 有界测试与证据

入口 `tests/test_build_demo_initial_judgment.py --out-dir <全新证据容器>`。先做一个正常和一个必要绑定反例小样，局部错误定点修正；最终一次全新容器运行以下有限检查，不重复建宿主链：

1. 正常模拟提交及“暂不能判断”对照：真实调用新API，准确绑定packet/批次，原文保留，完整返回与规范指纹读回相等，输入前后同引用指纹不变；调用前观察，不能用两个调用后值冒充前后。
2. MAIN12条、C06b1条和C03零条的已保存事实包均可接收批次初判，finding_ids与来源绑定准确；零条不自动产生“无问题”。只读下列已存在packet，不调用上游、不读取答案册、不把旧容器当作当前宿主恢复成功。
3. 绑定反例：错误批次、错误提交指纹、旧expected指纹下packet事实字节对应对象变化，均准确Blocked，无成功记录。
4. 协议反例：空/空白assessment或reason、未知字段、越界身份/模拟标记、无时区时间、重复/未知备注ID、非法packet状态或严格布尔字段；可按维度分组，不做无穷组合或全面上游回归。
5. 确定性与无别名：重复调用输出一致；修改返回记录不改变输入；可选键省略与显式空列表按约定等值；保留前导零ID及文字中的类指令字符串，核心不执行它们。
6. 纯内存及停止点：加载测试输入后，用计数抛错守卫限制文件/网络/子进程入口，仅在新API调用期间启用；命中0且仍成功。record固定null/false边界，无文件/时间/随机身份生成；导入静态依赖只为标准库。
7. 真实证据和保护：每次新API直接调用均登记完整返回或异常/原因链、预期结果；逐项实读文件引用存在性及哈希、双向核对记录；记录missing/unregistered已执行结果并进入正式failures。一次正确基线保护比较changed=[]/missing=[]，现有宿主/测试/核心冻结哈希及三份输入文件哈希一致。全部必要检查结束后才保存最终checks/summary并决定退出码，不把早期快照当最终检查清单。

本卡不强制复用TASK-015的大型宿主测试、receiver/checker计数或隔离框架；仅登记本卡实际API、证据文件与保护结果，未执行的动作不填假0。若为新证据helper加隔离自测，只改一个审核副本条件，不同时删除多处来掩盖观察缺口。

三份只读packet来源及文件字节SHA-256：

- C06b：`data/batches/task015r2_run_03/r1_normal_control/workflow/fact_packet/fact_packet.json` = `8cecbf3b9b5c463476b1dcf712065b60c2d75d5d9948c3a3f9ac141516e98755`。
- MAIN：`data/batches/task015_run_06/main_01/workflow/fact_packet/fact_packet.json` = `711fe8d71035d7beaa4bc1972a0ea90a21c5c3932703e6850c765a149448b926`。
- C03：`data/batches/task015_run_06/g2_c03/workflow/fact_packet/fact_packet.json` = `9644a10a656580aebf9d42f4716d7aee7634f65ca3af10e9259534453f2f4426`。

测试从实读对象计算规范指纹，文件字节指纹与对象规范指纹分列，不能互换。负向探针只改内存深拷贝，不回写三份输入。

## 8. 交付与验收纪律

指南记录API、完整字段、模拟身份、指纹口径、有效暂不能判断、纯内核不保存/不认证/不解锁AI、后续宿主责任。新回执给最终完整源文件哈希、真实命令/退出、各组证据、API实际次数及来源、最终checks/failures、保护比较、过程失败和未解决项。自身哈希只在交接消息给出，不追求自指。

业务/来源绑定错误、生成或预填判断、伪身份/伪批准、失败误报成功、改冻结文件、影响结论的证据错误阻断；不影响结论的辅助旧记录问题登记，不反复重跑历史流程。遇业务口径问题交GPT/人类，不自行改规格。

完成后执行端停止本卡实施，交GPT验收，不自行做宿主接入或AI。GPT验收通过后按主理人持续授权制定下一卡，预计将本纯核心接入开发态宿主并保存模拟初判；是否正式建立契约、开放真实Gate或形成真实审计判断仍须主理人明确决定。DSH卡片由人类操作。
