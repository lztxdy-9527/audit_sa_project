# TASK-023 执行回执（Gate1 真实文件材料与只读候审请求适配器）

任务：按 `docs/tasks/TASK-023_DRAFT.md`（**C 类，GPT 设计 + DSH 执行**）实现 Gate1 只读候审请求适配器；
前提为 `docs/reviews/REVIEW_TASK_022_R4.md` 的 **ACCEPTED** 及其最终保护登记。
日期：2026-10-14。执行/测试/调试：DeepSeek；Architect/Reviewer：GPT；业务决定与真实批准：人类主理人。

**范围声明**：本卡**止于只读准备**。未提交/保存任何 Gate 决定，未调用存储 save/verify，未枚举历史记录，
未接开发宿主/控制器，未执行标准化/装载/筛查，未构造真实流程检查点或 `0009`，未处理 Gate2/真实初判/
AI/终判。**所有既有文件冻结未改**（保护比较 `changed=[]`）。`status=HUMAN_GATE1_REQUEST_PREPARED` 与
质量 OK **都不是批准**；快照保存/候审准备 ≠ 批次批准 ≠ 运行放行 ≠ 身份认证 ≠ 来源真实性证明。

---

## 1. 起点基线（先核验后实施）

| 项 | 值（实读） |
| --- | --- |
| 验收结论 | `data/reviews/task022_r4_gpt_20261014_004745/review_result.json` → **verdict=ACCEPTED** ✅ |
| 保护基线 | 同目录 `source_hashes_after.json` = `d36260d94df374d1f2ccd90e2b2127c1b599b075ecb9ff870a842b82d0a5a5c9`、**140077** 项（两个确切自指元数据排除） |
| 存储（冻结） | `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7` ✅ |
| P1（冻结） | `5ccdd0f32e1f3b28bc00a168cbbcfb10725414811ae388f7af0da8b16a444e79` ✅ |
| 宿主 / 控制器（冻结） | `3886968135459992ccd37b0b015c114d1cf0e65bf9505429a52136a3495ca307` / `a6b7b8e18249c4a70d8dc3db66ee1ec9c62af9efe2b45ee396d56aeb79ce3a8c` ✅ |
| 接收器 / checker（冻结） | `5219562017d15f1f3d4e19485225568f00929fbae8b31784205de618fe941df6` / `a7e5eb6797f4635ade4fbbc4bcc5c00e561a03e04f6bd232cd66fc1dbfb2c2e8` ✅ |
| 正式契约 / 生效登记 | `174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad` / `042086cb90066da45f78f185d2358447166ec11bc809186837d7c15ff8fa061d` ✅ |

## 2. 交付文件（写后实读）

| 文件 | 说明 | SHA-256 | 字节 |
| --- | --- | --- | --- |
| `scripts\prepare_demo_human_gate1.py` | 适配器（唯一公开入口，只读） | `5e8ed565cc6567b210c65c475ec16a8e2f271da49b4bcb6a745cad6cb329da02` | 48689 |
| `tests\test_prepare_demo_human_gate1.py` | 测试与证据入口 | `4e7662f599c665ea3ea43fc6809c2ae25c863c79cdc537ea73efed0ec3c9dcae` | 59101 |
| `config\human_flow_v1.json` | 固定合成业务范围配置（非批准/放行配置） | `ae4caa38a4f029cf1eb8ccb023176712da5ad9cd969afe907d3d54fdfaedfb7c` | 219 |
| `docs\HUMAN_GATE1_REQUEST_GUIDE.md` | 使用与边界指南 | `0230ac8787743f002adbe27dab275d4697b60ab304cce335c06ffca1c3e6458f` | 9433 |
| `docs\EXEC_REPORT_023.md` | 本回执 | 自身最终 SHA **只在交接消息给出** | — |
| `data\human_gate1_request_tests\task023_run_01\` | 正常轮次证据容器（12 项载荷台账） | 见 `evidence_ledger.json` | — |
| `data\batches\task023_run_01\` | 同轮批次根（5 个真实接收样本 + 负向隔离副本） | 见 `sample_build_records.json` | — |
| `data\batches\task023_dev_01…dev_05\`、`data\human_gate1_request_tests\task023_dev_01…dev_05\` | 过程容器（保留、不回写） | — | — |

## 3. 实际运行、调用与来源

```text
.venv\Scripts\python.exe -B tests\test_prepare_demo_human_gate1.py \
    --out-dir data\human_gate1_request_tests\task023_run_01
→ TASK-023 测试组：52 项检查，0 项失败；prepare 调用 22、真实 P1 调用 3、接收器运行 5
→ 退出码 0
```

| 作用域 | 实测 | 来源 |
| --- | --- | --- |
| 公开 `prepare_human_gate1_request` 调用 | **22**（prepared 7 / blocked 14 / error 1） | `api_records.json`、`prepare_registry.json` |
| 真实冻结 P1 调用 | **3**（= 入口代码帧观察 3，闭合） | `p1_call_records.json` |
| 冻结接收器 CLI 真实运行 | **5**（`normal`/`currency_usd`/`no_allocations`/`late_change`/`count_tamper`，退出码 0/1/1/0/0） | `sample_build_records.json`（含 argv/stdout/stderr） |
| 内部 checker | 每次接收由接收器自己启动（退出码见上，`report_result=pass/issues_found`），**未单独直调** | 同上 |
| helper | 冻结接收器只读 `validate_report`（只做结构验证，不执行其 CLI） | 适配器 §5 |
| 子进程（测试侧） | 5 次接收器 CLI + 1 次真实 junction 建立；内部未知函数次数记 `null` | `sample_build_records.json`、`late_change_records.json` |
| 生产 prepare 的 P1/存储调用 | **0 / 0** | `guard_records.json`（业务模块导入计数 0） |

## 4. 样本、正常与阻断结果

三个主样本由**冻结接收器 CLI** 在同轮新批次根真实构造（原 fixture `data\generated\demo_20260930_a\fixtures\C06b.xlsx` 只复制不改）：

| 样本 | 构造 | 接收/checker 退出码 | 报告 | issues | 适配器映射 |
| --- | --- | --- | --- | --- | --- |
| `C06b_normal` | 原样复制 | 0 / 0 | `pass` | `[]` | 质量 **OK**（三列表全空） |
| `C06b_currency_usd` | 仅 `payables.currency` 行 2 改 `USD` | 1 / 1 | `issues_found` | `CURRENCY_INVALID` | 质量 **BLOCKED**（入 `quality_blockers`） |
| `C06b_no_allocations` | 仅删除 `allocations` 工作表 | 1 / 1 | `issues_found` | `MISSING_SHEET` | 质量 **BLOCKED**（入 `structural_blockers`） |

公开 API 验收：外层恰六键、`materials` 七键、`expectations` 八键、`evidence` 七键、`boundaries` 七项严格
false；`materials.files` **31 项**，其字节长度与 SHA 由测试用标准库**独立复算**逐一比对全等（未使用生产
helper 作期望）；`materials_fingerprint` 由测试独立 canonical 复算一致；`expectations` 的
`expected_request_id` **原样**（含前导零/64hex 形状/指令样式文本三种输入）、`expected_prior_gate1=null`、
`expected_files` 31 项与 `materials.files` 双向一致；相同输入重复调用**规范字节相等**；改返回不影响后续
调用（深拷贝无别名）；`evidence` 前五项与同轮 `batch_manifest.json` 原文逐项一致。

**兼容性（仅在测试内直接调用冻结 P1，各一次并完整登记）**：正常材料 + 显式 `PROTOCOL_TEST_FIXTURE_ONLY`
submission 与显式历史夹具 → `HUMAN_GATE_DECISION_MEMORY_VALIDATED`；BLOCKED 材料 + `HOLD` → 同样 VALIDATED
（质量 BLOCKED 如实进入记录）；BLOCKED 材料 + `APPROVE` → 被真实 P1 拒绝（`submission.decision`）。P1 记录
`boundaries` 六项严格 false 原样；**未写任何决定叶目录**。

## 5. 拒绝与故障定点

| 用例 | 注入形态 | 结果（定位） |
| --- | --- | --- |
| N01/N02 | 越界 `data/`、允许根 `data/batches/` 自身 | Blocked `batch_dir` |
| N03 | 副本加入 `normalized/`（下游产物） | Blocked `batch_dir` |
| N04 | 副本删除 `gate1_packet.md` | Blocked `batch_dir`（条目集合） |
| N05 | `batch_manifest.json` 写成 `[]` | Blocked `batch_manifest.json`（非对象 JSON） |
| N06 | 副本 `gate1_packet.md` 追加一字节 | Blocked `batch_manifest.json.gate1_packet.sha256` |
| N07 | `hashes.snapshot_written` 改为 `1` | Blocked `batch_manifest.json.hashes.snapshot_written`（严格布尔） |
| N08 | **真实新样本**的报告 `issue_counts_by_code` 改为 `{"FAKE":1}` 并同步 manifest 声明 SHA | Blocked `checks/quality_report.json.issue_counts_by_code`（计数与实际不符） |
| N09 | 副本 `code_snapshot/check_demo_data.py` 追加一字节 | Blocked `batch_manifest.json.code_snapshot.check_demo_data.py.sha256` |
| N10/N11 | `request_id` 纯空白 / 非字符串 | Blocked `request_id` |
| N12 | **真实 Windows junction**（`mklink /J`）指向正常样本 | Blocked `batch_dir`（reparse） |
| L0 | 无注入观察末次消费次序 | 正常返回；读取事件按真实通道记录 |
| L1 | **最后必要消费之后**仅给新样本 `checks/quality_report.json` 追加 LF（不更新哈希） | 本次即 Blocked `checks/quality_report.json`（最终确认发现字节变化） |
| L2 | 撤销注入 wrapper、保留磁盘变更再调用 | 仍 Blocked（声明 SHA 与实际不符） |
| L3 | 恢复本轮原件后调用 | 成功（全程只读、不写 failure） |
| L4 | **末次实读通道**注入一次受控 `OSError`（映射注入，非真实磁盘故障） | `Error(stage="final_read")` + 原因链含 `OSError`，命中 1，无输出写入 |

**守卫**：22 次公开调用期间 `write_ops_total=0`、`forbidden_total=0`（socket/子进程为 0）、下游业务模块
导入计数 0、批次目录与项目文件字节前后完全相等。

## 6. 证据收尾

- 12 项载荷台账逐文件实读一致（`missing=[]`/`unregistered=[]`；测试输入副本按**确切路径**登记，无目录前缀豁免）。
- 终审**同缓冲**读回后，`api_records`/`p1_call_records`/`prepare_registry` 三个**完整解析对象**与终审前
  定稿的真实观察预期按 **canonical JSON 字节**严格比较一致（`equal=true`）。
- 隔离自测：删一条真实 `prepare` 登记 → 真实 audit 拒绝、原件通过；把一条真实观察载荷改为
  `OK-TAMPERED` → 完整内容比较拒绝、原件通过。
- 审核失败支配返回码：任何内容/台账不一致都会追加正式 `failures`、`summary=FAIL`、返回非零并写
  `final_audit_diagnostic.json`；本轮正常入口无此类失败。

## 7. 保护（定稿后一次全树比较）

- 基线：`data/reviews/task022_r4_gpt_20261014_004745/source_hashes_after.json`（`d36260d9…a5c9`、
  **140077** 项、`ACCEPTED`）；只按该清单声明的两个确切自指元数据路径排除。

### 7.1 结果与最终身份

| 项 | 值 |
| --- | --- |
| 实扫文件数 | **140662** |
| 原有文件 `changed` | **`[]`**（本卡只新增文件，未改任何既有文件） |
| `changed_out_of_scope` / `missing` / 读取错误 / 范围外新增 | **0 / 0 / 0 / 0** |
| 新增登记 | **585** 项，全部落在：本卡 5 个确切新增文件（适配器 `5e8ed565…da02`、测试 `4e7662f5…dcae`、配置 `ae4caa38…fb7c`、指南 `0230ac87…458f`、本回执）+ `data/human_gate1_request_tests/task023_run_01` 与 `task023_dev_01…dev_05` + `data/batches/task023_run_01` 与 `task023_dev_01…dev_05`（逐确切路径登记，`prefix_exemption_used=false`） |
| 冻结身份 | 接收器 `52195620…df6`、checker `a7e5eb67…2e8`、存储 `594e42d0…48e7`、P1 `5ccdd0f3…4e79`、宿主 `38869681…a307`、控制器 `a6b7b8e1…3a8c`、正式契约 `174a021b…40ad`、生效登记 `042086cb…061d` **全部一致（mismatch=[]）** |
| 扫描后动作 | 仅有限登记本回执与指南身份（本节）；**未再改实现/测试/配置**，未重复全树扫描；junction 与全部旧现场保留未删除 |

## 8. 过程失败与未执行（如实登记）

1. **过程失败**：首轮实现中，证据收尾的目录快照对越界路径（`data/`、`data/batches/`）做了**全树递归哈希**，
   导致测试自旋被终止（现场保留在 `task022`…→ 本轮 `task023_dev_02` 之前的容器）；已改为**有界快照**
   （仅批次级小目录逐文件哈希，大目录只登记有界摘要）。随后两次失败分别为收尾顺序（`isolation_self_tests.json`
   在终审读回之后写入）与反例期望（副本叶目录名导致 `batch_id` 先被拒绝、注入点落在初始读取）——均定点修正，
   过程容器 `task023_dev_01…dev_05` 全部保留不回写。
2. 为让计数反例与晚变更探针走**真实接收样本**，本轮共真实运行接收器 **5 次**（3 个主样本 + 晚变更样本 +
   计数反例样本），比卡内最低要求多 2 次；如实登记为过程记录。
3. **未执行**：宿主/控制器接线与调用、存储 save/verify、标准化/装载/数据库/筛查链、Gate2、真实初判、
   `0009`、AI/终判、网络/UI/ERP、强身份认证、真实批次批准、跨目录历史枚举、R01—R04 计算、
   checker 内部未知函数次数（记 `null`）；未清理任何旧现场，未初始化 Git、未安装依赖。
4. 未发现需要修改冻结接收器/P1/存储/宿主/契约、改变 Gate 时序/材料/历史范围/执行边界或分类不适用的事项；
   未触发重新定界/升级。

## 9. 绝对路径

- `D:\harness work\audit_sa_project\scripts\prepare_demo_human_gate1.py`
- `D:\harness work\audit_sa_project\tests\test_prepare_demo_human_gate1.py`
- `D:\harness work\audit_sa_project\config\human_flow_v1.json`
- `D:\harness work\audit_sa_project\docs\HUMAN_GATE1_REQUEST_GUIDE.md`
- `D:\harness work\audit_sa_project\docs\EXEC_REPORT_023.md`
- `D:\harness work\audit_sa_project\data\human_gate1_request_tests\task023_run_01\`
- `D:\harness work\audit_sa_project\data\batches\task023_run_01\`

## 10. 停止点

完成本卡后执行端停止实施并交 GPT 验收；**技术验收通过前不推进任何 Gate 接线**；不生成真实批准、初判或
`0009`，不开放 AI。人类操作看板并作出业务决定，技术验收不能代签。若发现需要修改冻结接收器/P1/存储/宿主/
契约、改变 Gate 时序/材料/历史范围/执行边界，或本卡分类不适用，**立即停止受影响实施、保留现场、报告并
重新定界/升级**。持续制定下一卡的授权属于架构端，不授权执行端自行接线。
