# 原始数据投放指引（data/inbox）

标识：`TASK-058-intake-1.0`。实现：`scripts/build_intake_guide.py`（仅标准库）。
依据：`docs/decisions/DECISION_20261018_DSH_INTAKE_AND_ONECLICK.md`（`DSH-SCOPE-20261017-07`）。
边界：本指引只说明**放什么、放哪里、怎么校验**；只读扫描，不复制、不移动、不修改任何文件；
不构成审计结论。真实批准 `null`、真实初判未保存、0008、`next/AI=false`。

## 1. 目录骨架

```
data/inbox/
├─ README.md                     总说明：四类数据、命名、示例、校验命令
├─ 01_业务台账/                  suppliers / payables / payments / allocations 四表（xlsx）
├─ 02_凭证附件/                  index.json + 发票/合同/回单/审批/入库（json）
├─ 03_银行流水/                  bank_transactions.json
└─ 04_总账账套/                  GL v1 十个文件（含 gl_manifest.json）
```

每个子目录有 `_放入说明.md`（放什么、命名、必填字段、示例、校验命令、"不规整整包退回、不修数据"）
与 `放入此处.txt` 占位。

## 2. 四类数据要求

| 类别 | 应放文件/模式 | 必填字段 | 校验 |
| --- | --- | --- | --- |
| 业务台账 | `业务台账_<期间>.xlsx`（四张表） | 应付单号/供应商/日期/金额（分）；付款类型/日期/金额；分摊编号/付款/应付/金额 | `input_contract_v1.py` |
| 凭证附件 | `index.json` + `V-INV/CTR/BR/APR/GR-*.json` | 凭证编号/类型/金额（分）/日期；附件号按类型 | 索引结构 + 逐文件存在/金额整数分 |
| 银行流水 | `bank_transactions.json` | 日期/方向（IN/OUT）/金额（分）/参考号 | 结构检查 + 字段格式 |
| 总账账套 | GL v1 十个文件 | 科目/凭证/余额表/总账/明细账/报表/对账单/日记账/附件索引/清单 | `gl_input_contract_v1.py` |

金额一律**整数分**；日期 `YYYY-MM-DD`；文件名固定，不改名、不改目录。

## 3. 状态页

```powershell
.venv\Scripts\python.exe -B scripts\build_intake_guide.py `
  --intake-root data\inbox `
  --out-dir data\runtime_initial_judgment_recording_tests\task058_status_01
```

输出 `intake_status.html`（纯静态、无脚本、纯审计语言）与 `intake_manifest.json`
（逐目录/文件、状态、大小、SHA、更新时间）：

- **已提供**：文件存在且可读（GL 需契约校验通过）；
- **缺失**：应放文件不存在；
- **需校验**：存在但格式/结构/哈希不符（只读判断，不修数据）。

状态页顶部有边界横幅；表格列：数据类别、应放目录、应放文件或模式、状态、大小与更新时间、
校验方式、说明链接。只读扫描，不改变 inbox 内任何字节。

## 4. 校验命令

```powershell
# 业务台账 / 凭证 / 银行流水（项目输入契约；以已接受的输入包为样板）
.venv\Scripts\python.exe -B scripts\input_contract_v1.py --input-root data\evidence_inputs\task043_v1_1

# 总账账套
.venv\Scripts\python.exe -B scripts\gl_input_contract_v1.py --gl-root data\inbox\04_总账账套
```

格式不符、字段缺失、金额非整数分、清单哈希不符 → **整包退回**，不修数据、不补默认值；
校验通过后才会进入机器核对。

## 5. 测试

`.venv\Scripts\python.exe -B tests\test_intake_guide.py --out-dir data\runtime_initial_judgment_recording_tests\task058_run_02`

- 骨架：README、四个目录、四份 `_放入说明.md`、占位文件；
- 空 inbox → 全部缺失；合法样例 → 全部已提供；坏文件 → 对应项需校验；
- 语言红线、链接、确定性（两次字节相同）、只读（inbox 前后快照一致）。

## 6. 未做

一键启动器（TASK-059）不在本卡；不接 UI/看板；不做数据清洗。

## 7. 异常兜底（TASK-058-R1）

四类校验（业务台账 / 凭证附件 / 银行流水 / 总账账套）均为**异常安全**：

- 解析错误（非法内容/编码/IO）、顶层形状错误（数组/字符串/数字/null）、必需键缺失
  （如银行缺 	ransactions、附件索引缺 ouchers）、字段类型错误（金额非整数、方向非 IN/OUT、
  日期非 ISO）→ 该类别状态 **需校验**，detail 写明原因（如“银行流水文件顶层不是对象”）；
- **exit 0 且状态页/清单照常生成**，不出现 traceback、不中断其他类别；
- 测试覆盖：银行流水为数组、附件索引缺键、GL 文件为数组/非法内容、xlsx 为文本/损坏；
  上述情况下其他类别仍正确判定（互不影响）。

只读不变：不复制、不移动、不修改 inbox 内任何文件。
