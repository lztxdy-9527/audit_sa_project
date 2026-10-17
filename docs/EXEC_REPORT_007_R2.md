# TASK-007-R2 执行回执（补齐命中键的字符串类型检查）

任务：修复 TASK-007-R1 复验发现的唯一残留缺口——命中键用 `str(value)` 构造身份键，导致字符串 `"1"` 与整数 `1`（`"True"`／`true`、`"None"`／`null`）被判为同一 ID 而误报一致。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-007-R2.md`、`docs/reviews/REVIEW_TASK_007_R1.md`、`docs/tasks/TASK-007-R1.md`、`docs/EXEC_REPORT_007_R1.md`、`docs/RULE_CROSSCHECK_GUIDE.md`、`docs/tasks/TASK-007_DRAFT.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务八，未接入 `data/batches`，未批准任何 Gate，未生成 AI 判断或人类判断预填值。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。旧回执 `EXEC_REPORT_007.md` 与 `EXEC_REPORT_007_R1.md` 保持原字节，未回写。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| **最小修复** | 命中键身份键由「字段名 + 值类型 + `repr(值)`」构成，**不再 `str(value)` 归一化**：字符串 `"1"`／`"True"`／`"None"` 与整数 `1`／布尔 `true`／`null` 是**不同身份**，不会合并为同一个键，也不会因渲染相同而误报一致 |
| **处理方式（固定）** | 选择保留观察值与类型并返回明确 **MISMATCH**：新增差异代码 `HIT_KEY_TYPE_MISMATCH`，记录字段路径、预期（字符串）值与原类型、实际值与实际类型；`hit_keys` 维度 `matched=false`；身份键不同同时产生对应的 `MISSING_HIT`／`EXTRA_HIT` |
| **命中键契约校验** | 新增 `HIT_KEY_FIELDS` 与 `_validate_hit_key()`：`rule_id` 与各规则规定的 ID 字段（R01 `ap_id`／`payee_supplier_id`、R02 `ap_id`、R03／R04 `allocation_id`）必须是非空**字符串**；字段集合不符也记录；合法的 `"1"`／`"True"`／`"None"`／`"0001"` 与含空格／单引号／竖线的字符串 ID 不因外观被禁止或规范化 |
| **诊断配对** | 「渲染相同但类型不同」的键会逐字段给出 `HIT_KEY_TYPE_MISMATCH`（例如 `hit_key.ap_id`，expected `'1'`(str) vs actual `1`(int)），`_key_render()` 仅用于诊断配对，**不承担身份归一化** |
| **版本** | 复核核心升为 `TASK-007-crosscheck-1.2`；说明页首与结果字段表的 `crosscheck_version` 一并统一为 1.2（修正 R1 验收单附带指出的文案不一致） |
| **保持** | 四条规则、复算公式、比较层其余部分、上游模块与答案册**均未改动**；漏报／多报／重复命中／规则身份／S5 分组键不碰撞等检查保留 |
| **开发验证** | **29 个工作簿输入，测试失败 0，退出 0**：初次一致 21、上游阻断 8；checker CLI **29** 次、SQL 核心 **21** 次、复核调用 **58** 次（原 50 + 四组正负配对 8） |
| **四组配对回归** | 正向控制全部 `MATCHED`；负向全部 `MISMATCH` 且含 `HIT_KEY_TYPE_MISMATCH`，`hit_keys.matched=false`；单点变更路径经结构化比对确认只有指定字段改变 |
| **历史保护** | TASK-007-R1 验收扩充基线（11626 项）**变化 3、缺失 0**（恰为本卡授权三个文件）；任务六 R1 的 **10236**、任务五 R2 的 8547、任务四 R1 的 6511、任务三 R3 的 4902、任务二 R2 的 874 基线均 **0 变化、0 缺失**；旧回执与全部 GPT 证据保持原字节 |

---

## 2. 修改与新增的文件

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py` | `8fe75bfe58f66e006828cfe6311ae9da8c722db061bc5e3dd47641e1d4eb3ad2` |
| `D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py` | `1e65fb48f8c3994261bf8738183cee163d553316f22b0475850f5fe99aa8a7c4` |
| `D:\harness work\audit_sa_project\docs\RULE_CROSSCHECK_GUIDE.md` | `6c1f0130f07fd9f2943ef738ac74ffebb50e3f5a884924886bcfd1d4a25e0bd0` |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_007_R2.md` | 本文件（新增） |

**未改动**：`docs/EXEC_REPORT_007.md`、`docs/EXEC_REPORT_007_R1.md`、`scripts/screen_demo_sqlite.py`（`1b123766…`）、`sql/rules/r01.sql`—`r04.sql`、`scripts/store_demo_sqlite.py`（`1abfad89…`）、`sql/demo_schema.sql`（`7e0c6463…`）、`scripts/normalize_demo_data.py`（`a2bae49e…`）、`scripts/check_demo_data.py`（`a7e5eb67…`）、`docs/SPEC_V1.md`（`5df632ed…`）、`docs/AUDIT_CONTRACT_DRAFT.md`、答案册与全部 GPT 验收证据。

新增测试容器（`data\sqlite_tests\`）：`task007_r2_02`（**最终**，288 个文件）、`task007_r2_01`（`diff_paths` 列表处理修正前现场）、`task007_r2_smoke_01`（四组配对冒烟）。旧容器 `task007_r1_01` 等全部保留，未覆盖。

## 3. 完整执行命令与实际退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
```

### 3.1 语法检查

```powershell
& $py -B -m py_compile 'D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py'
& $py -B -m py_compile 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py'
```

退出码均 **0**。

### 3.2 四组配对冒烟（C04 内存对象）

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' --workbook 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r2_smoke_01\C04\input.xlsx' --report 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r2_smoke_01\C04\checker_report.json'
```

随后在内存中调用标准化、装载、SQL 筛查与复核 API，并构造四组正负控制；结果与第 5 节一致。

### 3.3 最终开发验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' --out-dir 'D:\harness work\audit_sa_project\data\sqlite_tests\task007_r2_02'
```

退出码 **0**；关键输出：

```text
工作簿输入 29 个：初次一致 21、上游阻断 8、初次不一致 0、前提阻断 0、意外运行错误 0
checker CLI 29 次、SQL 核心调用 21 次、复核调用 58 次、预期不一致检查 20 项、前提阻断检查 6 项
[PASS] M1—M20（原 20 项差异检查）
[PASS] K01_ap_id_int / K02_ap_id_bool / K03_ap_id_null / K04_payee_int（正向 MATCHED、负向 MISMATCH）
[PASS] P1—P6（前提阻断）  [PASS] D1_determinism / I1_static_imports / I2_runtime_guard
受保护文件前后哈希一致: True（37 个）
```

命令与日志：`task007_r2_02\command_log.json`、`stdout.txt`／`stderr.txt`（本入口自身完整捕获）、`crosscheck_results.json`、`mismatch_checks.json`、**`hit_key_checks.json`**、`precondition_checks.json`、`isolation_checks.json`、`summary.json`；每组正负输入与完整返回值另存 `mutations\K0*.control.normalized.json`、`K0*.control.report.json`、`K0*.mutated.report.json`、`K0*.negative.report.json`。

### 3.4 其他核验

```powershell
& $py -c "import sys, sqlite3; print(sys.version.split()[0], sqlite3.sqlite_version)"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\crosscheck_demo_rules.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_crosscheck_demo_rules.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\RULE_CROSSCHECK_GUIDE.md' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\EXEC_REPORT_007_R1.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -B -`）用于基线比对与结构化核对；未新增 `.py` 文件。

---

## 4. 分类计数（原 50 次与新增 8 次分开）

| 项目 | 数量 |
| --- | --- |
| 工作簿输入 | **29**（主文件 + 22 fixture + 6 小样） |
| 初次 MATCHED | **21** |
| 上游阻断（SQL／复核未执行） | **8** |
| checker CLI 调用 | **29** |
| SQL 筛查核心调用 | **21** |
| 复核调用合计 | **58** = 原 50（29 输入初次 21 + 差异检查 20 + 前提阻断 6 + 确定性 2 + 隔离 1）＋**新增 8**（命中键配对 4 组 × 正向／负向各 1） |
| 差异检查 | **20**（R1 及以前，全部保持） |
| 命中键配对检查 | **4** 组（正向控制 4 次全部 `MATCHED`，负向 4 次全部 `MISMATCH`） |
| 前提阻断检查 | **6** |
| 确定性／隔离检查 | **3** |
| 工作簿质量阻断 / 初次不一致 / 意外运行错误 | 8 / 0 / 0 |
| 测试失败 | **0** |

四组负向调用按固定方式返回 **MISMATCH**（不是前提阻断），因此单列为“命中键配对检查”，未混入工作簿质量阻断、也未混入初次 MATCHED。

## 5. 四组正负配对实测

每组流程：在 C04 的内存对象中把相关 ID **一致地**改成下列**合法字符串**（`normalized` 与 `screening_report` 同时改，测试侧同步 `load_source` 与 `run_metadata` 的 `normalized_payload_sha256` 为新指纹）→ 正向控制；再深复制该报告，**只改一个 `hit_key` 字段**的类型 → 负向。

| 组 | 规则与字段 | 正向控制 | 负向结果 | 差异代码 | 单点变更路径（结构化比对确认） | 预期／实际类型 |
| --- | --- | --- | --- | --- | --- | --- |
| K01 | R02 `hit_key.ap_id` | `DEV_CROSSCHECK_MATCHED` | `DEV_CROSSCHECK_MISMATCH` | `HIT_KEY_TYPE_MISMATCH`、`MISSING_HIT`、`EXTRA_HIT` | `findings[1].hit_key.ap_id` | expected `'1'`(str)／actual `1`(int) |
| K02 | R02 `hit_key.ap_id` | `DEV_CROSSCHECK_MATCHED` | `DEV_CROSSCHECK_MISMATCH` | 同上 | `findings[1].hit_key.ap_id` | expected `'True'`(str)／actual `True`(bool) |
| K03 | R02 `hit_key.ap_id` | `DEV_CROSSCHECK_MATCHED` | `DEV_CROSSCHECK_MISMATCH` | 同上 | `findings[1].hit_key.ap_id` | expected `'None'`(str)／actual `None`(null) |
| K04 | R01 `hit_key.payee_supplier_id` | `DEV_CROSSCHECK_MATCHED` | `DEV_CROSSCHECK_MISMATCH` | 同上 | `findings[0].hit_key.payee_supplier_id` | expected `'1'`(str)／actual `1`(int) |

四组均满足：`hit_keys` 维度 `{executed: true, matched: false, difference_count: 4}`；差异记录含原始 expected／actual、双方类型与字段路径；正向与负向调用之间**只有指定字段发生变化**（测试侧用递归路径比对给出唯一变更路径）。合法的 `"1"`／`"True"`／`"None"` 字符串在正向控制中**正常 MATCHED**，未被禁止或规范化。

（指纹同步仅作用于新内存控制对象，另存 `mutations\K0*`；未修改任何旧 JSON／工作簿／数据库，也不声称这些改名样例有对应的新真实来源文件。）

## 6. 原有回归保持

- 29 个工作簿输入、21 个初次 MATCHED、8 个上游阻断不变；34 条线索、168 个来源实体、MAIN 12 键与 R02 超额合计 **1 600 000** 分不变（答案册额外验证仍在其后读取）。
- 原 20 项差异检查（含等值 float 金额、bool 统计、`net_per_payment` 浮点、退款摘要重复、规则身份、字段缺失与置 null、多维度改动）与 6 项前提阻断全部保持 PASS，未删除或放宽。
- 确定性（复调用一致、入参指纹不变、数据库字节不变）、隔离（静态无数据库／上游核心／答案册引用；运行期守卫下受限路径读取 0）与 S5 分组键不碰撞检查均保持 PASS。

## 7. 历史保护对照

- TASK-007-R1 验收扩充基线（`data/reviews/task007_r1_20261011_075928/source_hashes_after.json`）：记录项 **11626**、变化 **3**（`scripts\crosscheck_demo_rules.py`、`tests\test_crosscheck_demo_rules.py`、`docs\RULE_CROSSCHECK_GUIDE.md`）、缺失 **0**。
- 任务六 R1 的 **10236** 文件冻结基线：**0 变化、0 缺失**；任务五 R2 的 **8547**、任务四 R1 的 **6511**、任务三 R3 的 **4902**、任务二 R2 的 **874**：均 0 变化、0 缺失；TASK-007 与 TASK-007-R1 的验收证据目录逐文件核对未变。
- 测试内建核验的 **37 个受保护文件**（冻结脚本、schema、四份规则 SQL、规格、契约草案、上游回执与说明、筛查测试、主演示输入与 22 份 fixture）前后哈希一致。
- 依赖未变（Python 3.11.1、SQLite 3.39.4、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未安装依赖、未初始化 Git；运行使用 `-B` 与 `PYTHONDONTWRITEBYTECODE=1`，并清理了编译检查产生的 `__pycache__`。

## 8. 失败尝试与修正过程

1. **单点变更断言一度失败**：测试侧的 `diff_paths()` 未处理列表（`findings` 是列表），只返回 `findings` 而无法证明“只改了一个字段”，四组 K 用例因此判失败（负向本身的 MISMATCH 与 `HIT_KEY_TYPE_MISMATCH` 已正确）→ 为 `diff_paths()` 增加列表按索引递归，得到唯一变更路径 `findings[1].hit_key.ap_id` 后通过；现场保留在 `task007_r2_01`。
2. **版本号编辑被 PowerShell 吞掉引号**：首次用内联脚本改 `CROSSCHECK_VERSION` 与 `METHOD_NOTE`（含三引号字符串）时语法错误、编辑未生效 → 改用文件编辑工具逐处修改并复核（说明与代码现均为 1.2，且 `crosscheck` 版本字符串在说明中只出现 1.2）。
3. **维度映射设计**：为避免“渲染相同、类型不同”同时以 `MISSING_HIT`／`EXTRA_HIT` 结束而不给类型信息，新增诊断配对：身份键仍按类型区分，同时逐字段输出类型差异，使 K01—K04 的差异既准确又可定位。
4. 未通过转换输入、重写观察报告、跳过观察项或修改标准化数据让错误对象 MATCHED；未导入 GPT QA 脚本到生产核心。

## 9. 说明文档更新

- 页首与结果字段表的 `crosscheck_version` 统一为 `TASK-007-crosscheck-1.2`（修正附带文案不一致）。
- §3.2 增补“命中键的 ID 类型属于事实身份”：`rule_id` 与各规则 ID 字段必须为非空字符串，身份键含类型、不做 `str(value)` 归一化，合法字符串 ID 不因外观被禁止；字符串化仅用于差异诊断配对。
- §3.3 差异代码新增 `HIT_KEY_TYPE_MISMATCH`，并说明其记录预期／实际值与类型、字段路径，且 `hit_keys` 维度为 false。
- §5 测试覆盖新增“4 组命中键类型配对回归”，并说明每组正负输入与完整返回值的留痕位置。

## 10. 偏差、未解决问题与停止状态

- **偏差**：采用卡中“保留观察值及类型进行比较、返回明确 MISMATCH”的方式（未采用前提阻断方式），并新增差异代码 `HIT_KEY_TYPE_MISMATCH`；核心版本升至 1.2。
- **未执行（不主张通过）**：任务八、正式事实底稿展示、正式契约、批准控制、Gate 放行、人类判断保存、后置 AI 建议、真实 ERP 接入、OCR、RAG、UI、压力测试；未重跑任务二至六整套历史测试（新链路调用其冻结 API 并核对哈希）。
- **已知限制**：本层只比较报告内部声明与绑定，不实际读取或重验数据库字节；不证明来源真实性，不声称抵御同权限篡改；复核一致**不构成审计结论**，也不替代人类独立判断；不补零、不修复输入、不回写报告。
- **停止状态**：未接入 `data/batches`、未修改旧 `batch_manifest.json`、未建立契约或批准控制、未批准 Gate、未生成 AI 建议、未替人类填写判断、未推进任务八。
- 等待主理人把本回执与 `docs\RULE_CROSSCHECK_GUIDE.md`、`data\sqlite_tests\task007_r2_02` 转交总架构师复验。
