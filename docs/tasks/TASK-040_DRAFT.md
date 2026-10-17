# TASK-040：合成运行的人类独立初判保存与只读恢复

分类C，Architect设计、执行端实施、Architect独立验收。生效前提是 `data/reviews/task039r1_gpt_20261017_100901/review_result.json` 正式ACCEPTED；从其中实读新接受基线SHA/项数。本卡是合成数据建设授权，不批准任何真实批次，不启动执行会话。实现范围以本卡和已接受TASK-039设计1.1共同限定；不得扩展到初判后的下一业务步骤。

## 1. 身份、允许修改与新增

先读REVIEW_TASK_039_R1、同根review_result/source_hashes_after，TASK-039-R1修正卡及已接受运行保存设计全文/44例、REVIEW_TASK_038和现有初判三个组件。旧NOT_ACCEPTED及所有过程证据只读保留，不执行旧测试/评审run或main。

唯一可修改既有文件：`scripts/runtime_gate1.py`，起点290568 B / SHA `ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a`。允许新profile必要常量/材料名单变化、有限私有共享材料分支、Windows锁封装与两个指定公开API。其余生产/核心/P1/store/history/SQL/schema/正式契约/生效登记/配置/旧测试/指南/宿主全部冻结。不拆模块、不重写核心、不新增依赖/通用框架/生产CLI/UI/身份系统或数据库schema。

必须实读冻结身份：

- 初判core：`scripts/build_demo_human_initial_judgment.py`，28927 B / `312022e830b4925c6a23da12023a69b601a6c89e2167d9be24eccafd5bb4ac35`，TASK-035核心1.1。
- store：`scripts/store_demo_human_initial_judgment.py`，25787 B / `a1b4389d38fa4541eb7792feec034becf94a108ecf72a1fe11fc78ccb4da280c`，TASK-036存储1.1。
- history：`scripts/inspect_demo_human_initial_judgment_history.py`，15064 B / `7276ddb704d27cec031ca3c2af4122a3c2c890d613bd4cfa90e6454d72000b22`，TASK-037历史1.0。
- 运行保存协议：`docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md`，36779 B / `0b92e8629a9d8306a8fc9b383a835f393db028a4acdda6d91bde901de7a6b2db`。
- 运行保存案例：同目录 `RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_CASES_V1_DRAFT.md`，23542 B / `177d58018071b7f87c74be04ce2f1a0d8a7600598e168e9396b8010cb735729b`。

正式契约 `docs/AUDIT_CONTRACT.md` SHA `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`；生效登记 `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md` SHA `042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`。TASK-034原协议/案例及其余冻结身份从接受基线实读。

仅新增三份交付：`tests/test_runtime_initial_judgment_recording.py`、`docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md`、`docs/EXEC_REPORT_040.md`。允许本轮新具名根：

- `data/runtime_initial_judgment_recording_tests/task040_<轮次>/`。
- `data/runtime/task040_<场景>/`，含新登记/运行计算输出及协议固定的 `<登记叶名>.initial/` 封装。
- `data/human_gate_decision_records/gate1/task040_<场景>/`、gate2同名根。
- `data/sqlite_tests/task040_<场景>/`。
- `data/human_initial_judgment_records/task040_<场景>/`，含绑定声明域、直接叶六文件及namespace同级的协议固定锁文件。锁路径必须仍位于本轮task040根内，不借本卡在旧域同级写锁。

根不是前缀豁免；实际新增展开每个确切文件路径，包括失败、半写、锁、保存原件/坏字节、子进程控制及过程产物。只读复用 `data/batches/task027r1_run_04/batch_normal`（input.xlsx SHA `8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341`），不改批次。Windows/PowerShell，Python一律-B。不能删移/清理旧或本轮失败现场；若必须改冻结组件、协议政策、扩大根/分类，停止该级处理并报告Architect。

## 2. 新profile与共享材料

新代码清单仍恰十七项：既有十三冻结组件、初判core/store/history、适配器自身。新 `CODE_MANIFEST_VERSION=TASK-040-code-manifest-1.0`、`REGISTRY_VERSION=TASK-040-runtime-registry-1.0`、`RUNTIME_VERSION_028=TASK-040-runtime-gate1-1.0`。登记仍十四键，initial_judgment_history仍两个字段且在Gate1之前固定；六项run_binding结构和全链精确一致规则不变。适配器自身FILE来自本次开始缓冲，不自嵌哈希。

Gate1材料从TASK-038的38项增加上述已接受运行保存协议/案例两项，恰**40项**，project角色及UTF8排序/唯一规则沿现有口径；登记原件仍为runtime/runtime_registry.json角色。两新件用上述独立固定身份读核、开始捕获及末次确认，不只在新登记里自报哈希。Gate1/Gate2/事实/初判绑定均包含同一新代码身份；阶段材料摘要无需相同。旧TASK-038凭证明确版本/身份拒绝，不迁移、补签或改旧文件。

原十七公开业务API签名和既有规则保持，增加本卡两个后共十九。公开prepare仍只读、当前域已有本批记录即拒绝；不能为恢复加入公共skip/ignore/force/allow_existing。允许将其已核验Gate/事实、九键材料正文/八FILE角色、独立expectations物化提取为有限私有共享分支：输入只能内部本次捕获源与真实核验结果。保存仍真实调用公开prepare一次；恢复从真实当前history核出的目标取request_id/P0，但当前材料预期来自当前Gate/事实源，不能从存储候选反推。

原请求版本TASK-038-human-initial-judgment-request-1.0、TASK-034材料/预期schema及本次已接受TASK-039保存stage/status/封装/锁版本常量保持；材料runtime_version取当次真实TASK-040登记。旧静态checker绑定TASK-038且检查未来函数尚未实现，是冻结档案，不为使其在新生产版本PASS而改它或旧指南。

## 3. 两入口与固定流程

```python
def save_runtime_initial_judgment(
    batch_dir, runtime_dir, request_id, submission, record_relative, *,
    scope_dir, event_relative, database_path, gate2_event_relative,
    history_expectations
): ...

def verify_runtime_initial_judgment(
    batch_dir, runtime_dir, *, scope_dir, event_relative, database_path,
    gate2_event_relative, record_relative, history_expectations
): ...
```

严格实现已接受协议1.1的S1—S9/V1—V8、键集合/首报顺序/常量/异常与44例关系，不在本卡重设政策。record_relative恰绑定域+安全直接叶，原始路径链先于resolve/消段，域既存且固定、save叶/封装从未存在，verify目标在caller独立固定完整名单中。参数先类型/原链再关系，严格UTF8、dict/list/int/bool及canonical比较；False/0和0/0.0不能同等。人类字段原对象直接交冻结store.save，不先序列化非法submission或复制核心首报逻辑。

保存：持自锁后真实prepare一次固定完整请求、H0/P0和操作开始源；started不填未知人类event/actor；复确认后冻结store.save一次（内部核心构建一次）；同缓冲六原文件绑定完整STORED十一键与四输入快照。E1仅E0加本次已核验manifest FILE；真实post-history一次核n+1叶，完整H1及旧叶、本次目标与独立E1闭合，旧P0/expectations不改。context完整H0/S/H1及原提交、两键prepared；receipt最后写。完整十二键成功候选/独立预期先构造审核，全部必要消费后以开始缓冲/本次writer缓冲末次确认，再释放自锁，直接返回RECORDED。

恢复：全程只读；锁/两类failure/布局优先，同缓冲固定全部源、m叶及三封装。真实history一次核完整当前名单，目标取其完整VERIFIED十一键，不额外直verify目标。封装完整绑定S/P0/H0/H1；私有材料分支真实直接Gate1/Gate2/fact各一次，不调用公开prepare、不重建材料算法。当前materials整对象相同，expectations前十项当前来源、后二项已核验保存P0；旧H0/H1叶和引用仍在当前域逐字节/四字段匹配，允许后来合法其他批次叶。不是当前域减自身、不是拿当前Hc覆盖保存H1。完整十二键候选审核后末次原字节/集合/路径/failure/锁确认，直接返回VERIFIED；不写failure/日志、不取时钟/随机/网络/子进程。

三封装成功恰started/context/receipt，历史直接叶仍恰冻结六件。FILE与FP按已接受27项有限来源角色及冻结契约，不按后缀；对象/长度/FILE同缓冲，FP单列，readback对本次writer缓冲，末次确认不能重采后自比。返回含完整storage_verification/history_verification及三封装描述，所有运行九边界false，核心八边界及persisted=false保持。独立store成功后运行失败不得作为RECORDED。

异常按实际加载类对象映射：store/history Blocked原field加前缀、reason/reasons/cause保留；Error原stage/reason/reasons/cause/secondary保留。本层failure十一键仅本次独占封装目录创建后独占写一次，不新增时间字段、不覆盖坏诊断。有效失败优先，坏失败先schema，不让缺context或原生KeyError遮蔽。诊断故障不替换主异常。两个根不原子，不自动回滚、重试、清锁/删叶/补签。

## 4. Windows真实句柄锁

仅用标准库ctypes或等效系统接口在适配器内作有限封装；按已接受协议真实CREATE_NEW，请求读/写/DELETE，仅共享读，不共享写/删除。锁是namespace同级唯一普通文件、五技术键，无人类owner/新时间/随机；任意既有锁先Blocked，不读正文猜过期。记录原父身份/句柄file ID/属性/大小/本次writer缓冲，持有至全部确认。不得使用创建即DELETE_ON_CLOSE导致失败现场被自动删除。

成功只以**已持有句柄**设置删除标记并关闭，确认本次锁已释放；不得close后按路径unlink，不删同内容替代锁，不将pending当完成。失败不设置删除标记，保留现存锁/半写并关闭资源；释放阶段部分失败保留实际剩余状态，不伪造重建。调用不可用/权限或平台能力不满足时按Error release.lock等协议阶段失败，不回退路径盲删。外来锁永不释放；verify不取得锁。

开发前可先在本轮独立纯技术锁场景验证实际CreateFileW/句柄读写、兼容共享、文件ID、按句柄删除及释放。它不是Gate/初判批准。真实保存并发至少证明A持锁时B在同域公开save拒绝、B业务调用增量0，A可继续正常完成；不同runtime同域锁名共用可用原生锁原语控制证明，明确其不是第二条完整业务API成功证明。未运行的物理junction继续null+原权限原因，不重试绕过。

## 5. 具名最小场景、人类字段与必要验证

先完成局部实现/原生锁控制，再建立一条定稿代码的新profile正常前提链，SQL/标准化/装载/复算/事实各一次；独立预期R01/R02/R03/R04=0/1/0/0、R02超额400000分仅用于测试。正常保存/恢复、后续只读注入优先复用该链。若开发确需前提，最多另建一条明确标为开发的链，原样保留；不把代码改变前的凭证用于定稿成功。

失败保存会永久保留锁/封装，不能靠删移来复用。允许必要的具名隔离失败场景，优先仅原生锁或本轮只读/内存接缝；若确需完整业务前提，可额外建立至多八条小样失败链，每条登记必要性/对应问题族、代码同一定稿身份，setup调用全部分列。不得为每个字段/44例重复建链；若超过此明确上限先报告Architect。未取得正常真实前提、仅内部控制的例子要准确标证据层级，不能声称完整API实测。

Gate人类字段只用已登记 `data/decision_protocol_checks/task020r2_run_01/fixture_values.json`（35465 B / SHA `6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337`）的合成APPROVE原文；只变技术批次/请求/路径/当前材料/前序绑定，不编造身份/事件/决定时间/原因。

初判六原文只用已登记夹具：event1 `data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json`（1627 B / SHA `81521ff0219f2201d63a5abd55e3ca9351a67e9dc7dee80e6ba509cb6e17f560`）；event2 `data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json`（1728 B / SHA `e7bb88137e11e4db2b24aeaa05a4a488084f7d57fd424f25c2166de17696868a`）。按登记原值取六字段，日期不补时间/时区；“通过”不变成执行许可。技术submission版本/batch/request/M可构造；缺失/错型/错绑定可作隔离负例，不伪造未登记正例。

非空/后来不同batch历史优先把已接受TASK-037合成独立六文件叶按原字节复制到本轮新域（登记准确源/FILE与无旧引用冲突的正常对照），或有限setup调用冻结store，以已登记event2和独立技术材料建立另一batch叶。明确这是独立store历史setup，不宣称另一运行层API保存成功；不改旧快照/P0，不为它重跑业务算法。初判event不足的新正例不造值，登记未执行及原因。

必要问题族如下，交付用44例映射表说明本轮真实实测、冻结证据引用和未执行的具体边界，不追求检查数量：

1. 正常n=0保存、m=1恢复完整返回和九文件与写前独立内存预期一致；原submission/history_expectations真实引用进入/store后/外层收尾三时点不变，副本无别名；公开prepare在已有本批历史后仍拒绝。后来另batch合法叶使Hc大于H1时恢复成功，旧P0/H0/H1/receipt不变；非空n场景若实际执行按公式计，未执行不可套预测实测。
2. 路径/域/scope/完整名单/目标缺失、已有空叶/封装/外来坏锁、原链alias/reparse/..在正确层拒绝；真实OSError阶段准确。当前历史缺旧引用、FP矛盾、重复event/batch及坏其他叶不可跳过。优先复用本轮小样自有场景，不重跑TASK-035/036/037历史矩阵。
3. 已真实固定独立M和H0后，陈旧M/缺assessment或reason/非法人类字段交真实store/core拒绝；不由适配器预处理掩盖。核心前晚改来源本次拒绝，store.save/core构建增量0、目标未建。输入不可序列化时不要先FP而抛原生异常，精确字段优先保持冻结顺序。
4. S6完整S/四快照、S7完整H1/独立E1、S8/V7完整候选分别与独立预期绑定；至少一例形状合法、摘要自洽但完整内容错，不重采预期。RC-44三个摘要角色控制保持更早前提合法并精确定位；False/0、int/float及反序多错首报准确，不能只比较摘要或Python相等。
5. 实际独占句柄半写：冻结store真实writer包装半份后OSError，另一个context或receipt真实writer失败控制；不以替换整个writer声称生产except被运行。receipt真实writer返回后sentinel用write.receipt；有效/坏运行及store failure优先，诊断次错误保留主异常类型/stage/field/reason/reasons/cause。独立六件成功但封装/释放失败仍不成功，失败锁/半写/坏字节具名保留。
6. 最后必要消费后晚改本轮单文件：保存或恢复本次末端拒绝。至少恢复例撤销wrapper保留坏字节仍拒绝，仅精确恢复本轮原件后成功；恢复不写failure。新增叶/failure/未知文件控制现场不删移，sticky失败与可恢复单文件控制分开。锁身份控制分“系统真实阻止替换”和“内部身份矛盾拒绝”，不能把模拟不同file ID写成物理替换已成功；release真实失败不得返回RECORDED。
7. 恢复写/时钟/随机/网络/子进程/save/算法守卫先证明生效，实际恢复成功窗口命中0；允许history内store.verify/core和fact内render，分清禁止build。真实代码对象入口计数、父关系、登记、完整参数/返回/异常/traceback/cause/secondary与三时点闭合；直接/嵌套、构建/核验、setup/正式窗口分列，不能把重放旧观察算新业务调用。
8. 定稿完整观察先固定独立内存预期，candidate全量canonical绑定，台账自身真实同缓冲读回与末次字节确认支配最外层test main退出码、summary、failures。四个实际main新进程replay控制0/1/1/1：正常、内容反例、台账替换、最后读后字节漂移。均不新增业务调用；不得按注入标志直接返回1或只内部FAIL而外层0，坏字节原样保留。

固定正常调用图：save直接prepare1/store.save1/post-history1，history总2、初判store.verify=2n+1、core总2n+2（构建1、核验2n+1）、直接core0；verify公开prepare/save0、history1、store.verify/core各m、直接core0。两者Gate1verify6/Gate2verify5/loadinspect5/screeninspect2/crosscheckinspect1/factinspect-render各1/Gatestoreverify-P1各11/冻结prepare6；SQL/标准化/装载/复算/事实build/旧模拟初判0。失败按实际前缀计，不套正常公式。

新指南先定稿上述schema/阶段/调用图/首报/边界，再验证。测试入口 `.venv\Scripts\python.exe -B tests\test_runtime_initial_judgment_recording.py --out-dir data\runtime_initial_judgment_recording_tests\task040_<新名>`。仅有限复用已接受观察helper定义，不执行旧run/main或增加通用框架。未执行给null及原因；引用旧证据与本轮实际重跑分列。零线索、暂不能判断等无本轮合法完整前提的正例可引用冻结核心接受结果并明确运行层未执行，不编造新fixture或伪改事实凑覆盖。

## 6. 定稿、保护与停止

局部实现/新测试/新指南/回执/完整观察/四CLI定稿后，一次最终全树保护扫描，相对TASK-039-R1新接受基线唯一既有changed为runtime_gate1.py；新missing/范围外新增/读取错误/身份漂移0。新增逐确切路径登记，前次快照自身与review_result仅两条元数据有限单列；扫描后只做有限自身元数据，不因局部工具错误反复扫树。

139历史损失、27恢复、R5越界326、R1命名19、TASK-030原41 B锁及所有旧过程现场冻结，不追认、恢复/重建/删移/清理。回执列四交付身份/19 API/17代码/40材料/正常和失败的真实调用图/原生锁平台实证/44例证据层级/未执行项/完整保护结果。交付停止待独立验收，不推进TASK-041，不改看板。

固定澄明商贸有限公司、CNY、2026年9月/截至2026-09-30；整数分、原ID、主表与分摊分列，R01—R04是待核查线索。事实模板提示保持。真实批准null、真实初判未保存、开发宿主0008、next/AI=false；本卡只建设合成测试快照，技术验收不批准真实批次，不认证身份、不开放真实数据、AI或终判。
