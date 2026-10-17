# TASK-039-R1：摘要角色契约定点修正

分类C，Architect限定范围、执行端修正文档/静态检查、Architect独立复验。本卡以 `data/reviews/task039_gpt_20261017_015556/review_result.json` 正式发布NOT_ACCEPTED及B1为生效依据。不是保存/恢复实施卡；不推进TASK-040，不批准真实批次。

## 1. 起点、身份及范围

先读REVIEW_TASK_039、同根semantic_counterexamples.json/independent_result和本轮source_hashes_observed.json。后者是NOT_ACCEPTED现场身份，不是接受基线。最后接受基线仍TASK-038的168728项/SHA `e841d1caa03c0445246db76148551175cfa7ea2522fe21d1c5dd954d4d40dcb9`；本轮观察快照SHA/项数从review_result实读，不猜测。

只允许修改三份TASK-039交付：

- `docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md`，实施前32071 B / SHA `5091060d774eda05efd429010543220d9e7d25dd2777e0fb92f00ad68ed0634e`。
- `docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_CASES_V1_DRAFT.md`，21907 B / `1c69957c8476711819e8a290a6ad0b9d5936b3479ab6bf959c5dbba15b28f8f5`。
- `tests/check_runtime_initial_judgment_recording_protocol.py`，22135 B / `500c520932c0efa9939e4d55142c7fb2fbe6e42f232a3f2d6d8dbd115257cab3`。

仅新增 `docs/EXEC_REPORT_039_R1.md` 及 `data/runtime_initial_judgment_recording_protocol_checks/task039_r1_<轮次>/` 中具名静态/交付/保护证据。原EXEC_REPORT_039、TASK-039任务卡/旧证据/所有review文件冻结。所有生产组件、正式契约/生效登记/旧协议/指南/测试/历史全部冻结；适配器仍290568 B / SHA `ca1139abbe18fc9cd2f1c3ad893f42b8b1b5b5bce28d1ed1216c0434309b6b9a`。不创建运行/Gate/SQLite/初判记录或锁，不加载/调用业务组件，不增加框架/依赖或网络执行能力。

Windows/PowerShell、Python -B。新增逐确切路径登记，根不是前缀豁免；不递归删移、不清理旧锁/探针/失败/过程输出。若需改生产、首报政策或扩大范围，停止该级处理并报告Architect。

## 2. 唯一阻断B1

协议§9写“所有`*_fingerprint`/`*_sha256`分别是本次指定对象FP/文件FILE”，把后缀当语义分类依据。这与当前直接继承对象冲突：

- `source_binding.registry_binding.run_binding_sha256 = FP(registry.run_binding)`，不是登记文件FILE。
- `context.prepared_request.request_sha256 = FP(prepared_request.request)`，不是请求/封装文件FILE。
- 继承的 `packet_canonical_sha256`、normalized/screening/crosscheck对象摘要也不能因SHA后缀改成文件摘要。

独立复证读取TASK-038已接受来源，以上两字段精确等于对象FP，且与对应文件SHA及C(object)+LF的SHA不同；没有调用业务核心。当前checker实际main仍92/92 PASS，说明其通用定义/锚点检查没有覆盖角色矛盾。详见semantic_counterexamples.json，不得以现有PASS消除B1。

## 3. 必须完成的定点修改

1. 删除后缀一律分类的规则。明确每字段按其已规定的语义和来源取FILE或FP，不能根据名称猜测或互换。给出本层新字段及上述直接继承字段的有限明确角色登记，至少包括record/binding/prior/history对象FP、registry/request/packet规范对象SHA例外、三封装/六快照/manifest的确切FILE；继承TASK-034/036/037/038完整对象继续沿冻结字段契约，不改其算法/常量/schema。所需少量角色说明可放机器块的设计元数据，业务键集合和成功/失败/锁形状保持。
2. 在现有43例后仅追加RC-44“64hex形状正确但摘要角色错”的隔离符号例：先满足形状、来源、名单与更早关系，FILE替换FP或反向替换仍须在指定关系检查拒绝，不靠格式检查掩盖。注明独立缓冲/固定时点、准确对象路径/阶段及不刷新预期；不给人类提交值，不运行业务。
3. 顺带澄清非阻断C1：RC-02的`packet.finding_ids`不是实际packet字段。改为 `materials.fact_snapshot.finding_ids` 或 `packet.findings` 的正确空列表关系，不改零线索仍需完整人类提交的政策。
4. 静态checker交叉核对该有限角色登记、协议/案例和冻结来源。至少实读已接受来源同一缓冲，分别计算对象FP与文件FILE，证明 `run_binding_sha256`/`request_sha256` 的确切角色；或用冻结AST明确的fingerprint调用一并闭合。不能只查“FILE/FP”词语、键数或两个候选自报摘要。增加一个纯内存角色表反例，使错误角色标注本次静态FAIL并影响实际main非零；不改落盘候选文档来注入，不执行业务模块。允许为44例更新原固定数量检查。

design_version统一改为 `TASK-039-recording-design-1.1`，协议/案例/checker一致；未来业务stage/status/版本常量、两个拟定签名、S1—S9/V1—V8、原八/九false边界和正常调用公式保持。不能借本修正重设保存、锁、恢复、历史时点或正式契约政策。

## 4. 有限验证与交付

只执行必要静态核对：四件身份、有限角色来源、44例、原机器schema/调用公式、角色错标的纯内存拒绝及实际main外层结果。正常checker新进程退出0；内存错误角色控制退出非零、summary/failures（若落盘）一致，使用实际审核结果而非注入标志直接判失败。引用旧样本/AST是只读，不算新核心调用。profile证明scripts原函数入口0、业务导入0；未执行的保存/恢复/并发/真实句柄/物理junction/AI等仍null+原因。

不用重跑历史业务矩阵或四组业务main replay，不新建业务前提链。原过程证据完整保留，不覆盖task039_run_01/02/03或本轮评审根。回执说明B1/C1改动和实际静态结果，原“92静态PASS但语义NOT_ACCEPTED”现场不得回写成通过。

局部定稿后一次最终全树保护扫描，同次对双口径出结果：相对本轮NOT_ACCEPTED观察快照仅上述三件可变；相对TASK-038接受基线原既有文件变化仍为0（这三件是TASK-039新增）。两基线missing/读取错误/范围外新增/身份漂移0，新增逐确切路径登记，前次观察快照自身/review_result有限元数据单列，无前缀豁免。扫描后仅有限自身元数据，不重扫全树。

139历史损失、27恢复、326越界、19命名偏差、TASK-03041 B锁及TASK-038/039全部旧现场保持，不追认、不恢复/重建/删移。交付停止待Architect独立验收，不实施下一卡、不改看板。真实批准null、真实初判未保存、开发宿主0008、next/AI=false；本修正及静态验收不批准任何批次。
