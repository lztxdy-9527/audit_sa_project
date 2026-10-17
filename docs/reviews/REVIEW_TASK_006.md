# TASK-006 验收：需修复退款来源证据

日期：2026-10-11。验收端：GPT。结论：**CHANGES_REQUIRED**。

规则计算在本次已检查的输入中正确，但退款证据链未满足原任务卡，暂不验收任务六，不发任务七。修复由 DeepSeek 执行；GPT 本轮没有修改实现、SQL、测试入口或旧文档，没有批准任何 Gate。

## 1. 复验结果

在全新容器 `data/sqlite_tests/task006_gpt_20261011_064634` 重跑提交的测试入口，退出 0：29 个输入、21 个规则成功、8 个上游阻断；checker CLI 29 次、核心调用 27 次、原测试失败 0。三项额外接口调用按预期阻断，与输入案例统计分开。

主演示数据得到 R01=3、R02=5、R03=2、R04=2，共 12 条线索；R02 唯一应付超额合计 1600000 分。只读检查、复调用确定性以及测试所实现的答案隔离检查通过。

GPT 另用 Python 整数循环直接读取这 21 份标准化输入，独立复算，不读取答案册、不复用规则 SQL。逐键核对全部 34 条线索的金额、原付款/原分摊/退款 ID、退款状态和统计：**计算差异 0**。对输出已携带的 146 个来源实体逐项核对标准化来源及完整 cells，现有内容无差异；但要求提供的实体存在遗漏，见 F01。

本轮开始时保护的 9394 个既有文件：变化 0、缺失 0。任务五 R2 的 8547 文件基线、任务四 R1 的 6511 文件基线、任务三 R3 的 4902 文件基线、任务二 R2 的 874 文件基线也均为变化 0、缺失 0。

## 2. F01：退款摘要没有对应的完整来源实体（阻断验收，P2）

原卡第 6 节已经要求：

> 证据至少包含相关应付、原付款、原分摊、退款主表和退款分摊的 ID、实际业务值和来源定位；从 source_records 读取 workbook_sha256／sheet／excel_row／完整 cells，JSON 解码后保留。

并要求来源缺项或非法 JSON 明确失败。这是落实既有规格，不增加新业务规则。

`scripts/screen_demo_sqlite.py:467` 的 `_evidence_block` 只对传入的应付、原付款和原分摊调用 `source_provenance`；最后才调用 `_refunds_for_allocations` 取得退款摘要。退款主表和退款分摊从未进入来源读取集合。因此：

- `evidence.related_refunds` 有退款 ID、金额、日期、状态和计入标志；`evidence.entities` 没有对应退款主表/分摊的原始 cells，`source_rows` 也没有对应 Excel 行号。
- 21 个成功输入中，C06b、C09b、C10b、S1、S4 共 5 个输入的 7 条线索受影响；逐线索计数，共缺少 22 个来源实体出现项。这个数字按线索分别计数，不是 22 个不同退款，也不是新增异常数。
- C06b 的 R02 显示退款 R01/AR01，退款 100000 分、净付款 900000 分、超额 400000 分；证据实体却只有 AP01、P01/P02、A01/A02，缺少 R01、AR01 的来源。
- C09b 的 R04 全退后保留事实且净额 0，计算正确，但同样缺少退款来源。S4 中已展示的非结算退款也应有来源，即使它们不抵减净额。

GPT 在内存中拦截只读连接的来源查询，未修改数据库或其哈希，做了两项对照：

1. 让 C09b 的原付款 P01 来源查询返回缺失：得到 `RuleScreenError`，符合要求。
2. 让同一输入的退款 R01 来源查询返回缺失：核心根本没有查询该来源，仍返回 `DEV_RULES_COMPUTED`，不符合要求。

该问题妨碍审计人员追查“这笔退款据何抵减”。不影响本轮已经复算正确的金额，但证据完整性与失败处理尚不能验收。

修复时必须保持 `related_ids.payment_ids` / `allocation_ids` 的原付款、原分摊含义；退款来源只扩充证据集合及对应行号，不混入唯一原付款数量或资金统计。

## 3. 验证缺口与说明修正

提交的测试入口只比较答案册登记的来源行号，未检查证据所必需的完整实体集合，也没有完整 cells 的自动逐项比较。现有测试退出 0 无法证明退款来源齐全。

R1 要先独立推导必需集合，再检查覆盖和内容。不能只遍历当前输出已有实体，也不能只检查 `related_refunds` 存在；这些检查均会漏掉本次问题。补充退款主表/退款分摊的缺来源、非法 JSON 负向测试，并保留原付款缺来源对照。

`docs/RULE_SCREEN_GUIDE.md:144` 的“不计算超付、重复付款”与 R01/R02 的实际功能矛盾。改成准确的“按规格计算重复足额付款和净付款超额线索，但不直接认定损失、舞弊或审计调整”等表述即可，不需修改规则。

旧 `EXEC_REPORT_006.md` 保留原字节。R1 回执解释此前“完整 cells 核对”未覆盖退款来源，并给出修复后的可复现结果。

## 4. 证据与实际命令

证据目录：`D:\harness work\audit_sa_project\data\reviews\task006_20261011_064634`。

- `regression_execution.json`、`regression.stdout.txt`、`regression.stderr.txt`：真实测试命令、退出码与输出。
- `independent_review.py` / `independent_review.json`：独立复算、必需来源覆盖检查及两项内存故障探针；脚本执行退出 0 表示证据采集完成，其中退款探针的 `contract_met=false` 明确表示发现失败，不能写成验收通过。
- `protected_files_comparison.json`：五组保护基线逐文件核对。
- `acceptance_summary.json`：机器可读结论、交付文件完整哈希与边界。
- `source_hashes_after.json`：供 R1 使用的扩充保护基线，排除本证据目录本身，避免自引用。

实际执行（均未安装依赖）：

```powershell
& 'C:\Users\alan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B 'D:\harness work\audit_sa_project\data\reviews\task006_20261011_064634\run_review.py'
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_gpt_20261011_064634'
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\data\reviews\task006_20261011_064634\independent_review.py'
& 'C:\Users\alan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B 'D:\harness work\audit_sa_project\data\reviews\task006_20261011_064634\finalize_evidence.py'
```

第二条由第一条启动，不是第二次重跑。上述执行退出码均为 0，验收结论仍为需修复。

## 5. 下一步

将本验收单和 `docs/tasks/TASK-006-R1.md` 一起转交 DeepSeek；由它完成限定修复并提交新回执后，GPT 再复验。

主理人本轮不需要手工检测、填写审计判断或模拟 Gate 批准。任务六仍处于开发验证阶段，不能推进正式批次、AI 建议或任务七。
