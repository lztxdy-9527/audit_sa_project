# TASK-015：将冻结事实底稿核心接入开发态宿主

日期：2026-10-12。当前实施任务卡，供人类转交 DeepSeek。GPT 负责 Architect / Reviewer；DeepSeek 负责本卡实施、测试、调试和如实交付；人类负责业务判断、真实 Gate 批准及 DSH 看板操作。

## 1. 起点、目标与停止边界

TASK-014 及 R1/R2 已由 GPT 验收、人类关闭。以实际文件及 `docs/reviews/REVIEW_TASK_014_R2.md` 为准：已验收宿主链止于 0006，`phase=DEV_GATE2_APPROVED`、`screening_status=RULE_SCREEN_RECORDED`、`crosscheck_status=RULE_CROSSCHECK_RECORDED`；真实两处批准为 null，`next_step_allowed=false`。

本卡只接入 TASK-008-R1 已验收的确定性事实底稿核心：在**同版本新批次的合法 0006** 上显式调用一次，保存完整 JSON 事实包和对应 Markdown，成功后追加 0007，并支持新进程只读恢复。不得重写规则、复算或展示业务逻辑。

这仍是合成数据的开发态演示，不建立正式契约或真实 Gate，不保存/预填人类初判、终判，不生成 AI 建议，不增加判断表、LLM、网络、UI、ERP 接入或性能任务。0007 只表示事实底稿已持久化，不能叫“审计完成”“审计通过”或“已批准底稿”；不新增 0008。

**执行端完成本卡后停止实施并交 GPT 验收。** 这只限制执行端本轮实施；GPT 按主理人的持续授权，在每卡验收通过后继续制定下一张明确范围与验收标准的任务卡，不需要人类重复提出。制定下一卡不等于执行下一卡，也不代替人类业务决定或真实批准。

先读：本卡、`docs/reviews/REVIEW_TASK_014_R2.md`、`docs/reviews/REVIEW_TASK_008_R1.md`、`docs/FACT_PACKET_GUIDE.md`、宿主指南及实际宿主/事实底稿接口；业务争议再定位 `docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md`。不靠历史聊天替代实际文件。

## 2. 允许路径与冻结基线

只允许修改两个既有文件：

- `scripts/run_demo_workflow.py`，起点 SHA-256 `8cf41ca8da12c77f5fc2a9827c936971aeeafd93a963746cc778a9c1d72031f7`。
- `docs/WORKFLOW_HOST_GUIDE.md`，起点 SHA-256 `5ce64aee26986a1ace88ac5ef64a016799077ff10ac0d1d933c87fc455bdbb68`。

只新增 `tests/test_fact_packet_demo_workflow.py`、`docs/EXEC_REPORT_015.md`，以及本轮唯一名称的全新目录：

- `data/workflow_host_tests/task015_<唯一名称>/`：测试记录、故障探针、保护比较。
- `data/batches/task015_<唯一名称>/`：本轮新批次及明确登记的探针副本。
- `data/sqlite_tests/workflow_gate2/task015_<唯一名称>/`：本轮外置 SQLite。

不得修改本卡、既有评审/回执、纯核心、其他旧测试/指南、控制器、接收器、标准化/装载/筛查/复算模块、SQL/schema、规格、契约草案、生成器/答案册、原始工作簿或历史容器。不得初始化 Git、安装依赖、清理历史目录或回写旧凭证。新宿主与旧宿主代码绑定不兼容时如实拒绝；新测试从现有冻结工作簿创建新批次，不迁移旧批准或旧链。

本卡保护基线固定为：

`data/reviews/task014_r2_gpt_20261012_225658/source_hashes_after.json`

共 **118788 项**；基线文件 SHA-256 `19639176acb6dae72cdd0c2ede0df86c4f917d05971cba9da45da99080505e1b`。不得再误用 116059/117422 项读数充当本卡基线。对基线既有文件仅允许宿主/宿主指南两项变化，missing 必须为 0；本卡等基线后新增的管理文档在实施开始时另记选定哈希并冻结。一次当前扫描即可复用比较，不重复扫描所有历史嵌套基线。哈希读数不等于 Git 恢复点。

关键冻结件如下，实施前与交付后均核对完整哈希：

- `scripts/build_demo_fact_packet.py`：`f4998d922eb8054dde9a8263a42aff171fdd499dfe43e114befaa38a74978b62`。
- `tests/test_build_demo_fact_packet.py`：`46d426e7c262f3b5c773ba6717e5b3e002c34783d11d24a5bd3c43b80effeb36`。
- `docs/FACT_PACKET_GUIDE.md`：`48c051be9bfca3659560c73e4693892ecd1a72629fba7401698eb87f8657ff9d`。
- `scripts/crosscheck_demo_rules.py`：`8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`。
- `tests/test_crosscheck_demo_workflow.py`：`f34533833d0fa0ac41274f1c847f933ecaf8110de65e35acc43c8bf12393cf43`。
- `tests/test_screen_demo_workflow.py`：`27c432db5f1d52ec84220e5ffc07d0f13613fd8b438b7c84bdc260beb6858eca`。

## 3. 冻结核心与新增接口

必须真实调用既有 `build_fact_packet(normalized, screening_report, crosscheck_report) -> dict`。仅传三个内存对象，不传数据库/文件路径、答案册、SQL 或生成器。事实底稿核心只消费这三个对象；数据库实读和文件核验由宿主负责。

实际冻结协议为：

- `PACKET_VERSION=TASK-008-fact-packet-1.1`。
- 返回对象恰为 `{packet, packet_sha256, markdown}`；packet 为对象，packet_sha256 为 packet 的规范 JSON SHA-256，markdown 为字符串。
- packet 内 `batch_status=DEV_FACT_PACKET_READY`、`mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed is False`。
- `FactPacketBlocked` 映射为 `WorkflowHostBlocked` / 退出 1；`FactPacketError` 映射为 `WorkflowHostError` / 退出 2，保留原始异常、cause/context、完整原因链及本层阶段 `fact_packet`。意外运行/I/O 错误仍为退出 2，协议/前提错误为退出 1。

冻结事实底稿指南第 3 节仍写 packet 1.0，是 TASK-008-R1 已登记的非阻断旧标注；本卡以实际核心和其验收确认的 **1.1** 为准，不修改冻结指南，不为该旧文案另开修订。

新增公开 API：`build_dev_fact_packet(batch_dir) -> dict`。

新增 CLI：`build-fact-packet --batch-dir <existing-new-batch>`。现有七个子命令保留，共八个；stdout 结构化 JSON，stderr 诊断，退出码沿用 0/1/2。该命令显式触发；screen/crosscheck/status 不自动接着生成底稿。

宿主实现版本升为 `TASK-015-workflow-host-1.0`。既有 TASK-012 checkpoint/manifest/Gate2 协议、TASK-013 screening 协议、TASK-014 crosscheck 协议保留，不随实现版本盲目改名。只新增：

- `TASK-015-fact-packet-start-1.0`。
- `TASK-015-fact-packet-artifacts-1.0`。
- `TASK-015-fact-packet-failure-1.0`。

更新宿主页首、CLI 帮助及宿主指南，统一说明当前实际职责、八命令、0007 恢复和开发态边界。特别纠正指南中“本版本不运行筛查/复核/事实底稿”、旧宿主版本和 0006 后控制器允许值的过时描述，不回写历史验收记录。

## 4. 固定执行顺序与输入保护

1. 共用恢复核验，要求当前**恰为合法 0006**。验证连续 0001—0006、真实来源/代码/SQL/配置/契约草案绑定、宿主清单、Gate2 材料与数据库、筛查与复算报告/引用、完整 MATCHED 十维度，以及各层失败/未完成状态。仅有 phase、matched 标志或一份底稿文件不能视为前提满足。已有 fact_packet 目录必须在本次写入前拒绝。
2. 使用操作开始时重新实测的绑定调用冻结控制器 `check_dev_action(..., SCREEN_AND_BUILD_FACTS, current_bindings=...)`，`simulation_allowed` 必须严格为 true。这仍是开发态模拟允许；不能为了本卡改控制器状态机或自造批准。
3. 从固定文件 `workflow/gate2/normalized.json`、`workflow/screening/screening_report.json`、`workflow/crosscheck/crosscheck_report.json` 读取三个对象；各对象解析与对应文件字节哈希来自**同一次读取缓冲**。与已核验的各自前序凭证比较，不用后来读到的不同版本替换初始预期。构建前实读固定推导数据库路径，其字节哈希须与前序材料一致。
4. 独占创建 `workflow/fact_packet/`，独占保存并读回 `started.json`，记录批次、宿主/核心版本与哈希、运行绑定、初始 manifest/0006 文件字节哈希、三个输入固定相对路径/文件哈希/规范对象指纹、数据库绑定。只有本次真正创建现场后才可保存本次失败诊断。
5. **真实调用一次**冻结 `build_fact_packet`，不再调用筛查或复算核心，不读取答案册。调用前留三个对象的规范指纹，核心返回后及公开操作返回前按保留的同一对象引用核对未变。宿主不向输入添字段、不对返回 packet/markdown 二次加工；发现输入被改动须拒绝成功。
6. 校验本次返回的必需键和严格类型、packet 版本/开发态/期间/主体/币种、三对象及工作簿绑定、规范 packet 指纹。summary/findings 的接口形状与数量须符合已核验报告，不能只看 READY 字符串。业务公式、来源上下文和正文渲染继续由冻结核心负责，不在宿主复制另一套底稿构建器。
7. 独占保存完整 `fact_packet.json` 和 `fact_packet.md`，关闭后实读验证：JSON 与该次真实返回的 packet 严格规范 JSON 相等，规范指纹等于返回的 packet_sha256；Markdown 磁盘字节**精确等于**返回 markdown 的 UTF-8 字节。UTF-8 无 BOM，明确 LF 写入策略，不用平台默认换行、不额外插删结尾换行、不 strip、不重写文案。再保存/读回 artifacts，最后保存/读回 0007；任何收尾失败不得报成功。
8. 在**最后一次必需控制器调用和最后一次用于返回摘要的数据消费之后、返回成功之前**复测本次消费的材料：三个输入及上游相关产物、数据库、manifest、静态绑定、0001—0007、started/packet/Markdown/artifacts、失败及未知项状态。预期只来自初始同缓冲读取或本次真实 writer 结果。旧 0001—0006 与已有输入前后字节不变。收尾只核验既有预期，不再消费新版本生成摘要；不要求无限循环读取，不另造通用 I/O 框架。

复用已有小型核验与故障诊断模式；本卡授权必要的 0007 分支/本层 helper 和独占 Markdown 写入，不授权全面重构宿主、事件框架或跨任务测试框架。

## 5. 固定落盘与成功凭证

本层固定目录 `workflow/fact_packet/`：

- `started.json`：本次开始凭据。
- `fact_packet.json`：完整 packet，保留原整数分、ID、来源 entities/cells、退款事实及逐笔上下文。
- `fact_packet.md`：同次返回的完整确定性中文正文，与 JSON 同目录。
- `artifacts.json`：完整绑定摘要。
- `failure.json`：仅本次已开始后失败时出现，成功现场不得有该文件。

无需新增含重复大对象的宿主 build_result.json；完整核心返回在测试证据中单份保存即可。JSON 文件字节 SHA-256、packet 规范对象 SHA-256、Markdown 文件字节 SHA-256 分开命名和核验，不能混用。规范 JSON 沿用 `ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False`，再 UTF-8 SHA-256。

started 与 artifacts 的三个输入指纹字段分别明确为：`normalized_file_sha256` / `normalized_payload_sha256`，`screening_report_file_sha256` / `screening_report_canonical_sha256`，`crosscheck_report_file_sha256` / `crosscheck_report_canonical_sha256`。核心 packet.bindings 内现有 `screening_report_sha256` / `crosscheck_report_sha256` 是**对象规范指纹**，不能当作文件哈希。

artifacts 至少绑定：固定协议版本、batch_id、host_version、事实底稿核心版本/实测源码哈希、运行绑定指纹、初始 host_manifest 与 0006 文件字节哈希、上述三个固定输入引用和两类指纹、各层本次已消费的上游产物文件哈希、数据库固定推导路径/实测字节哈希、Gate2 模拟决定正文指纹、期间/截至日、started 文件哈希、固定 packet/Markdown 相对路径、`packet_file_sha256`、`packet_sha256`、`markdown_file_sha256`、fact_packet_status。不能将待写 artifacts 自身哈希写入自身。

成功后才追加 `workflow/checkpoints/0007.json`：

- revision 为严格整数 7（排除 bool/float），`operation.kind=BUILD_FACT_PACKET`。
- previous_file_sha256 为操作开始时实读 0006 的字节哈希；manifest 引用仍为文件字节哈希。
- workflow 与 0006.workflow **完整严格相等**，不增减 history、请求、模拟决定或真实批准。
- operation 绑定 started/packet/Markdown/artifacts 的固定相对路径、对应实际文件字节哈希、packet 规范指纹、核心/宿主身份、绑定与 `fact_packet_status=FACT_PACKET_RECORDED`，保留 artifacts 的完整内嵌副本。恢复时先验必需键/类型，再核对固定路径、绑定、磁盘值及内嵌副本，不能只验哈希长度或信任内嵌摘要。

链只扩展为连续 0001—0007；拒绝未知 checkpoint/缺号/半文件/目录。0005、0006 各自核验自身操作与各自初始前序哈希，不能因为链尾变 0007，就把 else 分支全部当作复算，或用链尾 operation/hash 提取筛查/复算摘要。

成功 API/status 保留筛查与复算摘要，新增 `fact_packet_status=FACT_PACKET_RECORDED`、`fact_packet` 摘要和 completed_actions 项 `FACT_PACKET`；给出固定文件引用、三种结果指纹、packet_version、条数/规则分布等已核验摘要。phase 仍为 DEV_GATE2_APPROVED，真实批准仍 null、next_step_allowed=false。可以说明筛查→复算→事实展示这一确定性子流程已记录完成，不宣称后续人类判断或 AI 已完成。

`actions_simulated_allowed` / `simulated_action_allowed` 保持**冻结控制器的真实返回**。控制器在 DEV_GATE2_APPROVED 仍允许 SCREEN_AND_BUILD_FACTS；宿主通过 revision/已有现场禁止重复，不把历史完成项伪写成控制器拒绝或真实放行。0007 也不开放任何 AI/人类判断入口。

## 6. 失败、重启与只读恢复

本层 failure.json 延续已验收失败协议：版本/批次/宿主身份、严格整数退出码、错误类别、准确 fact_packet 阶段、完整原因与 exception_chain（含 cause/context），实际已写文件/报告位置。保存后读回核验；诊断保存也失败时如实报运行失败，不假称已持久化。

共用恢复入口在**解析 checkpoint 链之前**核验本层有效失败诊断，防止半写 0007 把真实运行失败 2 遮成任意 JSON 错误 1。完整 0007 写完后抛错而保存了有效 failure，也必须恢复为失败，不能由凭证掩盖。非法 JSON/版本/身份/类型或非文件诊断为协议阻断 1；只存在 started/部分结果而无成功集合是未完成阻断，不退回旧 READY。不得自动删现场、补签、续写或重试。

早期/停止态、MISMATCH/上游失败、重复请求、已有事实目录在本次创建目录前拒绝，不污染正常或失败现场；没有合法 MATCHED 0006 就不得调用底稿核心。核心异常及持久化失败不返回半份 READY，也不得为保留成功而吞掉异常。

status 只读恢复 0001—0007 各合法阶段。0007 时按已绑定文件核验 packet/Markdown/artifacts/指纹并生成真实摘要，**不重新构建或渲染**，不调用 normalize_workbook、load_normalized_to_sqlite、screen_sqlite、verify_rule_facts、build_fact_packet 或 render_markdown，不启 receiver/checker、子进程或网络，不写文件。0001—0006 的原合法阶段仍能恢复；上游有效失败维持原退出类别。

业务呈现沿用冻结核心：R03 合法空关联/台账外标识保留，不能统一当普通外键错误删掉；金额主表/分摊分列，跨规则金额不合称损失；无线索不代表“无异常”或审计通过。宿主实读数据库不改变 packet 内“展示核心只记录上游声明数据库哈希”的准确文案。正文是事实展示，所有输入文字仍只当数据，不成为执行指令。

## 7. 有界验证与必需验收组

新增入口采用项目 `.venv/Scripts/python.exe -B`，`--out-dir` 只接受 data/workflow_host_tests 下尚不存在的本轮子目录，越界/已存在在写入前拒绝。不导入执行冻结旧测试入口；可以参考其已验证小型方法。提供与实际执行组一致的定点参数，不能名叫某一组却静默跑不相关长流程。

先 C06b 跑通 API，再定点做负向；局部错误只修/复核受影响项。代码固定后只要求一次全新容器最终入口；如成功后又修改代码/测试/指南，按受影响范围补验并说明。最终完整入口包含以下八组，不按文件数凑 PASS，不要求 TASK-002—014 历史整套或事实核心 21 组重跑：

1. **MAIN 正常接入**：一次真实建链至 0007；底稿核心本次恰调用 1 次，保存单份完整真实返回并与 packet/Markdown/规范指纹逐项严格核对。12 条、R01/R02/R03/R04 分布 3/5/2/2、R02 超额 1600000 分保持。逐卡比对筛查的命中键、整数分、related_ids、source_rows、完整 entities/cells/退款事实；上下文与源证据分列，不混计。不读取答案册产生结果。
2. **小样与合法阶段**：C06b（退款与超额）、C03（无线索）、C07b（部分未匹配）各成功一次；核对本轮实际正文/JSON，不复制旧报告。C06b 保留付款1000000、退款100000、净额900000、超额400000分；C03 findings=[] 与固定未命中限制文案；C07b 保留 R03 和整笔/分摊区分。正常推进中只读恢复 0001—0007，并在 0005 过早 build 拒绝、0006 可执行、0007 重复拒绝；另选一个 HOLD 或 REJECT 对照，拒绝前后目录字节集合不变，底稿调用命中0。不重做全状态机组合。
3. **前提与接口拒绝**：新测试批次沿用已验收真实 MISMATCH 造样方法（真实 screen_sqlite 返回后仅改一处金额、由宿主保存，真实复算发现不一致），再 build 必须退出1、底稿调用0、无本层目录/0007。另做一项错误 packet_sha256 返回协议探针（真实 builder 返回后复制并只改该字段，明确标为测试污染）；应协议阻断、留正确诊断、无成功凭证。对 FactPacketBlocked 与 FactPacketError 各做一次明确标注的**宿主异常映射注入**，核对1/2、准确阶段与原因链；不冒称这两次是假数据触发的真实核心业务失败。
4. **有限持久化故障**：只要求目标 0007 的两场景——进入真实 JSON writer，在真实独占写句柄上写前半缓冲再抛 OSError；完整真实 writer 保存后再抛 sentinel。复用 TASK-014-R2 已验证方法，不替换 writer 重造实现。记录实际 writer进入/句柄写命中、模式/换行、待写完整UTF-8缓冲单份文件及读回哈希、现场前缀/完整字节、异常链。当前与新进程 status 均退出2、旧0001—0006和输入不变，完整凭证也不能遮失败。半写文件数与可解析/经恢复确认成功的凭证数分列。不要求增加更多 I/O 故障矩阵。
5. **晚变更与固定引用**：先无注入记录真实摘要读取位置；在 status 最后一次用于底稿摘要的真实读取返回原对象之后，直接 wrapper 单次修改 fact_packet.md 字节，原样返回原对象。本次 API 即拒绝；撤销wrapper后新进程CLI仍拒绝；恢复原件后CLI成功。不得以更早读取、猜序号或下一次才拒绝证明本次检测。另只改0007.operation的固定Markdown路径，必须指出该字段阻断；再改started中的一个输入规范指纹，指向字段拒绝。只在本轮新探针现场改动，留恢复记录，不改历史交付。
6. **只读/隔离与输入不变**：同进程把五个真实下游函数替换为计数后抛错守卫，调用公开 inspect_dev_batch 成功且命中均0；包括 build_fact_packet，不能仅在父进程打补丁后用子进程证明。另作正常新进程CLI对照，两者前后批次文件哈希集合与数据库字节不变。构建观察保留三个输入同一引用，在真实核心调用前、返回后、公开调用完成后三个时点核对指纹；静态核对宿主新动作不调用答案册/生成器/LLM/网络，status不调用构建/渲染。源码哈希绑定所需读取不误判为执行。
7. **证据登记与计数**：所有实际宿主CLI/公开API调用（含造样/负向）进入小型统一记录器；保存真实命令、完整stdout/stderr、退出码，API的完整返回或真实异常/traceback/cause单份引用。receiver与checker按receive_invocation及checker_invocation双向核对命令/started/退出码及文件存在+实读SHA。计数从现场导出，直接CLI/API、receiver内checker、MATCHED报告、已恢复确认的成功0007、失败/半文件、副本、模拟决定/真实批准分列；子集明确scope，无法观察的内部次数写null。台账缺失、未登记、错误引用进入正式failures/非零判定。只在审核副本**删除一条调用登记**、保留其他台账不变，执行同一正式审计helper必须失败；无需重跑整套受损入口。
8. **保护与停止点**：正确118788项基线仅宿主/宿主指南变化、missing=0；关键冻结哈希一致，本卡不变；产物固定路径、新目录、不覆盖。最终链0001—0007有效、workflow未变、真实批准0、next_step_allowed=false，无0008/AI/人类判断/正式契约/真实Gate。该保护结论进入正式失败判据。

每项负向同时核对类别和目标原因，不以任意异常算通过。必须区分执行端实跑、只读既有证据与 GPT 以后实际复验；预期故障不算测试失败，但探针没命中/未保存真实原因应失败。大对象单份保存、路径与实读字节哈希引用，避免每条日志重复嵌套 normalized/workflow/packet。

最终命令形状：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_fact_packet_demo_workflow.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\workflow_host_tests\task015_<最终唯一名称>'
```

## 8. 回执、交接与验收判定

`docs/EXEC_REPORT_015.md` 给出实际实现/协议版本、两个修改文件/新增测试的完整SHA-256、冻结件核对、真实最终命令/退出码、八组结果与证据引用、实际调用/现场计数、真实核心返回与输入观察、故障命中/原因链、文件台账读回、正确基线保护比较、过程失败尝试及未解决项。回执写完后的自身最终哈希放交接消息，不写回自身追求自指一致。

交付三条绝对路径：本轮测试容器、批次父目录、外置SQLite父目录；中间失败尝试现场保留，不能清理/回写成成功。人类转交 GPT 验收并操作 DSH；执行端不把卡自报 done 当作验收完成。

阻断项：业务事实或绑定错误、伪批准/预填判断、失败误报成功、未实际调用核心、旧文件被改、影响结论的观察/引用/登记错误。旧文案等不影响结论的辅助问题如实登记，不为已补证事项反复整套重跑。

本卡不存在需要人类先决定的新业务口径。若实际遇到必须改变冻结核心、规则/金额/缺失关联口径，或必须作真实业务决定才能继续，保存具体字段、矛盾与现场，停止受影响部分交回 GPT/人类；不得自行扩大授权。

完成后停在**开发态0007 / FACT_PACKET_RECORDED**，等待 GPT 验收；不实施下一任务。GPT验收通过后继续制定下一张任务卡，真实Gate批准和审计判断仍由人类作出。
