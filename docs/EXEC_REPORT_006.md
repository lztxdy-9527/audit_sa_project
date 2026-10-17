# TASK-006 执行回执（开发态只读 SQL 规则核心与事实溯源）

任务：开发可调用的只读规则核心及开发验证——用新合成工作簿副本 → 真实 checker → 冻结标准化 API → 冻结装载 API → 新规则 API，实现 R01—R04 确定性事实、逐条来源与固定提示。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-006_DRAFT.md`、`docs/reviews/REVIEW_TASK_005_R2.md`、`docs/SQLITE_LOAD_GUIDE.md`、`docs/SPEC_V1.md` 第 1、3—6 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 3—5 节、`docs/DEMO_DATA_GUIDE.md` 答案册使用边界。
状态：本卡范围内工作完成并自检通过，**停止于此**；未接入正式批次，未做 AI 建议或人类判断预填，未推进任务七。

> 命令均为完整参数、不使用省略号；未执行的验证一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| **公共 API** | `screen_sqlite(database_path, load_report: dict, *, cutoff_date="2026-09-30") -> dict`；只提供 Python API，**不写任何文件**、不推进任何批次 |
| **只读实现** | SQLite URI `mode=ro` 打开（无可创建连接回退）+ 实测 `PRAGMA query_only = 1`；只用固定 `SELECT`／CTE；不建临时表／视图，无 DDL／DML／`executescript`；查询前后数据库字节哈希相等 |
| **前提核对** | 装载报告（`DEV_SQLITE_VERIFIED`／开发模式／装载与 schema 版本／路径与字节哈希一致）→ 冻结装载器与 schema 哈希 → 从数据库**实读** `run_metadata`（模式、版本、输入哈希、对象指纹、装载器／schema 哈希）→ 业务日期范围；任一不符即 `RuleScreenBlocked` |
| **四条规则** | R01 现存重复足额（`(ap_id, payee_supplier_id)` 组内逐付款净额＝应付金额且至少两笔）；R02 应付净付款超额（唯一应付、跨对象，严格大于）；R03 台账未找到关联（逐分摊，区分 `EMPTY_AP_ID`／`AP_NOT_IN_LEDGER`）；R04 收款对象不同（逐分摊、按原字符串精确比较）；R03／R04 不加“净额大于 0”过滤 |
| **退款口径** | 退款按 `original_allocation_id` 先汇总再关联原分摊；非结算退款不抵减；全额退款后仍保留 R03／R04 历史事实 |
| **命中键与证据** | 结构化键（不拼字符串、每键恰好一次、稳定排序）；`amounts_cents` 整数分；`related_ids`、`source_rows`、`evidence`（`source_records` 的完整 `cells` 解码保留）、固定 `fact` 与 R03／R04 固定提示 |
| **开发验证** | **29 个输入，测试失败 0，退出 0**：规则成功 **21**、上游阻断 **8**（不写“成功零命中”）、接口阻断 **0**、运行错误 **0**；checker CLI **29** 次；核心调用 **27** 次（复调用 **6**） |
| **答案册对照** | 主文件 **12** 个结构化键（R01 3／R02 5／R03 2／R04 2）逐键、逐已登记金额、相关 ID、原 Excel 行号全部一致；R02 唯一应付超额合计 **1 600 000** 分一致 |
| **答案隔离** | 静态检查（核心与 SQL 不引用答案册／生成器）＋ 运行期守卫（守卫下成功且实际拦截 8 次文件读取，未触碰 `evaluation/`）＋ 生成器未被导入 ＋ **全部 21 份核心输出保存完成后**才读取答案册 |
| **上游冻结** | 装载器 `1abfad89…`、schema `7e0c6463…`、标准化器 `a2bae49e…`、checker `a7e5eb67…`、接收器 `52195620…`、生成器 `e899aa2f…`、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| **历史保护** | TASK-005-R2 验收基线 **8547 个文件**：**0 个变化、0 个缺失**；TASK-004-R1 基线 6511 个、TASK-003-R3 基线 4902 个、任务二基线 874 个：均 0 个变化 |
| **未执行** | AI 候选结论／等级、人类判断预填、正式契约、批准控制、任务七、压测；未安装依赖、未初始化 Git |

---

## 2. 实际新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\screen_demo_sqlite.py` | `e4a0a5daf82731c6838ee7a93f90c0263fac0386d5198178ea6147c0f2c5edab` |
| `D:\harness work\audit_sa_project\sql\rules\r01.sql` | `7a19ff2faba088f0b498d9c5004f0a865aac4d59b6f8ed699869051ecbe5e882` |
| `D:\harness work\audit_sa_project\sql\rules\r02.sql` | `58af03e634008fcc61426e15a7433b6370cae0180c0436136de226b8d87b08b3` |
| `D:\harness work\audit_sa_project\sql\rules\r03.sql` | `8a4b84d9ba0ed201ea89a6d58ea5ea67deec9ab8dbe8908e246c79c76876525a` |
| `D:\harness work\audit_sa_project\sql\rules\r04.sql` | `b60e4db078e6632c653adb4ec20f1280c7ef58c70d4496f7caa6cb5cf567ec2d` |
| `D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py` | `e5d494d9b309dc8aabd3216597fddc3d92418613d036960bab2c297970dc3f72` |
| `D:\harness work\audit_sa_project\docs\RULE_SCREEN_GUIDE.md` | `9dc45fe5bd25ba9c97a656bdb3dd175493a82ee79261f2da3888396a518bdab6` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_006.md` | 本文件（新增） |

新增测试容器（`data\sqlite_tests\`）：`task006_04`（**最终**，204 个文件）、`task006_03`（答案册读取顺序修正后）、`task006_02`（守卫未生效现场）、以及 `task006_smoke_01/02`（冒烟）。全部保留，未覆盖；未向历史容器补文件。

---

## 3. 实现要点

- **前提核对顺序**：截至日（仅支持 `2026-09-30`）→ 路径（`data/sqlite_tests` 内已存在的最终库；拒绝目录、缺失、越界、`.staging`）→ 实际字节哈希 → 装载报告字段 → 冻结装载器／schema 哈希 → 数据库 `run_metadata` 实读核对 → 业务日期范围（`payables.ap_date`、`payments.payment_date` 全部落在 `2026-09-01`—`2026-09-30`，范围不符即阻断而非 `WHERE` 静默过滤）。
- **SQL 粒度**：四份 SQL 自包含共同基础 CTE（`settled_pay_alloc`／`settled_refund_alloc`／`base`），参数仅 `:cutoff_start`、`:cutoff_end`；退款先按 `original_allocation_id` 汇总再关联，避免多条退款重复累计原付款金额。R01 先按 `(ap_id, payee_supplier_id, payment_id)` 求净额、再筛净额等于应付金额的付款、最后按组统计 `HAVING COUNT(*) >= 2`，一条组线索列出全部满足条件的付款。
- **总体勾稽**：独立从 `payments` 与 `allocations` 粒度计算已结算 PAY／REFUND 总额、已知／缺失（空 `ap_id` 与台账外分开）关联净额与主表净额，逐项对照装载报告；不一致即 `RuleScreenError`。
- **证据**：`source_records` 读取 `workbook_sha256`／`sheet`／`excel_row`／完整 `cells`（JSON 解码保留）；来源缺项或非法 JSON 明确失败；R03 无应付记录时在 `evidence.missing` 明示缺失。
- **严格关闭**：正常关闭失败即 `RuleScreenError`（不返回成功）；已有错误后的清理关闭失败仅作附记，不覆盖最初错误。
- **统计口径**：`statistics.involved_payments` 为四规则涉及的唯一原付款事件及其**整笔**已结算总额（14 笔、6 100 000 分），并注明该口径不能当作缺失关联分摊额或损失；`r02_overpayment_total_cents` 按唯一应付汇总一次。

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

### 4.2 主文件全链路冒烟

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_smoke_02\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_smoke_02\checker_report.json'
```

随后在内存中依次调用标准化、装载与规则 API；checker 退出 **0**，规则返回 `DEV_RULES_COMPUTED`，命中数 `{'R01': 3, 'R02': 5, 'R03': 2, 'R04': 2, 'total': 12}`，超额合计 1 600 000 分，`master_net` 267 249 329 分。

### 4.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task006_04'
```

退出码 **0**；输出“输入 29 个：规则成功 21、上游阻断 8、接口阻断 0、运行错误 0；核心调用 27 次（复调用 6）；checker CLI 29 次；测试失败 0”。
命令与日志：`data\sqlite_tests\task006_04\command_log.json`（29 次 checker 调用的完整 `argv`、退出码、独立 stdout／stderr 路径）、`summary.json`（统计、逐案结果、保护与隔离核对）；每个案例目录内含 `input.xlsx`、`checker_report.json`、`normalized.json`、`load_report.json`、`demo.sqlite`、`screening_report.json`。

### 4.4 其他核验

```powershell
& $py -c "import sys, sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version)"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\screen_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_screen_demo_sqlite.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\RULE_SCREEN_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\store_demo_sqlite.py' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结果核对；未新增 `.py` 文件。

---

## 5. 实际结果与对照

### 5.1 统计（从实际结果计算）

| 项目 | 数量 |
| --- | --- |
| 输入案例数 | **29**（主文件 + 22 份 fixture + 6 个小补充场景） |
| 规则成功 | **21** |
| 上游阻断（checker／标准化阶段，登记“未执行／上游阻断”） | **8** |
| 接口阻断 | **0** |
| 运行错误 | **0** |
| 测试失败 | **0** |
| 真实 checker CLI 调用 | **29** |
| 规则核心调用 | **27**（其中复调用 **6**：确定性 2、运行期守卫 1、接口边界 3） |

### 5.2 主文件逐条对照（答案册 `ground_truth.json`）

| 项目 | 实测 |
| --- | --- |
| 命中键 | R01 3、R02 5、R03 2、R04 2，合计 **12**，无漏报、无多报、无重复 |
| R01 | `AP00987`／`AP00988`／`AP00989` 各 `S001`；`payable_amount=500000`、`net_per_payment` 与 `net_total=1000000` 逐项一致 |
| R02 | `AP00987`—`AP00991`；付款总额 1 000 000／1 000 000／1 000 000／550 000／550 000，超额 500 000／500 000／500 000／50 000／50 000 分；合计 **1 600 000** 分 |
| R03 | `AL01002`（未填写关联）、`AL01003`（填写的标识不在台账）；`allocated_amount=paid_amount=500000`、`refunded=0`、`net=500000` |
| R04 | `AL01004`／`AL01005`，`payable_supplier_id=S001`、`payee_supplier_id=S002`，`payable_amount=500000`、`net_amount=500000` |
| 相关 ID | `related_ids` 的 `payable_id`／`payment_ids`／`allocation_ids`／`refund_ids`（R03／R04 另含 `missing_kind`／双方 ID）逐项一致 |
| 原 Excel 行号 | `source_rows` 与答案册登记行号逐项一致（如 `AP00987`=988、`PM00987`=988、`AL00992`=993） |
| 完整 cells 证据 | `evidence.entities` 携带 `source_records` 的完整 `cells`，与数据库来源逐项核对通过 |

### 5.3 14 份质量有效 fixture（对照 `fixture_expectations.json`）

全部逐键、逐已登记金额一致；重点项：C03 合并付款无命中且整笔付款只计一次（1 000 000 分）；C06 全额退款后无 R01／R02；C06b 仅 R02 且超额 400 000 分；C07b R03 涉及分摊额 200 000 分（非整笔 5 000 元）；C09b 全额退款后仍保留 R04 且 `refunded_amount=500000`、`net_amount=0`；C10 非结算无命中且已结算为 0；C10b 未结算退款不抵减（`refund_total=0`）。

### 5.4 8 份质量阻断 fixture

保留真实 checker 问题（退出 1 且 `issue_counts_by_code` 非空），登记“未执行／上游阻断”，**未建立数据库、未调用规则核心、未写成“成功且零命中”**。

### 5.5 六个小补充场景（预期按卡固定，不依赖答案册）

| 场景 | 实测 |
| --- | --- |
| S1 C07 原缺失关联付款全额退款 | 仍一条 R03，`allocated=500000`、`refunded=500000`、`net=0`；退款保持原空关联；R01／R02／R04 无命中 |
| S2 三笔足额付款 | R01 一条列出三个 `payment_id`（`net_total=1500000`）；R02 一条超额 1 000 000 分（三笔仍是一条组线索） |
| S3 第二笔改为另一已登记对象 | R02 一条超额 50 000 分；第二笔原分摊另命中 R04 且分摊额 250 000 分；无 R01 |
| S4 追加 FAILED／VOIDED 退款 | 两笔足额原付款仍命中 R01／R02（`refund_total=0`）；三种非结算退款 `counted_in_net=false`，证据含状态 `FAILED/PENDING/VOIDED` |
| S5 分组键不碰撞 | `("A|B"," C' ")` 与 `("A","B| C' ")` 两条 R01、两条 R02 各超额 500 000 分；R03／R04 无命中；空格、引号与前导零原样保留 |
| S6 有应付无资金事件 | 四规则空数组，资金净额 0，应付与来源保留，未因退款分组为空而阻断 |

### 5.6 接口边界与确定性

| 检查 | 实测 |
| --- | --- |
| 缺失数据库 | `RuleScreenBlocked`，且**未创建**文件 |
| 字节与装载报告不符 | `RuleScreenBlocked`（原因指向 `database_sha256`；已同步正确路径，证明测到哈希核验而非路径不符） |
| 未发布 `.staging` | `RuleScreenBlocked`（原因含“未发布的暂存库”） |
| 复调用确定性 | 同一数据库两次调用的 `findings` 结构化键、金额与顺序完全相等且与首次一致；数据库字节哈希未变 |

### 5.7 只读与答案隔离

- 只读：`{"uri_mode": "ro", "query_only": 1}`，查询前后数据库字节哈希相等（`database_unchanged=true`）。
- 答案隔离：核心与四份 SQL 的静态文本不含 `ground_truth`／`fixture_expectations`／`evaluation`／`make_demo_data`；运行期文件读取守卫下核心仍返回 `DEV_RULES_COMPUTED`，守卫**实际拦截 8 次**文件读取（SQL 与冻结文件哈希）且**未触碰** `evaluation/`；`sys.modules` 中无生成器模块；答案册首次读取发生在 **21/21** 份核心输出全部保存之后。

## 6. 失败尝试与修正过程

1. **测试脚本两处语法错误**（多行 lambda 赋值续行）：`py_compile` 拦下，改为括号包裹的单行表达式（未创建容器）。
2. **S1 断言取错层级**：写成 `item["related_refunds"]`，实际该键在 `evidence` 下 → 改为 `item["evidence"]["related_refunds"]`。
3. **答案册读取顺序**：初版在主文件／fixture 对照之后才跑六个小样，导致“答案册首次读取”早于最后 6 份输出保存 → 把小补充场景整体前移，最终 21/21 份核心输出保存完成后才读取答案册。
4. **运行期守卫一度无效**：只替换了 `builtins.open`，而 `Path.read_bytes()` 走 `io.open`，守卫记录为 0 次 → 改为同时替换 `io.open` 并**断言守卫实际拦截次数 > 0**（修正后为 8 次），否则判失败。
5. **冒烟脚本引号问题**：PowerShell 5.1 传递内联脚本时吞掉双引号导致语法错误 → 改用全单引号的探测脚本；现场保留在 `task006_smoke_01`。
6. 未修改上游代码、规格、契约草案、答案册、旧回执与历史测试产物；未向 GPT 验收目录追加文件。

## 7. 历史保护对照

- TASK-005-R2 验收基线（`data/reviews/task005_r2_20261011_062240/source_hashes_after.json`）**8547 个文件**：变化 **0**、缺失 **0**。
- TASK-005-R1 验收基线 8101 个中变化的 3 个即 TASK-005-R2 授权的装载器／测试／装载说明（该基线早于 R2）；TASK-004-R1 基线 **6511 个**、TASK-003-R3 基线 **4902 个**、任务二 R2 基线 **874 个**：均 **0 个变化、0 个缺失**。
- 上游冻结哈希见第 1 节；测试内建核验的 **32 个受保护文件**（冻结脚本、schema、规格、契约草案、上游回执与说明、装载测试、主演示输入与 22 份 fixture）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 8. 偏差、未解决问题与停止状态

- **偏差**：为在测试中证明隔离边界，测试驱动替换了内存中的 `builtins.open`／`io.open` 并在结束后恢复（不改真实源码）；规则核心未新增任何仅供测试的开关。
- **未执行（不主张通过）**：AI 候选结论／等级、人类初步与最终判断保存、正式契约、批准控制、Gate 1／Gate 2 放行、任务七；未重跑任务二至五整套测试（新测试调用其冻结 API 并另核对冻结哈希与历史保护）；未做压力测试。
- **已知限制**：本层只验证消费的接口与来源证据，不实现 ERP 质量 checker；本地哈希与只读保护证明未改输入，**不声称抵御同权限篡改**；不证明真实 ERP 兼容性或真实数据完整性；规则输出是待核实线索，不含舞弊、损失、控制缺陷或审计调整结论；四条规则的涉及金额不相加称为损失。
- **停止状态**：未接入 `data/batches`、未修改任何旧 `batch_manifest.json`、未建立契约或批准指纹控制、未生成 AI 建议、未替人类填写判断、未推进任务七。
- 等待主理人把本回执与 `docs\RULE_SCREEN_GUIDE.md`、`data\sqlite_tests\task006_04` 转交总架构师验收。
