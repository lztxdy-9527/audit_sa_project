# TASK-059-R1 执行回执：测试可重复运行

日期：2026-10-18。交付状态：按 `TASK-059-R1` 修复测试不可重复运行，**交独立验收**；
TASK-059 为 NOT_ACCEPTED（`docs/reviews/REVIEW_TASK_059.md`，`ae23c45c…`）；引擎/启动器/配置
行为不变、未改引擎文件。既有 changed = 0（基线 TASK-058-R1 接受快照
**205561 项 / `0dbdaa6a…`**）。

## 1. 改动身份（两件，实测）

| 文件 | 长度 | SHA-256 |
| --- | --- | --- |
| `tests/test_run_all.py` | 10662 B | `a654f8a8fb2bf21c…` |
| `docs/RUN_ALL_GUIDE.md` | 4576 B | `4304124cf35c72fa…` |

新增 `docs/EXEC_REPORT_059_R1.md` 与 `task059r1_*` 证据根；`scripts/run_all.py`、`一键对账.cmd`、
`config/run_all.json` 未改动。

## 2. 修复内容（B1）

- 测试每次运行生成**唯一 run-id**：`normal_<时间戳>_<随机>`、`bad_input_…`、`bad_gl_…`、
  `det_a_…`、`det_b_…`；run_all 的中间目录（task043/task059/task056r1/task057_* 的 `*_runall_*`、
  `task059_demo_*`）随之唯一，不再与历史运行冲突。
- 测试使用**本次专属输出根** `<out-dir>/outputs_<时间戳>_<随机>`，不复用 `outputs/task059_run_01`
  等既有目录；测试创建的目录唯一命名并保留（不删除项目既有证据）。
- 六个用例语义不变：正常七步、拒绝覆盖、输入缺文件、GL 契约坏、启动器与配置、确定性；只读断言不变。

## 3. 复验（实测）

在**已有 `outputs/` 与历史测试产物**的工作区连续运行两次：

- `task059r1_run_01` → **6/6 PASS**、`read_only_ok=true`；
- `task059r1_run_02` → **6/6 PASS**、`read_only_ok=true`；
- 两次输出根分别 `outputs_20261018_040055_dc7eb9`、`outputs_20261018_040409_d8c87a`（唯一命名）。

## 4. 证据

`task059r1_evidence_01/command.json`：两次运行命令/退出码/用例数、两次测试报告身份、
示例成功 run 的 `run_summary.json` 与日志、输入哈希快照。

## 5. 保护安排与判据

定稿后**一次**全树扫描（`task059r1_finalization/protection_scan.py`），基线 = TASK-058-R1 接受快照
（205561 项 / `0dbdaa6a…`）：**既有 changed 必须为 0**（本卡只改 TASK-059 未接受的两个新文件）；
其余全新增逐路径登记；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。

## 6. 边界

一键运行只做机器核对与出页，不构成审计结论；不修数据、不联网、不安装依赖。
真实批准 `null`、真实初判未保存、0008、`next/AI=false`。
