# TASK-022-R3 执行回执（测试证据与本次真实观察完整绑定）

任务：按 `docs/tasks/TASK-022-R3.md`（B 类，DSH 处理）完成**唯一剩余**的 B3 证据收尾修正：终审内容必须与**本次真实观察**完整绑定；依据 `docs/reviews/REVIEW_TASK_022_R2.md`（NOT_ACCEPTED）。
日期：2026-10-13。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：`STORED_SNAPSHOTS_ONLY` 不变。**生产存储实现自本卡起冻结**（未改一字节），未改 P1、正式契约、宿主/控制器或业务文件；未接宿主/控制器，未生成真实批准/初判/`0009`，未开放 AI/终判。快照保存 ≠ 批次批准 ≠ 运行放行 ≠ 身份认证。

---

## 1. 起点身份、冻结件与保护基线

| 项 | 值（实读） |
| --- | --- |
| **生产存储模块（冻结，本卡未改）** | `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7`（41353）✅ |
| 测试（起点） | `fa66ac697f24a623fbb06baecf7d72f5ef048616691edc97c4304c7023d17b61`（93717）✅ |
| 指南（起点） | `953ec1008d2584fafe295f0cbad2fa7de8bc80dcf3f0c745f8bec11a75a3cc3f`（18504）✅ |
| P1 / 正式契约 / 生效登记 | `5ccdd0f3…4e79` / `174a021b…40ad` / `042086cb…061d` ✅ |
| 宿主 / 控制器 | `38869681…a307` / `a6b7b8e1…3a8c` ✅（仅实读） |
| 保护基线 | `data/reviews/task022_r2_gpt_20261013_234348/source_hashes_after.json` = `5d2223763562e9e0a0d27e2e6ddd3984c1d84eac5d613e24407132505cbbdbc6`、**136714** 项、`verdict=NOT_ACCEPTED`（只排除两个确切自指元数据路径） |

其他既有文件、全部旧回执/评审/现场/junction **未改、未删、未移动、未补签**；未执行旧容器脚本。

---

## 2. 交付文件（写后实读）

| 文件 | 说明 | SHA-256 | 字节 |
| --- | --- | --- | --- |
| `tests\test_store_demo_human_gate_decision.py` | 独立预期 + 终审完整内容比较 + 内容定点（本卡唯一实现改动） | `43884b406b1f70293d31d9dadac0b925021e7bc37b36e015b06d4e32fe26d817` | 105015 |
| `docs\HUMAN_GATE_DECISION_STORE_GUIDE.md` | 证据能力同步（§10.2） | `3d3805f42444f3e6f06b3a77e55744dcf9c3849252e105c9f67078067ae2582f` | 20165 |
| `docs\EXEC_REPORT_022_R3.md` | 本回执 | 自身最终 SHA **只在交接消息给出**（不写回自身） | 11200 |
| `scripts\store_demo_human_gate_decision.py` | **冻结未改**（§7.1 冻结身份核对一致） | `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7` | 41353 |
| `task022r3_run_01` | 正常轮次（证据容器 + 记录轮次根） | 见 `evidence_ledger.json`（13 项、`missing=[]`/`unregistered=[]`、`content_compare.ok=true`、`core_audit.ok=true`、`api_audit.ok=true`） | — |
| `task022r3_fault_01`（故障脚本）/ `fault_02`（`{}` 替换）/ `fault_03`（合法形状自洽替换）/ `fault_04`（checks LF 对照） | 分离故障轮次 | 见三个 `*_result.json`（均 `ok=true`） | — |
| `task022r3_dev_01`—`dev_02` | 过程容器（保留不回写） | — | — |

---

## 3. 唯一阻断的修正（逐项关闭）

### 3.1 独立、定稿的真实观察预期

- 新增 `_observation_expectation(core_registry, api_records, call_registry_payload)`：在**全部 API 与真实核心
  观察（含三时点）定稿后、任何终审读取之前**，从**该次实际观察结果**建立**独立深拷贝**预期，覆盖完整
  `core_call_registry`、完整 `api_records` 与权威调用登记；来源标记
  `in_memory_real_observations`，**不读候选磁盘文件、不再调用 P1**、不与后续可变对象互为自身。
- 正式检查「R3-01 定稿真实观察预期已冻结」验证：预期与内存观察规范相等、且为**不同对象**（`is not`）、
  条目计数一致；预期在有界两轮审核中**不刷新**。

### 3.2 同缓冲内容、关系与字节审核

- 终审**一次读取**各最终载荷缓冲，从同缓冲取对象与 SHA；新增
  `_content_compare(expected, core, api, call)` 对三个完整解析对象做**规范比较**，并按
  `core_call_id` / `call_id` **定位差异字段路径**（`_field_diff` / `_located_differences`）。
- 顺序固定为：**完整内容比较 → 既有 ID/entry/total/入口/API 关联审核 → 字节漂移确认**；文件 SHA/长度来自
  通过内容审核的缓冲，漂移确认仍以该读数为准，**不在替换后重新读成“新正确预期”**。
- 任何不一致进入正式 `failures`、`summary=FAIL`、非零返回与 `final_audit_diagnostic.json`；故障现场不恢复、
  不重写核心载荷凑成功。
- `returned` 载荷最低形状收紧为冻结 P1 的完整两键外层（`record` + `record_fingerprint`），`{}` 不再被视为
  完整成功外层；异常与输入记录受**同一完整比较**约束。
- 正式检查「R3-02 终审缓冲的完整对象与定稿真实观察一致（core/API/权威登记）」在正常轮次通过。

### 3.3 定点与隔离（`_content_isolation`，全部走真实比较 helper）

| 情形 | 结果 |
| --- | --- |
| 真实完整原件 | 通过（`original_content_compare_ok=true`） |
| 只把一条 returned 的 `result` 替换为 `{}`（ID/计数不变） | **拒绝**，定位 `core-001: result.record / result.record_fingerprint` |
| **合法形状的自洽替换**（改人类 reason 并同步内部规范指纹，键/计数不变） | **拒绝**，定位 `core-001: result.record.reason / result.record_fingerprint` |
| 输入理由改写（inputs 侧） | **拒绝**（同一完整比较约束） |
| 既有控制（删 ID / 删完整 entry / 重复 entry / 空壳 entry） | 继续拒绝（保留 R2 成果） |
| `_entry_complete` 对 `{}` 判定 | 不完整（`entry_completeness_rejects_empty=true`） |

---

## 4. 真实入口故障（评审时机）

三个故障均**分离新轮次**，wrapper 调用真实 reader/审核并返回其原值，不伪造失败列表：

| 故障 | 轮次 | 时机与改动 | 结果 |
| --- | --- | --- | --- |
| `{}` 返回替换 | `fault_02` | 第一次终审读取**之前**，只把磁盘 `core-001.result` 换成 `{}`；ID/entry 数/total/入口/API 关联与内存观察不变（`counts_and_ids_preserved=true`） | **返回 1 / FAIL / failures 非空**；`content_compare.ok=false`，定位 `core-001: ["result.record","result.record_fingerprint"]` |
| 合法形状自洽替换 | `fault_03` | 同上，改为改写 reason 并同步 `record_fingerprint` 使候选自洽 | **返回 1 / FAIL**；定位 `core-001: ["result.record.reason","result.record_fingerprint"]` |
| checks.json LF 对照 | `fault_04` | 首轮终审读数之后仅对 `checks.json` 追加一个 LF | **返回 1 / FAIL**；漂移检出 `checks.json` |

三个 harness 的 `checks` 全真（`ok=true`），现场均**保留不恢复**。

---

## 5. 实际运行与 scope

```text
.venv\Scripts\python.exe -B tests\test_store_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_store_tests\task022r3_run_01
→ TASK-022-R3 测试组：134 项检查，0 项失败；存储 API 51 次、嵌套核心 26、直接核心 0、
   入口观察 26；读取事件 606、守卫命中 0
→ 退出码 0
```

| 作用域 | 实测 |
| --- | --- |
| 公开存储 API | **51**（save 24 / verify 27） |
| 嵌套真实 P1 / 直接真实 P1 / 入口观察 | **26 / 0 / 26**（五者计数一致、`closure_ok=true`） |
| 读取 / 写入事件（真实 `io.open`/`os.*`） | **606**；范围外读取 0；守卫 0 |
| 台账 | **13 项**逐文件实读一致；期望来自通过内容审核与漂移确认的终审读数 |
| 内容比较 | `content_compare.ok=true`（core / api / 权威登记三项 `equal=true`） |
| 正常返回码 | **0**；三个故障返回码 | **1 / 1 / 1** |

**未执行**（记 `null`/`not_executed`）：宿主/控制器接线与调用、Gate1/Gate2 适配器、业务核心与业务历史入口、
真实初判、`0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨目录全局历史发现、P1 的 195 次完整入口
与协议 117 例全套；**只执行证据收尾的 `--only` 定点模式未实现**（`not_executed: only_r3_mode`），
其审核不适用默认零通过；采集预期/观察器读取/被测组件 IO 的作用域已分列登记（`read_observation.json`、
`core_call_registry.json`、`api_records.json`）。

---

## 6. 过程失败与有限更正

1. 本轮局部运行两次失败：`_content_compare` 初版把 `api_records`（列表）当作字典取 `.keys()` →
   `AttributeError`；已改为按记录定位的通用实现（支持 dict/list 顶层）。另初版 `_content_isolation` 有
   无意义的自比较字段，已替换为 `counts_preserved`/`located` 证据。现场保留在 `task022r3_dev_01`。
2. R2 回执中的 `TASK-022-R2` 打印标签已在本轮更新为 `TASK-022-R3`；**旧回执不改**。
3. 旧接缝/旧脚本、旧评审根与故障根、junction 均未改未执行；旧回执措辞/大小/路径仅登记。

---

## 7. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task022_r2_gpt_20261013_234348/source_hashes_after.json`（`5d222376…dbc6`、
  136714 项、`NOT_ACCEPTED`）；只按两个确切自指元数据路径排除，**无目录前缀豁免**。
- 执行者：正常轮次容器内 `scan_protection.py`（只读项目文件、只写本容器 `protection_result.json`），
  **仅一次**；另含**冻结身份核对**（生产存储/P1/正式契约/生效登记/宿主/控制器实读 SHA 必须一致）。

### 7.1 扫描结果与最终身份

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **137882** |
| `changed` | **仅 2 项**：`tests/test_store_demo_human_gate_decision.py`（`43884b40…d817`）、`docs/HUMAN_GATE_DECISION_STORE_GUIDE.md`（`3d3805f4…582f`）；**范围外变化 0** |
| 冻结身份 | 生产存储 `594e42d0…48e7`、P1 `5ccdd0f3…4e79`、正式契约 `174a021b…40ad`、生效登记 `042086cb…061d`、宿主 `38869681…a307`、控制器 `a6b7b8e1…3a8c` **实读一致（不一致 0）** |
| `missing` / 读取错误 / 范围外新增 | **0 / 0 / 0** |
| 本轮允许新增 | **1168** 项：`docs/EXEC_REPORT_022_R3.md` + 七个 `task022r3_*` 证据容器 + 六个 `task022r3_*` 记录轮次根（确切路径逐项登记，`prefix_exemption_used=false`） |
| 扫描后动作 | 扫描后**仅**对本回执的产物身份做有限登记（§2 与 §7.1 的 SHA/字节），**未再改测试或指南**；未重复全树扫描（`tests/` 与指南哈希在扫描前后一致） |
| junction 现场 | 前轮与 GPT 评审 junction **未删除、未移动** |

---

## 8. 绝对路径

- `D:\harness work\audit_sa_project\tests\test_store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_STORE_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_022_R3.md`
- `D:\harness work\audit_sa_project\scripts\store_demo_human_gate_decision.py`（冻结未改）
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r3_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_records\task022r3_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r3_fault_01\`

---

## 9. 停止点

完成本卡后执行端停止实施并交 GPT 验收；**技术验收通过前不推进 Gate1/Gate2**；不生成真实批准、初判或
`0009`，不开放 AI。人类操作看板并作出业务决定，技术验收不能代签。若实际发现需修改生产存储/P1/API/schema、
正式契约、材料时序、允许根、历史范围或运行放行，**立即停止本卡受影响处理并报告重新定界/升级 C 类**。
