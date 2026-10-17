# TASK-022-R1 执行回执（恢复异常、链接路径与观察证据定点修正）

任务：按 `docs/tasks/TASK-022-R1.md`（B 类，DSH 处理）定点修正 `docs/reviews/REVIEW_TASK_022.md` 的三组阻断；依据 TASK-022 已定义的保存/核验协议，不新增 Gate 或证据链设计。
日期：2026-10-13。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：`STORED_SNAPSHOTS_ONLY` 不变。**未改 P1、正式契约、宿主/控制器或业务文件**；未接宿主/控制器，未生成真实批准/初判/`0009`，未开放 AI/终判。**快照保存 ≠ 批次批准 ≠ 运行放行 ≠ 身份认证**；通过前不推进 Gate1 适配器或宿主接线。

---

## 1. 起点身份与保护基线

| 项 | 值（实读） |
| --- | --- |
| 存储模块（起点） | `d6b1bb2fc775e9079e723467bb9eb9c9cba8c9b6d7c8b16d4372bc9560192d9c`（38015）✅ |
| 本任务测试（起点） | `5ab0b35a5efd182a69bc6bde0be718d417556dacaa88d201344007910eacc533`（54793）✅ |
| 存储指南（起点） | `05e725c2a662a86c97eddf370bce5667b993089d0960e214a4adefc53109795b`（13006）✅ |
| 保护基线 | `data/reviews/task022_gpt_20261013_222104/source_hashes_after.json` = `999900f4d778ea79274bf748dd54c21c97d81edb15af87acb66ba4b5db754ec7`、**134314** 项、`verdict=NOT_ACCEPTED`；其声明只排除两个确切自指元数据路径 |
| P1 核心 / 正式契约 / 生效登记（冻结） | `5ccdd0f3…4e79` / `174a021b…40ad` / `042086cb…061d` ✅ |
| 协议 / 案例 / 宿主 / 控制器（冻结，仅实读核对） | `68c931b3…3e76` / `bd1fc37d…d2a6` / `38869681…a307` / `a6b7b8e1…3a8c` ✅ |

旧回执、样本、过程/故障/评审目录（含评审建立的 junction）**未改一字节**；未执行旧容器脚本、未覆盖或清理任何现场。

---

## 2. 交付文件（写后实读）

| 文件 | 说明 | SHA-256 | 字节 |
| --- | --- | --- | --- |
| `scripts\store_demo_human_gate_decision.py` | 存储组件（B1—B3 定点修正） | `7b62e13f78e9ec5ee92887ea8685237e8e2f817d125f520863c3a74f95a1d46e` | 40393 |
| `tests\test_store_demo_human_gate_decision.py` | 测试与证据入口（G1—G6 + R1 定点） | `9d75b0e6e8ab9660e73fa34dc51103893dedcf8ad1aabde418b520af3d913dbd` | 76870 |
| `docs\HUMAN_GATE_DECISION_STORE_GUIDE.md` | 指南（能力/观察/映射同步） | `a8c4c119eb802fd33107ca7904591cdc83af3efb5858c12c653e8be132609f6f` | 15835 |
| `docs\EXEC_REPORT_022_R1.md` | 本回执 | 自身最终 SHA **只在交接消息给出**（不写回自身） | — |
| `data\human_gate_decision_store_tests\task022r1_run_01\` + `data\human_gate_decision_records\task022r1_run_01\` | 正常轮次（13 项载荷台账 + 记录轮次根） | 见 `evidence_ledger.json` | — |
| `task022r1_fault_01\`（故障脚本）与 `task022r1_fault_02\`（故障套件轮次） | 终审字节故障现场（**分离新轮次**，不再使用 `final_audit_fault_suite` 根名） | 见 `final_audit_fault_result.json` | — |
| `task022r1_dev_01`—`dev_03`（证据容器 + 记录轮次根） | 过程容器（保留、不回写） | — | — |

---

## 3. B1：类型拒绝、I/O 映射、失败诊断链（逐项关闭）

- **2.1 先检查再消费**：verify 在读入六份文件后、任何 `.get`/`.items`/摘要派生/嵌套消费之前执行
  `_precheck_parsed_objects`：六份顶层必须为 JSON 对象、`decision_result.json` 必须是**完整两键对象**且
  `record` 为对象。实测评审四例（六文件齐全、JSON 可解析、外层 payload 大小/SHA 已同步）：`[]`／`null`／`7`
  → **`decision_result.json` Blocked**；`materials` 为 `[]` → **`materials.json` Blocked**；未出现原生
  `AttributeError`/`TypeError`/`KeyError`，也未以“捕获全部原生异常”替代检查（完整 P1 schema/矩阵/历史
  校验仍由冻结 P1 承担）。
- **2.2 完整 I/O 错误边界**：目录枚举（`_verify_enumeration`）、初始读取、**末次确认读取**、组件绑定实读
  （`_read_component`）与保存侧 `_readback_check` 全部映射为 `StoreError(stage, reason)` 并保留 cause；
  协议/类型/路径错误仍为 `Blocked`，未因统一映射而降级。实测：真实 reader 初始读取正常、**末次同目标读取**
  抛受控 `OSError`（命中 **1**，此前真实 P1 已执行）→ `StoreError(stage="final_read")` 且原因链含 `OSError`，
  **不写** failure；正常路径仍成功（124/0）。
- **2.3 诊断前原因链已建立**：`save` 的通用 `except` 分支改为**先** `wrapped.__cause__ = exc`，**再**写
  `failure.json`。实测：真实 manifest 完整写入并读回后抛 `RuntimeError` sentinel（真实 P1 = 1、manifest
  存在）→ API `StoreError` 传播链含 `StoreInjectionSentinel`，且磁盘 `failure.json.cause_chain` 同样含
  `StoreInjectionSentinel`（不再是 `[]`）；原半写 `OSError` 仍为 `Error`、保留独占现场、不覆盖不重试；
  诊断自身失败仍保留主异常与诊断错误。

---

## 4. B2：真实路径拒绝（逐项关闭）

- `_resolve_leaf` 改为**先按调用方原始绝对路径逐级检查**（含允许根自身）符号链接/junction/reparse
  （`os.lstat` + `FILE_ATTRIBUTE_REPARSE_POINT`），**再** `resolve()` 核对严格后代关系，并对解析后链路再查一次；
  保存与核验都适用。
- **真实 Windows junction 复现（本轮实际执行）**：在本轮记录根内 `mklink /J junction_alias → junction_target`
  （returncode 0；`lstat` 确认 reparse；`resolve()` 与 target 相等）；先经直接路径正常保存成功，随后：
  - 经 `junction_alias/new_record` 保存 → **Blocked `out_dir`、真实 P1 = 0、target 下未建立记录**；
  - 经 `junction_alias/normal_record` 核验 → **Blocked `out_dir`**，target 目录**逐文件字节不变**；
  - junction 与现场**保留未删除**，未以模拟 `_is_reparse_point=True` 冒充原生路径反例。
- 另：六份载荷必须是**正常文件**（`_verify_file_state` 拒绝链接/reparse 与非文件），未知项/目录/链接不会被
  当作合法载荷读取。

---

## 5. B3：完整真实调用与读取观察（逐项关闭）

### 5.1 三类调用分列闭合

| 作用域 | 实测 |
| --- | --- |
| 公开存储 API | **47**（save 26 / verify 21；returned / blocked / error / unexpected 见 `counts.json`） |
| 其中**嵌套**真实 P1 | **24** |
| 测试**直接**调用真实 P1 | **0**（G1 的对照已改为**观察保存那一次的真实返回**，不再二次调用核心） |
| 核心入口代码帧观察总数 | **24**（= 嵌套 24 + 直接 0，`closure_ok=true`） |

- 旧回执中“嵌套 26”声明**已在 `docs/EXEC_REPORT_022_R1.md` 更正如上**（旧回执不回写）：原 26 = 21 嵌套 + 5 直接。
- 每次真实核心调用均登记：完整四个输入对象快照、**进入核心的真实引用 `id()`**、调用前/返回后指纹、
  完整返回或异常 + 真实 traceback + cause/context 链；`core_call_registry.json` 与 `api_records.json`
  的嵌套清单**按核心调用 ID 双向一致**，且与实际入口观察数闭合。
- 每次存储 API 也保存**完整输入快照**（保存调用：四个输入对象；核验调用：`record_dir` + 初始目录快照），
  拒绝路径同样留完整异常与真实 traceback。
- `decision_result.json` 与**保存那一次**真实核心返回严格规范相等（未二次调用核心冒充第一次返回）。

### 5.2 覆盖实际读取通道

- 观察器新增真实 **`io.open`**（`Path.read_bytes` 使用的通道）并**分读/写**记录：正常入口实测
  **读取事件 416、写入事件 72**（旧版仅有 os.open/write，读取为 0）。
- **G5-08** 逐路径核对：全部读取只落在**本轮记录轮次根**与四项固定组件文件（P1 模块、存储模块、正式契约、
  生效登记），范围外读取 **0**；socket/子进程守卫命中 **0** 保留。
- **末次消费接缝**：保存接缝移至**末次组件绑定读取之后**、最终六文件字节确认之前；核验接缝在唯一一次纯核心
  复算之后、末次实读之前。测试**先无注入观察真实读/写次序**，再注入：保存晚变更 LF → **本次 Blocked
  `submission.json`**（命中 1）；核验晚变更 LF → **本次 Blocked `materials.json`**（命中 1，且**不写**
  failure）；两者均带 `MARK` 次序证据。

### 5.3 正常收尾与故障支配

- 台账 13 项逐文件实读一致（`missing=[]`、`unregistered=[]`）；存储 API 与核心调用登记分别与记录**双向审核**
  并**磁盘读回**复核。
- **删审核副本一条真实核心调用登记**（`core-024`）→ 由真实 audit 判定失败，原件通过（另保留删一条存储 API
  登记的隔离与文件台账隔离，三者作用区分）。
- **分离的新终审故障轮次**：故障脚本位于 `task022r1_fault_01/`，套件运行到 `task022r1_fault_02/`
  （记录轮次根 `task022r1_fault_02/`），注入命中 1、终审检测到 `checks.json`、**返回码 1**、`summary=FAIL`、
  failures 非空、现场保留。
- 未执行动作写 `null`/`not_executed`（宿主/控制器、业务核心、Gate 适配器、AI/终判、真实初判、子进程内部次数）。

---

## 6. 有限同步事项（§5）

- `component_bindings` 生产运行**恰四项**（P1、本存储模块、正式契约、生效登记）；协议/案例/宿主/控制器的
  冻结身份已**移至测试/保护层**独立核对（`test_frozen_identities.json`，实测全部相符），不再因后续宿主接线
  改变代码而阻断新快照。四项 manifest schema、P1 `run_binding` 语义与契约预期不变。
- `os.open` 的 `O_CREAT|O_EXCL|O_BINARY` + 显式字节写入保持（未因表面 API 名称改写 writer）。
- 旧临时删除/看板补建/固定故障根命名偏差**仅登记**，未补跑、未清理；本轮新轮次统一 `task022r1_<唯一名>` 命名。

---

## 7. 实际运行、计数与 scope

**正常入口（全新轮次）**：

```text
.venv\Scripts\python.exe -B tests\test_store_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_store_tests\task022r1_run_01
→ TASK-022-R1 测试组：124 项检查，0 项失败；存储 API 47 次、嵌套核心 24、直接核心 0、入口观察 24；
   读取事件 416、守卫命中 0
→ 退出码 0
```

**故障验证**：`task022r1_fault_01/final_audit_fault.py` → 套件返回码 **1**、`summary=FAIL`、注入命中 1、
终审 `missing=["checks.json"]`、failures 非空（五项断言全真）。

---

## 8. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task022_gpt_20261013_222104/source_hashes_after.json`（`999900f4…4ec7`、134314 项、
  `verdict=NOT_ACCEPTED`）；只按两个确切自指元数据路径排除，**未按 reviews/records 目录前缀豁免**。
- 执行者：正常轮次容器内 `scan_protection.py`（只读项目文件、只写本容器 `protection_result.json`），**仅一次**，
  在三个交付文件与本回执定稿、正常入口与故障验证均完成后执行。
- 结果见 §8.1（扫描后有限登记）。

### 8.1 扫描结果

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **135075** |
| `changed` | **仅 3 个本轮被修改文件**：`scripts/store_demo_human_gate_decision.py`（`7b62e13f…d46e`）、`tests/test_store_demo_human_gate_decision.py`（`9d75b0e6…3dbd`）、`docs/HUMAN_GATE_DECISION_STORE_GUIDE.md`（`a8c4c119…9f6f`）；**范围外变化 0** |
| `missing` / 读取错误 / 范围外新增 | **0 / 0 / 0** |
| 本轮允许新增 | **761** 项：`docs/EXEC_REPORT_022_R1.md` + 六个 `task022r1_*` 证据容器 + 五个 `task022r1_*` 记录轮次根（确切路径逐项登记，`prefix_exemption_used=false`） |
| 扫描后动作 | 仅对本回执与保护元数据做有限身份登记；未再改实现、未重复全树扫描 |
| junction 现场 | 本轮 junction（`task022r1_run_01` 记录根内 alias→target）保留未删除；保护遍历按真实文件系统行为登记，未递归移动 |

---

## 9. 过程问题与未执行

1. **过程失败（如实登记）**：本轮首两次局部运行分别出现字段名不一致（`nested_p1_calls_observed`）与
   G1-04 期望构造未重算材料指纹导致的 1 项失败，均**定点修正**后通过；失败现场保留在
   `task022r1_dev_01`/`task022r1_dev_02`。
2. **旧偏差**：冒烟临时删除、看板补建、固定故障根命名（`final_audit_fault_suite`）仅登记，不回写、不补跑；
   本轮不使用固定故障根名。
3. **未执行**：宿主/控制器接线与调用、Gate1/Gate2 适配器、业务核心与业务历史入口、真实初判、`0009`、
   AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨目录全局历史发现、P1 的 195 次完整入口与协议 117 例全套。

---

## 10. 绝对路径

- `D:\harness work\audit_sa_project\scripts\store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\tests\test_store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_STORE_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_022_R1.md`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r1_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_records\task022r1_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r1_fault_01\`

---

## 11. 停止点

完成本卡后执行端停止本轮实施并交 GPT 验收；**TASK-022 通过前不制定或实施 Gate1/Gate2 接线**。不生成真实批准、
初判或 `0009`，不开放 AI。人类操作看板并作出业务决定，技术验收不能代签。若发现还须改 P1/API/schema、
正式契约、材料时序、允许根、全局历史范围或运行放行边界，**立即停止受影响 B 类处理并报告升级 C 类**。
