# TASK-023-R2 执行回执（helper 完整观察保存与终审闭合）

任务：按 `docs/tasks/TASK-023-R2.md`（**B 类，DSH 处理**）关闭 `docs/reviews/REVIEW_TASK_023_R1.md` 的
唯一剩余阻断（helper 证据层）；生产适配器与全部上游冻结。
日期：2026-10-14。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：本卡只改 `tests/test_prepare_demo_human_gate1.py` 与 `docs/HUMAN_GATE1_REQUEST_GUIDE.md`
（受影响证据说明），只新增 `docs/EXEC_REPORT_023_R2.md`、`data/human_gate1_request_tests/task023r2_*`
与同轮 `data/batches/task023r2_*`。**生产适配器冻结未改**（`ce23671f…0ac4`）、配置 `ae4caa38…fb7c`
与 P1/存储/契约/生效登记/receiver/checker/宿主/控制器/业务文件全部冻结；未接存储/历史/宿主/Gate2/
真实初判/AI；未生成真实批准。

---

## 1. 起点与基线

| 项 | 值（实读） |
| --- | --- |
| 评审结论 | `data/reviews/task023_r1_gpt_20261014_031403/review_result.json` → **NOT_ACCEPTED**（施工起点） |
| 基线 | 同目录 `source_hashes_after.json` = `5cdeb08bc96715ea970d04662b16016c08c4d6c8e4a60c20cef1d66be6a57a6d`、**141939** 项、两个确切自指元数据排除 |
| 测试（起点 → 写后） | `e739df9b55de87ad758333def339cfc3838caae641b1eaf71b63467bf1afa518`（80889）→ `59214e21f8faebbac9ee8199de9ff8a78ecf875f60600db5ba4acacd0aff3287`（94209） |
| 指南（起点 → 写后） | `025b2241a8e6d5ab0347b6993f80a09ef47937c5ef407477305414d713cd007f`（11629）→ `c55c0eba0f223badb4be8a4139b34068e8f11f5fd64358ff12a9438e6def393d`（12530） |
| 生产适配器（冻结） | `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4`（56069）**未改** |
| 配置（冻结） | `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c`（219）**未改** |

## 2. 关闭证据

### 2.1 完整真实观察与保存

- `HelperObserver` 在进入**真实冻结 `validate_report` 之前**保存完整输入快照（`inputs.report` 深拷贝
  与规范指纹 `inputs_fingerprint.report`），并在调用后对**同一引用**复核 `input_unchanged_after_call`
  为严格 true；完整真实返回（含 `result_type`/规范指纹/`problems_count`）或真实异常
  （`_exception_detail` + `traceback.format_exc()`，并按适用带上 field/stage/reason 与 cause/context 链）
  一并保存；观察期间不做任何文件写入。
- 新增固定测试载荷 **`helper_call_records.json`**（`total` + 完整 `records`，每条唯一 `call_id`、完整输入、
  真实完整返回或异常、`outcome`）。`result: []` 为**合法完整结果**（按键存在判定，不以真值判断缺失）。
- 该文件已进入**实际待写缓冲**、`PAYLOAD_FILES`（13 项）、文件台账、首轮同缓冲读回、字节漂移确认与
  **canonical 内容比较**（`_content_compare` 新增该文件项，差异按 `call_id` 定位
  `located_call_ids`）；完整预期在终审之前从本次真实观察**独立深拷贝**定稿，不从候选磁盘、也不从
  “已截短的待审核 payload”刷新。

### 2.2 实际计数、ID 与载荷闭合

- 以**函数代码对象身份**的轻量真实入口观察（`sys.setprofile`，只比较 `frame.f_code is code`，不做路径
  解析、不改入参/返回、不包装外层 API）分别计数 prepare、P1、冻结 `validate_report`：本轮正常入口
  **prepare 37 / P1 3 / helper 14**，与各自完整记录分列闭合；三者共用一个 profiler（避免相互覆盖）。
- `_final_registry_audit` 现同时核对：独立 helper 入口观察数 == 声明 `total_helper_calls` ==
  `records` 长度 == `helper_call_records.total`；`registry.helper_call_ids` 与 `record.call_id` **双向
  唯一集合**一致（重复/缺失即拒绝）；每条 entry **完整**（有输入快照、`outcome` ∈ {returned, raised}、
  有 `result` 或 `exception` 键、调用前后输入指纹不变）。prepare/P1 现有正确审核保持（P1 次数不等同
  prepare 次数）。名为 **disk** 的审核消费本轮 `_audited_read` 的**实际候选对象**（`prepare_registry`
  与 `helper_call_records` 的 parsed 值），台账登记 `disk_audit_source="first_read_disk_candidate"`、
  `disk_candidate_records=14`；内存真实观察（独立入口数/固定完整预期）与磁盘候选两类来源明确分列。
- 完整内容主判据仍为 canonical JSON 字节相等：任一输入/返回/异常/关联字段被合法形状改写都会拒绝，
  并按 `call_id` 定位。

### 2.3 隔离审核（同一实际审核 helper，不建业务链）

| 控制 | 结果 |
| --- | --- |
| 正常完整原件 | 通过（`original_passes=true`） |
| 删一条 prepare 登记 | 同一 helper 拒绝 |
| **删一条 helper 完整 entry（保留 total/ID/入口观察数）** | 同一 helper 拒绝，并**定位 `helper-001`** |
| 删一个 helper ID | 拒绝（ID 集合不闭合） |
| 重复一条 entry | 拒绝（ID 非唯一/长度不符） |
| 空壳 entry（仅 call_id/outcome/result） | 拒绝（entry 不完整） |
| 合法 `[]` 返回 | 原件通过（`legal_empty_result_present=true`） |
| 一条返回改为合法字符串列表 | 完整内容比较拒绝并**按 `call_id` 定位** |

### 2.4 磁盘故障（分离轮次）

`data/human_gate1_request_tests/task023r2_fault_01/helper_entry_fault.py` → 套件运行到
`task023r2_fault_02/`：在 helper 文件已完整保存、固定真实预期已定稿后、**首轮终审读取之前**，只从磁盘
`helper_call_records.json` 删一条完整 entry（保留 total=14、`registry.helper_call_ids`、入口观察数 14），
包装真实 `_audited_read` 先删磁盘再调用真实 reader 并**原样返回其读数**（不替换审核结论、不回填）。

| 项 | 值 |
| --- | --- |
| 套件返回 / summary / failures | **1 / FAIL / 非空** |
| 删除的 call_id / 候选 records | `helper-001` / **13**（声明 total 14、入口观察 14） |
| 审核判定 | `records_length(13) != declared_total(14)`，缺失 entry **定位 `helper-001`** |
| 候选处理 | **未回填/未重建**（最终 SHA == 故障后 SHA） |
| harness 断言 | **8/8 全真**（`ok=true`） |

## 3. 实际运行与计数

```text
.venv\Scripts\python.exe -B tests\test_prepare_demo_human_gate1.py \
    --out-dir data\human_gate1_request_tests\task023r2_run_01
→ TASK-023-R1 测试组：72 项检查，0 项失败；prepare 调用 37、真实 P1 调用 3、
   接收器运行 7、helper 调用 14
→ 退出码 0
```

| 作用域 | 实测 |
| --- | --- |
| prepare 调用 / 独立入口观察 | **37 / 37** |
| 真实冻结 P1 调用 / 独立入口观察 | **3 / 3** |
| 冻结 `validate_report`（helper）调用 / 独立入口观察 / 保存记录 | **14 / 14 / 14** |
| 冻结接收器 CLI | **7** |
| 生产 prepare 的 P1/存储调用 | **0**；守卫写文件/网络/子进程 **0** |
| 台账 | **13 项**逐文件实读一致；`content_compare.ok=true`、`registry_audit.ok=true`（磁盘候选来源）、`disk_candidate_records=14` |

## 4. 未退化收尾

完整实际观察定稿 → **一次性**最终载荷写入 → 首轮同缓冲对象与 SHA 审核（含 helper 完整载荷）→
**任何后续写入之前**按保留读数做真实字节漂移确认 → 正常路径只写台账。未恢复第二次 `write_bodies`
覆盖、未重新采集已漂移文件当期望、未无限“改文件→重建台账”。内容/ID/entry/计数/台账/漂移失败一律
追加正式 failures、FAIL、非零与诊断并保留坏载荷；未执行项记 `null`/`not_executed`，不默认零。

## 5. 过程问题与未执行（如实登记）

1. 测试侧局部迭代三次失败后定点修正：① `helper_records` 在 `counts` 之前不可用（改为在卸载观察器后
   写入 `counts`）；② `_content_compare`/`_content_isolation` 未覆盖新增 helper 文件（补齐并加
   `call_id` 定位）；③ 三个独立 `sys.setprofile` 相互覆盖导致入口观察为 0（改为**单一** profiler
   同时按代码对象身份计数 prepare/P1/helper）。过程容器 `task023r2_dev_01…dev_06` 全部保留。
2. 本轮未单独重跑已通过的 checks LF 完整故障与来源/链接/ID 生产定点，也未运行 TASK-021/022、
   宿主/历史入口；首轮读回/漂移确认/失败写入顺序未改（无需补 LF 故障）。旧现场、旧 junction、
   旧回执/评审全部保留未清理。
3. 回执身份：R1 回执实读 **13839 字节 / `882c19ce9f403972d6064ffaa59282c347f552b721a217bc461b44ccee74be50`**，
   与 R1 交接口径一致（交接只给字节数），不称旧哈希不一致。
4. 未执行：宿主/控制器接线、存储 save/verify、标准化/装载/DB/筛查、Gate2、真实初判、`0009`、AI/终判、
   网络/UI/ERP、强身份认证、真实批次批准、历史枚举、R01—R04 计算、子进程内部未知次数（`null`）。

## 6. 保护（定稿后一次全树比较）

- 基线：`data/reviews/task023_r1_gpt_20261014_031403/source_hashes_after.json`
  （`5cdeb08b…a57a6d`、**141939** 项、NOT_ACCEPTED）；仅两个确切自指路径排除，`prefix_exemption_used=false`。

### 6.1 结果与最终身份

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **142978** |
| `changed` | **恰为测试 `59214e21f8faebbac9ee8199de9ff8a78ecf875f60600db5ba4acacd0aff3287` 与指南 `c55c0eba0f223badb4be8a4139b34068e8f11f5fd64358ff12a9438e6def393d` 两项**；生产适配器与全部其他旧件不变 |
| `missing` / 读取错误 / 范围外变化 / 范围外新增 | **0 / 0 / 0 / 0** |
| 新增登记 | **1039** 项：本回执 + 本轮九个 `task023r2_*` 证据/故障容器 + 八个 `task023r2_*` 批次根（逐确切路径登记，`prefix_exemption_used=false`） |
| 冻结身份 | 适配器 `ce23671f…0ac4`、配置 `ae4caa38…fb7c`、P1、存储、接收器、checker、宿主、控制器、正式契约、生效登记、`EXEC_REPORT_023.md` `fb01538f…e44a`、`EXEC_REPORT_023_R1.md` `882c19ce…be50` **全部一致**（`mismatch=[]`） |
| 扫描后动作 | 仅有限登记本回执身份（本节）；**未再改测试**，不声称旧扫描有效；旧现场/junction/回执保留未清理 |

## 7. 交付文件（写后实读）

| 文件 | SHA-256 | 字节 |
| --- | --- | --- |
| `tests\test_prepare_demo_human_gate1.py` | `59214e21f8faebbac9ee8199de9ff8a78ecf875f60600db5ba4acacd0aff3287` | 94209 |
| `docs\HUMAN_GATE1_REQUEST_GUIDE.md` | `c55c0eba0f223badb4be8a4139b34068e8f11f5fd64358ff12a9438e6def393d` | 12530 |
| `scripts\prepare_demo_human_gate1.py`（冻结未改） | `ce23671f4c19d60808f90755d4c8575b1b8ad018bfc7e0f3bcebee3b06de0ac4` | 56069 |
| `docs\EXEC_REPORT_023_R2.md` | 自身最终 SHA **只在交接消息给出** | — |

## 8. 四类来源分列（R2 要求）

| 来源 | 内容 | 用途 |
| --- | --- | --- |
| 完整真实 helper 记录（内存定稿后落盘） | `helper_call_records.json`：14 条完整输入/返回/异常 + 指纹 | 固定测试载荷、台账、内容比较（按 `call_id` 定位） |
| 独立入口观察（函数代码对象身份） | prepare 37 / P1 3 / helper 14 | 与声明 total、`records` 长度、ID 集合闭合 |
| 磁盘候选（首轮 `_audited_read`） | `prepare_registry` + `helper_call_records` 的 parsed 值（14 条） | **disk** 审核实际消费对象，台账登记来源 |
| 固定完整预期（内存真实观察深拷贝） | `expectation`（含 `helper_call_records`、两个入口观察数） | canonical 字节相等主判据 |

## 9. 绝对路径

- `D:\harness work\audit_sa_project\tests\test_prepare_demo_human_gate1.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE1_REQUEST_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_023_R2.md`
- `D:\harness work\audit_sa_project\data\human_gate1_request_tests\task023r2_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate1_request_tests\task023r2_fault_01\`
- `D:\harness work\audit_sa_project\data\batches\task023r2_run_01\`

## 10. 停止点

完成后执行端停止实施并交 GPT 验收；**验收通过前不制定或实施 TASK-024**、不推进任何 Gate 接线；
不生成真实批准、初判或 `0009`，不开放 AI。真实批准仍 `null`、`next=false`；人类继续负责业务判断与看板。
若需修改生产/配置/冻结上游或改变原范围，立即停止受影响处理、保留现场并报告重新定界升级。
