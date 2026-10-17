# TASK-010-R4 执行回执（只修 writer 验证的取值时点与完整字节证据）

任务：修复测试中「前后哈希都在事后读取」与「完整待写大小使用简化占位对象」两处假阳性。
日期：2026-10-11。执行端：DeepSeek。
依据：`docs/tasks/TASK-010-R4.md`、`docs/reviews/REVIEW_TASK_010_R3.md`。状态：完成并自检通过，**停住等复验**；未推进 TASK-011。

---

## 1. 结论摘要

| 缺口 | 修复 |
| --- | --- |
| **前后哈希取值时点** | `old_0001_before` 在**新故障批次副本创建完成后、目标故障调用发生前**取得（阶段标记 `before_fault_call`）；`old_0001_after` 在调用返回/异常捕获且文件句柄关闭之后取得（`after_fault_call_file_closed`）。两者与取值阶段、调用顺序一并保存到 `writer_proof.json`，并由 `guard_unchanged(before, after)` 断言相等（缺任一值也判失败） |
| **完整待写内容字节证据** | 删除 `workflow={}`、不完整 operation 与恒假表达式拼出的占位对象；改由测试代理 `FaultyHandle.write(text)` 在**实际被调用时捕获原生产 writer 传来的完整 text**，保存其 UTF-8 字节数、SHA-256 与完整 JSON 到新容器；断言该内容可解析为完整 checkpoint（7 个顶层键齐备）且部分文件字节数 >0 且小于该次真实完整 UTF-8 字节数 |
| **隔离判据自测** | 新增 `unchanged_guard_self_test`（并入 `self_tests.json`）：前后同值→通过、前后不同值→**必须判失败**、缺前置值→失败，另含**容器内新副本被改动**→判失败；不动任何真实历史文件，也不向正式 `failures` 塞假失败 |
| **checker 计数口径** | 在新回执与审计中区分：当前可读清单 **16**、H02 保留的原清单再确认 **1**、实际总数 **17**（`checker_runs_visible_manifests` / `checker_runs_backup_confirmed` / `checker_actual_total`），最终读回以实际总数比对 |
| **修改范围** | **只改 `tests/test_run_demo_workflow.py`**；宿主 `run_demo_workflow.py` 保持 `d42aeec3a4450d630507821e103e5b923c052e91e790644df143f5311e9475d0`，指南保持 `2c164eff0c6e46c5d3de372c0105ccf6736a1c19db7664ff8e3e0bac89038cb3`，未升宿主版本 |
| **开发验证** | 真实接收 **17**、checker **17**（可见 16 + 备份确认 1）、副本 **17**、writer 部分字节 **40** < 完整 **21168**、模拟决定 **3**、**真实批准 0**、故障注入 **26**；CLI start 16／status 33／record 17；公开宿主 API **9**、控制器造样 **3**；**测试失败 0，退出 0** |
| **历史保护** | R3 基线（24341 项）**只变化测试文件 1 项、缺失 0**；R2／R1／TASK-010 基线仍为核心/测试/指南三项累计变化；14691／13330／12546／10236／8547／6511／4902／874 全部 **0 变化、0 缺失** |

## 2. 文件与产物

| 文件 | SHA-256 |
| --- | --- |
| `tests\test_run_demo_workflow.py`（本轮唯一变更） | `852bf336cd2d259e43b4da9eee539a52f48253767c52ff9327f62e12015f5f8c` |
| `scripts\run_demo_workflow.py`（冻结未改） | `d42aeec3a4450d630507821e103e5b923c052e91e790644df143f5311e9475d0` |
| `docs\WORKFLOW_HOST_GUIDE.md`（冻结未改） | `2c164eff0c6e46c5d3de372c0105ccf6736a1c19db7664ff8e3e0bac89038cb3` |
| `docs\EXEC_REPORT_010_R4.md` | 本文件（新增） |

- 测试容器：`data\workflow_host_tests\task010r4_02`（164 个文件；新增 `writer_proof.json`、`writer_full_expected_checkpoint.json` 即真实完整待写内容、`self_tests.json`、`count_audit.json`、`final_readback.json`）。
- 批次与副本：`data\batches\task010r4_02`（34 个叶子目录 / 455 个文件）。
- 过程容器：`task010r4_01`（保留现场）。

## 3. 实际命令与退出码

```powershell
& $py -B -c "src = open(r'...\tests\test_run_demo_workflow.py', encoding='utf-8').read(); compile(src, 'x', 'exec'); print('compile OK')"   # 0
& $py -B '...\tests\test_run_demo_workflow.py' --out-dir '...\data\workflow_host_tests\task010r4_02'   # 0
```

```text
CLI 调用：start 16、status 33、record-simulated-decision 17；宿主 API 直接调用 9；控制器造样 3
真实接收启动 17 次（入口侧 13）、checker 运行 17 次（当前可读清单 16 + 备份确认 1；入口侧 12）、
批次副本 17 份、真实 writer 故障命中 1 次（部分字节 40）、模拟决定 3 条、真实批准 0 条、故障注入 26 次
[PASS] R3/R4 隔离自测：计数核验可发现缺留痕；故障匹配器要求类别+目标原因一致；前后哈希判据在同值通过、改动后判失败
[PASS] R2_COUNT_AUDIT 计数与调用记录一一对应（接收 17、checker 16、副本 17）
[PASS] R3_FINAL_ARTIFACT_READBACK 最终汇总与审计一次落盘并读回一致
测试失败 0；受保护文件前后哈希一致: True（18 个）
```

## 4. writer 证据（本轮核心，全部取自 `writer_proof.json`）

| 项目 | 值 |
| --- | --- |
| `old_0001_sha256_before`（阶段 `before_fault_call`） | `a4bcc64021a681ed6ea9d2555cbb98b64a8bdb891428920774219d8cd90a7a80` |
| `old_0001_sha256_after`（阶段 `after_fault_call_file_closed`） | `a4bcc64021a681ed6ea9d2555cbb98b64a8bdb891428920774219d8cd90a7a80` |
| 调用顺序 | `copy_batch → before_fault_call → record_simulated_gate1_decision → after_fault_call_file_closed → guard_unchanged` |
| 判据结果 | `guard_unchanged` = **True**（缺任一值即判失败） |
| 真实完整待写内容 | **21168 UTF-8 字节**，SHA-256 `9a86fc37a694a1b47a8fccf2fc152e92575257c0140245883d729cc97077bb91` |
| 完整内容可解析 | True；顶层键 `batch_id / checkpoint_version / host_manifest_file_sha256 / operation / previous_file_sha256 / revision / workflow` |
| 部分文件实际字节 | **40**（>0 且 < 21168；本例前 40 字符全为 ASCII，字符数与字节数一致，断言以实际文件字节数为准） |
| 打开／实际写入／抛错 | 1 / 1 / 1 |
| 异常链 | `WorkflowHostError`，`__cause__` = `OSError`，message 与 sentinel 完全一致 |
| 半文件与恢复 | 半文件保留；后续 `status` 拒绝；未报告提交成功；旧 `0001` 未被破坏 |

**隔离自测**（`self_tests.json`）：前后同值→True、前后不同值→**False（判失败）**、缺前置值→False、容器内新副本被改动→False；计数核验自测与故障匹配器自测同样通过，三项自测结果单列。

**checker 口径**：当前可读清单 16 + H02 备份清单确认 1 = 实际 17；不为该文案改动宿主或指南，也不回写旧回执。receiver 17、副本 17。

## 5. 历史保护、边界与未执行

- R3 保护基线 `data/reviews/task010_r3_20261011_123002/source_hashes_after.json`：24341 项，变化 **1**（仅测试文件）、缺失 **0**；R2／R1／TASK-010 基线仍为三项累计变化；14691／13330／12546／10236／8547／6511／4902／874 全部 0 变化、0 缺失；测试内建 18 个受保护文件前后一致；旧回执／任务卡／验收单、GPT 证据与历史现场未回写。
- 未安装依赖、未初始化 Git、未加生产测试开关、未改生产 writer；使用 `-B` 与禁写 bytecode，语法检查用编译源文本。
- 未执行：TASK-011、`prepare` Gate2、正式契约、真实 Gate、人类判断、AI 建议、标准化／SQLite／规则／底稿、并发／超时重试／安全隔离、无边界 fuzz，未重跑 TASK-002—009 全套。
- 本地哈希只证明字节一致，不证明来源真实；不提供身份认证；模拟决定只是开发态测试样例，**不是**真实批准。

## 6. 失败尝试

1. 将 checker 实际总数（17）写入 `summary` 后，最终读回仍与审计的可见数（16）比较 → 出现一次可复现的产物矛盾；改为读回时比较 `checker_actual_total`，并额外核验可见清单数，之后一次通过。
2. 前一轮遗留的占位 `expected_checkpoint_text`（368 字符下界）与真实捕获内容并存会造成两种口径 → 本轮删除占位对象，只用捕获到的真实完整内容字节数断言。
