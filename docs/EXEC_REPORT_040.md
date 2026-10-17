# TASK-040 执行回执：合成运行初判保存与只读恢复

日期：2026-10-17。交付状态：实现、测试、指南与证据定稿，**交 Architect 独立验收**；本回执不宣布验收通过、
不改看板、不推进下一卡。真实批准仍 `null`，真实独立初判未保存，开发宿主仍 0008，`next_step_allowed=false`、`ai_enabled=false`。

唯一实施依据：`docs/tasks/TASK-040_DRAFT.md`，18513 B / `a1fb5e0f7347c0cfdd1b7ff7c003106c1796da216a2f643c623cd180b2b521a1`。
设计依据：TASK-039-R1 已接受协议/案例（`TASK-039-recording-design-1.1`）与冻结初判 core/store/history。

本回执在最终保护扫描之前定稿，**不预填尚未取得的扫描结果**；扫描实际数字、四件最终身份与确切新增清单
在扫描后写入 `data/runtime_initial_judgment_recording_tests/task040_finalization/delivery.json`，
不回写本回执迎合结果。唯一既有可修改文件仍是 `scripts/runtime_gate1.py`。

## 1. 四件交付身份（实测同缓冲长度/SHA）

| 交付 | 相对路径 | 长度 | SHA-256 |
| --- | --- | --- | --- |
| 适配器（唯一修改的既有文件） | `scripts/runtime_gate1.py` | 389797 B | `7b3267153cbaf192360403e92d429d45af701bec6cd3f4f1bb1d7dcbf508345d` |
| 新测试 | `tests/test_runtime_initial_judgment_recording.py` | 46473 B | `a4e285feaadbac6e67be81875b84b9681081eaf9aeeedafa0070f5ebf804ddef` |
| 新指南 | `docs/RUNTIME_INITIAL_JUDGMENT_RECORDING_GUIDE.md` | 7807 B | `673844fea3cd136d55a52bbb4cb9ef38c464f4416136af28458e5ed686c72e12` |
| 本回执 | `docs/EXEC_REPORT_040.md` | 见 delivery.json | 见 delivery.json |

## 2. Profile：19 API / 17 代码 / 40 材料

- 原有十七公开业务 API 签名与规则保持，新增两个后共 **19**：`save_runtime_initial_judgment`、
  `verify_runtime_initial_judgment`。
- 代码清单仍 **17** 项：13 冻结组件 + 初判 core/store/history + 适配器自身（适配器 FILE 来自本次开始缓冲）。
- Gate1 材料由 38 项增至 **40** 项：新增已接受的
  `docs/proposals/RUNTIME_HUMAN_INITIAL_JUDGMENT_RECORDING_PROTOCOL_V1_DRAFT.md`（0b92e862…6b2db，36779 B）与
  `..._CASES_V1_DRAFT.md`（177d5801…729b，23542 B），以独立固定身份读核、开始捕获并末次确认。
- 版本：`REGISTRY_VERSION=TASK-040-runtime-registry-1.0`、
  `CODE_MANIFEST_VERSION=TASK-040-code-manifest-1.0`、`RUNTIME_VERSION_028=TASK-040-runtime-gate1-1.0`；
  旧 TASK-038 凭证的版本/身份明确拒绝（不迁移、不补签）。新链登记实测为 `TASK-040-runtime-registry-1.0`
  且 `run_binding.code.file_sha256` 等于当前适配器 SHA（`task040_dev_01/iter07`、`task040_run_05` 实读）。

## 3. 正常链与完整调用图（实测，非预测）

正常链（`task040_run_05`）：注册 → Gate1 请求/保存 → 装载 → Gate2 请求/保存 → 筛查 → 复算 → 事实各一次；
人工提交只用已登记夹具（event_id="2"、actor_id="1"、declaration_note="1"、decided_at_raw="2026-10-16"、
assessment="通过"、reason="无明显不一致且合规"），技术 request 为 `TECH-REQ-IJ-0001`。

n=0 保存调用图（`save.initial` 实际 code-object 入口计数）：公开 prepare 1、store.save 1、保存后 history 1
（总 history 2）、初判 store.verify 1、初判 core 2（构建 1 + 核验 1）；Gate1 核验 6、Gate2 核验 5、
装载 inspect 5、筛查 inspect 2、复算 inspect 1、事实 inspect 1、`render_markdown` 1、Gate store 核验 11、
Gate core 11、冻结准备器 6；归一化/装载/筛查/复算/事实 build/旧模拟初判均 0。

m=1 恢复调用图（`verify.initial`）：直接 history 1、Gate1 6、Gate2 5、装载 inspect 5、筛查 2、复算 1、
事实 inspect 1、render 1、Gate store 核验 11、Gate core 11、冻结准备器 6；公开 prepare 0、store.save 0、
初判 store.verify 1、初判 core 1；算法/构建 0。m=2（`verify.later_batch`）时初判 store.verify/core 各 2。

## 4. 观测与输入三时点

- 测试入口 56 项 check 全部通过（`summary.status=PASS`，`checks_failed=0`；`api_call_count=17`、
  `core_call_count=341`），实际退出码 0。
- 原 `submission` 对象在保存后仍是同一引用、内容与保存前逐字节一致，且与目标叶 `submission.json` 一致
  （check S9）；原 `history_expectations` 未被改写（S10）；嵌套记录保存每个冻结调用进入/返回/异常前后
  的输入点快照（`input_refs_before/after/api_end`，同引用三时点）。
- 保存返回恰十二键、九权限边界严格 `false`；`storage_verification` 与保存时除 `status` 外字段一致；
  目标叶恰六文件、运行封装恰三件、锁已解除（S1—S8）；`manifest_file_sha256` 与目标 manifest 实际字节一致，
  `record_fingerprint` 与目标正文规范指纹一致（S5/S6）；核心 `persisted` 仍 `false`、`record_status` 为
  `HUMAN_INITIAL_JUDGMENT_VALIDATED`（S7）。
- 恢复返回 `VERIFIED`、身份/记录/清单稳定字段与保存一致；后来其他 batch 的已接受 TASK-037 合成叶
  （`z_first`，byte-exact 复制）使当前域大于保存时 H1 后仍 VERIFIED，旧 P0/H1/receipt/封装字节全部未变
  （R1/R2）。恢复窗口写/网络/子进程/时钟守卫先证明生效再运行，实际命中 0 且未落盘（V5/V6）。

## 5. Windows 真实句柄锁平台实证

纯技术锁场景（`_work` 外置 scratch，非项目证据）实测：`CREATE_NEW` 成功；正文五技术键；
持锁时普通路径读取与重命名被共享拒绝，同路径二次独占被拒；真实独占句柄半写后文件保留并阻止重试；
file ID 不符时拒绝按路径删除且句柄关闭；按已持有句柄设置删除标记并 `CloseHandle` 后原路径消失。
Git 说明：锁请求读/写/删除、仅共享读，因此持锁期间普通读者（含 Python `open`）按 Windows 共享规则
被拒绝——这是"仅共享读 + 删除权"的真实结果，不视为缺陷；本层自身只用持柄读写与属性读取。

## 6. 具名失败场景（7 条，均在 `task040_run_05_f0x_*` 独立根，同一定稿代码）

| 场景 | 控制 | 实测结果 | 现场 |
| --- | --- | --- | --- |
| f01_bad_submission | 删除 `assessment` | `Blocked store.submission.assessment` | 封装 started+failure；无目标叶；锁保留 |
| f02_stale_materials | 陈旧 64hex 材料指纹 | `Blocked store.submission.request_binding.materials_fingerprint` | 同上 |
| f03_store_half_write | 包装冻结 store 真实 writer 半份后 OSError | `Error stage=write.expectations.json` | 半写叶+失败现场+封装 failure；锁保留 |
| f04_context_half_write | 包装本层 context writer 半份后 OSError | `Error stage=write.context` | 六快照+started+半 context+failure；锁保留 |
| f05_receipt_sentinel | 真实 receipt 写完后 sentinel OSError | `Error stage=write.receipt` | 完整 receipt 保留为失败现场；锁保留 |
| f06_release_failure | 注入释放失败 | `Error stage=release.lock`，绝不返回 RECORDED | 六快照+三封装+failure；锁保留 |
| f07_lock_preexisting | 真实独占句柄控制锁先存在 | `Blocked lock`（业务调用增量 0） | 无本次封装/叶；控制锁保留 |

全部失败场景均未返回成功值，未删除/移动任何叶、锁、半写或坏字节。

## 7. 44 例映射（实测 / 引用 / 未执行）

逐例映射由测试写入 `summary.json` 的 `results.case_map`（40 例有明确处置），要点：

- 实测：RC-01（n=0/m=1）、RC-05（f01）、RC-07（f02）、RC-11/29/30（单文件漂移与精确恢复）、
  RC-14（不完整名单）、RC-17（真实锁拒绝 + 恢复锁存在拒绝）、RC-22（f03）、RC-24（f04）、
  RC-25（f05）、RC-27（S8/S11/R2）、RC-31（m=1）、RC-32（m=2 后来其他 batch）、RC-39（守卫证明）、
  RC-41/42（CLI replay）、RC-43（f06）、RC-44（run_binding/request_sha256/context FILE 显式字段角色核对）。
- 只读引用已接受证据、本轮未重跑：RC-02（零线索字段路径，沿用 TASK-039-R1 RC-02 字段关系）、
  RC-21（原链 alias/reparse 由既有 TASK-038/039 检查承担）、RC-38（代码身份漂移拒绝由 registry 绑定承担）。
- 未执行（原因在各例）：RC-03/04/08/09/10/12/13/15/16/18/19/20/23/26/28/33/34/35/36/37/40。
  主要为：需第二注册叶/第二事件链或会永久锁定唯一正常链；物理 junction 无权限；候选内部审核注入
  未另设接缝（避免为控制数量扩大框架）。

## 8. 四项 CLI 控制（各自新进程、新 out-dir）

| 控制 | 命令要点 | 实际退出 | 摘要 |
| --- | --- | --- | --- |
| 正常 | `--out-dir ...task040_run_05` | 0 | PASS，56/56 checks，failures 空 |
| 内容反例 | `--replay ...task040_run_05 --mutate candidate-return` | 1 | `api_records_mismatch:call_001` |
| 台账替换 | `--replay ... --mutate ledger-replaced` | 1 | `ledger_mismatch`/`ledger_bytes_mismatch`/`drift:file_ledger.json` |
| 最后读后字节漂移 | `--replay ... --mutate late-drift` | 1 | `drift:checks.json` |

三次 replay 均未新增业务调用；正常目录内容在两次末次读后未被改动。

## 9. 过程与未执行

- 开发链 `data/runtime/task040_dev_01/iter01..iter07` 原样保留（前六次为本次实现过程中的真实失败/半成功现场：
  S3 预期不一致、`sources['history']` KeyError、记录状态常量误判、S9 历史域集合、verify 末次确认与
  `gate2_event` KeyError、字节比较错误；均伴随锁/封装/failure 保留）。`iter07` 用同一定稿代码身份完成
  n=0 保存 + m=1 恢复冒烟并通过。
- 测试迭代 `task040_run_01..run_04` 目录与场景原样保留；`run_05` 为本次正常最终链与失败场景证据；
  `task040_cli_candidate_return / ledger_replaced / late_drift` 为四项控制证据。
- 未执行：真实数据、强认证、AI、终判、物理 junction、非 Windows 平台、并发双进程真实竞态（只做同进程
  真实独占句柄与路径/重命名拒绝）、非合作篡改证明。原因：本卡为合成数据建设授权，业务边界不变。

## 10. 保护安排与判据

本回执/指南/测试/适配器/全部本轮证据定稿后，仅执行**一次**新的全树扫描（脚本
`data/runtime_initial_judgment_recording_tests/task040_finalization/protection_scan.py`），
根层排除与接受快照相同的 `.venv/.git/__pycache__`，其余逐文件实读。判据：

- 相对 TASK-039-R1 接受基线（168839 项 / `43fa7288…ccae2`）唯一既有 changed 为 `scripts/runtime_gate1.py`；
- 新 missing 0、范围外新增 0、读取错误 0、身份漂移 0；
- 全部新增按**确切文件路径**登记（四份交接文件、三份本轮交付、本轮 `task040_*` 明确根内逐项展开），
  不使用目录前缀豁免，不改接受快照或旧 `review_result`；
- 139 历史损失、27 恢复、326 越界、19 命名偏差、TASK-030 41 B 锁继续单列冻结，不追认、不重建、不清理。

扫描结果、四件最终身份与确切新增清单见同根 `delivery.json` / `protection_result.json`。
