# TASK-022-R4 执行回执（规范 JSON 相等判定的最小修正）

任务：按 `docs/tasks/TASK-022-R4.md`（B 类，DSH 处理）修正**唯一剩余阻断**：Python 宽松数值相等被当作既定 canonical JSON 相等；依据 `docs/reviews/REVIEW_TASK_022_R3.md`（NOT_ACCEPTED）。
日期：2026-10-14。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：`STORED_SNAPSHOTS_ONLY` 不变。**只改测试判定与诊断**；**生产存储实现与指南均冻结未改一字节**，未改 P1、正式契约、登记、宿主/控制器或业务文件；未接宿主/控制器，未生成真实批准/初判/`0009`，未开放 AI/终判。快照保存 ≠ 批次批准 ≠ 运行放行 ≠ 身份认证。

---

## 1. 根因

`_field_diff` 叶节点用 Python `expected != candidate` 判等，`_content_compare` 又以“无 field_diff”决定
`equal/ok`。Python 中 `False == 0` 与 `0 == 0.0` **成立**，但既定 canonical JSON（`ensure_ascii=False`、
`sort_keys=True`、`separators=(",",":")`、`allow_nan=False`、UTF-8）中 `false` / `0` / `0.0` **字节不同**。
因此候选规范 SHA 已不同，套件仍可能标 `equal=true` 并返回 0/PASS（评审在真实入口复现：
候选 `a8ff8833…7456` ≠ 预期 `68f0990c…6fcd`，套件仍 **0/PASS**）。

## 2. 主判据与诊断分工（最小修正）

| 角色 | 实现 |
| --- | --- |
| **主判据** | `_canonical_equal(expected, candidate)`：`_canon(expected) == _canon(candidate)`（UTF-8 / `ensure_ascii=False` / `sort_keys=True` / 固定 separators / `allow_nan=False`）。`_content_compare` 对 core/API/权威登记三项 `equal` **一律由规范字节相等决定**，并登记 `primary_criterion="canonical_json_bytes_strict_equal"` 与双方规范 SHA。**不使用 Python `==`/`!=`，也不用“field_diff 为空”代替**；不转换类型、不 strip、不规范化业务字符串。 |
| **诊断（有界）** | `_field_diff` 仅在主判据判不等后定位差异：递归到字段路径（dict 键、list 下标），叶节点用**同一 canonical 比较**并输出 `expected_type`/`candidate_type`/`type_difference`/双方 canonical 片段与 SHA，因此 `False→0`、整数→浮点可定位到具体字段；**不决定忽略真实差异**。键顺序不同但规范字节相同的对象在递归入口即判相等（返回空诊断）。 |

其余不变：完整观察深拷贝预期仍固定于终审前（不读候选磁盘、不刷新、不二次调 P1）；内容错误继续影响
`failures`/`summary`/返回码；已通过的字节漂移逻辑与故障现场保留。

---

## 3. 隔离定点（真实 helper，`isolation_self_tests.json.content_isolation`）

| 情形 | 结果 |
| --- | --- |
| 真实完整原件 | 通过（`original_content_compare_ok=true`） |
| `boundaries.persisted` **False → 整数 0** | **拒绝**，`equal=false`，定位 `core-001: ["result.record.boundaries.persisted"]` |
| `quality_summary.structural_blockers_count` **整数 0 → 浮点 0.0** | **拒绝**，`equal=false`，定位 `core-001: ["result.record.quality_summary.structural_blockers_count"]` |
| 仅**字典键顺序不同**（规范字节相同） | **通过**（`key_order_only_change_accepted=true`，`key_order_canonical_equal=true`） |
| Python 宽松相等对照 | `python_equal_would_miss=true`（`0 == False` 与 `0 == 0.0` 成立，但规范字节不等） |
| 既有控制 | `{}` 替换、合法形状自洽替换、输入改写、删 ID/删完整 entry/重复/空壳 entry **继续拒绝** |

候选记录/ID/计数与关联在上述类型用例中保持不变（`bool_to_int_counts_preserved` /
`int_to_float_counts_preserved`），**真实预期未同步修改**。

## 4. 真实入口类型故障（评审时机）

`task022r4_fault_01/type_change_fault.py` → 套件运行到 `data/human_gate_decision_store_tests/task022r4_fault_02/`
（记录轮次根同名）：在**第一次终审读取之前**（`_audited_read` 包装内），仅把一条真实 returned entry 的
`result.record.boundaries.persisted` 由布尔 `false` 改成整数 `0`，**ID 名单、entry 数、声明 total、入口观察、
API 关联与内存真实观察全部不变**；wrapper 调用**真实 reader** 并返回其原值（不伪造审核返回、不改真实预期）。

| 实测 | 值 |
| --- | --- |
| 注入 | 命中 **1**；`false`/`bool` → `0`/`int`；ID/计数保持（`counts_and_ids_preserved=true`） |
| 套件 | **返回 1**、`summary=FAIL`、failures 非空、`final_audit_diagnostic.json` 保留 |
| 内容比较 | `equal=false`、`primary_criterion=canonical_json_bytes_strict_equal` |
| 规范 SHA | 预期 `bf15239b206b20112cadc80f44011d4abec33d5908a8d9dd947c6102f02cbb4e` ≠ 候选 `9218e2afd912271242c82689709d8bb78b8100d7e0f1658e93fcc38dd3f6c30b` |
| 定位 | `core-001: ["result.record.boundaries.persisted"]` |

harness 九项断言全真（`ok=true`），故障现场**不恢复**。

---

## 5. 正常入口、调用与台账

```text
.venv\Scripts\python.exe -B tests\test_store_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_store_tests\task022r4_run_01
→ TASK-022-R4 测试组：135 项检查，0 项失败；存储 API 51 次、嵌套核心 26、直接核心 0、
   入口观察 26；读取事件 606、守卫命中 0
→ 退出码 0
```

| 项 | 实测 |
| --- | --- |
| 检查项 | **135**（R3 基础 134 项全部保留 + R4 新增 1 项「R4-01 canonical 主判据：False→0 与 整数0→浮点0.0 规范字节不同即拒绝」） |
| 存储 API / 嵌套核心 / 直接 / 入口观察 | **51**（save 24 / verify 27）/ **26** / **0** / **26**（计数闭合） |
| 读取 / 写入 / 守卫 | 606 / 见 `read_observation.json`（范围外读取 0）/ **0** |
| 台账 | **13 项**逐文件实读一致（`missing=[]`/`unregistered=[]`） |
| 内容比较 | `content_compare.ok=true`，core/API/权威登记三项 `equal=true` 且双方规范 SHA 相同（core `f2979ffe…6f42`） |
| 核心/API 审核 | `core_audit.ok=true`、`api_audit.ok=true`（完整 entries 与关系审核保留） |

---

## 6. 交付文件（写后实读）

| 文件 | 说明 | SHA-256 | 字节 |
| --- | --- | --- | --- |
| `tests\test_store_demo_human_gate_decision.py` | 唯一实现改动（`_content_compare`/`_field_diff` 相等判定与诊断 + 定点） | `c5f5fcb95b1f276b437f84a465ed896c82aa0600798163540c806e575bddfec4` | 110305 |
| `docs\EXEC_REPORT_022_R4.md` | 本回执 | 自身最终 SHA **只在交接消息给出**（不写回自身） | 见 §7 登记 |
| `scripts\store_demo_human_gate_decision.py` | **冻结未改** | `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7` | 41353 |
| `docs\HUMAN_GATE_DECISION_STORE_GUIDE.md` | **冻结未改** | `3d3805f42444f3e6f06b3a77e55744dcf9c3849252e105c9f67078067ae2582f` | 20165 |
| `task022r4_run_01` / `task022r4_dev_01`—`dev_02` / `task022r4_fault_01`—`fault_02` | 正常/过程/故障轮次 | 见 `evidence_ledger.json` 与 `type_change_fault_result.json` | — |

**起点身份**：测试起点 `43884b406b1f70293d31d9dadac0b925021e7bc37b36e015b06d4e32fe26d817`（105015）；
保护基线 `data/reviews/task022_r3_gpt_20261014_000920/source_hashes_after.json` =
`e37009b285f37e0065b8c73c28c307efab1be90876b70e60a61b0580cb3cfd41`、**138881** 项、
同目录 `review_result.json` **verdict=NOT_ACCEPTED**（仅两个确切自指元数据路径排除）。

---

## 7. 保护（定稿后一次全树扫描）

- 执行者：正常轮次容器内 `scan_protection.py`（只读项目文件、只写本容器 `protection_result.json`）；
  只按基线清单声明的两个确切自指路径排除，`prefix_exemption_used=false`。

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **139660** |
| `changed` | **恰为 1 项**：`tests/test_store_demo_human_gate_decision.py`（`c5f5fcb9…fec4`）；指南与生产存储**未变** |
| `missing` / 读取错误 / 范围外变化 / 范围外新增 | **0 / 0 / 0 / 0** |
| 本轮允许新增 | **779** 项：`docs/EXEC_REPORT_022_R4.md` + 五个 `task022r4_*` 证据容器 + 四个 `task022r4_*` 记录轮次根（确切路径登记） |
| 冻结身份 | 生产存储 `594e42d0…48e7`、指南 `3d3805f4…582f`、P1 `5ccdd0f3…4e79`、正式契约 `174a021b…40ad`、生效登记 `042086cb…061d`、宿主 `38869681…a307`、控制器 `a6b7b8e1…3a8c` **全部一致**（`mismatch=[]`） |
| 扫描后动作 | 仅对本回执做有限身份登记；**未再改测试**、未重复全树扫描；junction 现场保留未删未移动 |

---

## 8. 过程问题与未执行（如实登记）

1. **保护扫描前两次执行无效（不采纳为证据）**：`scan_protection.py` 由 R3 脚本改写时基线文件夹名替换
   未生效（仍是 R2 基线），两次运行分别报出 `changed` 含指南、范围外新增 2167 项；判定为**脚本生成错误**
   导致的无效运行，已修正基线后重跑一次（§7 数值）；期间一次断言失败未写文件。有效扫描以 §7 为准。
2. 本轮局部运行按 `_canonical_equal` 与类型诊断分步实现，`task022r4_dev_01`（135 项前形态）与
   `dev_02`（含 R4-01 检查）现场均保留。
3. **R3 回执交接 SHA 与实际读取差异**（非阻断，按卡要求只在新回执说明、不改旧回执）：
   `docs/EXEC_REPORT_022_R3.md` 交接时为 11664 字节/`32b004fb…68df8`，其最终实际实读为
   **11766 字节 / `5aa6fc69d951fa68f274a37271eefe1c9dca4f44c52f3a76a33aaca48f2e02ca`**（扫描后追加了
   一行“扫描后动作”登记，未再改测试/指南）。测试、指南与运行证据不受该文档身份差异影响。
4. 未执行：宿主/控制器接线与调用、Gate1/Gate2 适配器、业务核心与历史入口、真实初判、`0009`、AI/终判、
   网络/UI/ERP、强身份认证、真实批次批准、跨目录全局历史发现、P1 195 次完整入口与协议 117 例全套；
   本轮**未单独重跑**已通过的空返回/自洽 reason/checks LF 三个完整故障，也未重跑加载/路径/writer 定点组；
   仅执行证据收尾的定点模式未实现，记 `not_executed: only_r4_mode`（不以默认零通过代替）。
5. 未发现须扩大到生产存储/P1/协议/契约/宿主、改变材料时序或允许根/历史/放行边界的事项，未触发 C 类升级。

---

## 9. 绝对路径

- `D:\harness work\audit_sa_project\tests\test_store_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_022_R4.md`
- `D:\harness work\audit_sa_project\scripts\store_demo_human_gate_decision.py`（冻结未改）
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_STORE_GUIDE.md`（冻结未改）
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r4_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_records\task022r4_run_01\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_store_tests\task022r4_fault_01\`

---

## 10. 停止点

完成本卡后执行端停止实施并交 GPT 验收；**技术验收通过前不推进 Gate1/Gate2**；不生成真实批准、初判或
`0009`，不开放 AI。人类操作看板并作出业务决定，技术验收不能代签。若发现需扩大到生产存储/P1/协议/契约/
宿主、改变材料时序或允许根/历史/放行边界，**立即停止本卡受影响处理并报告重新定界/升级 C 类**。
