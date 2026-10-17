# TASK-007 验收：复算正确，比对边界需修复

日期：2026-10-11。验收端：GPT。结论：**CHANGES_REQUIRED**。暂不推进任务八。

独立核心确实从标准化记录重新计算，没有调用 SQL、筛查核心或答案册。本轮正常输入的计算和来源均正确；但复核器会对部分错误报告返回 MATCHED，差异报告也存在表达不完整的问题。本轮只新增 QA 和交接文档，GPT 没有修改实现或上游文件。

## 1. 已实际通过的检查

全新容器 `data/sqlite_tests/task007_gpt_20261011_074219` 重跑提交的验证入口，退出 0：29 个工作簿输入、21 个初次一致、8 个上游阻断；checker CLI 29 次、SQL 核心 21 次、复核核心 40 次；原 11 项差异检查、5 项前提阻断、确定性及隔离检查均通过，测试失败 0。

GPT 另直接读取本轮标准化输入，用此前独立 QA 的整数循环复算，与新模块产出的 recomputed_facts 比较：21 个输入、34 条线索、168 个来源实体，差异 0。主文件 12 键及 R02 超额合计 1600000 分保持。

本轮开始时的 10748 个既有文件变化 0、缺失 0。任务六 R1 的 10236、任务五 R2 的 8547、任务四 R1 的 6511、任务三 R3 的 4902、任务二 R2 的 874 文件基线也均为变化 0、缺失 0。

## 2. F01：比较未统一保留金额类型（P2，阻断）

任务卡要求金额为整数分、bool 不等于 0/1、比较保留类型差异。`_compare_amounts`（约第 575 行）对标量只额外排除 bool，仍用 Python 普通数值相等比较；统计和勾稽部分也直接使用 `!=`。

两个真实探针均错误返回 `DEV_CROSSCHECK_MATCHED`：

- P01：只将 MAIN 的一个 R02 overpayment 从整数 `500000` 改为浮点数 `500000.0`，身份绑定和其他字段不变。
- P02：只将无资金事件样本的 `statistics.involved_payments.settled_amount_cents` 从整数 `0` 改为 bool `false`。

应返回 MISMATCH，不能用数值等价吞掉类型差异。修复须统一覆盖标量、嵌套 net_per_payment、退款金额、资金统计和勾稽；计数、行号和 ID 也应按其声明类型比较，不通过 str() 转换让不同类型变得相等。

## 3. F02：退款摘要重复和 finding 规则身份没有被发现（P2，阻断）

两个真实探针也错误返回 MATCHED：

- P03：C09b 的 R04 退款摘要列表原样追加同一条 R01/AR01 摘要。`_compare_refunds`（约第 614 行）先构造字典覆盖重复项，因而看不见列表多了一条。
- P04：只将 MAIN 第一条 finding 的外层 `rule_id` 从 R01 改成 R04，保留 hit_key.rule_id=R01。`compare_facts` 只根据 hit_key 比较，完全忽略外层规则身份；报告此时会把 R01 事实标成 R04。

退款摘要需要先检查元素结构和多重性，再逐项比对；不能用字典覆盖、过滤非对象项等方式静默丢掉观察事实。外层 rule_id 必须与 hit_key.rule_id 以及复算规则一致。身份冲突可以明确阻断或报告差异，但绝不能 MATCHED。

## 4. F03：分项状态及差异诊断不能准确表达问题（P2，阻断）

三个直接复现：

- P05：R02 overpayment 加 1 分后，整体正确返回 MISMATCH 和 AMOUNT_MISMATCH，但 `comparison.checks.amounts_cents` 仍为 true，其余维度也全部 true。此字段若意指“执行过”，必须明确命名，并另给分项一致状态；现在不符合“各比较维度状态”的交付要求。
- P06/P07：分别删除 overpayment、将它设为 null，两份 differences 完全相同，均 actual=null。任务卡要求区分缺失、null、0。
- P08：改动一个来源 cells 的 raw_value，差异虽然被发现，却只保存 expected="完整 cells"、actual="与标准化记录不一致"。这不是预期值和实际值，读者无法由差异记录知道改了什么。

需要输出准确分项一致状态；使用可序列化的缺失标记区分缺失和 null；保存实际 expected/actual 值。来源可定位到具体单元格字段，也可保留该路径下完整的预期和实际对象，不可用提示语代替值。

## 5. F04：质量前提的“无问题”条件未核对（P2，阻断）

原卡第 4 节要求质量 pass 且无质量问题。`_check_inputs`（约第 140 行）只检查 result=pass，未消费 issue_counts_by_code。

P09：normalized 的质量结果仍为 pass，但将问题计数设为 `{"FOREIGN_KEY_MISSING":1}`，同步两处对象指纹以隔离质量前提检查；核心仍返回 MATCHED。应为 CrossCheckBlocked。

此探针只检验本层声明要消费的质量前提，不证明同权限篡改防御，也没有改数据库或任何旧输入。修复只需检查冻结标准化契约的质量字段，不要求重建 ERP 数据质量 checker。

## 6. 证据与命令

证据目录：`D:\harness work\audit_sa_project\data\reviews\task007_20261011_074219`。

- `regression_execution.json`、`regression.stdout.txt`、`regression.stderr.txt`：真实重跑命令、退出码及完整输出；提交测试的结构化详情在新测试容器中。
- `positive_outputs.json`：对独立复算事实、金额和完整来源的再次核验。
- `boundary_probes.json`：9 项探针。P01/P02/P03/P04/P09 共 5 项错误返回 MATCHED；其余发现了整体差异，但暴露诊断问题。
- `P*.input.json` / `P*.result.json`：每项内存测试的输入与实际完整返回值。P09 的指纹同步仅为测试设置，不是批准或修复真实数据。
- `diagnostic_comparison.json`：缺失与 null 的差异列表相同的实证。
- `protected_files_comparison.json`、`acceptance_summary.json`、`source_hashes_after.json`：保护核对、机器可读结论、供 R1 使用的扩充基线。

GPT 实际执行新的 run_review.py、independent_review.py、finalize_evidence.py，均退出 0。independent_review 退出 0 表示证据采集完成，不能写成这些负向案例通过。回归入口由 run_review 启动，命令为：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_gpt_20261011_074219'
```

GPT 额外调用了 9 次复核核心，独立于原回归的 40 次。所有探针只操作新读取对象的内存副本，未改旧报告、数据库、实现或答案册。

## 7. 下一步与边界

把本验收单及 `docs/tasks/TASK-007-R1.md` 一起转交 DeepSeek，按限定范围修复。正常计算公式和上游实现无需调整，旧 EXEC_REPORT_007 保留。

主理人本轮不需要手工检测或模拟批准；修复后交 GPT 复验。任务八、正式事实底稿、契约/Gate、人类判断保存及后置 AI 建议仍未开始。
