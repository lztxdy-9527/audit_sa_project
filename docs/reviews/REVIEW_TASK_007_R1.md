# TASK-007-R1 复验：已修复主要缺口，命中键类型仍会误报一致

日期：2026-10-11。验收端：GPT。结论：**CHANGES_REQUIRED**。只退回 F01 的一处残留，不推进任务八。

金额比较、退款多重性、外层规则身份、分项状态、缺失/null 诊断、来源实际值和质量前提的修复已通过实测。规则复算公式及原有事实正确。剩余问题是命中键仍将不同类型的 ID 转成同一字符串，错误报告可能返回 MATCHED。本轮 GPT 只新增 QA 和交接文件，没有修改实现。

## 1. 实际通过的验证

在全新容器 `data/sqlite_tests/task007_r1_gpt_20261011_075928` 重跑当前验证入口，退出 0：29 个工作簿、21 个初次 MATCHED、8 个上游阻断，测试失败 0；checker 29 次、SQL 核心 21 次、复核核心 50 次。原有及 R1 新增的 20 项差异检查、6 项前提检查、确定性和隔离检查均符合预期。

GPT 再用独立整数循环核对新结果：21 个成功输入、34 条线索、168 个来源实体，差异 0；主文件仍为 12 个命中键，R02 超额合计 1600000 分。上轮 P01—P09 全部得到正确结果：前八项 MISMATCH，质量矛盾项 CrossCheckBlocked；金额分项状态正确，缺失与 null 可区分，cells 诊断保留实际值。

本轮开始时的 11304 个既有文件变化 0、缺失 0。相对 TASK-007 的 10990 项基线，仅三个授权文件变化；10236、8547、6511、4902、874 项历史基线均变化 0、缺失 0。

## 2. F01 残留：命中键把非字符串 ID 转成字符串（P2，阻断）

`scripts/crosscheck_demo_rules.py:113` 的 `_key_tuple` 仍执行：

```python
return tuple(sorted((key, str(value)) for key, value in hit_key.items()))
```

`compare_facts` 使用该返回值建立命中集合和索引，随后没有对原始 hit_key 的 ID 类型另行核对。因此金额和 related_ids 即使采用严格比较，也无法发现只发生在 hit_key 中的类型错误。这仍不满足 TASK-007-R1 第 3 节“声明为字符串的 ID 保持原类型和值，不能用 str(value) 将类型差异抹平”。

GPT 以 C04 的内存对象建立四组配对测试。每组先将关联 ID 一致地改成合法字符串并同步两处标准化对象指纹，正向控制均 MATCHED；然后只修改观察报告中的一个 hit_key 字段，其他字段及标准化输入不变：

- K01：R02 `hit_key.ap_id`，字符串 `"1"` → 整数 `1`。
- K02：R02 `hit_key.ap_id`，字符串 `"True"` → 布尔值 `true`。
- K03：R02 `hit_key.ap_id`，字符串 `"None"` → null。
- K04：R01 `hit_key.payee_supplier_id`，字符串 `"1"` → 整数 `1`。

四项均错误返回 `DEV_CROSSCHECK_MATCHED`，differences 为空，十个维度均 matched=true。应明确 MISMATCH 或因命中键类型非法而 CrossCheckBlocked。

这是纯内存接口测试，没有修改工作簿、数据库、旧报告或答案册；不声称改名后的内存样例对应真实来源文件。合法字符串 ID（包括看起来像数字、布尔值或空值的文字）属于既定接口范围，不能禁止它们来规避问题。

## 3. 证据和执行记录

证据目录：`D:\harness work\audit_sa_project\data\reviews\task007_r1_20261011_075928`。

- `regression_execution.json`、`regression.stdout.txt`、`regression.stderr.txt`：新回归的真实命令、退出码及完整输出。
- `positive_outputs.json`、`boundary_probes.json`、`diagnostic_comparison.json`：独立事实核验及上轮九个探针的本轮结果。
- `key_type_probes.py`、`key_type_probes.json`：四组配对测试及汇总；每组的 control/mutated input/result JSON 保留完整入参与实际返回值。
- `protected_files_comparison.json`、`acceptance_summary.json`、`source_hashes_after.json`：保护核对、机器可读结论及下一轮冻结基线。

实际运行 `run_review.py`、`independent_review.py`、`key_type_probes.py`、`finalize_evidence.py`，退出均为 0。QA 退出 0 表示采集和证据核验完成，不能解读为四个错误 MATCHED 通过了验收。提交验证入口的真实命令为：

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r1_gpt_20261011_075928'
```

GPT 另调用复核核心 17 次：上轮探针 9 次，新正向控制 4 次，新负向探针 4 次；不混入回归入口的 50 次。

附带说明：RULE_CROSSCHECK_GUIDE 的结果字段表仍把 crosscheck_version 写成 1.0，实际代码和页首为 1.1。此文案不单独阻断，R2 更新说明时一并统一。

## 4. 下一步

将本验收单与 `docs/tasks/TASK-007-R2.md` 一起转交 DeepSeek。只补命中键的类型检查及相关回归，不调整四条规则、复算公式、上游模块或答案。

主理人无需手工测试或批准 Gate。R2 完成后由 GPT 复验；任务八、正式契约/Gate、人类判断保存、AI 建议继续暂停。
