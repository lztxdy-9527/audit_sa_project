# TASK-018-R1：导出/离线核验收尾与来源身份闭合

日期：2026-10-13。依据 `docs/reviews/REVIEW_TASK_018.md`。只修两项实现阻断B1/B2及E1对应证据收尾；原TASK-018开发态、固定22来源/24 payload/25文件、只读/确定性/无0009/真实批准null/AI不允许等继续有效。

## 1. 允许路径与冻结

仅允许修改：

- `scripts/export_demo_review_bundle.py`，起点 `baea8fd1ff9c4092aca2e120233bbff960545fc9799d8b33156c46c10147dc44`。
- `tests/test_export_demo_review_bundle.py`，起点 `7b385bd6ebffb5495b565be44ed818766427e1ba8c52297c8479bc7326ac88f1`。
- `docs/DEV_REVIEW_BUNDLE_GUIDE.md`，起点 `08ba5545c6d66c03937e3e05bedbf56544b19935d2f762e0f1a3ad0bb91e1f91`，只更新受影响说明，非必改。

只新增 `docs/EXEC_REPORT_018_R1.md`、本轮全新 `data/review_bundle_tests/task018r1_<唯一>/` 和 `data/review_bundles/task018r1_<唯一>/`。**不新建batches或SQLite，不重建上游链。** 只读复用 `data/batches/task018_run_06/c06b` 及其宿主推导的外置DB，所有故意变更仅作用于本轮新输出或隔离副本。

其他所有既有文件/现场冻结，包括宿主 `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`、控制器/全部纯核心/SQL/旧测试/指南/原卡/回执/评审、本卡及交付包。不得迁移、补签、覆盖、删除或清理历史，不安装依赖、不初始化Git、不新增通用框架。

正确保护基线 `data/reviews/task018_gpt_20261013_051328/source_hashes_after.json`，文件哈希/项数见同目录review_result.json。它冻结本轮未通过交付；changed只允许上述三个既有文件，missing=[]、读取错误0。一次完整扫描复用，不能文档写后再扫全树；仅有限刷新本轮新增产物身份。

## 2. B1：在最后必要消费后核验实际字节

GPT已复现：manifest真实writer写后读回并返回原结果后，只给README追加LF，本次export仍成功，随后的verify1；离线verify完成24份字节检查后，在最后record JSON读取返回原对象后追加LF，本次仍成功，撤销wrapper后CLI1。

导出：manifest保存和读回、末次公开status、源/DB复测等必要消费之后，返回成功前，以初始待写缓冲/初始合法status绑定为预期，**实读全部24份payload及manifest**字节，确认长度/哈希或确切字节相等，并检查固定文件集合、无failure。manifest自身预期来自本次确切待写字节/writer返回，不内嵌自身哈希。保留22份来源/DB最后实读核验；不要将后来读数替换初始预期，不只检查文件名存在。

离线verify：必要JSON对象必须与该次通过manifest哈希检查的同一字节缓冲绑定；可缓存同缓冲解析对象，或后来对象读取时同时验证相应初始字节预期。返回成功前，在全部必要身份/对象/README消费之后作有限最终确认：25文件字节（manifest与初次同缓冲实读预期比较，24 payload与初始manifest预期比较）、固定集合、无failure。不能拿后来两次读数自比，也不能等下一次verify才拒绝。

复用现有小helper或直接步骤，不构建通用I/O/事务框架，不通过无限重复读取声称抵御任意时点并发变化。verify仍纯只读且只访问包内固定文件，不写failure、不读取源/DB/宿主；导出创建输出后的Blocked/Error仍只向本轮新输出写有效failure，半写/错误不能改报成功。

下文“最后必需消费”指生成/核对摘要或身份对象所需的数据消费，不包括最终纯字节确认本身；不在最后一个字节确认已经结束之后再注入并要求无限追加检查。

## 3. B2：包内来源/身份关系必须一致

GPT四个格式合法反例均错误成功：manifest.packet_file_sha256与实际packet不同；复制项source_initial_file_sha256与历史status/实际复制件不同；manifest声明的0008.previous与实际0008/0007不同；manifest/host_status改为OTHER-BATCH且只更新status payload大小/SHA，但0008/record/submission仍c06b。

请明确核对以下必要关系，数据只来自本包内同缓冲对象和实际字节，**不重写宿主全套协议、不调用冻结核心作复算**：

- 22复制件的actual SHA、payload.file_sha256、source_initial_file_sha256、历史status固定映射的对应文件SHA必须一致；路径仍由固定白名单决定，不跟随清单任意路径。可复用纯映射helper，不借此调用宿主。
- manifest的packet_file_sha256、record_file_sha256、checkpoint_0008_file_sha256、database_sha256等既有来源字段，与对应实际payload/历史status声明一致；对象规范指纹仍按packet/record实际规范JSON单独核对。host代码/绑定和版本身份与包内host_manifest/status/0008已有声明对应，不能只验证64位格式。
- manifest.source_batch.batch_id、manifest.batch_id、host_status.batch_id、host_manifest及0008.batch_id、record.source.batch_id、record.simulated_initial_judgment.batch_id与submission.batch_id同属一批次；record/source/submission/0008.operation声明的packet指纹与实际packet一致。
- manifest.checkpoint_0008.previous_file_sha256等声明与实际0008对应；实际0008.previous_file_sha256等于包内0007实际文件SHA；0008.operation身份/packet/record指纹与manifest及实际材料一致，workflow保持与0007严格规范等值。
- 固定开发/模拟/正式契约未建立/真实批准null/next与AI严格false的边界在manifest、历史status、0008和record间一致。已声明为严格整数的revision/计数等使用严格类型，避免bool/float通过相等比较；非法结构应为可定位的Blocked，运行/I-O仍为Error并保留cause。

只核对现有字段及必要身份关系，不新造事件、签名、认证、审批或业务判断，不改packet/record。COPIED_BYTES_ONLY含义继续限定包内一致性，不证明来源业务真实性或真实身份；这是避免自相矛盾，并非加入外部安全保证。

## 4. E1：真实直接调用登记与必要观察

交付status_of直接运行宿主，G1/G6未登记完整返回；GPT实测宿主代码帧1、API/registry增量0。修正共享的直接宿主读取，让每次测试显式公开API调用均登记完整实际返回或异常；不要额外再调用一次补记录。工具内部嵌套status观察与测试直接宿主调用分列，不能用“API条数=内部status次数”的错误等式。

原g2_missing_batch实际上被工具is_dir前置拒绝，宿主代码帧0。保留它作为“工具前置拒绝”，另做一次已登记的真实HOST.inspect_dev_batch缺失批次调用，捕获真实WorkflowHostBlocked及完整链，确认宿主确实进入；无须新建任何批次或伪造空现场。

R1入口实际运行registry/引用双向核验、逐文件exists+SHA、完整异常/traceback链、仅单删审核副本一条registry的隔离自测、正确本轮保护及停止点；全部进入正式failures。missing/unregistered必须来自已执行检查，未测为null/not_executed。观察器绑定实际使用的模块/代码帧，不观察另一个同名模块，不以已登记列表证明所有直接调用完整。

新回执同时澄清：原21条“协议阻断”是18 Blocked+3 Error；3个failure_only目录实际是保留payload/半写/manifest的失败现场，不是只含failure.json。旧回执/现场不回写、不清理。

## 5. 有界定点入口

新增明确 `--only r1`。默认旧入口可保留但本轮不运行完整七组、smoke、MAIN/零条、源晚变更、真实writer故障或历史入口。定点模式不自动调用build_c06b_batch，仅只读复用§1批次。

1. **一个正常包**：用最终工具真实export一次，保存22份来源初始绑定/实际复制字节和真实status返回；正常verify/新进程CLI0。六个真实下游抛错守卫命中0，实际宿主公开status观察与登记scope对应；包25文件/24 payload、C06b1条R02、判断原文和开发边界不变。以后反例复用该包的隔离副本，不重复正常建链。
2. **导出收尾两个有限目标**：各用一个新输出，在真实manifest保存/读回之后、最后一次来源/DB必需数据消费返回原缓冲之后，对README.md及manifest.json分别追加LF（不改内存/不同步哈希）。先无注入观察真实消费位置，再用最小wrapper在该点注入；实现调整时选择实际等价消费点，不在最终纯字节确认之后注入，也不能在早期writer读回就制造提前拒绝。两例本次即Blocked1、消息指出目标、新输出failure有效；撤销wrapper后CLI verify1，原源/DB/正常包不变。明确wrapper调用了真实writer/reader并返回其原值，此处不声称执行新的writer故障分支。
3. **离线最后消费反例**：只在正常包隔离副本，在最后必需record JSON/缓冲读取返回真实原对象之后为该文件追加LF，不同步哈希。若改为同缓冲缓存，则定位该文件实际缓冲消费读取点；本次verify即Blocked1，撤销wrapper后CLI1，verify全程不写failure或其他文件，正常原包不变。不能沿用已删除helper或假定全局第N次；以本轮无注入观察为准。
4. **四个来源/身份反例**：按§3/GPT复现各独立副本，候选始终可解析、25固定文件及24清单齐全；前三个只改合法64位声明，第四个仅更新候选status的payload大小/SHA，保持c06b的record/checkpoint/submission未改以证明跨文件绑定。均本次Blocked1且指向矛盾字段，不因外层哈希没同步提前拒绝。必要时只增加极少严格类型对照，不扩张为全协议穷举。
5. **登记与前提观察**：一个正常直接宿主status及一个真实缺失批次status均真实登记；工具缺失批次导出前置拒绝另列、实际嵌套宿主0。所有本轮API/CLI和测试注入/实际观察scope分清，计数按现场导出。无需为此复跑原G1/G6或新建业务链。
6. **最终证据/保护**：实际入口执行E1收尾，保护只允许§1文件changed、missing=[]/读取错误0；原源37文件/DB/0001—0008及正常包均核对字节不变，无0009，真实批准null、next=false、AI=false。先小样与必要负向，再在全新最终容器一次跑定点入口；局部错误定点修复，过程容器保留。

原_write_exclusive真实writer半写/完整后sentinel的保存/诊断方法本轮不要求修改或重跑；若实现没有触及该路径，只引用原现场并明确“读取证据，未重跑”。如确有影响再补受影响单场景，不能默认重跑整组和上游。

## 6. 回执与停止

新回执提供写后完整SHA、实际定点命令/退出、B1/B2/E1关闭证据、真实观察点/命中、完整返回/异常与CLI原文、来源/DB/旧链保护、注册/台账/隔离自测/最终failures、正确保护基线身份与一次扫描结果、过程失败及未执行项。列测试证据/导出两条新绝对根和使用的只读源/DB路径；自身哈希只在交接给出。

完成后停止本卡实施并交GPT验收，不做TASK-019/0009、真实判断/批准、正式契约或AI/LLM/网络/UI/ERP。GPT验收通过后再按持续授权制定下一任务；DSH关闭由人类操作。
