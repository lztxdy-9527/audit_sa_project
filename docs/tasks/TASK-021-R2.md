# TASK-021-R2：历史记录跨字段合法性与终审失败传播

执行分类：**B类，DSH处理**。Architect/Reviewer：GPT；人类保留业务判断与真实批准。依据`docs/reviews/REVIEW_TASK_021_R1.md`。这是恢复既定协议的剩余修正，不进入P2。

## 1. 目标与保留成果

原12反例已正确拒绝、完整字段schema/真实入口观察/权威登记隔离/正常最终台账均已确认，保留不重开。只修：

- 历史record的quality_summary与decision组合、Gate2前序摘要自身关系。
- 测试最终validation_final非空时仍退出0/summary PASS的失败传播。

不改变API、schema/输出常量、材料算法、业务矩阵、14步、纯内存和false边界，不新增参数/历史全局发现/祖先图/磁盘核验。若实施发现必须改变上述边界，立即停止受影响处理，报告并升级C类；不得扩大B类范围继续。

## 2. 文件与保护范围

允许修改：

- `scripts/build_demo_human_gate_decision.py`，起点SHA `081f725e1374a51405a6cccdece30e8acf7eda234cf2cf531fe6ca6064e4f595`。
- `tests/test_build_demo_human_gate_decision.py`，起点SHA `37108ff863b53723974d0c32ecc65d0006cd6648c06f99648dbc8a8e6e6b2ded`。
- `docs/HUMAN_GATE_DECISION_GUIDE.md`，起点SHA `0839632e86f7df6a0809f860dfa68680c59b89a285fdecce6c75060ec94e4b5b`，仅必要能力/编号映射同步，非必改。

仅新增`docs/EXEC_REPORT_021_R2.md`与全新`data/human_gate_decision_tests/task021r2_<唯一名>/`（必要过程容器保留）。原R1回执SHA `194cc8e5e40e708d996d2411ef2c620fec377a030fdb22f4a514cb5822918daa`及所有旧容器/脚本/评审冻结，不执行旧容器中的工具、不覆盖现场。

保护基线：`data/reviews/task021_r1_gpt_20261013_204526/source_hashes_after.json`；先核验同目录`review_result.json`的清单SHA/项数及NOT_ACCEPTED。只按这两个确切路径单列自指排除，不豁免reviews目录。

正式契约`174a021b…40ad`、协议`68c931b3…3e76`、案例`bd1fc37d…d2a6`、D1/D2/D3、宿主/控制器/全部上游与历史产物冻结。不建batches/SQLite/审阅包/真实批准文件，不新增依赖/Git，不接真实数据、AI或终判。

## 3. 历史record自身关系（B1剩余）

### 3.1 质量与决定组合

对已提供历史完整record应用与合法输出一致的矩阵约束：

- quality_summary=OK且三计数0：APPROVE/HOLD/REJECT均可为合法历史。
- quality_summary=BLOCKED且结构/质量计数≥1、失败计数0：HOLD/REJECT可接受，APPROVE拒绝。
- quality_summary=FAILED：三种决定均不得作为成功MEMORY_VALIDATED历史record接受，即使失败计数≥1使“状态与计数”自身一致也必须拒绝。

保持已有状态/计数严格类型与自洽检查，不能仅新增对评审值的黑名单，也不能一律拒绝BLOCKED历史。错误field指向该历史record.decision或quality_summary.status等实际关系目标，原因清楚。

### 3.2 Gate2摘要与历史record的关系

历史record.gate为GATE2时，现有prior_gate1摘要必须符合合法输出的派生关系：gate为GATE1、decision为APPROVE、batch_id与**该历史record**批次一致、actor_kind为HUMAN_DECLARED；保留完整键/字符串/哈希检查。摘要event_id不得与该record自身event_id相同（事件不能自我充当前序）；无需扫描全局或要求祖先wrapper一定出现在所给历史范围内。

比较对象是该历史record，不是当前提交批次。合法其他批次Gate2历史、合法HOLD/REJECT历史继续接受；不得把当前Gate2的前序“同本批/同运行”等约束套给所有历史。Gate1的prior_gate1=null不变。

这些规则只核现有字段，不认证来源、不证明摘要对应的原始业务真实，不从哈希反推材料。

## 4. 最终审核失败必须支配测试结论（B2剩余）

当前收尾重建ledger_final后已真实计算validation_final；其missing/unregistered非空时，必须形成明确失败、非零返回与FAIL结论，不可只把错误写入ledger而继续PASS。保留已有正常最终字节闭合/summary计数刷新/入口观察/权威登记双向审核。

收尾方式由执行端选最小实现，避免无限“写审核→改文件→重新审核”循环；正常载荷定稿后检查，错误路径可用独立终审诊断或有界失败收尾，必须如实反映失败和实际文件情况。台账不内嵌自身SHA，不新增通用I/O框架。

新增**真实**收尾故障验证：调用真实最终ledger读取取得原字典后，只对本次新容器checks.json追加一个LF，不同步期望/不替换验证器。最后真实audit应发现该文件，入口必须非零且不能summary PASS/failures=[]。参照评审脚本的注入时机即可，不能只返回伪造的missing列表冒充实际字节反例，也不要求抵御函数返回后的外部变化。

正常控制和故障现场分开新目录，故障现场不恢复/清理凑成功；旧文件完全不动。

## 5. 最小验证与证据

先新增定点验证，全部通过后运行一次完整纯核心测试入口；不重复上游/业务/历史入口，不运行旧文档工具。

1. 复现评审8个新反例：其他批次完整历史BLOCKED+APPROVE；FAILED+三决定；Gate2历史摘要分别改为GATE2、HOLD、REJECT、错误批次。每例保持非目标部分合法、正确重算record/wrapper摘要，当前输入不变，实际Blocked到关系字段。
2. 历史正向对照：OK三决定、BLOCKED HOLD/REJECT、合法其他批次Gate2；补自我前序事件反例。其他批次/运行/契约历史不得被一律套当前前序条件拒绝。
3. 原14控制/反例仍全部满足；C-112—C-115实际运行绑定目标字段与C-116正常、原117设计映射、R1字段/schema/时间/纯内存/无别名/质量矩阵/内部Error原因链继续有效。可以复用当前入口，不从旧评审期望值硬编码跳过构造或只检查摘要。
4. 正常最终容器台账12项（或明确登记的最终载荷集合）实读一致，summary/checks/counts互相一致，真实入口=登记覆盖，权威登记隔离删副本一条调用必须由真实helper失败，原件通过。
5. 收尾故障真实字节注入命中1、最后audit确实发现checks.json、入口非零/FAIL、完整stdout/返回码/最终诊断留证，不修改核心或旧现场。该故障运行与正常完整回归分列，不能把故障运行称为正常347/0。

每次真实核心调用全部登记，完整输入/返回或异常/真实traceback/cause/context；前后同引用指纹不变。定点模式如未执行某审核，写null/not_executed。必要时使用小型辅助集中最终审核，但不引入新权限或证据链设计。

## 6. 有限记录、保护与停止点

子步编号偏移属于非阻断映射事项：冻结协议11f仍是运行绑定，R1实现注释11g表达同一目标；在新指南/回执明确语义对应，或仅调整注释标号，不为编号修改已关闭的实际校验顺序。summary中原117与新增维度编号分列计数。辅助文件台账隔离若保留“真实审核”声明，应调用实际audit，不硬编码original_passes；不影响已通过的权威调用登记隔离结论。旧回执不回写。

原R1两次扫描/看板补建顺序偏差登记即可，不回归、不清理。局部验证/正常完整入口/受影响故障验证完成、交付正文与新回执齐备后，才进行一次最终全树保护扫描；扫描后仅有限登记本轮产物/回执身份，不再改核心/测试/指南。

新回执提供本轮起点/写后SHA、B1/B2剩余逐项证据、调用与运行scope、正常/故障退出码、实际保护基线/changed/missing/错误/范围外新增、过程失败及未执行项。自身最终SHA只在交接消息提供，不写回自身。

完成后交GPT整体验收并停止本轮实施。通过前不制定/实施P2，不生成真实Gate批准、真实初判或0009，不开放AI。若需要改变架构或业务规则，立即停止相关B类处理并报告升级；人类D1/D2/D3与契约生效确认不重开。
