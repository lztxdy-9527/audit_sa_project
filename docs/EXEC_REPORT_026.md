# TASK-026 执行回执：共享运行登记与只读 Gate1 候审请求

日期：2026-10-15。任务卡：`docs/tasks/TASK-026_DRAFT.md`（`bd42b405…b882f`）。
依据：`docs/reviews/REVIEW_TASK_025_R2.md`（ACCEPTED，以工作区修正版为准）。
分类：**B 类实施**（DSH 落地、GPT 验收）。未改变冻结 P1/契约/字段形状，未拆新生产模块，
未新增实现能力之外的范围。

## 1. 起点核对（只读实读）

| 对象 | 要求 | 实读 | 一致 |
| --- | --- | --- | --- |
| 保护基线 `data/reviews/task025_r2_gpt_20261015_020841/source_hashes_after.json` | `cd0ba41ee940ca7f3b7ab572be2961cc8ad9bdb074fcf86423f4fe7a63b7431e`（157302 项） | 同 | ✅ |
| `docs/proposals/HUMAN_GATE_RUNTIME_INTEGRATION_V1_DRAFT.md` | `070fcb26fff69151d39ad4a44f3d9b594b46f221642965d262e2c5d5e3b80cd9`（53188） | 同 | ✅ |
| `docs/proposals/HUMAN_GATE_RUNTIME_CASES_V1_DRAFT.md` | `845732e69413e46d718ec32cbadf3d4376875dd3b5fd2ba73d69334592f8f073`（23493） | 同 | ✅ |
| 修正版基样 `runtime_baseline_corrected.json` | `84cdd60347ffccd8afbeccdce1372c572a1da7ab1a4a1ac97571fa1f71504a84`（55915） | 同 | ✅ |
| `scripts/prepare_demo_human_gate1.py`（冻结准备器） | `ce23671f…0ac4` | 同 | ✅ |
| 旧 Gate1 适配器 `scripts/record_demo_human_gate1.py` | `d8ace42f…34d9` | 同（**零改动**） | ✅ |
| `scripts/store_demo_sqlite.py`（下游入口，未调用） | `1abfad89…a446` | 同 | ✅ |

DSH 原十三键基样（`716d8982…cd8`）仅作历史读取，**未照抄其 schema、未重跑旧构造器**。

## 2. 交付物（只新增四份文件与三个明示根）

| 路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `scripts/runtime_gate1.py` | 43166 | `360be2f50d441f0c7d8c883704bba3da6c57b57920ef6e83ed4bce7b4db834a5` |
| `tests/test_runtime_gate1_registry.py` | 39889 | `f15681114d59b5a08ccf2d6643afb0a981828d3318d6f7382c8011fdc389f633` |
| `docs/RUNTIME_GATE1_REGISTRY_GUIDE.md` | 5932 | `3928887b9f8fee78766aca488afd101143c5b30e0cb05e6a69c571d20ffce62e` |
| `docs/EXEC_REPORT_026.md`（本回执） | 11462 | 最终 SHA-256 见交接消息（避免自指反复改写） |
| `data/runtime_gate1_registry_tests/task026_run_01/summary.json` | 1393 | `82ba8322c5aee92baa2d9f85cb6c46212a8c11900fbb5562828ba584d30a06e9` |
| 同根 `checks.json` / `failures.json` | 14351 / 3 | `65ce4808…8800` / `37517e5f…b570` |
| 同根 `protection_scan_026.py` / `protection_scan_026.json` | 7350 / 22726 | `cedae845…6231` / `5d46180f…3d38` |
| 同根 `isolation_bad_batch/`（隔离副本，8 文件） | — | 逐项见保护扫描新增登记 |
| `data/batches/task026_run_01/`（C06b_normal、C14a_blocked、inputs、两批 manifest 等） | — | 逐项见保护扫描新增登记 |
| `data/runtime/task026_run_01/`（9 个技术叶目录，含正常/阻断/拒绝/半写/晚变更现场） | — | 同上 |

成功叶目录**恰两份登记文件**：`runtime_registry.json`（5095 B）+ `runtime_registry_readback.json`（351 B）。
未创建任何决定记录事件、scope 内容、SQLite 目录、运行 profile 或宿主检查点。

## 3. 实现概要（三 API，无 CLI）

```
build_runtime_registry(batch_dir, runtime_dir, *, scope_dir)  -> 恰三键
read_runtime_registry(runtime_dir)                           -> 恰两键
prepare_runtime_gate1_request(batch_dir, runtime_dir, request_id) -> 恰两键
```

- **真实调用冻结准备器**：build 与 prepare 各一次（build 用固定技术 request_id
  `TASK-026-REGISTRATION-SOURCE-CHECK` 只做来源核验），只复用其**来源核验结果**；
  本层自身 14 项代码清单（13 冻结 + 本脚本）与 32 项材料（冻结 31 项 + 本脚本）由本层独立实读并断言。
- **registry 恰 13 键**：版本/批次/登记时间/scope 引用/8 项批次文件/14 项代码清单/4 项规则清单/
  配置（固定复用冻结 `config/human_flow_v1.json`，不建新配置）/输入/冻结契约三键/run_binding 六字段/
  内层指纹/常量 note。登记对象不含自身指纹；`registry_sha256` 由调用方从返回取得。
- **两份文件**：canonical UTF-8 + 单 LF，独占写并读回；readback 恰五键且不含自身哈希。
- **六键请求**：`materials` 冻结七键（files 恰 32 项）、`expectations` 冻结八键
  （`expected_prior_gate1=null`、`expected_request_id` 原样绑定）、`evidence` 冻结七键
  （五项来源说明取自真实准备器返回，两张清单使用**本次登记**的完整对象，无旧适配器残留）、
  `boundaries` 冻结七键且全部严格 `false`。
- **路径与最终确认**：`runtime_dir` 必须是 `data/runtime/` 内从未存在的新叶（空目录也拒绝）；
  逐级检查 link/junction/reparse 后 resolve 复查；源与 runtime 不得相等或互为祖先；
  所有消费、复算与来源核验完成后做**一次有界实读确认**（含登记文件字节复确认），此后直接返回。
- **失败协议**：叶创建后的失败在本次新叶独占写五键 `failure.json`；创建前拒绝不留输出；
  `read`/`prepare` 只读，发现 `failure.json` 即拒绝且不写诊断。

## 4. 最小验收（测试入口 91 项检查，0 失败）

入口：`.venv\Scripts\python.exe -B tests\test_runtime_gate1_registry.py --out-dir data\runtime_gate1_registry_tests\task026_run_01`
→ `status=PASS`、`checks_total=91`、`checks_failed=0`、`audit_ok=true`。

| 组 | 覆盖 | 结果 |
| --- | --- | --- |
| 1 正常往返（1.1—1.48） | 三 API 外层键、13 键登记、14/4 清单、8 批次/32 材料、6/7/8/7 形状、canonical 字节关系、readback 五键与内部关系、证据使用本层清单、boundaries 全 false、请求不含顶层批次/夹具字段、scope 未被写入、`prepare` 两次规范相同且源与登记字节不变、普通 ID（前导零/换行/64hex）原样保留、非法 request_id 拒绝 | 全部通过 |
| 2 BLOCKED 与拒绝（2.1—2.12） | BLOCKED 来源可登记且可候审、保留真实阻断分类原文、不伪装 OK、来源状态/退出码原样；坏来源（非 xlsx）拒绝且不留输出；缺字段/bool 冒充整数/SHA 尾 LF 的最小隔离例拒绝；错绑定（批次不符）拒绝且未改动登记字节 | 全部通过 |
| 3 路径/持久化（3.1—3.13） | 既有空目录叶拒绝且不写入；越界/根拒绝；源与 runtime 重叠拒绝且不留目录；scope 越界与不存在拒绝；重复 build 拒绝且旧字节不变；**半写注入**（真实写入登记后、读 readback 前注入一次 `OSError`）→ `RuntimeGate1Error` + 五键 `failure.json` + 半写现场保留 + `read` 拒绝 + 坏文件未被覆盖；junction/reparse 一例因本环境 `WinError 1314`（无创建特权）**未能建立**，已记录实际原因（未冒充已执行） | 全部通过 |
| 4 晚变更（4.1—4.7） | 最后来源读取之后的接缝改 `source/input.xlsx` → 立即拒绝且字段指向该文件；恢复后同一请求通过；**改登记输出字节**（保持 canonical）→ 拒绝且字段为 `registry_file_sha256`、坏字节保留；`read` 路径只读不改字节；被改写值的登记 `read` 亦拒绝；无注入对照通过且接缝为空 | 全部通过 |
| 5 范围与证据（5.1—5.5） | P1/store/下游入口守卫**命中 0**；冻结准备器真实调用次数分列（本进程观察 20 次，含组 1—4 的 build/prepare 与重复准备）；未观察的子进程内部计数记为 `null` + 原因；未创建决定记录/SQLite 目录；关键前后源字节已记录 | 全部通过 |

- 测试自身**独立**计算 canonical/字段/文件 SHA 与结果比较，不调用被测 helper 计算期望。
- 落盘后**真实读回审核** `summary/checks/failures`：总数、失败数与 `case` 唯一一致；
  最终失败会支配测试入口的**非零退出与 FAIL**。同名重复定义：未新增。
- **隔离副本检出**：组 2 的错绑定副本与组 4 的登记改写副本均被真实 API 检出并拒绝。

## 5. 真实调用 / 替身注入 / 读取旧证据 / 未执行（分清）

- **真实调用**：冻结准备器 `prepare_human_gate1_request`（build 1 次 + prepare 1 次/请求）；
  冻结接收器 CLI 2 次（`--workbook` 正常夹具、阻断夹具；`checker` 子进程真实退出码 0 与 1）；
  本层三个 API；测试自身的独立复算。
- **替身注入（全部在同进程、且只在观测接缝上）**：`build_after_registry_write` 注入一次 `OSError`
  模拟半写；`prepare_after_last_source_read` 注入来源/登记字节变化模拟晚变更。
  生产路径默认无操作（`INJECTION_HOOKS` 空字典）；**未替换整 writer 冒充分支**。
- **读取旧证据**：TASK-025 修正版基样（只读参考）；DSH 原十三键基样与 54 项自检只读引用、未重跑。
- **未执行**：未调用冻结 P1 公开入口、store、标准化/装载、Gate2、筛查/复算/事实底稿/初判/AI/终判；
  未创建决定记录、scope 内容、SQLite 库、运行 profile、宿主检查点；未改任何冻结文件；
  未重跑 TASK-002—024 历史入口；未运行全量套件。
- 未观察项按 `null` + 原因登记（子进程内部计数）。

## 6. 边界与残余

- 登记不是决定、`PREPARED` 不是批准：本层不产生 submission、不接受人类字段、不赋予动作许可。
- 真实批准 `null`、宿主 `0008`、`next/AI=false`；看板由人类操作。
- 能力边界：本层检测**普通本地字节变化**（含登记输出晚变更），**不**建设同权限全面重写的防御框架。
- 环境边界：本环境无建立 junction/symlink 的特权（`WinError 1314`），reparse 一例如实记录为**未建立**，
  未以其他方式冒充真实路径执行。
- 已知现场：`data/runtime/task026_run_01/` 内含观察到的失败/拒绝现场（含 `failure.json` 与半写叶），
  按纪律**保留不清理**、不覆盖。

## 7. 保护与历史留证

- 最终一次全树扫描（`protection_scan_026.py` / `protection_scan_026.json`，`5d46180f…3d38`）：
  基线 `data/reviews/task025_r2_gpt_20261015_020841/source_hashes_after.json`（157302 项）；
  实读结果 **`changed = 0`**（本卡未修改任何既有文件）、`out_of_scope_changed = 0`；
  `added = 50`，**全部**落在本卡明示的四份交付文件与三个本轮根
  （`data/batches/task026_run_01/`、`data/runtime/task026_run_01/`、
  `data/runtime_gate1_registry_tests/task026_run_01/`，后者含隔离副本与扫描输出）；
  `allowed_added = 50`、`out_of_scope_added = 0`、`missing = 0`、`read_errors = 0`；
  R5 越界 326 项逐项不变（`drifted = 0`、`gone = 0`）；`scope_compliant = true`。
- 旧 R5 越界 326 项逐项不变、不追认；旧 harness 不列恢复例外。
- 旧回执/旧自检/旧扫描**未覆盖、未重跑**。上一轮两个确切自指元数据按路径单列。

## 8. 待 GPT 裁决

1. 三 API 的**外层键与内部键集**是否与已验收设计一致（含 read/prepare 恰两键、`prepare` 需先解包）；
2. 半写与晚变更的**注入方式**是否可接受（真实实现上的观测接缝 + 保留现场，未替换 writer）；
3. junction 一例因环境特权缺失而**未建立**的登记方式是否可接受；
4. 本卡只实现登记/read/候审请求，Gate1 保存、有效批准核验、标准化/入库与 Gate2 候审留待后续范围。
