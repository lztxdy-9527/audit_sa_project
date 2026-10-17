# TASK-012 草案：保存 Gate2 模拟决定，恢复状态后停住

执行：DeepSeek；架构与验收：GPT；主理人转交本卡。项目根目录：`D:\harness work\audit_sa_project`。

**本卡可交执行；只完成本卡，回执后停住。**先读 `docs/reviews/REVIEW_TASK_011_R2.md`、本卡、现行宿主/控制器指南和相关公共 API。不要按旧回执猜现行接口。

## 1. 当前成果与本次实务场景

项目检查澄明商贸有限公司 2026 年 9 月人民币办公耗材采购付款的合成 ERP 导出数据。接收、质量核验、标准化、SQLite、规则、独立复算和事实底稿模块已分别验收；宿主现在已实际接收、标准化和装载，形成完整 Gate2 材料并停在 `DEV_GATE2_PENDING`。

实务对应：数据已入库，数量金额与来源核对材料齐备，接下来记录一次“材料是否允许进入筛查”的决定。本轮只是**显式模拟决定的保存与恢复**，不进行真实审批，不执行筛查。

本轮增加：

```text
新 start → Gate1 显式模拟 APPROVE → prepare-gate2 → Gate2 pending
→ 人工构造并明确标注的 Gate2 模拟 APPROVE / HOLD / REJECT
→ 保存 0004 → 新进程 status 恢复 → 停住
```

三种结果都停住。APPROVE 后控制器可以声明 `SCREEN_AND_BUILD_FACTS.simulation_allowed=true`，但宿主**没有执行筛查的命令**。HOLD/REJECT 为停止态，不能改签或继续，需补证/修订时新建批次。

仍为 `DEVELOPMENT_TEST_ONLY`、`DRAFT_NOT_IN_FORCE`；`gate1_approval=gate2_approval=null`、`next_step_allowed=false`、真实批准 0。不得把模拟 APPROVE 写成真实 Gate2 已放行。

## 2. 文件范围、版本和保护

仅允许修改两个既有文件：

- `scripts/run_demo_workflow.py`
- `docs/WORKFLOW_HOST_GUIDE.md`

只新增：

- `tests/test_record_demo_gate2_decision.py`
- `docs/EXEC_REPORT_012.md`
- 全新 `data/workflow_host_tests/<新容器>/`、`data/batches/<新父目录>/`、推导的 `data/sqlite_tests/workflow_gate2/<新批次相对路径>/`。

不新增生产模块；不安装依赖、不建 Git、不生成新业务数据。不改冻结控制器、接收器、checker、标准化器、装载器、schema/规则 SQL、筛查/复算/底稿、SPEC/契约草案、原 Excel/答案册。**旧测试入口（含 test_prepare_demo_gate2.py）、回执/卡片/验收单、GPT 证据、旧批次与数据库一律不改、不删、不覆盖。**旧入口的范围断言不适用于新版本，不为让旧测试通过而修改旧入口。

起点 SHA-256：

- 宿主：`4ee841b1e925f148979fdecb2906f471cb37239a89630d7e2f558a3bb12285b1`
- 指南：`99f91242a06f78bec6f508c1541d81916d9ccf70c4ea4ab6ac70fd7b3858c23a`
- 冻结 TASK-011 测试：`11d4fe57690ff5d5438aaf25b9a3953ced9a1e500ccef1620f61f39ec548b4e4`
- 冻结 TASK-010 测试：`852bf336cd2d259e43b4da9eee539a52f48253767c52ff9327f62e12015f5f8c`

主保护基线：`data/reviews/task011_r2_20261011_150713/source_hashes_after.json`。仅宿主、指南两项既有文件允许变化，其余 0 变化、0 缺失；更早基线按各自起点列累计授权变化。

新版本统一使用 TASK-012 前缀与 1.0：host、host-manifest、checkpoint、gate2-artifacts、gate2-failure。现有代码中的对应固定值、材料 `prepare_version`、指南和测试预期一致。发布后用最终固定代码新建批次；不迁移、重签或替旧批次补决定，不接受旧代码绑定。

冻结上游前缀：控制器 a6b7b8e1、接收器 52195620、checker a7e5eb67、标准化 a2bae49e、装载器 1abfad89、schema 7e0c6463、筛查 1b123766、复算 8fe75bfe、底稿 f4998d92、SPEC 5df632ed、契约草案 af405cb6。执行时保存完整哈希。

## 3. 唯一新增接口与保存顺序

保留四个现有 CLI 与公共 API 的含义。`record-simulated-decision` 仍只处理 Gate1，不暗中改成通用批准入口。

新增：

```text
record_simulated_gate2_decision(batch_dir, decision) -> dict
record-simulated-gate2-decision --batch-dir <新批次> --decision-file <显式模拟决定 JSON>
```

决定结构沿用冻结控制器：`event_id, batch_id, gate, request_id, materials_sha256, decision, actor_kind, actor_id, occurred_at, reason, simulation`；APPROVE 另需 `confirmations.reconciliation_reviewed=true`（严格 bool）。`gate=GATE2`；`SIMULATED_HUMAN` 与 `SIMULATED_TEST_ONLY` 必须显式提供。request/materials 指向本批次 0003 中实际 Gate2 请求；不得自动补齐身份、确认项或默认 APPROVE。HOLD/REJECT 的确认项按冻结控制器既有契约处理。

执行顺序：

1. 共用现行恢复核验：完整链、实际输入/代码绑定、Gate2 材料/数据库字节和语义、失败诊断、初始 checkpoint 哈希及收尾均有效。
2. 当前必须恰为合法 `0003 / DEV_GATE2_PENDING`。早期阶段、停止态、已有 0004、失败/未完成准备、旧版本、绑定变化均在写入前拒绝。
3. 保留初始 0001/0002/0003、manifest、全部 Gate2 产物与数据库哈希；使用实测 current_bindings，把调用方完整决定交给冻结 `record_dev_decision`。不从 phase 字符串推导批准，不自己实现决定约束。
4. 独占写入 `0004.json`，不修改任何前三份 checkpoint、manifest、接收材料、Gate2 产物或数据库。
5. 关闭/读回，用共用恢复协议重放完整链；在最后一次必要控制器调用后，复测所有已消费产物、四份 checkpoint、manifest、失败状态及静态绑定。和初始/本次写入值一致才返回成功。
6. 输出实际 phase、决定摘要、四份 checkpoint 引用、控制器允许动作、真实批准 0 与 next_step_allowed=false。不调用接收/标准化/装载/规则/复算/底稿/AI，也不触发下一步。

数据库仍由旧固定规则推导，不引入调用方任意路径，不复制/移动数据库，不改变旧 run_bindings；新产物继续通过既有 artifacts/0003 引用绑定。

## 4. 0004 协议、恢复及失败语义

0004 顶层与既有 checkpoint 同形：版本、严格 int revision=4、前序为初始实读 0003 字节哈希、batch_id、manifest 文件哈希、完整 workflow、operation。

operation 与现有 0002 的决定摘要风格保持一致：`kind=SIMULATED_GATE2_DECISION`、`at_utc`、完整 recorded decision、由剥离 decision_sha256 后正文算出的 `decision_sha256`、`phase_after`、`bindings_sha256`。

恢复时：

- 只允许连续的 0001 至最多 0004。0003 仍只为 PREPARE_GATE2；0004 只为一次 Gate2 决定；未知/跳号/半文件/目录/0005 一律拒绝。
- 每份对象和 SHA-256 来自同一次初始字节缓冲；重放后不得重新取预期哈希。对 0003 的材料核验及 `gate2_expected` 要保留到 0004 恢复和最终收尾，不能因当前是决定事件就跳过数据库核验。
- 用冻结 `record_dev_decision(0003.workflow, 决定正文, current_bindings=实测绑定)` 复算完整返回，与 0004.workflow 严格比较。保存的决定摘要、正文 SHA、history 末事件与 simulated_decisions 末条相同。
- 0001—0003 的 history 前缀、Gate1/Gate2 请求、已有 Gate1 决定完整保留；新增恰好一次 Gate2 决定，决定总数恰为 2。不能重排、遗漏、增加第三个请求或伪造真实批准。
- status 对 Gate2 APPROVED 声明 SCREEN_AND_BUILD_FACTS 模拟允许、NORMALIZE_AND_LOAD 不允许；对 Gate2 HELD/REJECTED 二者均不允许。AI 始终不允许，真实 next_step_allowed 恒 false。
- Gate1 记录命令、重复 prepare-gate2、重复/冲突 Gate2 决定全部拒绝，不追加 0005、不改签、不清理现场。

保留现行 0/1/2 与异常链。任何保存异常，本次命令不得返回成功；保留半文件与旧 checkpoint，不自动重试、回退或删除。

**决定保存的恢复约定**：本轮不另建一套“决定提交回执/失败标记”协议。若写出完整 0004 后才抛错，原调用仍失败；随后独立 status 必须按磁盘事实重新验证：完整合法链可恢复“决定已记录”的当前状态，非法/不完整链则拒绝。这不追认原命令成功，也不自动再提交或执行下游。指南提示遇到保存异常先用 status 查明事实，不重复决定。现有 `workflow/gate2/failure.json` 仍表示准备阶段失败，继续优先阻断；不得删除、忽略或拿决定保存异常覆盖它。不要把本约定误套到 TASK-011 的准备失败恢复。

## 5. 有界测试与真实留痕

新测试入口用项目 Python `-B`，编译源文本，使用全新容器/批次。只读既有 Excel，不读答案册。无需重跑 TASK-002—011 整套冻结入口，但新入口要覆盖本卡完整流程与关键回归。

至少覆盖以下八组（可合并有限探针，组数按实际）：

1. MAIN 实际 start→Gate1 模拟 APPROVE→真实 prepare-gate2→新进程 Gate2 模拟 APPROVE→新进程 status；全套材料/数据库字节不变，前三份 checkpoint 真正调用前后哈希相等，0004 前序/完整重放一致。决定和 status 阶段真实 normalize/load/规则调用均为 0；该批次此前真实标准化装载另计。
2. 小样 C02 两个独立批次分别 Gate2 HOLD/REJECT，恢复停止态、不能改签/继续；C07b 合法未匹配关联批次可模拟 APPROVE，保留其金额/来源，不改成质量问题。MAIN 金额不能硬编码为批准条件。
3. 早期 Gate1 pending、Gate1 APPROVED 尚未 prepare、Gate1 HOLD/REJECT、失败准备或有有效 failure+完整0003，Gate2 记录均拒绝；错误 gate/request/materials、AI 身份、REAL、缺 reason、确认项 false 或数字1、重复 event_id 分别匹配目标原因。用少量新内存决定/副本复用材料，不为每个字段重复跑重型 MAIN。
4. 三种 Gate2 决定后重复提交/冲突提交、Gate1 再提交、prepare-gate2 再执行，全部拒绝且文件字节不变、无0005；旧版本/普通接收批次有限回归。
5. 0004 有限副本错前序、错决定正文指纹、错操作摘要、phase 伪造、不是0003合法延续、未知0005；恢复均按字段拒绝。改数据库/报告仍拒绝，证明0004没有绕过0003材料检查。同步造样指纹仅为进入目标检查，逐项注明，不冒称上游重算。
6. 真 writer 的0004部分写入一次：完整 text 捕获并保存，实际部分文件0<bytes<完整UTF-8字节数，真实 write/raise 各1、sentinel OSError 原因链、调用前后旧0001—0003字节相等，后续恢复拒绝。另有限完整0004写后抛错，对照上述决定恢复约定，原命令失败而正常status验证完整链可恢复；不宣称原命令成功。
7. 有界收尾变化：在 Gate2 决定纯重放返回时只改变新0004字节，当前调用即拒绝；另在写后重放时改 load_report 字节，当前调用及撤销后恢复均拒绝。各命中1、真before/after、未变化正向；保留TASK-011 checkpoint同源读取原则，不扩大fuzz/并发/锁试验。
8. status只读守卫：不写文件、不启子进程/网络，不调用normalize/load/筛查/复算/底稿；静态+适当运行期核对无答案册/生成器/LLM。最终summary/checks/日志由同一最终对象落盘读回后输出；隔离matcher与计数自测不污染failures。

负向同时匹配异常类别和**具体目标原因**；保存完整命令、退出码、调用参数/返回/异常、同步说明和真正前后哈希，不能只留 bool 或截断关键原因。

计数由实际调用记录导出：公开宿主 API 包括通过 status helper 进入的 inspect_dev_batch，不能只累加部分调用点；CLI 子进程调用、进程内公开 API、私有调用、控制器造样与宿主内部重放分清。推荐测试侧统一包装/观察公共入口，禁止生产测试开关。receiver/checker 启动与留痕一一对应，副本排除，失败前真实调用要计；不可观测次数明确 null，不当总数。新回执不照抄旧计数，旧测试/回执不回写。

## 6. 指南、回执与停止

指南增加第五个 CLI 的可复制模板及显式 Gate2 模拟决定样例，固定 `reconciliation_reviewed`，无默认批准。写清三种状态、状态恢复与决定保存异常后先查 status 的约定，及“模拟允许筛查但当前宿主未执行筛查”。

顺带纠正现行指南的几处过时句子：只允许0001/0002；APPROVED后无标准化命令；宿主不导入标准化/装载；目录中重复的workflow根artifacts.json；failure与0003的“不共存”应为“失败记录存在就不宣告成功”，失败现场可以同时有完整0003。只改与当前链/版本/行为直接相关的说明，不做无关改写。

EXEC_REPORT_012.md 列完整哈希、实际命令/退出码/计数、三条新产物路径、三种决定结果、重启恢复、失败/收尾证据、保护结果、失败尝试及未执行项。没有执行的检查不得写通过。GPT 负责复验，主理人无需运行测试或签真实 Gate。

**完成后停止。**不新增筛查/复算/底稿执行命令，不跑 R01—R04，不建正式契约或真实审批，不保存人类判断，不生成 AI 建议，不做UI/真实ERP/压测，不推进 TASK-013，不宣布项目完成。
