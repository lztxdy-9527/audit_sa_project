# TASK-033-R1：事实上下文来源与必需结构修正

本指南是 TASK-033 原指南的定点补充，不替换旧文档。实现版本为 `TASK-033-R1-runtime-gate1-1.0`。TASK-033 尚待 Architect 整体验收，最后接受基线仍为 TASK-032；本指南及测试不批准任何真实批次。

## 1. 接口与停止点

原十六公开 API、参数、成功协议与固定文件集合不变。`run_gate2_fact_packet` 仍真实调用一次冻结 `build_fact_packet`，其内部 renderer 一次；`inspect_gate2_fact_packet` 只在结构与来源校验完成后调用一次冻结 renderer，不重建事实或运行 SQL/独立复算/标准化/装载/决定保存。

生产变更仅限 `_validate_fact_context_033`、`_validate_fact_packet_033`、四个私有小 helper 及实现版本常量。冻结事实核心、Markdown 模板、BANNER、LIMITS、其他阶段均未修改。事实卡由冻结核心生成，本运行层只核对既有关系，不重算 R01—R04。

开发宿主仍为 0008，真实批准 null，真实独立初判未保存，next/AI=false；未实施 TASK-034、初判或 AI。

## 2. 按角色核对原记录

校验不再递归寻找偶然存在的 `status`，也不接受任意表中的一个 data/source/cells 三元组作为当前展示角色的依据。

- `context` 必须有 payable、payments、allocations、refunds；实际应付存在时还必须有 payable_supplier。其他键拒绝。
- payable 使用本条 finding.related_ids.payable_id 查 normalized.payables；payments/allocations 按本条原 ID 列表逐项比较长度、顺序、record_id 和对应表记录。
- refund/refund_allocation 只依据本条 evidence.related_refunds 的退款 ID，在 payments/allocations 各自表内核对。
- payable_supplier 来自实际应付记录的 supplier_id；每笔 payment.payee_supplier 来自该笔实际付款的 payee_supplier_id，分别核对 suppliers。
- entry 的 status、label、record_id 先验存在、类型及原值。实际 ID 存在必须 found，完整 data/source/cells 与那条实际记录严格 canonical 相等；确实为空或不在对应表才允许 not_found。found 必需的三对象及角色嵌套项不可缺，也不允许多余键。
- 应付缺失种类代码绑定原 finding.related_ids.missing_kind_code，中文标签绑定冻结展示口径。R03 卡的 missing_kind 同样核对，不自动变为“无问题”。

缺少 `facts.packet.findings[0].context.payable.status` 会直接产生 `RuntimeGate1Blocked`，field 为该完整路径，reason 明确缺失；不会进入 renderer 再发生 KeyError。真实 I/O 或冻结核心运行错误的既有 Error 分类和原因链保持。

私有 `_validate_fact_payable_033` 与整包校验共用同一应付角色核验。它无文件读写、无规则计算，仅用于原记录/原关联核对；不是新的公开 API 或恢复入口。

## 3. 定点复验入口

```powershell
.venv\Scripts\python.exe -B tests\test_runtime_fact_packet_r1.py --out-dir data\runtime_fact_packet_tests\task033_r1_<新名>
```

输出必须从未存在。正常入口只读复用 C06b 接收产物，按当前代码建立新的运行登记、夹具 Gate1/Gate2、装载、筛查、复算和底稿链。所有身份/决定时间/原因来自已登记合成夹具；不构成人类批次批准。

定点验证包含正常 build/inspect、完整真实返回与 JSON/Markdown 确切字节、原模板和 runtime_context、消费引用三时点、只读守卫、上游/DB 不变，以及四个隔离反例：

1. AP01 实际存在却改 not_found；测试侧真实 renderer 生成矛盾 Markdown，同步外层摘要后 inspect 仍须在 renderer 前拒绝。
2. 仅删 payable.status 并同步 packet 摘要；须精确字段 Blocked，renderer 0。
3. 删必需 payable；须字段 Blocked，renderer 0。
4. 串换两个实际存在的付款上下文；须按原关联 ID 拒绝，renderer 0。

候选具名保全后只精确恢复本轮三份原件；最终 inspect 成功且不写 failure，上游不变。测试侧候选生成 renderer、公开调用、嵌套核心和私有 helper 分列，不混称 inspect 的渲染次数。

## 4. 合法历史 R03 对照的范围

任务卡指定 C07b 的 packet/normalized/screening 三文件先与本轮评审登记、TASK-032 接受基线双重核对 SHA/长度，并完整保全实际字节。历史 packet 的 context 有旧版顶层 payee_supplier 布局，不能把它称为当前整包协议或运行凭证。

因此对照只在内存调用生产共用 `_validate_fact_payable_033`，传入该原始 payable entry、由原 normalized 建立的原表/原 ID 索引、该原 finding.related_ids，核对 `EMPTY_AP_ID`/null/not_found/原标签成立。完整历史输入单独保全，未迁移其布局、未建历史批准、未调用 build/renderer/SQL/复算，也未放宽当前 context 的封闭结构。

## 5. 可信收尾与保护

继续只读复用已验收短收尾：真实观察定稿成独立预期后不刷新；候选内容、台账同缓冲读回及末次原始字节确认支配 main 返回码与磁盘 summary/failures。四个新进程 replay 是同一次定稿观察的审核控制，不是新业务调用。

```powershell
.venv\Scripts\python.exe -B tests\test_runtime_fact_packet_r1.py --replay <本轮定稿观察根> --out-dir data\runtime_fact_packet_tests\task033_r1_<新名> --mutate none
```

可控模式为 none/candidate-return/ledger-late/checks-late；坏候选保留。外部代码观察独立确认 replay 的新增业务入口为 0。

最终一次全树扫描复用同一组读数报告两套口径：TASK-032 接受基线的累计改动，以及 TASK-033 未接受现场快照的本轮净改动；后者不能称接受基线。新增按确切路径列示，不以目录前缀豁免。139 历史损失、27 恢复项、326 越界项、19 命名偏差、TASK-030 锁目录偏差持续单列冻结。

原 TASK-033 半写、晚变更、分类映射和旧 CLI 证据本轮仅引用，未重跑；旧测试/指南/回执/坏现场不回写。完成后交独立验收，执行端不自行 ACCEPTED 或看板 done。
