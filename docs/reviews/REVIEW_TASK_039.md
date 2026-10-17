# TASK-039 独立验收

结论：**NOT_ACCEPTED**。存在一个协议摘要角色阻断B1；不实施保存/恢复，不推进TASK-040。执行端92项静态PASS及文件保护通过不能消除语义矛盾。定点修正卡为 `docs/tasks/TASK-039-R1_DRAFT.md`。

评审根 `data/reviews/task039_gpt_20261017_015556/`。最后接受基线仍TASK-038：168728项，SHA `e841d1caa03c0445246db76148551175cfa7ea2522fe21d1c5dd954d4d40dcb9`。本轮source_hashes_observed.json仅登记NOT_ACCEPTED现场，不发布新接受基线。以本轮一次最终保护结果及review_result正式发布身份。

## 1. 最终身份和实际范围

只用 `data/runtime_initial_judgment_recording_protocol_checks/task039_run_03/delivery.json` 为交付入口；run_01/02是保留过程证据。实读四件长度/SHA全部匹配：协议32071 B / `5091060d774eda05efd429010543220d9e7d25dd2777e0fb92f00ad68ed0634e`；案例21907 B / `1c69957c8476711819e8a290a6ad0b9d5936b3479ab6bf959c5dbba15b28f8f5`；checker22135 B / `500c520932c0efa9939e4d55142c7fb2fbe6e42f232a3f2d6d8dbd115257cab3`；回执10707 B / `3eba019fd5382cead506dbecb713d0e6da942b287905fc00d9fa279d0195f900`。

交付引用文件逐项读回与接受基线/登记一致，有限postscan读回22件也一致。适配器仍290568 B / ca1139…，初判core/store/history、正式契约/生效登记、旧协议/案例和人类夹具冻结。没有修改生产、交付、既有指南或原任务卡，没有创建业务运行/Gate/SQLite/初判记录或锁。见identity_audit.json。

## 2. B1：后缀分类与冻结字段语义冲突

协议 `RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md:197` 的字段值规则写：

> record_fingerprint及所有`*_fingerprint`/`*_sha256`分别是本次指定对象FP/文件FILE，不能因都为64hex互换。

这把SHA后缀归为文件FILE，与本协议直接继承的两个对象摘要冲突：

- `source_binding.registry_binding.run_binding_sha256 = FP(registry.run_binding)`。
- `context.prepared_request.request_sha256 = FP(prepared_request.request)`。

前者来自当前已接受登记，后者来自当前完整两键请求返回。冻结runtime源码明确用fingerprint(binding)/fingerprint(request)赋值；不是文件SHA。继承的packet_canonical_sha256、normalized/screening/crosscheck对象摘要也不能按名称改成FILE。

本轮只读已接受的TASK-038评审来源，对同一实际缓冲解析对象并独立复算：两字段都等于对应规范对象FP，且不同于其实际包含文件的SHA、也不同于C(object)+LF的SHA。完整数值/源路径/源FILE/源码行保存在semantic_counterexamples.json，业务调用0。此处是字段契约矛盾，不是计算核心故障，也不是以不同数值代替角色证明：字段语义先由冻结源码及协议来源确定，数值对照用于复现。

未来实施若照该通配句按文件摘要校验会拒绝合法登记/请求；若继续按原对象FP校验则违反该新值规则。不能让执行端自行猜测例外或用两个自报64hex相等掩盖。修正应按字段实际语义/来源列有限角色登记，明确对象SHA例外，并让静态检查覆盖它；禁止修改冻结组件迎合错误句子。

## 3. 静态main独立复验与检查边界

实际执行当前交付checker的真实__main__，输出到从未存在的 `data/runtime_initial_judgment_recording_protocol_checks/task039_review_015556/`：**92/92 PASS、退出0**。全部check记录与执行端定稿完整canonical相等，scope均STATIC_ONLY；五份新静态载荷、实际open记录和scripts原代码对象profile保存。实际生产函数入口0、业务导入0；不把未实施的保存/并发/句柄行为填作动态PASS。

checker当前只检查通用FILE/FP定义、关键条款锚点、schema形状及公式，没有交叉核对B1的字段角色，因此该矛盾仍能得到92 PASS。这正是静态结果的实际限制，不把PASS复述成架构验收。见actual_static_main.json、semantic_counterexamples.json及independent_result.json。

本轮补充对安装后的io.open/socket/Popen/datetime/import接口实际作受控调用，全部在真实操作前拒绝，未创建文件/进程/连接或加载生产模块；profile为0。首次辅助记录的guard_proof只是拒绝闭包直接调用，未当作实际API守卫证明；actual_guard_probe.json明确限定并补充了真实接口控制，原记录保留。checker本身的生产窗口无守卫命中。

## 4. 已完成的其他语义审核及非阻断澄清

独立逐段阅读全文、43个八栏符号案例及checker。除B1外，以下主要设计关系成立：六文件历史叶与三文件运行封装分开；锁在域外且跨运行同域共用；持锁后重新核验来源；store.save一次、核心内部一次；E1只由旧E0加本次manifest FILE；旧P0/expectations不写成H1；恢复先完整Hc含自身，不以Hc减自身回造旧历史；允许后来其他批次但旧引用/旧字节及当前材料必须一致；store成功而封装/确认/释放失败不返回运行成功。首报、准确异常分类、主/次错误和末次原字节支配外层结果已有明确义务。

正常公式保存history2、初判verify2n+1/core2n+2；恢复history1、初判verify/core各m，和冻结调用方式一致；Gate/fact图沿TASK-038，引用旧预测有接受结果及本会话上轮实际图的交叉依据，不称本轮新业务调用。十二键外层、七/十/八键三封装、十一键failure及九false边界与案例相互一致。

Windows句柄绑定释放有官方实现路径：CreateFileW定义CREATE_NEW和共享访问，SetFileInformationByHandle允许具DELETE权的指定句柄设置FileDispositionInfo。这支持协议可实现性的推断，**未证明当前文件系统/权限或真实释放完成**；本卡未开原生句柄或锁。[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)、[SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle)。不能把DELETE_ON_CLOSE设成失败也自动删除来替代本协议仅成功释放。

非阻断C1：RC-02写packet.finding_ids为空，但冻结packet实际字段为findings，finding_ids属于materials.fact_snapshot。修正卡允许顺带改成准确路径，零线索仍需完整人类提交的政策不变。没有其他要求执行端自行扩大修改的阻断。

## 5. 保护与后续

本轮局部定稿后一次最终全树扫描，以TASK-038接受快照为基线，要求既有changed=[]、新missing/范围外新增/读取错误/身份漂移0；全部执行与评审新增展开确切路径，无目录前缀豁免。扫描后仅有限确切自身元数据。实际扫描项数/SHA见protection_result/review_result/source_hashes_observed.json；保护通过也不代表语义接受。

139历史损失与本轮missing分开；27恢复、326历史越界、19命名偏差、TASK-03041 B锁及TASK-038/039旧现场保持，不追认、恢复/重建/清理或删移。没有操作看板或向执行会话发送指令。

TASK-039-R1只改本协议、符号案例和静态checker，新增修正回执/新静态根；B1角色规则修正并追加一个64hex正确但角色错误的符号/静态反例，C1准确路径顺带澄清。双基线保护、生产和全部旧现场冻结；交付后再次独立验收。TASK-040保存/恢复实施尚未发布。

动态保存/恢复/并发/真实句柄/物理junction/真实数据/强认证/AI/终判均null+未实施。真实批准null、真实独立初判未保存、开发宿主0008、next/AI=false。本次文件保护、静态PASS或NOT_ACCEPTED评审均不批准真实批次。
