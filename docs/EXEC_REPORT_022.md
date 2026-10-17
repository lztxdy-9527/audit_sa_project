# TASK-022 执行回执（P2-S1 独立 Gate 决定快照保存与只读恢复核验）

任务：按 `docs/tasks/TASK-022_DRAFT.md`（C 类，GPT 设计 + DSH 执行）新增独立存储组件；依据 `docs/reviews/REVIEW_TASK_021_R2.md`（整体验收 ACCEPTED）。
日期：2026-10-13。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：本卡范围 **`STORED_SNAPSHOTS_ONLY`**——只验证**已提供快照**的内部关系与实际存储字节；不发现全局历史、不实读业务材料/工作簿/DB、不证明材料清单完备或来源真实。**快照保存 ≠ 批次批准 ≠ 运行放行 ≠ 身份认证**；真实批准仍 `null`、真实初判未保存、`next=false`、AI 未开放；宿主/控制器接线与 Gate1/Gate2 适配器**不在本卡范围**（后续分卡验收）。

---

## 1. 起点身份、冻结件与保护基线

| 项 | 值（实读） |
| --- | --- |
| 保护基线 | `data/reviews/task021_r2_gpt_20261013_214052/source_hashes_after.json` = `6241c96ba724e8a38696f46c16cf1edf0fab071229895950dc235f4325f07ba7`、**133682** 项；同目录 `review_result.json` **verdict=ACCEPTED**；其声明只按两个确切元数据路径自指排除（`review_result.json`、`source_hashes_after.json`），未按目录前缀豁免 |
| P1 核心 | `5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79`（53584）✅ |
| P1 测试 | `472586942f9822bd249385a88607a90c5dbcf9db54730b1ea5c18296be9885a8`（111931）✅ |
| P1 指南 | `9345baf16297dd53a7bfeb83d5392697c08b86f11d34504f78f068546fffd980`（20780）✅ |
| 正式契约 | `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`（13289）✅ |
| 生效登记 | `042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d`（3195）✅ |
| 协议 / 案例 | `68c931b3…3e76`（39298）／`bd1fc37d…d2a6`（43060）✅ |
| 宿主 / 控制器（只实读校验身份，**不导入**） | `scripts/run_demo_workflow.py` = `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307`；`scripts/control_demo_workflow.py` = `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c` ✅ |

**未修改任何既有文件**（保护扫描 `changed=[]` 证明）；不创建 Git、不安装依赖、不建 batches/SQLite/审阅包。正式契约生效时间按其原文登记；未用 Gate 决定的时间语法否定契约生效，未生成新确认、未修改任何人类文件。

---

## 2. 交付文件（写后实读）

| 文件 | 说明 | SHA-256 | 字节 |
| --- | --- | --- | --- |
| `scripts\store_demo_human_gate_decision.py` | 独立存储组件（仅标准库；无 CLI） | `d6b1bb2fc775e9079e723467bb9eb9c9cba8c9b6d7c8b16d4372bc9560192d9c` | 38015 |
| `tests\test_store_demo_human_gate_decision.py` | 测试与证据入口（G1—G6） | `5ab0b35a5efd182a69bc6bde0be718d417556dacaa88d201344007910eacc533` | 54793 |
| `docs\HUMAN_GATE_DECISION_STORE_GUIDE.md` | 六文件协议/保真范围/只读核验/版本策略/未完成职责 | `05e725c2a662a86c97eddf370bce5667b993089d0960e214a4adefc53109795b` | 13006 |
| `docs\EXEC_REPORT_022.md` | 本回执 | 自身最终 SHA **只在交接消息给出**（不写回自身） | — |
| `data\human_gate_decision_store_tests\task022_run_01\` | 正常证据容器（10 项载荷台账 + 保护脚本/结果） | 见 `evidence_ledger.json`（`entry_count=10`） | — |
| `data\human_gate_decision_records\task022_run_01\` | 正常记录轮次根（22 个记录叶目录、125 文件） | 见 `store_inventory.json` | — |
| `data\human_gate_decision_store_tests\task022_fault_01\`、`data\human_gate_decision_records\final_audit_fault_suite\` | 终审字节故障现场（与正常分开、保留不清理） | 见 `final_audit_fault_result.json` | — |
| `task022_dev_01`、`task022_dev_02`（证据容器 + 记录轮次根） | 过程容器（保留、不回写） | — | — |

---

## 3. 组件实现要点（§3—§7 对应）

- **公开 API（无 CLI）**：`save_human_gate_decision_snapshots(out_dir, submission, materials, expectations, *, prior_history=None)` 与 `verify_human_gate_decision_snapshots(record_dir)`；成功返回**恰八键**，三个 `false` 严格布尔；异常为 `HumanGateDecisionStoreBlocked(field, reason)` 与 `HumanGateDecisionStoreError(stage, reason)`，P1 的 Blocked **保留实际 field/reason**、P1 的 Error **保留 cause 链**。
- **目录与六文件**：只接受解析后 `data/human_gate_decision_records/` 的**严格后代**，拒绝等于根/越界/既有目标（含空目录）/符号链接与 Windows reparse；逐级检查祖先、`os.mkdir` **独占建立**叶目录；成功叶目录**恰六份**文件（子目录/未知文件/failure 即拒绝）。
- **字节协议**：P1 canonical JSON + **一个 LF**、UTF-8 无 BOM、字节先构造再以**真实 `O_CREAT|O_EXCL`** 独占写入；逐文件读回核对长度/SHA/对象相等；`manifest.json` **最后写入**且不内嵌自身哈希；P1 record **原样**保存（17 键、`note`、六项 `boundaries` 含 `persisted=false`）。
- **manifest 封闭协议**：版本常量 `TASK-022-human-gate-decision-store-manifest-1.0`、顶层**恰八键**；`identity` 与 submission/materials/expectations（`expected_batch_id`/`expected_gate`）/`decision_result.record` 精确闭合；`component_bindings` 四项来自固定项目路径**真实文件实读**（并核对 §2 全部冻结身份，含协议/案例/宿主/控制器，**只读不导入**）；`fingerprints` 六项沿用 P1 算法（`materials_body_fingerprint` 用 P1 的 `materials_body`）；`payloads` 五项按 relative UTF-8 升序且逐项 `{relative, byte_size, file_sha256}`；`boundaries` 五项严格 `false`；全层拒绝未知/缺失键、非严格类型、非全串 64hex。
- **保存顺序**：路径/绑定 → 独立快照（保留真实消费引用）→ **恰一次**真实 P1（`prior_history=None` 交给真实 P1 拒绝，不默认空历史；P1 拒绝**不建叶目录**）→ 输入指纹前后不变 → 构造待写缓冲 → 独占建叶目录 → 独占写五份 payload + 读回 → 独占写 manifest + 读回 → 组件绑定复测 → **最终六文件字节确认** → 返回成功。
- **失败现场**：叶目录建立后的任何失败只在该新目录独占写 `failure.json`（版本 `TASK-022-human-gate-decision-store-failure-1.0`、阶段、Blocked/Error 分类、`field`（无则 `null`）、`reason`、完整 cause/context 链），不覆盖既有诊断、不删半写文件、不重试凑成功；诊断写入失败保留原异常并记录诊断错误。
- **只读核验**：路径/无 failure/固定集合 → **同一缓冲**绑定长度/SHA 与解析对象 → manifest 全封闭 schema + payloads 字节闭合 + 六项指纹复算 + 身份闭合 + 组件绑定与当前真实组件一致 → 从四份已绑定快照**恰一次**调用同一冻结 P1 并严格比较两键对象/记录指纹/输入未变 → 再次实读六文件比较 → 返回成功；**全程不写任何文件**。
- **版本策略**：只有当前组件字节与固定正式契约一致的记录可按本版本恢复；版本/文件身份变化**如实阻断**，不迁移、不补签、不重写。

---

## 4. 实际运行、计数与 scope

**正常控制（全新容器）**：

```text
.venv\Scripts\python.exe -B tests\test_store_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_store_tests\task022_run_01
→ TASK-022 测试组：106 项检查，0 项失败；存储 API 38 次、真实 P1 入口观察 26 次；守卫命中 0
→ 退出码 0
```

| 计数项 | 值 |
| --- | --- |
| 公开存储 API 调用 | **38**（save 19 / verify 19；returned 12 / blocked 24 / error 2 / **unexpected 0**） |
| 嵌套**真实 P1 入口观察**（`sys.setprofile` 于冻结核心入口代码帧） | **26**（保存成功路径 7、核验成功路径 5、其余为 P1 拒绝或故障路径） |
| 两者关系 | **分列报告、不要求相等**；提前路径拒绝时真实 P1 = **0** |
| 守卫（socket/subprocess）命中 | **0** |
| 记录叶目录 / 记录文件 | 22 / 125 |
| checks / failures | **106 / 0** |
| 台账 | 10 项载荷逐文件实读一致（`missing=[]`、`unregistered=[]`） |

**scope 分列**：存储 API 次数、嵌套真实 P1 次数、测试运行器进程作用域分别记录；未观察子进程内部次数写 `null`；业务核心/宿主/控制器调用为 **0**（未导入：AST 检查存储模块导入集合 = 标准库；`sys.modules` 无宿主/控制器/业务模块；I/O 观察显示只读取本轮记录目录与固定组件文件）。

**G1—G6 实测摘要**：

| 组 | 结果 |
| --- | --- |
| G1 正常与确定性 | Gate1 OK 的 APPROVE/HOLD/REJECT、Gate1 BLOCKED HOLD、Gate2 APPROVE 五组控制各保存+核验成功；`decision_result.json` 与真实 P1 完整两键返回**规范相等**；六项指纹独立复算一致；双目录**逐文件相同字节**；输入引用前后不变 |
| G2 前提与路径 | 已有叶目录/已有空目录/越界/根自身**均拒绝且旧文件不变**；空白 reason、模拟 `actor_kind`、BLOCKED+APPROVE、`prior_history=None`（与省略等价）**由真实 P1 拒绝且不建叶目录**；同路径二次保存被拒、不覆盖 |
| G3 恢复负向与只读 | 10 例（payload 字节、manifest SHA 加 LF、`byte_size=true`、未知项、遗漏/重复/越界名单、`failure.json`、跨文件 batch 矛盾、**同步外层 payload SHA 与对象指纹后使内层提交绑定矛盾**）全部**可定位拒绝**且核验前后目录**逐文件不变**；其中内层矛盾一例由关系核验/真实 P1 拒绝（非旧外层哈希提前拒绝） |
| G4 真实 writer 与晚变更 | 半写 `OSError`（真实 `os.write` 命中 1）→ Error + 完整链 + 现场 `failure.json`（阶段 `payload_write`）+ 核验拒绝 + 既有记录不受影响；manifest 完整写入读回后 sentinel → Error（阶段 `manifest_write`）+ 现场 + 核验拒绝；保存/核验“末次消费后追加 LF”→ **本次** Blocked 且分别指出 `submission.json`／`materials.json`，命中 1，核验反例**不写** failure |
| G5 边界与观察 | 见上表；记录 `boundaries` 原样、外层不放行、无 `0009`/真实初判/AI；夹具标识 `PROTOCOL_TEST_FIXTURE_ONLY` **未进入** P1 封闭 schema |
| G6 证据收尾与保护 | 台账逐项实读一致；权威登记隔离删 `call-038` 由**真实 audit 失败**、原件通过；文件台账隔离调用真实 audit（副本 `unregistered=['checks.json']`）；磁盘读回双向一致；**分离的终审故障现场**：注入命中 1、终审发现 `checks.json`、**返回码 1**、`summary=FAIL`、failures 非空（正常入口 0/106/0 分列留证） |

---

## 5. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task021_r2_gpt_20261013_214052/source_hashes_after.json`（`6241c96b…ba7`、133682 项、`verdict=ACCEPTED`），其声明的两个元数据路径自指排除；**未使用旧基线、未按目录前缀豁免**。
- 执行者：正常容器内 `scan_protection.py`（只读项目文件、只写本容器 `protection_result.json`），**仅一次**，在组件/测试/指南/回执齐备、正常入口与故障验证均完成后执行。
- 结果：实扫 **134235** 文件 → **changed=[]（未修改任何既有文件）**、**missing=0、读取错误=0、范围外新增 0**；新增允许 **553** 项按四个交付文件 + 本卡显式列出的容器/记录轮次根（8 个确切根路径）逐项登记，`prefix_exemption_used=false`。
- 扫描后只有限登记（本节与本回执身份），**未再修改**组件/测试/指南。

---

## 6. 过程失败与偏差

1. **局部迭代**：首次局部运行 106 项检查 / 1 失败——`G5-05` 用子串匹配源码导致把刻意写出的宿主/控制器**文件路径常量**误判为导入；改为 **AST 导入集合**检查（只允许标准库）后通过。该失败现场保留在 `task022_dev_01`。
2. **临时冒烟数据清理（如实披露）**：接口冒烟阶段曾在 `data/human_gate_decision_records/task022_smoke_01/` 下生成临时记录，冒烟通过后**由执行端删除**（属本卡临时数据，不含任何既有文件或凭证）；该轮次根与临时脚本均不进入本轮产物登记。
3. 早前轮次的流程偏差（R1 两次扫描与看板补建顺序、R2 看板补建顺序）按卡**仅登记、不回归、不清理**；本轮看板卡在依据任务卡完成实现后补建（顺序偏离，如实登记）。
4. 未发现需要修改冻结 P1/正式契约/宿主、改变决定矩阵/身份/材料时序或扩大历史发现范围的事项；B/C 类授权范围未被自行扩大。

---

## 7. 未执行事项

宿主/控制器接线与调用、Gate1/Gate2 适配器（本批材料实读、完整历史枚举）、业务核心与业务历史入口、真实初判、`0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨目录全局历史发现、子进程内部次数观察——均在证据中记为 `null`/`not_executed`；未重跑 P1 的 195 次完整入口与协议 117 例全套，未运行旧文档工具或旧容器脚本。

---

## 8. 绝对路径

- `D:\harness work\audit_sa_project\scripts\store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\tests\test_store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_STORE_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_022.md`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_records\task022_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022_fault_01\`

---

## 9. 停止点

执行端完成本卡后停止实施并交 GPT 验收；**通过后由 GPT 按持续授权制定下一卡**。不接宿主/控制器，不生成真实 Gate 批准、真实初判或 `0009`，不开放 AI 或终判；人类操作看板，技术验收不能代替真实批准。若发现需要修改冻结 P1/正式契约/宿主、改变决定矩阵/身份/材料时序或扩大历史发现范围，**立即停止受影响实施、保留现场并向 GPT 报告新设计范围**。
