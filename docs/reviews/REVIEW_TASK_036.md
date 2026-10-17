# TASK-036 独立验收：未通过

日期：2026-10-16。结论 **NOT_ACCEPTED**，确认B1/B2两项P2协议实施阻断，退回执行端按TASK-036-R1定点修正。Architect未修改实现、交付测试、既有指南或看板，没有子Agent、执行会话、跨会话指令或历史现场清理。最新接受状态仍TASK-035-R1；不发布TASK-036接受基线，不推进TASK-037。

评审证据根：`data/reviews/task036_gpt_20261016_190210/`。最终交付入口为 `data/human_initial_judgment_store_tests/task036_finalization_03/delivery.json`，最终业务观察为task036_run_03，四个最终执行端CLI为task036_final_cli_*。finalization_01/02及各dev/run过程均保留，不混作最终或本轮新执行。

## 1. 实读身份、范围与旧证据审核

四件长度/SHA从各自同一缓冲核对，与最终delivery一致：

- 存储模块25318 B / `ff25a5b5d82b76ca17d2edd745f287b9b816ba684d44ece83023109b5e6c194c`。
- 测试32446 B / `77182f1f509a4a0ab9e62b3840ab568589a0a16fbb93d825d996c8a8f6f2974f`。
- 新指南7305 B / `d6e98f8116b0d5df2b3a646490ea8f65490836f7162dfd4bbb407b33d594c450`。
- 回执14468 B / `fda1e58b2790de7653c145601099cc8200dc43b70bbfa912595e42284d716e7c`。

最新接受基线166390项/SHA `63ba73224065bdcdf53538b58a23d966ab6469aed8cdf7330445846828005948`、TASK-036任务卡、冻结初判核心1.1、正式契约/生效登记/协议/案例和运行适配器逐项核对。生产模块仅十项标准库依赖、两个公开API，无CLI或运行接线。六件组件实读、自身源绑定、核心从绑定缓冲真实compile/exec及调用前再次确认的正常结构成立；十四项运行代码清单及16个API未接入新存储。

执行端最终68项检查、34条存储API、14条嵌套核心与expected_observations完整规范一致；七项台账逐项同缓冲长度/SHA实读。公开输入与核心实际消费输入分别三时点同引用闭合，父调用/实际增量一致；10份成功核心返回按协议独立重建后完整比较。公开34与嵌套14分列，不要求数量相等。producer的verify I/O观察中写事件0；junction原命令退出1、Access is denied按原文保留。见identity_audit.json、delivery_evidence_audit.json。

## 2. 本轮实际复验

执行新的verify_current.py：**11次公开原代码对象入口（save5、verify6）与9次冻结核心原代码对象入口**，完整输入/返回或异常、cause/context、实际引用三时点、文件场景前后及父调用保存在independent_observations.json。另有1次私有raw-chain诊断控制，明确不计入公开API或核心。

正常save/verify每次核心1，六份完整原字节、manifest与全部十一键返回由评审端另写构造核对。唯一运行变值为已存技术登记时间，独立校验其格式/来源；其他预期来自定稿输入、独立核心记录及六件真实源字节，不调用生产摘要/manifest构造helper。core八false、store九false、FILE/FP、原人类字段和独立技术时间闭合。见static_semantic_audit.json。

消费前非法entity bytes准确Blocked、核心1、叶未建；真实xb句柄写入expectations一半、flush后抛OSError，得到准确StoreError(stage=write.expectations.json)及原OSError原因链，半文件/有效failure保留。有效failure与半文件/缺manifest并存时verify优先拒绝，核心0且字节未变。

完整返回构建后给本轮judgment_result追加LF，本次verify按起始缓冲拒绝；撤销wrapper保留坏字节仍拒绝且不写failure；坏字节具名保全后仅精确恢复本轮单文件原件，verify重新成功。两个使用点的末次确认在完整返回构建及输入复测之后、return之前，正常顺序与固定原缓冲约束成立。上述通过不替代下面两项阻断。

## 3. 阻断与复现

**B1 / P2：原始路径链在检查前已被规范化消去。**

定位 `scripts/store_demo_human_initial_judgment.py:143` 的 `_resolve_leaf`，第149行先 `Path(os.path.abspath(value))`，再 `_reject_chain`。abspath会消去原文中的 `raw_alias/..`，违反任务卡§4要求的原始链检查；后续对resolved再检查也不能找回已消去的段。

本轮建立普通raw_alias目录和正常快照，原路径为 `data/human_initial_judgment_records/task036_review_190210/raw_alias/../normal`。仅对这个自建raw_alias的真实lstat返回套上合成reparse属性，其余lstat完全真实：公开verify实际成功、核心1，raw_alias的lstat命中0；直接把未规范化路径交给相同 `_reject_chain`，实际命中1并Blocked(field=record_dir)。原路径parts、abspath结果、命中数和完整公开返回均保留，证明公开入口漏掉了要求消费的原始段，而helper本身能拒绝它。

此为**合成元数据控制和源码证据**，不是物理junction动态通过或真实越界攻击证明。执行端物理junction权限拒绝按任务卡允许继续记null+原因，本轮没有重试创建物理链接；这个覆盖缺口不单列为阻断。B1要求在任何消去原始段的规范化之前完成原链检查，save与verify共用此入口，两个API都要修正。

**B2 / P2：失败诊断构建/技术时间异常顶替主存储异常。**

定位 `_write_failure` 第322—327行：failure对象的构建、`_chain`及 `_registration()`发生在保护secondary错误的try之外。任务卡§4要求失败诊断不能覆盖原主因，当前只保护了后续序列化/写入。

本轮新叶使用真实xb句柄半写并抛 `OSError("REVIEW_REAL_HALF_WRITE")`；第一次技术时间调用（成功manifest）真实返回，第二次（failure诊断）由本轮接缝抛 `OSError("REVIEW_DIAGNOSTIC_TECHNICAL_TIME_ERROR")`。公开save实际传播**裸OSError，stage=null**；应保留原HumanInitialJudgmentStoreError(stage=write.expectations.json)及其主OSError，并把诊断故障作为secondary信息。原主异常仍在context链中，但顶部异常类型/阶段及调用契约已被替换。半文件保留，failure未建，未返回成功；完整链见diagnostic_error_masks_primary。

这不要求在时钟失败时伪造技术时间或保证failure一定落盘；要求所有辅助诊断阶段失败均不顶替原主异常。现有“failure写句柄再抛OSError”测试只覆盖try内部，不能证明诊断构建阶段也受保护。

## 4. main收尾、过程和保护

四个本轮新进程经短profile launcher执行当前交付main，仅只读replay task036_run_03。实际退出码 **0/1/1/1**，stdout末次结果、summary、failures和返回码闭合；candidate-return审核失败，ledger/checks晚变更各命中1、加1个LF且末次bytes_ok=false。逐进程profile全部项目scripts函数，新增业务调用均实测0，回放源全部SHA未变；旧34/14不冒充新调用。坏字节保留，见closure_controls.json及新task036_review_cli_*_190210根。

按回执分列准备/五轮业务测试/早期finalization过程，未重跑旧套件或旧业务链。dev_01控制被guard拦截、缺失与未知混淆、run_02新只读guard拦截测试注入、早期引用问题均保留为过程；最终来源只取run_03/finalization_03。回执记载的新场景单文件rename继续作为过程说明保留，不据文件范围通过追认任何历史越界行为。额外合法闰日/±14人类正例仍null+未登记原文；真实业务/完整历史/运行层/AI等未执行项按范围写null，不由replay的0推论正确性。

局部定稿后仅一次最终全树保护扫描，以TASK-035-R1接受快照166390项核对：既有changed=[]，新missing/读取错误/范围外新增/身份漂移须0；所有新增逐个确切路径登记，无目录前缀豁免，扫描后自身元数据有限登记。最终实测值及本次**观察快照**身份见protection_result.json / review_result.json。范围通过不改变NOT_ACCEPTED结论。

139历史损失与当前baseline missing分列；27恢复、R5的326项、R1的19项、TASK-030具名41 B锁偏差及所有旧失败现场保持，不追认、恢复、重建、移动、清理或执行。本轮注入只作用于新建场景及本次载入模块的测试接缝，冻结源字节未改。

## 5. 修正卡与业务边界

发布 `docs/tasks/TASK-036-R1.md`，仅由执行端修正原始路径检查和诊断辅助失败保护并补有限对照；不由Architect直接实施，不推进TASK-037。新源码将使旧快照的store_file_sha256绑定失配，旧快照保持原状，不改manifest迁移/补签，修后验证另建新场景。

真实批准仍null、真实独立初判未保存、开发宿主0008、next/AI=false。物理快照/VALIDATED/本次技术审查均不批准真实批次、不认证身份、不证明完整历史或形成审计结论。看板由人类办理。
