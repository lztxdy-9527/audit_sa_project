# TASK-006-R1 复验：开发态验收通过

日期：2026-10-11。验收端：GPT。结论：**ACCEPTED_DEVELOPMENT_SCOPE**。TASK-006 的 F01 已关闭；任务六可作为后续开发的冻结基础。

本结论仅是模块开发验收，不是 Gate 1/Gate 2 放行，不建立正式契约，不代表真实 ERP 兼容或真实审计完成。GPT 没有修改实现、SQL、测试入口或旧文件，没有填写人类判断或生成 AI 建议。

## 1. 实测

在全新容器 `data/sqlite_tests/task006_r1_gpt_20261011_072212` 重跑当前测试入口，退出 0：29 个输入、21 个规则成功、8 个上游阻断、测试失败 0；checker CLI 29 次、核心调用 32 次。额外接口、复调用、五项来源故障调用与工作簿输入分别理解，不把预期错误当作测试失败。

GPT 再用上轮的独立 Python QA 脚本读取本轮新标准化输入和实际输出，不用规则 SQL 或答案册复算：21 个成功输入、34 条线索，命中键、整数分金额、相关 ID、退款状态与统计差异均为 0；168 个来源实体的 workbook 哈希、sheet、Excel 行号和完整 cells 均精确一致，必需实体缺项 0。

主演示仍为 R01=3/R02=5/R03=2/R04=2，共 12 条，R02 唯一应付超额合计 1600000 分。合并付款、全额/部分退款、缺失应付关联、收款对象差异、非结算、特殊字符串分组与无资金事件的预期均保持。

## 2. F01 关闭依据

`_evidence_block` 先取得相关退款，再读取退款主表和退款分摊来源，合并、去重和排序；完整来源同时进入 `evidence.entities` 与 `source_rows`。相关的非结算退款仍有来源且不抵减。

原先 C06b、C09b、C10b、S1、S4 的 7 条线索缺少的 22 个退款实体出现项现在全部存在。原付款 ID 集合与付款统计口径没有因扩充证据而混入退款。

重跑真实触发的五项来源故障回归：原付款主表缺来源、退款主表缺来源、退款分摊缺来源、退款主表 cells JSON 非法、退款分摊 cells JSON 非法，均为 `RuleScreenError`，每项注入命中 1，数据库字节未变。

GPT 另重跑了上轮两项对照探针：原付款来源缺失和退款来源缺失均按要求报错；上轮退款来源未被查询而返回成功的问题已消失。

## 3. 文件保护与冻结

本轮开始时的 10030 个既有文件：变化 0、缺失 0。相对上轮 9600 项基线，恰好只有本卡允许的三个文件改变；任务五 R2 的 8547、任务四 R1 的 6511、任务三 R3 的 4902、任务二 R2 的 874 文件基线均为变化 0、缺失 0。

本次冻结：

- `scripts/screen_demo_sqlite.py`：`1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe`，版本 `TASK-006-rule-core-1.1`。
- `tests/test_screen_demo_sqlite.py`：`d4afa890cff0d129b56f116e7188fcf30228d69201033f57303259a26be29247`。
- `docs/RULE_SCREEN_GUIDE.md`：`84aeed5633641a193a717cae593d8b72a25a7bde7b632942e7a4314ca43062d7`。
- `docs/EXEC_REPORT_006_R1.md`：`ac75b955efae183022e0ffa147a3791c5e441255aad31102b18d8f988a6e3071`。

四份规则 SQL 保持原哈希，完整值见机器可读验收汇总。所有旧回执与上游冻结实现均保持原字节。

## 4. 一项非阻断记录说明

R1 回执称 `summary.json` 包含逐来源检查和五项故障详情，但测试代码没有把局部的 `source_reports` / `fault_results` 数组写入该 JSON。实际断言存在且成功，详情在控制台输出中；GPT 本轮已完整保存 stdout，并另有独立 QA JSON，足以闭合 F01，故不再要求一轮修复。

应引用 `data/reviews/task006_r1_20261011_072212/regression.stdout.txt` 的实际记录，不能称提交的 summary 已保存这些明细。下一任务的复核差异和测试分类必须直接保存为结构化文件，并捕获整个验证入口的 stdout/stderr。旧测试入口和旧回执继续冻结，不为此回写历史。

## 5. 证据及实际执行

证据目录：`D:\harness work\audit_sa_project\data\reviews\task006_r1_20261011_072212`。

`regression_execution.json` 记录真实回归命令与退出 0，`regression.stdout.txt` / `regression.stderr.txt` 留完整输出；`independent_review.json` 留独立复算和两项探针；`protected_files_comparison.json` 留六组保护比较；`acceptance_summary.json` 留机器可读结论和完整哈希；`source_hashes_after.json` 是供下一任务使用的扩充基线。

GPT 实际执行三个新 QA 入口：`run_review.py`、`independent_review.py`、`finalize_evidence.py`，均退出 0。回归由 run_review 启动项目 Python 3.11.1 的以下命令，运行 SQLite 3.39.4：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_r1_gpt_20261011_072212'
```

未安装依赖、未初始化 Git、未重跑任务二至五整套测试；新链路实际调用其冻结 API。开发态只读与哈希记录不提供抵御同权限恶意篡改的安全隔离。

## 6. 下一步

TASK-007 限定为 Python 独立复算与 SQL 事实结果的一致性复核。独立指计算实现分开，不宣称独立多智能体审计保证；两套程序一致也不能替代已知案例验证与人工职业判断。

主理人现在只需把本验收单和 `docs/tasks/TASK-007_DRAFT.md` 一起转给 DeepSeek，无需手动检测或模拟批准。正式流程和人类判断环节另行下卡。
