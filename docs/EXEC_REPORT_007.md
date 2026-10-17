# TASK-007 执行回执（Python 独立复算与 SQL 事实一致性复核）

任务：开发可调用的独立复算核心及开发验证——用另一套 Python 整数实现从标准化记录复算 R01—R04 事实，与既有 SQL 筛查报告逐项比较，并在交给人类判断前发现可验证差异。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-007_DRAFT.md`、`docs/reviews/REVIEW_TASK_006_R1.md`、`docs/SPEC_V1.md` 第 3—7 节、`docs/AUDIT_CONTRACT_DRAFT.md` 第 4—6 节、`docs/RULE_SCREEN_GUIDE.md`、`docs/NORMALIZATION_GUIDE.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务八，未接入正式批次，未批准任何 Gate，未生成 AI 判断或人类判断预填值。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| **公共 API** | `verify_rule_facts(normalized: dict, screening_report: dict) -> dict`；只接收两个内存对象、只返回报告，**不写文件、不修改入参**；不读数据库／Excel／答案册／历史复核结果，不执行 SQL、不调用筛查核心、不导入生成器或旧测试／QA 脚本；标准库仅用 `json`／`hashlib` |
| **算法分开实现** | 以 `records[*].data` 为输入，用字典分组与整数循环复算四规则；退款按 `original_allocation_id` 汇总后抵减；另从 `payments`／`allocations` 两种粒度独立求资金勾稽，**不从 findings 反推应有结果**，不使用 `normalized.amount_reconciliation` 汇总值 |
| **对象指纹** | 自行按固定 JSON 规范（`ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False`）计算 `normalized` 与 `screening_report` 的 SHA-256，与报告 `load_source`／`run_metadata` 绑定值比较；不导入装载器函数 |
| **输入前提** | 版本／模式／`next_step_allowed`／质量结果／四表记录与字段类型／日期范围／规则版本与 SQL 哈希／装载状态与版本／来源哈希／对象指纹／数据库 before=after=load_source 且 `database_unchanged`／`read_only={ro,1}`；不成立即 `CrossCheckBlocked` |
| **结果** | 全部一致 → `DEV_CROSSCHECK_MATCHED`／`matched=true`；存在差异 → `DEV_CROSSCHECK_MISMATCH`／`matched=false` + 差异列表（`code`／`hit_key`／`field_path`／`expected`／`actual`）；两者均开发态、`next_step_allowed=false` |
| **开发验证** | **29 个工作簿输入，测试失败 0，退出 0**：初次一致 **21**、上游阻断 **8**、初次不一致 **0**、前提阻断 **0**、意外运行错误 **0**；checker CLI **29** 次、SQL 核心调用 **21** 次、复核调用 **40** 次 |
| **差异检查** | **11 项**故意改错 SQL 报告的检查全部得到 `DEV_CROSSCHECK_MISMATCH` 且命中指定代码（`MISSING_HIT`／`EXTRA_HIT`／`DUPLICATE_HIT`／`AMOUNT_MISMATCH`／`STATISTIC_MISMATCH`／`SOURCE_ENTITY_MISSING`／`SOURCE_VALUE_MISMATCH`／`REFUND_FACT_MISMATCH`／`RELATED_IDS_MISMATCH`／`RECONCILIATION_MISMATCH`／`SOURCE_ROW_MISMATCH`） |
| **前提阻断** | **5 项**（源哈希不匹配／对象指纹不匹配／非开发态／不支持的截至日／质量非 pass）全部 `CrossCheckBlocked`，未返回成功或差异报告 |
| **确定性与隔离** | 同一合法输入复调用返回对象**精确相等**；两次入参规范指纹不变；测试数据库字节不变；核心静态无数据库／上游核心／答案册引用；运行期守卫下核心成功且**受限路径读取 0**，守卫以受控探测确认生效 |
| **历史保护** | TASK-006-R1 扩充保护基线（10236 项）**0 变化、0 缺失**；任务五 R2 的 8547、任务四 R1 的 6511、任务三 R3 的 4902、任务二 R2 的 874 基线均 0 变化；冻结筛查核心与四份规则 SQL 哈希未变 |

---

## 2. 实际新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py` | `feaa72d5e601d987864ebb4f69056446848d2d746eaf525cb8747c7090ac0677` |
| `D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py` | `ee338db4570c22e2237358c7a37cd01a3673c27d98fdd549accd7addb9be2966` |
| `D:\harness work\audit_sa_project\docs\RULE_CROSSCHECK_GUIDE.md` | `40eda9d1ec3bff3c4f4be27b4d4dfb6124b3933f2ff369df94af230839bad5b4` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_007.md` | 本文件（新增） |

新增测试容器（`data\sqlite_tests\`）：`task007_02`（**最终**，240 个文件）、`task007_01`（同一 29 输入，结构文件去重前现场）、`task007_smoke_01/02`（冒烟）。全部保留，未覆盖；未修改 GPT 验收目录或任何历史容器。

## 3. 未改动的冻结文件

| 文件 | SHA-256 |
| --- | --- |
| `scripts/screen_demo_sqlite.py` | `1b123766b57849c1d64a5a18cb504fbeb03f563bcd96b2de708586f19c9e71fe` |
| `sql/rules/r01.sql` | `7a19ff2faba088f0b498d9c5004f0a865aac4d59b6f8ed699869051ecbe5e882` |
| `sql/rules/r02.sql` | `58af03e634008fcc61426e15a7433b6370cae0180c0436136de226b8d87b08b3` |
| `sql/rules/r03.sql` | `8a4b84d9ba0ed201ea89a6d58ea5ea67deec9ab8dbe8908e246c79c76876525a` |
| `sql/rules/r04.sql` | `b60e4db078e6632c653adb4ec20f1280c7ef58c70d4496f7caa6cb5cf567ec2d` |
| `scripts/store_demo_sqlite.py` | `1abfad898e18c54fd5dd81e44973d078187b2837838638c1a6f46e9c8c74a446` |
| `sql/demo_schema.sql` | `7e0c64637aa115a3d636e333b0855d7e3cfe84081dd88d84d11b9df42b918205` |
| `scripts/normalize_demo_data.py` | `a2bae49e3686c6bca012fd4207b6a39424e21515b82af8ce8e7c05b276b72310` |
| `scripts/check_demo_data.py` | `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8` |
| `docs/SPEC_V1.md` | `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236` |
| `docs/EXEC_REPORT_006_R1.md` | `ac75b955efae183022e0ffa147a3791c5e441255aad31102b18d8f988a6e3071` |

## 4. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 4.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py'
```

退出码均 **0**。

### 4.2 冒烟（主文件／C06b／C09b／C07b 的复算与比对）

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_smoke_02\MAIN\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_smoke_02\MAIN\checker_report.json'
```

随后在内存中调用标准化、装载、SQL 筛查与复核 API；各案例均返回 `DEV_CROSSCHECK_MATCHED`（主文件复算 3／5／2／2，差异 0）。

### 4.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_02'
```

退出码 **0**；关键输出：

```text
工作簿输入 29 个：初次一致 21、上游阻断 8、初次不一致 0、前提阻断 0、意外运行错误 0
checker CLI 29 次、SQL 核心调用 21 次、复核调用 40 次、预期不一致检查 11 项、前提阻断检查 5 项
[PASS] M1_missing_hit 期望 MISSING_HIT 实际 ['MISSING_HIT']  …（M1—M11 全部 PASS）
[PASS] P1—P5 前提阻断 outcome=blocked
[PASS] D1_determinism 复调用一致=True 入参指纹不变=True 数据库字节不变=True
[PASS] I1_static_imports / I2_runtime_guard
受保护文件前后哈希一致: True（37 个）
```

命令与日志：`data\sqlite_tests\task007_02\command_log.json`（29 次 checker 调用的完整 `argv`、退出码、独立 stdout／stderr 路径）；`stdout.txt`／`stderr.txt` 为**本入口自身**的完整捕获；结构化检查详情见 `summary.json`、`crosscheck_results.json`、`mismatch_checks.json`、`precondition_checks.json`、`isolation_checks.json`；每案目录含 `input.xlsx`、`checker_report.json`、`normalized.json`、`load_report.json`、`demo.sqlite`、`screening_report.json`、`crosscheck_report.json`；被改错的对象另存于 `mutations\*.json`。

### 4.4 其他核验

```powershell
& $py -c "import sys, sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version)"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\RULE_CROSSCHECK_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\screen_demo_sqlite.py' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结构化文件核对；未新增 `.py` 文件。

---

## 5. 逐项检查与分类计数

### 5.1 分类计数（从实际结果计算）

| 项目 | 数量 |
| --- | --- |
| 工作簿输入 | **29**（主文件 + 22 fixture + 6 小样） |
| 初次 MATCHED | **21** |
| 上游阻断（SQL／复核未执行） | **8** |
| 初次 MISMATCH | **0** |
| 复核调用被阻断（前提） | **0** |
| 意外运行错误 | **0** |
| checker CLI 调用 | **29** |
| SQL 筛查核心调用 | **21** |
| 独立复核调用 | **40**（29 输入初次 21 + 差异检查 11 + 前提阻断 5 + 确定性 2 + 隔离 1） |
| 预期不一致检查 | **11**（全部命中指定代码） |
| 前提阻断检查 | **5**（全部 `CrossCheckBlocked`） |
| 确定性／隔离检查 | **3** |
| 测试失败 | **0** |

### 5.2 11 项差异检查（深拷贝 SQL 报告、每次只改一处）

| 检查 | 目标 | 期望代码 | 实测 |
| --- | --- | --- | --- |
| M1 | 主文件删一条 R03 | `MISSING_HIT` | 一致命中 |
| M2 | 复制一条 R02 改为不存在的应付键 | `EXTRA_HIT` | 一致命中 |
| M3 | 原样追加已有 finding | `DUPLICATE_HIT` | 一致命中（未因字典覆盖而漏） |
| M4 | 一个 R02 `overpayment` 加 1 分 | `AMOUNT_MISMATCH` | 一致命中 |
| M5 | R02 超额合计统计加 1 分 | `STATISTIC_MISMATCH` | 一致命中 |
| M6 | C09b 删除退款主表证据实体 | `SOURCE_ENTITY_MISSING` | 一致命中 |
| M7 | 一个实体 `cells.raw_value` 改动 | `SOURCE_VALUE_MISMATCH` | 一致命中 |
| M8 | C09b 已结算退款 `counted_in_net` 改 false | `REFUND_FACT_MISMATCH` | 一致命中 |
| M9 | 一个 R04 `related_ids.payee_supplier_id` 改为应付供应商 | `RELATED_IDS_MISMATCH` | 一致命中 |
| M10 | 主文件 `missing_payable_link_net` 加 1 分 | `RECONCILIATION_MISMATCH` | 一致命中 |
| M11 | 仅改一个 `source_rows` 原 Excel 行号 | `SOURCE_ROW_MISMATCH` | 一致命中 |

所有改错对象另存为 `mutations\<name>.json`，其差异详情写入 `mismatch_checks.json`；改动均不触及身份前提字段，因此测到的是对应差异比较而非提前阻断。派生数量／统计随删增线索出现更多差异属合理，未要求只报一条。

### 5.3 5 项前提阻断

| 检查 | 注入 | 实测 |
| --- | --- | --- |
| P1 源哈希不匹配 | `load_source.input_sha256`／`run_metadata.input_sha256` 改为全 0 | `CrossCheckBlocked`（含 `input_sha256`） |
| P2 对象指纹不匹配 | `normalized` 中一条付款金额 +1 分 | `CrossCheckBlocked`（含 `normalized_payload_sha256`） |
| P3 非开发态 | `screening_report.mode = "PRODUCTION"` | `CrossCheckBlocked`（含 `mode`） |
| P4 不支持的截至日 | `cutoff_date = "2026-09-29"` | `CrossCheckBlocked`（含 `cutoff_date`） |
| P5 质量非 pass | `normalized.quality_report.result = "issues_found"` | `CrossCheckBlocked`（含 `quality_report`） |

五项均未返回 MATCHED 或 MISMATCH 报告；字段与原因保存在 `precondition_checks.json`。

### 5.4 答案册额外验证与顺序

- 主文件复算结果与答案册 `ground_truth.json` 的 12 个结构化键、登记金额逐项一致；R02 唯一应付超额合计 **1 600 000** 分一致。
- 14 个有效 fixture 的复算结果与 `fixture_expectations.json` 登记键／金额一致；8 个质量阻断输入只登记“上游阻断、SQL／复核未执行”，未记为匹配且零命中。
- 答案册首次读取发生在**全部 21 份初次结果保存完成之后**（`answer_book_first_read_after_outputs_saved = 21`，`outputs_saved = 21`）；六个小样输入从已验收容器**只读复制 `input.xlsx`**，未使用其中旧报告作为答案。

### 5.5 确定性与隔离

- **确定性**：同一合法输入两次调用返回对象的规范 JSON 完全相同，且与首次结果一致；两次调用前后 `normalized`／`screening_report` 的规范指纹不变；测试数据库字节哈希不变。
- **静态隔离**：独立核心源码不含 `import sqlite3`、`openpyxl`、`normalize_demo_data`、`store_demo_sqlite`、`screen_demo_sqlite`、`make_demo_data`、`ground_truth`、`fixture_expectations`、`evaluation`、`sql/rules`、`subprocess`、旧 QA 脚本引用。
- **运行期隔离**：在替换 `builtins.open`／`io.open` 的守卫下，先用受控探测（读取核心文件）确认守卫生效，再调用核心：核心返回 MATCHED，**受限路径（规则 SQL 目录／`evaluation`／GPT 验收 cases）读取 0 次**；所有内存替换均已恢复。测试驱动为上游筛查读取 SQL、为最终验证读取答案册，守卫只在核心调用期间生效。

## 6. 历史保护对照

- TASK-006-R1 扩充保护基线（`data/reviews/task006_r1_20261011_072212/source_hashes_after.json`）：记录项 **10236**、变化 **0**、缺失 **0**。
- 任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874** 文件基线：均 **0 变化、0 缺失**。
- 说明：TASK-006 验收的 9600 项基线中存在变化的 3 个文件（筛查核心、筛查测试、筛查说明），它们是 TASK-006-R1 卡授权的修改，本卡未再改动；该基线早于 R1。
- 测试内建核验的 **37 个受保护文件**（冻结脚本、schema、四份规则 SQL、规格、契约草案、上游回执与说明、筛查测试、主演示输入与 22 份 fixture）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 7. 失败尝试与修正过程

1. **`_entities_for` 签名重构漏改一处调用点**：改为显式传入工作簿哈希后，R03／R04 分支仍用旧签名，首次冒烟以 `TypeError` 暴露（被包装为 `CrossCheckError`）→ 更正全部调用点；同时移除了早期用 `id(index)` 作键的模块级临时字典，改为显式传参。
2. **遗留占位代码**：编写过程中一度留下两处无效代码块（一个会**提前读取答案册**、一个恒假条件）→ 运行前删除；前者若保留会破坏“初次结果保存后才读答案册”的顺序证据。
3. **结构化文件重复行**：`crosscheck_results.json` 起初对 MAIN 记录两行（基本检查与答案册对照各一次）→ 改为按 `(case, kind)` 覆盖，结构化文件对每个输入恰好一行（29 行）。
4. **内联脚本引号问题**：PowerShell 5.1 吞掉内联 Python 中的双引号导致语法错误 → 改用全单引号探测脚本；现场保留在 `task007_smoke_01`。
5. 未修改任何上游代码、SQL、说明、回执、任务卡、验收单、答案册或历史容器；未修改 GPT 验收目录。

## 8. 偏差、未解决问题与停止状态

- **偏差**：测试驱动在内存中替换 `builtins.open`／`io.open` 做运行期隔离守卫并随后恢复，未给生产核心加入任何测试开关；独立核心不含 CLI。
- **未执行（不主张通过）**：任务八、正式事实底稿展示、正式契约、批准控制、Gate 放行、人类判断保存、后置 AI 建议、真实 ERP 接入、OCR、RAG、UI、压力测试；未重跑任务二至六整套测试（新链路实际调用其冻结 API 并另核对冻结哈希与历史保护）。
- **已知限制**：本层只比较**报告内部声明与绑定**，**不实际读取或重验数据库字节**；只核对本输入下标准化记录与报告证据是否一致，**不证明来源真实性**，不声称抵御同权限篡改；复核一致**不构成审计结论**，也不替代人类独立判断；不补零、不静默删记录、不修复输入、不回写报告。
- **停止状态**：未接入 `data/batches`、未修改任何旧 `batch_manifest.json`、未建立契约或批准控制、未批准 Gate、未生成 AI 建议、未替人类填写判断、未推进任务八。
- 等待主理人把本回执与 `docs\RULE_CROSSCHECK_GUIDE.md`、`data\sqlite_tests\task007_02` 转交总架构师验收。
