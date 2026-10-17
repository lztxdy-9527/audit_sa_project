# TASK-059-R1：一键启动器测试可重复运行（临时 out-root + 唯一 run-id）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-058-R1 ACCEPTED**（205561 / `0dbdaa6a…`）；TASK-059 为 **NOT_ACCEPTED**（`docs/reviews/REVIEW_TASK_059.md`，B1：测试用固定 run-id，重跑被“目录已存在”挡住）。

## 1. 允许修改/新增

**允许修改（changed 恰两件）**：`tests/test_run_all.py`、`docs/RUN_ALL_GUIDE.md`。
**允许新增**：`docs/EXEC_REPORT_059_R1.md`、证据根 `data/runtime_initial_judgment_recording_tests/task059r1_*/`。
**禁止**：改 `scripts/run_all.py`（引擎行为已通过独立复验）、启动器、配置、其他生成器/核对器、既有输入/证据、看板。

## 2. 必须修复（B1）

1. 测试使用**临时 out-root**（如 `data/runtime_initial_judgment_recording_tests/task059r1_test_out_<pid>_<n>` 或系统临时目录）与**每次唯一 run-id**，不得复用 `outputs/task059_run_01` 等既有目录；
2. 测试结束清理自己创建的临时 out-root（或保留但唯一命名；不得删除项目既有证据）；
3. 在**已有 `outputs/`（含既有 run 目录）**的工作区连续运行两次，两次均 **6/6 PASS**；
4. 六个用例语义不变：正常七步/拒绝覆盖/输入缺文件/GL 契约坏/启动器与配置/确定性；
5. 只读断言不变：批次、task043、GL、账务库前后哈希一致。

## 3. 验收方式（架构端）

- 我在当前工作区连续运行 `tests/test_run_all.py` **两次**，均 6/6；
- 另用独立 run-id 重跑七步成功、两类失败、确定性；
- 保护扫描：基线 205561，既有 changed 为 0（059 文件尚未接受）；新增逐路径登记。

## 4. 保护与停止

一次全树扫描，基线 = TASK-058-R1 接受基线（205561 / `0dbdaa6a…`）：**既有 changed = 0**；新增仅限 §1 与架构端已知增量；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不改看板、不接 AI/终判。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；一键运行只做机器核对与出页，不构成审计结论。
