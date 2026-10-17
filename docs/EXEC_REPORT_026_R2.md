# TASK-026-R2 执行回执：补齐有限残余与测试真实收尾

日期：2026-10-15。任务卡：`docs/tasks/TASK-026-R2_DRAFT.md`。依据：`docs/reviews/REVIEW_TASK_026_R1.md`（**NOT_ACCEPTED**，部分关闭）。
分类：**B 类定点修复**（DSH 实施、GPT 验收）。只处理 B1/B2 残余与 E1 收尾；**不重做** R1 已关闭的常见 schema、
合法 scope 构建、prepare 独立 SHA、真实 writer 半写；未新增功能/协议/IO 框架/业务判断；未推进 TASK-027。

## 1. 起点核对（只读实读）

| 对象 | 要求 | 实读 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | `d27d3289245d6ddffa4da9aac0c11848795e9a13f606a891f5458af5ede0e6e8` / 55702 | 一致 |
| `tests/test_runtime_gate1_registry.py` | `2e46a9e48fee042bb13672188c9d441a4f1bdfed9ddbb191bc72207007a10e0d` / 45350 | 一致 |
| `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md` | `cede81881a0822c713f0e27b385980c24c7b6287c68ab0e5bda33300ae7d85f2` / 7048 | 一致 |
| 基线 | `data/reviews/task026_r1_gpt_20261015_032227/source_hashes_after.json` | 见同根 `review_result.json` |

## 2. 交付物

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py`（修改） | 60761 | `a373f4b508e15548bd7a17c9f5270d365b1c12d19988fedd9a9fbcef15432c3a` |
| `tests/test_runtime_gate1_registry.py`（修改） | 39871 | `e898483f369008780ae43774245d6a6a79df21edee203fd0db38becb19d41ad7` |
| `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md`（修改） | 8406 | `5d11e754e957c537a9542d65f738a11604591c63342f8dace8add31ea7dac188` |
| `docs/EXEC_REPORT_026_R2.md`（本回执） | 见交接消息 | 最终 SHA 见交接消息（避免自指） |
| `data/runtime_gate1_registry_tests/task026r2_run_01/`、`task026r2_fault-check/`、`task026r2_fault-payload/` | — | 见 §6 |
| `data/batches/task026r2_run_01/`、`data/runtime/task026r2_run_01/` | — | 逐条确切路径见保护扫描 |

## 3. B1 残余关闭依据

1. **静态 capture 不再被丢弃**：`_require_current_static_identity(registry, self_capture, captures)`
   把本次实读的 13 代码 / 4 规则 / 冻结准备器 / 配置 / 契约 / 生效记录全部写入 `captures["project"]`
   与 `captures["frozen_prepare"]`；`read` 与 `prepare` 的末端复测逐项 `_recheck_capture`
   （read 实测 25 项末端字段，含 `docs/SPEC_V1.md`、`config/human_flow_v1.json`、契约等）。
2. **23 份 project 材料全量实读**：来源核验返回后，对声明中的每一份 `project/` 材料做同缓冲实读
   并与该次声明逐项闭合；存在未被覆盖的 project 材料即拒绝。
   `prepare` 登记 24 项 project 材料（23 份既有 + 本脚本）与 32 项材料总数经测试核对。
3. **来源目录集合收尾**：`_require_fixed_members` 按**集合相等**核验批次顶层
   （`batch_manifest.json`、`gate1_packet.md` 与四个固定子目录）与 `checks/ code_snapshot/ logs/ source/`
   四个子目录的叶子集合；build 与 prepare 末端都核验，叶目录集合同样按集合相等核验。
4. **最低实测**：
   - 静态材料（`docs/SPEC_V1.md` 的**字节相同隔离副本**，在真实身份核验读取时被重定向到该副本，
     未改任何冻结文件）在真实末端复测的取数行之前改盘 → `read` 本次拒绝：
     `RuntimeGate1Blocked: docs/SPEC_V1.md`（注入命中 1 次、末端读数 7 次）。
   - 合法批次在真实来源核验返回后 `checks/` 新增 `unknown.json` → `build` 本次拒绝：
     `RuntimeGate1Blocked: batch/checks`（注入命中 1 次）。
   - 正常对照：build/read/prepare 全部成功，登记字节稳定。

## 4. B2 残余关闭依据（隔离副本同步全部外层摘要）

| 反例 | 结果 |
| --- | --- |
| `registered_at="not-a-time"` | Blocked `registry.registered_at` |
| `registered_at="2026-10-15T00:00:00"`（缺时区） | Blocked `registry.registered_at` |
| `rules_manifest.entries[0].rule_id=[]` | Blocked `registry.rules_manifest.entries[0].rule_id`（非空字符串预检，**无 TypeError 泄漏**） |
| `scope_ref` 指向**已存在的旧空 scope** | Blocked `registry.scope_ref` |
| 合法带时区 ISO 时间（`+00:00`）对照 | 通过 |

`registered_at` 按“合法 ISO 8601 + 真实日期 + 必须带时区”的技术登记时间核验（不是人类决定时间协议）；
`rule_id` 在任何字典查询前判非空字符串；`read` 与其他两 API 一致拒绝既有 scope，并在末端核对该计划路径状态。

## 5. E1 关闭依据

### 5.1 实际调用观察（同一套轻量记录路径）

- `call_api` 覆盖**全部** 20 次直接公开 API 调用（成功与拒绝）：`call_id`、操作名、调用**前**文件读数、
  关键输入、完整真实返回（10 次）或异常 + traceback + `field`/`stage` + `cause_chain`（10 次）。
- 冻结准备器嵌套调用独立观察：`sys.setprofile` 按**真实代码身份**统计
  `scripts/prepare_demo_human_gate1_request` 命中 **8** 次；公开 API 按真实代码身份统计为
  `build_runtime_registry=3`、`read_runtime_registry=7`、`prepare_runtime_gate1_request=10`。
  禁止入口（P1/store 快照/sqlite 装载/标准化）真实观察命中 **[]**。
- 接收器 CLI 两次真实执行命令、完整 stdout/stderr（528B/524B 等，无截断）与返回码 0/1 全部落盘；
  子进程内部计数按 `null` + 原因登记。
- 业务/证据路径全部由 `--out-dir` 技术轮次派生；旧现场只读、未删除。

### 5.2 写盘与审核（一次写定 + 末次真实裁决）

- 写盘前冻结本次实际观察的完整期望 `expected_payloads` 与 `expected_audit`
  （预期最终状态、预期问题），此后不刷新。
- 全部证据载荷**一次写入**：`summary.json`、`checks.json`、`failures.json`、`api_records.json`、
  `audit.json`、`audit_failure.json`；随后做**最后有界字节确认**并写 `final_confirm.json`；
  `evidence_ledger.json` 覆盖全部 7 份载荷（不含自身 SHA）。成功路径此后不改写已登记载荷。
- 末次审核由同一 `audit_evidence` helper 直接消费结果：canonical 形态、`checks_total/checks_failed/failures`
  一致、`call_id` 双向唯一、**由载荷内容复算指纹**并与定稿观察比较、`expected_audit` 行核对、
  台账逐项长度/SHA。审核失败/字节漂移 → 入口非零、磁盘 `summary.status=FAIL`、
  `audit_failure.json.failure_reasons` 非空。

### 5.3 三个真实收尾控制（同一 main 与审核 helper，均实测）

| 控制 | 入口 | 磁盘 `summary.status` | 失败记录 |
| --- | --- | --- | --- |
| 正常 `task026r2_run_01` | **0** | `PASS` | `failures=[]`、`audit_ok=true`、`problems=[]` |
| `--fault-check`（写盘前只改一项磁盘检查结果，内存未预先设 FAIL） | **1** | `FAIL` | `failures` 非空（含被改项） |
| `--fault-payload`（只改一项已记录返回值内容：`registry_file_sha256=64×0`，ID/计数/形状合法） | **1** | `FAIL` | `audit_failure.problems=['payload_content_mismatch:call_001']` |

隔离副本（删一条 API 记录）由同一 helper 检出 `api_call_ids_mismatch`；`--audit-fail` 这种“预先制造内存失败”
的方式已被删除，不再作为收尾证据。

### 5.4 out-dir 与 scope 契约

- `--out-dir` 使用 `Path.relative_to(TEST_ROOT)` 严格后代判定（**不用 startswith**）：同前缀兄弟目录、
  越界、证据根本身、既有非空目录均拒绝。
- **不在记录根创建/删除任何 scope**（包括测试临时目录）；既有 scope 只读复用于 3.4 的拒绝对照
  （`data/human_gate_decision_records/gate1/task024_dev_04_approve`）。本轮 scope 路径
  `task026r2_run_01_scope` 始终不存在。

## 6. 本轮真实执行 / 注入 / 旧证据读取 / 未执行

- **真实执行**：冻结接收器 CLI 3 轮 ×2 次（真实 checker 子进程返回码 0/1）；冻结准备器真实调用 8 次/轮；
  本层三 API 20 次/轮；独立 canonical/字段/文件 SHA 复算。
- **注入（同进程、包装真实读取或真实接缝）**：静态材料末端漂移 1 次；来源核验后批次集合变化 1 次；
  四类 B2 隔离副本反例；`--fault-check` / `--fault-payload` 各 1 次（均在同一 main 的真实末次审核边界）。
- **读取旧证据**：R1/R2 任务卡与评审、TASK-025 基样、TASK-026 和 R1 的既有证据与回执只读引用；
  旧 `task026_run_01`、`task026r1_*` 现场**未重跑、未改动**。
- **未执行 / not_executed**：本轮未重跑 writer 半写、历史核心入口与 R1 已通过坏字段大套件（引用旧证据，
  已注明未重跑）；未调用 P1/store/标准化/装载/Gate2/筛查/初判/AI/终判；未创建决定记录、SQLite、
  运行 profile、宿主检查点；未创建或删除任何 scope。

## 7. 更正 R1 不符声明（只写新回执，旧回执不改）

- R1 称“守卫装在真实入口”：实际是 `load_guard_target` 另建三个独立模块做本地替换，相同 `__file__`
  不证明同一 module/函数。本轮改为 `sys.setprofile` 按真实代码身份统计真实入口命中。
- R1 称“完整登记”：实际只登记 3 条正常调用。本轮覆盖全部 20 次公开 API 与 8 次嵌套准备器调用，
  保存完整返回或异常链，调用前读数在调用前取得。
- R1 称“一次写定并完整覆盖最后字节”“磁盘审核失败已落盘”：实际在最终确认后又重写
  summary/checks/failures/audit，`--audit-fail` 按 flag 直接 return 1。本轮一次性写定全部载荷、
  末次审核直接支配入口，且 `--fault-check`/`--fault-payload` 在真实末次审核边界注入并被检出。

## 8. 保护与收尾

- 一次最终全树扫描（`data/runtime_gate1_registry_tests/task026r2_run_01/protection_scan_026r2.json`，
  `03dd3b36d25df621b21894ae77a3d1e6c341a06e4a03d27e6e1f5f4b1653411b`）：基线
  `data/reviews/task026_r1_gpt_20261015_032227/source_hashes_after.json`（实读 157657 项）；
  `changed = 3`，恰为本卡三份修改文件；`out_of_scope_changed = 0`；`added = 152`、
  `allowed_added = 152`（逐条确切路径计算，`ALLOWED_ADDED_PREFIXES` 为空集）、`out_of_scope_added = 0`；
  `missing = 0`、`read_errors = 0`；R5 越界 326 项逐项不变（drifted 0 / gone 0）；`scope_compliant = true`。
- 文件范围与临时目录动作分别如实登记：本轮未在记录根内建删任何目录；三个证据根与
  `data/batches/task026r2_run_01`、`data/runtime/task026r2_run_01` 均按确切路径登记。

## 9. 待 GPT 裁决

1. 静态材料读数集合与末端复测覆盖是否满足 B1（含 23/24 份 project 材料与目录集合相等）。
2. `registered_at` / `rule_id` / `scope_ref` 三处预检口径。
3. 收尾三控制与证据台账（含 `expected_audit` 行、`audit_failure.json`）是否足以替代旧声明。
