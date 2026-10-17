# TASK-003-R3 执行回执（补齐成功条件与哈希留痕）

任务：修复 TASK-003-R2 复验剩余问题——A 结束阶段必需哈希未知却仍候审就绪、B 固定字段映射未检查必需键、C 哈希读取未保留已确认的存在状态。
日期：2026-10-11。
执行端：DeepSeek（Harness 会话）。
依据：`docs/tasks/TASK-003-R3.md`、`docs/reviews/REVIEW_TASK_003_R2.md`、`docs/tasks/TASK-003-R2.md`、`docs/tasks/TASK-003-R1.md`、`docs/tasks/TASK-003_DRAFT.md`。
状态：本卡范围内工作完成并自检通过，**停止于此**；未推进任务四。

> 命令均为完整参数、不使用省略号；未执行的检查一律写明“未执行”。

---

## 1. 结论摘要

| 项目 | 结果 |
| --- | --- |
| A 结束哈希未知必须阻断 | 原输入、原始快照、接收入口、checker 四项结束哈希改为**成功条件**：未知或不可读即 `FAILED_RUNTIME`／退出 **2**，不再因值为 `null` 跳过比较；对 checker 退出 1 的批次同样生效（升级为 2） |
| B 固定字段映射检查必需键 | 对实际存在的固定表要求给出该表**全部固定字段键**（四表合计 22 个）；缺键或映射对象为空 → 报告结构无效／退出 **2**；键存在值为 `null` 仍接受；缺表不要求条目 |
| C 保留已确认的存在状态 | 存在性确认为真、仅读取字节失败 → `exists=true`、`sha256=null`、`read_error` 为真实错误；存在性检查本身失败才记 `exists=null`；确认不存在记 `exists=false`；读取错误仍导致核验失败 |
| 集成验证 | **61 个用例全部通过、失败 0**（原 52 例 + R3 新增 9 例），测试退出 **0**；预期负向案例 **44** 个 |
| 调用与日志 | 入口实际调用 **61** 次：真实 CLI **34** 次 + 内存模拟 **27** 次；**122** 个独立 stdout／stderr 日志文件 |
| 最终主演示批次 | `data\batches\dev_receive_003_r3_main_01`：8 项产物齐全，`DEV_GATE1_PACKET_READY`，四表 20/993/1000/1005，缺失关联净额 1 000 000 分，**四项结束哈希全部已知且一致** |
| 最终验证容器 | `data\batches\task003_r3_tests_02`（563 个文件） |
| 冻结源码 | checker `a7e5eb67…`、任务二回归脚本 `555c5ef7…`、生成器 `e899aa2f…`、规格 `5df632ed…`、契约草案 `af405cb6…` 全部未变 |
| 既有文件保护 | 三份基线分别复核：R2 复验 **3225 个文件**、R1 复验 **1805 个文件** 均为 3 个变化（全部是授权文件）、0 个缺失；任务二 R2 基线 **874 个文件** 0 个变化 |
| 未执行 | 标准化、入库、R01—R04、AI 建议、正式契约、人工守门点、真实 ERP 接入；未安装依赖、未初始化 Git |

---

## 2. 实际修改与新增

### 2.1 修改（本卡授权的三个文件）

| 文件 | 当前 SHA-256 |
| --- | --- |
| `D:\harness work\audit_sa_project\scripts\receive_demo_batch.py` | `5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6` |
| `D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py` | `6374a5d7ead327fbc65fbeaefe3a9377daba58eb0dcfea731847616df87b6c96` |
| `D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md` | `fccadcdd098d76ccf9f7061e4fafac72b3aba95e64ea53f3e794c1ad8dafbcfd` |

### 2.2 新增

| 路径 | 说明 |
| --- | --- |
| `D:\harness work\audit_sa_project\docs\EXEC_REPORT_003_R3.md` | 本回执 |
| `D:\harness work\audit_sa_project\data\batches\dev_receive_003_r3_main_01` | **最终 R3 主演示批次**（8 个文件） |
| `D:\harness work\audit_sa_project\data\batches\task003_r3_tests_02` | **最终 R3 验证容器**（563 个文件） |
| `D:\harness work\audit_sa_project\data\batches\task003_r3_tests_01` | 第一次 R3 运行（3 条断言作用域写错，见第 8 节），按“不覆盖历史”保留 |
| `D:\harness work\audit_sa_project\data\batches\task003_r3_smoke_01`、`task003_r3_smoke_02` | 实现过程中的两次单跑冒烟（C01 正常 / C14a 阻断），保留现场 |

既有批次与 GPT 证据目录全部原样保留，未覆盖、未删除。

---

## 3. 三项修复的落点

### A. 必需一致性检查：未知也必须阻断

- 新增 `require_hash(state, label, info, stage, expected)`：取该项哈希，**为 `None` 即判运行失败**并把 `read_error` 写入失败原因；有预期值时再比较是否相等。
- `execute_batch` 的结束阶段改为对四项逐一要求：
  - 原输入（核验结束，与复制前比较）、原始快照（核验结束，与复制后比较，快照确实写入时）、接收入口源码（核验结束，与执行前比较）、checker 源码（核验结束，与执行前比较）。
  - 值仍诚实保留为 `null`，但**不再**因为 `null` 而跳过比较：`read_error`、文件消失或未知一律 `FAILED_RUNTIME`／退出 2。
- 该逻辑位于 `execute_batch` 内，因此对 checker 本来退出 1 的批次同样生效：质量问题之外出现一致性读取错误会**升级为运行失败／退出 2**（已用 C14a 叠加故障验证）。
- 保留原有原子提交、失败清单／材料同步、代码副本比对实现；不伪造“已核验”状态，也不以后续成功读取抹掉本轮已发生的运行错误。

### B. 固定字段映射要检查键存在

- 新增 `FIXED_FIELDS` 常量，按 SPEC_V1 四表字典列出 22 个固定字段（suppliers 2、payables 6、payments 9、allocations 5）。
- `validate_report` 对 `sheets_found` 中**实际存在**的固定表：映射条目必须是对象且非空，并**包含该表全部固定字段键**；键缺失或映射对象为空 → 结构无效／退出 2；键存在而值为 `null` → 接受（这是 checker 已提供的“未映射到该列”信息）；值为正整数接受，布尔不算。
- 工作簿实际缺失某张表时**不要求**该表映射条目，也不因此判成运行失败（已用“删除 payables 表”的工作簿副本验证：仍为 `BLOCKED_QUALITY`／退出 1）。
- 只核实报告接口，未复制 checker 业务逻辑，未依据答案册修报告。

### C. 哈希读取保留已知存在状态

- `safe_hash_file` 拆开两步：先单独判定存在性（失败记 `exists=null`），确认存在后再读取字节（失败记 `exists=true`、`sha256=null`、`read_error`）；确认不存在记 `exists=false`。
- 新增最小接缝 `read_file_bytes()`（生产路径唯一实现），使验证可以在**存在性检查成功之后**模拟读取字节失败，而不是整体替换 helper。
- 读取错误仍然导致所需核验失败（`_require_artifact` 与 `require_hash` 均按“哈希不可用即失败”处理），不因 `exists=true` 放行。

---

## 4. 完整执行命令与实际退出码

```powershell
$py   = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$recv = 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py'
$tst  = 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py'
```

### 4.1 语法检查

```powershell
& $py -m py_compile 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py'
& $py -m py_compile 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py'
```

退出码均 **0**。

### 4.2 两次冒烟单跑

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\fixtures\C01.xlsx' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r3_smoke_01' --source-description 'R3 冒烟：C01'
& $py -B 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\fixtures\C14a.xlsx' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r3_smoke_02' --source-description 'R3 冒烟：C14a'
```

退出码分别为 **0**（`DEV_GATE1_PACKET_READY`）与 **1**（`BLOCKED_QUALITY`），两者四项结束哈希均已知且一致。

### 4.3 最终主演示批次

```powershell
& $py -B 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' --workbook 'D:\harness work\audit_sa_project\data\generated\demo_20260930_a\input\erp_export.xlsx' --out-dir 'D:\harness work\audit_sa_project\data\batches\dev_receive_003_r3_main_01' --source-description 'TASK-003-R3 开发验收：现有合成 ERP 导出演示文件，来源描述尚不构成人类范围确认'
```

退出码 **0**；证明见第 5 节。

### 4.4 最终集成验证

```powershell
& $py -B 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' --out-dir 'D:\harness work\audit_sa_project\data\batches\task003_r3_tests_02'
```

退出码 **0**；输出“用例总数 61，通过 61，失败 0”“入口调用 61 次（真实 CLI 34 次 + 内存模拟 27 次）”“预期负向案例 44 个”“只读输入前后哈希一致: True（受保护 39 个）”。

### 4.5 其他核验

```powershell
& $py -c "import sys; from importlib.metadata import version; print('Python:', sys.version.split()[0]); [print(n+': '+version(n)) for n in ['openpyxl','et-xmlfile','pandas','numpy','chromadb']]"
Get-FileHash 'D:\harness work\audit_sa_project\scripts\check_demo_data.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\scripts\receive_demo_batch.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\tests\test_receive_demo_batch.py' -Algorithm SHA256
Get-FileHash 'D:\harness work\audit_sa_project\docs\BATCH_RECEIVE_GUIDE.md' -Algorithm SHA256
```

退出码均 **0**。另有内联脚本（`@' … '@ | & $py -`）用于与三份基线比对哈希、核对最终批次字段与容器计数；未新增 `.py` 文件。

---

## 5. 主演示批次证明（`dev_receive_003_r3_main_01`）

| 项目 | 实测 |
| --- | --- |
| 批次状态 / 退出码 | `DEV_GATE1_PACKET_READY` / **0**，`failure_reasons` 为空 |
| 8 项产物 | `source/input.xlsx`、`checks/quality_report.json`、`logs/checker.stdout.txt`、`logs/checker.stderr.txt`、`code_snapshot/receive_demo_batch.py`、`code_snapshot/check_demo_data.py`、`batch_manifest.json`、`gate1_packet.md` **全部存在** |
| 四表行数 | suppliers 20、payables 993、payments 1000、allocations 1005 |
| 缺失应付关联净额 | 1 000 000 分（未知 AP 的资金部分保留） |
| 材料 | `gate1_packet.exists=true`，`sha256` 与磁盘文件一致 |
| 报告 | `sha256` 与磁盘一致；`report_validation.valid=true` |
| 必需一致性比较 | 原输入 复制前=复制后=结束时；快照 核验前后相等；接收入口与 checker 的前后哈希均已知且相等（`stable_during_run=true`）；`snapshot_matches_source=true` |
| 其他 | `source.size_bytes=104304`；`checker_invocation.attempted=true`、`started=true`、`exit_code=0`；`gate1_approval=null`、`gate2_approval=null`、`next_step_allowed=false`、`contract_status=DRAFT_NOT_IN_FORCE`、`mode=DEVELOPMENT_ONLY` |

## 6. R3 新增用例与实际结果（9 例）

| 用例 | 方式 | 期望／实际退出码 | 关键断言 |
| --- | --- | --- | --- |
| `R3_source_end_hash_unreadable` | 内存（`read_file_bytes` 第 3 次读原输入失败） | 2／**2** | `FAILED_RUNTIME`；`source_after_check=null`；复制前=复制后仍成立；失败原因含“原输入（核验结束）”；不能候审就绪 |
| `R3_snapshot_end_hash_unreadable` | 内存（第 2 次读快照失败） | 2／**2** | `snapshot_after_check=null`；`snapshot_matches_source=true`（复制阶段事实保留）；退出 2 |
| `R3_receiver_end_hash_unreadable` | 内存（第 2 次读真实接收器失败） | 2／**2** | `receive_script.sha256_at_end=null`；`stable_during_run` 不为 true；退出 2 |
| `R3_checker_end_hash_unreadable` | 内存（第 2 次读真实 checker 失败） | 2／**2** | `checker.sha256_at_end=null`；`stable_during_run=null`；退出 2（对应复验 T02） |
| `R3_c14a_end_hash_failure_upgrades_to_2` | 内存 + C14a 输入 | 2／**2** | checker 自身退出 **1**，但一致性读取失败使入口升级为 **2**（不是 1） |
| `R3_mapping_key_missing` | 内存（有效报告删除 `payables.payable_amount` 键） | 2／**2** | 结构无效；失败原因含“固定字段”；不产生就绪清单（对应复验 T03） |
| `R3_mapping_entry_empty` | 内存（`payables` 映射对象置空） | 2／**2** | 结构无效（空对象不算已提供映射）；退出 2 |
| `R3_missing_sheet_still_blocked` | 新副本（删除 payables 表的工作簿） | 1／**1** | 仍为 `BLOCKED_QUALITY`；报告结构 `valid=true`；`failure_reasons` 为空；`payables` 不在 `sheets_found` 中 |
| `R3_spec_read_bytes_failure_keeps_exists_true` | 内存（存在性成功、读取 SPEC 字节失败） | 2／**2** | `spec.exists=true`、`sha256=null`、`read_error` 非空；退出 2（对应复验 T04） |

原有 52 例全部保留并重跑通过（含 22 份既有 fixture：14 份退出 0、8 份退出 1）。
统计：**用例 61 个，通过 61，失败 0**；预期负向案例 **44** 个；入口调用 **61** 次 = 真实 CLI **34** 次 + 内存模拟 **27** 次，**122** 个独立日志文件（`command_log.json` 以 `mode` 区分）。

## 7. 文件保护结果

- 授权修改的 3 个文件：哈希见第 2.1 节。
- 冻结源码未变：checker `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8`、任务二回归脚本 `555c5ef7320c6fd3078264f808a5c2a43f492909058b9b0d361fb43dee09bbb6`、生成器 `e899aa2f37590241328a4068f2c61d160c22e9f014e743cdb4b9dd1966a01a3b`、规格 `5df632ed7529507c07bec151586d06858091c9d849c363c8b2cb0962a9a79236`、契约草案 `af405cb6e3c4eb103b967b9520bd221a03acd266c1cd666fe79a12fe9eedca27`。
- 三份 GPT 基线复核：**3225 → 变化 3**、**1805 → 变化 3**（均为授权文件）、**874 → 变化 0**，全部 0 缺失。
- 集成验证内建核验：**39 个只读输入**与 6 个测试输入副本前后哈希一致；并额外校验真实磁盘上的 checker 与接收器哈希未变。
- 依赖未变（Python 3.11.1、openpyxl 3.1.5、et-xmlfile 2.0.0、pandas 3.0.6、numpy 2.4.6、chromadb 1.5.9）；未执行 `pip install`；Git 未初始化；`py_compile` 产生的 `__pycache__` 已删除。

## 8. 失败尝试、偏差与修复过程

1. **第一次 R3 验证运行（`task003_r3_tests_01`）58/61 通过**：三条失败同源，是我新写断言**作用域写错**——在“原输入／快照结束哈希不可读”的用例里断言 `checker.stable_during_run is not True`，但这些用例中 checker 哈希本身正常，该字段应当为 `true`。接收器行为正确（三者均退出 2、`FAILED_RUNTIME`、保留失败原因与材料）。改为**按用例断言各自受影响的字段**（源／快照用例断言复制阶段事实保留与未知值诚实为 `null`；入口／checker 用例才断言 `stable_during_run` 不为 true），并在新容器 `task003_r3_tests_02` 重跑通过。失败容器按“不覆盖历史”保留；**未改数据、报告或既有批次来让断言通过**。
2. **一次自查脚本字段名笔误**：核对主批次时我误用了顶层键名 `hashes.receiver_sha256_before_run`（实现中该值在 `hashes.receive_script.sha256_before_run`），报 `KeyError`；属核对脚本自身笔误，改正键名后复核通过，批次与清单本身无误。
3. **实现过程中的一处顺序修正**：`require_hash` 与 `read_file_bytes` 接缝的插入位置一开始改动了 `resolve_out_dir` 的一行，编译检查发现后立即恢复并重新验证（未产生错误的成功批次）。
4. 旧回执与旧清单保留、未迁移修补；`task003_r3_smoke_01/02` 为最终修订前的单跑现场，其 `code_snapshot` 记录当时版本。

## 9. 尚未通过项、限制与停止状态

- 未执行（不主张通过）：标准化、SQLite 入库、业务状态机、R01—R04 筛查、AI 审计建议、正式契约、正式人工守门点、RAG、OCR、百万行压测、真实 ERP 接入；未统计召回率或误报率。
- 已知限制：
  - 报告结构校验只覆盖入口消费的内容（含 22 个固定字段键的存在性），不等同于 checker 报告的完整通用 schema 校验；
  - 代码留档与结束哈希检查用于发现普通复制／读取故障与留档可靠性问题，**不抵御同权限恶意篡改**；
  - 原子提交依赖文件系统语义；存储彻底不可写时只能保证退出 2 与 stderr 说明；
  - 候审材料是开发态材料，不含风险等级或业务结论；金额 `null` 表示不可得，不得读作零；
  - 结束哈希未知时清单中该项仍为 `null`（诚实留痕），但批次必然为 `FAILED_RUNTIME`、退出 2。
- 本卡范围内工作已停止：未推进任务四，未代主理人审定契约、批准 Gate 1／Gate 2 或填写职业判断。
- 等待主理人把本回执与 `data\batches\dev_receive_003_r3_main_01`、`data\batches\task003_r3_tests_02` 转交总架构师复验。
