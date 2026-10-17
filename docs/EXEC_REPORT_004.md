# TASK-004 执行回执（开发态标准化核心、逐单元格溯源与转换勾稽）

任务：开发标准化核心与开发测试——读取合成工作簿与匹配的质量报告，把四表转换为确定的数据类型，保存每个固定字段的逐单元格来源，并核对转换前后数量与金额。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-004_DRAFT.md`、`docs/reviews/REVIEW_TASK_003_R3.md`、`docs/SPEC_V1.md` 第 2—4 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 2、3、5 节。
状态：本卡范围内工作完成并自检通过，**停止于此**；未接入既有接收批次，未做 SQLite／筛查，未推进任务五。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| 公共 API | `normalize_workbook(workbook_path: Path, quality_report: dict) -> dict`；只提供 Python API，**无面向业务批次的 CLI**，不写回工作簿、不建批次、不代签批准 |
| 异常语义 | `NormalizationBlocked`（前提不成立：报告不可用／质量未通过／报告与输入不匹配等）与 `NormalizationError`（运行／一致性错误：读取、解析、列位置、哈希变化、勾稽不成立）分开 |
| 前提核对 | 复用只读接收器的 `validate_report`；要求 `result=pass`、`issues` 为空、报告哈希与输入及冻结 checker 一致、勾稽 `ASSESSED` 且相等、四表无隔离行；转换后再核对输入哈希 |
| 转换口径 | 文本原样保留（不 strip／不改写／不补零）；日期转 `YYYY-MM-DD`；三个金额字段改为 `*_cents` 且为 Python `int`，**标准数据不保留“元”字段**；不排序、不合并、不补造；完全空白行单独记录原行号 |
| 逐单元格来源 | 每条记录含 `data`／`source`（工作簿哈希、sheet、原 Excel 行号）／`cells`（输入字段、实际列号与坐标、Excel data_type、Python 类型、原值与编码、目标字段与标准值） |
| 转换勾稽 | 行数、三表金额、逐事件分摊、已结算 PAY／REFUND 主表与分摊、主表净额＝已知＋缺失关联净额，全部从标准记录独立汇总并与 checker 报告对照；不一致即 `NormalizationError` |
| 开发验证 | **32 个输入全部符合预期，测试失败 0**：转换 **18**、预期阻断 **12**、预期运行错误 **2**；checker CLI 调用 **32** 次；测试进程退出 **0** |
| 冻结源码 | checker `a7e5eb67…`、接收器 `52195620…`、生成器 `e899aa2f…`、任务二／三回归脚本、规格与契约草案全部未变 |
| 既有文件保护 | 对 R3 验收基线 **4902 个文件**复核：**0 个变化、0 个缺失**；任务二基线 **874 个文件**：0 个变化；R2 复验基线 3225 个中变化的 3 个正是 R3 卡当时授权的文件 |
| 未执行 | SQLite 入库、R01—R04 筛查、AI 建议、判断表、正式契约、批准命令、状态机、真实 ERP 接入；未安装依赖、未初始化 Git |

---

## 2. 实际新增的文件

| 文件 | 当前 SHA-256 | 行数 |
| --- | --- | --- |
| `D:\harness work\audit_sa_project\scripts\normalize_demo_data.py` | `a1c4aa23ac88df77f4bc8736ba3989128ea95e537bf019062a364853d399fde4` | 593 |
| `D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py` | `4bf41b3d9581760d2ef2c1df2b70e9515bcf0c47e4cc54b7eb78c4c14e724b64` | 715 |
| `D:\harness work\audit_sa_project\docs\NORMALIZATION_GUIDE.md` | `9e6ae4d8e0cc88afc05c946878bed3dee5595ebc2d4f8e47e96e271825ee87b1` | 141 |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_004.md` | 本文件 | — |

新增测试容器（`data\standardization_tests\`）：`task004_04`（**最终**，148 个文件：`cases\` 146、`summary.json`、`command_log.json`）、`task004_03`（S6 注入位置错误的失败现场）、`task004_02`（首次运行在 `EmptyCell` 属性上崩溃的现场）。三次运行均按“不覆盖历史”保留。

未修改、未删除任何既有文件；未在旧目录补文件。

---

## 3. 公共 API 与实现要点

```python
normalize_workbook(workbook_path: Path, quality_report: dict) -> dict
```

- **前提核对（转换前）**：报告必须是字典 → `RECEIVER.validate_report()` → `result == "pass"` 且 `issues == []` → 报告 `workbook.sha256` 等于当前输入字节哈希（报告与另一输入混用即拒绝）→ 报告 `checker.sha256` 等于冻结 checker → `reconciliation.status == "ASSESSED"` 且 `known_plus_missing_equals_master is True` → 四表 `blocked_rows` 为 0、无 `structural_block`、`accepted_rows == source_rows`。结构缺失时明确阻断，**不用 `get` 默认空对象继续**。
- **复用只读脚本**：`importlib` 按路径加载冻结的 `check_demo_data.py` 与 `receive_demo_batch.py`，使用其 `FIELD_SPEC`／`read_text`／`parse_date_cell`／`parse_amount_cell`／`validate_report`；只在新模块写薄封装，未复制业务核验、未修改旧脚本。
- **列定位**：用实际表头名定位，并与报告 `structure.sheet_field_mapping` 的列位置逐字段比对，不一致抛 `NormalizationError`；不假定固定列号。
- **逐单元格来源**：`read_only` 模式下空单元格可能是 `EmptyCell`（无 `coordinate`／`number_format`），因此行号按 `iter_rows` 顺序自行推算、坐标由列字母与行号拼出、`number_format`／`data_type` 用 `getattr` 兜底。
- **勾稽**：`_reconcile()` 从标准记录独立汇总（行数、三表金额、付款类型／状态统计、逐事件分摊、已结算主表与分摊、已知＋缺失关联净额），与报告对照；任何差异抛 `NormalizationError` 并列出具体差异项。
- **收尾**：转换后再核对输入哈希（读取失败或变化都不返回成功结果）；返回前用 `json.dumps(..., allow_nan=False)` 校验可序列化且无 `NaN`／`Infinity`。

## 4. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 4.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\normalize_demo_data.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py'
```

退出码均 **0**（`-B` 与 `PYTHONDONTWRITEBYTECODE=1` 避免在旧证据目录写入 `__pycache__`）。

### 4.2 标准化开发验证（最终）

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' --out-dir 'D:\harness work\audit_sa_project\data\standardization_tests\task004_04'
```

退出码 **0**；输出“输入 32 个：转换 18、预期阻断／错误 14；checker CLI 调用 32 次；测试失败 0”“受保护文件前后哈希一致: True（32 个）”。

### 4.3 其他核验

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\normalize_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\NORMALIZATION_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于与既有基线比对哈希、核对标准化结果与容器计数；未新增 `.py` 文件。

---

## 5. 实际结果与具体断言

### 5.1 统计（从实际结果计算）

| 项目 | 数量 |
| --- | --- |
| 输入总数 | **32** |
| 转换成功（产出 `normalized.json`） | **18** |
| 预期阻断（`NormalizationBlocked`，无 `normalized.json`） | **12** |
| 预期运行错误（`NormalizationError`，无 `normalized.json`） | **2** |
| checker CLI 调用 | **32**（每次 stdout／stderr 独立保存，`command_log.json` 记录完整参数与退出码） |
| 测试失败 | **0** |

转换成功的 18 个：主演示文件 + C01、C02、C03、C04、C05、C06、C07、C08、C09、C10、C06b、C07b、C09b、C10b + `S1_identifier_fidelity`、`S2_small_amounts`、`S3_dates_blank_row_column_order`。
预期阻断的 12 个：C11、C12、C13、C14a、C14b、C14c、C14d、C14e + `S4_input_report_mismatch`、`S5_report_unusable_null`、`S5_report_unusable_empty_object`、`S5_report_quality_blocked`。
预期运行错误的 2 个：`S6_after_hash_read_failure`、`S6_after_hash_changed`。

### 5.2 主演示文件

| 断言 | 实测 |
| --- | --- |
| 四表转换行数 | 20 / 993 / 1000 / 1005 |
| 未知关联净额 | 1 000 000 分 |
| 已知关联净额 | 266 249 329 分 |
| 主表净额 | 267 249 329 分 |
| 三表金额与报告对照 | `payables_payable_amount` 267 849 329、`payments_amount` 270 149 329、`allocations_allocated_amount` 270 149 329，三项 `equal=true` |
| `checks` 全部通过 | true（含已结算 PAY／REFUND 主表＝分摊、主表净额＝已知＋缺失） |
| `normalized_equals_report` | true |
| 标准数据 | 无“元”金额字段；金额标准值均为 `int` |
| 模式 | `mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed=false` |
| 来源 | `source.input_sha256` 等于输入文件字节哈希 `f86c3f65…` |

逐单元格来源抽样（主文件）：分摊记录 `AL00001` 的标准值 `allocated_amount_cents = 1` 来自 `allocations!D2`，原值为文本 `"0.01"`（`encoding=str`、`excel_data_type=s`），并带 `workbook_sha256` 与原行号 2；`ap_id` 来源同为 `C2`、`encoding=str`、`target_field=ap_id`。

### 5.3 14 份质量有效 fixture

全部转换成功，各自 `checks` 全通过、无“元”字段、金额为 `int`、checker 退出 0；其中 C01 净额 500 000 分，C03（一笔付款分摊到两张应付）净额 1 000 000 分。

### 5.4 8 份质量阻断 fixture

全部 `NormalizationBlocked`、**无 `normalized.json`**、checker 退出 1、保留原问题代码；C14c 仍报 `AMOUNT_INVALID`（未补零）、C14e 仍报 `AMOUNT_SCALE_INVALID`（未四舍五入）。

### 5.5 保留行为的定点断言

| 用例 | 断言 |
| --- | --- |
| C07 | `allocations[0].ap_id is None`（空关联原样保留） |
| C08 | `allocations[0].ap_id == "AP_MISSING"`（台账外标识原样保留） |
| C09 | 付款对象 `S002` 与应付供应商 `S001` 差异保留；分摊金额 500 000 分 |
| C06 | 存在 `original_payment_id == "P02"` 的 REFUND 与 `original_allocation_id == "A02"` 的退款分摊；退款金额仍为正数 |
| C10 | 三种非结算状态 `FAILED/PENDING/VOIDED` 保留；已结算资金总额为 0 |

### 5.6 开发小样

| 小样 | 断言与实测 |
| --- | --- |
| `S1_identifier_fidelity` | 首尾空格 ID `" AP01 "` 原样保留；前导零付款 ID `"0001"` 保留；文字 `NULL`、`N/A` 与**真正文本** `#N/A`（`excel_data_type=s`）均保留为文本；`cells` 编码为 `str` 且 `raw_value` 与原文一致 |
| `S2_small_amounts` | 应付 0.30 元 → 30 分；两笔付款（数值 `0.1` 与文本 `"0.20"`）→ 10 与 20 分；两条分摊 → 10 与 20 分；净额精确 30 分；标准数据无浮点金额字段；数值金额来源编码 `float_repr`、文本金额编码 `str` |
| `S3_dates_blank_row_column_order` | 原生日期 → `"2026-09-05"`；午夜日期时间 → `"2026-09-10"`；suppliers 完全空白行记录为 `blank_rows=[3]`，其后记录 `excel_row=4`；payments 列顺序改变后 `amount` 列号 7、`currency` 列号 6 跟随实际位置；行数未丢；勾稽仍成立 |
| `S4_input_report_mismatch` | C01 报告配 C02 字节输入 → `NormalizationBlocked`（原因含“不匹配”），无 `normalized.json` |
| `S5_report_unusable_*` | 报告为 `None`、空对象或质量阻断报告 → 均 `NormalizationBlocked`，未被默认值变成成功结果 |
| `S6_after_hash_read_failure` / `S6_after_hash_changed` | 仅针对输入文件第 2 次读取注入（转换后核对）：分别抛 `NormalizationError`（“无法读取输入哈希”／“发生变化”），不返回成功结果、无 `normalized.json` |

## 6. 保护结果

- 受保护文件 **32 个**（冻结 checker、接收器、生成器、任务二／三回归脚本、规格、契约草案、旧回执、主演示输入与 22 份 fixture）在测试前后哈希全部一致；被验证模块 `normalize_demo_data.py` 与冻结 checker 亦在测试前后一致。
- 对三份 GPT 基线复核：**R3 验收基线 4902 个 → 0 变化、0 缺失**；任务二 R2 基线 **874 个 → 0 变化**；R2 复验基线 3225 个中变化的 3 个正是 R3 卡当时授权的接收器、接收测试与接收说明（本卡未再改动它们）。
- 冻结版本实测：checker `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8`、接收器 `5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6`、生成器 `e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`、规格 `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236`、契约草案 `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27`。
- 依赖未变（Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未执行 `pip install`；Git 未初始化；本次运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 7. 失败尝试与修复过程

1. **测试脚本语法错误**：`C14c/C14e` 两条断言的多行 lambda 续行非法，`py_compile` 报 `SyntaxError: invalid syntax` → 改为单行布尔表达式后通过。该次失败发生在创建容器之前，未留下目录。
2. **`AttributeError: 'EmptyCell' object has no attribute 'coordinate'`**：`read_only=True` 下空单元格没有 `coordinate`／`number_format` → 行号改为按 `iter_rows` 顺序自行推算、坐标由列字母与行号拼出、属性读取用 `getattr` 兜底。现场保留在 `task004_02`。
3. **S6 注入位置错误**：最初补丁对所有 `read_file_bytes` 调用计数，导致第 2 次调用命中“冻结 checker 哈希读取”而不是“转换后输入哈希”，在 `frozen_checker_sha256()` 处就抛错 → 改为**按路径与出现次数**注入，只命中输入文件的第 2 次读取。现场保留在 `task004_03`。
4. **运行前发现的两处设计问题**（未产生失败运行）：`report_override=None` 无法表达“显式传入 `None`” → 增加哨兵对象；S3 原设计在 payments 表插入重复数据行会触发主键重复导致无法转换 → 改为在 suppliers 表插入空白行并另加一条有效主数据，同时保留 columns 重排验证。
5. 未为便于导入或通过断言修改任何旧脚本、规格、契约、原数据或既有批次。

## 8. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：SQLite 入库、R01—R04 筛查、AI 审计建议、判断表、正式契约、批准命令、业务状态机、RAG、OCR、百万行压测、真实 ERP 接入。
- 已知限制：报告结构检查覆盖接收入口消费的字段，不等同于完整通用 schema 验证；来源为 openpyxl 解码值，原始 Excel 字节副本才是权威载体；不宣称真实性、全部业务完整性或特定 ERP 模板兼容性；“元”字段不进入标准数据，只保留在来源信息中；四表行数不相加称为资金笔数。
- 本卡范围内工作已停止：未将任何既有接收批次推进到下一状态，未读取 `data/batches` 作为处理对象，未修改任何旧 `batch_manifest.json`，未实现契约／批准指纹检查，也**未宣称已实现 Gate 1／Gate 2 放行**。
- 等待主理人把本回执与 `docs/NORMALIZATION_GUIDE.md`、`data\standardization_tests\task004_04` 转交总架构师验收。
