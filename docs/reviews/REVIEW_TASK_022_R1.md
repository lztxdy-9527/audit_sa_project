# TASK-022-R1 评审：前轮修正有效，加载错误与最终证据审核仍未闭合

日期：2026-10-13。结论：**NOT_ACCEPTED**，暂不关闭 TASK-022/R1，不推进 Gate1。转交 `docs/tasks/TASK-022-R2.md`，仍属 **B 类定点修正、DSH 执行**。GPT 未改实现；正式契约、P1、宿主和业务范围不变。

## 1. 最终身份与既有正常证据

四份交付的实际大小/SHA 与交接一致：

- 存储模块 40393 字节：`7b62e13f78e9ec5ee92887ea8685237e8e2f817d125f520863c3a74f95a1d46e`。
- 测试 76870 字节：`9d75b0e6e8ab9660e73fa34dc51103893dedcf8ad1aabde418b520af3d913dbd`。
- 指南 15835 字节：`a8c4c119eb802fd33107ca7904591cdc83af3efb5858c12c653e8be132609f6f`。
- 回执 14075 字节：`97fc9cf97a7cb3a5ef2f0777aac849a5c982e0c2a510c403ee1353d2b69530c4`。

有限实读执行端 `task022r1_run_01`：台账 **13 项全部与磁盘一致**；API47、嵌套核心24、直接核心0、入口观察24闭合；正常源证据含完整24项核心记录，读取观察已包含真实 io.open。执行端124/0和checks.json终审故障1/FAIL保留，不能与本轮GPT运行混称。

实际 API 分类为 **save22 / verify25**，不是交接及回执的26/21。这是分列数字错误，登记为非阻断文案事项；不否认47个总调用及24个真实核心入口。

## 2. GPT实际复验与已关闭部分

新评审根 `data/reviews/task022_r1_gpt_20261013_225622/`；所有新脚本由GPT本轮编写，没有执行旧容器工具。

独立定点 **11次存储API、4次真实P1**：正常保存/核验成功，输入不变；前轮decision_result=[]/null/7、materials=[]均准确StoreBlocked，目录不变；末次reader受控OSError映射为StoreError(final_read)且保留原因；manifest真实读回后的RuntimeError同时出现在API链与failure.json；真实已有junction经verify及保存调用均以reparse原因阻断、P1=0、目标字节不变。junction保存探针使用已存在叶目录并核对明确reparse原因，防止历史写入，未声称本轮新建链接或测试了一个不存在叶目录。前轮B2主体路径拒绝结合执行端原生新叶目录反例关闭。

原B1的四类型、末次读取、诊断链修正有效；原B3的真实核心包装观察、删除5次二次对照、读取通道和正常核心数量闭合也有效。保留这些成果，不重开P1算法、六文件协议或独占writer。

本轮另外实际执行一次**核心证据缺失故障套件**，24次真实P1，见第4节。因此GPT实际核心调用分为定点4与故障套件24；不是一次无注入124/0正常回归。没有重跑原checks.json终审故障、P1全套或业务历史链。

## 3. B1剩余：首次加载P1的I/O仍在错误边界之外

save和verify入口仍先执行 `core = _core()`，save在try之外，verify也没有加载映射。`load_frozen_p1_core`中的spec.loader.exec_module没有处理运行/I-O错误。

定点探针使用真实spec，仅在其loader执行位置抛受控OSError，命中1，当前尚未调用P1、尚未建叶目录：save **泄漏原生OSError**，而不是StoreError(stage,reason)+cause。这是加载映射注入，不声称实际P1文件缺失/损坏；未修改冻结模块字节。

TASK-022-R1 §2.2已要求完整I/O边界及save/core加载同类路径，故不能以末次read已映射概括成所有运行入口已完成。最小修正应将实际加载错误纳入结构化运行错误，保留cause，不把协议Blocked改成Error，不将未完整加载的模块作为正常缓存复用。

证据：`probe_records.json`、`probe_summary.json`。前轮5个原生消费/末次读取错误已经关闭，剩余仅此加载入口。

## 4. B3剩余：核心完整记录丢失，最后审核仍PASS

### 4.1 实际审核只看ID，且“核心磁盘审核”使用内存

`_core_audit`比较core_call_ids与API的nested_core_call_ids、入口计数，却不核对完整entries集合、每个entry的ID、声明total与完整载荷的一致关系。`core_disk_audit = _core_audit(core_registry, registry.records)`的两个对象均来自内存，不是磁盘读回；API登记另有真实磁盘审核。

有限隔离实测：读取正常core_call_registry和api_records，深拷贝后仅删除 `entries` 中完整core-024，保留24个ID/声明/入口计数。真实 `_core_audit`返回 **ok=true**，原件也true。原隔离删除的是call_ids，不能证明“登记ID存在但完整输入/返回记录已缺失”会被拒绝。

### 4.2 全新故障套件实际误报成功

GPT运行当前完整入口到全新 `data/human_gate_decision_store_tests/task022r1_gpt_fault_20261013_225622/`，记录根同名。本轮获准执行真实junction用例，链接及全部故障现场留存。

仅包装真实 `_core_audit`：当真实run_suite直接调用最终核心审核时，**在调用真实审核前**，从本轮磁盘core_call_registry.json删除一条完整entry，不改ID名单/声明total/入口计数，不改内存登记，不伪造审核返回。命中1，core-024完整输入/返回丢失，文件230148→216295字节。

实际结果：

- 磁盘完整entries **23**，IDs **24**，声明total和真实入口仍 **24**。
- 真实核心审核 **ok=true**；后续台账重新对已变更文件取摘要，validated.missing/unregistered均空。
- 套件打印 **124项检查、0失败**，summary **PASS**，failures **[]**，**返回0**。

这是缺失核心证据仍报告完整通过，影响验收有效性，必须阻断。与此前checks.json LF故障不同：那个最后字节审核仍有效，不需重开；此处缺的是核心登记内容关系与其磁盘绑定。不能仅把故障值列为黑名单，或在缺失后重建“新期望”掩盖现场。

证据：`core_evidence_fault.py`、`core_evidence_fault_result.json`、stdout原文和上述完整故障目录。脚本退出0表示已记录反例；套件返回0是被发现的错误，不能称预期非零通过。

## 5. B3剩余：核验输入快照与第三时点

正常47条API记录中25条为verify，全部 `inputs.payload_snapshots=null`，没有初始目录快照。回执称“record_dir+初始目录快照”与实际不符，也没有为不存在/不可读输入说明未取得状态。R1 §4.1明确要求的输入现场留证尚未完成。

P1包装器已记录真实进入引用ID及调用前/返回后指纹，但没有保留引用供API收尾计算第三时点；`references_unchanged`比较的是包装器局部引用，不能替代原卡要求的收尾指纹。修正可在测试观察层保留私有引用、API收尾后登记最终指纹；不改生产数据或核心算法、不再调用一次核心来补观察。

这些收尾项与第4节在同一B3范围修正，不扩展成新证据链设计。

## 6. 非阻断与保护

生产component_bindings已恢复原定四项，宿主/控制器额外固定值移至测试/保护层；这一耦合事项关闭。路径原生测试和I/O观察已有实际证据，不因辅助计数字段重复运行它们。save/verify26/21文案在新回执更正为实际22/25，旧回执不改；旧过程偏差不清理不补跑。

GPT 本轮一次最终全树保护扫描，基线为 `task022_gpt_20261013_222104/source_hashes_after.json`（134314项，SHA `999900f4d778ea79274bf748dd54c21c97d81edb15af87acb66ba4b5db754ec7`）。实扫 **135321 文件**：**changed恰为授权存储模块/测试/指南三项；范围外变化=[]、missing=[]、读取错误=[]、范围外新增=[]**。执行端新回执/六个证据根/五个记录根、前轮两个自指元数据及本轮评审/故障根按确切路径分别登记。junction不删除，别名和目标按真实遍历行为登记。扫描后仅有限刷新本轮评审身份，不再次全树扫描。详见protection_result.json；R2使用的完整基线SHA/项数及两个确切自指排除路径见review_result.json。

转交TASK-022-R2，先定点修复加载映射与核心完整载荷审核、输入观察收尾，再做必要的新入口验证。真实批准仍null、宿主0008、next=false、AI未开放；本评审不批准任何批次。
