# TASK-022 评审：未通过，转定点修正

日期：2026-10-13。结论：**NOT_ACCEPTED**。暂不关闭 TASK-022，不制定 Gate1 实施卡，转 `docs/tasks/TASK-022-R1.md`。原卡为 C 类存储设计；本轮发现的是既定设计的异常、路径拒绝和验证证据缺口，修正归 **B 类，DSH 执行**。GPT 未修改实现。

## 1. 文件身份与已确认成果

四份交付实读大小/SHA 均与交接一致：

- 存储模块 38015 字节：`d6b1bb2fc775e9079e723467bb9eb9c9cba8c9b6d7c8b16d4372bc9560192d9c`。
- 本任务测试 54793 字节：`5ab0b35a5efd182a69bc6bde0be718d417556dacaa88d201344007910eacc533`。
- 存储指南 13006 字节：`05e725c2a662a86c97eddf370bce5667b993089d0960e214a4adefc53109795b`。
- 回执 14370 字节：`0d0184565405a86bd941f2bd071d2d407a20b6b1b515815f91408d3fa170bca4`。

对执行端 `data/human_gate_decision_store_tests/task022_run_01/` 做有限实读：10 项台账与磁盘字节一致，summary/checks 均 106，38 个存储 API 记录与权威登记 ID 一致。这些成果保留；106/0 和终审故障 1/FAIL 属于执行端既有运行，本轮 GPT **没有重跑完整入口或终审故障入口**，不将它们称为 GPT 实测通过。

GPT 实际运行均在新评审根 `data/reviews/task022_gpt_20261013_222104/` 留证，对象目录只用新 `data/human_gate_decision_records/task022_gpt_20261013_222104/`。实际 11 次存储 API、7 次真实 P1 入口分四个作用域：基础反例 7/3、junction 反例 2/2、诊断反例 1/1、真实读取观察 1/1。公开保存及核验正常控制成功、调用者输入未变；没有运行宿主、控制器或业务建链。

## 2. B1：恢复未先校验对象类型，部分 I/O 与诊断原因链不符合协议

### 2.1 可解析错误对象泄漏原生异常

verify 在六份文件读入后，对 `decision_result.get("record")` 与 P1 `materials_body(materials)` 的调用早于类型检查。四例均为六文件齐全的独立副本，JSON 可解析，目标 payload 长度/SHA 及对应外层对象指纹已同步：

- decision_result 顶层分别为 `[]`、`null`、`7`：**原生 AttributeError**，没有 StoreBlocked 的文件/字段定位。
- materials 顶层为 `[]`：调用 `.items()` 产生 **原生 AttributeError**。

这是收到的协议对象类型错误，不是运行故障。应在使用 `.get`/`.items` 前定位拒绝，不能用捕获所有 AttributeError 的方式替代正确检查，也不能靠未同步的外层哈希提前拒绝来声称已覆盖。

### 2.2 最终实读错误泄漏 OSError

包装真实 `_read_bytes`，初始读取正常；只在同一文件第二次、最终确认读取时抛受控 OSError。注入命中 1、此前真实 P1 已执行，verify **泄漏原生 OSError**，未映射 StoreError(stage, reason)。这是异常映射探针，不声称发生了实际磁盘损坏。目录未写失败诊断。

### 2.3 已传播原因，落盘诊断却丢链

在新目录真实完成六文件写入、manifest 读回后，由既有接缝抛 RuntimeError sentinel。保存 API 正确抛 StoreError，传播链含 RuntimeError；但磁盘 `failure.json.cause_chain=[]`。通用 except 在建立 `raise ... from exc` 链之前就写了诊断，导致诊断与实际异常不一致。此反例真实 P1=1、真实 manifest 存在，完整现场保留。须先绑定原因再保存诊断，不能仅把 sentinel 放进 reason 字符串冒充完整链。

证据：`probe_records.json`、`probe_summary.json`、`diagnostic_probe_record.json`、`diagnostic_probe_summary.json`。

## 3. B2：先 resolve 再检查 reparse，真实 junction 被接受

`_resolve_leaf` 首先 `Path(target).resolve()`，随后只检查解析后路径的祖先。原始路径中的 junction 已被消去；允许根本身也未纳入原始路径检查。

GPT 在本轮新记录根内建立真实 Windows junction：`junction_alias` → 同根 `junction_target`。`os.lstat`/模块自身检查均确认它是 reparse 点，解析结果与目标相等。两者都在本轮新根内，不指向旧证据或外部目录；创建时环境先拒绝，权限获准后创建成功，未修改历史。

经 `junction_alias/new_record` 调用：

- 保存 **成功**，在真实 target 下建立六文件记录。
- 再经同一 junction 路径核验 **成功**。

两次分别真实 P1=1，均应按原卡 §4 的明确拒绝要求 Blocked。只证明“解析后仍在允许根内”不能替代“不经 reparse 路径”。证据在 `junction_probe_records.json` / `junction_probe_summary.json`；junction 和现场保留，不删除来凑通过。

修正应检查原始路径及已存在祖先，再核对解析后的严格后代关系；不得放宽允许根或接受链接。固定文件应是正常文件，不能绕过目录路径检查去读取链接载荷。无需引入锁服务或声称抵御所有返回后的竞态。

## 4. B3：真实调用、输入保真与读取观察的证据缺口

### 4.1 26 不是全部嵌套调用，5 次直接核心调用未登记

执行端的 38 个 API 记录中，`p1_nested_calls_observed` 合计为 **21**；全程核心代码帧计数为 **26**。差值 **5** 对应 G1 循环中直接调用 P1 生成对照返回。它们不在权威调用登记内，也没有独立完整输入/返回记录。因此不能将 26 全部称为“嵌套真实 P1”。

当前 API 记录只保存调用者输入的指纹，**0 条含完整输入对象快照**。正常 G1 通过再次调用 P1 得到 direct 对照，未保留保存过程那一次真实核心返回的独立观察，也未在测试端保留存储组件实际传入 P1 的四个引用及三时点指纹。记录文件中的四快照不能替代拒绝调用输入或真实消费引用的观察。

需要分列存储 API、嵌套核心、测试直接核心；所有真实调用完整登记。对进入真实 P1 的对象和返回做只读观察，不二次调用核心冒充第一次返回，不修改输入/返回，也不在 I/O 守卫内写证据。

### 4.2 I/O 观察没有捕获实际读取

现有 guard 包装 builtins.open 与 os.open/read/write/close，却没有覆盖 Path.read_bytes 使用的 `io.open`。既有 io_observations 的全部操作只有 os.open/write/close 与 MARK：**读取/open 事件为 0**。因此 G5-06 的“只读取允许路径”主要检查的是写入 os.open，不能支持回执的实读观察声明。

GPT 在正常只读 verify 上包装真实 `io.open`，观察到 **20 次 rb 打开**，API 正常返回、P1=1。应把实际读取通道纳入有限观察，并分读/写记录；限制到本轮新目录与规定的固定组件文件，不以宽泛目录前缀作证据豁免。现有守卫 socket/子进程命中0与静态无宿主导入检查保留，不把本缺口扩展成未发生的联网问题。

原“保存末次消费后”探针挂在 manifest 读回之后，后面还消费组件绑定；现有 I/O 日志又未记录读取，故不能声称已观察到最后消费。补测时先观察实际必要消费次序，再在真实最后消费返回原值之后单次改 LF，保持原来的最终字节确认要求。

证据：`evidence_audit.json`、`read_observation.json`。正常台账10项闭合和38个存储 API ID闭合不撤销；缺口在真实核心调用和读取观察覆盖。

## 5. 非阻断事项与范围处理

- os.open 的 O_CREAT|O_EXCL|O_BINARY 加显式字节写入具有原卡 xb 的独占语义，本轮不因 API 表面写法不同阻断，也不要求改用文本 writer。
- 生产组件额外硬编码协议/案例/宿主/控制器冻结哈希，当前不导入它们，未导致本轮正常控制失败。但这会让后续宿主接线改变代码后连新快照也无法保存，超出原定四项 component_bindings 职责。R1 可同步将这些身份核对保留在测试/保护层，生产运行仅绑定原卡四组件；不改 P1 run_binding 语义。这是消除额外耦合，不是开放 Gate。
- 冒烟临时数据删除、看板补建，以及故障记录根名 `final_audit_fault_suite` 不符合原卡 task022_<唯一名> 约定，登记为流程偏差；不清理、不回写旧回执，也不因命名补跑旧入口。R1 统一新轮次命名。
- 不因以上事项改正式契约、重新征求人类 D1/D2/D3 或修改已验收 P1。

## 6. 保护与交接

GPT 本轮一次最终全树保护扫描，基线为 `task021_r2_gpt_20261013_214052/source_hashes_after.json`（133682 项，SHA `6241c96ba724e8a38696f46c16cf1edf0fab071229895950dc235f4325f07ba7`）。实扫 **134312 文件**：**changed=[]、missing=[]、读取错误=[]、范围外新增=[]**。执行端四交付/八个显式产物根、前轮两个自指元数据、本轮评审/记录路径分别按确切名单分类；固定故障根的命名偏差另记，不作前缀豁免。新 junction 的别名和目标均限本轮目录，文件按实际遍历行为登记、链接未删除。扫描后仅有限刷新本轮评审产物身份，不再全树扫描。结果见 protection_result.json；新修正卡基线完整 SHA/项数及两个确切自指排除路径见 review_result.json。

转交 TASK-022-R1，先定点复核上述阻断，再一次正常存储入口及必要终审故障收尾。当前没有 GPT 完整106/0回归声明；避免在已确认阻断后重复运行整套。真实 Gate 批准仍 null、真实初判未保存、宿主0008、next=false、AI 未开放。本结论不批准任何批次。
