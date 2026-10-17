# TASK-002-R1 执行回执（数据质量校验器返修）

任务：修复 TASK-002 验收发现的四类校验问题（A 日期、B 表头与字段映射、C 标识保真与真实类型、D 金额不可用时的有限报告）并补回归验证。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-002-R1.md`、`docs/reviews/REVIEW_TASK_002.md`、`docs/SPEC_V1.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未启动 TASK-003，未宣布 TASK-002 最终验收通过。

> 本回执只记录本卡**实际执行**的命令与结果；未执行的验证一律写明“未执行”。命令均为完整参数，不使用省略号。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 四类问题（A/B/C/D） | 全部修复；GPT 报告中的 B01—B09 九份边界输入用返修后校验器复跑，行为全部符合要求 |
| 新增回归验证 | `tests/test_check_demo_data_regression.py` 实际运行：**42 个用例全部通过**（19 个边界／正向／覆盖保护 + 主文件 + 22 份原案例） |
| 主文件复跑 | 退出码 **0**，四表行数仍为 20 / 993 / 1000 / 1005，完整金额与勾稽可正常评估 |
| 22 份原 fixture 复跑 | **14 份退出 0、8 份退出 1**，主要问题代码无遗漏 |
| 只读输入保护 | 回归脚本对 26 个只读输入（主输入 + 22 份 fixture + 规格 + 返修卡 + 验收报告 + 原回执 + 生成器）做前后哈希比较：**全部一致** |
| GPT 验收证据哈希核对 | GPT 记录的 94 个文件中 **93 个逐字节未变**，唯一变化的是本次授权修改的 `scripts\check_demo_data.py` |
| 依赖 | 本轮**未安装、未升级**任何依赖：openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9 |
| 未执行 | R01—R04 检测引擎、SQL、SQLite 入库、状态机、Gate 1／Gate 2、AI 审计建议、正式契约、Git、RAG、OCR、百万行压测、真实 ERP 接入 |

---

## 2. 实际修改与新增的文件

### 2.1 修改（仅两个授权文件）

| 文件 | 当前 SHA-256 | 说明 |
| --- | --- | --- |
| `D:\harness work\audit_sa_project\scripts\check_demo_data.py` | `034a4504ecd5853e3d9ae453f688094ef4f80fec508e01551330956843a5c333` | 四类问题修复；在原文件内改，未整体重写 |
| `D:\harness work\audit_sa_project\docs\DEMO_DATA_GUIDE.md` | `0d8f73f1d9a36cce8422f8d2c3cae6ee3928d135fdb1dd2686f67d4cc0b324b4` | 只同步校验报告语义（6.1—6.3 节）、返修摘要与新的验证方法；业务范围与原数据含义未改 |

### 2.2 新增

| 文件 | 当前 SHA-256 | 说明 |
| --- | --- | --- |
| `D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py` | `b3b692645bcf1d630836391717e7c15a52e57eb685bd3dea66b2ce8650b552bc` | 可直接执行的回归验证文件，仅用标准库与现有 openpyxl，未新增测试框架依赖 |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_002_R1.md` | 本文件 | 新返修回执；原 `EXEC_REPORT_002.md` 未覆盖、未修改 |

### 2.3 新证据目录（`data\generated\task002_r1_01\`，共 137 个文件）

| 子路径 | 文件数 | 内容 |
| --- | --- | --- |
| `baseline_reports\` | 23 | 返修后复跑主文件（`main.json`）与 22 份原 fixture 的报告 |
| `recheck_boundary\` | 9 | 复跑 GPT 报告 B01—B09 九份边界输入的报告 |
| `regressions\regression_summary.json` | 1 | 42 个回归用例的逐项结果、失败清单、只读输入前后哈希 |
| `regressions\command_log.json` | 1 | 每次调用的完整参数数组、退出码、报告路径（机器可读） |
| `regressions\inputs\` | 19 | 回归用的输入副本（每组从原 C01/C07b/C14a 的新副本开始） |
| `regressions\reports\` | 19 | 各边界／正向用例的校验报告 |
| `regressions\logs\` | 42 | 每次调用的校验器 stdout/stderr 原文 |
| `regressions\baseline_reports\` | 23 | 回归脚本内部的基线复跑报告 |

未覆盖 `demo_20260930_a`（含其 `checks\` 旧报告）、`demo_20260930_b`、`dev_try_01`、`dev_try_02` 或 GPT 证据目录中的任何文件。

---

## 3. 四项问题（A/B/C/D）的具体改法与报告字段变化

### A. 必填日期与时间成分

- `parse_date_cell` 改为三返回值 `(日期, 问题代码, 是否存在内容)`：
  - 空单元格、空字符串、**纯空白文本** → `MISSING_REQUIRED_VALUE`；
  - 原生 `datetime` 且时／分／秒／微秒任一非零 → 新代码 `DATE_TIME_COMPONENT_PRESENT`，**不再** `value.date()` 截取；
  - 原生 `date`、**午夜原生日期时间**（时间部分全为 0）、纯 `YYYY-MM-DD` 文本、时间部分全为 0 的日期时间文本 → 无损转换通过；
  - 其余无效或歧义表示 → `DATE_INVALID`；跨月、非法日期仍阻断。
- 九月范围（`DATE_OUT_OF_RANGE`）与退款日期先后校验保持不变，未通过“跳过空值”绕过。

### B. 固定表头与字段映射

- 表头改为**逐字匹配、不 strip**：`ap_id `（末尾空格）不再算 `ap_id`，报 `REQUIRED_COLUMN_MISSING`。
- 列存在检查、重复列检查、读取索引**统一使用同一份原始表头名称**（原来一处 strip、一处用原始表头，是漏检根因）。
- 新增报告字段 `structure.sheet_field_mapping`：逐字段给出列号或 `null`，未映射字段一目了然，不再静默当作已核验。
- 空行判定改为**按原始整行单元格**（不再依赖成功映射的字段），数据只落在未识别列的行不会被当成空白行丢弃；未映射字段在行记录中以 `unmapped_fields` 标记。
- 全部问题保留工作表名、Excel 原行号、字段名与原值定位。

### C. 标识保真与真实类型

- `read_text` 改为三返回值且**不再 `strip()`**：非空文本原样保留（`" AP01"` 仍是 `" AP01"`）；纯空白文本按空处理。
- 布尔、数值、日期等非文本类型统一报告类型问题；**可空标识字段（`ap_id`、`original_payment_id`、`original_allocation_id`）与银行流水号同样适用**，统一使用 `ID_TYPE_INVALID`（原实现只对必填文本字段用该代码，可空字段会漏报）。
- 必填纯空白标识仍阻断；文本前导零保留；`0001`（文本）与 `1`（数值）不会被认定相同。
- 收款对象与应付供应商不同仍**不是**本校验器的质量阻断条件。

### D. 金额不可用时的有限报告

- 不再用 `or 0` 拼完整总额。报告分三层：`amount_summary.known_valid_subtotals_cents`（已知有效小计）、`amount_summary.complete_totals_cents`（完整总额，依赖不完整时为 `null`）、`amount_summary.unusable_amount_cells`（不可用单元格数量、按原因计数与来源清单；按 `(表, 行, 列)` 去重，同一单元格只计一次）。
- 不可用原因覆盖：空值／纯空白、无法解析、超过两位小数、公式、非正金额。
- 按付款类型／状态的小计同样披露完整性：`known_valid_amount_cents` 与 `complete_amount_cents`（后者在该组存在不可用单元格时为 `null`）。
- 勾稽：采用本卡允许的保守方案——批次存在任何问题时 `reconciliation.status = NOT_ASSESSED`，`complete_totals_cents` 全为 `null`，`known_plus_missing_equals_master` 为 `null`（不再显示 `true`）；同时保留明确命名的诊断小计 `diagnostic_known_valid_subtotals_cents`。未实现复杂依赖图。
- 金额列未映射时（如 C14a 缺 `payable_amount`），该表已知小计与完整总额**都为 `null`**，并在 `amount_summary.unmapped_amount_columns` 中登记。
- 质量有效的数据（主文件与 14 份有效 fixture）仍精确计算，金额全部为整数分，勾稽正常评估。

### 3.1 报告字段变化（供验收对照）

| 旧字段（TASK-002） | 新字段（TASK-002-R1） |
| --- | --- |
| `amount_summary.by_table_cents.*` | 拆为 `amount_summary.known_valid_subtotals_cents.*` 与 `amount_summary.complete_totals_cents.*` |
| `amount_summary.unparsable_amount_rows` | 替换为 `amount_summary.unusable_amount_cells`（`total` / `by_reason` / `sources`） |
| `amount_summary.payments_by_type_and_status.*.amount_cents` | `known_valid_amount_cents` + `complete_amount_cents`（可空）+ `unusable_amount_cells` |
| `reconciliation.settled_pay_total_cents` 等 | `reconciliation.diagnostic_known_valid_subtotals_cents.settled_pay_total` 等 |
| `reconciliation.known_plus_missing_equals_master`（布尔） | 布尔或 `null` |
| （无） | `reconciliation.status`（`ASSESSED` / `NOT_ASSESSED`）、`reconciliation.complete_totals_cents`、`amount_summary.unmapped_amount_columns`、`structure.sheet_field_mapping` |
| 新问题代码 | `DATE_TIME_COMPONENT_PRESENT` |

限制（未变或已知）：`issues[*].severity` 仍统一为 `blocking`，未实现分级；退出码仍固定 0／1／2；`demo_20260930_a\checks\` 内的旧报告仍是旧字段语义（保留为 R0 证据，未重新生成）。

---

## 4. 回归验证实际结果（42 个用例，全部通过）

回归命令见第 6.5 节；逐项结果与失败清单见 `task002_r1_01\regressions\regression_summary.json`，每次调用的完整参数数组见 `command_log.json`。

| 用例 | 输入改动 | 退出码 | 关键断言（实际） |
| --- | --- | --- | --- |
| B01_payment_date_blank | 付款日期清空 | 1 | `MISSING_REQUIRED_VALUE` 定位 payments.payment_date；勾稽 NOT_ASSESSED；比较字段 null |
| B02_ap_date_blank | 应付日期清空 | 1 | `MISSING_REQUIRED_VALUE` 定位 payables.ap_date |
| B03_payment_date_nonmidnight_datetime | 原生 datetime 2026-09-10 12:34:56 | 1 | `DATE_TIME_COMPONENT_PRESENT`，不再截取日期 |
| P04_midnight_datetime_is_accepted | 原生 datetime 2026-09-10 00:00:00 | 0 | 未被误拦；完整金额 500000 分；勾稽 ASSESSED 且相等 |
| B04_ap_id_header_trailing_space | payables 表头改为 `ap_id ` | 1 | `REQUIRED_COLUMN_MISSING` 定位 payables.ap_id；映射显示 ap_id 为 null；该行未丢（source_rows=1、blank_rows=0） |
| B05_ap_id_value_leading_space | 分摊 ap_id 改为 `" AP01"` | 0 | 质量通过；已知应付关联净额 0；缺失应付关联净额 500000 分；`ap_id_not_in_ledger` 500000 |
| B09_boolean_payment_ids | 付款主键与分摊引用改为 True | 1 | `ID_TYPE_INVALID` ×2（payments.payment_id、allocations.payment_id） |
| B10_boolean_nullable_id | 可空 original_allocation_id 改为 True | 1 | `ID_TYPE_INVALID` 定位 allocations.original_allocation_id |
| P05_leading_zero_text_ids_accepted | 付款与分摊 ID 同改为文本 `0001` | 0 | 通过；勾稽相等 |
| B11_numeric_ids_rejected | 付款与分摊 ID 改为数值 1 | 1 | `ID_TYPE_INVALID` ×2（数值不能靠显示格式当文本） |
| B06_both_amounts_NA | 付款与分摊金额同改 `N/A` | 1 | `AMOUNT_INVALID` ×2；不可用单元格 2；payments/allocations 完整总额 null；已知小计 0；NOT_ASSESSED；比较字段 null |
| B07_both_amounts_blank | 两个金额同时清空 | 1 | `MISSING_REQUIRED_VALUE` ×2；不可用 2；完整总额 null；已知小计 0；NOT_ASSESSED |
| B08_both_amounts_formula | 两个金额同改 `=5000` | 1 | `FORMULA_NOT_ALLOWED` ×2；不可用 2；完整总额 null；NOT_ASSESSED |
| B12_zero_amounts | 两个金额同改 `0.00` | 1 | `AMOUNT_NOT_POSITIVE` ×2；不可用 2；完整总额 null |
| B13_negative_amounts | 两个金额同改数值 `-100` | 1 | `AMOUNT_NOT_POSITIVE` ×2；不可用 2；NOT_ASSESSED |
| P01_intact_c01 | 未改动 C01 副本 | 0 | 无问题；三表完整金额均 500000 分；不可用 0；勾稽相等 |
| P02_intact_c07b | 原 C07b | 0 | 总体资金 500000 分；已知关联 300000 分；缺失关联 200000 分；`empty_ap_id` 200000；勾稽相等 |
| B14_c14a_missing_amount_column | 原 C14a（缺 payable_amount 列） | 1 | `REQUIRED_COLUMN_MISSING`；payables 完整总额与已知小计均 null；`unmapped_amount_columns` 含 `payables_payable_amount`；NOT_ASSESSED |
| R16_report_overwrite_guard | 同一报告路径连跑两次 | 第二次 2 | 首次 0 且报告生成；第二次拒绝覆盖（退出码 2） |
| MAIN_erp_export | 原主工作簿 | 0 | 四表行数 20/993/1000/1005；不可用 0；三表完整金额非 null；勾稽 ASSESSED 且相等；已结算 PAY 267949329 分、已结算退款 700000 分、缺失应付关联净额 1000000 分 |
| FIXTURE_C01…C14e（22 项） | 原 fixture 逐份 | 14×0、8×1 | 8 份阻断均含预期主要代码（C11 `SETTLED_BANK_REFERENCE_DUPLICATE`、C12 `ALLOCATION_SUM_MISMATCH`、C13 `REFUND_EXCEEDS_ORIGINAL`、C14a `REQUIRED_COLUMN_MISSING`、C14b `PRIMARY_KEY_DUPLICATE`、C14c `AMOUNT_INVALID`、C14d `DATE_INVALID`、C14e `AMOUNT_SCALE_INVALID`） |

回归脚本自带的只读输入保护结果：`protected_inputs_unchanged = true`（26 个只读输入前后哈希一致）。

### 4.1 复跑 GPT 报告的九份边界输入

用返修后校验器复跑 `data\reviews\task002_20261011_052857\boundary_inputs\` 的九份副本（只读，未改动），结果与要求逐条一致：

| 验收编号 | 旧行为 | 返修后实际 |
| --- | --- | --- |
| B01 付款日期清空 | 退出 0、result=pass | 退出 **1**，`MISSING_REQUIRED_VALUE`（payments.payment_date） |
| B02 应付日期清空 | 退出 0、result=pass | 退出 **1**，`MISSING_REQUIRED_VALUE`（payables.ap_date） |
| B03 原生 datetime 12:34:56 | 退出 0，静默丢时间 | 退出 **1**，`DATE_TIME_COMPONENT_PRESENT` |
| B04 表头 `ap_id ` | 退出 0，且 500000 分被误列缺失关联 | 退出 **1**，`REQUIRED_COLUMN_MISSING`（ap_id 未映射，行未丢） |
| B05 分摊 ap_id `" AP01"` | 退出 0，但被偷偷匹配成已知关联 | 退出 **0**（允许），已知关联 0、缺失关联 500000 分 |
| B06 两个金额 `N/A` | 退出 1，但完整金额 0、勾稽 true | 退出 **1**，不可用单元格 2、完整总额 null、已知小计 0、NOT_ASSESSED、比较字段 null |
| B07 两个金额清空 | 退出 1，完整金额 0、勾稽 true、不可解析计数 0 | 退出 **1**，不可用 2（`MISSING_REQUIRED_VALUE`）、null、NOT_ASSESSED |
| B08 两个金额公式 | 退出 1，完整金额 0、勾稽 true、计数 0 | 退出 **1**，不可用 2（`FORMULA_NOT_ALLOWED`）、null、NOT_ASSESSED |
| B09 布尔 payment_id | 退出 0、无类型问题 | 退出 **1**，`ID_TYPE_INVALID` ×2 |

---

## 5. 只读文件、输入与依赖核对

- **回归内建核验**：主输入、22 份原 fixture、`docs\SPEC_V1.md`、`docs\tasks\TASK-002-R1.md`、`docs\reviews\REVIEW_TASK_002.md`、`docs\EXEC_REPORT_002.md`、`scripts\make_demo_data.py` 共 26 个只读输入，整轮回归前后哈希一致。
- **对 GPT 记录的 94 个文件重新计算哈希**：93 个与 GPT 的 `source_hashes_after.json` **逐字节一致**；唯一变化的是 `scripts\check_demo_data.py`（本卡授权修改）。GPT 证据目录自身的 `source_hashes_before.json` 与 `source_hashes_after.json` 完全相同（差集为 0），说明其本轮也未改动这些文件。
- **主输入未变**：`data\generated\demo_20260930_a\input\erp_export.xlsx` = `f86c3f65ee5dbac064fc2b6fc04e061ffd10914f4d1a49499a54c1cf52691252`，与 `EXEC_REPORT_002.md` 记录一致。
- **依赖未变**：Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9；本轮未执行任何 `pip install`／升级。
- **项目 Git 仍未初始化**（`.git` 不存在），本轮未初始化。

---

## 6. 完整执行命令与实际退出码

变量定义（后续命令均使用这些完整路径，无省略号）：

```powershell
$py   = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$chk  = 'D:\harness work\audit_sa_project\scripts\check_demo_data.py'
$test = 'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py'
$a    = 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a'
$r1   = 'D:\harness work\audit_sa_project\data\generated\task002_r1_01'
$bnd  = 'D:\harness work\audit_sa_project\data\reviews\task002_20261011_052857\boundary_inputs'
```

### 6.1 语法检查

```powershell
& $py -m py_compile $chk
& $py -m py_compile $test
```

退出码均为 **0**。

### 6.2 复跑 GPT 的九份边界输入（报告写入新目录，未覆盖旧证据）

```powershell
Get-ChildItem $bnd -File | Sort-Object Name | ForEach-Object {
  $name = $_.BaseName
  & $py $chk --workbook $_.FullName --report "$r1\recheck_boundary\$name.json"
  Write-Output "$name exit=$LASTEXITCODE"
}
```

退出码依次为：B01 **1**、B02 **1**、B03 **1**、B04 **1**、B05 **0**、B06 **1**、B07 **1**、B08 **1**、B09 **1**。

### 6.3 基线复跑：主文件（返修卡第 5 节示例路径）

```powershell
& $py $chk --workbook "$a\input\erp_export.xlsx" --report "$r1\baseline_reports\main.json"
```

退出码 **0**；四表来源行数 20/993/1000/1005；问题数 0；不可用金额单元格 0；完整金额 `payables_payable_amount=267849329`、`payments_amount=270149329`、`allocations_allocated_amount=270149329`（整数分）；勾稽状态 `ASSESSED`。

### 6.4 基线复跑：22 份原 fixture

```powershell
$cases = @('C01','C02','C03','C04','C05','C06','C07','C08','C09','C10','C11','C12','C13','C06b','C07b','C09b','C10b','C14a','C14b','C14c','C14d','C14e')
foreach ($c in $cases) {
  & $py $chk --workbook "$a\fixtures\$c.xlsx" --report "$r1\baseline_reports\$c.json"
  Write-Output "$c exit=$LASTEXITCODE"
}
```

退出码：C01—C10 **0**；C11、C12、C13 **1**；C06b、C07b、C09b、C10b **0**；C14a—C14e **1**。合计 **14 个 0、8 个 1**。

### 6.5 新增回归验证（42 个用例）

```powershell
& $py $test --out-dir "$r1\regressions"
```

退出码 **0**；输出“用例总数 42，通过 42，失败 0”“只读输入前后哈希一致: True”。完整参数数组见 `$r1\regressions\command_log.json`。

### 6.6 其他核验命令

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' -Algorithm SHA256
```

退出码均为 **0**。另有两次内联（标准输入）脚本：一次比对 GPT 的 94 个文件哈希、一次整理证据目录结构；均以 `@' … '@ | & $py -` 方式执行，未新增 `.py` 文件。

---

## 7. 偏差、失败尝试与修复过程

1. **本轮无失败执行**：语法检查、九份边界复跑、回归验证（42 项）、主文件与 22 份 fixture 基线复跑，全部一次通过；因此没有“失败后重跑”的记录可报。此前 TASK-002 的两处失败（fixture 缺默认主数据、C14a 缺列崩溃）仍保留在 `dev_try_01` 与原回执中，本卡未修改它们。
2. **回归脚本在运行前的两处实现问题**（静态检查发现、运行前修正，未产生失败运行）：
   - 造副本辅助函数最初把所有编辑都写到第 2 行，表头用例（B04）会改错位置；改为区分数据行编辑与 `header_edits` 表头编辑；
   - 基线报告最初会写进 `reports\`，与边界用例混在一起；改为写入独立的 `baseline_reports\`。
3. **`py_compile` 产生的缓存**：`scripts\__pycache__`、`tests\__pycache__` 属非授权产物，已删除；`scripts\` 现只有两个授权源码文件，`tests\` 只有一个授权测试文件。
4. **未做“为让检查通过”的调整**：未改动规格、答案册、生成器、原 fixture 或原主工作簿；所有修复都在本卡授权文件内完成。B05 这类“允许保留的业务线索”仍是**通过**，没有被一刀切禁止未知 `ap_id`。
5. **一处文档口径**：文本形式的负数（如 `-1.00`）按第一版的严格正数格式判为 `AMOUNT_INVALID`；数值形式的负数（如 `-100`）判为 `AMOUNT_NOT_POSITIVE`。两者都阻断并计入不可用金额单元格，仅代码不同，回归脚本对两种形式都做了覆盖。

## 8. 尚未通过项、限制与停止状态

- 未执行（因此不主张通过）：R01—R04 检测引擎、SQL、SQLite 入库、业务状态机、Gate 1／Gate 2、AI 审计建议、正式契约、Git 初始化、RAG、OCR、百万行压测、真实 ERP 接入；**也未统计召回率与误报率**。
- 已知限制：`issues[*].severity` 仍统一 `blocking`，未做分级；勾稽采用“有任一问题即 NOT_ASSESSED”的保守方案，未实现依赖图级的精细判定；`demo_20260930_a\checks\` 中的旧报告仍保留旧字段语义，未重新生成（作为 R0 证据）。
- 本卡范围内工作已停止：未启动 TASK-003，未修改任务一／任务二的只读文件，**未自行宣布 TASK-002 最终验收通过**。
- 等待主理人将本回执与 `data\generated\task002_r1_01\` 证据目录转交总架构师复验。
