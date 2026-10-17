# 合成演示数据与校验说明（TASK-002 / 含 TASK-002-R1 返修）

版本：TASK-002 + R1 + R2；日期：2026-10-11；执行端：DeepSeek；依据：`docs/SPEC_V1.md`、`docs/tasks/TASK-002_DRAFT.md`、`docs/tasks/TASK-002-R1.md`、`docs/tasks/TASK-002-R2.md`、`docs/reviews/REVIEW_TASK_002.md`、`docs/reviews/REVIEW_TASK_002_R1.md`。

本文只说明**怎么生成、怎么校验、数据是什么**，不包含任何筛查规则结论，也不预填任何人的审计判断。全部数据为合成数据，仅用于审计辅助工具的开发与验收演示。

> **TASK-002-R1 返修摘要（只改校验器，未改业务口径与数据）**：验收追加测试发现四类校验问题，均已修复——① 必填日期为空仍通过、原生日期时间被静默截断；② 表头去空格与取值映射不一致导致必需字段漏检；③ 标识被自动去空格、布尔值被当作合法标识；④ 金额不可用时按零汇总并给出“勾稽相等”。受影响的是校验器与本文第 6 节的报告语义；**主工作簿、22 份 fixture、答案册与生成器都未改动**。
>
> **TASK-002-R2 收尾摘要**：① Excel 错误单元格（`data_type = e`，如 `#N/A`、`#REF!`）不再被当作合法文本标识，真文本里写着 `#N/A` 仍合法；② 收回 R1 额外引入的“带时间文本日期”格式——第一版日期文本只接受 `YYYY-MM-DD`；③ 回归验证在发现只读输入哈希不一致时**必须失败退出**，且每次校验调用使用唯一 stdout 日志名。同样**未改动数据、答案册与生成器**。

---

## 1. 这份数据是什么

模拟企业：**澄明商贸有限公司**；期间：**2026-09-01 至 2026-09-30**（截至日 2026-09-30，含当日）；币种：人民币；单一公司、无期初余额。

主演示工作簿 `input/erp_export.xlsx` **只有四张业务表**，不含答案页、异常标签列、隐藏标签、异常颜色或透露答案的批注：

| 工作表 | 实务含义 | 每行代表 |
| --- | --- | --- |
| `suppliers` | 供应商及收款对象主数据 | 一个本次范围内的供应商或指定的收款对象 |
| `payables` | 有效应付单 | 一张有效应付单（**不是发票**） |
| `payments` | 付款／退款资金事件 | 一笔资金事件（付款或收回原付款） |
| `allocations` | 资金分摊关联明细 | 一笔资金事件分配到某一个应付对象的金额 |

字段共 22 个，逐字以 `docs/SPEC_V1.md` 第 2 节为准。要点：

- `ap_number` 只是展示编号，**不承担关联或唯一键职责**；本数据里刻意有两张应付单共用同一展示单号、供应商与 `ap_id` 都不同。
- `allocations.ap_id` 允许为空，也允许填写台账中不存在的标识，**这是要保留的业务线索状态，不是脏数据**。
- 退款金额写正数，方向由 `transaction_type=REFUND` 决定；退款必须关联原付款及其原分摊。
- 只有 `SETTLED` 计入资金计算；`PENDING/FAILED/VOIDED` 只保留记录和名义金额。

第一版刻意采用**规范单元格类型**：金额以两位小数文本写入、日期以 `YYYY-MM-DD` 文本写入、标识为真实文本单元格并保留前导零、空值为真正空单元格。故意非法的单元格只出现在负向 fixture 中。

## 2. 1000 条的统计口径（最容易误读的地方）

**1000 指 `payments` 表的资金事件行数**，不是四张表的合计，也不等于“1000 笔采购”。

| 表 | 行数（不含表头） |
| --- | --- |
| `suppliers` | 20 |
| `payables` | 993 |
| `payments` | 1000 |
| `allocations` | 1005 |

`payments` 的构成：已结算 PAY 995 笔、已结算 REFUND 2 笔、非结算 PAY 3 笔。

`payables` 与 `payments` 行数不同是正常的：一张应付单可以被分期支付（多笔付款对应一张应付），一笔付款也可以合并支付多张应付单。**应付总额本来就不要求等于付款总额**，未付款与超付款都会让两者不相等。

## 3. 生成方法

固定解释器：`D:\harness work\audit_sa_project\.venv\Scripts\python.exe`（Python 3.11.1）。

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' `
  'D:\harness work\audit_sa_project\scripts\make_demo_data.py' `
  --seed 20260930 `
  --out-dir 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a'
```

- `--seed` 默认 20260930；`--out-dir` 必填。
- 输出目录必须是 `data\generated` 内**尚不存在**的子目录：路径越界或目录已存在时退出码 **2**，且在写入任何内容前停止，不覆盖、不自动删除旧产物。
- 相同种子生成相同四表记录、顺序与逻辑答案；`input/erp_export.xlsx` 的**字节** SHA-256 会因 XLSX 容器元数据而不同，所以复现性以**业务内容指纹**（重新读取四表表头与有序行内容后的 SHA-256）和逻辑答案为准，不以字节哈希为唯一依据。

每个输出目录包含：

```
input/erp_export.xlsx                 主演示工作簿（唯一的业务输入）
fixtures/                             22 份小型验收工作簿（与主输入隔离）
evaluation/ground_truth.json          主演示答案册
evaluation/ground_truth.md            答案册的人工可读版
evaluation/fixture_expectations.json  小工作簿的独立预期
manifest.json                         合成声明、种子、规格/代码哈希、版本、实际行数、输入哈希、内容指纹
checks/                               校验报告、失败测试副本与日志
```

## 4. 主工作簿与负向 fixture 的区别

- **主工作簿**：正常业务形态，**不含阻断性质量错误**。质量校验退出码应为 0。它包含 9 组已知场景标签（见第 5 节），但这些标签不是“异常列”，只登记在答案册里。
- **fixtures/**：22 份**独立**的小工作簿，逐条忠实展开规格第 6 节 C01—C13、C06b/C07b/C09b/C10b、C14a—C14e。
  - 其中 **14 份**质量通过（退出码 0）：C01、C02、C03、C04、C05、C06、C07、C08、C09、C10、C06b、C07b、C09b、C10b。
  - 其中 **8 份**故意制造阻断（退出码 1）：C11 已结算流水重复、C12 主表与分摊不平、C13 超额退款、C14a 缺必需列、C14b 主键重复、C14c 金额无法解析、C14d 无效日期、C14e 金额超过两位小数。
  - **阻断不等于零命中**：有阻断时规则预期标为“未执行”，不能读成“没有异常”。
  - 质量通过也不等于没有业务线索，两者是不同层面。

## 5. 答案册只用于开发验证

`evaluation/ground_truth.json` / `.md` 按“正在构造哪种已知场景”登记，**不调用任何检测规则推导**，其内容：

- 版本、合成声明、种子、主输入 SHA-256、四表行数；
- 预期命中计数：R01=3、R02=5、R03=2、R04=2，合计 12；
- 每条预期的规则号、结构化命中键（R01=`ap_id`+收款对象；R02=`ap_id`；R03/R04=`allocation_id`）、相关应付／付款／分摊／退款 ID、整数分金额、理由，以及**实际工作表行号**；
- 四规则范围内**不应命中**的场景：分期付款、合并付款、重复付款后全额退款、正常部分退款、非结算状态、共用展示单号的两张应付、尚未付款的应付。

三条必须同时记住的口径：

1. **九组场景、十二条命中、超额金额是不同统计口径**，不能互相替代，更不能相加称为损失。
2. 预期超额合计 16000.00 元（1 600 000 分）是按唯一应付单汇总的结果，不是付款行数乘以某个数。
3. 答案册**只用于开发期验证生成器与校验脚本**，不得作为检测程序输入，也不得作为人类初步判断界面的预填内容。检测程序将来若读取答案册产生线索，即属违规。

## 6. 校验方法

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' `
  'D:\harness work\audit_sa_project\scripts\check_demo_data.py' `
  --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' `
  --report 'D:\harness work\audit_sa_project\data\generated\task002_r1_01\baseline_reports\main.json'
```

- 校验器**从实际落盘的 Excel 重新读取原值与类型**，不校验生成器内存中的列表。
- 报告路径必须是**新文件**，不能覆盖输入或已有报告；输入与报告路径相同、报告已存在时退出码 2。
- 退出码：**0** 质量通过；**1** 发现质量／范围问题；**2** 参数、路径或文件无法读取等运行问题。
- 检查内容：四表字段与类型、主键唯一、日期与币种、金额正数与精度、强制关系、已结算流水唯一、每笔分摊平衡、退款指向／对象／日期与累计上限；并列出四表行数、按类型与状态的金额小计、已知与缺失应付关联的资金勾稽，以及带工作表与行号的问题定位。
- **不做的事**：不实现 R01—R04，不输出命中计数或审计等级，不读取答案册，也不导入生成器的造数函数。空或未知 `ap_id`、收款对象与应付供应商不同，都不会导致质量检查失败。

### 6.1 第一版的严格口径（TASK-002-R1 引入，TASK-002-R2 收尾）

1. **日期**：`ap_date`、`payment_date` 为空或纯空白 → `MISSING_REQUIRED_VALUE`；原生日期时间含非零时分秒或微秒 → `DATE_TIME_COMPONENT_PRESENT`，**不**直接截取日期；原生 `date`、午夜原生日期时间可无损转换。**日期文本只接受 `YYYY-MM-DD`**：带显式时间的文本（无论时间是否全零、无论用空格还是 `T` 分隔）一律报 `DATE_TIME_COMPONENT_PRESENT` 并阻断，不截取、不扩展格式。
2. **表头**：列名**逐字匹配，不自动去空格**。表头写成 `ap_id `（末尾有空格）不算 `ap_id`，报 `REQUIRED_COLUMN_MISSING`；字段映射结果在报告的 `structure.sheet_field_mapping` 中逐字段列出，未映射字段不得静默当作已核验。
3. **标识保真**：非空文本标识**原样保留**，不去前后空格、不改大小写、不补零、不做模糊匹配。仅把分摊 `ap_id` 改成 `" AP01"` 时，该完整字符串归入“所提供台账不存在的标识”，其金额进入缺失关联净额（质量检查仍可通过，这本身是允许保留的业务线索）。
4. **标识必须是真实文本单元格**：布尔、数值、日期类型，以及 **Excel 错误单元格**（`cell.data_type == "e"`，如 `#N/A`、`#REF!`、`#DIV/0!`）一律报 `ID_TYPE_INVALID`，适用于所有标识字段（含可空的 `ap_id`、`original_payment_id`、`original_allocation_id` 与银行流水号），不只是主键。判断依据是**单元格类型**，不按显示内容做黑名单：真正文本单元格里写着 `#N/A`（类型 `s`）仍然合法。

### 6.2 金额报告语义：已知有效小计 ≠ 完整总额

金额不可用时**不得按零补齐**，报告因此区分三层：

| 报告字段 | 含义 |
| --- | --- |
| `amount_summary.known_valid_subtotals_cents` | **已知有效小计**：只累加可解析、为正、精度不超过两位的金额单元格；不可用时为 `0`（表示“已核验的已知部分为零”，**不等于**真实金额为零） |
| `amount_summary.complete_totals_cents` | **完整总额**：仅当对应金额列已映射且该列没有任何不可用单元格时给出，否则为 `null` |
| `amount_summary.unusable_amount_cells` | 不可用于标准计算的金额单元格数量与来源，覆盖空值、无法解析、超两位小数、公式、非正金额；**同一单元格只计一次** |
| `payments_by_type_and_status.*.complete_amount_cents` | 按付款类型／状态的小计同样披露完整性，不可用时为 `null` |
| `reconciliation.status` | `ASSESSED` 或 `NOT_ASSESSED`；批次存在任何问题时（保守方案）统一为 `NOT_ASSESSED` |
| `reconciliation.known_plus_missing_equals_master` | 只在 `ASSESSED` 时为 `true`/`false`；否则为 `null`，不得显示 `true` |

例如把某笔付款与其分摊的金额同时改成 `N/A`：报告会给出完整总额 `null`、已知有效小计 `0`、不可用金额单元格 `2`、`reconciliation.status = NOT_ASSESSED`，而不是“完整金额 0、勾稽相等”。质量检查遇到这类情况仍然退出 1 阻断批次。

### 6.3 回归验证（TASK-002-R1 新增）

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' `
  'D:\harness work\audit_sa_project\tests\test_check_demo_data_regression.py' `
  --out-dir 'D:\harness work\audit_sa_project\data\generated\task002_r1_02\regressions'
```

- 通过命令行运行**真实校验器**，断言退出码与落盘报告内容；不测试私有辅助函数，也不搜索源码字符串。
- 每组从 `fixtures/C01.xlsx` 的新副本开始，只改少量字段；预期来自 `docs/SPEC_V1.md` 与返修卡，不读取答案册、不导入生成器、不用当前输出反推预期。
- 构造“错误单元格”用例后会**重新读取副本**并核对目标单元格的实际 `data_type`（错误值应为 `e`，真文本应为 `s`），不靠写入时的 Python 值判断类型。
- 输出目录必须是 `data\generated` 内**尚不存在**的子目录，拒绝覆盖旧证据；失败用例的副本、报告与日志一律保留。
- **完整性失败即验证失败**：只读输入前后哈希不一致时，验证进程返回 1、摘要记录 `protected_inputs_unchanged = false` 与具体路径，**不打印总体成功结论**。
- 每次校验调用使用**唯一 stdout 日志名**，`command_log.json` 登记对应日志路径，任何一次输出都不会被后续调用覆盖。
- 报告覆盖保护用例用同一个报告路径连跑两次：第二次退出 2，并比较报告前后哈希证明第一份报告未被改写。
- 全部通过返回 0，存在失败断言或完整性失败返回 1，参数或环境问题返回 2。
- 回归同时复跑**主工作簿**与**22 份原 fixture**，并对只读输入做前后哈希比较，保证原始来源不变。


## 7. 用三个例子理解这份数据（帮助阅读，不是结论）

- **合并付款（C03 同类）**：一笔 10000.00 的资金事件分摊到两张应付单（6000.00 + 4000.00）。只有**一笔**资金事件，分摊行不是第二笔钱，所以不能把整笔金额重复累计。
- **分期付款（C02 同类）**：一张应付 5000.00，分两笔 2000.00 + 3000.00 付清。有两次付款不等于重复付款，任一笔都不等于整张应付金额。
- **缺失关联（C07/C08 同类）**：付款 5000.00 的分摊里，`ap_id` 为空或填写了台账中不存在的标识。**记录必须保留**，其金额仍计入总体勾稽；这只能说明“在所提供台账中未找到关联对象”，**不能说成没有发票、没有真实采购或违法支付**。

## 8. 交给总架构师查看哪些报告

原 TASK-002 批次的报告在 `data\generated\demo_20260930_a\checks\`（旧版字段语义，见该批次的执行回执），其中：

| 文件 | 内容 |
| --- | --- |
| `main_validation.json` | 主工作簿的质量校验报告（退出码 0） |
| `fixtures\<案例>.validation.json` | 22 份 fixture 的逐份报告（14 份通过、8 份阻断） |
| `fixture_expectation_comparison.txt` | 预期与实际的逐项比对表 |
| `acceptance_verification_log.txt` | 逐项重读核验与答案册结构核对日志 |
| `main_validation_corrupted_copy.xlsx` | 有效性测试用的损坏副本（只把一条普通付款分摊 +0.01 元） |
| `corrupted_copy_validation.json` | 上述副本的校验报告（退出码 1，`ALLOCATION_SUM_MISMATCH`） |

**返修后的新证据**（TASK-002-R1）在 `data\generated\task002_r1_01\`：

| 路径 | 内容 |
| --- | --- |
| `baseline_reports\main.json` | 返修后校验器复跑主工作簿（退出码 0，四表完整金额可评估） |
| `baseline_reports\<案例>.json` | 返修后复跑 22 份原 fixture（14 通过 / 8 阻断） |
| `recheck_boundary\<B##>.json` | 复跑验收报告 B01—B09 的九份边界输入 |
| `regressions\regression_summary.json` | 42 个回归用例的逐项结果、失败清单与只读输入哈希 |
| `regressions\command_log.json` | 每次调用的完整参数数组与退出码 |
| `regressions\inputs\`、`reports\`、`logs\` | 回归用的输入副本、报告与校验器输出 |

主演示工作簿：`data\generated\demo_20260930_a\input\erp_export.xlsx`。

另外 `data\generated\` 下还有两个**开发试跑目录** `dev_try_01`、`dev_try_02`，属于修复过程的保留历史（见执行回执），**不要当作业务输入**；任何后续程序只能读取某个目录下的 `input\erp_export.xlsx`，不能递归把 `fixtures`、`evaluation`、`checks` 当成审计输入。

## 9. 人类现在需要做什么

**不需要。** 本任务是开发期造数与自检：

- 不需要填写重要性参数，也不需要模拟审批或守门点放行；
- 两处人工守门点（Gate 1／Gate 2）属于后续业务批次的流程，本任务未触发、也未伪造；
- 契约草案尚未被审定，正式契约仍未建立；
- 本数据上的**业务结论、缺陷分级、风险评估与最终审计判断全部留给人类**，程序与 AI 只提供事实与线索。

## 10. 本说明的边界

- 本任务是合成数据生成与数据质量自检，**不是**审计程序运行，也不是独立复核。
- 尚未执行：R01—R04 检测引擎、SQLite 入库、业务运行状态机、人工门禁、AI 审计建议、正式契约、Git 初始化、RAG、OCR、百万行压测、真实 ERP 接入。
- 与真实企业相比，本数据的导出字段、状态来源与银行证据均未核实；`SETTLED` 与银行流水号只是案例设定，不代表取得真实银行证据。
