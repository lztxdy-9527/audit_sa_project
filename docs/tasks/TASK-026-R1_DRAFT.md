# TASK-026-R1：补齐登记来源/恢复/末端与实际测试证据

日期：2026-10-15。**B类定点修复**，DSH实施、GPT验收。仅处理 `REVIEW_TASK_026.md` 的B1/B2/B3/E1，不新增功能、架构、案例体系或业务判断；错误分类需升级时停止受影响处理。

## 1. 范围与起点

只允许修改：

- `scripts/runtime_gate1.py`，`360be2f50d441f0c7d8c883704bba3da6c57b57920ef6e83ed4bce7b4db834a5` /43166 B。
- `tests/test_runtime_gate1_registry.py`，`f15681114d59b5a08ccf2d6643afb0a981828d3318d6f7382c8011fdc389f633` /39889 B。
- `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md`，`3928887b9f8fee78766aca488afd101143c5b30e0cb05e6a69c571d20ffce62e` /5932 B。

只新增 `docs/EXEC_REPORT_026_R1.md` 和三类本轮根：`data/runtime_gate1_registry_tests/task026r1_<round>/`、`data/batches/task026r1_<round>/`、`data/runtime/task026r1_<round>/`。不得创建决定记录/scope目录或SQLite目录；旧scope/输出/回执/扫描/探针全部只读，不删改、不迁移、不重试覆盖。

基线：`data/reviews/task026_gpt_20261015_024732/source_hashes_after.json`，项数/SHA/两个确切自指排除见同根review_result。保留原卡三个签名、13/14/32构成、全部版本/五键失败协议、六键请求、固定配置与false边界。冻结prepare/P1/store/契约/宿主/控制器不改。未来功能仍不在本卡。

先读原卡、评审及同根 `probe_summary.json`、`extra_api_records.json`、`late_source_result.json`；只读，不运行旧脚本覆盖证据。已通过正常形状/ID原文/无下游方向不重做协议设计。

## 2. B1：从操作起始固定读数，三API共同落实末端

build的来源八文件、全部项目消费材料和自身代码要取实际同缓冲字节/对象/长度/SHA；后续registry中的batch_files、input、清单与契约均闭合到这些读数。冻结prepare返回用于来源核验，但不能返回后重读已变化文件并把新值冒充同次预期。发现读数不同立即拒绝。

两份输出预期只来自本次待写缓冲及writer读回；read的预期取各自初始同缓冲。**不是最后再解析一次JSON即可通过**。全部对象消费/摘要复算/静态核验/返回对象构造先完成，之后一次有界原始字节确认：完整消费文件、两输出、固定目录集合、failure、路径reparse、scope状态。之后直接返回，不读取候选刷新预期或决定成功。

prepare覆盖readback、failure/未知项及全部当前来源；read同样有末端确认，不能只核对自身SHA。build失败创建前不产叶；创建后留五键有效failure及坏字节。read/prepare全程只读，失败不写诊断。

最低定点：build写后较早输出加LF、read初始读取后登记加LF、prepare来源核验后readback加LF/新增failure/未知项；再一次合法新接收批次在source核验后仅改input。均本次定位拒绝，撤销包装后的恢复行为与实际现场一致；正常对照成功。注入器包装真实函数并返回原值，按实际观察接缝，不硬猜第N次。不要求重建多套上游链。

## 3. B2：封闭schema、静态/派生关系及错误边界

先确认解析值类型再消费，不让registry=[]、code_manifest=[]产生原生AttributeError。完整核验13键及所有嵌套对象/名单条目：键集合、严格类型/枚举/常量、SHA fullmatch、非负严格整数、唯一升序、固定14/4/8集合；batch_id/时间/scope/note、config/input/contract/run_binding均按原卡。

把code/rules清单指纹、主文件SHA、配置/输入SHA、batch_files输入条目、registry/readback的正文/文件/长度/内层摘要逐项闭合。read虽不核验当前批次源，也必须核对本次代码/静态冻结字节；不接受外层摘要同步后内部仍不合法的登记。**不会要求read没有batch_dir却证明当前源未变**。

全部冻结13代码须独立预期；特别冻结prepare自身不在其FROZEN_PROJECT_SHA中，须在加载/使用缓存前以验收SHA实读核验。当前脚本自身从本次操作初始字节绑定并收尾实读；避免跨调用_SELF_BYTES缓存让预期落在旧操作。无需新配置或依赖。

枚举/lstat/stat/resolve/读写/末次确认的真实I/O失败映射RuntimeGate1Error(stage)+cause/context；缺件/坏协议/越界仍Blocked。不存在的计划路径允许FileNotFound的预期分支，其他lstat OSError不能吞成“不是reparse”。failure.cause_chain记录真实异常链，不只塞reason；诊断自身失败保留主/次错误，不覆盖坏现场。

最低反例沿用GPT已隔离构造：空note、contract_effective=false、空代码清单、错配置SHA、未知input键、float byte_size、内层SHA尾LF且同步全部外层摘要、顶层/嵌套非对象；一次真实枚举OSError。每项Blocked/具体字段或Error/stage正确；正常相同对象不同键序仍接受。选定这些维度即可，不扩成上百条矩阵。

## 4. B3：恢复原卡scope语义及逐级路径

scope_dir是Gate1记录根下**尚不存在**的计划技术路径；build/read/prepare只登记/核验引用，不创建scope、不依赖其存在，**已存在scope拒绝**。指南和测试反向断言同步改回。按原始绝对路径逐级检查（包括允许根、批次固定子目录/文件、项目文件、运行文件），resolve后复查，末端再核对集合/路径。原卡已要求，不新增目录协议。

`data/human_gate_decision_records/gate1/task026_run_01_scope`保留不动，在新回执说明已知来源和证据；若来源不可知就写不可确认，不编造创建者。本轮不得把它作为正常scope。旧task026登记因原scope规则/新脚本字节不能恢复时如实阻断，不迁移旧凭证。

最小正向用尚不存在路径且前后仍不存在；现有空scope/既有非空scope均拒绝。symlink与junction分开表述；环境可用时一项真实junction即可，不可用如实not_executed且不计成功。不要为路径测试在旧目录移动文件或清理旧junction。

## 5. E1：可信、可重复但小型的测试收尾

测试入口的out-dir必须在本卡证据根下、从未存在/空的新目录；由技术轮次派生**新**batch/runtime路径。删除固定task026_run_01和fresh_leaf递归删除旧现场的行为。旧测试不再执行；修正版在新轮次运行。失败停止保留现场，不删除/自动换轮次掩盖。

- 半写必须保留真实独占writer，仅包装它真实打开的句柄，一次write写入部分缓冲后抛OSError，使生产writer自身映射Error；记录预期/实际字节数、模式、命中和完整原因链。原写完后hook异常只列“写后受控异常”，不能补称真实半写。测试可包装真实reader/writer，不需要生产INJECTION_HOOKS回调；可删除现有测试回调设施。
- 在**实际运行路径**观察冻结prepare完整输入/真实返回或异常与次数；P1/store/下游入口0来自实际入口观察/正确模块守卫，不加载另一个无关module假守卫。接收器CLI记录命令、真实stdout/stderr/返回码；其内部checker观察范围和直接checker CLI分列，未观察记null+原因。
- 公开API使用小型call_id登记，落完整返回或异常/traceback/cause/field/stage、关键输入及前后源/输出文件读数。冻结prepare嵌套调用另列，不能和公开API条数混称。独立canonical/字段常量/文件SHA核对，不能照被测常量算所有期望。
- 内存实际观察定稿后固定独立预期，再一次写summary/checks/failures/API记录与文件台账；读回核验canonical内容、ID双向关系、各文件长度/SHA及最后字节漂移，不从磁盘候选重建期望。少量helper即可，不新建泛化审核框架/多层观察器。
- **真实收尾失败支配入口**：不管内存检查原先是否通过，磁盘审核不通过必须返回非零、summary=FAIL、failures非空并保留坏候选。只打印FAIL不算完成。用同次观察的独立副本删一条登记或改ok/结果载荷，经同一实际审核helper检出，并验证实际测试入口非零；无需为证据故障重新接收或建业务链。

完成正常/BLOCKED控制与本卡定点反例即可收尾，不按旧“91项”数量制造成功，不补跑历史核心大套件。不追加两种独立观察通道/对象身份认证等额外机制。

## 6. 最终交付

实施前建卡；冻结哈希先核对。局部错误局部处理，所有必要代码/指南/回执及本轮实测就绪后**一次最终全树扫描**：changed仅上述实际修改文件，missing/读取错误/范围外变化/新增0；新增逐条确切路径登记，不能用startswith目录前缀豁免。文件身份与空目录范围分别如实登记，旧R5 326项不变、不追认。

回执区分本轮真实执行、注入、旧证据读取和not_executed；更正旧半写/守卫/隔离审核声明只写新回执，不改旧文件。全部必要收尾完成再交GPT，未遇真实阻断不分轮留下扫描/回执。当前仅修本卡，禁止Gate1保存/有效批准/标准化/DB/Gate2/真实初判/0009/AI/终判；看板done和真实批准由人类作出。
