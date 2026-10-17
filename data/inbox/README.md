# 原始数据投放说明（数据收集区）

本目录是**原始数据收集区**：审计人员把收到的资料按类别放进对应文件夹，然后运行校验命令。
系统只读取、不整理、不修复；**格式不符或不完整的数据整包退回**，不做清洗。

## 四类数据

| 类别 | 目录 | 放什么 |
| --- | --- | --- |
| 业务台账 | `01_业务台账/` | 应付、付款/退款、分摊、供应商四张表（`.xlsx`） |
| 凭证附件 | `02_凭证附件/` | 发票、合同、银行回单、审批单、入库单（`.json`）及 `index.json` |
| 银行流水 | `03_银行流水/` | `bank_transactions.json`（日期、方向、金额分、参考号） |
| 总账账套 | `04_总账账套/` | GL v1 十个文件（科目表、凭证、余额表、总账、明细账、报表、对账单、日记账、附件索引、清单） |

## 命名与格式

- 金额一律**整数分**（如 5,000.00 元写作 `500000`）；日期 `YYYY-MM-DD`。
- 文件名用英文小写与下划线；不要改动示例文件名。
- 业务台账：一个工作簿四张表（`suppliers`、`payables`、`payments`、`allocations`），表头见 `_放入说明.md`。
- 凭证附件：`index.json` 列示全部凭证编号与类型；每张凭证一个 `.json`。
- 银行流水：`bank_transactions.json`，逐笔 `date / direction / amount_cents / reference`。
- 总账账套：十个文件与 `gl_manifest.json` 齐全，清单内逐文件长度/SHA 必须与实际一致。

## 校验命令

```powershell
# 业务台账 / 凭证 / 银行流水（按项目输入契约）
.venv\Scripts\python.exe -B scripts\input_contract_v1.py --input-root data\evidence_inputs\task043_v1_1

# 总账账套（GL v1 契约）
.venv\Scripts\python.exe -B scripts\gl_input_contract_v1.py --gl-root data\inbox\04_总账账套

# 状态页（数据是否已提供 / 缺失 / 需校验）
.venv\Scripts\python.exe -B scripts\build_intake_guide.py --intake-root data\inbox --out-dir data\runtime_initial_judgment_recording_tests\task058_status_01
```

## 说明

每个子目录都有 `_放入说明.md`（放什么、命名、必填字段、示例、校验命令）。
状态页只读扫描，不复制、不移动、不修改任何文件；`放入此处.txt` 仅作占位。
