# TASK-024 整体验收：NOT_ACCEPTED

日期：2026-10-14。Architect / Reviewer：GPT。依据实际文件、TASK-024_DRAFT 和本轮独立复验；执行端交接与勾选清单不代替验收。六组阻断未关闭前，不制定 TASK-025，不接 Gate2/执行放行/真实初判。看板由人类操作。

## 1. 实际身份与证据范围

四份交付的实读 SHA/长度与本次交接一致：

- `scripts/record_demo_human_gate1.py`：`c002243ade1332e9e56ecd0a2b932a100c1d9f57191983f5689751e4f7fbd650`，53998 字节。
- `tests/test_record_demo_human_gate1.py`：`50f1268ea7ca8871eeb6405e5ac2ebec9c7d743e90a2868b493b35689d48df6c`，51059 字节。
- `docs/HUMAN_GATE1_DECISION_GUIDE.md`：`9c8f4409a1c964a65fe64139424795e635ecdf33a55f1724fec683fe9998c2fb`，10300 字节。
- `docs/EXEC_REPORT_024.md`：`1b5d73705e5e5c72e29953e9c7e1dd903c3c0c16e68cfcd9f209904950dcbdc4`，12658 字节。

证据根：`data/reviews/task024_gpt_20261014_050915/`。`finite_audit.json` 保存 13 项输入身份及交付时只读证据；`reviewed_inputs/` 保存本次读取的源码/任务卡/指南/回执副本。准备器、存储、P1、契约/生效登记、配置、宿主/控制器与上一验收基线一致。GPT 未修改实现或测试。

读取既有证据：`data/human_gate1_decision_tests/task024_run_05/` 的 summary/calls/protection。它自报 44/0、prepare 2/save 22/verify 13；本轮不把这些数称作 GPT 重新实测。

GPT 实际运行：`verify_current.py` 在全新 `task024_gpt_normal_20261014_050915` 调用当前完整测试入口；返回 0、43 项/0 失败。本环境没有成功建立 junction，测试跳过了该一个反例，故不能称 GPT 复跑了交接中的 44 项或重新验证了 junction。没有为此重复整套造样。正常路径及其余用例通过不消除下列独立反例。

独立代码帧观察：本层 prepare 12/save 21/verify 13，冻结 prepare 31、store.save 14/store.verify 8、真实 P1 22、scope 枚举 38、evidence_audit 4。各类分列，不要求不同层次数相等。`normal_core_observations.json` 保存这 22 次真实 P1 的输入和返回观察；profile 的 return=None 不单独证明异常类型，本评审不作这种推断。

## 2. B1：只读 verify 在已消费材料失效后仍返回成功

位置：实现 `_final_confirm_decision_request`、`_final_confirm_history`、`verify_human_gate1_decision` 收尾（约 1007、1074—1092 行）。verify 先核验整个历史，但收尾只比较目标事件八文件；没有确认全部历史、目标失败/集合变化，32 个来源确认后也还有必要消费。

用两个真实新事件，先无注入 verify 成功；包装真实 `_final_confirm_decision_request`，返回原值后各独立变更一次：

- 更早事件 `event_0001/context.json` 追加 LF：本次 verify 返回 VERIFIED；撤销 wrapper 后拒绝，恢复原件后成功。
- 当前源 `checks/quality_report.json` 追加 LF：本次 VERIFIED；撤销后拒绝（还误映射为 Error，见 B4），恢复后成功。
- 目标事件新增 `failure.json`：本次 VERIFIED；撤销后按失败事实拒绝，移除本轮故意注入的文件后成功。
- scope 新增空的 `unregistered_event/`：本次 VERIFIED；撤销后因事件不完整拒绝，移除本轮空目录后成功。

四个接缝均真实调用原函数、返回原值，注入命中各 1；未同步哈希。本轮只有新建的评审批次/记录被故意改变，撤销操作限这些隔离测试输入；旧证据没有修改。新增普通 stray.txt 被现有枚举正确拒绝，已作为对照登记，不能据此覆盖“新增目录仍成功”。只读 verify 自身没有写 failure。

证据：`probe_records.json`、`additional_probe_records.json`。修复须在最后必要消费之后确认全部已消费来源/历史/新事件及既定路径、集合、失败/锁状态，预期绑定初始读数/本次 writer，不刷新为候选磁盘；save 同样满足原卡收尾义务。这里要求有界收尾，不声称杜绝返回之后的所有并发变化。

## 3. B2：合法保存的事件可能不能恢复

位置：`_list_scope` 按名字排序，`_verify_history` 直接用枚举下标当 revision；`_read_event` 的历史 records 又直接用 revision 顺序。

两个独立正向反例：

1. 同 scope 先向 `z_first` 保存 revision 1，再向 `a_second` 保存 revision 2，均返回 RECORDED；随后 verify 把 `a_second` 当 revision 1，拒绝 `a_second.context.revision`。任务卡没有目录名必须编码 revision 的要求。
2. 目录名仍为 event_0001—0003：先 EV-0002/HOLD（批次 B），再 EV-0001/APPROVE（批次 A），再 EV-0003/REJECT（批次 B）。三次真实保存均成功；第三次恢复拒绝 `event_0003.snapshots/prior_history.json`。该快照由保存端按 event_id 排序为 0001、0002，而恢复端要求 revision 顺序 0002、0001。

第三份夹具已在任何使用前由 GPT 登记为纯测试输入：`registered_fixture_0003.json`，SHA `6c69c75cde41014fd8740b95d58b9e8a805bd30003fb14ac6f8fb40c93cf23c3`。它没有业务批准效力，可只读用于修复回归。

证据：`lex_*` 和 `event_order_*` 记录。必须按实际严格整数 revision 核验连续唯一并排定前缀；P1 records 在每一个前缀独立按原 event_id UTF-8 排序。两种顺序不得混用，不可通过限制目录名/事件 ID 或仅支持两条来规避。

## 4. B3：历史封套 schema/严格类型未闭合

位置：`_read_event`，特别是 context.request/source_batch_relative/snapshot_files/prior_events 的消费。多处用 Python 容器相等替代规范相等，未先完整核验嵌套 schema。

对真实两事件现场逐例修改较早事件，仅同步有关 context/receipt 和后继 prior_events 的字节哈希，避免外层哈希过早遮蔽；六份存储快照及记录均不改：

- 较早 `context.request={}`：目标第二事件 verify 仍成功。
- 较早 `context.source_batch_relative=7`：仍成功。
- 较早 `context.snapshot_files[0].byte_size` 整数改同值浮点数：仍成功。

证据：`additional_probe_records.json` 的三项 `history_*`，均为实际公开 verify 返回。浮点数与整数在 Python 中可相等，但 canonical JSON 不同。任务已要求完整六键 request、严格整数/封闭字段/路径关系；这不是新增业务规则。

修复需对所有已消费历史封套及其嵌套成员按既定 schema 严格核验，并把 request 与相应六快照的 materials/expectations、record/manifest 及代码/规则声明关系闭合；规范相等使用 canonical 字节。历史业务源仍不实读，不为修复新增全局发现/认证。

## 5. B4：公开异常边界与失败诊断不完整

位置：`_frozen_request` 429—446、公开 prepare 503—509、save 的通用异常分支、`_write_failure` 827—841。

实际反例：

- 从本轮正常批次复制出隔离样本，删必需 `gate1_packet.md`。公开 prepare 泄漏下游 `HumanGate1RequestBlocked`；公开 save 把同一协议拒绝包装成 `HumanGate1DecisionError(stage=prepare)`，并留下 `.gate1.lock`，没有建立事件。协议拒绝应保持本层 Blocked/field/reason，当前自锁应按既定无现场分支清理。
- 在真实 spec/loader 的 exec_module 接缝注入一次 ImportError：公开 prepare 泄漏原生 ImportError；缓存没有写入，撤销后正常。这类运行失败应本层 Error + 原因链。
- 包装真实 fdopen 写句柄，context 半写抛 OSError，然后失败诊断写入再抛第二个 OSError：两处各命中 1，最终 API 只有第一条 context 错误链，第二条诊断写失败被 `_write_failure` 吞掉，磁盘 failure 为 0 字节。必须保留主错误并明确报告诊断写失败。

作为正向定位，GPT 另跑一次真实 context writer 半写：进入原 `_write_exclusive` 的 OSError 分支，正确映射本层 Error，原 OSError 留在 API/失败诊断链；这一正常映射不代表双重失败已处理。

证据：`additional_probe_records.json`、`runtime_probe_records.json`。所有测试仅用本轮新路径。不得用“捕获一切后改为 Blocked”掩盖错误分类，也不得删锁/删现场凑成功。

## 6. E1：两项 writer 证据不满足原卡

位置：测试约 780—830 行；原卡 §8.6。

- `half_write` 替换整个 `_write_exclusive`，自建句柄写半段，然后直接抛 `HumanGate1DecisionError`。没有真实 OSError，没有执行原 writer 的错误映射分支；S10.1 也未核对原 OSError 链。
- `sentinel_write` 真实写 receipt 后追加 X，产生读回差异 Blocked；没有抛 sentinel 异常。它可以是额外“字节污染”测试，但不能充当“完整写后抛 sentinel”的 Error/原因链测试。

执行回执/交接把两者称真实 writer 两例并非可接受的证据等价。修复只需替换这两个测试方法及准确说明，生产 writer 已有单次真实半写正向证据，不要求另造 I/O 框架或重跑旧 store writer 历史套件。

## 7. E2：调用证据、内容审核与终审台账未闭合

位置：`submission_for` 135—149、`evidence_audit` 195—232、套件计数/收尾约 356—390、830—结束。

- `submission_for` 直接调用公开 prepare 不登记。本轮独立观察 prepare 12，calls/summary 只登记 2；因此“每次公开 API 完整登记”不成立。
- P1/冻结 prepare/scope 枚举/审核 helper 没有真实入口计数和完整观察的统一闭合。store 两个 wrapper 只计数，不保存对应真实输入/返回、原因链及 P1 新提交/历史复算的完整载荷。
- 对实际 normal calls 的一个完整返回改为 `{}`，保留 IDs/数量，真实 `evidence_audit` 仍 `ok=true`。证据 `audit_empty_return_probe.json` 明确这是隔离 helper 实测，**不是又跑了一个故障套件**。代码同样没有将首轮磁盘对象与终审前冻结的真实内存观察作完整 canonical 比较；在首轮读数前自洽替换就能成为新预期。
- 台账最后写出后没有读回审核。接收器 CLI 仅保存 stdout/stderr 尾部，内部 checker 的实际 started/退出及引用文件字节没有双向核验。本卡要求的完整证据不能由计数/截断输出代替。
- S1.3 用核心自己的 helper 复算，不能称独立算法核验；14/32 主要只看数量和某些内部相等，需用测试独立 canonical/字节读数核对实际清单及来源。

原“缺一条登记”故障可证明数量缺失检测，但不能证明完整载荷真实性。修复沿用本项目已验收的“真实观察定稿 → 独立深拷贝 → 同缓冲磁盘候选 → canonical 内容/入口/ID审核 → 字节确认 → 台账读回”模式，限定当前任务，不复制历史大套件。

## 8. 非阻断事项、保护与结论

旧回执 §5/§9 还残留 run_03 路径，`_write_failure` 注释仍写“八键”，以及已执行 junction 在 summary 的 not_executed 中仍为 null。这些文案/标签在新回执按实际范围更正，不回写旧回执，不单独要求旧场景回归。

本轮未运行 TASK-021/022/023 历史入口、宿主/控制器、标准化/DB/筛查/Gate2/真实初判/AI；没操作看板。未成功建立新的 junction，本轮不声称复验该项。没有任何真实批次批准，真实批准保持 null、宿主仍开发态 0008、next=false、AI=false。

GPT一次最终全树保护扫描：基线143274项，实扫146999文件；**既有文件 changed=[]、missing/读取错误/范围外新增均0**。执行端四份交付/明确过程根、前轮两个确切自指元数据和本轮评审/新测试/新批次/新记录根逐项登记，无目录前缀兜底；旧现场和junction保留。扫描后仅有限登记评审及元数据身份，不重新遍历项目树。修复起点 source_hashes_after.json 的完整SHA/项数/两个确切自指排除见同目录review_result.json，verdict=NOT_ACCEPTED。

结论：**TASK-024 NOT_ACCEPTED**。修复卡 `docs/tasks/TASK-024-R1_DRAFT.md`，**B 类：DSH 定点修复既定设计**。涉及已授权实现/证据错误，不能按 A 类由 GPT 随手修；若需要改冻结核心或本卡架构/范围，立即升级重新定界。原卡保持 in_review；本轮不生成下一阶段卡。
