# TASK-038 独立验收

结论：**ACCEPTED**，仅接受新运行profile及只读初判请求。正式发布以同根review_result和本轮一次最终保护扫描为准。执行端PASS/看板不是本结论依据，不批准真实批次。

评审根 `data/reviews/task038_gpt_20261017_003401/`；前置TASK-037接受快照168367项，SHA `155f0247e7a62f033c46f919c22925017bc3683d9913cfd1f8875c7c9cbcc75c`。交付入口 `data/runtime_initial_judgment_request_tests/task038_finalization_01/delivery.json`；最终代码身份链为task038_run_02，最终证据容器task038_run_03。没有修改生产、交付测试、既有指南或原任务卡。

## 1. 身份、授权与代码范围

四件身份实读匹配delivery：runtime 290568 B / SHA `ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a`；测试62539 B / `3b0732b138a31fadba7ec61505ad3216a4828c803da30ef5bb789e7560287f13`；指南7584 B / `d201d2e27c72a84b40dfbdf1a6a3fdf11b5b257871d73877cc6bce45c295ad1a`；回执13836 B / `926ab6925814aa1b78b27111bb52f4fdb2c8dc05d2dd905dd9671891aba4e567`。所有冻结输入与接受快照一致；原适配器264105 B缓冲匹配TASK-037接受SHA。见identity_audit.json与runtime_diff.patch。

与原件AST比对：既有十二个定义作有限新profile/域绑定/末次确认改动，未删旧定义；只有build_runtime_registry增加必填关键字，其余十五个原业务API签名不变。新增一个业务API，合计十七；canonical/fingerprint/self_sha等技术工具不冒充业务API。清单十七、registry十四键、Gate1三十八材料均有实际完整独立预期及源FILE复算。新增registry单一顶层键initial_judgment_history，其内恰两字段；不是新增两个顶层键。

history异常映射修正的额外最终链有人类直接授权，独立记录SHA `fcd6db6bfcfce9213e346ed5d5c7377d6c1d5cce6e7e241dd41e80d3b2bc8fab`。开发链task038_run_01的代码SHA为 `d7b107ad79ded67d9d7727cc1a4668726ede364a657b75e96438bfc71647fb76`；最终链task038_run_02绑定ca1139…，二者明确不同且原件保留，不把旧凭证改新。两条执行链各自五个计算核心一次，不能说整卡只运行一次；本轮评审另建一条必要小样链，下文单列。

## 2. 源码与协议结论

逐段阅读新增入口和所有改动。三新代码及协议/案例以独立冻结SHA实读核对；namespace原串/UTF-8/路径链/既存后代/无交叠先验检查，登记绑定域而不固定增长名单。真实registry原文件FILE/长度加入Gate1共享材料；同步重算readback不能保留原批准。旧registry版本先明确拒绝，无迁移或默认域。

新入口固定来源开始缓冲，实际直接Gate1 verify/Gate2 verify/fact inspect/history各一次；保留既有真实只读嵌套。完整Gate记录、FILE/正文FP、事实artifacts/packet/Markdown和历史十二键返回与开始原件闭合。历史成功后同批拒绝，未收到人类event不编造提交。独立expectations先固定，完整candidate严格canonical比较，返回先深拷贝构建，全部原字节/路径/集合/failure/锁/自身/组件末次确认后直接return。

新入口无直接初判核心/save/SQL/标准化/装载/复算/事实build调用，不保存请求/failure/初判，不生成判断或人类时间。history按实际异常类型映射，Blocked加history.前缀，Error保留准确stage，reason/reasons/cause及已有secondary_errors不丢失。事实模板原提示、金额/ID口径及十false边界保持。

## 3. 两段交付证据审核

audit_delivery.py独立审核92项检查、40组外层API、912条完整原入口观察，全部与定稿内存expected载荷规范相等；三时点引用ID/完整快照/FP及登记、父嵌套关系闭合。33/690来自run_02原检查点，7/222为run_03接续进程新增；source.bin与原检查点逐字节相同，SHA `013e172e5dc19dd12d5aec8554c98412b4183a2a8243e20ab683ce69d189a952`。未把aggregate当本进程新增调用，未恢复不存在的旧checks/IO队列。

按冻结协议从输入独立重建**189份完整Gate核心返回、8份完整初判核心返回**，不是只复算候选自己的FP；再从实际八角色文件缓冲及录制时固定的历史名单独立重建空/非空**两份完整请求**，均一致。七项台账逐文件读回长度/FILE一致。最终profile与源码身份闭合，开发链不混用。

resume便捷normal_call_graph.json的counts仅含接续进程初始化过的角色，不能作完整计数来源。本评审从912条原观察重新归集完整正常图，与指南预测及本轮实际调用一致；这不是生产阻断。前段未落盘IO队列仍null，本轮自身完整守卫观察补充只读复验，不伪称恢复原队列。见delivery_evidence_audit.json、process_notes.json。

## 4. 本轮实际独立复验

交付最终历史域保留同批记录、坏引用/failure，事实根也保留failure，不能正常复用且不得清理。本轮仅在task038_review_003401具名运行/Gate/SQLite/历史根建立**一条**评审小样前提链，只读复用既有工作簿和登记Gate人类夹具；五个计算核心各一次，其余分支复用本链。原交付与历史现场未写入。

主复验21组外层调用、619条原入口观察：9次前提链setup、1次独立初判store setup save、11次新只读请求。history9、初判store.verify3/core4（其中setup核心1）；Gate store.save2/verify128/core130分别计数。正常请求直接四调用各1，Gate1 verify总6、Gate2总5、load inspect5、screen inspect2、crosscheck inspect1、facts inspect/render各1、Gate store.verify/P1各11、冻结准备器6。空域初判verify/core0；非空域真实逐叶1/1；同批拒绝前真实两叶2/2成功。setup保存的登记event1是合成夹具，非真实初判。

正常空/非空完整请求与调用前独立固定预期精确相等；八角色同缓冲FILE/长度及FP、全部原文/材料/预期/七键证据闭合。独立复建完整registry十四键/十七代码/三十八Gate1材料，原件和M一致。候选False→0及int→float均在initial.request拒绝。三时点输入和所有成功纯核心完整返回再次独立重建，父调用/原代码对象计数闭合。主复验写/网络/子进程/时钟守卫先证明，再生产窗口命中0、只读请求写事件0、禁止算法/save增量0。

最后消费后对本轮fact_packet.json真实追加LF，本次facts.fact_packet.json拒绝；撤销wrapper保留坏字节仍在facts.artifacts拒绝；坏字节具名保全，仅精确恢复本轮单文件后完整成功，未写failure。最后消费后追加完整event2叶，本次与保留新增叶后均拒绝旧空名单，不删除它凑成功；后续独立固定新名单再真实核验得到非空请求。所有旧源字节保持。

仅在真实history公开入口执行期间，实际manifest读取边界注入OSError；准确Error(stage=read)，链为RuntimeGate1Error→HistoryError→StoreError→OSError，reasons与原history一致，未被类型误判或诊断覆盖。此为本轮真实读取边界控制，不是把一个伪造成功返回当异常。

补充绑定探针用本轮真实alternate registry/readback副本先实际私有读取成功，只有域不同；随后用该实际读数的隔离视图让原Gate1在context.registry_file_sha256拒绝、核心0。自有物理源码副本的实际缓冲视图在初判业务核心前被registry.run_binding.code.file_sha256拒绝、核心0，未改生产源码。这些是明确副本接缝，不声称物理篡改冻结源码。成功记录见binding_controls_rerun.json。

该补充探针首次在三个调用及断言完成后，因捕获缓冲bytes未编码而观察JSON序列化失败，保留0 B的binding_controls.json。只修正新评审脚本的bytes编码并校验原自有副本一致后局部重跑；未重建链/改实现/重扫全树。首轮2次公开调用+1次私有读取，原帧计数未落盘为null；重跑2次公开+1次私有读取有完整观察。因此全轮实际外层公开调用25（主21+探针首轮2+重跑2），不把未保存帧台账补造为原证据。见process_notes.json。

## 5. 实际main与保护分类

四个新进程执行当前交付测试真实__main__ --replay：**0/1/1/1**，磁盘summary/failures/stdout相符；坏完整候选、末次ledger和checks漂移确实支配最外层非零。原函数代码对象profile实测新增业务调用**0/0/0/0**，源证据逐文件不变；旧912条观察不算新调用。见closure_controls.json。

执行端原唯一扫描scope_compliant=false，唯一unknown是本架构端人类授权记录；原扫描保留，后续只对该确切路径补充分类型、核同一SHA及有限postscan元数据，未重复全树。该记录确由此前本会话登记，人类授权原文及来源闭合，分类成立；不得把原始false说成原始PASS。

本轮局部定稿后另作一次独立最终全树扫描，以TASK-037接受基线为准；唯一允许既有changed为runtime_gate1.py，身份须等于本次交付ca1139…。所有执行与架构新增均逐确切路径登记，前次快照自身/review_result及授权记录单列，无目录前缀豁免。新missing/读取错误/范围外新增/身份漂移0才发布新接受基线；实际项数/SHA在本轮protection_result/review_result/source_hashes_after.json。

139历史损失与本轮baseline missing分开；27恢复、326历史越界、19命名偏差及TASK-03041 B锁保持，不追认历史偏差。没有恢复/重建/删移/清理历史现场或改看板。

## 6. 未执行、下一卡与业务边界

物理junction仍null+既有权限拒绝；未重试绕过。运行层初判save/verify、真实批次/真实初判、强认证、AI/终判、额外未提供人类时间正例及全时间删失证明均未执行，不计PASS。合成store setup不是运行层保存，也不改变真实状态。

发布TASK-039：先固定运行层初判保存/恢复协议及符号案例，解决历史叶六件限制、跨运行同域锁、加入自身后的历史时点、恢复自身与部分成功保留语义；只做文档/有限静态核对，尚不实施保存。这一步避免直接复用公开prepare时误拒绝自身或错误刷新旧历史FP。任务卡 `docs/tasks/TASK-039_DRAFT.md`；未创建执行会话或发送指令。

本次技术验收不批准真实批次、不认证身份。正式契约V1保持生效，开发宿主0008；真实批准null、真实人类独立初判未保存、next/AI=false，固定业务/整数分/原ID/主表与分摊分列/规则线索非结论保持。
