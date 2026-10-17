# TASK-059：一键对账启动器（双击出 HTML 到输出文件夹）

分类 C；Architect 设计、执行端实施、Architect 独立验收。前置：**TASK-058 ACCEPTED**。依据 `DSH-SCOPE-20261017-07` D-IO-2/3：静态页面不能起进程；用根目录双击启动器 `一键对账.cmd` 调 `scripts/run_all.py`，顺序跑完并输出 `outputs/<run_id>/index.html`。

## 1. 允许写入

- 新增 `scripts/run_all.py`（编排器，仅标准库）、`一键对账.cmd`、`config/run_all.json`；
- 新增 `tests/test_run_all.py`、`docs/RUN_ALL_GUIDE.md`、`docs/EXEC_REPORT_059.md`；
- 新增证据根 `data/runtime_initial_judgment_recording_tests/task059_*/`、输出根 `outputs/`（本卡运行产物）。
- **不允许修改任何既有文件**（changed=0），包括所有生成器、核对器、输入根。

## 2. 使用方式

```text
双击  一键对账.cmd
  → .venv\Scripts\python.exe -B scripts\run_all.py --open
  → 依次执行：
     1) task043 输入契约校验（input_contract_v1.py）
     2) GL 输入契约校验（gl_input_contract_v1.py）
     3) 运行层演示（run_runtime_demo.py，新运行根）
     4) 证据链索引（build_trace_index.py）
     5) GL 六类核对（reconcile_gl_v1.py）
     6) 站点（build_drilldown_site.py）
     7) Excel 底稿（build_excel_workbook.py）
     8) 可选：审阅合并（apply_review_notes.py，若配置了审阅记录）
  → 输出 outputs/<run_id>/（index.html、gl/、excel/、logs/、run_summary.json）
  → --open 时用系统默认浏览器打开 index.html
```

- `config/run_all.json`：输入根（批次、task043 输入、GL 根）、输出根、是否打开浏览器、可选审阅记录路径；相对项目根解析。
- `--run-id` 可指定；缺省 `run_YYYYmmdd_HHMMSS`（仅目录名，不写入产物内容）。
- `.cmd` 采用 `chcp 65001`、`-B`、结束 `pause`，便于非技术用户看到结果；另在指南给出 PowerShell 备用命令。

## 3. 行为约束（硬性）

1. **只读输入**：批次、task043、GL 根在运行前后字节不变；任何漂移立即停止。
2. **每次新目录**：`outputs/<run_id>/` 必须不存在；不覆盖旧运行；不清理旧证据。
3. **失败即停**：任一步非零退出，写 `run_summary.json`（`steps[]`：id/命令/退出码/错误字段），**不生成/不发布半成品 index.html**；整体 exit 1。
4. **不联网、不安装依赖**；`run_all.py` 只调用项目内脚本与标准库。
5. **成功判据**：七步全 0 且 `index.html` 存在，`run_summary.overall=SUCCESS`；否则 `FAILED`。
6. 汇总中附"未执行项"（函证/监盘/期后付款等），并写边界横幅。

## 4. 测试与证据

1. 正常：用已接受输入跑一遍 → exit 0、`outputs/task059_run_01/index.html` 存在、`run_summary.json` 七步 SUCCESS、`gl/` 报告、`excel/证据链底稿.xlsx` 存在；`--open` 不在测试中真正弹浏览器（用 `--no-open`）。
2. 负例：task043 输入缺文件 → 第 1 步失败、exit 1、无 index.html；GL 契约坏 → 第 2 步失败；输出目录已存在 → 拒绝（exit 2）。
3. 只读：运行前后输入根/批次哈希不变；`outputs/` 只新增本 run 目录。
4. 启动器：`一键对账.cmd` 存在、含 `run_all.py` 调用与 `pause`；`config/run_all.json` 路径可解析。
5. 确定性：同一 `--run-id` 内容（除 source 路径字段）一致；不同 run-id 不覆盖。
6. 证据 `task059_evidence_01/`：成功/失败运行日志、run_summary、哈希快照。

## 5. 保护与停止

一次全树扫描，基线 = TASK-058 接受基线：既有 changed 必须为 0；新增仅限 §1 与架构端已知增量（决策记录与本卡逐确切路径登记）；missing/读取错误/未登记新增 0；139/27/326/19/TASK-030 41 B 锁继续冻结。交付后停止待验收；不改看板、不接 AI/终判。

真实批准 `null`、真实初判未保存、0008、`next/AI=false`；一键运行只做机器核对与出页，不构成审计结论。
