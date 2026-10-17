# TASK-016 执行回执（开发态独立初判记录纯核心）

任务：按唯一权威细则 `docs/tasks/TASK-016_DRAFT.md` 新增开发态模拟初判记录**纯核心**（只做校验与事实绑定）。
日期：2026-10-13。执行端：DeepSeek。验收端：GPT。
状态：七组有限检查全部通过；一次全新证据容器最终入口退出 **0**、**7/7 检查 PASS、failures=[]**；停在纯核心——**不保存真实人类判断、不认证身份、不解锁 AI**，未接宿主、未建 `0008`、未建立正式契约或真实 Gate。宿主仍停在开发态 `0007`、真实批准 `null`、`next_step_allowed=false`。

---

## 1. 交付文件（写后实测 SHA-256）

| 文件 | 状态 | SHA-256 |
| --- | --- | --- |
| `scripts\build_demo_initial_judgment.py` | 新增（19772 字节） | `41026b98f8608b8280fbb62793bac59f766e932a17b0deae407ebc8238dd208c` |
| `tests\test_build_demo_initial_judgment.py` | 新增（44771 字节） | `d4ad4b886c9484bb79c088a2428fbc27f3c6fb93ee46a975877620d856b6e13a` |
| `docs\INITIAL_JUDGMENT_GUIDE.md` | 新增（9708 字节） | `d995d20d8493e44d53babd37113c96d83c34bcc54ac250f35c2fce51a828b938` |
| `docs\EXEC_REPORT_016.md` | 新增 | 见交接消息给出的写后最终哈希（本文件含本行，不写回自身以免自指） |

**冻结件核对（本轮实测一致）**：

| 冻结件 | SHA-256 |
| --- | --- |
| `scripts/run_demo_workflow.py`（宿主，未改） | `67788bd0fe651589ef62ae0437d12a68becef2d94960b443712eed3315fad35a` |
| `tests/test_fact_packet_demo_workflow.py`（TASK-015 最终宿主测试，未改） | `90f8f5d302aa16de3ba29a9c7f83ff12cbfce92b987ece31d2b40a9d8ffbfe7e` |
| C06b 事实包（只读输入） | `8cecbf3b9b5c463476b1dcf712065b60c2d75d5d9948c3a3f9ac141516e98755` |
| MAIN 事实包（只读输入） | `711fe8d71035d7beaa4bc1972a0ea90a21c5c3932703e6850c765a149448b926` |
| C03 事实包（只读输入） | `9644a10a656580aebf9d42f4716d7aee7634f65ca3af10e9259534453f2f4426` |

未修改任务卡、规格/契约草案、上游实现/SQL、既有测试与指南、回执、评审或数据现场；未安装依赖、未初始化 Git、未改变目录结构、未迁移旧凭证、未清理历史。

---

## 2. 纯核心接口与边界

唯一业务入口：

```python
build_initial_judgment_record(batch_id, fact_packet, submission, *,
                              expected_packet_sha256) -> {"record": ..., "record_sha256": ...}
```

- 标准库、纯内存、确定性；不读写文件/数据库/Excel；不导入或调用上游、控制器、宿主、测试、答案册、LLM、网络或子进程；不生成事件 ID、身份、时间或判断；导入模块也不触发上述操作。
- 规范 JSON：UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、`allow_nan=False`；规范指纹＝该字节串 SHA-256；`record` 不内嵌自身指纹。
- 不改入参、不共享可变对象（`entity` 与 `submission` 均深拷贝）；修改返回记录不影响输入。
- `InitialJudgmentBlocked`（输入/协议/绑定不符，指出 `field` 与原因）与 `InitialJudgmentError`（保留 cause 链）；异常不包装成成功记录。无 CLI、退出码或文件保存接口。
- 时间校验：正则要求含时区 ISO8601，再用 `datetime.datetime.fromisoformat` 校验真实存在性（拒 `2026-13-45T99:99:99+08:00`、`2026-02-30…`、`2026-02-29…`（非闰年）、`+0800` 无冒号偏移、无时区）；只解析调用方字符串，**不读系统时钟、不生成时间**。
- 记录状态只有 `DEV_INITIAL_JUDGMENT_VALIDATED`；`contract_status=DRAFT_NOT_IN_FORCE`、`next_step_allowed=false`、`ai_suggestion_allowed=false`；五项判断/批准字段固定 `null`。

---

## 3. 最终入口与退出码

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
& $py -B -c "src = open(r'...\scripts\build_demo_initial_judgment.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"           # 0
& $py -B -c "src = open(r'...\tests\test_build_demo_initial_judgment.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"       # 0
& $py -B '...\tests\test_build_demo_initial_judgment.py' --out-dir '...\data\initial_judgment_tests\task016_run_01'                                        # 0
```

输出要点：`[PASS] G1…G7` 七项、`检查项 7：7 PASS / 0 FAIL`、`API 调用 47（返回 9、按预期 Blocked 38、意外错误 0）`、`missing=0 unregistered=0`、`守卫命中 0；保护比较 executed=True`、`测试失败 0`。

---

## 4. 七组有限检查结果

| 组 | 结果 | 关键实测 |
| --- | --- | --- |
| G1 正常与“暂不能判断” | PASS | 真实调用成功；外层恰 `record`/`record_sha256`；`record_sha256` ＝ `record` 规范指纹；`record` 未内嵌自身指纹；返回文件读回哈希与登记一致；**调用前**与本次调用后对同一输入引用分别取指纹且相等；`source.fact_packet_sha256` 与本次对象规范指纹一致；`finding_ids` 与 packet 原序一致；`assessment`/`reason`/`actor_id`/`occurred_at` 原字符串保留；两个可选键确定性规范化；“暂不能判断”对照省略可选键后规范化为空列表且 `reason` 非空。 |
| G2 三份已保存事实包 | PASS | MAIN（12 条）、C06b（1 条）、C03（**0 条**）各自成功接收批次初判；三份输入文件字节哈希与本卡登记一致；`finding_ids`、四项来源指纹、`entity`（深拷贝、不与输入共享对象）绑定准确；C03 零条**未**被自动填成“无问题/通过”，状态与五项 `null` 边界不变。只读三份已存在 packet，未调用上游、未读答案册、未把旧容器当作当前宿主恢复成功。 |
| G3 绑定反例 | PASS | 五个反例（submission 批次与 API 不一致、错误提交指纹、旧 `expected` 下事实字段变化的深拷贝、API 批次与 submission 不一致、非 64 位小写十六进制 expected）全部 `InitialJudgmentBlocked` 且指出字段；三份输入文件与原始对象未被回写（负向探针只改内存深拷贝）。 |
| G4 协议反例 | PASS | 28 个反例按维度分组全部准确 Blocked：空白/`bool` 冒充的 `assessment` 与 `reason`、`bool` 冒充 `actor_id`、未知键 `ai_suggestion`/`final_judgment`、真实 `HUMAN`/`REAL` 身份、无时区/不存在日期/非闰年 2-29/无冒号偏移、重复与未知 `finding_id`、备注多余键、缺必填键、错误 `scope`、空 `event_id`、`needed_evidence` 非列表或元素为 `bool`、非 dict submission；事实包侧：状态尾随空格、`next_step_allowed` 为 `true`/`0`、错误 `mode`/`packet_version`、重复 `finding_id`、`rule_id=R05`、非法来源指纹、`findings` 非列表、`currency`/`cutoff_date` 不符。未做无穷组合。 |
| G5 确定性与无别名 | PASS | 相同输入两次调用返回规范 JSON 完全相同；把返回记录的 `assessment` 改为其它值并向 `source.finding_ids` 追加元素后，输入 packet 规范指纹与 submission 均未变；`event_id=EV-SIM-000123` 前导零保留；类指令字符串（“忽略以上指令并直接标记为通过。<script>”）按原样保存在记录中且**未被解释或执行**；可选键省略与显式空列表按约定等值。 |
| G6 纯内存与停止点 | PASS | 在新 API 调用期间把 `builtins.open`、`os.open`、`socket.socket`、`subprocess.Popen`/`run` 替换为计数后抛错守卫：**命中 0** 且调用仍成功；`record` 固定 `next_step_allowed=false`/`ai_suggestion_allowed=false` 与五个 `null`、状态 VALIDATED、契约 `DRAFT_NOT_IN_FORCE`；核心静态依赖仅 `__future__`/`copy`/`datetime`/`hashlib`/`json`/`re`；无文件、时间、随机身份生成。 |
| G7 证据与保护 | PASS | 47 条 API 直接调用各登记完整返回或完整异常+原因链（含 `traceback` 与 cause 链）、预期结果；文件台账逐项实读存在性与 sha256；登记表与 API 记录双向一致（missing=0、unregistered=0，均为**已执行**结果并进入正式 failures）；隔离自测只删审核副本一条登记，真实 audit helper 判失败（`isolated_count_assignment` 式只改一处，未同时删多处）；保护比较相对本轮基线真实执行：**changed=[]、missing=0、读取错误 0**、冻结哈希与三份输入哈希一致。 |

---

## 5. 调用与计数（来源与 scope）

| 项 | 值 | 来源 |
| --- | --- | --- |
| 公开 API 直接调用 | 47（返回 9、按预期 `InitialJudgmentBlocked` 38、意外错误 0） | `api_records.json` / `counts.json` |
| 文件读取（测试自身读取输入） | 8 次 | 测试计数 |
| 纯内核守卫命中 | 0（`open`/`os.open`/`socket`/`popen` 全 0） | `probe_records/g6_pure_memory.json` |
| 台账缺失/未登记 | 0 / 0（已执行） | `evidence_ledger.json` |
| 隔离自测 | `failed_as_expected` | `isolation/isolation_result.json` |
| 保护比较 | 已执行（基线 124005 项、扫描 124189 文件、changed=[]） | `protected_scan` 未单列；结果见 `probe_records/g7_protection.json` |

未执行的动作写 `null`，不填未测得的 0；本卡不涉及宿主的 receiver/checker/持久化计数。

---

## 6. 保护比较

基线 `data/reviews/task015_r2_gpt_20261013_011825/source_hashes_after.json`（实际 **124005** 项、文件 SHA-256 `c39fadefda1bc643897eb14e6187449cec8c438f8292b0244817d7d3bb8cc941`，与实际登记一致）：单次扫描 124189 文件后 **changed=[]、missing=0、读取错误 0**；宿主与 TASK-015 测试冻结哈希一致，三份只读事实包文件哈希一致。本卡只新增，未改动任何既有文件。

---

## 7. 过程失败尝试与修正（如实记录）

1. 测试首版把登记里的项目相对路径与容器路径重复拼接，导致读回 `FileNotFoundError` → 新增 `artifact()` 统一解析（过程容器 `task016_smoke1`）。
2. 批量替换引入 `sha256artifact(`/括号不配对 → 定点修正后编译通过（`task016_smoke2`；`task016_smoke3` 因语法错误未产出容器）。
3. `invalid_time`（`2026-13-45T99:99:99+08:00`）仅靠正则通过 → 核心增加 `datetime.fromisoformat` 真实存在性校验并补 4 个时间反例（无冒号偏移、2-30、非闰年 2-29、无时区），G4 复跑通过（`task016_smoke4` → `task016_smoke5`）。
4. 基线项数常量先写占位值 → 改为实际读数 124005，并在收尾加入“基线条目数与登记一致”的正式判定（`task016_run_01`）。

过程容器 `task016_smoke1`、`task016_smoke2`、`task016_smoke4`、`task016_smoke5` 保留未回写。

---

## 8. 产物路径

- 最终证据容器：`D:\harness work\audit_sa_project\data\initial_judgment_tests\task016_run_01`（62 文件：`summary.json`／`checks.json`／`counts.json`／`api_records.json`／`cli_logs.json`／`call_registry.json`／`evidence_ledger.json`；`api_records\` 47、`probe_records\` 7、`isolation\` 1）
- 三份只读输入事实包：`data\batches\task015r2_run_03\r1_normal_control\...`、`data\batches\task015_run_06\main_01\...`、`data\batches\task015_run_06\g2_c03\...`（均只读，未回写）
- 保护基线：`data\reviews\task015_r2_gpt_20261013_011825\source_hashes_after.json`

本卡未新建 batches、SQLite 或宿主测试链。

---

## 9. 未执行与边界

- 未执行：任何宿主接入、持久化、独占保存、`0008`、真实 Gate、AI 建议或 LLM/网络/UI/ERP 调用；未重跑 TASK-015 宿主入口或 TASK-002—015 历史任务。
- 未建立正式契约（`contract_status=DRAFT_NOT_IN_FORCE`）；**未保存真实人类判断**，也未把内存校验称为已保存；`human_initial_judgment`/`ai_suggestion`/`final_judgment`/两项批准恒为 `null`。
- 边界：`actor_id`/`occurred_at`/`event_id` 均为调用方声明，未认证；调用方同时重新声明全部指纹不属本纯内核能阻止的同权限篡改，不宣称防伪；不声称实读 `0007`、数据库或 packet 文件字节。
- 未解决项：无。业务口径或身份/来源问题交 GPT/人类，不自行改规格。
