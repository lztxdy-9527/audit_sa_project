# TASK-006-R1 执行回执（补齐退款来源证据与回归验证）

任务：修复 TASK-006 验收发现的 F01——退款摘要存在但退款主表／退款分摊没有完整来源实体，且退款来源缺失时核心仍返回成功；并补齐自动验证、纠正说明中的一句矛盾表述。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-006-R1.md`、`docs/reviews/REVIEW_TASK_006.md`、`docs/tasks/TASK-006_DRAFT.md`、`docs/RULE_SCREEN_GUIDE.md`、`docs/EXEC_REPORT_006.md`、`docs/SPEC_V1.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务七，未接入 `data/batches`，未生成 AI 判断或人类判断预填值。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧 `docs/EXEC_REPORT_006.md` 保持原字节（`b4fc55a8…`），未回写。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| **缺口（修复前）** | `_evidence_block` 只对应付、原付款主表、原付款分摊调用 `source_provenance`；退款仅以 `evidence.related_refunds` 摘要形式出现，退款主表与退款分摊**从未进入来源读取集合**，`source_rows` 也没有其 Excel 行号；退款来源缺失／`cells` 非法时不会失败 |
| **修复** | 必需来源集合改为「相关应付 ＋ 原付款主表／分摊 ＋ **每条相关退款分摊及其引用的退款主表**」；退款实体同样经 `source_provenance` 读取 `workbook_sha256`／`sheet`／`excel_row`／**完整 `cells`**，其行号并入 `source_rows.payments`／`allocations`；同一退款主表只出现一次；实体、行号、退款列表稳定排序 |
| **失败处理** | 退款来源缺项或 `cells` JSON 非法一律 `RuleScreenError`（带阶段、表名、业务 ID），不返回 `DEV_RULES_COMPUTED`；异常清理不掩盖原错误，正常关闭仍严格 |
| **口径不变** | `related_ids.payment_ids`／`allocation_ids` 仍只列原付款与其分摊；`statistics.involved_payments` 仍只含唯一原付款及其整笔已结算金额；四份规则 SQL **保持原哈希未改**；R01／R02 金额、R03／R04 历史事实、总体勾稽均不变 |
| **核心版本** | `TASK-006-rule-core-1.1` |
| **自动核验** | 21 个成功输入、**34 条线索**逐条必需来源集合与完整 `cells` 核对：**缺项 0**；重点 5 个输入（C06b／C09b／C10b／S1／S4）**7 条线索、22 个退款实体出现项、缺项 0** |
| **五项故障回归** | 原付款主表缺来源、退款主表缺来源、退款分摊缺来源、退款主表 `cells` 非法、退款分摊 `cells` 非法 → **全部 `RuleScreenError`**，注入均被目标查询触发（各 1 次），数据库字节未变 |
| **既有结果** | 主文件仍 12 个结构化键（R01 3／R02 5／R03 2／R04 2），R02 唯一应付超额合计 **1 600 000** 分；C03 不翻倍；退款、缺失关联、对象差异、非结算、分组键、无资金事件原预期全部不变 |
| **开发验证** | **29 个输入，测试失败 0，退出 0**：规则成功 21、上游阻断 8、接口阻断 0、运行错误 0；checker CLI **29** 次；核心调用 **32** 次（复调用与故障注入调用合计 11） |
| **历史保护** | GPT 扩充保护基线（`task006_20261011_064634/source_hashes_after.json`，9600 项）**变化 3、缺失 0**，恰为本卡授权的三个文件；任务五 R2 的 **8547** 基线 **0 变化、0 缺失**；任务四 R1 的 6511、任务三 R3 的 4902、任务二 R2 的 874 基线均 0 变化 |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 | 说明 |
| --- | --- | --- |
| `D:\harness work\audit_sa_project\scripts\screen_demo_sqlite.py` | `1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe` | F01 实现；核心版本升至 1.1 |
| `D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py` | `d4afa890cff0d129b56f116e7188fcf30228d69201033f57303259a26be29247` | 必需来源集合／完整 cells 核验 + 五项来源故障回归 |
| `D:\harness work\audit_sa_project\docs\RULE_SCREEN_GUIDE.md` | `84aeed5633641a193a717cae593d8b72a25a7bde7b632942e7a4314ca43062d7` | 版本、证据集合、验证方法与说明修正 |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_006_R1.md` | 本文件 | 新增回执 |

**未改动的关键文件**（保持原字节）：

| 文件 | SHA-256 |
| --- | --- |
| `sql/rules/r01.sql` | `7a19ff2faba088f0b498d9c5004f0a865aac4d59b6f8ed699869051ecbe5e882` |
| `sql/rules/r02.sql` | `58af03e634008fcc61426e15a7433b6370cae0180c0436136de226b8d87b08b3` |
| `sql/rules/r03.sql` | `8a4b84d9ba0ed201ea89a6d58ea5ea67deec9ab8dbe8908e246c79c76876525a` |
| `sql/rules/r04.sql` | `b60e4db078e6632c653adb4ec20f1280c7ef58c70d4496f7caa6cb5cf567ec2d` |
| `docs/EXEC_REPORT_006.md` | `b4fc55a8a83cd7dc72d0b99f328147a729169050ad51b9d37d66d7adde43ec14` |
| `scripts/store_demo_sqlite.py` | `1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446` |
| `sql/demo_schema.sql` | `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205` |
| `scripts/normalize_demo_data.py` | `a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310` |
| `scripts/check_demo_data.py` | `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8` |
| `docs/SPEC_V1.md` | `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236` |
| `docs/AUDIT_CONTRACT_DRAFT.md` | `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27` |

新增测试容器（`data\sqlite_tests\`）：`task006_r1_02`（**最终**，204 个文件）、`task006_r1_01`（故障注入补丁写法错误现场）、`task006_r1_smoke_02`（退款实体冒烟）。旧容器 `task006_04` 等全部保留，未覆盖。

---

## 3. F01 实现说明

`_evidence_block` 现在先取相关退款摘要，再由摘要确定退款主表与退款分摊 ID，一并进入去重后的来源读取集合：

```text
refunds                = 相关退款分摊 + 其退款主表（已结算与非结算都返回，标明 counted_in_net）
refund_payment_ids     = 去重排序后的退款 payment_id
refund_allocation_ids  = 去重排序后的退款 allocation_id
payables               = source_provenance(payables, 相关应付)
payments               = source_provenance(payments, 原付款) ⊕ source_provenance(payments, 退款主表)
allocations            = source_provenance(allocations, 原分摊) ⊕ source_provenance(allocations, 退款分摊)
source_rows            = {payables / payments / allocations: {业务 ID: 原 Excel 行号}}（稳定排序）
evidence.entities      = 上述实体（含 workbook_sha256、sheet、excel_row、完整 cells），(table_name, record_id) 不重复
```

- 退款来源缺项或 `cells` JSON 非法时 `source_provenance` 抛 `RuleScreenError`（消息含阶段、表名、业务 ID），因此**退款来源缺失不会再返回成功**。
- `related_ids` 与 `statistics` 的资金口径未变：退款只通过 `refund_ids`、`related_refunds` 与扩充后的实体／行号追溯。
- 修复后的证据示例（`task006_r1_02\cases\C06b\screening_report.json`，R02 `AP01`）：实体 = `payables AP01`、`payments P01/P02/R01`、`allocations A01/A02/AR01`；`source_rows.payments = {P01:2, P02:3, R01:4}`、`source_rows.allocations = {A01:2, A02:3, AR01:4}`；金额仍为 `paid_total=1000000`、`refund_total=100000`、`net_total=900000`、`overpayment=400000`。

## 4. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 4.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\screen_demo_sqlite.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py'
```

退出码均 **0**。

### 4.2 退款来源实体冒烟

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_r1_smoke_02\C06b\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_r1_smoke_02\C06b\checker_report.json'
```

随后在内存中调用标准化、装载与规则 API；C06b R02、C09b R04、C10b R01／R02 的退款实体覆盖率均为 True，行号含退款主表，核心版本 `TASK-006-rule-core-1.1`。

### 4.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_r1_02'
```

退出码 **0**；关键输出：

```text
[PASS] R1_REQUIRED_SOURCES 逐条必需来源集合与完整 cells 核对（21 个成功输入、34 条线索）
[PASS] R1_REFUND_EVIDENCE 5 个退款相关输入：线索 7、退款实体出现项 22、缺项 0
[PASS] F1_original_payment_source_missing outcome=runtime_error 注入命中=1
[PASS] F2_refund_payment_source_missing outcome=runtime_error 注入命中=1
[PASS] F3_refund_allocation_source_missing outcome=runtime_error 注入命中=1
[PASS] F4_refund_payment_cells_invalid outcome=runtime_error 注入命中=1
[PASS] F5_refund_allocation_cells_invalid outcome=runtime_error 注入命中=1
[PASS] R1_FAULT_DB_UNCHANGED 故障注入未改动数据库字节
输入 29 个：规则成功 21、上游阻断 8、接口阻断 0、运行错误 0；核心调用 32 次（复调用 11）；checker CLI 29 次；测试失败 0
```

命令与日志：`data\sqlite_tests\task006_r1_02\command_log.json`（29 次 checker 调用的完整 `argv`、退出码、独立 stdout／stderr 路径）、`summary.json`（统计、逐案结果、保护与隔离核对、五项故障结果）；每案目录含 `input.xlsx`、`checker_report.json`、`normalized.json`、`load_report.json`、`demo.sqlite`、`screening_report.json`。

### 4.4 其他核验

```powershell
& $py -c "import sys, sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version)"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\screen_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\RULE_SCREEN_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\sql\rules\r01.sql' -Algorithm SHA256
```

退出码均 **0**；四份规则 SQL 哈希与 TASK-006 提交时完全一致。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结果核对；未新增 `.py` 文件。

---

## 5. 自动核验结果（必需来源集合与完整内容）

验证代码**独立**从数据库业务表推导必需集合（相关应付 ＋ 原付款主表／分摊 ＋ 相关退款分摊及其退款主表），不使用当前输出已有实体作为“应有集合”，逐条检查：

- 必需实体齐全，同一 `(table_name, record_id)` 不重复；
- 每个实体的 `workbook_sha256`／`sheet`／`excel_row`／**完整 `cells`（JSON 解码后）**与 `source_records` 逐项精确相等；
- 每个源行号都进入 `source_rows`；
- `related_refunds` 与其实体一致，`counted_in_net` 与结算状态／日期相符。

| 范围 | 线索数 | 必需实体 | 缺项 |
| --- | --- | --- | --- |
| 全部 21 个成功输入 | **34** | 逐条推导 | **0** |
| 重点 5 个输入（C06b、C09b、C10b、S1、S4） | **7** | 退款实体出现项 **22** | **0** |

其中「22 个实体出现项」按线索分别计数（同一退款出现在多条线索时各计一次），与验收单给出的数字一致，**不是** 22 个不同退款，也不是业务异常总数。修复前这 22 项全部缺失、且退款来源缺失不会失败；现在缺项为 0。

## 6. 五项来源故障回归（真实核心调用）

注入方式：只读连接代理（`open_readonly` 包装）拦截目标 `source_records` 查询，不改数据库、不给生产核心加测试开关；断言注入确实由目标查询触发（`注入命中=1`）。

| 用例 | 目标 | 模式 | 实际结果 |
| --- | --- | --- | --- |
| `F1_original_payment_source_missing` | `payments` `P01`（C09b 原付款） | 缺失 | `RuleScreenError`：`[source_provenance] payments P01 缺少来源记录，不能返回“证据完整”` |
| `F2_refund_payment_source_missing` | `payments` `R01`（退款主表） | 缺失 | `RuleScreenError`：`[source_provenance] payments R01 缺少来源记录…` |
| `F3_refund_allocation_source_missing` | `allocations` `AR01`（退款分摊） | 缺失 | `RuleScreenError`：`[source_provenance] allocations AR01 缺少来源记录…` |
| `F4_refund_payment_cells_invalid` | `payments` `R01` | `cells_json` 非法 | `RuleScreenError`：`[source_provenance] payments R01 的 cells JSON 非法：Expecting property name…` |
| `F5_refund_allocation_cells_invalid` | `allocations` `AR01` | `cells_json` 非法 | `RuleScreenError`：`[source_provenance] allocations AR01 的 cells JSON 非法：Expecting property name…` |

五项均为 `RuleScreenError`（非 `RuleScreenBlocked`、非成功），故障注入后数据库字节哈希未变。

## 7. 既有结果与统计（未变）

- 主文件仍为 R01 3／R02 5／R03 2／R04 2，合计 **12** 个结构化键；R02 唯一应付超额合计 **1 600 000** 分；总体勾稽 `master_net` 267 249 329 分与装载报告一致；只读（`mode=ro` + `query_only=1`）与数据库字节未变。
- 逐键对照答案册、14 份有效 fixture 的期望、8 份上游阻断登记、六个小补充场景、三项接口边界与确定性复调用均与 TASK-006 相同（断言未放宽、未删减 `related_refunds`、未取消证据要求）。
- 计数：输入 29（规则成功 21、上游阻断 8、接口阻断 0、运行错误 0）、checker CLI 29、核心调用 32（原 27 + 故障注入 5）、测试失败 0；故障调用与工作簿输入分开统计，预期错误不计为测试失败，也不写成“规则成功且零命中”。

## 8. 失败尝试与修正过程

1. **故障注入补丁写法错误**：把连接工厂直接赋给 `open_readonly`，导致核心拿到的是函数而不是连接（`AttributeError` 在 `enable_query_only` 阶段暴露），5 项故障用例全部误判 → 改为**把工厂应用到真实函数**（`factory(original)`），并在断言中要求 `注入命中=1`，确保测到目标查询而非提前失败。现场保留在 `task006_r1_01`。
2. **PowerShell 写回引入 BOM**：用 `Set-Content -Encoding utf8` 调整测试章节注释时写入 UTF-8 BOM → 检测到后去除 BOM 并复核（交付物均为 UTF-8 无 BOM）。
3. **冒烟脚本引号问题**：内联脚本中的双引号被 PowerShell 5.1 吞掉导致语法错误 → 改用全单引号脚本（现场保留在 `task006_r1_smoke_01`）。
4. 未通过删减 `related_refunds`、取消证据要求、放宽断言或修改答案册让测试过关；未修改上游代码、规格、契约草案、答案册、旧回执与 GPT 验收证据。

## 9. 说明文档修正

- 版本更新为 `TASK-006-rule-core-1.1`（依据加入 `TASK-006-R1.md` 与 `REVIEW_TASK_006.md`）。
- 新增「必需来源集合（TASK-006-R1 起）」小节：明确退款主表与退款分摊须进入 `evidence.entities` 与 `source_rows`，缺项／非法 JSON 即失败；明确 `related_ids` 与资金统计口径不变。
- 验证方法补充「必需来源集合与完整内容自动核验」与「来源失败回归」两项；测试覆盖清单加入新检查与五项故障回归。
- 纠正矛盾表述：原第 8 节“不计算超付、重复付款、风险等级或损失”改为“**按规格计算重复足额付款线索（R01）与净付款超额线索（R02）等确定性事实，但不直接认定损失、舞弊、控制缺陷或审计调整**；不设重要性阈值；不导出审计调整；不计算超付损失金额、风险等级或责任归属”。

## 10. 历史保护对照

- GPT 扩充保护基线（`data/reviews/task006_20261011_064634/source_hashes_after.json`）：记录项 **9600**、变化 **3**（`scripts\screen_demo_sqlite.py`、`tests\test_screen_demo_sqlite.py`、`docs\RULE_SCREEN_GUIDE.md`，恰为本卡授权文件）、缺失 **0**。
- 任务五 R2 的 **8547** 文件冻结基线：**0 变化、0 缺失**；任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874** 基线：均 **0 变化、0 缺失**。
- 说明：任务五 R1 的 8101 基线中存在变化的 3 个文件（装载器、装载测试、装载说明），它们是 TASK-005-R2 卡当时授权的修改，本卡未再改动；该基线早于 R2，故与本卡授权集合不同。
- 测试内建核验的 **32 个受保护文件**（冻结脚本、schema、规格、契约草案、上游回执与说明、装载测试、主演示输入与 22 份 fixture）前后哈希一致；四份规则 SQL 与旧回执哈希见第 2 节。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 11. 偏差、未解决问题与停止状态

- **偏差**：核心版本由 1.0 升至 1.1（与卡一致）；四份规则 SQL、规则版本与业务口径未变。测试驱动在内存中替换 `open_readonly`／`builtins.open`／`io.open` 并恢复，不改真实源码，也不给生产核心加跳过校验的开关。
- **未执行（不主张通过）**：任务七、正式契约、批准控制、Gate 放行、AI 候选结论／等级、人类判断预填；未重跑任务二至五整套测试（新测试调用其冻结 API 并另核对冻结哈希与历史保护）；未做压力测试。
- **已知限制**：来源核验证明本模块读取并保留了 `source_records` 中的完整来源，**不证明来源真实性**，也不声称抵御同权限篡改；规则输出是待核实线索，不含舞弊、损失、控制缺陷或审计调整结论；四条规则涉及金额不相加称为损失。
- **停止状态**：未接入 `data/batches`、未修改任何旧 `batch_manifest.json`、未建立契约或批准控制、未生成 AI 建议、未替人类填写判断、未推进任务七。
- 等待主理人把本回执与 `docs\RULE_SCREEN_GUIDE.md`、`data\sqlite_tests\task006_r1_02` 转交总架构师复验。
