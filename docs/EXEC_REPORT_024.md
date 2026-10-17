# TASK-024 执行回执（Gate1 决定保存与限定历史核验适配器）

任务：按 `docs/tasks/TASK-024_DRAFT.md`（**C 类，GPT 设计 + DSH 执行**）实现并交付；前提为
`docs/reviews/REVIEW_TASK_023_R2.md` 的 **ACCEPTED** 与最终保护登记。
日期：2026-10-14。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：本卡只新增 `scripts/record_demo_human_gate1.py`、`tests/test_record_demo_human_gate1.py`、
`docs/HUMAN_GATE1_DECISION_GUIDE.md`、`docs/EXEC_REPORT_024.md` 与 `data/human_gate1_decision_tests/
task024_*`、`data/batches/task024_*`、`data/human_gate_decision_records/gate1/task024_*`；
**所有既有文件冻结未改**（保护比较 `changed=[]`）。未接宿主/控制器、未执行标准化/DB/筛查、未接 Gate2、
未产生 `0009`/真实初判/AI/终判；`execution_allowed`/`workflow_connected`/`ai_enabled` 严格 false；
不把 `APPROVE` 解释为执行许可。测试人类字段只来自登记夹具，外层标 `PROTOCOL_TEST_FIXTURE_ONLY`。

---

## 1. 起点基线（实读）

| 项 | 值 |
| --- | --- |
| 验收结论 | `data/reviews/task023_r2_gpt_20261014_034254/review_result.json` → **ACCEPTED** ✅ |
| 基线 | 同目录 `source_hashes_after.json` = `514fd954e644b4869406278d45e00c07df6db738bd3d0e96355cd5eba5ae31d4`、**143274** 项、两个确切自指元数据排除 |
| 冻结身份 | 准备器 `ce23671f…0ac4`、存储 `594e42d0…48e7`、P1 `5ccdd0f3…4e79`、配置 `ae4caa38…fb7c`、宿主 `38869681…a307`、正式契约 `174a021b…`、生效登记 `042086cb…` **全部一致** |
| 交付前状态 | 四个新交付文件均不存在；`data/human_gate_decision_records/gate1` 不存在（本卡首次按需建立） |

## 2. 交付文件（写后实读）

| 文件 | SHA-256 | 字节 |
| --- | --- | --- |
| `scripts\record_demo_human_gate1.py` | `c002243ade1332e9e56ecd0a2b932a100c1d9f57191983f5689751e4f7fbd650` | 53998 |
| `tests\test_record_demo_human_gate1.py` | `50f1268ea7ca8871eeb6405e5ac2ebec9c7d743e90a2868b493b35689d48df6c` | 51059 |
| `docs\HUMAN_GATE1_DECISION_GUIDE.md` | 见 §7.1 登记 | — |
| `docs\EXEC_REPORT_024.md` | 自身最终 SHA **只在交接消息给出** | — |
| 夹具登记 | `data\human_gate1_decision_tests\task024_dev_01\fixtures\TASK024_G1_HOLD_0002.json` = `8e3cf5670e91f3c48776360ab8fc22b6fef3f9bce76f56d3793804142b5cd4fa`（927）、`FIXTURE_REGISTRATION.md` = `c86d1c801a85629f30a58eaefd1554ee51864e4e0ae4a5c914f32dfd8097a6ce`（2583） | — |

## 3. 三个公开 API（无 CLI）

prepare 六键（`request_version=TASK-024-human-gate1-decision-request-1.0`、
`status=…REQUEST_PREPARED`、materials 七键、expectations 八键、evidence 七键、**原七项** false 边界）；
save/verify 恰九键（`adapter_version=TASK-024-human-gate1-adapter-1.0`、
`status` = `HUMAN_GATE1_DECISION_RECORDED`/`…VERIFIED`、`scope=LOCAL_GATE1_DECISION_RECORDS_ONLY`、
`identity{batch_id,event_id,decision}`、`record_fingerprint`、`event_dir`/`scope_dir`、`store_result`、
六项 false `boundaries`）。`scope_dir=None` → 结构化 Blocked `scope_dir`（不默认空历史）。
下游冻结 prepare/store 的 field/reason 与原因链原样透传（前缀 `prepare.`/`store.`）。

## 4. 新层绑定与独立预期

每次真实调用冻结 `prepare_human_gate1_request` 一次并只消费其经核验返回；扩展为 **32 项材料 / 14 项代码**：
`code_manifest.entries` 14 项（UTF-8 升序唯一）、`materials.files` 32 项（旧 31 项不删改）、
`run_binding.code.file_sha256` = 本层适配器实际字节、`manifest_fingerprint` = 14 项规范指纹、
`rules`/`config`/`input`/`contract` 原绑定；`materials_fingerprint` 由冻结 P1 公开
`materials_body`+`fingerprint` 复算；八键 expectations 由本次读数重建。最终确认（全部必要消费之后）逐项
复读 32 份白名单字节/SHA、复查路径逐级无链接、复算材料指纹。

## 5. 实际运行与计数（正式轮次 `task024_run_03`）

```text
.venv\Scripts\python.exe -B tests\test_record_demo_human_gate1.py \
    --out-dir data\human_gate1_decision_tests\task024_run_05
→ TASK-024 测试组：44 项检查，0 项失败；prepare 2、save 22、verify 13、接收器 3、
   冻结 store.save 实际调用 14、冻结 store.verify 实际调用 8
→ 退出码 0；summary PASS 44/0；台账 5 项；pending/disk 审核 ok；byte_drift=[]
```

| 作用域 | 实测 | 说明 |
| --- | --- | --- |
| 本层 API | prepare 2 / save 22 / verify 13 | 每次完整返回或异常+traceback+原因链单份保存 |
| 冻结 `store.save` | **14** | 计数器真实包裹冻结函数（不改行为） |
| 冻结 `store.verify` | **8** | 历史核验的 P1 复算另计，不并入新提交 |
| 冻结接收器 CLI | **3** | 样本 A/B/仅币种 USD（退出码 0/0/1） |
| 生产源与历史 | 只读 | 未读历史业务源文件；未接宿主/DB/Gate2 |

## 6. 验收点关闭证据（对应卡 §8）

1. **准备与绑定**：六键形状/新层常量/原七项 false、32 项材料与 14 项代码、`code.file_sha256`=适配器字节
   且与材料项一致、材料指纹独立复算一致、相同输入 canonical 相等且无 submission 痕迹（清单 3/4/5）。
2. **真 save + verify**：正常批次 A + 登记夹具 `FIXTURE-EV-G1-0001` + APPROVE → `RECORDED`；封套
   context 9 键/receipt 10 键/snapshots 恰六文件/scope 仅本事件；`verify` → `VERIFIED` 且
   `record_fingerprint` 与 save 一致（清单 6/11/13）。
3. **历史与追加**：同 scope revision 2（批次 B + 新登记夹具 `FIXTURE-EV-G1-0002`/HOLD）→
   `prior_events` 完整引用 event_0001（5 键、六快照）、`prior_history` 三键 wrapper、
   `prior_history_fingerprint` 闭合为 True；独立 scope 中“先 HOLD 后 APPROVE”成功（合法 HOLD 不被一律
   拒绝）；同批次已有 APPROVE 后再次提交被真实 P1 拒绝且不建事件（清单 10，清单 20 部分）。
4. **质量阻断**：USD 材料 + APPROVE 由真实 P1 拒绝、不建事件、不留锁；USD + HOLD 合法记录。
5. **参数与路径反例**（10 例，全部结构化拒绝且不建事件）：`scope_dir` 缺省 / 越界 / 不存在、
   event_dir 已存在（空目录，独立 scope）/ 非直接子目录、错批次声明、错材料绑定、模拟 actor、占用锁
   （`scope_dir.lock`，旧锁保留）、**真实 junction**（`mklink /J` 建立的 scope 链接，`is_reparse=true` →
   Blocked `scope_dir`，事件未建）；scope 成员集合保持仅本次注入的锁。
5b. **守卫（真实 I/O 通道）**：在正常 save+verify 期间包裹 `io.open`/`builtins.open`/`os.open`/
   `socket.socket`/`subprocess.Popen` → 网络/子进程尝试 **0**、scope 外写入 **0**、生产源三文件字节
   不变，全部写入均落在本 scope（锁 + 事件八文件，≥9 次）。
6. **历史枚举反例**（8 例，全部阻断不跳过）：缺 receipt、缺六快照之一、事件目录未知项、封套 identity
   矛盾、revision 非严格 1、事件含 failure 诊断、scope 存在锁、scope 未知项。
7. **真实源晚变更**：包装**真实**冻结 `store.save` 返回值后给本轮源 `checks/quality_report.json` 追加一个
   LF（不更新哈希）→ 本次 save 拒绝（`BLOCKED`，`stage=final_confirmation`，
   `field=batch/checks/quality_report.json`），failure 7 项协议字段且现场保留；恢复原字节后 `verify`
   仍拒绝失败事件（失败事实不被抹掉）；未写 failure 的只读核验路径同样拒绝当前源已变化的记录。
8. **封套 writer 两例**：context 半写 OSError → `Error`（`stage=context_write`）+ failure 有效 + 半写
   context 与完整 snapshots 现场保留；receipt 完整写后 sentinel（追加字节）→ 读回不一致拒绝 + failure
   有效 + receipt 现场保留（末字节仍为哨兵）。
9. **证据终审与分离故障**：载荷内存定稿 → 一次性写入 → 同缓冲读回 → 登记审核（总数/分类型计数/
   case_id 唯一/记录完整/样本与检查闭合）→ 同一审核的隔离控制（删一条登记拒绝、改出重复 case_id 拒绝）
   → 字节漂移确认（0）；**分离轮次** `task024_fault_01` → 套件 `task024_fault_04`：首轮读数前从磁盘
   `calls.json` 删一条完整登记（声明总数 33、候选 32）→ **返回 1 / summary FAIL / failures 非空**，
   审核定位“调用登记 32 与声明总数 33 不一致”“prepare 登记数与声明不一致”，候选**未回填/未重建**，
   harness 6/6 断言通过（清单 20）。
10. **夹具登记**（按 GPT 裁决执行“先登记后调用”）：新夹具全文+来源（GPT 2026-10-14 架构答复，经人类
    转交）+身份 SHA 已登记；两个事件的 `event_id`/`actor`/`decided_at_raw`/`reason`/`decision` 均来自
    登记来源，程序只按冻结 schema 组装 `submission_version`/`request_binding`/`prior_decision_binding`。

## 7. 保护（定稿后一次全树比较）

- 基线：`data/reviews/task023_r2_gpt_20261014_034254/source_hashes_after.json`
  （`514fd954…31d4`、**143274** 项、ACCEPTED）；仅两个确切自指路径排除，`prefix_exemption_used=false`。

### 7.1 结果与最终身份

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **146503** |
| `changed` | **`[]`**（本卡只新增文件，未改任何既有文件） |
| `missing` / 读取错误 / 范围外变化 / 范围外新增 | **0 / 0 / 0 / 0** |
| 新增登记 | **3229** 项：本卡 4 个新增端文件（适配器/测试/指南/回执）+ 本轮 `task024_*` 证据/故障容器与批次根、`gate1/task024_*` 记录根，逐确切路径登记（含早期命名轮次 `dev_02`/`dev_06_s1..s3` 作为过程容器显式登记），无前缀兜底 |
| 扫描后动作 | 仅有限登记本回执身份（本节与 §2）；未再改实现 |

## 8. 过程问题、口径更正与未执行（如实登记）

1. **口径更正**：本卡看板清单第 17 项写“失败诊断恰**八**键”，而卡 §92 原文列举的是 **7** 项
   （`failure_version`/`status`/`stage`/`field`/`reason`/`exception_chain`/`boundaries`）。实现与测试按
   **卡原文 7 项**执行，看板文字以本条为准更正。
2. 测试侧定点修正（保留过程容器 `task024_dev_*`/`task024_fault_*`）：把 store 反向包装装到了错误的模块
   对象（应包装适配器实际加载的 `load_frozen_store()`）；“event_dir 已存在”反例最初污染了共享 scope
   导致后续反例先被历史枚举拒绝（已改独立 scope）；`evidence_audit` 需比较声明总数与分类型计数才能
   察觉“删一条登记”；`run_suite_main` 抽出以便分离故障轮次调用真实套件。
3. 真实终审顺序与失败写入顺序未改（仍为“定稿→一次写入→同缓冲读回→审核→漂移确认→正常只写台账”），
   故未重跑旧 checks LF 故障与 TASK-021/022/023 套件。
4. **未执行**（记 `null`/`not_executed`）：宿主/控制器接线、存储之外的历史入口、标准化/装载/DB/筛查、
   Gate2、真实初判、`0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨 scope 历史发现；
   子进程内部未知函数次数记 `null`。真实 junction 反例与下游业务/网络守卫已在终版套件中执行（见 §6.5/§6.5b）。

## 9. 绝对路径

- `D:\harness work\audit_sa_project\scripts\record_demo_human_gate1.py`
- `D:\harness work\audit_sa_project\tests\test_record_demo_human_gate1.py`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE1_DECISION_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_024.md`
- `D:\harness work\audit_sa_project\data\human_gate1_decision_tests\task024_run_03\`
- `D:\harness work\audit_sa_project\data\human_gate_decision_records\gate1\task024_run_05_s1\`

## 10. 停止点

完成本卡后执行端停止实施并交 GPT 验收；**验收通过前不制定或实施下一阶段（Gate2/真实初判）**；
不生成真实批准、`0009` 或 AI 决定。真实批准仍 `null`、宿主开发态 `0008`、`next=false`、AI 未开放；
人类继续负责业务判断与看板。若需改冻结 prepare/store/P1/契约/配置/宿主，或改本卡 32 项/封套/历史/锁/
执行边界，立即停止受影响处理、保留现场并报告重新定界升级。
