# TASK-002-R2 执行回执（输入类型与验证退出行为收尾）

任务：修复 R1 复验发现的三项问题（A Excel 错误单元格、B 收回带时间文本日期、C 完整性失败必须使验证失败且日志不得覆盖），并补充针对性回归。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-002-R2.md`、`docs/reviews/REVIEW_TASK_002_R1.md`、`docs/SPEC_V1.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未启动 TASK-003，未宣布 TASK-002 最终通过。

> 本回执只记录本卡**实际执行**的命令与结果；未执行的检查一律写明“未执行”。命令均为完整参数，不使用省略号。旧回执与旧日志一律未覆盖。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| A Excel 错误单元格 | `read_text` 同时核验单元格类型；`data_type = e`（`#N/A`、`#REF!`）一律报 `ID_TYPE_INVALID`，覆盖主键、外键、可空标识与银行流水号；真文本 `#N/A`（类型 `s`）仍合法 |
| B 带时间文本日期 | 已收回 R1 的额外格式：日期文本只接受 `YYYY-MM-DD`；带显式时间的文本（空格或 `T` 分隔、时间是否全零）一律报 `DATE_TIME_COMPONENT_PRESENT` 并退出 1；原生午夜日期时间仍接受 |
| C 完整性失败与日志 | 只读输入哈希不一致时验证进程**退出 1**、摘要 `protected_inputs_unchanged = false`、失败原因含具体路径、不再打印总体成功；每次校验调用使用唯一 stdout 日志名并在 `command_log.json` 登记 |
| 正常回归 | **50 个用例全部通过**（42 个原用例 + 8 个新增），checker 实际调用 **51** 次，退出码 **0**，受保护输入 **28** 个且前后哈希一致 |
| 完整性故障模拟 | 独立输出目录，功能用例仍全通过，但进程**退出 1**、`protected_inputs_unchanged = false`、失败项含主工作簿路径、未输出总体成功 |
| 授权范围 | GPT R1 复验记录的 **280 个文件**中 **277 个逐字节未变**，变化的恰好是本卡授权的 3 个文件（checker、回归脚本、说明文档） |
| 依赖 | 未安装、未升级：Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9 |
| 未执行 | R01—R04 引擎、SQL、SQLite 入库、状态机、Gate 1／Gate 2、AI 建议、正式契约、Git、RAG、OCR、百万行压测、真实 ERP 接入 |

---

## 2. 实际修改与新增

### 2.1 修改（本卡授权的三个文件）

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\check_demo_data.py` | `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8` |
| `D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py` | `555c5ef7320c6fd3078264f808a5c2a43f492909058b9b0d361fb43dee09bbb6` |
| `D:\harness work\audit_sa_project\docs\DEMO_DATA_GUIDE.md` | `ad94e5a860368623947c05f483e95f8c40ae9a337706a338d2dec587b97e660e` |

说明文档只同步了 6.1（类型与日期）、6.3（验证行为）与顶部返修摘要，业务范围与原数据含义未改。

### 2.2 新增

| 路径 | 说明 |
| --- | --- |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_002_R2.md` | 本回执（含 R1 回执勘误） |
| `D:\harness work\audit_sa_project\data\generated\task002_r2_01\` | R2 输出根目录 |
| `D:\harness work\audit_sa_project\data\generated\task002_r2_01\regressions\`（130 个文件） | 正常回归：`regression_summary.json`、`command_log.json`、`inputs\` 27、`reports\` 27、`logs\` **51**、`baseline_reports\` 23 |
| `D:\harness work\audit_sa_project\data\generated\task002_r2_01\probe_type_check\`（2 个文件） | 造数前的 openpyxl 类型探针（证明 `#N/A` 落盘为 `e`、强制后为 `s`） |
| `D:\harness work\audit_sa_project\data\generated\task002_r2_01_integrity_probe\`（130 个文件） | 完整性故障模拟的独立输出目录 |

未覆盖、未删除：`task002_r1_01`、`task002_r1_gpt_*`、`data\reviews\*`、`demo_20260930_a/b`、`dev_try_01/02`、任何旧回执或旧日志。

---

## 3. A／B／C 的具体改法

### A. Excel 错误单元格不能作为文本标识

- `read_text` 在 `cell.data_type == "f"` 之后新增 `cell.data_type == "e"` 分支：返回类型问题，不再因为「Python 里是 str」而放行。
- 标识字段（`ID_FIELDS` 集合）把该问题细化为 `ID_TYPE_INVALID`，包含主键、外键、可空标识（`ap_id`、`original_payment_id`、`original_allocation_id`）与 `bank_reference`，不是只修 `payment_id`。
- 判断依据是**单元格类型**，不做内容黑名单：真正文本单元格里写着 `#N/A`（类型 `s`）仍被接受，文本合法性与关系规则按原规格处理。
- 定位信息保留工作表、Excel 原行号、字段名与原值。

### B. 收回日期文本的额外格式

- 删除 R1 中「时间部分全零的日期时间文本可无损转换」的放行逻辑；`DATE_TIME_TEXT_PATTERN` 保留为**识别**用途：命中即报 `DATE_TIME_COMPONENT_PRESENT` 并阻断，不解析、不截取。
- 原生 `date`、午夜原生 `datetime` 仍可无损接受；原生 `datetime` 含非零时分秒或微秒仍阻断。
- 日期必填、九月范围、退款不早于付款等校验未改动，R1 已修的空值必填问题没有回退。

### C. 完整性失败必须失败、日志不得覆盖

- `hash_problems` 非空时：向 `regression.failures` 追加一条 `kind = "integrity"` 的失败记录（含每个不一致路径），最终**返回 1**，并打印“存在失败用例或完整性失败，返回非零退出码（不输出总体成功结论）”，不再打印“全部回归用例通过”。
- 摘要新增 `protected_inputs_count`（实际 28）与 `totals.checker_invocations`（实际 51），计数由运行结果计算，不手填。
- `run_checker` 增加调用序号，stdout 日志名形如 `NN_<用例>.stdout.txt`，每次调用唯一；`command_log.json` 每条记录新增 `call_index` 与 `stdout_log`。
- 报告覆盖保护用例仍使用**同一个报告路径**连跑两次，并新增前后 SHA-256 比较，证明第二次（退出 2）没有改写第一份报告；两次 stdout 各自独立保存。

---

## 4. 新增用例与实际结果（全部 PASS）

新增用例均从原 `fixtures\C01.xlsx` 的新副本构造，只写入 R2 目录；造数后**重新读取副本并核对实际 `data_type`**：

| 用例 | 写入内容 | 观察到的实际类型 | 退出码 | 关键断言 |
| --- | --- | --- | --- | --- |
| E01_error_cell_payment_ids | payments!A2 与 allocations!B2 = `#N/A` | `e`、`e` | 1 | `ID_TYPE_INVALID` ×2，分别定位 payments.payment_id、allocations.payment_id |
| E02_error_cell_bank_reference | payments!I2（已结算） = `#REF!` | `e` | 1 | `ID_TYPE_INVALID` 定位 payments.bank_reference（另含 `BANK_REFERENCE_MISSING`，因该错误值不可用作流水标识） |
| E03_error_cell_nullable_ap_id | allocations!C2（可空） = `#N/A` | `e` | 1 | `ID_TYPE_INVALID` 定位 allocations.ap_id，未被当作允许的未知文本 |
| E04_true_text_error_looking_ids | 两处均写文本 `#N/A` 并强制文本类型 | `s`、`s` | 0 | 真文本不被按内容黑名单禁止；两份文本一致，勾稽仍相等 |
| E05_text_date_zero_time_space | payment_date = `2026-09-10 00:00:00` | `s` | 1 | `DATE_TIME_COMPONENT_PRESENT` |
| E06_text_date_zero_time_T_separator | payment_date = `2026-09-10T00:00:00` | `s` | 1 | `DATE_TIME_COMPONENT_PRESENT` |
| E07_text_date_nonzero_time | payment_date = `2026-09-10 12:34:56` | `s` | 1 | `DATE_TIME_COMPONENT_PRESENT`（保留 R1 既有阻断行为） |
| E08_text_negative_amounts | payments!F2 与 allocations!D2 = 文本 `-1.00` | `s`、`s` | 1 | `AMOUNT_INVALID` ×2；不可用金额单元格 2；完整总额 null；勾稽 NOT_ASSESSED |

原有 `B13_negative_amounts`（数值 `-100`）继续保留并退出 1，因此本轮**文本与数值两种负金额都由本卡实际执行**。
报告覆盖保护用例结果：第一次退出 **0**、第二次退出 **2**；第一份报告 SHA-256 `05e67fc0ea6fa3e9…` 前后相同；两次 stdout 分别保存为 `logs\27_R16_report_overwrite_guard.stdout.txt` 与 `logs\28_R16_report_overwrite_guard.stdout.txt`。

---

## 5. 正常回归结果（与故障模拟分开列明）

- 用例总数 **50**（42 个原用例 + 8 个新增），通过 **50**，失败 **0**；checker 实际调用 **51** 次（覆盖保护调用两次）。
- 受保护只读输入 **28** 个（主输入 1 + 原 fixture 22 + 规格／R2 卡／R1 复验报告／原回执／生成器 5），前后哈希一致。
- 基线部分：主文件退出 **0**（四表 20/993/1000/1005）；22 份原 fixture **14 个退出 0、8 个退出 1**，主要代码未遗漏；金额报告继续区分已知有效小计、完整总额与 `NOT_ASSESSED`。
- 进程退出码 **0**。

## 6. 完整性故障模拟结果（单独一次，独立目录）

按 R2 卡第 5 节指定的方法复用 GPT 的模拟脚本（在 `data\reviews\task002_r1_20261011_054723\command_log.json` 第 10 条 argv 中取得），只把输出目录换成本轮全新目录；模拟仅在内存中替换 `sha256` 返回值，**磁盘源码与输入均未改动**：

| 项目 | 结果 |
| --- | --- |
| 功能用例 | 50 个仍全部通过 |
| `protected_inputs_unchanged` | **false** |
| `protected_inputs_changed` | `["D:\\harness work\\audit_sa_project\\data\\generated\\demo_20260930_a\\input\\erp_export.xlsx"]`（注入值，非真实改动） |
| `failures` | 含 `kind = "integrity"` 的记录，问题描述含上述路径 |
| 进程退出码 | **1**（输出最后一行 `INTEGRITY_PROBE_PROCESS_RETURN 1`） |
| 是否打印总体成功 | **否**，打印“存在失败用例或完整性失败，返回非零退出码（不输出总体成功结论）” |
| 真实磁盘状态 | 主输入 SHA-256 仍为 `f86c3f65ee5dbac064fc2b6fc04e061ffd10914f4d1a49499a54c1cf52691252`，未变 |

---

## 7. 完整执行命令与实际退出码

```powershell
$py   = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$chk  = 'D:\harness work\audit_sa_project\scripts\check_demo_data.py'
$test = 'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py'
$r2   = 'D:\harness work\audit_sa_project\data\generated\task002_r2_01'
```

### 7.1 类型探针（决定如何构造错误单元格与真文本）

完整命令见**附录 A.1**（`@' … '@ | & $py -` 形式执行，退出码 **0**）。实际结果为：直接写入 `#N/A`／`#REF!` 落盘后 `data_type = e`；写入后设置 `cell.data_type = 's'` 再保存，重新读取为 `s`。探针文件保留在 `D:\harness work\audit_sa_project\data\generated\task002_r2_01\probe_type_check\`（`probe_direct_write.xlsx`、`probe_forced_text.xlsx`）。

### 7.2 语法检查

```powershell
& $py -m py_compile 'D:\harness work\audit_sa_project\scripts\check_demo_data.py'
& $py -m py_compile 'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py'
```

退出码均 **0**。

### 7.3 正常回归

```powershell
& $py 'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py' --out-dir 'D:\harness work\audit_sa_project\data\generated\task002_r2_01\regressions'
```

退出码 **0**；输出“用例总数 50，通过 50，失败 0，checker 调用 51 次”“只读输入前后哈希一致: True（受保护输入 28 个）”。

### 7.4 完整性故障模拟

```powershell
$probe = @'
import sys, importlib.util
spec = importlib.util.spec_from_file_location('regression_under_review', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module.sha256
reads = {}
def mismatching_hash(path):
    key = str(path)
    reads[key] = reads.get(key, 0) + 1
    if path == module.MAIN_INPUT and reads[key] == 2:
        return '0' * 64
    return original(path)
module.sha256 = mismatching_hash
rc = module.main(['--out-dir', sys.argv[2]])
print('INTEGRITY_PROBE_PROCESS_RETURN', rc)
sys.exit(rc)
'@
& $py -B -c $probe 'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py' 'D:\harness work\audit_sa_project\data\generated\task002_r2_01_integrity_probe'
```

退出码 **1**；末行 `INTEGRITY_PROBE_PROCESS_RETURN 1`。

### 7.5 其他核验

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\DEMO_DATA_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本用于核对 GPT R1 复验记录的 280 个文件哈希与整理证据计数，全文见**附录 A.2**，均以 `@' … '@ | & $py -` 方式执行，未新增 `.py` 文件。

---

## 8. 只读依据、输入与依赖核对

- 回归内建核验：28 个受保护输入（含主输入、22 份原 fixture、规格、R2 卡、R1 复验报告、原回执、生成器）前后哈希一致。
- 主输入：`f86c3f65ee5dbac064fc2b6fc04e061ffd10914f4d1a49499a54c1cf52691252`，与 R1 一致。
- 生成器：`e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`，未改动。
- `docs\EXEC_REPORT_002_R1.md`：`5f98acd088498458d98f9f44523764e67e4ca619e0341e507a3b5471f7205a4c`，未改动（勘误写在本回执中）。
- 对 GPT R1 复验记录的 **280 个文件**重新计算哈希：**277 个未变**，变化 3 个且全部在本卡授权范围内（checker、回归脚本、说明文档），无未授权变化、无缺失。
- 依赖未变；项目 Git 仍未初始化；`py_compile` 产生的 `__pycache__` 已删除，`scripts\` 与 `tests\` 只保留授权文件。

## 9. R1 回执勘误

| 原回执（EXEC_REPORT_002_R1.md）的说法 | 事实 |
| --- | --- |
| “26 个只读输入” | 实际 **28** 个（主输入 1 + fixture 22 + 其他只读依据 5）；R2 摘要新增 `protected_inputs_count` 直接输出该数 |
| “94 个文件中 93 个不变、仅 checker 改动” | 实际是 **92 个不变、2 个授权文件改动**（checker 与 DEMO_DATA_GUIDE）；该次测量发生在说明文档修改之前 |
| “回归脚本覆盖了文本与数值两种负金额” | R1 脚本当时**只有数值** `-100`；文本 `-1.00` 由 GPT 在 R1 复验中独立验证。本轮 R2 才真正执行文本负金额用例（E08） |
| （未提及）覆盖保护两次调用共用同一日志名 | R1 的 43 次调用只保留 **42** 个 stdout（第一次被 `w` 模式覆盖）；R2 已改为唯一日志名，51 次调用保留 **51** 个 stdout，并在 `command_log.json` 登记日志路径 |

原回执与旧日志均未修改，勘误只写在**本回执**中。

## 10. 失败尝试与修复过程

1. **类型探针（本轮先做）**：确认 openpyxl 对 `#N/A`／`#REF!` 的落盘类型为 `e`，强制 `data_type='s'` 后重新读取为 `s`；据此构造 E01—E04，避免只凭写入值判断类型。
2. **完整性模拟首次尝试失败（已保留记录）**：第一次执行 `-c` 模拟脚本时报 `NameError: name 'regression_under_review' is not defined`，原因是 PowerShell 向原生程序传参时吞掉了脚本里的双引号，模块加载即失败、`main()` 从未运行。改为在 Python 脚本中使用单引号字面量后重试成功。该失败未产生输出目录（重试前已确认目录不存在），也未改动任何文件；两次尝试的命令与输出均在本次会话记录中。
3. 本轮没有其他失败执行：语法检查、正常回归、基线复跑、故障模拟均按预期返回。

## 11. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：R01—R04 检测引擎、SQL、SQLite 入库、业务状态机、Gate 1／Gate 2、AI 审计建议、正式契约、Git、RAG、OCR、百万行压测、真实 ERP 接入；未统计召回率与误报率。
- 已知限制：`issues[*].severity` 仍统一 `blocking`；勾稽采用“有任一问题即 `NOT_ASSESSED`”的保守方案；`demo_20260930_a\checks\` 中的旧报告仍是旧字段语义（作为 R0 证据保留）；E02 除 `ID_TYPE_INVALID` 外还会附带 `BANK_REFERENCE_MISSING`，属同一损坏的连带问题，未遗漏主要原因。
- 本卡范围内工作已停止：未启动 TASK-003，未覆盖或删除任何旧批次、旧回执、旧日志或 GPT 验收证据，**未自行宣布 TASK-002 最终通过**。
- 等待主理人把本回执与 `data\generated\task002_r2_01`、`data\generated\task002_r2_01_integrity_probe` 转交总架构师复验。

---

## 附录 A：内联脚本全文（完整命令，无省略）

### A.1 openpyxl 单元格类型探针（对应第 7.1 节）

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$dir = 'D:\harness work\audit_sa_project\data\generated\task002_r2_01\probe_type_check'
New-Item -ItemType Directory -Path $dir -Force | Out-Null
@'
import shutil
from pathlib import Path
from openpyxl import load_workbook

src = Path(r'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\fixtures\C01.xlsx')
out = Path(r'D:\harness work\audit_sa_project\data\generated\task002_r2_01\probe_type_check')

# 探针 1：直接写 #N/A、#REF!
p1 = out / 'probe_direct_write.xlsx'
shutil.copyfile(src, p1)
wb = load_workbook(p1)
wb['payments']['A2'] = '#N/A'
wb['payments']['I2'] = '#REF!'
wb.save(p1)
wb2 = load_workbook(p1)
for ref in ('A2', 'I2'):
    c = wb2['payments'][ref]
    print(f'直接写入后 payments!{ref}: value={c.value!r} data_type={c.data_type!r}')

# 探针 2：写入后强制 data_type = s
p2 = out / 'probe_forced_text.xlsx'
shutil.copyfile(src, p2)
wb = load_workbook(p2)
for sheet, ref in (('payments', 'A2'), ('allocations', 'B2')):
    cell = wb[sheet][ref]
    cell.value = '#N/A'
    cell.data_type = 's'
wb.save(p2)
wb3 = load_workbook(p2)
for sheet, ref in (('payments', 'A2'), ('allocations', 'B2')):
    c = wb3[sheet][ref]
    print(f'强制文本后 {sheet}!{ref}: value={c.value!r} data_type={c.data_type!r}')
print('探针完成，文件保留在', out)
'@ | & $py -
```

### A.2 GPT R1 复验记录（280 个文件）哈希核对（对应第 7.5 节）

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
@'
import json, hashlib
from pathlib import Path
root = Path(r'D:\harness work\audit_sa_project')
ev = root / 'data' / 'reviews' / 'task002_r1_20261011_054723' / 'source_hashes_after.json'
recorded = json.loads(ev.read_text(encoding='utf-8'))
changed, missing, same = [], [], 0
for rel, expected in recorded.items():
    p = root / rel
    if not p.exists():
        missing.append(rel); continue
    if hashlib.sha256(p.read_bytes()).hexdigest() == expected:
        same += 1
    else:
        changed.append(rel)
print(f'GPT 记录总数 {len(recorded)} | 未变 {same} | 变化 {len(changed)} | 缺失 {len(missing)}')
for rel in changed:
    print('   变化:', rel)
authorized = {'scripts\\check_demo_data.py', 'tests\\test_check_demo_data_regression.py', 'docs\\DEMO_DATA_GUIDE.md'}
print('变化文件是否都在 R2 授权范围内:', set(changed) <= authorized)
print('未授权变化:', sorted(set(changed) - authorized))
'@ | & $py -
```

### A.3 证据目录计数（对应第 2.2、5 节）

```powershell
foreach ($d in @('task002_r2_01\regressions','task002_r2_01\regressions\logs','task002_r2_01\regressions\inputs',
                 'task002_r2_01\regressions\reports','task002_r2_01\regressions\baseline_reports',
                 'task002_r2_01\probe_type_check','task002_r2_01_integrity_probe')) {
  $p = Join-Path 'D:\harness work\audit_sa_project\data\generated' $d
  if (Test-Path $p) { Write-Output ("{0,-52} {1,4} 个文件" -f $d, (Get-ChildItem $p -Recurse -File).Count) }
}
```

实际输出：`regressions` 130（其中 `logs` 51、`inputs` 27、`reports` 27、`baseline_reports` 23）、`probe_type_check` 2、`task002_r2_01_integrity_probe` 130。
