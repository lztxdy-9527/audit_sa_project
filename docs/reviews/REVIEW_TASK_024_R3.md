# TASK-024-R3 终审

日期：2026-10-14。结论：**NOT_ACCEPTED**。不进入 TASK-025、Gate2、宿主接线或真实初判。本轮只保留两个影响结论的残余，其他已关闭项不重新派发。

## 1. 已核对身份与具名恢复

本次实读与交接一致：

- `scripts/record_demo_human_gate1.py`：`76e95b0de262a4e751c2b35431249094e25148efc20bc32d0ac82dee812b82f4`，85015 字节。
- `tests/test_record_demo_human_gate1.py`：`a4ad793240bd7c8973c15b1620759426cf45cf7bbad908afd0f1ac37e9581fde`，156692 字节。
- `docs/EXEC_REPORT_024_R3.md`：`ea37db7bfa50034cb5d23a724a1a9dfa5474f8fe1b86989d620b86a4f967d3ec`，12084 字节。
- Gate1 决定指南及冻结 prepare/store/P1、正式契约、生效登记、配置、开发宿主身份均一致；完整范围比较另见本轮 protection_result。

旧 `data/human_gate1_decision_tests/task024r1_fault_00/aux_fault_r1.py` 已达到 `7506a64bbe4bd432497a22628435868661c3e7bba9d689a7d06c17f22daa1035`、4248 字节，与 GPT 具名恢复材料逐字节相同。保全副本为 `c148abea44cdbcf8fef2156afed37ab1460355cad22e9a421661fef17e7a3b4d`、6386 字节。**授权恢复完成；不追认 R2 越界。** 本轮没有执行旧 harness、恢复材料或保全副本，没有改写旧结果。

## 2. GPT 实际复验及读取证据的区别

实际运行：本轮 `verify_current.py` 在新根运行真实接收器 1 次，记录 Gate1 公开 API 13 次（prepare 2、save 4、verify 7），另记录真实 P1 观察控制 1 次。独立代码帧观察保存于 verification_summary，未要求宿主 API 与嵌套核心次数相等。全部使用已登记合成夹具，不构成真实批准。

正常 HOLD→APPROVE 两事件追加、revision 2 恢复及负向恢复后的正常控制成功。B3 的 currency=USD、period_start=2026-09-00、company 矛盾三例同步外层 context/receipt/后继引用哈希后，均由实际目标字段阻断。真实 P1 返回后、逻辑 API 收尾前改变保留内存引用，第三时点检出了变化。

另在 `finite_audit.py` 调用真实冻结 prepare 1 次，执行下述目录观察控制；不重建业务链。

读取既有证据：R3 run_07 的 88 项 PASS、13 项台账及层计数闭合；fault_01/02 的 505/506 条核心结构、候选与最终磁盘 SHA 相等、失败诊断与 FAIL 结果。本次实读审核 run_07 台账各项长度/SHA 与正式 audit 均通过；两个故障目录确为核心条目，已经消除 R2 把 API calls 覆盖到 core 文件的问题。**这些是本次读取的执行端证据，并非 GPT 重跑其完整入口或故障套件。** 本轮未重跑历史入口、writer/loader 故障组，也未新建真实 junction。

## 3. B1 残余：本次新事件没有进入终端固定集合确认

位置：`scripts/record_demo_human_gate1.py:888` 的 `_terminal_confirm`，及 save 调用处。

该函数只对 `events` 循环调用 `_confirm_event_layout`。save 传入的是操作开始前的历史事件；**本次 `target_dir` 只检查八个已知文件字节和 failure，不检查目标顶层/snapshots 的固定集合**。所以历史事件与批次未知项已补上，本次新事件仍有缺口。

GPT 两个独立新 scope 的实测：包装真实 `_source_snapshot`，在其返回原始缓冲后只新增一个文件，注入各命中 1 次：

1. 新事件 `event_0001/unknown.json`：save 返回 RECORDED，未知文件存在，未写 failure；撤销 wrapper 后真实 verify 在 `event_0001` 拒绝。
2. 新事件 `event_0001/snapshots/unknown.json`：save 仍返回 RECORDED，未知文件存在，未写 failure；撤销 wrapper 后真实 verify 在 `store.files` 拒绝。

这是“本次报告保存成功、立即只读恢复却拒绝”的实际不一致，违反 R3 §2 对历史/目标两类事件的既有要求。两个失败现场保留于本轮 reviewer 新 scope，未删未知文件凑成功。需要同一终端规则覆盖目标事件，保留既有字节、路径、failure、锁及限定 scope 规则；无需新协议或更多语义复算循环。

## 4. E2 残余：prepare 的目录观察遗漏嵌套文件字节

位置：`tests/test_record_demo_human_gate1.py:349` 的 `bounded_dir_scene`，以及 `object_fingerprint` / `describe_input` 调用。

目前首层文件有长度/SHA，但子目录只有文件名列表。真实 prepare 消费的八份文件中，checks/source/logs/code_snapshot 内的文件没有进入目录现场的字节摘要。

GPT 在自己新批次上分别给以下文件追加一个 LF，再恢复原件；每份文件 SHA 确实变化，但 batch_dir 的场景规范对象与指纹均完全不变：`checks/quality_report.json`、`source/input.xlsx`、`logs/checker.stdout.txt`、`code_snapshot/check_demo_data.py`。

进一步实际调用真实冻结 prepare，经真实 `observe_core` 返回后，只给 quality_report 加 LF，再执行 `finalize_api_time_point`：`input_unchanged_through_api=true`、`three_time_points_equal=true`。将该完整观察替换既有正常候选中同层同 ID 的一条，实际 `evidence_audit` 仍 `ok=true`。控制后已恢复本轮源原字节。完整真实返回、前后现场与审核结果保存在 `directory_observer_formal_control.json`。

因此“目录真实有界现场”和三时点对内存对象的修正有效，但**不能据此声称 prepare 的八份文件输入字节均被观察**。应按既定八个相对路径记录存在性/类型/长度/SHA，以同一规则计算三个时点；store.verify 的六文件目录及 store.save 输出角色保持区分。禁止扩大成全树递归或仅用目录名/文件名列表替代文件内容。

## 5. 关闭项、非阻断事项与后续

具名恢复、B3 范围与真实日期、内存消费引用的第三时点控制、本次读取的核心层计数闭合及新 driver 的实际候选结构均不再作为残余阻断。历史未知项/批次未知项的 R3 执行证据保留，不要求为新目标缺口重复整套历史回归。

执行交接“154041”与保存 protection_result 的“154043”等辅助计数口径应在新回执分来源说明；不为这些不影响结论的文字差异修改旧回执或重复全树扫描。

保护依据是 R2 NOT_ACCEPTED 快照（151000 项，`44c6f280ae9f05d1ebf7307f9bdd58047c068b728376c44f55cf64405bf4c387`）；普通变化仅 adapter/test，旧 harness 单列授权恢复。GPT 最终一次完整扫描实读 154101 文件，普通 changed 恰为 adapter/test 两项；授权恢复 SHA 正确，missing/读取错误/范围外变化/范围外新增均为 0，scope_compliant=true。之后仅有限登记本轮评审元数据，未再次遍历项目树。修复基线的完整 SHA、项数及两个确切自指排除见 review_result；这是 GPT 实际扫描，独立于执行端保存的扫描结果。

本次形成 `docs/tasks/TASK-024-R4_DRAFT.md`，仅修上述两项。真实批准仍 null、开发宿主仍 0008、next/AI false。看板由人类处理，当前四张卡继续等待整体验收。

证据根：`data/reviews/task024_r3_gpt_20261014_185350/`。
