# 标准化核心说明（TASK-004）

版本：TASK-004-normalized-1.1（TASK-004-R1 起）；日期：2026-10-11；执行端：DeepSeek；依据：`docs/tasks/TASK-004_DRAFT.md`、`docs/tasks/TASK-004-R1.md`、`docs/reviews/REVIEW_TASK_004.md`、`docs/SPEC_V1.md` 第 2—4 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2、3、5 节。

本文说明开发态标准化核心的**数据结构、类型与金额单位、来源定位、JSON 原值编码、勾稽口径、实际测试命令**，以及它**尚未**接入业务批次／审批／数据库的边界。

> 本模块是 `DEVELOPMENT_TEST_ONLY`：未接入任何业务批次，不构成 Gate 1／Gate 2 批准，也不代表契约生效。

---

## 1. 公共 API

函数签名：

```python
def normalize_workbook(workbook_path: Path, quality_report: dict) -> dict: ...
```

合法调用示例：

```python
from scripts.normalize_demo_data import normalize_workbook

result = normalize_workbook(workbook_path, quality_report)
```

- 读取工作簿、返回**内存中的**标准化结果字典；**不写回工作簿、不创建批次、不代签批准**。
- 质量报告由调用方提供；测试驱动用真实 checker CLI 对当前输入副本重新生成（不得使用旧 `checks`、答案册或生成器内存数据）。
- 返回值为 JSON 可序列化字典，并在返回前用 `json.dumps(..., allow_nan=False)` 校验（**不使用 `default=str` 兜底串化**）。
- 异常类型（两种，语义不同）：
  - `NormalizationBlocked`：输入不满足“可转换”前提——报告不是可用对象、结构无效、`result` 不是 `pass`、存在 issues、报告与输入或冻结 checker 不匹配、勾稽不是 `ASSESSED`、存在隔离行或结构阻断，以及**本层消费的报告字段缺失或类型不符**（给出字段路径）。**不转换、不产出标准数据。**
  - `NormalizationError`：运行或一致性错误——文件读取或打开失败、字段解析失败、表头列位置与报告不一致、转换后输入哈希读取失败或变化、报告与标准记录的对照不成立、结果不可 JSON 序列化。**停止该输入，不返回成功结果。**

### 1.1 报告前提与错误语义

转换前的核对顺序：报告可用性 → 结构（复用只读接收器的 `validate_report`）→ `result=pass` 且 `issues` 为空 → 报告 `workbook.sha256` 等于当前输入字节哈希（报告与另一输入混用即拒绝）→ 报告 `checker.sha256` 等于冻结 checker → 勾稽 `ASSESSED` 且 `known_plus_missing_equals_master is True` → 四表无隔离行、接受行数等于来源业务行数 → **本层新增消费字段的类型检查**（见第 5 节）。

文件操作边界统一转成 `NormalizationError`，并保留**阶段、路径与原始异常**（可用异常链查看原错误）：

| 阶段标签 | 触发位置 |
| --- | --- |
| `read_input_hash` | 初次读取输入字节／哈希 |
| `read_checker_hash` | 初次读取冻结 checker 哈希 |
| `read_spec_hash` | 读取规格草案哈希 |
| `open_workbook` | 打开工作簿失败（含权限等） |
| 转换后核对 | 转换结束再读取输入哈希时失败或发现变化 |

失败时**不返回任何标准结果**，调用方不得落盘 `normalized.json`；文件读取失败不会被伪装成质量检查通过，报告内容错误也不会被混成文件错误。

## 2. 固定转换口径

| 项目 | 口径 |
| --- | --- |
| 处理范围 | 只处理四张固定工作表的固定字段；额外工作表与额外列**只登记**（`extra_sheets`／`extra_columns`），不擅自映射 |
| 列定位 | 用**实际表头名**定位，并与报告 `structure.sheet_field_mapping` 的列位置逐一比对；两者不一致即报错，不假定字段固定在某个列号 |
| 解析复用 | 复用冻结 checker 的 `read_text`／`parse_date_cell`／`parse_amount_cell` 与 `FIELD_SPEC`；薄封装只做接口适配，不复制业务核验；**并检查这些函数的错误返回** |
| 文本 | 非空文本原样保留：不 strip、不改大小写、不合并名称、不猜补前导零；可空字段按已验收口径转为 `None`；文字 `NULL`／`N/A`／真正文本 `#N/A` 保持文本；Excel 错误类型不等同于文本 |
| 日期 | `ap_date`、`payment_date` 标准值为 `YYYY-MM-DD` 字符串；原生日期与午夜 `datetime` 可无损转换；带非零时间或带显式时间的文本不自行截断（由 checker 口径阻断） |
| 金额 | `payable_amount` → `payable_amount_cents`、`amount` → `amount_cents`、`allocated_amount` → `allocated_amount_cents`；值为 Python `int`（非 `bool`）；**标准数据不保留同名的“元”业务字段**，原值保存在来源信息中；使用已验收 Decimal 解析所得整数分，不经 float 乘 100、不用 round 修复、不用浮点累计 |
| 业务保真 | 保留全部资金状态、付款／退款关联、空或未知 `ap_id` 及收款对象差异；退款金额仍为正数，方向由 `transaction_type` 决定 |
| 行序 | 不排序、不重编号、不合并业务行、不补造主键或分摊；输出按原工作表业务行顺序；**完全空白行**单独记录其原 Excel 行号 |

## 3. 结果结构

```jsonc
{
  "normalization_version": "TASK-004-normalized-1.1",
  "mode": "DEVELOPMENT_TEST_ONLY",
  "next_step_allowed": false,
  "source": { "input_path": "...", "input_sha256": "...", "checker_path": "scripts/check_demo_data.py",
              "checker_sha256": "...", "spec_path": "docs/SPEC_V1.md", "spec_sha256": "...",
              "path_note": "路径只是附加信息，来源身份以字节哈希为准" },
  "quality_report": { "result": "pass", "issue_counts_by_code": {}, "report_workbook_sha256": "...",
                      "report_checker_sha256": "...", "reconciliation_status": "ASSESSED" },
  "tables": { "suppliers": { "records": [...], "blank_rows": [], "extra_columns": [] },
              "payables": {...}, "payments": {...}, "allocations": {...} },
  "blank_rows": { "suppliers": [], "payables": [], "payments": [], "allocations": [] },
  "row_accounting": { "payables": { "source_rows": 993, "normalized_rows": 993, "quarantined_rows": 0,
                                    "blank_rows": 0, "report_accepted_rows": 993 }, "...": {} },
  "amount_reconciliation": { "...": "见第 5 节" },
  "extra_sheets": [],
  "scope_limits": ["..."]
}
```

每条记录：

```jsonc
{
  "data": { "allocation_id": "AL00001", "payment_id": "PM00001", "ap_id": "AP00001",
            "allocated_amount_cents": 1, "original_allocation_id": null },
  "source": { "workbook_sha256": "f86c3f65…", "sheet": "allocations", "excel_row": 2 },
  "cells": {
    "allocated_amount": {
      "excel_data_type": "s", "encoding": "str", "raw_value": "0.01", "python_type": "str",
      "input_field": "allocated_amount", "column_index": 4, "column_letter": "D", "cell": "D2",
      "target_field": "allocated_amount_cents", "standard_value": 1, "number_format": null
    }
  }
}
```

来源定位示例（可直接回答“这个整数分和这个日期来自哪个单元格”）：`AP00001` 的 `allocated_amount_cents = 1` 来自 `allocations!D2`（原值文本 `"0.01"`）；该记录同时带有工作簿哈希与 Excel 行号 2。

### 3.1 `cells` 每项保留的内容

`input_field`、`column_index`（1-based 实际列号）、`column_letter`、`cell`（单元格坐标）、`excel_data_type`（`s`/`n`/`d`/`b`/`e`/`f`）、`python_type`、`raw_value` 及其 `encoding`、`target_field`、`standard_value`，数值与日期另记 `number_format`。

### 3.2 原值编码（`encoding`）

| 情形 | encoding | raw_value |
| --- | --- | --- |
| 空单元格 | `empty` | `null` |
| 普通字符串 | `str` | 原字符串（不 strip） |
| 整数 | `int` | Python int |
| 浮点 | `float_repr` | `repr(float)` 字符串，并注明“不代表 Excel 原始 XML 字面值或显示格式” |
| 日期 / 日期时间 | `iso_date` / `iso_datetime` | ISO 字符串 |
| 布尔 | `bool` | `true`/`false` |
| Excel 错误 / 公式 | `excel_error` / `formula` | 字符串形式 |

说明：这里的“原值”是 **openpyxl 解码值**；**原始 Excel 字节副本仍是权威原始载体**，JSON 不声称能完整还原工作簿。`number_format` 只作记录，**不据它猜补 ID**。JSON 禁止 `NaN`／`Infinity`。

## 4. 逐单元格来源与哈希

- `source.workbook_sha256` 是该记录所属工作簿的字节哈希（SHA-256），逐记录重复记录，便于把任意标准值追回到具体输入字节。
- `source.excel_row` 是该记录在**原工作表**中的实际 Excel 行号（`read_only` 模式下按 `iter_rows` 顺序自行推算，不依赖空单元格对象属性）。
- 列号来自实际表头位置，因此**列顺序变化后来源坐标会跟随实际位置**；完全空白行进入 `blank_rows`，不参与记录，也不占用记录序号。

## 5. 转换勾稽（`amount_reconciliation`）

单位统一为**分**；全部从标准化记录**独立汇总**，再与本批次 checker 报告对照，不把报告数字直接复制成“转换通过”：

1. `row_accounting`：四表分别满足 来源业务行数 = 标准化行数 + 隔离行数（成功时隔离为 0），且标准化行数等于报告 `accepted_rows`；空白行单列，**四表不相加称为资金笔数**。
2. `table_totals`：三个金额字段按表独立求和，与报告 `complete_totals_cents` 相等（`normalized`／`report`／`equal` 三项并列）。
3. `payments_by_type_and_status`：**双向对照**。先从标准化付款记录独立形成类型／状态分组，再与报告分组比较**键集合**——既检查报告多出的分组，也检查**报告漏掉的实际分组**；对共有的每个分组分别核对 `count`、`known_valid_amount_cents` 与 `complete_amount_cents`。
   - **空分组对象本身不是错误**：真实没有任何付款／退款事件且 checker 通过时，实际分组与报告都为空，应正常转换（此时资金净额为 0，应付金额保留，且不要求应付总额等于付款总额）。
4. 每笔主表 `amount_cents` 等于其全部 `allocated_amount_cents` 之和（含非结算与未匹配部分）。
5. `settled_pay_master_total` = `settled_pay_allocation_total`；`settled_refund_master_total` = `settled_refund_allocation_total`。
6. `master_net` = `known_payable_link_net` + `missing_payable_link_net`；缺失部分区分 `empty_ap_id` 与 `ap_id_not_in_ledger`，两者都保留。
7. **完整净额三项对照**：独立算出的主表净额、已知应付关联净额、缺失关联净额分别与 `reconciliation.complete_totals_cents` 的 `master_net`、`known_payable_link_net`、`missing_payable_link_net` 比较；**差 1 分也必须失败**，不能只凭 `known_plus_missing_equals_master=true` 或诊断小计一致就略过。同时保留第 6 项的诊断小计与缺失分类对照。

`checks` 区段逐项记录上述布尔结果（含 `master_net_equals_report_complete`、`known_net_equals_report_complete`、`missing_net_equals_report_complete`、`payment_groups_match_report_keys`），`normalized_equals_report` 汇总是否全部一致。**任何不一致都会抛 `NormalizationError` 并给出具体分组与差异，不返回成功的完整结果。**

本层实际消费、因而必须通过类型检查的报告字段（缺失或类型不符抛 `NormalizationBlocked` 并给出字段路径；**不使用默认空对象或默认零绕过**）：

- `amount_summary.payments_by_type_and_status`（对象；每个实际分组条目为对象，且 `count`、`known_valid_amount_cents`、`complete_amount_cents` 为整数，bool 不算整数，质量通过时完整金额不可为 `null`）；
- `reconciliation.complete_totals_cents`（对象，含 `master_net`、`known_payable_link_net`、`missing_payable_link_net`，本次可转换前提下三项均为整数）；
- `reconciliation.diagnostic_known_valid_subtotals_cents` 及其 `missing_payable_link_detail`（对象，含 `empty_ap_id`、`ap_id_not_in_ledger` 整数）。

不要求应付总额等于付款总额，不将主表与分摊金额相加，不计算超付、重复足额、规则命中或损失——完整业务质量核验仍由冻结 checker 承担。

## 6. 实际测试命令

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -B `
  'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\standardization_tests\task004_r1_01'
```

- 测试容器必须是 `data\standardization_tests` 内**尚不存在**的子目录；越界、指向该目录本身或已存在时在写入前退出 2。
- 每个输入使用独立子目录，保存输入副本、新 checker 报告、逐次调用日志；**只有转换成功的输入**才写 `normalized.json`。
- 覆盖 **47 个输入**（数量按实际运行统计）：
  - 主演示文件、22 份既有 fixture（14 份可转换 / 8 份阻断）；
  - **9 个开发小样**：标识保真、精确小额、日期与空白行与列顺序、输入／报告错配、报告不可用（`null`／空对象／质量阻断三类）、转换后哈希读取失败与变化；
  - **本轮新增 14 个定点回归**：报告分组整段缺失（P01）、分组置空但实际有记录（P02）、完整 `master_net` 加 1 分（P03）、`missing_payable_link_detail` 非对象（P04）、四类文件操作失败（P05—P08：初始输入读取、工作簿打开、SPEC 读取、checker 读取）、只删单个分组的漏项、完整 known／missing 净额各加 1 分、完整净额字段缺失与置 `null`、某分组 `complete_amount_cents` 加 1 分，以及**空付款正例**（无资金事件时分组为空仍正常转换）。
- 报告故障注入一律使用**内存副本**：原始 `checker_report.json` 保留，注入副本另存为 `injected_report.json` 并附 `injection_note.txt` 说明修改内容，**不冒称 checker 自己生成了不一致报告**。
- 退出码：0 全部符合预期；1 存在断言失败或保护失败；2 参数或环境问题。预期阻断、预期运行错误与脚本自身失败分开统计，且断言到**具体异常类与差异原因**，不只断言“抛了异常”。

## 7. 边界（尚未做，也不在本卡范围）

- 未接入任何业务批次：不读取 `data/batches` 作为处理对象，不修改任何 `batch_manifest.json`，不把既有批次变成“已标准化”。
- 未实现 SQLite 入库、R01—R04 筛查、AI 建议、判断表、正式契约、批准命令或状态机。
- 未实现业务入口所需的契约与批准指纹检查；测试核心函数**不构成 Gate 1 放行**。
- 不宣称真实性、全部业务完整性或特定 ERP 模板兼容性已经验证；`scope_limits` 会随结果一起返回。
- 来源为 openpyxl 解码值，原始字节副本才是权威载体。
