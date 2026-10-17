# TASK-024-R4 终审

日期：2026-10-14。结论：**NOT_ACCEPTED，原 B1 与八文件字节覆盖已关闭，仅剩测试侧 E2 的故障豁免作用范围。** 生产适配器不再派发修改；不进入 TASK-025。

## 1. 交付身份与范围

本次实读：

- `scripts/record_demo_human_gate1.py`：`d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9`，85064 字节。
- `tests/test_record_demo_human_gate1.py`：`0df0982f865d485625c39cdce1744e41158cc7410ee99d97fcd725d85187e55e`，170089 字节。
- `docs/EXEC_REPORT_024_R4.md`：`74899eefa29c84df0a739efa7469db2ecf60e9081a70f766b42111db77fbd372`，8369 字节。
- 指南未改；prepare/store/P1、契约及生效登记、配置、宿主/控制器有限身份核对与上轮基线一致。
- 旧 harness 仍为 `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`、4248 字节，本轮无恢复授权、没有修改。保全副本及其他旧现场继续冻结。

## 2. GPT 实际复验：原两项修复的有效部分

本轮新证据根 `data/reviews/task024_r4_gpt_20261014_201447/`。实际运行 `verify_current.py`：真实接收器 1 次；Gate1 公开 API 13 次（prepare 2 / save 4 / verify 7），另有真实 P1 内存观察控制 1 次。按实际代码帧分别计数，不把 API 包装次数充作核心次数。

**B1 关闭**：两个独立新 scope，在真实 `_source_snapshot` 返回原值后分别给本次新目标顶层、snapshots 新增 unknown.json；各命中 1 次，本次 save 均为 `HumanGate1DecisionBlocked`，field 分别是 `event_0001`、`event_0001/snapshots`。本层 failure 恰七键、全部边界 false，撤销 wrapper 后 verify 仍拒绝，故意新增文件与失败现场保留。未注入 HOLD→APPROVE 两事件追加、revision 2 只读恢复成功。

**八文件目录字节覆盖关闭**：实际场景现在包含固定八相对路径的文件长度/SHA。给 quality_report、input.xlsx、checker.stdout、check_demo_data.py 各追加 LF 时目录指纹均变化，逐项恢复原件后正常。内存引用第三时点控制仍能检出变化；B3 的币种、非法日期、公司矛盾三例仍定位拒绝。

以上运行不修改生产/测试代码，也不修改既有批次。实际用到的人类字段均来自已登记合成夹具，无真实批准。

## 3. 唯一剩余阻断：旧路径登记成为后续调用的持续豁免

位置：`tests/test_record_demo_human_gate1.py` 的 `finalize_api_time_point`，当前约 563 行；以及 S9 / R3 注入对 `EXPECTED_PATHS` 的登记。

当前判定为：有差异路径，且差异路径是全局 `EXPECTED_PATHS` 的子集，就设 `expected_mutation=true`。**路径分支不要求当前注入窗口 active，API 收尾也没有清空该全局集合。** S9 给 `checks/quality_report.json` 登记后，后续普通调用同一路径的新变化也可被豁免。只比较相对路径不足以证明它属于这一次故意注入。

GPT `verify_observer_window.py` 使用实际冻结 prepare 和实际 `evidence_audit`（没有复制判据）做三个隔离控制，每例真实 prepare 恰调用一次：

1. 空登记、active=false，prepare 返回后/API 收尾前给 quality_report 加 LF：第三时点不一致，`expected_mutation=false`，实际审核 `ok=false`。
2. 保留先前 S9 使用的 quality_report 路径登记、**active=false**，同样在新的 prepare 调用收尾前加 LF：第三时点不一致且正确定位该文件，但 **`expected_mutation=true`，实际审核 `ok=true`**。
3. 保留旧 quality_report 登记、active=false，改另一文件 check_demo_data.py：实际审核拒绝。

第二项按实际 S9 登记语句重现其结束后的残留集合；本轮没有运行 S9 业务场景。每例只把一条真实、完整的 prepare 观察替换正常候选中同层同 ID 的一条；其他条目、计数和关系保持不动，调用的是实际共享 audit。完整实际返回、第二点/收尾点观察、文件前后 SHA、active 值、登记集合及审核结果保存在 `observer_window_probe.json`；本轮故意改动的源字节均已恢复。

第二例证明审核能检出变化，却把**当前没有故障注入的普通异常变化**解释成先前探针的预期变化。这违反 R4 的“不放宽普通异常变化”要求，影响证据收尾结论，必须阻断。修正属于 **B 类测试证据问题**，无需改变生产协议或架构。

## 4. 读取的执行端证据与非阻断记录

读取 R4 run_04 的 summary、完整观察、13 项台账并实读长度/SHA，正常候选的实际 audit 通过；登记的 93 项、526 核心条目及逐层闭合按其现场保存。本轮未重跑其整套入口、writer/loader 故障或历史套件，不把读取的 PASS 称作 GPT 重跑。

R4 的 prepare 字节辨识度控制以复制的条件文本构造 formal_problems，并非实际调用共享 audit。本次 GPT 已用实际 audit 完成正负对照，故不另派一张重复实现修复；下一卡的控制应直接使用实际 helper，并如实标明来源。不得将“相同文本”说成“同一 helper 已运行”。

交接/回执的扫描 155572 与保存 protection_result 的 155574，以及旧 R3 154041/154043 等辅助计数差异，登记为非阻断文案事项；只在新回执引用实际保存值，不回写旧文件，不为此重复全树扫描。“未运行原完整 88 项”与当前入口实际包含的旧检查范围，也应按实际具名检查说明，避免泛称；不因此重跑。

## 5. 最终保护与下一步

基线 `task024_r3_gpt_20261014_185350/source_hashes_after.json`，154103 项，完整 SHA `d66dfdcceaf044f34a835791e005482c9d8fa8a9ae03d5e1d5dcc126fd64965b`，NOT_ACCEPTED。

GPT 一次最终完整扫描实读 155637 文件；changed 恰为 adapter/test 两项，范围外变化、missing、读取错误、范围外新增均为 0，scope_compliant=true。旧 harness 与基线原字节一致，本轮没有恢复例外。新增按本轮明确根/确切路径和两个前轮自指元数据登记，未使用 reviews 前缀兜底。扫描后仅有限定稿本轮评审文档/元数据，没有第二次项目树遍历。下一修复基线 SHA/项数及两个确切自指排除见 review_result。

下一卡为 `docs/tasks/TASK-024-R5_DRAFT.md`，**只修测试侧调用范围与实际审核控制**。冻结生产适配器 d8ace42f…34d9、指南与全部既有生产组件；不重新派发已关闭的 B1、八文件覆盖、内存第三时点或排序/历史/版本/锁规则。

真实批准 null、开发宿主 0008、next/AI false；技术验收和合成夹具都不构成真实 Gate 决定。看板由人类处理，TASK-024 系列等待最终整体验收。
