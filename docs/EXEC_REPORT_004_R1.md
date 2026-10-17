# TASK-004-R1 执行回执（补齐报告对照与 API 错误分类）

任务：修复 TASK-004 验收发现的两类边界——A 报告对照遗漏（分组漏项、完整净额不一致仍能成功、嵌套类型错误抛裸异常）、B 公共 API 的文件操作错误未按约定分类。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-004-R1.md`、`docs/reviews/REVIEW_TASK_004.md`、`docs/tasks/TASK-004_DRAFT.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未接入 `data/batches`，未做 SQLite 或筛查，未推进任务五。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧回执 `EXEC_REPORT_004.md` 未回写，其两处说明修正记录在本回执第 7 节。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| A1 消费字段类型检查 | 新增 `_check_consumed_report_fields()`：`payments_by_type_and_status`（对象，条目内 `count`／`known_valid_amount_cents`／`complete_amount_cents` 为整数）、`reconciliation.complete_totals_cents` 三项整数、诊断小计与 `missing_payable_link_detail` 两项整数；缺失或类型不符抛 **`NormalizationBlocked`** 并给出**字段路径**，不再抛裸 `KeyError`／`AttributeError` |
| A2 分组双向对照 | 从标准付款记录独立形成分组，与报告比较**键集合**（含报告漏项与多项），并对共有分组分别核对数量、已知金额、完整金额；不一致抛 **`NormalizationError`** 并列出具体分组与差异。**空分组对象本身不是错误** |
| A3 完整净额对照 | 独立算出的 `master_net`／`known_payable_link_net`／`missing_payable_link_net` 分别与报告 `complete_totals_cents` 三项对照，**差 1 分即失败**；保留既有诊断小计与缺失分类对照 |
| B 文件错误分类 | `read_input_hash`、`read_checker_hash`、`read_spec_hash`、`open_workbook` 四个边界统一转为 **`NormalizationError`**，保留阶段、路径与原始异常（异常链）；转换后输入哈希失败／变化的既有处理保持不变 |
| 开发验证 | 原 32 输入全部重跑通过；**共 47 个输入全部符合预期，测试失败 0**：转换 **19**、预期阻断 **16**、预期运行错误 **12**；checker CLI 调用 **47** 次；测试进程退出 **0** |
| 版本 | 结果版本提升为 `TASK-004-normalized-1.1`（新增三项完整净额对照与分组键对照；字段含义未变），说明文档已同步 |
| 冻结文件 | checker `a7e5eb67…`、接收器 `52195620…`、生成器 `e899aa2f…`、任务二／三回归脚本、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| 既有文件保护 | TASK-004 验收基线 **5819 个文件**：**3 个变化（恰为本卡授权文件）、0 个缺失**；R3 验收基线 **4902 个**、任务二基线 **874 个**：均 0 个变化 |
| 未执行 | SQLite 入库、R01—R04 筛查、AI 建议、判断表、正式契约、批准命令、状态机、真实 ERP 接入；未安装依赖、未初始化 Git |

---

## 2. 实际修改与新增

### 2.1 修改（本卡授权的三个文件）

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\normalize_demo_data.py` | `a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310` |
| `D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py` | `afb1ea647cb3a1b70f847e94f50e78ef1b09464cd8834bfeac708cee6344a7ed` |
| `D:\harness work\audit_sa_project\docs\NORMALIZATION_GUIDE.md` | `ecd85127f77bea04ac12898cd04ba2385a321ae58890b26e754f95c915f86217` |

### 2.2 新增

| 路径 | 说明 |
| --- | --- |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_004_R1.md` | 本回执 |
| `D:\harness work\audit_sa_project\data\standardization_tests\task004_r1_02` | **最终 R1 验证容器**（229 个文件：`cases\` 227、`summary.json`、`command_log.json`） |
| `D:\harness work\audit_sa_project\data\standardization_tests\task004_r1_01` | 上一版（`1.0` 版本串）的 47 例运行现场，保留 |
| `D:\harness work\audit_sa_project\data\standardization_tests\task004_r1_smoke` | 实现过程中的两次单点冒烟（C01 正常、空付款正例），保留 |
| `D:\harness work\audit_sa_project\data\standardization_tests\task004_04`、`task004_02`、`task004_03` | 任务四原现场，全部原样保留 |

未覆盖、未删除任何旧容器、旧回执、GPT 证据或既有批次。

---

## 3. 两类修复的落点

### A. 只补本层消费的报告核对

- **A1 明确阻断**：新增 `_get_required`／`_as_object`／`_as_int`／`_check_consumed_report_fields`。`_as_int` 把 `bool` 视为非整数、不接受 `null`；所有缺失与类型错误都由 `NormalizationBlocked` 给出**字段路径**（例如 `reconciliation.complete_totals_cents.master_net`），不抛裸 `KeyError`／`AttributeError`，也不用默认空对象或零绕过。检查范围只限本层实际消费的字段：`amount_summary.payments_by_type_and_status`、`reconciliation.complete_totals_cents`、`reconciliation.diagnostic_known_valid_subtotals_cents` 及其 `missing_payable_link_detail`。
- **A2 双向分组对照**：`_reconcile()` 先独立构造 `{类型/状态: {count, amount_cents}}`，再与报告分组比较 `set(actual) - set(report)`（**报告漏项**）与 `set(report) - set(actual)`（报告多项）；共有分组逐一核对 `count`、`known_valid_amount_cents`、`complete_amount_cents`。差异写入 `differences` 并抛 `NormalizationError`，`normalized_equals_report` 不再可能为 `true`。空分组对象合法：实际无资金事件时两侧都是空集合，正常转换。
- **A3 完整净额对照**：新增三项比较（`master_net`／`known_payable_link_net`／`missing_payable_link_net` 对 `reconciliation.complete_totals_cents`），并把 `master_net_equals_report_complete`、`known_net_equals_report_complete`、`missing_net_equals_report_complete`、`payment_groups_match_report_keys` 记入 `checks`。**不自动修补报告数字，也不把报告数字复制成计算结果。**

### B. 文件操作错误遵守 API 约定

- 新增 `_file_error(stage, path, exc)`：把原始异常类型与消息写入 `NormalizationError` 的消息与 `reasons`（含 `阶段=`、`路径=`、`原始异常=`），并用 `raise ... from exc` 保留异常链。
- 四个边界统一处理：初次读取输入字节／哈希（`read_input_hash`）、初次读取冻结 checker 哈希（`read_checker_hash`）、读取规格哈希（`read_spec_hash`）、打开工作簿（`open_workbook`）；规格哈希改为在校验后立即读取并复用，不再在结果拼装时裸调用。
- 转换结束的输入哈希失败／变化处理保持原样（不放宽原断言）；失败一律不返回标准结果，调用方不落盘 `normalized.json`；文件读取失败不会被伪装成质量检查通过。

---

## 4. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 4.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\normalize_demo_data.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py'
```

退出码均 **0**。

### 4.2 最终验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' --out-dir 'D:\harness work\audit_sa_project\data\standardization_tests\task004_r1_02'
```

退出码 **0**；输出“输入 47 个：转换 19、预期阻断／错误 28；checker CLI 调用 47 次；测试失败 0”“受保护文件前后哈希一致: True（32 个）”。

### 4.3 其他核验

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\normalize_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_normalize_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\NORMALIZATION_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结果统计；未新增 `.py` 文件。

---

## 5. 实际结果与具体断言

### 5.1 统计（从实际结果计算）

| 项目 | 数量 |
| --- | --- |
| 输入总数 | **47**（原 32 + 本轮新增 15 个 R1 用例） |
| 转换成功（产出 `normalized.json`） | **19**（原 18 + 空付款正例） |
| 预期阻断（`NormalizationBlocked`） | **16** |
| 预期运行错误（`NormalizationError`） | **12** |
| 预期负向合计 | **28** |
| checker CLI 调用 | **47**（每次 stdout／stderr 独立保存） |
| 测试失败 | **0** |

原 32 个输入（主文件、22 份 fixture、9 个既有小样）全部重跑通过，断言未放宽。

### 5.2 本轮新增 15 个用例的实际异常类型与对照结果

| 用例 | 注入方式 | 期望／实际 | 关键断言 |
| --- | --- | --- | --- |
| `R1_P01_report_groups_missing` | 内存副本删除 `amount_summary.payments_by_type_and_status` | `NormalizationBlocked`／**blocked** | 原因含字段名与“缺失”，非裸 `KeyError` |
| `R1_P02_report_groups_empty_but_actual` | 该对象置为 `{}`（C01 实际有一笔已结算 PAY） | `NormalizationError`／**error** | 原因含“报告漏掉实际付款分组”；`normalized_equals_report` 不可能为 true |
| `R1_P03_report_complete_master_net_plus1` | `complete_totals_cents.master_net` 加 1 分 | `NormalizationError`／**error** | 原因含“完整净额 master_net” |
| `R1_P04_report_detail_not_object` | `missing_payable_link_detail` 换成非空数组 | `NormalizationBlocked`／**blocked** | 原因含该字段路径与“必须是对象”，非裸 `AttributeError` |
| `R1_P05_initial_input_read_failure` | 输入路径第 1 次读取抛 `PermissionError` | `NormalizationError`／**error** | 阶段 `read_input_hash`、路径与 `PermissionError` 均在 `reasons` |
| `R1_P06_open_workbook_failure` | `load_workbook` 抛 `PermissionError` | `NormalizationError`／**error** | 阶段 `open_workbook` |
| `R1_P07_spec_read_failure` | SPEC 读取抛 `PermissionError` | `NormalizationError`／**error** | 阶段 `read_spec_hash` |
| `R1_P08_checker_read_failure` | 冻结 checker 读取抛 `PermissionError` | `NormalizationError`／**error** | 阶段 `read_checker_hash` |
| `R1_groups_partial_omission` | 主文件报告仅删除 `PAY/PENDING` 分组 | `NormalizationError`／**error** | 发现漏项且原因含具体分组名（不只覆盖“整段为空”） |
| `R1_complete_known_payable_link_net_plus1` | 完整 `known_payable_link_net` 加 1 分 | `NormalizationError`／**error** | 发现 1 分差异 |
| `R1_complete_missing_payable_link_net_plus1` | 完整 `missing_payable_link_net` 加 1 分 | `NormalizationError`／**error** | 发现 1 分差异 |
| `R1_complete_master_net_missing` | 删除完整 `master_net` 字段 | `NormalizationBlocked`／**blocked** | 字段缺失不得成功 |
| `R1_complete_master_net_null` | 完整 `master_net` 置 `null` | `NormalizationBlocked`／**blocked** | `null` 不接受 |
| `R1_group_complete_amount_plus1` | `PAY/SETTLED` 分组只改 `complete_amount_cents` 加 1 分 | `NormalizationError`／**error** | 原因含“完整金额” |
| `R1_empty_payments_positive` | 新副本移除 payments／allocations 业务行（保留表头、供应商、应付） | **normalized**／成功 | checker 退出 0；报告分组 `{}`；资金净额 0；应付金额保留 500000 分；勾稽检查全通过 |

报告故障注入一律使用**内存副本**：原始 `checker_report.json` 保留，注入副本另存 `injected_report.json` 并附 `injection_note.txt` 说明修改内容，未冒称 checker 自己生成了不一致报告。文件类故障只在内存中替换读取函数，未改真实源码或原文件。

### 5.3 主演示文件与既有断言

主文件仍为 20／993／1000／1005 行；主表净额 267 249 329 分 = 已知关联 266 249 329 分 + 缺失关联 1 000 000 分；三表金额与报告逐项相等；`checks` 全通过（现含三项完整净额对照与分组键对照）。C01 净额 500 000 分；C03 净额 1 000 000 分；8 份阻断 fixture 仍全部未标准化；C07／C08／C09／C06／C06b／C10／C10b 的保留行为断言不变。

## 6. 保护结果

- 受保护文件 **32 个**（冻结 checker、接收器、生成器、任务二／三回归脚本、规格、契约草案、旧回执、主演示输入与 22 份 fixture）与模块哈希在测试前后全部一致。
- 基线复核：**TASK-004 验收基线 5819 个 → 3 个变化（恰为本卡授权文件）、0 个缺失**；**R3 验收基线 4902 个 → 0 个变化**；**任务二 R2 基线 874 个 → 0 个变化**。
- 冻结版本实测：checker `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8`、接收器 `5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6`、生成器 `e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`、任务二回归脚本 `555c5ef7…`、任务三回归脚本 `6374a5d7…`、规格 `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236`、契约草案 `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27`。
- 依赖未变（Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未执行 `pip install`；Git 未初始化；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 7. 说明文档修正与偏差

1. **函数签名与调用示例分开**：`NORMALIZATION_GUIDE.md` 第 1 节现在先给 `def normalize_workbook(workbook_path: Path, quality_report: dict) -> dict: ...`，再给可执行的 `result = normalize_workbook(workbook_path, quality_report)` 调用示例（此前把类型注解写进调用表达式，不能作为 Python 执行）。
2. **开发小样数量**：改为实际 **9 个**（标识保真、精确小额、日期与空白行与列顺序、输入／报告错配、报告不可用三类、转换后哈希读取失败与变化）；文中并说明 23 个主文件／fixture 输入 + 9 个小样 + 本轮新增 15 个 R1 用例 = 47。**旧 `EXEC_REPORT_004.md` 未回写**，该处勘误记录在本回执。
3. **版本串**：结果版本由 `TASK-004-normalized-1.0` 提升为 `TASK-004-normalized-1.1`（新增三项完整净额对照与分组键对照，字段含义未变），说明文档与模块同步；上一版 47 例现场保留在 `task004_r1_01`。
4. **本轮无失败执行**：两次完整验证（`1.0` 与 `1.1`）均一次通过。运行前修正了一处编辑失误——替换分组对照逻辑时误删了分组构造循环，读文件核对时发现并补回；另有两处单点冒烟（C01 正常、空付款正例）用于确认改动方向。
5. **说明文档编码修正（交付物范围内）**：更新 `NORMALIZATION_GUIDE.md` 时曾用 Windows PowerShell 5.1 的 `Set-Content -Encoding utf8` 写回，该实现会**写入 UTF-8 BOM**；内容本身完好（无 `U+FFFD`、无 NUL、行数 175），检查发现后已去掉 BOM 并重新核对，因此最终哈希为 `ecd85127…`（第 2.1 节记录的是修正后的值）。同批交付的另外三份文件均为 UTF-8 无 BOM。

## 8. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：SQLite 入库、R01—R04 筛查、AI 审计建议、判断表、正式契约、批准命令、业务状态机、RAG、OCR、百万行压测、真实 ERP 接入。
- 已知限制：报告检查只覆盖本层实际消费的字段，不等同于完整通用 schema 验证；空分组对象合法（真实无资金事件时两侧为空）；来源为 openpyxl 解码值，原始 Excel 字节副本才是权威载体；不宣称真实性、业务完整性或 ERP 模板兼容性；四表行数不相加称为资金笔数。
- 本卡范围内工作已停止：未接入 `data/batches`、未修改任何旧 `batch_manifest.json`、未实现契约／批准指纹检查、**未宣称已实现 Gate 1／Gate 2 放行**，也未做 SQLite 或推进任务五。
- 等待主理人把本回执与 `docs\NORMALIZATION_GUIDE.md`、`data\standardization_tests\task004_r1_02` 转交总架构师复验。
