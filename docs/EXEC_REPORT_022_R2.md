# TASK-022-R2 执行回执（加载错误与核心证据收尾闭合）

任务：按 `docs/tasks/TASK-022-R2.md`（B 类，DSH 处理）只修 `docs/reviews/REVIEW_TASK_022_R1.md` 的剩余两组阻断；保留 R1 已关闭成果，不推进 Gate1/Gate2 接线。
日期：2026-10-13。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：`STORED_SNAPSHOTS_ONLY` 不变。**未改 P1、正式契约、宿主/控制器或业务文件**；未接宿主/控制器，未生成真实批准/初判/`0009`，未开放 AI/终判。快照保存 ≠ 批次批准 ≠ 运行放行 ≠ 身份认证。

---

## 1. 起点身份与保护基线

| 项 | 值（实读） |
| --- | --- |
| 存储模块（起点） | `7b62e13f78e9ec5ee92887ea8685237e8e2f817d125f520863c3a74f95a1d46e`（40393）✅ |
| 本任务测试（起点） | `9d75b0e6e8ab9660e73fa34dc51103893dedcf8ad1aabde418b520af3d913dbd`（76870）✅ |
| 存储指南（起点） | `a8c4c119eb802fd33107ca7904591cdc83af3efb5858c12c653e8be132609f6f`（15835）✅ |
| 保护基线 | `data/reviews/task022_r1_gpt_20261013_225622/source_hashes_after.json` = `3bedd0fb12c82fb8dc42cf48dc24974c43700773a5190c532a35147623bf66b2`、**135323** 项、同目录 `review_result.json` **verdict=NOT_ACCEPTED**（只排除两个确切自指元数据路径） |
| 冻结件 | P1 `5ccdd0f3…4e79`、正式契约 `174a021b…40ad`、生效登记 `042086cb…061d`、协议 `68c931b3…3e76`、案例 `bd1fc37d…d2a6`、宿主 `38869681…a307`、控制器 `a6b7b8e1…3a8c`（仅实读核对，未导入） |

旧回执/现场、GPT 新评审根与故障根、junction 均**未改一字节**；未执行旧容器脚本、未删除/移动/补签。

---

## 2. 交付文件（写后实读）

| 文件 | 说明 | SHA-256 | 字节 |
| --- | --- | --- | --- |
| `scripts\store_demo_human_gate_decision.py` | 加载错误边界 + 缓存清理 | `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7` | 41353 |
| `tests\test_store_demo_human_gate_decision.py` | 完整 entries 审核、磁盘读回与漂移绑定、输入现场、三时点 | `fa66ac697f24a623fbb06baecf7d72f5ef048616691edc97c4304c7023d17b61` | 93717 |
| `docs\HUMAN_GATE_DECISION_STORE_GUIDE.md` | 能力/收尾同步 | `953ec1008d2584fafe295f0cbad2fa7de8bc80dcf3f0c745f8bec11a75a3cc3f` | 18504 |
| `docs\EXEC_REPORT_022_R2.md` | 本回执 | 自身最终 SHA **只在交接消息给出**（不写回自身） | 11108 |
| `task022r2_run_01`（证据容器 + 记录轮次根） | 正常轮次 | 见 `evidence_ledger.json`（13 项、`missing=[]`/`unregistered=[]`、`core_audit.ok=true`/`api_audit.ok=true`） | — |
| `task022r2_fault_01`（故障脚本）/ `fault_02`（核心载荷缺失）/ `fault_03`（终审字节变更） | 分离故障轮次 | 见 `core_evidence_fault_result.json` / `checks_byte_fault_result.json`（均 `ok=true`） | — |
| `task022r2_dev_01`—`dev_03` | 过程容器（保留不回写） | — | — |

---

## 3. B1 剩余：首次 P1 加载运行错误（逐项关闭）

- `load_frozen_p1_core` 把 spec 建立与 `exec_module` 的**运行/I-O 错误**映射为
  `StoreError("p1_load", reason)` 并保留 cause；**未完整加载的模块从 `sys.modules` 清理且不写入
  `_CORE`**（不作为正常缓存复用）；协议 Blocked 仍为 Blocked，未捕获 `AttributeError` 等程序错误。
- `save` 与 `verify` 都在**错误边界内**先加载冻结核心（`save` 的 `_core()` 已移入 try，stage 初值
  `p1_load`）。
- **定点实测（真实 spec + loader 执行位置注入，命中 1，非真实磁盘损坏）**：
  - G4-06（save）：`StoreError(stage="p1_load")`，原因链含 `OSError`，**未建叶目录**、**无 P1 入口**（入口观察计数不变）；
  - G4-07（verify）：`StoreError(stage="p1_load")`，原因链含 `OSError`，**无 P1 入口**、**不写** failure；
  - G4-08：撤销注入后**新记录仍可正常保存/核验**（验证缓存已清理、未复用半执行模块）。

---

## 4. B3 剩余：完整核心载荷、磁盘与计数共同闭合（逐项关闭）

### 4.1 审核完整 entries（不再只看 ID）

- `_core_audit` 现审核**完整 entries 集合关系**：`entries` / `core_call_ids` / 声明
  `total_core_entries` / **入口代码帧观察数** / API 嵌套清单**五者一致**；每个 entry 的
  `core_call_id` 与 ID 名单匹配；重复 ID、重复 entry、`ids_without_entry`、`entries_without_id`、
  **不完整 entry（空壳：无完整输入或返回/异常）**、API 嵌套缺失/额外一律判失败。
- 隔离实测（在**同轮容器**内）：原登记真实审核通过；只删一个 `core_call_id` 拒绝；**只删一个完整
  entries 成员（保留 ID 名单/声明 total/入口计数）拒绝**；重复 entry 拒绝；空壳 entry 拒绝。

### 4.2 真实磁盘读回与最终字节绑定

- 新增 `_core_audit_from_disk(out_dir, phase="final")`：**同一次读取**得到 `core_call_registry.json`
  的对象与文件 SHA（不再把内存比较命名为“磁盘审核”）。
- 终审改为**有界两轮**：首轮写入最终 checks/failures/summary → 审核完整 entries/API 关系并做**字节
  漂移确认**（与本次终审读数比较）；通过则次轮以最终校验和读数落台账。台账期望**绑定通过漂移确认的
  那次读数**，不再在核心记录被改后重新采集为新期望；失败则形成正式 failure、`summary=FAIL`、返回非零
  并写 `final_audit_diagnostic.json`，**不重建台账**。
- **真实套件故障（分离轮次）**：在**新的最终核心审核调用之前**，从该轮磁盘只删一条完整 entry
  （保留 ID/声明 total/真实入口数）→ 真实审核返回 `ok=false`、`ids_without_entry=["core-026"]`，
  套件**返回 1 / FAIL / failures 非空**，诊断文件保留、现场不恢复。
- **原 checks.json LF 故障路径的必要对照**：新收尾的等价接缝是 `_audited_read`（旧 `_ledger_from_disk(phase="final")`
  已被替换，旧脚本未改动、仅登记为接缝变更）；包装真实 `_audited_read` 在首轮读数后给 `checks.json`
  追加一个 LF → **漂移确认检出 `checks.json`**、套件返回 1 / FAIL / failures 非空。

### 4.3 输入现场与第三时点

- 每次 **verify API 调用开始前**登记初始输入现场：`record_dir`、（存在时）目录文件集合与各文件确切
  大小/SHA；不存在/不可读时记录 `not_available` 与原因，不填空白成功值。
- P1 观察器**保留进入核心的四个真实消费引用**，在调用前、返回后、**API 收尾**三时点复算指纹并登记
  （`input_fingerprints_at_api_finalize`、`third_timepoint_matches`）；不改对象、不再调用核心、不在 I/O
  守卫内落盘。实测：嵌套核心 **26** 条全部三时点一致，API 收尾指纹来自同一保留引用。

---

## 5. 有限更正

`docs/EXEC_REPORT_022.md`（R1 回执）称保存/核验分列为 26/21，**实际为 22/25**（正常 47 与核心 24 不变）。
本轮 `counts.json` 已直接为 `save 22 / verify 25`，新回执按实际登记；**旧回执不回写**。

---

## 6. 实际运行与 scope

```text
.venv\Scripts\python.exe -B tests\test_store_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_store_tests\task022r2_run_01
→ TASK-022-R2 测试组：131 项检查，0 项失败；存储 API 51 次、嵌套核心 26、直接核心 0、
   入口观察 26；读取事件 606、守卫命中 0
→ 退出码 0
```

| 作用域 | 实测 |
| --- | --- |
| 公开存储 API | **51**（save 24 / verify 27；按结果见 `counts.json`） |
| 嵌套真实 P1 / 直接真实 P1 / 入口观察 | **26 / 0 / 26**（五者闭合） |
| 读取 / 写入事件（真实 `io.open`/`os.*`） | **606 / 见 `read_observation.json`**；范围外读取 0 |
| 守卫（socket/子进程） | **0** |
| 台账 | **13 项**逐文件实读一致（期望来自通过漂移确认的终审读数） |
| 故障一（核心完整 entry 缺失） | 返回 **1** / FAIL / failures 非空；`ids_without_entry=["core-026"]` |
| 故障二（终审读数后 checks.json 加 LF） | 返回 **1** / FAIL；漂移检出 `checks.json` |

---

## 7. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task022_r1_gpt_20261013_225622/source_hashes_after.json`（`3bedd0fb…66b2`、
  135323 项、`NOT_ACCEPTED`）；只按两个确切自指元数据路径排除，**无目录前缀豁免**。
- 执行者：正常轮次容器内 `scan_protection.py`（只读项目文件、只写本容器 `protection_result.json`），
  **仅一次**，在三个文件与本回执定稿、正常入口与两个故障验证均完成后执行。

### 7.1 扫描结果与最终身份

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **136491** |
| `changed` | **仅本卡三个被修改文件**：`scripts/store_demo_human_gate_decision.py`（`594e42d0…48e7`）、`tests/test_store_demo_human_gate_decision.py`（`fa66ac69…7b61`）、`docs/HUMAN_GATE_DECISION_STORE_GUIDE.md`（`953ec100…cc3f`）；**范围外变化 0** |
| `missing` / 读取错误 / 范围外新增 | **0 / 0 / 0** |
| 本轮允许新增 | **1168** 项：`docs/EXEC_REPORT_022_R2.md` + 七个 `task022r2_*` 证据容器 + 七个 `task022r2_*` 记录轮次根（确切路径逐项登记，`prefix_exemption_used=false`） |
| 扫描后动作 | 仅对本回执与保护元数据做有限身份登记；未再改实现、未重复全树扫描 |
| junction 现场 | 前轮与 GPT 评审 junction **未删除、未移动**；保护遍历按真实文件系统行为登记 |

---

## 8. 过程问题与未执行

1. 本轮局部运行首两次失败：`G6-02` 仍用旧字段名（`audit_copy_fails`）与 `_core_audit` 的重复 ID
   检测复用了同一 `seen` 集合导致误报 → 均定点修正后通过；现场保留在 `task022r2_dev_01`/`dev_02`。
2. 旧接缝变更（`_ledger_from_disk(phase="final")` → `_audited_read`）已如实登记，旧脚本未改、未执行。
3. 未执行：宿主/控制器接线与调用、Gate1/Gate2 适配器、业务核心与业务历史入口、真实初判、`0009`、
   AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨目录全局历史发现、P1 的 195 次完整入口与协议
   117 例全套——均记 `null`/`not_executed`。
4. 未发现须改 P1/API/schema、正式契约、材料时序、允许根、全局历史或放行边界的事项，未触发 C 类升级。

---

## 9. 绝对路径

- `D:\harness work\audit_sa_project\scripts\store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\tests\test_store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_STORE_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_022_R2.md`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r2_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_records\task022r2_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r2_fault_01\`

---

## 10. 停止点

完成本卡后执行端停止实施并交 GPT 验收；**TASK-022/R1/R2 通过前不制定或实施 Gate1/Gate2 接线**；不生成
真实批准、初判或 `0009`，不开放 AI。人类操作看板并作出业务决定，技术验收不能代签。若发现必须改
P1/API/schema、契约、材料时序、允许根、全局历史或放行边界，**立即停止受影响 B 类处理并报告升级 C 类**。
