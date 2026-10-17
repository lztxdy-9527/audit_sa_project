# TASK-021 执行回执（P1 独立纯内存 Gate 决定记录核心）

任务：按 `docs/tasks/TASK-021_DRAFT.md` 实现 P1 纯内存核心；依据 `docs/reviews/REVIEW_TASK_020_R3.md`（整体验收 **ACCEPTED**）。
日期：2026-10-13。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与批次批准：人类主理人。
状态：四个交付文件已定稿，最终完整入口在**全新容器**通过；全树保护扫描见 §6。

**边界重申**：本卡成功止于 **`HUMAN_GATE_DECISION_MEMORY_VALIDATED`** 的纯内存结果——**返回内存记录 ≠ 已保存 ≠ 身份认证 ≠ 批次批准 ≠ 运行放行**。无持久化/恢复/独占保存/失败现场文件协议，无宿主/控制器接线，不新增 `0009`，不填写或修改真实批准/初判/`next`/AI/终判，不接 UI/LLM/网络/ERP/真实数据。宿主仍止于模拟 `0008`；真实批准 `null`、真实初判未保存、`next=false`、AI 未开放；正式契约生效与 D2 建设许可**均不批准任一批次**。

---

## 1. 任务开始实读核验的输入身份

| 输入 | 期望 | 实读结果 |
| --- | --- | --- |
| `docs/AUDIT_CONTRACT.md` | `174a021b…40ad`，13289 字节，V1/已生效 | ✅ 一致（13289 字节） |
| `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md` | `042086cb…061d` | ✅ 一致（3195 字节） |
| `docs/decisions/REAL_FLOW_DECISIONS_20261013.md` | `bface683…35e4` | ✅ 一致（4100 字节） |
| `docs/proposals/HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md` | `68c931b3…3e76`，39298 字节 | ✅ 一致（39298 字节） |
| `docs/proposals/HUMAN_GATE_DECISION_CASES_V1_DRAFT.md` | `bd1fc37d…d2a6`，43060 字节 | ✅ 一致（43060 字节） |
| 保护基线 `data/reviews/task020_r3_gpt_20261013_193016/` | `review_result.json` 的 `verdict=ACCEPTED` | ✅ `verdict=ACCEPTED`；`source_hashes_after.json` = `cb90782134bdf5763ab5aa0d2a7ae4d916ced33b654a620e0ea9988b0bc27047`、**133396** 项 |

未运行旧辅助脚本；未回写任何冻结文件。协议旧标题/"尚未验收"标记保留交付快照语义。

---

## 2. 交付文件（写后实读）

| 文件 | 说明 | SHA-256 | 字节 |
| --- | --- | --- | --- |
| `scripts\build_demo_human_gate_decision.py` | 纯内存核心（仅标准库） | `1355dce0b22a90dbe1d1d08bb05c49a6d5e76c2c6b21d15a8ae6b512463d6a68` | 44307 |
| `tests\test_build_demo_human_gate_decision.py` | 测试与证据入口 | `f7a6c8c8a073a891c2505c69a09409e2e1f5739eebc1156d34d2ee55ac67b02b` | 65762 |
| `docs\HUMAN_GATE_DECISION_GUIDE.md` | 接口/语义/能力限制/验证方式 | `5a753b15c0ca378cb07b4e2fb7e782fed7b2944dc7f2cad599c8bd5f6ce50caa` | 15225 |
| `docs\EXEC_REPORT_021.md` | 本回执 | 自身最终 SHA **只在交接消息给出**（不写回自身） | — |
| `data\human_gate_decision_tests\task021_run_01\` | 最终证据容器（含 `scan_protection.py` 与 `protection_result.json`） | 见 `evidence_ledger.json` 与 §6 | — |

**未修改任何既有文件**；未创建 `AGENTS.md`/正式批准/生效/运行配置/持久化目录/迁移脚本；未新增依赖；未初始化 Git。

---

## 3. 核心实现（按冻结协议 §3—§14）

- **唯一业务入口**：`build_human_gate_decision_record(submission, materials, expectations, *, prior_history=None) -> dict`；成功外层**恰两键** `{"record", "record_fingerprint"}`；`record` **17 键**、不内嵌自身指纹。
- **异常**：`HumanGateDecisionBlocked(field, reason)`（协议/类型/绑定/前提，均可定位）与 `HumanGateDecisionError(stage, reason)`（`raise ... from exc` 保留 `__cause__`；实测注入验证见 §4）。
- **14 步固定顺序**：第 1—4 步形状/类型/常量/键集合/列表规则（含时间字段**类型**、`contract_effective` 类型与 `true`、按 Gate 的前序字段形状、`records` 唯一/升序）；第 5—12 步值/关系（身份→时间语义→契约→运行绑定→材料正文复算→名单双向比较→前序 11a—11i→历史与重复事件）；第 13 步质量矩阵；第 14 步构建。
- **材料正文唯一算法**：仅删除顶层 `materials_fingerprint`；四者精确相等；`files` 与 `expected_files` 双向完整比较后再逐项比较文件 SHA。
- **前序闭合 11a—11i**：wrapper 形状/常量 → 记录键集合/常量/枚举/`note` → **记录正文复算** → 身份（GATE1/同批次/APPROVE/HUMAN_DECLARED）→ 契约一致 → **11f 前序运行绑定与本次材料及独立预期六字段全等**（`expected_prior_gate1.run_binding` 作为独立前序预期同样参与比较）→ 质量与固定 `false` 边界 → 三处指纹与 `gate/batch_id/event_id` 闭合 → 历史含同一 wrapper。
- **时间**：恰好两种写法、全串匹配、真实日历/闰年、分量与偏移至 ±14:00、原文保存、不补时间/不生成 normalized。
- **质量矩阵**：`OK` 三决定可记录；`BLOCKED` 下 APPROVE 拒绝、HOLD/REJECT 记录且 `execution_allowed=false`；`FAILED` 三决定拒绝、不产生成功记录；矛盾状态第 2 步拒绝；计数由真实列表长度派生。
- **纯内存/保真**：仅标准库；不读写文件/库/网络、不调子进程、不依赖时间/随机/环境/可变全局状态；四入参调用前后不变；返回与入参无共享可变别名；同输入同输出；canonical JSON 口径固定为 UTF-8/`ensure_ascii=False`/`sort_keys=True`/`separators=(",",":")`/`allow_nan=False`。
- **能力边界（指南 §9 明示）**：不实读磁盘、不核验契约生效、不证明来源与身份、**不能发现调用方两侧同时少报的材料文件**、不覆盖声明范围之外的隐藏历史。

---

## 4. 实际运行与计数（§5/§6）

真实运行命令与结果：

```text
.venv\Scripts\python.exe -B tests\test_build_demo_human_gate_decision.py \
    --out-dir data\human_gate_decision_tests\task021_run_01
→ TASK-021 测试组：267 项检查，0 项失败；核心调用 132 次；守卫命中 0
→ 退出码 0
```

| 计数项 | 值 |
| --- | --- |
| 核心公开入口调用总数（`call_registry.json` 权威登记） | **132** |
| 按结果 | `returned=27`、`blocked=104`、`error=1`（受控注入）、`unexpected=0` |
| 按类别 | `normal=125`、`prior_prep=1`、`determinism=2`、`no_alias=2`、`injection=1`、`guard=1` |
| 设计案例映射 | **117 / 117**（`case_map.json`：设计案例→实际调用→断言/结果；允许合并或拆分，例：C-103→C-08 调用、C-104→C-07、C-97→C-91、C-11/C-108→确定性两次调用） |
| 守卫命中（`builtins.open`/`os.open`/`socket.socket`/`subprocess.Popen`） | **0** |
| 测试运行器进程 | 不计入核心调用数（证据中单列说明） |
| checks / failures | `267` / `0` |

**独立比对**：期望值由测试脚本**自实现**的 canonical JSON/指纹与**冻结案例正文**两块 JSON 推导（不调用被测核心的同一 helper）：BASE1 材料 `5f0299e1…f739`、BASE2 材料 `ce95ec25…c45e`、`record1` `15bebb48…8c19`；核心对 BASE1 的输出记录与正文 `record1` **规范（canonical）相等**、指纹一致；Gate2 的完整期望对象亦由测试独立推导（逐字段比较，不只检查状态/摘要）。C-112—C-115 用 R3 正确顺序（**先材料、后记录**）自行构造快照，实际拒绝字段分别为各自 11f 目标（`…run_binding.code.file_sha256` / `rules.manifest_fingerprint` / `config.file_sha256` / `input.file_sha256`），C-116 同版本对照成功；与 R3 证据 JSON **只读交叉**一致（未导入/运行旧构造器）。

**受控内部注入（明确标注）**：仅替换核心私有函数 `_build_and_validate` 为抛 `ValueError("controlled-injection")` 的实现，调用仍从**公开边界**进入 → 实测 `HumanGateDecisionError(stage="internal")` 且 `__cause__` 链为 `ValueError`；与协议 Blocked 分列。**台账隔离自测**：删审核副本一条登记即必须失败、原件仍通过（`ledger_isolation_self_test.json`）。

**未执行项**：receiver/checker 链、宿主/控制器、持久化/重放、AI/终判、TASK-002—020 历史业务链均记 `not_executed`/`null`（不沿用历史模板填 0）。

---

## 5. 失败过程（如实登记）

| 容器 | 用途 | 结果 |
| --- | --- | --- |
| `task021_dev_01` | 首次局部运行 | 265 项检查、**5 项失败**（保留） |
| `task021_dev_02` | 修正后局部运行 | 265/0，但设计案例映射仅 108/117（保留） |
| `task021_dev_03` | 补映射覆盖 | 267 项检查、**1 项失败**（C-11 未映射；保留） |
| `task021_dev_04` | 覆盖齐全 | 267/0（保留） |
| `task021_run_01` | **最终完整入口** | 267/0，退出码 0 |

失败与修正（均由局部运行发现、定点修复，未改协议/案例）：

1. **C-36 缺省省略 prior_history 被错误地"通过"**：测试登记器总是传 `prior_history`。修正为支持"省略该关键字"的调用形态 → 实际拒绝 `field="prior_history"`。
2. **C-58 files 额外项被错误地"通过"**：测试在材料侧加了额外文件后把独立名单也同步了。修正为**不同步**独立名单（额外项在第 10 步暴露 `materials.files[extra/x.json]`）。
3. **C-61 错 Gate 的步号**：核心原先按 `expectations.expected_gate` 判定第 3 步的前序字段形状，导致先在第 3 步拒绝。按协议"按 Gate 规定的形状"以 **submission.gate** 为准（第 5 步再报两者不一致）→ 实际拒绝 `expectations.expected_gate`（第 5 步），与设计案例一致。
4. **C-80 的字段粒度**：`{"phase": …}` 对象按协议 §3.5"未知键给完整路径"报 `submission.prior_decision_binding.phase`（第 1 步）；设计案例文字写的是 `submission.prior_decision_binding`。此处**保持协议 §3.5 的精确路径**（步号相同），并在测试与指南中说明该粒度差异，不倒换顺序。
5. **C-82 的构造位置**：Gate2 基线上构造会先在第 11i 步因历史缺前序而拒绝，改为在 Gate1 基线上构造 → 实际拒绝 `submission.event_id`（第 12 步）。
6. **设计案例映射覆盖**：首轮仅 108/117，补齐 C-11/C-97/C-103/C-104/C-106/C-107/C-108/C-110/C-111 的别名与特殊调用登记 → 117/117。
7. 核心实现过程中另修正一处内部缺陷（运行绑定比较的路径展开写成嵌套元组导致 `KeyError`）：该次调用被 `HumanGateDecisionError` 正确捕获并保留原因链——这同时验证了异常映射，但属**实现自检过程中的真实内部错误**，在此如实登记。

---

## 6. 保护（定稿后一次全树扫描）

- 基线：`data/reviews/task020_r3_gpt_20261013_193016/source_hashes_after.json`（`cb907821…7047`、133396 项、同目录 `review_result.json` 的 `verdict=ACCEPTED`）。
- 扫描执行者：证据容器内 `scan_protection.py`（只读项目文件、只写 `protection_result.json`）；**仅执行一次**，在核心/测试/指南/回执定稿且最终完整入口通过之后。
- 结果：见 §6.1（扫描数值于扫描后有限登记）。

### 6.1 扫描结果

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **133463** |
| `changed` | **[]（空）**——既有文件无一被修改 |
| `missing` | **[]** |
| 读取错误 | **0** |
| 本轮允许新增 | **65** 项：四个交付文件（`scripts/build_demo_human_gate_decision.py`、`tests/test_build_demo_human_gate_decision.py`、`docs/HUMAN_GATE_DECISION_GUIDE.md`、`docs/EXEC_REPORT_021.md`）+ `data/human_gate_decision_tests/task021_*` 五个容器共 61 个文件（`task021_run_01` 13 个、`dev_01`—`dev_04` 各 12 个），逐项登记 |
| 范围外新增 | **0** |
| 基线自身与同目录 `review_result.json` | 未纳入清单，按**两个确切路径**单列；**未豁免整个 reviews 目录** |
| 扫描后动作 | 仅对本回执做**有限身份登记**（写入本节扫描数值与文件身份）；**未再修改核心/测试/指南**，未再全树扫描 |

---

## 7. 过程问题与说明

1. **两处字段粒度/构造位置的偏离已在 §5 说明**（C-80 采用协议 §3.5 的完整路径；C-82 改在 Gate1 基线上构造），均**未改协议、未改案例、未倒换检查顺序**。
2. 过程容器（`task021_dev_01`—`dev_04`）按卡要求**保留、未回写**；最终容器 `task021_run_01` 为定稿后的完整入口。
3. 测试脚本自身含 CLI 与文件写入（证据落盘），这属测试层；**核心无 CLI、无文件保存、无恢复/放行入口**。
4. 期望值对比采用"测试自实现 canonical/指纹 + 冻结正文展开"，未使用核心的 helper 自比；未把案例期望称为"已运行测试"——117 个设计案例是**设计期望**，本轮实际执行的是本卡测试入口的 132 次核心调用与 267 项检查。
5. 未宣称"纯内存 VALIDATED 已保存真实决定"：核心结果只表示内存校验通过。

---

## 8. 绝对路径

- `D:\harness work\audit_sa_project\scripts\build_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\tests\test_build_demo_human_gate_decision.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE_DECISION_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_021.md`
- `D:\harness work\audit_sa_project\data\human_gate_decision_tests\task021_run_01\`（最终证据容器）

---

## 9. 停止点与下一阶段

本卡成功止于纯内存核心的 `HUMAN_GATE_DECISION_MEMORY_VALIDATED`。完成后执行端停止本轮实施并移交 GPT 验收；通过后由 GPT 按持续授权制定 **P2** 有界任务（持久化/恢复、宿主接线，Gate1/Gate2 分阶段验收），**不因 P1 通过自动放行**。人类继续保留每批次 Gate 决定与审计判断权；U1—U4（持久化、宿主接线与放行字段、真实初判 P3、AI/终判）均未在本卡范围。
