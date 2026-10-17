# TASK-035-R1：entity 字段拒绝与确定性首错定点修正

状态：Architect已制定，待执行端实施及独立验收。分类：C，协议核心实施修复。依据：`docs/reviews/REVIEW_TASK_035.md` 的 **NOT_ACCEPTED / B1、B2**。本卡不接受TASK-035，不推进TASK-036；执行端不自行ACCEPTED或改看板。

## 1. 权威入口和起点

先局部读取本卡、REVIEW_TASK_035、`data/reviews/task035_gpt_20261016_124800/review_result.json`及其观察快照登记，再读 TASK-034 正式接受协议/案例、TASK-035原卡和本轮相关代码。观察快照只用于本轮修复保护，不是接受基线；最新接受基线仍 `data/reviews/task034_gpt_20261016_115103/source_hashes_after.json`，166060项，SHA `cf6b59b525708ab025ee42411e52bab58488d7dda7d1ce25c0bbe5f9551bdcfc`。不得从旧快照回退当前文件。

当前核心 `scripts/build_demo_human_initial_judgment.py`：27384 B / SHA `d921b1a8dc73a4503294b915e8926f31ed332c52e3cfc8fc9fdbb07ff82be761`；当前测试 `tests/test_build_demo_human_initial_judgment.py`：37615 B / SHA `6ddfc1f748b3a67e3ce3e78a7133e4ca72c83cb5193f2ad50900e9ae1f6ddaa0`。实施前逐项实读核对。Windows/PowerShell；Python `.venv\Scripts\python.exe -B`，不产生新pycache。

允许修改仅上述**核心和当前核心测试两份文件**。仅允许新增 `docs/EXEC_REPORT_035_R1.md` 及 `data/human_initial_judgment_tests/task035_r1_*` 本轮具名根，新增全部展开确切文件路径登记。既有指南、TASK-035回执/卡、协议/案例、正式契约、运行适配器、所有其他测试和旧证据冻结。本卡由Architect建立，执行端不得改写。不得新增通用框架或无关重构；若必须越界或问题分类改变，停止该级处理，报告Architect，不自行扩大范围。

运行适配器仍264105 B / SHA `65946ffd740771c3917297d5d566c147c641004547fbbbb71873d5b53898e78a`，十四项代码清单及16个公开API不变。新初判组件不进入当前运行凭证，不新建开发宿主0009或业务运行/Gate/SQLite。

## 2. 必须关闭的两项阻断

**B1：消费前严格校验entity自有固定字段。** `_entity` 的 company/currency/cutoff_date及period.period_start/period_end均为协议固定字符串。必须在canonical或关系消费前以精确字段拒绝错类型/非法值/坏UTF-8；materials.entity和packet.entity两处适用。bytes/NaN等非法候选须为真实 `HumanInitialJudgmentBlocked(field,reason)`，不能落到internal Error/TypeError/ValueError。不可将所有序列化异常统改Blocked或省略完整canonical比较；真正内部技术异常仍 `HumanInitialJudgmentError(stage="internal")` 且保留cause。

**B2：关系首错独立于两侧字典插入顺序。** 协议§8同一步按对应schema键顺序、列表原序；未知键按UTF-8序的既有规则保留。`_match`及相关诊断不能使用候选或expected的插入顺序决定首错，也不能把所有schema改为字母排序。对已声明自有对象用明确协议次序，保留完整规范相等、类型敏感及叶级field；上游不透明载荷不重写业务schema。所有使用该关系比较的entity/contract/run/fact/gate/files嵌套按同一规则成立。仅作必要小修，不建立通用schema引擎。

保持唯一API签名、TASK-034协议对象版本、九键record/十键binding/外置FP、人类原文、历史语义、八false边界和成功记录内容不变。无默认值补救、预期刷新、排序修复候选、自动决定或权限开放。

## 3. 有限验证和证据

只用已登记人类夹具，技术负例可对合法基样做受控单处/具名多处变更；不作为新的人类决定。先固定独立预期，完整记录变更字段、阶段、field、异常类和cause，输入同引用三时点、原代码对象计数及父调用闭合。以本轮review的 technical_base 复现方法为参考，不执行旧评审脚本写旧根。

必要定点覆盖：

1. 合法完整返回与独立预期一致；递归改变两侧对象键插入顺序仍成功且FP不变，返回无输入别名、八项严格false。
2. B1：materials.entity.company bytes、NaN，period.period_start bytes，packet.entity.company bytes；各指向对应字段Blocked，无成功record。补有限非UTF-8固定字符串/典型错类型对照即可，不造巨大矩阵。
3. B2：同一规范对象company/currency双错、code/config双错，在候选反序和expected反序下，分别稳定首报company、code.file_sha256；明确后者满足前四步、第5步拒绝。再选一个已通过所有更早步骤的嵌套关系及files同成员多错对照，证明使用点闭合；不刷新待测内层独立预期。列表成员错误仍原下标，未知键仍UTF-8次序。
4. 缺失/类型/未知键早层、bool/int/float敏感、外层M不掩盖内层关系、历史语义、重复语法顺序及意外内部Error/cause保持；现有当前核心回归可用本测试一次定稿运行，禁止上游/历史大套件或重复建业务链。无需因B1/B2自造新的正向人类时间。
5. 纯核心导入/调用I/O等守卫先证明生效；核心调用真实代码对象与完整观察/父调用闭合，不把wrapper数当真实调用。只读复用既有小型观察/收尾helper，禁止执行其旧run/main。
6. 四个实际main新进程replay：0/1/1/1；新增核心/其他业务调用均由独立代码对象profile测得0，源文件不变。完整独立预期、候选内容、台账实读及末次原始字节确认共同支配外层返回码/summary/failures，不只内部诊断FAIL。保留所有坏字节和失败产物，不清理/覆写旧现场。

额外合法闰日和±14:00人类正例继续null+原因，不冒称PASS；如人类未来明确提供，先登记原文来源再测试。现有补充人类值可按已核对来源复用；指令样式测试句是普通数据，不新增权限。

## 4. 保护、回执与停止

局部定稿后一次最终全树保护扫描：同时对本轮观察快照检查仅允许两份修改，并对TASK-034接受基线单列累计新增/既有冻结状态。旧新增核心/测试在TASK-034基线中不存在，不能因此漏检本轮修改权限。新增均确切路径，范围外变化、新missing、读取错误为0；扫描后自身元数据有限确切登记，无目录前缀豁免。139历史损失与当前baseline missing分列；27恢复、R5的326项、R1的19项、TASK-03041 B具名锁偏差及其他失败探针均保留，不追认、恢复、重建、移动、清理或执行。

回执登记修后核心/测试和新回执长度/SHA、相对两基线的保护结果、每项阻断的前后真实异常/field、完整观察/实际调用、四CLI和未执行项。旧125/114保留旧证据身份，不能冒称本次实测。交付后停止，由Architect独立验收；不实施保存、恢复、适配、事实改写、初判持久化、AI或终判。

固定业务为澄明商贸有限公司/CNY/2026年9月/截至2026-09-30；金额整数分、原业务ID保留、主表与分摊分列，线索不称损失/舞弊/审计结论。人类是业务决定和真实Gate批准唯一决策者。真实批准null、真实初判未保存、开发宿主0008、next/AI=false。技术修复/验收不批准真实批次；看板由人类办理。
