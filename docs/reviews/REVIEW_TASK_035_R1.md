# TASK-035-R1 独立验收：通过

日期：2026-10-16。技术结论 **ACCEPTED**，以本轮 `review_result.json` 的最终保护确认发布为准。B1/B2关闭，接受范围为TASK-035修正后的独立纯内存人类初判核心及当前测试，不包含保存、完整历史发现、运行适配或真实初判。未修改生产代码、交付测试、既有指南或看板；没有子Agent、执行会话或跨会话指令。

证据根：`data/reviews/task035r1_gpt_20261016_132048/`。最终交付是 `data/human_initial_judgment_tests/task035_r1_finalization_01/delivery.json`，最终核心观察为 `task035_r1_run_02`；修前9次、过程run_01的144次、定稿144次分列，旧TASK-035的125/114不冒充本轮新执行。旧拒绝报告/快照和全部过程现场保留。

## 1. 身份与差异

实读同一缓冲核对三件交付长度/SHA，与delivery一致：

- 核心28927 B，`312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`。
- 测试43985 B，`9b003d983251f4b50e5db1f5992fd6ca33e6d3b570430d9b57e9b94cb2e805dd`。
- 修正回执11730 B，`04a17cef58141b5cfe4dac2539e7d2bd5abe7b5e00b96f473d8bee3c422e54bc`。

修前两份原字节与TASK-035交付SHA精确一致。从修前保全件逐定义AST比较，核心只改变 `_entity`、`_match`，只改变CORE_VERSION赋值为 `TASK-035-human-initial-judgment-core-1.1`；唯一API、异常类、其他函数/协议常量/成功record构建均不变。规范源码差异保存为core_diff.patch。运行适配器、十四项代码清单、16个运行API及正式契约身份与TASK-034接受基线一致；初判核心未进入现有运行凭证。旧指南的1.0和旧计数是原交付时点，冻结保留；当前补丁身份以R1回执及本报告为准。

从已接受协议的实际JSON缓冲提取schema，独立核对 `_match` 当前消费的15组对象诊断键序（含Gate2扩展）；不使用任一输入的插入顺序，也不把schema改为字母顺序。列表仍按下标，不透明载荷未重写业务schema。测试main及pure_guard AST与修前完全一致。详见identity_audit.json、static_semantic_audit.json。

## 2. 交付完整观察与独立复验

执行端156项检查/147条API（144核心+3审核helper）/144条核心观察与expected_observations完整内容规范一致；七项台账逐项实际读回长度/SHA。父调用参数和返回/异常、实际核心增量、同引用三时点快照闭合。全部15份成功返回由评审端按协议独立构造并比较；原14份成功内容另与旧定稿逐字节规范比较一致。29个新增负例的原阶段代码对象轨迹均实读与步骤1至拒绝步骤闭合。

非法Python输入的证据标签只用于可还原记录，不传给核心：bytes保留hex、NaN保留类型/repr、非法UTF-8保留转义。交付指纹明确是recorded_evidence_snapshot；非法原对象的raw_canonical_sha256为null+原因，合法原对象另有实际规范指纹。没有给不可规范化原值伪造JSON FP。核心守卫22个受控探测被拒，导入/调用命中0；pure_guard实现未改。

本轮执行新的 `verify_current.py`，共 **28次原公开函数代码对象入口**，每次保存完整输入/预期/返回或异常/cause、同引用三时点、实际阶段轨迹。旧评审脚本仅作为定义参考，未直接执行或写入旧路径；新增脚本和输出均在本轮根。

- **B1关闭**：修前四种bytes/NaN反例及坏UTF-8、period_end=null、cutoff整数对照均为真实HumanInitialJudgmentBlocked，精确field，实际阶段1—2；坏UTF-8保留UnicodeEncodeError原因链。`_entity`现按schema逐项严格字符串/UTF-8/固定值校验后才作完整canonical比较。真正内部RuntimeError接缝仍为HumanInitialJudgmentError/internal并保留cause，没有用统一Blocked掩盖内部故障。
- **B2关闭**：entity与run双错的正/反序、run两侧同时反序，以及fact/Gate/files两侧反序均按schema稳定首报；分别实际停在第2/5/8/8/7步，晚层反例此前步骤真实完成。独立预期在调用前固定，未检测后刷新；unknown A_extra/Z_extra仍按UTF-8先报A_extra，列表下标保留。执行端另外20次五组四种两侧组合与2次unknown观察完整审阅通过。
- 合法完整返回、递归键序变化、登记的暂不能判断/秒精度时间及指令样式原文、八项严格false、深层返回无别名、history=None、false/0与0/0.0、正确外层M下来源矛盾、重复备注最早拒绝均通过。28次均一次真实核心入口，其他业务模块代码入口为0；独立守卫11次探测有效，导入和调用命中0。

数据和观察见independent_observations.json、verification_summary.json、delivery_evidence_audit.json。未将执行端PASS或清单勾选当作本轮验收依据。

## 3. 实际main、覆盖缺口与范围保护

四个当前交付测试的实际main新进程只读replay，真实退出码 **0/1/1/1**；完整候选返回替换、台账晚变更和checks晚变更均影响最外层返回码、stdout末次结果、summary和failures。两个晚变更真实命中1、增加1个LF，bytes_ok=false；candidate-return的audit_ok=false。逐进程profile全部项目scripts函数，新增业务调用均实测0。原task035_r1_run_02全部文件前后SHA一致，坏字节在新具名根保留。详见closure_controls.json及四组stdout/stderr/profile。

额外合法闰日、±14:00正向人类时间继续null+未提供对应原文；日期及+08:00两种格式已执行，日历/偏移实现静态核对。沿TASK-035/R1卡允许的明确补充缺口保留，不冒称动态通过，不阻断当前修复接受。已登记人类字段来源沿前次human_provenance_audit只读复用，没有新造人类值。

局部定稿后一次全树扫描，同时对TASK-035观察快照166224项/SHA `a0f9ca00b032c8a8240956f1209f1cc4c5b1888a4a96357bb5d7312fe8960829`，及TASK-034接受基线166060项/SHA `cf6b59b525708ab025ee42411e52bab58488d7dda7d1ce25c0bbe5f9551bdcfc` 计算保护口径。观察快照只允许核心/当前测试两份变化；接受基线既有冻结项changed=[]。新missing、读取错误、范围外变化/新增、身份漂移须0才能发布本轮接受结果和新基线。新增逐项确切路径登记，不使用目录前缀豁免；扫描后自身元数据有限登记。最终实测项数/SHA见protection_result.json/source_hashes_after.json/review_result.json。

139历史损失与本轮missing分列；27恢复、R5的326项、R1命名偏差19项和TASK-030具名41 B锁偏差保持原状，不追认、恢复、重建、移动、清理或执行。修前/过程根及旧TASK-035拒绝记录全部保留。

## 4. 下一卡与业务边界

下一卡 `docs/tasks/TASK-036_DRAFT.md` 仅独立初判对象快照独占保存与只读核验，真实调用冻结1.1核心，不接运行层、不发布已核验完整历史索引、不新建0009。单份快照中prior_history仍是传入的有界声明；未来运行接线负责真实Gate/fact/材料实读、完整历史枚举并先核验各完整旧快照后提取索引。本卡技术物理保存与真实独立初判业务状态明确分开，保存成功也不解锁AI。

当前真实批准null、真实初判未保存、开发宿主0008、next/AI=false。核心VALIDATED、快照保存能力、复算一致或本次技术验收均不批准真实批次、不认证身份、不形成审计结论。看板由人类办理，下一卡尚未实施。
