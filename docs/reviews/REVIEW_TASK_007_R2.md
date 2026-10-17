# TASK-007-R2 复验通过

日期：2026-10-11。验收端：GPT。结论：**ACCEPTED_DEVELOPMENT_TASK_007**，接受版本 `TASK-007-crosscheck-1.2`。可以启动 TASK-008 的开发任务。

这是开发模块验收，不是业务批次 Gate 放行，也不是审计结论。正式契约、批准控制、人类判断保存及后置 AI 建议仍未实施。GPT 没有修改实现代码。

## 1. 修复核验

身份键现在包含值类型与 repr；用于诊断配对的字符串渲染没有承担身份相等比较。观察报告中的非字符串 ID 不再与合法字符串 ID 合并。命中键的规定字段及非空字符串类型有明确检查。

GPT 独立重跑上轮四组配对：正向字符串 ID 全部 MATCHED；仅改 hit_key 的负向对象全部 MISMATCH，包含 HIT_KEY_TYPE_MISMATCH、对应漏报/多报，hit_keys 维度为 false。原始值、双方类型及字段路径保留；字符串 "1"、"True"、"None" 没有被禁止。

外层规则身份、退款重复、金额精确类型、缺失/null 诊断、来源原值及质量前提修复均保持。说明页首和结果字段表已经统一为 1.2。

## 2. 实际运行的检查

全新容器：`data/sqlite_tests/task007_r2_gpt_20261011_081630`。

- 回归入口退出 0：29 个工作簿、21 个初次 MATCHED、8 个上游阻断；初次不一致、前提阻断、意外错误和测试失败均为 0。
- checker CLI 29 次、SQL 核心 21 次、复核核心 58 次；20 项差异、6 项前提、4 组命中键配对、确定性及隔离检查全部符合预期。
- GPT 独立整数循环核对 21 份结果：34 条线索、168 个完整来源实体，差异 0。MAIN 仍为 R01/R02/R03/R04 = 3/5/2/2，共 12 键；R02 唯一应付超额合计 1600000 分。
- 上轮九个补充探针重跑正确；另四组正负控制重跑正确。GPT 额外调用复核核心 17 次，与入口的 58 次分开统计。

实际命令：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r2_gpt_20261011_081630'
```

GPT 的 run_review.py 启动上述命令并捕获 stdout/stderr；另实际运行 independent_review.py、key_type_probes.py、finalize_evidence.py，退出均为 0。预期 MISMATCH 与 Blocked 是负向检查的正确结果，不写成 MATCHED。

## 3. 保护与冻结版本

本轮开始时的 12207 个既有文件变化 0、缺失 0。相对 R1 的 11626 项基线，仅三个授权文件变化、缺失 0；相对 TASK-007 的 10990 项基线也是授权三文件变化。10236、8547、6511、4902、874 项历史基线均变化 0、缺失 0。

接受的完整哈希：

- `scripts/crosscheck_demo_rules.py`：`8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2`。
- `tests/test_crosscheck_demo_rules.py`：`1e65fb48f8c3994261bf8738183cee163d553316f22b0475850f5fe99aa8a7c4`。
- `docs/RULE_CROSSCHECK_GUIDE.md`：`6c1f0130f07fd9f2943ef738ac74ffebb50e3f5a884924886bcfd1d4a25e0bd0`。

上游筛查核心仍为 `1b123766…`，装载器 `1abfad89…`，标准化器 `a2bae49e…`，checker `a7e5eb67…`，SPEC `5df632ed…`；四份 SQL、schema、旧回执、答案册和历史证据不变。本轮没有重跑任务二至六各自的整套测试；新链路调用了其冻结 API，并完成哈希保护核对。

## 4. 证据与下一步

证据目录：`D:\harness work\audit_sa_project\data\reviews\task007_r2_20261011_081630`。

regression_execution/stdout/stderr、positive_outputs、boundary_probes、key_type_probes、protected_files_comparison、acceptance_summary 及各项完整输入/返回值均已保存。source_hashes_after.json 是下一任务保护基线，包含本轮 QA 文件，排除该哈希清单自身以避免自引用。

复核器仍只处理内存对象和报告内部绑定，不实读数据库字节，不证明来源真实性，不抵御同权限篡改；两套实现一致不构成审计结论。

将本验收单及 `docs/tasks/TASK-008_DRAFT.md` 一起交给 DeepSeek。TASK-008 只把已经筛查、复核的事实整理为可阅读底稿；主理人本轮无需手工检测或模拟批准。
