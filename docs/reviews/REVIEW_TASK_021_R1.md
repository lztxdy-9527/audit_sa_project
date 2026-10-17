# TASK-021-R1 评审：未通过，原修正有效但仍有跨字段合法性与终审失败传播缺口

日期：2026-10-13。结论：**NOT_ACCEPTED**。任务执行分类：**B类**。不关闭TASK-021/R1，不推进P2；转交TASK-021-R2。这里恢复既定协议的实现约束，不变更架构，不升级为C类；若后续必须改变协议/API/链路，须立即停止受影响处理并升级，不扩大本卡范围。

## 1. GPT实际复核范围与已关闭部分

四份交付的写后SHA/大小均与交接一致；详细实读结果见`data/reviews/task021_r1_gpt_20261013_204526/evidence_audit.json`。

实际运行独立`targeted_probes.py`，真实公开核心入口观察 **25=登记25**，全部输入未变。原评审14个控制/反例全部满足期望：两项正常返回、原12个非法输入正确Blocked。这确认原B1的字段缺层修复有效，不再重开这些问题。

新增历史控制与反例中，合法BLOCKED/HOLD、BLOCKED/REJECT、合法Gate2历史均成功；**8个不能由合法核心生成的历史记录仍成功**，见第2节。完整输入/返回/异常与入口观察在同根`probe_records.json`、`probe_summary.json`。

对交付正常容器`task021r1_run_02`做有限实读：台账12项全部与最终磁盘长度/SHA一致，missing/changed/unregistered为空；summary与checks都是347，183个API记录与权威登记ID一致。真实入口观察和权威登记隔离已实现，原B2相关缺口关闭；读既有183观察声明与本评审实际运行分列。

另外真实执行一次当前完整测试入口的**定点收尾故障运行**（183次核心调用/入口观察），只在新评审输出目录注入一次字节变化，复现终审失败仍报PASS，见第3节。本轮不是未注入完整回归通过：正常347/0来自执行端既有证据，GPT实际完整入口运行带有明确故障。

GPT本轮实际核心调用为25个定点调用及183个故障运行调用，两个作用域分别留证。不运行宿主/控制器/历史业务链，不修改实现或旧证据。

## 2. B1剩余：历史record自身合法性漏了跨字段关系

依据：协议§12决定矩阵、§14记录派生来源；TASK-021-R1 §3.2要求一般历史“自身协议合法”，而不是仅字段和计数各自合法。

### 2.1 质量与决定未联动

`_validate_record_quality_boundaries`第716—744行检查status和计数自洽，`_validate_record_full`第747—754行未将record.decision与quality_summary联动。第13步矩阵只应用于本次materials/submission，没有应用到已提供历史记录。

四例均使用其他批次的完整历史record；前序材料按相应quality列表正确构造/重算材料指纹，记录计数由列表长度派生，外层wrapper指纹正确，当前输入保持正常BASE1，不靠旧摘要或同批次重复遮蔽：

- BLOCKED、structural_blockers_count=1、verification_failures_count=0，decision=APPROVE → **实际成功，应拒绝**。
- FAILED、verification_failures_count=1，decision分别APPROVE/HOLD/REJECT → **3例均成功，应全部拒绝**。

这些record声称HUMAN_GATE_DECISION_MEMORY_VALIDATED，却不能由第13步合法生成。允许合法历史HOLD/REJECT、其他批次，并不允许历史中的非法APPROVE或FAILED成功记录。不能为处理此问题而一律拒绝BLOCKED历史；本评审BLOCKED/HOLD与REJECT正向均成功。

### 2.2 Gate2的prior_gate1摘要只核枚举，未核派生关系

`_validate_record_header`第659—670行对Gate2摘要允许gate=GATE1/GATE2、decision=APPROVE/HOLD/REJECT，并未核摘要batch_id与该历史record.batch_id相等。

以正常BASE2真实返回的合法Gate2 record为历史控制，在正常BASE1提交中可被接收。分别仅改历史record.prior_gate1的gate为GATE2、decision为HOLD、decision为REJECT、batch_id为OTHER-BATCH，正确重算wrapper指纹，**4例均成功，应拒绝对应摘要字段**。

协议§14明确该摘要从已通过§9的同批次Gate1 APPROVE wrapper派生；所以它应为Gate1/APPROVE/同批次/HUMAN_DECLARED。这只核现有字段自身关系，不要求查找全局祖先、认证来源或新增参数。

影响：核心在已知自相矛盾历史输入下仍构建成功记录。execution_allowed及六项边界仍false，没有实际放行，但历史合法性承诺未完成。

## 3. B2剩余：最后审核已发现错误，退出码与summary未传播失败

正常交付台账现已闭合；剩余问题在测试收尾错误路径。第1850行附近重建ledger_final后取validation_final并写入台账，却未将其非空问题加入failures、改变summary或返回码。

实际故障脚本`final_audit_fault.py`导入当前测试文件，包装真实`_ledger_from_disk`，**第三次真实读取返回原字典后**，只给新评审子目录checks.json追加一个LF。不修改期望字典、不替换验证器、不修改核心或旧文件。真实读数：84209→84210字节，注入命中1。

现场结果（`final_audit_fault_result.json`）：

- final ledger的真实`validated.missing=["checks.json"]`，即验证器确实检测到了字节不符。
- failures仍`[]`，summary.status仍`PASS`。
- 入口打印“347项检查，0失败”，**真实进程退出0**。
- 183次真实核心入口观察仍与登记相等，守卫命中0。

这是**失败误报成功**，不是单纯台账格式或文案问题，必须阻断。修正只需确保最后必要审核结果控制最终状态/退出码；不要求无限抵御返回后的外部篡改，也不引入通用I/O框架。

## 4. 非阻断记录与分级处置

- 实现把原11c—11i的子步编号重新分配，当前11g表示运行绑定、冻结协议11f表示运行绑定；API实际目标字段保持一致，主语义顺序仍为摘要、身份、契约、运行、质量、闭合。本轮不因标签单独阻断，也不据此认定架构变化。新回执/指南须明确映射，保持冻结协议不变，避免同时声称实现11g与协议11f是同一个编号；不为编号重写已关闭的校验行为。
- summary.design_cases_mapped=168，包含原117设计编号及51个新增维度编号；此标签粒度在新回执分列说明即可，不修改旧现场。
- 文件台账隔离辅助函数目前只按删键/长度判断，不调用真实文件audit，不能宣称它独立验证了真实文件缺失路径。权威调用登记隔离已调用实际audit且原件通过，此辅助声明登记为非阻断；可在本次测试收尾同步改为真实helper审核，避免硬编码original_passes。
- 实际两次全树扫描与先扫描后修测试、看板补建顺序已披露，最终容器/哈希重新核验，登记非阻断流程偏差；不为此重做历史回归或清理现场。原产物均保留。
- 核心历史跨字段规则与终审失败传播均涉及验收有效性，归B类交DSH；不以“A类小改”为由由GPT扩大修改范围。本轮未发现需要改变业务规则的C类事项。

## 5. 保护与交接

本轮一次最终全树扫描使用`task021_gpt_20261013_195927/source_hashes_after.json`（133481项，SHA `c972ad8c660097adfb2bcad02b99545ca16358e7cc9c2e2cfdbc0368fd710f29`），实扫**133582文件**：**changed恰为本轮授权的核心/测试/指南三项；范围外变化=[]、missing=[]、读取错误=[]、范围外新增=[]**。结果在本评审根`protection_result.json`；扫描后只有限登记本轮评审产物，不重复全树扫描。

转交`docs/tasks/TASK-021-R2.md`。正式契约/D1-D3/冻结协议与案例不动，原12反例和正常台账成果保留；修复剩余历史关系与终审失败传播后再整体验收，暂不制定P2。
