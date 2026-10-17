# TASK-002 执行回执

任务：生成采购付款合成 Excel 演示数据、独立答案册与小型验收工作簿，并完成开发期自检。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-002_DRAFT.md`、`docs/tasks/TASK-001_HANDOFF.md`、`docs/SPEC_V1.md`、`docs/AUDIT_CONTRACT_DRAFT.md`。
状态：本任务范围内的工作已完成并自检通过，**停止于此**，未启动 TASK-003。

> 本回执只记录本任务**实际执行**的动作与结果。凡未执行的检查一律写明未执行，不写成通过。

---

## 1. 结论摘要（先看这一段）

| 验收项 | 结果 |
| --- | --- |
| 四表实际行数 | `suppliers`=20、`payables`=993、`payments`=1000、`allocations`=1005（不含表头） |
| 资金事件构成 | 已结算 PAY 995、已结算 REFUND 2、非结算 PAY 3（合计 1000） |
| 主工作簿质量校验 | **退出码 0（通过）**，问题数 0 |
| 22 份 fixture | **14 份退出 0**、**8 份退出 1 且主要错误码正确**（8/8 与规格预期一致） |
| 同种子复现 | 业务内容指纹一致、逻辑答案一致；仅字节哈希与时间戳等来源字段不同（符合规格第 3.4 节） |
| 重复生成拒绝 | 向已存在的 a 目录再生成 → **退出码 2**，27 个既有产物哈希完全未变 |
| 有效性测试 | 损坏副本（一条普通付款分摊 +0.01 元）→ **退出码 1**，报 `ALLOCATION_SUM_MISMATCH`，主输入哈希不变 |
| 答案册结构 | 12 条预期键、R01=3 / R02=5 / R03=2 / R04=2、超额合计 1 600 000 分；行号与工作簿逐条对得上 |
| 只读文件保护 | 8 个只读文件（规格、契约草案、回执、交接说明、本任务卡、历史文档、安装日志）起止哈希**完全一致** |
| 未执行事项 | R01—R04 检测引擎、SQLite 入库、状态机、人工门禁、AI 审计建议、正式契约、Git、RAG、OCR、百万行压测、真实 ERP 接入 |

---

## 2. 实际新增或修改的文件

本任务**只新增**以下五个文件（其余文件一律未修改）：

| 文件 | 说明 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\make_demo_data.py` | 合成数据生成器：主工作簿、22 份 fixture、答案册、fixture 预期、manifest |
| `D:\harness work\audit_sa_project\scripts\check_demo_data.py` | 数据质量校验器：只做结构与质量核验，不实现 R01—R04 |
| `D:\harness work\audit_sa_project\requirements-demo.txt` | 只列本次新增直接依赖 `openpyxl==3.1.5`（非项目完整锁文件） |
| `D:\harness work\audit_sa_project\docs\DEMO_DATA_GUIDE.md` | 生成与校验说明、四表含义、统计口径、答案册使用限制 |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_002.md` | 本执行回执 |

**未修改**：`docs\SPEC_V1.md`、`docs\AUDIT_CONTRACT_DRAFT.md`、`docs\EXEC_REPORT_001.md`、`docs\PLAN_TO_ARCHITECT.md`、`docs\tasks\TASK-001_HANDOFF.md`、`docs\tasks\TASK-002_DRAFT.md`、`原方案和第一次优化方案.md`、`pip_install.log`（第 11 节给出起止哈希证据）。
**未创建**：正式 `AUDIT_CONTRACT.md`、`AGENTS.md`、SQL、数据库、门禁或审计报告；项目 Git 仓库仍未初始化。

### 生成产物（全部位于 `data\generated` 内）

| 目录 | 性质 |
| --- | --- |
| `data\generated\demo_20260930_a` | **正式验收产物**（规定命令生成） |
| `data\generated\demo_20260930_b` | 同种子复现产物 |
| `data\generated\dev_try_01` | 开发试跑：**存在已知缺陷**（fixture 缺默认主数据），按“不覆盖历史”保留 |
| `data\generated\dev_try_02` | 修复后的开发复跑，保留为过程证据 |

每个产物目录结构：`input\erp_export.xlsx`、`fixtures\*.xlsx`、`evaluation\ground_truth.json`、`evaluation\ground_truth.md`、`evaluation\fixture_expectations.json`、`manifest.json`、`checks\`。

**后续任何程序只能读取某个目录下的 `input\erp_export.xlsx`**，不得递归把 `fixtures`、`evaluation`、`checks` 或试跑目录当审计输入。

---

## 3. 依赖变化

| 包 | 变化 | 版本 |
| --- | --- | --- |
| openpyxl | 本次新增 | 3.1.5 |
| et-xmlfile | openpyxl 的传递依赖，本次新增 | 2.0.0 |
| pandas | 未升级、未改动 | 3.0.6 |
| numpy | 未升级、未改动 | 2.4.6 |
| chromadb | 未升级、未改动 | 1.5.9 |
| Python | 使用项目现有虚拟环境 | 3.11.1 |

安装方式：只进入项目虚拟环境，未改动系统 Python。

---

## 4. 完整执行命令与实际退出码

均使用 `D:\harness work\audit_sa_project\.venv\Scripts\python.exe`。

### 4.1 依赖安装

```powershell
& 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe' -m pip install --no-cache-dir -r 'D:\harness work\audit_sa_project\requirements-demo.txt'
```

退出码 **0**，实际安装 `openpyxl-3.1.5`、`et-xmlfile-2.0.0`。随后读取包元数据核实：Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9。

### 4.2 生成（含开发试跑与两次正式目录）

```powershell
# 语法检查
& $py -m py_compile 'D:\harness work\audit_sa_project\scripts\make_demo_data.py'      # 退出码 0
& $py -m py_compile 'D:\harness work\audit_sa_project\scripts\check_demo_data.py'     # 退出码 0

# 开发试跑（存在缺陷，见第 12 节）
& $py '...\scripts\make_demo_data.py' --seed 20260930 --out-dir '...\data\generated\dev_try_01'   # 退出码 0
# 修复后开发复跑
& $py '...\scripts\make_demo_data.py' --seed 20260930 --out-dir '...\data\generated\dev_try_02'   # 退出码 0

# 正式 a 目录（TASK-002 第 3.1 节规定命令）
& $py '...\scripts\make_demo_data.py' --seed 20260930 --out-dir '...\data\generated\demo_20260930_a'  # 退出码 0
# 同种子 b 目录
& $py '...\scripts\make_demo_data.py' --seed 20260930 --out-dir '...\data\generated\demo_20260930_b'  # 退出码 0
```

a 目录生成时输出：四表实际行数 20/993/1000/1005；已结算 PAY=995、已结算 REFUND=2、非结算 PAY=3；预期命中计数 R01=3、R02=5、R03=2、R04=2，合计 12；R02 预期超额合计 1 600 000 分（16000.00 元）；fixtures 22 份（有效预期 14、阻断预期 8）。

### 4.3 校验

```powershell
# 主文件（规定路径）
& $py '...\scripts\check_demo_data.py' `
  --workbook '...\data\generated\demo_20260930_a\input\erp_export.xlsx' `
  --report   '...\data\generated\demo_20260930_a\checks\main_validation.json'      # 退出码 0，问题数 0

# 22 份 fixture 逐一校验（报告写入 checks\fixtures\）
& $py '...\scripts\check_demo_data.py' --workbook '...\fixtures\<案例>.xlsx' --report '...\checks\fixtures\<案例>.validation.json'
```

退出码统计：**14 份 0**、**8 份 1**（明细见第 7 节）。

### 4.4 内联脚本（经标准输入执行，未新增 .py 文件）

比较脚本、逐项重读核验脚本、损坏副本制作脚本均以 `@' ... '@ | & $py -` 方式执行；关键输出已落盘为 `checks\acceptance_verification_log.txt` 与 `checks\fixture_expectation_comparison.txt`。

---

## 5. 主工作簿质量校验结果（退出码 0）

`checks\main_validation.json` 摘要：四表来源行数 20/993/1000/1005，`issues` 为空，`result` = `pass`。
报告内已包含：按类型与状态的金额小计、已结算付款／退款与分摊的勾稽、已知应付关联净额与缺失应付关联净额（含空标识与台账外标识）的拆分，且 `known_plus_missing_equals_master` 为真。

主文件**不含**阻断性质量问题；空或未知 `ap_id`（共 2 条：1 条空标识、1 条台账外标识）与收款对象差异均按规格保留，未被判为质量问题。

---

## 6. 逐项重读核验（TASK-002 第 5.1 节）

从**实际落盘的 Excel** 重新读取后核对，全部通过（日志：`checks\acceptance_verification_log.txt`）：

- 工作表恰为四张且均可见，无隐藏表、无定义的名称、无答案页；
- 四表表头与规格 22 个字段逐字一致，无多余列；
- 四表行数 20 / 993 / 1000 / 1005；
- 标识列为**真实文本单元格**，供应商 ID 保留前导零（S001—S020），应付 ID 形如 AP00001；
- 金额均为两位小数文本，**无浮点单元格**；
- 空值为真正空单元格：非结算事件银行流水为空 3 条、PAY 的原付款标识为空 998 条、空 `ap_id` 分摊 1 条、台账外 `ap_id` 分摊 1 条（缺失应付关联合计 2 条）；
- 日期均为 ISO 文本且落在 2026-09-01 至 2026-09-30；2 笔退款不早于原付款且收款对象与原付款一致；
- 每笔主表金额与分摊合计**精确相等**（Decimal，无误差容限）；
- 普通组金额含 0.01 与 1234.56；存在共用展示单号 `CG-2026-09-0417` 而供应商与 `ap_id` 不同的两张应付单（AP00001、AP00002）；
- 公式单元格 0、批注 0、非默认填充 0。

## 7. 22 份 fixture 通过／阻断清单（TASK-002 第 5.2 节）

| 案例 | 期望 | 实际 | 退出码 | 实际错误码 |
| --- | --- | --- | --- | --- |
| C01 | 通过 | 通过 | 0 | — |
| C02 | 通过 | 通过 | 0 | — |
| C03 | 通过 | 通过 | 0 | — |
| C04 | 通过 | 通过 | 0 | — |
| C05 | 通过 | 通过 | 0 | — |
| C06 | 通过 | 通过 | 0 | — |
| C07 | 通过 | 通过 | 0 | — |
| C08 | 通过 | 通过 | 0 | — |
| C09 | 通过 | 通过 | 0 | — |
| C10 | 通过 | 通过 | 0 | — |
| C11 | 阻断 | 阻断 | 1 | `SETTLED_BANK_REFERENCE_DUPLICATE` |
| C12 | 阻断 | 阻断 | 1 | `ALLOCATION_SUM_MISMATCH` |
| C13 | 阻断 | 阻断 | 1 | `REFUND_EXCEEDS_ORIGINAL` |
| C06b | 通过 | 通过 | 0 | — |
| C07b | 通过 | 通过 | 0 | — |
| C09b | 通过 | 通过 | 0 | — |
| C10b | 通过 | 通过 | 0 | — |
| C14a | 阻断 | 阻断 | 1 | `REQUIRED_COLUMN_MISSING` |
| C14b | 阻断 | 阻断 | 1 | `PRIMARY_KEY_DUPLICATE`（另有 `SETTLED_BANK_REFERENCE_DUPLICATE`，属同一损坏的附带问题） |
| C14c | 阻断 | 阻断 | 1 | `AMOUNT_INVALID` |
| C14d | 阻断 | 阻断 | 1 | `DATE_INVALID` |
| C14e | 阻断 | 阻断 | 1 | `AMOUNT_SCALE_INVALID`（2 处：主表与分摊） |

统计：有效 14/14 通过，阻断 8/8 命中预期主要代码（含 C14b 的附带问题，未遗漏主要原因）。
**阻断 ≠ 零命中**：阻断案例的规则预期按规格标为“未执行”。质量通过也不等于不存在业务线索。

## 8. 同种子复现（TASK-002 第 5.3 节）

| 比较项 | 结果 |
| --- | --- |
| 业务内容指纹（重新读取四表表头与有序行后的 SHA-256） | 一致：`6e58f18a5e979ac9ddb548eb623efca83e53ed5bb0306b4bf5d2e49680cfdf82` |
| 逻辑答案（预期键、结构化命中键、整数分金额、理由、行号、构成、非命中场景、fixture 预期） | **完全一致** |
| `input\erp_export.xlsx` 字节 SHA-256 | 不同（a：`f86c3f65…`，b：`aa66b83c…`）——XLSX 为 ZIP 容器，字节受元数据影响，按规格不以字节哈希为唯一复现依据 |
| `generated_at_utc`、文件哈希等来源字段 | 分别准确保存，未参与逻辑答案比较 |

## 9. 拒绝覆盖与损坏副本检查（TASK-002 第 5.4、5.5 节）

- **拒绝覆盖**：再次向 `demo_20260930_a` 生成 → 退出码 **2**，错误信息“输出目录已存在，不覆盖任何内容”；比较 `input`、`fixtures`、`evaluation` 共 27 个文件的 SHA-256，**无新增、无修改、无删除**。
- **有效性测试**：在 `checks\` 内另存主文件副本，仅把第 2 行分摊（AL00001 / PM00001 / AP00001）的 `allocated_amount` 由 `0.01` 改为 `0.02`；校验退出码 **1**，问题数恰为 1，错误码 `ALLOCATION_SUM_MISMATCH`；主输入文件 SHA-256 前后一致（`f86c3f65…`），未被改动。

## 10. 答案册核对（TASK-002 第 5.6 节）

- 预期命中 **12 条**：R01=3、R02=5、R03=2、R04=2；`expected_hit_counts` 与逐条登记一致。
- 命中键结构正确：R01 = `ap_id` + 收款对象；R02 = `ap_id`；R03/R04 = `allocation_id`。
- 每条含整数分金额、理由、相关应付／付款／分摊／退款 ID，且登记的**实际工作表行号**与工作簿中对应记录的键逐条一致。
- R02 预期超额合计 **1 600 000 分（16000.00 元）**。
- 这只是**场景标签核对**，不是检测引擎发现了 12 条；本任务**未**统计召回率或误报率，也**未**运行任何规则。

## 11. 只读文件保护（TASK-002 第 5.7 节）

任务开始与结束时逐一比对 SHA-256，全部一致：

| 文件 | SHA-256（起止一致） |
| --- | --- |
| `docs\SPEC_V1.md` | `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236` |
| `docs\AUDIT_CONTRACT_DRAFT.md` | `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27` |
| `docs\EXEC_REPORT_001.md` | `4968fab0844ce69bd5ca77dc4d2df8f9ead60e38b4142daa08c0ea7570e4d549` |
| `docs\PLAN_TO_ARCHITECT.md` | `6013905b2aa93443509ae110013de8ca00a268606443d79fae662d392bc5bd8c` |
| `docs\tasks\TASK-001_HANDOFF.md` | `64fb8c31075fd5e336fea446a869c33988b0a16e15b86647194bfd42c488cb54` |
| `docs\tasks\TASK-002_DRAFT.md` | `ebdf0e8d262253796677a6241753090ac1a810498b33a6d728dd921a3891e9ac` |
| `原方案和第一次优化方案.md` | `2995787f591048cebbdf6a8faf6cd2ad62ecaa6e4333a3c49dd8adfe161452a4` |
| `pip_install.log` | `98cce40e3a20722d5eab1d439f741c021677fe2e99f388ad586587ff7a16c444` |

项目 Git 仓库仍未初始化（`.git` 不存在），也未被本任务创建。

---

## 12. 偏差与失败修正记录（不隐瞒）

1. **首次生成的 fixture 缺默认主数据**：`dev_try_01` 中每份 fixture 的 `suppliers` 表只有表头，缺少规格第 6.0 节要求的 `S001=甲供应商`、`S002=乙收款对象` 两条默认记录，导致 22 份 fixture 全部报 `FOREIGN_KEY_MISSING`。原因在生成器未写入默认主数据；已修复为每份 fixture 固定写入两条默认主数据。按“修复后使用新输出目录、不覆盖历史”的规则，改用 `dev_try_02` 重新生成，`dev_try_01` 原样保留。
2. **首次校验器在 C14a 崩溃**：修复前的 `check_demo_data.py` 在缺少 `payable_amount` 列的 C14a 上报 `KeyError: 'payable_amount__cents'`（退出码 1 伴随回溯），原因是金额小计直接下标取值。已改为安全取值，并同时修正“每笔事件至少一条分摊”的遍历方式（改为按主表事件遍历）。失败记录留在 `dev_try_01\checks\` 内。
3. **自写核验断言写错（非数据问题）**：第 5.1 节核验脚本首次运行在“空 `ap_id` 分摊数”上断言 2 而实际为 1（设计上是 1 条空标识 + 1 条台账外标识 = 缺失关联 2 条）。属核验脚本自身口径写错，已更正断言并重跑通过；**未修改任何数据或规格**。
4. **未做“为让检查通过”的调整**：未修改已批准的规格、答案或数据来迁就检查结果；所有修正都在本任务授权文件内完成。
5. **编译缓存清理**：`py_compile` 语法检查在 `scripts\` 下产生了 `__pycache__`（2 个 `.pyc`），属非授权产物，已删除；`scripts\` 现只有两个授权源码文件。

## 13. 未解决问题与限制

- `data\generated` 下留有 `dev_try_01`、`dev_try_02` 两个开发试跑目录；这是依“不覆盖、不删除历史产物”保留的，**其中 `dev_try_01` 的 fixture 已知有缺陷**。是否清理由主理人决定，执行端未删除任何历史产物。
- 校验报告内含 `checked_at_utc`，因此报告文件本身不是字节级可复现产物（任务未要求）。
- 校验器把所有报告问题统一标为 `severity = blocking`，**未实现分级**（刻意为避免任何审计分级暗示）。
- 校验器不校验“范围外日期”以外的范围问题细节（如真实 ERP 的表结构差异）；本数据无范围外日期。
- 校验器未覆盖：公式型输入、真实 ERP 导出适配、多银行账户流水命名空间、真实银行证据、Excel 读取性能与百万行压测。
- 与业务运行相关的一切（R01—R04 检测、SQL、SQLite 入库、状态机、Gate 1／Gate 2、AI 审计建议、正式契约、Git、RAG、OCR）均**未执行**，本回执不主张其中任何一项已通过。
- 答案册与 fixture 预期只用于开发期验证；本任务**未**统计召回率与误报率，**未**生成任何审计意见、缺陷等级或最终结论。

## 14. 停止状态

本任务已按 TASK-002 第 6 节要求停止：

- 未开始 TASK-003；
- 未编写数据库、筛查 SQL、门禁或审计报告；
- 未修改任务一文件的历史状态（第 11 节哈希证据）；
- 等待主理人把本回执转交总架构师验收，由总架构师检查代码与实际产物后决定下一张任务卡。
